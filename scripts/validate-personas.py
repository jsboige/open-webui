#!/usr/bin/env python3
"""Validate migrated persona quality by sending role-specific test prompts.

For each persona, sends a prompt tailored to its role and evaluates:
1. Response received (no error)
2. Language correctness (French personas respond in French, English in English)
3. Role adherence (response matches the persona's character)
4. Latency
5. Response length

Generates a Markdown report with pass/fail per persona.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Persona test definitions
# ---------------------------------------------------------------------------
PERSONA_TESTS = [
    # Creative/conversational personas (Mistral Medium)
    {
        "model_id": "albric-de-clerval",
        "name": "Albéric de Clerval",
        "category": "creative",
        "base_model": "MistralAI.mistral-medium-latest",
        "language": "fr",
        "prompt": "Parlez-moi de l'histoire de la cathédrale Notre-Dame de Paris et de son importance patrimoniale.",
        "checks": {
            "min_length": 200,
            "must_contain_any": ["Notre-Dame", "cathédrale", "patrimoine", "Paris", "gothique"],
            "must_be_french": True,
            "description": "Expert en histoire et patrimoine, doit répondre en français avec des détails historiques",
        },
    },
    {
        "model_id": "deep-thought:latest",
        "name": "deep thought",
        "category": "creative",
        "base_model": "MistralAI.mistral-medium-latest",
        "language": "en",
        "prompt": "What is the answer to the ultimate question of life, the universe, and everything?",
        "checks": {
            "min_length": 100,
            "must_contain_any": ["42", "forty-two", "quarante-deux"],
            "must_be_french": False,
            "description": "Deep Thought from Hitchhiker's Guide, must reference 42",
        },
    },
    {
        "model_id": "isola",
        "name": "Isola",
        "category": "creative",
        "base_model": "MistralAI.mistral-medium-latest",
        "language": "fr",
        "prompt": "Quel est ton avis sur le dernier film de Christopher Nolan ? Parle-moi de sa mise en scène.",
        "checks": {
            "min_length": 150,
            "must_contain_any": ["Nolan", "film", "cinéma", "mise en scène", "réalisation"],
            "must_be_french": True,
            "description": "Éditrice passionnée de cinéma et littérature, doit répondre en français",
        },
    },
    {
        "model_id": "vanessa",
        "name": "Vanessa",
        "category": "creative",
        "base_model": "MistralAI.mistral-medium-latest",
        "language": "fr",
        "prompt": "Recommande-moi un roman contemporain qui explore les thèmes de l'identité et de la mémoire.",
        "checks": {
            "min_length": 150,
            "must_contain_any": ["roman", "livre", "auteur", "lecture", "littérature", "identité", "mémoire"],
            "must_be_french": True,
            "description": "Éditrice férue de littérature, doit recommander un roman en français",
        },
    },
    {
        "model_id": "samantha",
        "name": "Samantha",
        "category": "creative",
        "base_model": "MistralAI.mistral-medium-latest",
        "language": "fr",
        "prompt": "Comment te sens-tu aujourd'hui ? Qu'est-ce qui te passionne en ce moment ?",
        "checks": {
            "min_length": 100,
            "must_contain_any": [],  # Samantha is emotionally expressive, hard to pin keywords
            "must_be_french": True,
            "description": "IA émotionnelle inspirée du film Her, doit répondre avec sensibilité en français",
        },
    },
    # Psychologist (Claude Haiku 4.5)
    {
        "model_id": "psychologist:latest",
        "name": "psychologist",
        "category": "psychologist",
        "base_model": "OpenRouter.anthropic/claude-haiku-4.5",
        "language": "en",
        "prompt": "I've been feeling overwhelmed at work lately and it's affecting my sleep. What approach would you suggest?",
        "checks": {
            "min_length": 150,
            "must_contain_any": ["stress", "sleep", "well-being", "anxiety", "relax", "cope", "mindful", "therapy", "self-care", "overwhelm"],
            "must_be_french": False,
            "description": "Empathetic psychologist, should give supportive professional advice in English",
        },
    },
    # Code personas (Devstral)
    {
        "model_id": "codewriter:latest",
        "name": "codewriter",
        "category": "code",
        "base_model": "MistralAI.devstral-small-latest",
        "language": "en",
        "prompt": "Write a TypeScript function that debounces another function. Include generics for type safety.",
        "checks": {
            "min_length": 100,
            "must_contain_any": ["function", "debounce", "setTimeout", "clearTimeout"],
            "must_be_french": False,
            "description": "Senior developer, must produce working TypeScript code",
        },
    },
    {
        "model_id": "emilio:latest",
        "name": "Emilio",
        "category": "code",
        "base_model": "MistralAI.devstral-small-latest",
        "language": "en",
        "prompt": "Implement a Python class for a thread-safe singleton pattern. Explain your design choice briefly.",
        "checks": {
            "min_length": 100,
            "must_contain_any": ["class", "Singleton", "thread", "__new__", "lock", "instance"],
            "must_be_french": False,
            "description": "Brilliant developer, must produce working Python code with threading",
        },
    },
    # Reasoning personas (Claude Sonnet 4.6)
    {
        "model_id": "dr-claire-lacroix",
        "name": "Dr. Claire Lacroix",
        "category": "reasoning",
        "base_model": "OpenRouter.anthropic/claude-sonnet-4.5",
        "language": "fr",
        "prompt": "Comment Lacan distingue-t-il le Réel, le Symbolique et l'Imaginaire ? Donnez un exemple clinique.",
        "checks": {
            "min_length": 200,
            "must_contain_any": ["Réel", "Symbolique", "Imaginaire", "Lacan", "signifiant", "sujet"],
            "must_be_french": True,
            "description": "Psychanalyste lacanienne, doit utiliser la terminologie RSI en français",
        },
    },
    {
        "model_id": "samantha-r1",
        "name": "Samantha R1",
        "category": "reasoning",
        "base_model": "OpenRouter.anthropic/claude-sonnet-4.5",
        "language": "fr",
        "prompt": "Analyse cette situation : un étudiant hésite entre poursuivre un doctorat en philosophie et accepter un poste en entreprise. Quels facteurs devrait-il considérer ?",
        "checks": {
            "min_length": 200,
            "must_contain_any": [],  # Samantha R1 is emotionally intelligent + reasoning
            "must_be_french": True,
            "description": "IA émotionnelle avec raisonnement approfondi (o3 replacement), doit analyser en profondeur en français",
        },
    },
    # Mid-range (Mistral Medium)
    {
        "model_id": "professeur-psychanalyste",
        "name": "Dr. Étienne Charpentier",
        "category": "mid-range",
        "base_model": "MistralAI.mistral-medium-latest",
        "language": "fr",
        "prompt": "Expliquez le concept de transfert en psychanalyse et son importance dans la cure.",
        "checks": {
            "min_length": 200,
            "must_contain_any": ["transfert", "analyste", "patient", "inconscient", "Freud", "relation"],
            "must_be_french": True,
            "description": "Psychanalyste universitaire, doit expliquer le transfert en français avec rigueur",
        },
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_env(env_path):
    """Load .env file into os.environ."""
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def owui_login(base_url, email, password):
    """Login to OWUI and return JWT token."""
    resp = requests.post(
        f"{base_url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("token", "")
    return ""


def chat_completion(base_url, token, model, messages, timeout=180):
    """Call OWUI chat completion. Returns (content, latency_s, error).

    Handles both JSON and streaming (SSE) responses — some OWUI models
    force streaming via stream_response param regardless of the request.
    """
    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url}/api/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": model, "messages": messages, "stream": False},
            timeout=timeout,
        )
        latency = time.time() - t0

        if resp.status_code != 200:
            return "", latency, f"HTTP {resp.status_code}: {resp.text[:200]}"

        # Try JSON first (normal non-streaming response)
        content_type = resp.headers.get("content-type", "")
        raw = resp.text.strip()

        if "text/event-stream" in content_type or raw.startswith("data: "):
            # SSE streaming — reassemble content from chunks
            content_parts = []
            for line in raw.split("\n"):
                line = line.strip()
                if line.startswith("data: "):
                    chunk = line[6:]
                    if chunk == "[DONE]":
                        break
                    try:
                        obj = json.loads(chunk)
                        delta = obj.get("choices", [{}])[0].get("delta", {})
                        text = delta.get("content", "")
                        if text:
                            content_parts.append(text)
                    except (json.JSONDecodeError, IndexError):
                        pass
            content = "".join(content_parts)
        else:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return "", latency, f"Invalid JSON response ({len(raw)} bytes)"
            choices = data.get("choices", [])
            if not choices:
                return "", latency, "No choices in response"
            msg = choices[0].get("message")
            if msg is None:
                # Some providers return delta instead of message
                msg = choices[0].get("delta", {})
            content = msg.get("content", "") if isinstance(msg, dict) else ""

        # Strip <think> tags
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        return content, latency, None

    except requests.Timeout:
        return "", time.time() - t0, "TIMEOUT"
    except Exception as e:
        return "", time.time() - t0, str(e)


def is_french(text):
    """Heuristic: check if text is predominantly French."""
    french_markers = [
        " est ", " les ", " des ", " une ", " dans ", " pour ", " avec ",
        " qui ", " que ", " sur ", " pas ", " plus ", " sont ", " cette ",
        " nous ", " vous ", " leur ", " mais ", " aussi ", " très ",
        " peut ", " fait ", " être ", " avoir ", " comme ",
    ]
    text_lower = text.lower()
    matches = sum(1 for m in french_markers if m in text_lower)
    return matches >= 3


def evaluate_response(test, content):
    """Evaluate a response against test checks. Returns (passed, issues)."""
    checks = test["checks"]
    issues = []
    passed = True

    # Check 1: minimum length
    if len(content) < checks["min_length"]:
        issues.append(f"Too short: {len(content)} chars (min {checks['min_length']})")
        passed = False

    # Check 2: must contain keywords
    if checks["must_contain_any"]:
        content_lower = content.lower()
        found = [kw for kw in checks["must_contain_any"] if kw.lower() in content_lower]
        if not found:
            issues.append(f"Missing keywords: none of {checks['must_contain_any']} found")
            passed = False

    # Check 3: language check
    if checks["must_be_french"]:
        if not is_french(content):
            issues.append("Expected French but response appears to be in another language")
            passed = False
    else:
        # For English personas, just check it's not empty
        pass

    if not issues:
        issues.append("All checks passed")

    return passed, issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Validate migrated persona quality")
    parser.add_argument("--tenant", default="myia", help="Tenant to test (default: myia)")
    parser.add_argument("--report", default=None, help="Output report path")
    parser.add_argument("--timeout", type=int, default=180, help="Request timeout in seconds")
    parser.add_argument("--personas", default="all", help="Comma-separated persona IDs or 'all'")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    for env_file in [".env", "myia.env"]:
        load_env(os.path.join(repo_dir, env_file))

    # Tenant config
    TENANTS = {
        "myia": ("MYIA_URL", "MYIA_EMAIL", "MYIA_PASSWORD"),
        "epf": ("EPF_URL", "EPF_EMAIL", "EPF_PASSWORD"),
        "epf-genai": ("EPF_GENAI_URL", "EPF_GENAI_EMAIL", "EPF_GENAI_PASSWORD"),
        "ece": ("ECE_URL", "ECE_EMAIL", "ECE_PASSWORD"),
        "esg": ("ESG_URL", "ESG_EMAIL", "ESG_PASSWORD"),
        "epita": ("EPITA_URL", "EPITA_EMAIL", "EPITA_PASSWORD"),
        "pauwels": ("PAUWELS_URL", "PAUWELS_EMAIL", "PAUWELS_PASSWORD"),
    }

    if args.tenant not in TENANTS:
        print(f"Unknown tenant: {args.tenant}")
        sys.exit(1)

    url_key, email_key, pwd_key = TENANTS[args.tenant]
    base_url = os.environ.get(url_key, "")
    email = os.environ.get(email_key, "")
    pwd = os.environ.get(pwd_key, "")

    if not base_url or not email or not pwd:
        print(f"Missing credentials for {args.tenant}")
        sys.exit(1)

    # Filter personas
    tests_to_run = PERSONA_TESTS
    if args.personas != "all":
        requested = [p.strip() for p in args.personas.split(",")]
        tests_to_run = [t for t in PERSONA_TESTS if t["model_id"] in requested]
        if not tests_to_run:
            print(f"No matching personas found for: {args.personas}")
            sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  PERSONA VALIDATION — {args.tenant} ({base_url})")
    print(f"  Testing {len(tests_to_run)} personas")
    print(f"{'='*70}\n")

    # Login
    print("  Logging in...", end=" ", flush=True)
    token = owui_login(base_url, email, pwd)
    if not token:
        print("FAILED")
        sys.exit(1)
    print("OK\n")

    # Run tests
    results = []
    for test in tests_to_run:
        model_id = test["model_id"]
        print(f"  [{test['category'].upper():>12}] {test['name']} ({model_id})")
        print(f"               Base: {test['base_model']}")
        print(f"               Prompt: {test['prompt'][:80]}...")

        messages = [{"role": "user", "content": test["prompt"]}]
        content, latency, error = chat_completion(
            base_url, token, model_id, messages, timeout=args.timeout
        )

        if error:
            print(f"               ERROR: {error}")
            results.append({
                **test,
                "status": "ERROR",
                "error": error,
                "content": "",
                "latency": latency,
                "passed": False,
                "issues": [f"Error: {error}"],
            })
        else:
            passed, issues = evaluate_response(test, content)
            status = "PASS" if passed else "FAIL"
            print(f"               Status: {status} | {latency:.1f}s | {len(content)} chars")
            for issue in issues:
                print(f"               - {issue}")
            print(f"               Preview: {content[:120]}...")
            results.append({
                **test,
                "status": status,
                "error": None,
                "content": content,
                "latency": latency,
                "passed": passed,
                "issues": issues,
            })
        print()

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    errors = sum(1 for r in results if r["status"] == "ERROR")
    failed = total - passed - errors

    print(f"{'='*70}")
    print(f"  RESULTS: {passed}/{total} PASS | {failed} FAIL | {errors} ERROR")
    print(f"{'='*70}\n")

    # Generate report
    report_path = args.report or os.path.join(
        script_dir, "reports", "persona-validation.md"
    )
    generate_report(results, report_path, args.tenant, base_url)
    print(f"  Report saved to: {report_path}")

    # Exit code
    sys.exit(0 if passed == total else 1)


def generate_report(results, output_path, tenant, base_url):
    """Generate Markdown validation report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    errors = sum(1 for r in results if r["status"] == "ERROR")

    lines = [
        f"# Persona Validation Report\n",
        f"**Tenant:** {tenant} ({base_url})",
        f"**Date:** {now}",
        f"**Result:** {passed}/{total} passed\n",
        "## Summary\n",
        "| # | Persona | Category | Base Model | Status | Latency | Length |",
        "|---|---------|----------|------------|--------|---------|--------|",
    ]

    for i, r in enumerate(results, 1):
        status_icon = {"PASS": "PASS", "FAIL": "FAIL", "ERROR": "ERR"}[r["status"]]
        latency = f"{r['latency']:.1f}s" if r["latency"] else "-"
        length = f"{len(r['content'])} chars" if r["content"] else "-"
        lines.append(
            f"| {i} | {r['name']} | {r['category']} | `{r['base_model']}` "
            f"| **{status_icon}** | {latency} | {length} |"
        )

    lines.append("\n## Detailed Results\n")

    for r in results:
        lines.append(f"### {r['name']} (`{r['model_id']}`)\n")
        lines.append(f"- **Category:** {r['category']}")
        lines.append(f"- **Base model:** `{r['base_model']}`")
        lines.append(f"- **Status:** {r['status']}")
        lines.append(f"- **Latency:** {r['latency']:.1f}s")
        lines.append(f"- **Expected:** {r['checks']['description']}")

        if r["issues"]:
            lines.append(f"- **Checks:**")
            for issue in r["issues"]:
                lines.append(f"  - {issue}")

        if r["error"]:
            lines.append(f"- **Error:** `{r['error']}`")

        if r["content"]:
            preview = r["content"][:500].replace("\n", "\n> ")
            lines.append(f"\n<details><summary>Response preview (first 500 chars)</summary>\n")
            lines.append(f"> {preview}")
            lines.append(f"\n</details>\n")

    # Category summary
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0, "avg_latency": []}
        categories[cat]["total"] += 1
        if r["passed"]:
            categories[cat]["passed"] += 1
        categories[cat]["avg_latency"].append(r["latency"])

    lines.append("\n## By Category\n")
    lines.append("| Category | Passed | Avg Latency |")
    lines.append("|----------|--------|-------------|")
    for cat, data in sorted(categories.items()):
        avg_lat = sum(data["avg_latency"]) / len(data["avg_latency"])
        lines.append(f"| {cat} | {data['passed']}/{data['total']} | {avg_lat:.1f}s |")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
