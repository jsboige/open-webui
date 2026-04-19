#!/usr/bin/env python3
"""Benchmark OWUI models: compare OpenAI vs alternatives on latency, quality, and cost.

Sends a set of test prompts to multiple models via OWUI's OpenAI-compatible API
and measures response time, output length, and quality indicators.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Test prompts (diverse tasks: Q&A, code, analysis, French, reasoning)
# ---------------------------------------------------------------------------
TEST_PROMPTS = [
    {
        "id": "french_qa",
        "name": "Q&A Francais",
        "messages": [
            {"role": "user", "content": "Explique en 3 phrases ce qu'est l'intelligence artificielle et donne un exemple concret d'application."}
        ],
        "eval_criteria": "Reponse en francais, 3 phrases, exemple concret",
    },
    {
        "id": "code_python",
        "name": "Code Python",
        "messages": [
            {"role": "user", "content": "Write a Python function that checks if a string is a palindrome. Include type hints and a docstring. Return the function only, no explanation."}
        ],
        "eval_criteria": "Valid Python, type hints, docstring, correct logic",
    },
    {
        "id": "reasoning",
        "name": "Raisonnement",
        "messages": [
            {"role": "user", "content": "Un train part de Paris a 9h00 a 120 km/h vers Lyon (480 km). Un autre train part de Lyon a 10h00 a 150 km/h vers Paris. A quelle heure se croisent-ils et a quelle distance de Paris? Montre ton raisonnement."}
        ],
        "eval_criteria": "Correct math, clear reasoning, answer in French",
    },
    {
        "id": "structured_analysis",
        "name": "Analyse Structuree",
        "messages": [
            {"role": "user", "content": "Compare les avantages et inconvenients du cloud computing vs l'hebergement on-premise pour une PME de 50 employes. Structure ta reponse avec des bullet points."}
        ],
        "eval_criteria": "Structured bullets, balanced analysis, practical advice",
    },
    {
        "id": "creative_french",
        "name": "Creativite FR",
        "messages": [
            {"role": "user", "content": "Ecris un haiku en francais sur le theme de la programmation."}
        ],
        "eval_criteria": "French haiku (5-7-5 syllables), programming theme",
    },
]

# ---------------------------------------------------------------------------
# Model groups to benchmark
# ---------------------------------------------------------------------------
MODEL_GROUPS = {
    "tp_tutor_candidates": {
        "description": "Alternatives to OpenAI.gpt-4.1-mini for TP tutors (code + pedagogy)",
        "current": "OpenAI.gpt-4.1-mini",
        "candidates": [
            "MistralAI.mistral-small-latest",
            "MistralAI.devstral-small-latest",
            "DeepSeek.deepseek-chat",
            "Local.qwen3.6-35b-a3b-fast",
            "Local.qwen3.6-35b-a3b",
        ],
    },
    "general_candidates": {
        "description": "Alternatives to OpenAI.gpt-4o / gpt-5 for personas",
        "current": "OpenAI.gpt-4o",
        "candidates": [
            "OpenRouter.anthropic/claude-haiku-4.5",
            "OpenRouter.anthropic/claude-sonnet-4",
            "MistralAI.mistral-medium-latest",
            "OpenRouter.deepseek/deepseek-v3.2",
            "OpenRouter.x-ai/grok-3-mini",
        ],
    },
}

# Approximate pricing (USD per 1M tokens) — for cost estimation
# Source: provider pricing pages, March 2026
PRICING = {
    # OpenAI
    "OpenAI.gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "OpenAI.gpt-4o": {"input": 2.50, "output": 10.00},
    "OpenAI.gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "OpenAI.gpt-5": {"input": 10.00, "output": 30.00},
    "OpenAI.o3": {"input": 10.00, "output": 40.00},
    "OpenAI.o1": {"input": 15.00, "output": 60.00},
    # MistralAI
    "MistralAI.mistral-small-latest": {"input": 0.10, "output": 0.30},
    "MistralAI.mistral-medium-latest": {"input": 0.40, "output": 1.20},
    "MistralAI.devstral-small-latest": {"input": 0.10, "output": 0.30},
    # DeepSeek
    "DeepSeek.deepseek-chat": {"input": 0.14, "output": 0.28},
    # OpenRouter (approximate, varies)
    "OpenRouter.anthropic/claude-haiku-4.5": {"input": 0.80, "output": 4.00},
    "OpenRouter.anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "OpenRouter.deepseek/deepseek-v3.2": {"input": 0.14, "output": 0.28},
    "OpenRouter.x-ai/grok-3-mini": {"input": 0.30, "output": 0.50},
    "OpenRouter.qwen/qwen3-coder": {"input": 0.00, "output": 0.00},
    "OpenRouter.mistralai/mistral-small-3.1-24b-instruct": {"input": 0.00, "output": 0.00},
    # Local (free)
    "Local.qwen3.6-35b-a3b": {"input": 0.00, "output": 0.00},
    "Local.qwen3.6-35b-a3b-fast": {"input": 0.00, "output": 0.00},
    "Local.omnicoder-9b": {"input": 0.00, "output": 0.00},
}


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
    """Call OWUI chat completion. Returns (content, latency_s, error)."""
    t0 = time.time()
    try:
        resp = requests.post(
            f"{base_url}/api/chat/completions",
            headers={"Authorization": f"Bearer {token}"},
            json={"model": model, "messages": messages, "stream": False},
            timeout=timeout,
        )
        latency = time.time() - t0
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                # Strip <think> tags if present
                import re
                content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                return content, latency, None
            return "", latency, "No choices in response"
        return "", latency, f"HTTP {resp.status_code}: {resp.text[:100]}"
    except requests.Timeout:
        return "", time.time() - t0, "TIMEOUT"
    except Exception as e:
        return "", time.time() - t0, str(e)


def estimate_tokens(text):
    """Rough token estimation (4 chars per token for English/French mix)."""
    return len(text) // 4


def run_benchmark(base_url, token, models, prompts, timeout=180):
    """Run all prompts against all models. Returns results list."""
    results = []
    total = len(models) * len(prompts)
    idx = 0

    for model in models:
        for prompt in prompts:
            idx += 1
            print(f"  [{idx}/{total}] {model} / {prompt['name']}...", end=" ", flush=True)

            content, latency, error = chat_completion(
                base_url, token, model, prompt["messages"], timeout=timeout
            )

            if error:
                print(f"ERROR ({latency:.1f}s): {error[:60]}")
                results.append({
                    "model": model,
                    "prompt_id": prompt["id"],
                    "prompt_name": prompt["name"],
                    "latency_s": round(latency, 1),
                    "output_chars": 0,
                    "output_tokens_est": 0,
                    "error": error,
                    "response": "",
                })
            else:
                out_tokens = estimate_tokens(content)
                print(f"OK ({latency:.1f}s, {len(content)} chars)")
                results.append({
                    "model": model,
                    "prompt_id": prompt["id"],
                    "prompt_name": prompt["name"],
                    "latency_s": round(latency, 1),
                    "output_chars": len(content),
                    "output_tokens_est": out_tokens,
                    "error": None,
                    "response": content[:500],  # Truncate for report
                })

    return results


def generate_report(results, model_groups, output_path=None):
    """Generate Markdown benchmark report."""
    lines = []
    lines.append("# Model Benchmark Report\n")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Tool:** `scripts/benchmark-models.py`\n")

    for group_name, group_def in model_groups.items():
        lines.append(f"\n## {group_def['description']}\n")
        lines.append(f"**Current model:** `{group_def['current']}`\n")

        all_models = [group_def["current"]] + group_def["candidates"]
        group_results = [r for r in results if r["model"] in all_models]

        if not group_results:
            lines.append("*No results for this group.*\n")
            continue

        # Summary table
        lines.append("### Summary\n")
        lines.append("| Model | Avg Latency | Avg Output | Est. Cost/1M tok | Errors |")
        lines.append("|-------|------------|-----------|-----------------|--------|")

        for model in all_models:
            model_results = [r for r in group_results if r["model"] == model]
            if not model_results:
                lines.append(f"| `{model}` | - | - | - | not tested |")
                continue

            ok_results = [r for r in model_results if not r["error"]]
            errors = sum(1 for r in model_results if r["error"])

            if ok_results:
                avg_lat = sum(r["latency_s"] for r in ok_results) / len(ok_results)
                avg_chars = sum(r["output_chars"] for r in ok_results) / len(ok_results)
            else:
                avg_lat = 0
                avg_chars = 0

            pricing = PRICING.get(model, {})
            if pricing:
                cost_str = f"${pricing.get('output', '?')}/M out"
            else:
                cost_str = "unknown"

            is_current = " **(current)**" if model == group_def["current"] else ""
            is_free = " **FREE**" if pricing.get("output", 1) == 0 else ""

            lines.append(
                f"| `{model}`{is_current} | {avg_lat:.1f}s | {avg_chars:.0f} chars | {cost_str}{is_free} | {errors}/{len(model_results)} |"
            )

        # Detail table
        lines.append("\n### Detailed Results\n")
        lines.append("| Model | Prompt | Latency | Output | Response (excerpt) |")
        lines.append("|-------|--------|---------|--------|-------------------|")

        for r in group_results:
            error_str = f"**{r['error'][:30]}**" if r["error"] else ""
            excerpt = r["response"][:80].replace("\n", " ").replace("|", "\\|") if r["response"] else error_str
            lines.append(
                f"| `{r['model']}` | {r['prompt_name']} | {r['latency_s']}s | {r['output_chars']}c | {excerpt} |"
            )

    report = "\n".join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport saved to: {output_path}", file=sys.stderr)

    return report


def main():
    parser = argparse.ArgumentParser(description="Benchmark OWUI models")
    parser.add_argument("--url", default=None, help="OWUI URL (default: MYIA_URL)")
    parser.add_argument("--email", default=None, help="Login email (default: MYIA_EMAIL)")
    parser.add_argument("--password", default=None, help="Login password (default: MYIA_PASSWORD)")
    parser.add_argument("--group", default="all", choices=["all", "tp_tutor_candidates", "general_candidates"],
                        help="Which model group to benchmark")
    parser.add_argument("--timeout", type=int, default=180, help="Request timeout in seconds")
    parser.add_argument("--output", default=None, help="Output report path")
    args = parser.parse_args()

    # Load env
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    for env_file in [".env", "myia.env"]:
        load_env(os.path.join(repo_dir, env_file))

    url = args.url or os.environ.get("MYIA_URL", "")
    email = args.email or os.environ.get("MYIA_EMAIL", "")
    password = args.password or os.environ.get("MYIA_PASSWORD", "")

    if not url or not email or not password:
        print("ERROR: Missing URL/email/password. Set MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD or use --url/--email/--password", file=sys.stderr)
        sys.exit(1)

    output_path = args.output or os.path.join(script_dir, "reports", "benchmark-report.md")

    print(f"Connecting to {url}...")
    token = owui_login(url, email, password)
    if not token:
        print("Login failed!", file=sys.stderr)
        sys.exit(1)
    print("Login OK\n")

    # Select groups
    groups = (
        MODEL_GROUPS if args.group == "all"
        else {args.group: MODEL_GROUPS[args.group]}
    )

    # Collect all unique models
    all_models = set()
    for g in groups.values():
        all_models.add(g["current"])
        all_models.update(g["candidates"])

    print(f"Benchmarking {len(all_models)} models x {len(TEST_PROMPTS)} prompts = {len(all_models) * len(TEST_PROMPTS)} calls\n")

    # Run benchmark
    results = run_benchmark(url, token, sorted(all_models), TEST_PROMPTS, timeout=args.timeout)

    # Generate report
    report = generate_report(results, groups, output_path)
    print("\n" + report)


if __name__ == "__main__":
    main()
