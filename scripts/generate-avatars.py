#!/usr/bin/env python3
"""Generate avatars for OWUI custom models via SD Forge API and deploy to all tenants."""

import argparse
import base64
import io
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests Pillow", file=sys.stderr)
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    Image = None  # Will skip resize if Pillow not available

# ---------------------------------------------------------------------------
# Avatar definitions: model_id -> SD prompt
# ---------------------------------------------------------------------------
AVATARS = {
    "expert-analyste": {
        "prompt": "professional portrait of a distinguished male analyst wearing glasses and a dark suit, confident expression, office background with data charts, corporate headshot style, clean lighting, high quality",
        "negative": "cartoon, anime, deformed, blurry, low quality, text, watermark",
        "description": "Analyste structur\u00e9 fran\u00e7ais. D\u00e9compose les probl\u00e8mes complexes avec rigueur et clart\u00e9. Id\u00e9al pour les \u00e9tudes de cas, comparaisons et synth\u00e8ses argumentatives.",
    },
    "redacteur-technique": {
        "prompt": "professional portrait of a young woman with red hair and glasses, friendly smile, working at a desk with documents and laptop, warm office lighting, editorial style headshot, high quality",
        "negative": "cartoon, anime, deformed, blurry, low quality, text, watermark",
        "description": "R\u00e9dacteur de documentation technique en fran\u00e7ais. Produit des documents structur\u00e9s, clairs et p\u00e9dagogiques. Id\u00e9al pour tutoriels, rapports et manuels.",
    },
    "vision-expert": {
        "prompt": "futuristic robot head with glowing blue eyes, cyberpunk style, metallic surface with circuit patterns, dark background with holographic displays, sci-fi portrait, high quality digital art",
        "negative": "blurry, low quality, text, watermark, ugly",
        "description": "Sp\u00e9cialiste analyse d'images et documents visuels. OCR, analyse de graphiques, description d'images. Mod\u00e8le local avec capacit\u00e9s vision.",
    },
    "Local.qwen3.6-35b-a3b-fast": {
        "prompt": "minimalist icon design, bright yellow lightning bolt on dark blue circle background, clean vector style, sharp edges, modern flat design, high contrast, app icon style",
        "negative": "realistic, photo, blurry, text, watermark, complex background",
        "description": "Version rapide de Qwen3.6-35B sans r\u00e9flexion interne. R\u00e9ponses directes en 1-3 secondes. Id\u00e9al pour les questions factuelles et les t\u00e2ches simples.",
    },
    "tp-linux-debutant": {
        "prompt": "cute linux penguin tux mascot wearing a graduation cap, holding a terminal console, friendly cartoon style, education theme, bright colors, clean design, high quality illustration",
        "negative": "realistic, photo, blurry, text, watermark, dark, scary",
        "description": "Tuteur interactif Linux : exercices bash, filesystem, scripts. Ex\u00e9cution r\u00e9elle dans un terminal s\u00e9curis\u00e9.",
    },
    "tp-python-data": {
        "prompt": "friendly python snake mascot coiled around a colorful data chart, wearing small glasses, cartoon illustration style, data science theme with pandas logo and matplotlib graphs in background, bright cheerful colors",
        "negative": "realistic, photo, scary, dark, blurry, text, watermark",
        "description": "Tuteur interactif Python/Data Science : pandas, matplotlib, scikit-learn. Ex\u00e9cution r\u00e9elle dans un terminal s\u00e9curis\u00e9.",
    },
    "tp-git-workflow": {
        "prompt": "stylized git branch diagram as a tree with colorful nodes, merge arrows, cartoon style illustration, version control concept art, tech education theme, clean modern design, bright colors on white background",
        "negative": "realistic, photo, blurry, text, watermark, dark",
        "description": "Tuteur interactif Git : init, branches, merge, r\u00e9solution de conflits. Pratique r\u00e9elle dans un terminal s\u00e9curis\u00e9.",
    },
}

# SD Forge API parameters (SDXL Lightning 4-step)
SD_PARAMS = {
    "steps": 4,
    "cfg_scale": 1.5,
    "sampler_name": "Euler",
    "width": 1024,
    "height": 1024,
    "batch_size": 1,
    "n_iter": 1,
    "seed": -1,
}

AVATAR_SIZE = 256  # Resize to 256x256 for deployment


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


def generate_avatar(sd_url, prompt, negative_prompt):
    """Generate an avatar via SD Forge txt2img API. Returns base64 PNG string."""
    payload = {
        **SD_PARAMS,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
    }
    resp = requests.post(f"{sd_url}/sdapi/v1/txt2img", json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    images = data.get("images", [])
    if not images:
        raise RuntimeError("No images returned from SD Forge")
    return images[0]  # base64-encoded PNG


def resize_base64_image(b64_data, size):
    """Resize a base64 PNG image. Returns new base64 string."""
    if Image is None:
        return b64_data  # Skip resize if Pillow not available
    img_bytes = base64.b64decode(b64_data)
    img = Image.open(io.BytesIO(img_bytes))
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def owui_login(base_url, email, password):
    """Login to OWUI and return JWT token."""
    resp = requests.post(
        f"{base_url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("token", "")
    print(f"  Login failed: {resp.status_code}", file=sys.stderr)
    return ""


def owui_get_model(base_url, token, model_id):
    """Get a model by ID from OWUI."""
    resp = requests.get(
        f"{base_url}/api/v1/models/model",
        params={"id": model_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def owui_update_model(base_url, token, model_id, update_data):
    """Update a model on OWUI."""
    resp = requests.post(
        f"{base_url}/api/v1/models/model/update",
        params={"id": model_id},
        headers={"Authorization": f"Bearer {token}"},
        json=update_data,
        timeout=30,
    )
    return resp.status_code == 200


TENANTS = {
    "myia": ("MYIA_URL", "MYIA_EMAIL", "MYIA_PASSWORD"),
    "epf": ("EPF_URL", "EPF_EMAIL", "EPF_PASSWORD"),
    "epf-genai": ("EPF_GENAI_URL", "EPF_GENAI_EMAIL", "EPF_GENAI_PASSWORD"),
    "ece": ("ECE_URL", "ECE_EMAIL", "ECE_PASSWORD"),
    "esg": ("ESG_URL", "ESG_EMAIL", "ESG_PASSWORD"),
    "epita": ("EPITA_URL", "EPITA_EMAIL", "EPITA_PASSWORD"),
    "pauwels": ("PAUWELS_URL", "PAUWELS_EMAIL", "PAUWELS_PASSWORD"),
}


def main():
    parser = argparse.ArgumentParser(description="Generate and deploy OWUI model avatars")
    parser.add_argument("--sd-url", default="https://turbo.stable-diffusion-webui-forge.myia.io",
                        help="SD Forge API URL")
    parser.add_argument("--generate-only", action="store_true",
                        help="Only generate avatars, don't deploy")
    parser.add_argument("--deploy-only", action="store_true",
                        help="Only deploy from saved files, don't generate")
    parser.add_argument("--models", nargs="*", default=None,
                        help="Specific model IDs to process (default: all)")
    parser.add_argument("--output-dir", default=None,
                        help="Directory to save generated avatars (default: scripts/avatars/)")
    parser.add_argument("--tenant", default="all",
                        help="Tenant to deploy to (default: all)")
    args = parser.parse_args()

    # Load env files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    for env_file in [".env", "myia.env"]:
        load_env(os.path.join(repo_dir, env_file))

    output_dir = args.output_dir or os.path.join(script_dir, "avatars")
    os.makedirs(output_dir, exist_ok=True)

    models_to_process = args.models or list(AVATARS.keys())
    avatars_b64 = {}

    # --- Generate phase ---
    if not args.deploy_only:
        print(f"\n{'='*60}")
        print(f"  GENERATING AVATARS via {args.sd_url}")
        print(f"{'='*60}\n")

        for model_id in models_to_process:
            if model_id not in AVATARS:
                print(f"  SKIP: {model_id} (no avatar definition)", file=sys.stderr)
                continue

            avatar_def = AVATARS[model_id]
            print(f"  Generating: {model_id}...", end=" ", flush=True)
            t0 = time.time()
            try:
                raw_b64 = generate_avatar(args.sd_url, avatar_def["prompt"], avatar_def["negative"])
                resized_b64 = resize_base64_image(raw_b64, AVATAR_SIZE)
                avatars_b64[model_id] = resized_b64

                # Save to file
                safe_name = model_id.replace(":", "_").replace(".", "_")
                out_path = os.path.join(output_dir, f"{safe_name}.json")
                with open(out_path, "w") as f:
                    json.dump({"model_id": model_id, "image_b64": resized_b64}, f)

                size_kb = len(resized_b64) * 3 / 4 / 1024
                elapsed = time.time() - t0
                print(f"OK ({elapsed:.1f}s, ~{size_kb:.0f} KB)")
            except Exception as e:
                print(f"FAILED: {e}", file=sys.stderr)

    # --- Load from files if deploy-only ---
    if args.deploy_only:
        for model_id in models_to_process:
            safe_name = model_id.replace(":", "_").replace(".", "_")
            fpath = os.path.join(output_dir, f"{safe_name}.json")
            if os.path.exists(fpath):
                with open(fpath) as f:
                    data = json.load(f)
                    avatars_b64[model_id] = data["image_b64"]

    if not avatars_b64:
        print("\nNo avatars to deploy.", file=sys.stderr)
        return

    if args.generate_only:
        print(f"\n  Generated {len(avatars_b64)} avatars to {output_dir}")
        return

    # --- Deploy phase ---
    tenants_to_deploy = (
        list(TENANTS.keys()) if args.tenant == "all"
        else [args.tenant]
    )

    print(f"\n{'='*60}")
    print(f"  DEPLOYING AVATARS to {len(tenants_to_deploy)} tenants")
    print(f"{'='*60}\n")

    for tenant_name in tenants_to_deploy:
        url_key, email_key, pwd_key = TENANTS[tenant_name]
        url = os.environ.get(url_key, "")
        email = os.environ.get(email_key, "")
        pwd = os.environ.get(pwd_key, "")

        if not url or not email or not pwd:
            print(f"  {tenant_name}: SKIP (missing credentials)")
            continue

        print(f"  {tenant_name}: {url}")
        token = owui_login(url, email, pwd)
        if not token:
            print(f"    Login FAILED")
            continue
        print(f"    Login OK")

        for model_id, img_b64 in avatars_b64.items():
            model = owui_get_model(url, token, model_id)
            if not model:
                print(f"    {model_id}: not found, skipping")
                continue

            # Build update payload
            meta = model.get("meta", {})
            meta["profile_image_url"] = f"data:image/png;base64,{img_b64}"

            # Also set description if it's missing
            avatar_def = AVATARS.get(model_id, {})
            desc = avatar_def.get("description", "")
            if desc and not meta.get("description"):
                meta["description"] = desc

            update = {**model, "meta": meta}
            ok = owui_update_model(url, token, model_id, update)
            status = "OK" if ok else "FAILED"
            print(f"    {model_id}: avatar {status}")

        print()

    print("Done.")


if __name__ == "__main__":
    main()
