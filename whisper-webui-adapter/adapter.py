"""
Whisper WebUI → OpenAI-compatible STT adapter.

Translates OpenAI /v1/audio/transcriptions requests into
Gradio API calls to a running Whisper-WebUI (jhj0517/Whisper-WebUI) instance.

Environment variables:
  WHISPER_WEBUI_BASE_URL  - e.g. https://whisper-webui.myia.io
  WHISPER_WEBUI_USERNAME  - Gradio auth username
  WHISPER_WEBUI_PASSWORD  - Gradio auth password
"""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
log = logging.getLogger("whisper-adapter")

WHISPER_WEBUI_BASE_URL = os.getenv("WHISPER_WEBUI_BASE_URL", "").rstrip("/")
WHISPER_WEBUI_USERNAME = os.getenv("WHISPER_WEBUI_USERNAME", "")
WHISPER_WEBUI_PASSWORD = os.getenv("WHISPER_WEBUI_PASSWORD", "")

# Shared httpx client with persistent cookies (Gradio auth)
_client: Optional[httpx.AsyncClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client
    _client = httpx.AsyncClient(verify=False, timeout=300.0)
    log.info("Adapter started — target: %s", WHISPER_WEBUI_BASE_URL)
    yield
    await _client.aclose()


app = FastAPI(title="Whisper WebUI Adapter", lifespan=lifespan)


async def _ensure_auth():
    """Authenticate to Whisper WebUI Gradio if not already."""
    # Try a quick check — if cookies are still valid we skip login
    r = await _client.get(f"{WHISPER_WEBUI_BASE_URL}/gradio_api/info")
    if r.status_code == 200:
        return
    # Login
    log.info("Authenticating to Whisper WebUI…")
    r = await _client.post(
        f"{WHISPER_WEBUI_BASE_URL}/login",
        data={"username": WHISPER_WEBUI_USERNAME, "password": WHISPER_WEBUI_PASSWORD},
        follow_redirects=True,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Whisper WebUI login failed: {r.status_code}")
    log.info("Authenticated OK")


async def _upload_file(file_bytes: bytes, filename: str) -> str:
    """Upload a file via Gradio upload endpoint, return server path."""
    await _ensure_auth()
    r = await _client.post(
        f"{WHISPER_WEBUI_BASE_URL}/gradio_api/upload",
        files={"files": (filename, file_bytes)},
    )
    r.raise_for_status()
    uploaded = r.json()
    log.debug("Upload response: %s", uploaded)
    # Returns a list of paths like ["/path/to/file"]
    path = uploaded[0] if isinstance(uploaded, list) else uploaded
    return path


async def _transcribe(file_ref: str, file_size: int, filename: str, language: str = "french") -> str:
    """Call the Gradio transcribe_file endpoint and poll for result."""
    # Build the 54-param data array with sensible defaults
    # [0] files — uploaded file reference (Gradio FileData format)
    file_data = [{"path": file_ref, "orig_name": filename, "size": file_size, "mime_type": "audio/wav", "url": None, "is_stream": False, "meta": {"_type": "gradio.FileData"}}]
    data = [
        file_data,  # [0] files
        "",          # [1] input_folder_path
        False,       # [2] include_subdirectory
        True,        # [3] save_same_dir
        "txt",       # [4] file_format
        False,       # [5] add_timestamp
        "large-v3-turbo",  # [6] model
        language,    # [7] language
        False,       # [8] translate to english
        5,           # [9] beam size
        -1.0,        # [10] log prob threshold
        0.6,         # [11] no speech threshold
        "float16",   # [12] compute type
        5,           # [13] best of
        1.0,         # [14] patience
        True,        # [15] condition on previous text
        0.5,         # [16] prompt reset on temperature
        "",          # [17] initial prompt
        0.0,         # [18] temperature
        2.4,         # [19] compression ratio threshold
        1.0,         # [20] length penalty
        1.0,         # [21] repetition penalty
        0,           # [22] no repeat n-gram size
        "",          # [23] prefix
        True,        # [24] suppress blank
        [-1],        # [25] suppress tokens
        1.0,         # [26] max initial timestamp
        False,       # [27] word timestamps
        "\"'¿([{-",  # [28] prepend punctuations
        "\"'.。,，!！?？:：\")]}、",  # [29] append punctuations
        3,           # [30] max new tokens
        30,          # [31] chunk length
        3.0,         # [32] hallucination silence threshold
        "",          # [33] hotwords
        0.5,         # [34] language detection threshold
        1,           # [35] language detection segments
        24,          # [36] batch size
        True,        # [37] offload sub model
        False,       # [38] enable silero VAD
        0.5,         # [39] speech threshold
        250,         # [40] min speech duration ms
        9999,        # [41] max speech duration s
        1000,        # [42] min silence duration ms
        2000,        # [43] speech padding ms
        False,       # [44] enable diarization
        "cuda",      # [45] device
        "",          # [46] HF token
        False,       # [47] offload diarization model
        False,       # [48] enable BGM remover
        "UVR-MDX-NET-Inst_HQ_4",  # [49] BGM model
        "cuda",      # [50] BGM device
        256,         # [51] segment size
        False,       # [52] save separated files
        True,        # [53] offload BGM model
    ]

    # Submit the job
    log.debug("Sending transcribe_file with %d params, file_data=%s", len(data), json.dumps(data[0])[:200])
    r = await _client.post(
        f"{WHISPER_WEBUI_BASE_URL}/gradio_api/call/transcribe_file",
        json={"data": data},
    )
    r.raise_for_status()
    event_id = r.json().get("event_id")
    if not event_id:
        raise RuntimeError(f"No event_id in response: {r.text}")
    log.info("Transcription submitted, event_id=%s", event_id)

    # Poll SSE endpoint for result
    # Gradio SSE format: "event: <type>\ndata: <json>\n\n"
    # Events: "generating" (progress), "complete" (final result), "error"
    result_text = ""
    current_event = ""
    async with _client.stream(
        "GET",
        f"{WHISPER_WEBUI_BASE_URL}/gradio_api/call/transcribe_file/{event_id}",
    ) as stream:
        async for line in stream.aiter_lines():
            line = line.strip()
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                payload = line.split(":", 1)[1].strip()
                log.debug("SSE event=%s data=%s", current_event, payload[:200])
                if current_event in ("complete", ""):
                    try:
                        parsed = json.loads(payload)
                        # Gradio returns a list: [output_files, transcription_text, ...]
                        if isinstance(parsed, list):
                            for item in parsed:
                                if isinstance(item, str) and len(item) > 0:
                                    result_text = item
                                    break
                        elif isinstance(parsed, str):
                            result_text = parsed
                    except json.JSONDecodeError:
                        # Raw text data
                        if payload and payload not in ("null", ""):
                            result_text = payload
                elif current_event == "error":
                    log.error("Gradio error event: %s", payload)
                    if payload and payload != "null":
                        raise RuntimeError(f"Whisper WebUI error: {payload}")

    if not result_text:
        log.warning("Empty transcription result — SSE stream may have unexpected format")
        return ""

    # Clean Gradio wrapper text.
    # Format: "Done in X seconds! ...\n\n----\n<filename>\n\n<actual transcription>"
    if "----" in result_text:
        parts = result_text.split("----")
        # Take the last part (after the separator)
        after_sep = parts[-1].strip()
        # Skip the filename line (first non-empty line)
        lines = after_sep.split("\n")
        # Find first blank line after filename, then take the rest
        text_start = 0
        for i, line in enumerate(lines):
            if i > 0 and line.strip() == "":
                text_start = i + 1
                break
        if text_start > 0:
            result_text = "\n".join(lines[text_start:])
        else:
            # Fallback: skip first line (filename)
            result_text = "\n".join(lines[1:]) if len(lines) > 1 else after_sep

    return result_text.strip()


@app.get("/v1/models")
async def list_models():
    """Return a fake models list for compatibility."""
    return {
        "object": "list",
        "data": [
            {"id": "whisper-webui", "object": "model", "owned_by": "local"},
            {"id": "whisper-1", "object": "model", "owned_by": "local"},
        ],
    }


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),
    language: Optional[str] = Form(None),
    response_format: Optional[str] = Form(None),
):
    """
    OpenAI-compatible /v1/audio/transcriptions endpoint.
    Proxies to Whisper WebUI via Gradio API.
    """
    if not WHISPER_WEBUI_BASE_URL:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "WHISPER_WEBUI_BASE_URL not configured"}},
        )

    lang = language or "french"
    t0 = time.time()

    try:
        # 1. Upload file to Gradio
        file_bytes = await file.read()
        log.info("Received %s (%d bytes), language=%s", file.filename, len(file_bytes), lang)
        file_ref = await _upload_file(file_bytes, file.filename or "audio.wav")
        log.info("File uploaded: %s", file_ref)

        # 2. Transcribe
        fname = file.filename or "audio.wav"
        text = await _transcribe(file_ref, file_size=len(file_bytes), filename=fname, language=lang)
        elapsed = time.time() - t0
        log.info("Transcription done in %.1fs: %s", elapsed, text[:100])

        # 3. Return OpenAI-compatible response
        if response_format == "verbose_json":
            return {"text": text, "language": lang, "duration": elapsed}
        return {"text": text}

    except Exception as e:
        log.exception("Transcription failed")
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e)}},
        )


@app.get("/health")
async def health():
    return {"status": "ok", "target": WHISPER_WEBUI_BASE_URL}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8787)
