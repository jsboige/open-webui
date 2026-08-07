#!/usr/bin/env python3
"""Fleet-wide audio preflight for Open WebUI (STT + TTS).

Reports, for every tenant, what the instance is ACTUALLY configured to call and
whether that call works end to end. Read-only: it changes no configuration.

Why this exists
---------------
The TTS 401 and STT 502 incidents were re-diagnosed by hand every cycle, from
throwaway scripts that were never committed. Worse, the hand diagnosis was
wrong about STT: the fleet does not call the Gradio WebUI directly, it calls a
local adapter container which then calls the Gradio WebUI. Probing the host that
"looks like" the STT service (stt.myia.io -> 200) said nothing about whether
transcription worked (500, fleet-wide). This script follows the real chain.

Chain resolution
----------------
When a tenant's STT base URL points at the in-cluster adapter
(``whisper-stt-adapter``), the adapter's own upstream is probed too, so the
report names the host that is actually failing rather than the nearest hop.

Secret hygiene
--------------
Keys are only ever rendered as ``len=N sha256:8hex`` (never a prefix/suffix of
the value). See scripts/README or the project memory note on mask hygiene.

TTS cache trap
--------------
Open WebUI caches speech by raw request body: replaying an identical payload can
return a cached 200 long after the credentials broke. Every speech probe here is
cache-busted with a unique nonce in the text.

Usage
-----
    python scripts/audio-preflight.py                 # all tenants
    python scripts/audio-preflight.py --tenant myia   # one tenant
    python scripts/audio-preflight.py --no-exercise   # config report only
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO_ROOT, ".env")

TENANTS = ["MYIA", "EPF", "ESG", "ECE", "EPF_GENAI", "EPITA", "PAUWELS"]

# Adapter base URLs whose real upstream lives elsewhere. Probing the adapter
# alone would report "up" while transcription is broken one hop further.
ADAPTER_UPSTREAM_ENV = {
    "whisper-stt-adapter": ("myia-open-webui-whisper-stt-adapter-1", "WHISPER_WEBUI_BASE_URL"),
}


def load_env(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip().strip('"').strip("'")
    return out


def mask(secret: str | None) -> str:
    """Render a secret as length + short non-reversible digest. Never a prefix."""
    if not secret:
        return "UNSET"
    return f"len={len(secret)} sha256:{hashlib.sha256(secret.encode()).hexdigest()[:8]}"


def request(url, data=None, headers=None, timeout=60, raw=False):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            payload = body if raw else json.loads(body.decode())
            return resp.status, payload, time.time() - started
    except urllib.error.HTTPError as exc:
        return exc.code, None, time.time() - started
    except Exception as exc:  # noqa: BLE001 - report transport failures verbatim
        return type(exc).__name__, None, time.time() - started


def wav_silence(seconds: float = 1.0, rate: int = 16000) -> bytes:
    """A minimal valid mono 16-bit PCM WAV, so the STT call is a real request."""
    frames = int(rate * seconds)
    data = b"\x00\x00" * frames
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return header + data


def multipart(filename: str, blob: bytes, field: str = "file") -> tuple[bytes, str]:
    boundary = "----owuiAudioPreflight7d91"
    buf = io.BytesIO()
    buf.write(f"--{boundary}\r\n".encode())
    buf.write(
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        f"Content-Type: audio/wav\r\n\r\n".encode()
    )
    buf.write(blob)
    buf.write(f"\r\n--{boundary}--\r\n".encode())
    return buf.getvalue(), f"multipart/form-data; boundary={boundary}"


def adapter_upstream(base_url: str) -> str | None:
    """Resolve the real upstream behind an in-cluster adapter, if we know it."""
    for marker, (container, var) in ADAPTER_UPSTREAM_ENV.items():
        if marker in (base_url or ""):
            import subprocess

            try:
                out = subprocess.run(
                    ["docker", "exec", container, "printenv", var],
                    capture_output=True, text=True, timeout=30, check=False,
                )
                value = (out.stdout or "").strip()
                return value or None
            except Exception:  # noqa: BLE001 - docker may be unavailable
                return None
    return None


def probe(url: str) -> str:
    status, _, _ = request(url, timeout=25, raw=True)
    return str(status)


def check_tenant(name: str, env: dict[str, str], exercise: bool) -> dict:
    url = env.get(f"{name}_URL")
    email = env.get(f"{name}_EMAIL")
    password = env.get(f"{name}_PASSWORD")
    result: dict = {"tenant": name.lower(), "url": url}

    if not (url and email and password):
        result["error"] = "credentials missing from .env"
        return result

    status, data, _ = request(
        f"{url}/api/v1/auths/signin",
        data=json.dumps({"email": email, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
    )
    if not data:
        result["error"] = f"signin {status}"
        return result
    auth = {"Authorization": f"Bearer {data['token']}"}

    status, config, _ = request(f"{url}/api/v1/audio/config", headers=auth)
    if not config:
        result["error"] = f"audio/config {status}"
        return result

    stt = config.get("stt", {}) or {}
    tts = config.get("tts", {}) or {}
    result["stt"] = {
        "engine": stt.get("ENGINE"),
        "base_url": stt.get("OPENAI_API_BASE_URL"),
        "model": stt.get("MODEL"),
        "key": mask(stt.get("OPENAI_API_KEY")),
    }
    result["tts"] = {
        "engine": tts.get("ENGINE"),
        "base_url": tts.get("OPENAI_API_BASE_URL"),
        "voice": tts.get("VOICE"),
        "model": tts.get("MODEL"),
        "key": mask(tts.get("OPENAI_API_KEY")),
    }

    upstream = adapter_upstream(stt.get("OPENAI_API_BASE_URL") or "")
    if upstream:
        result["stt"]["adapter_upstream"] = upstream
        result["stt"]["adapter_upstream_status"] = probe(upstream)

    if not exercise:
        return result

    body, content_type = multipart("silence.wav", wav_silence())
    status, _, elapsed = request(
        f"{url}/api/v1/audio/transcriptions",
        data=body,
        headers={**auth, "Content-Type": content_type},
        timeout=120,
        raw=True,
    )
    result["stt"]["transcriptions"] = {"status": status, "seconds": round(elapsed, 1)}

    # Cache-busted: OWUI keys its speech cache on the raw request body.
    nonce = uuid.uuid4().hex[:8]
    status, _, elapsed = request(
        f"{url}/api/v1/audio/speech",
        data=json.dumps({"input": f"preflight {nonce}", "voice": tts.get("VOICE") or "alloy"}).encode(),
        headers={**auth, "Content-Type": "application/json"},
        timeout=120,
        raw=True,
    )
    result["tts"]["speech"] = {"status": status, "seconds": round(elapsed, 1), "nonce": nonce}
    return result


def render(results: list[dict]) -> int:
    failures = 0
    for item in results:
        print(f"\n=== {item['tenant']} ===")
        if "error" in item:
            print(f"  ERROR: {item['error']}")
            failures += 1
            continue
        stt, tts = item["stt"], item["tts"]
        print(f"  STT  engine={stt['engine']!r} url={stt['base_url']!r} model={stt['model']!r}")
        print(f"       key={stt['key']}")
        if "adapter_upstream" in stt:
            print(
                f"       adapter upstream={stt['adapter_upstream']} "
                f"-> HTTP {stt['adapter_upstream_status']}"
            )
        if "transcriptions" in stt:
            probe_result = stt["transcriptions"]
            flag = "OK" if probe_result["status"] == 200 else "FAIL"
            print(f"       transcriptions: {probe_result['status']} in {probe_result['seconds']}s  [{flag}]")
            failures += probe_result["status"] != 200
        print(f"  TTS  engine={tts['engine']!r} url={tts['base_url']!r} voice={tts['voice']!r}")
        print(f"       key={tts['key']}")
        if "speech" in tts:
            probe_result = tts["speech"]
            flag = "OK" if probe_result["status"] == 200 else "FAIL"
            print(
                f"       speech: {probe_result['status']} in {probe_result['seconds']}s "
                f"(nonce {probe_result['nonce']})  [{flag}]"
            )
            failures += probe_result["status"] != 200
    print(f"\n{failures} failing probe(s).")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tenant", help="single tenant (e.g. myia); default: all")
    parser.add_argument(
        "--no-exercise",
        action="store_true",
        help="report configuration only, do not call transcriptions/speech",
    )
    parser.add_argument("--json", action="store_true", help="emit raw JSON instead of a report")
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    if not env:
        print(f"No .env found at {ENV_PATH}", file=sys.stderr)
        return 2

    names = [args.tenant.upper().replace("-", "_")] if args.tenant else TENANTS
    results = [check_tenant(n, env, not args.no_exercise) for n in names]

    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    return render(results)


if __name__ == "__main__":
    raise SystemExit(main())
