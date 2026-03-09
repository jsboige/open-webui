#!/usr/bin/env python3
"""
Create thematic Knowledge Bases from existing Bibliographie IA files.

Maps uploaded files to subdirectory themes, creates one KB per theme,
and links existing file_ids to the new KBs (triggers re-embedding).

Usage:
  python scripts/create-thematic-kbs.py [--delay 10] [--dry-run]

Environment variables (from .env):
  MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD
"""

import os
import sys
import json
import time
import glob
import argparse
import urllib.request
import urllib.error


# Thematic KB definitions: directory name -> (KB name FR, description)
THEMATIC_KBS = {
    'Automata': (
        'IA - Automates',
        'Théorie des automates, langages formels, automates d\'arbres.'
    ),
    'BigData': (
        'IA - Big Data',
        'Algorithmes pour le Big Data, Apache Spark, traitement distribué.'
    ),
    'Constraint Programming': (
        'IA - Programmation par contraintes',
        'Satisfaction de contraintes (CSP/SAT/SMT), programmation par contraintes, CP-SAT.'
    ),
    'GameTheory': (
        'IA - Théorie des jeux',
        'Théorie des jeux, équilibres de Nash, regret minimization, jeux différentiels, poker IA.'
    ),
    'MachineLearning': (
        'IA - Apprentissage automatique',
        'Machine Learning, Deep Learning, transformers, GANs, diffusion, reinforcement learning.'
    ),
    'Probabilistic': (
        'IA - Méthodes probabilistes',
        'Modèles graphiques, inférence bayésienne, programmation probabiliste, free energy.'
    ),
    'Search': (
        'IA - Recherche et optimisation',
        'Recherche heuristique, optimisation convexe, géométrie computationnelle.'
    ),
    'Symbolic': (
        'IA - IA symbolique',
        'Logique, ontologies, planification, neurosymbolique, Web sémantique, blockchain.'
    ),
    'Trading': (
        'IA - Trading et finance',
        'Trading algorithmique, finance quantitative, comptabilité, mathématiques financières.'
    ),
}

BIBLIO_DIR = 'G:/Mon Drive/MyIA/IA/Bibliographie IA'


def load_env(env_path):
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def api_call(url, token, data=None, method=None, timeout=120):
    """Make an authenticated API call."""
    headers = {'Authorization': f'Bearer {token}'}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.load(resp)


def authenticate(base_url, email, password):
    data = json.dumps({'email': email, 'password': password}).encode()
    req = urllib.request.Request(
        f'{base_url}/api/v1/auths/signin',
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req)
    return json.load(resp)['token']


def get_all_files(base_url, token):
    """Fetch all uploaded files from OWUI."""
    result = api_call(f'{base_url}/api/v1/files/', token)
    files = result if isinstance(result, list) else result.get('files', result.get('data', []))
    # Build name -> id mapping
    file_map = {}
    for f in files:
        meta = f.get('meta', {}) or {}
        name = meta.get('name', f.get('filename', ''))
        if name:
            file_map[name] = f['id']
    return file_map


def build_theme_file_map(biblio_dir):
    """Map each PDF filename to its subdirectory theme."""
    theme_map = {}  # filename -> directory_name
    for dir_name in THEMATIC_KBS:
        subdir = os.path.join(biblio_dir, dir_name)
        if not os.path.isdir(subdir):
            print(f"  WARNING: Directory not found: {subdir}")
            continue
        pdfs = glob.glob(os.path.join(subdir, '*.pdf'))
        for pdf in pdfs:
            theme_map[os.path.basename(pdf)] = dir_name
    # Root-level AIMA books (shared across KBs)
    root_pdfs = glob.glob(os.path.join(biblio_dir, '*.pdf'))
    for pdf in root_pdfs:
        theme_map[os.path.basename(pdf)] = '__ROOT__'
    return theme_map


def create_kb(base_url, token, name, description):
    """Create a new Knowledge Base."""
    result = api_call(
        f'{base_url}/api/v1/knowledge/create',
        token,
        data={'name': name, 'description': description}
    )
    return result['id']


def add_file_to_kb(base_url, token, kb_id, file_id, timeout=600):
    """Add a file to a KB (triggers embedding)."""
    result = api_call(
        f'{base_url}/api/v1/knowledge/{kb_id}/file/add',
        token,
        data={'file_id': file_id},
        timeout=timeout
    )
    return result


def main():
    parser = argparse.ArgumentParser(description='Create thematic KBs from Bibliographie IA')
    parser.add_argument('--delay', type=float, default=10,
                        help='Delay between file additions (default: 10s)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show plan without executing')
    parser.add_argument('--biblio-dir', default=BIBLIO_DIR,
                        help=f'Bibliographie IA directory (default: {BIBLIO_DIR})')
    parser.add_argument('--include-aima', action='store_true', default=False,
                        help='Add AIMA root books to each thematic KB')
    parser.add_argument('--themes', nargs='+',
                        help='Only process these themes (e.g., Automata MachineLearning)')
    args = parser.parse_args()

    # Load credentials
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_env(env_path)

    base_url = os.environ.get('MYIA_URL', 'https://open-webui.myia.io')
    email = os.environ.get('MYIA_EMAIL')
    password = os.environ.get('MYIA_PASSWORD')

    if not email or not password:
        print("ERROR: MYIA_EMAIL and MYIA_PASSWORD must be set in .env")
        sys.exit(1)

    # Step 1: Map filenames to themes from filesystem
    print("=== Step 1: Mapping files to themes ===")
    theme_file_map = build_theme_file_map(args.biblio_dir)
    print(f"  Found {len(theme_file_map)} files across themes")

    # Build per-theme file lists
    themes_to_process = {}
    root_files = []
    for filename, theme in theme_file_map.items():
        if theme == '__ROOT__':
            root_files.append(filename)
            continue
        if args.themes and theme not in args.themes:
            continue
        themes_to_process.setdefault(theme, []).append(filename)

    print(f"\n  Root-level files (AIMA): {len(root_files)}")
    for f in sorted(root_files):
        print(f"    - {f}")

    print(f"\n  Thematic breakdown:")
    total_files = 0
    for theme in sorted(themes_to_process):
        files = themes_to_process[theme]
        kb_name = THEMATIC_KBS[theme][0]
        print(f"    {kb_name}: {len(files)} files")
        total_files += len(files)
    print(f"  Total: {total_files} files")

    if args.dry_run:
        print("\n=== DRY RUN: Detailed plan ===")
        for theme in sorted(themes_to_process):
            kb_name, desc = THEMATIC_KBS[theme]
            files = sorted(themes_to_process[theme])
            print(f"\n  KB: {kb_name}")
            print(f"  Description: {desc}")
            print(f"  Files ({len(files)}):")
            for f in files:
                print(f"    - {f}")
        est_time = total_files * args.delay
        print(f"\n  Estimated time: {est_time/60:.0f} minutes (with {args.delay}s delay)")
        print("  Run without --dry-run to execute.")
        return

    # Step 2: Authenticate
    print(f"\n=== Step 2: Authenticating to {base_url} ===")
    token = authenticate(base_url, email, password)
    print("  OK")

    # Step 3: Get existing files
    print("\n=== Step 3: Fetching uploaded files ===")
    owui_files = get_all_files(base_url, token)
    print(f"  {len(owui_files)} files in OWUI")

    # Step 4: Create KBs and link files
    print("\n=== Step 4: Creating thematic KBs ===")
    results = {}

    for theme in sorted(themes_to_process):
        kb_name, description = THEMATIC_KBS[theme]
        theme_files = sorted(themes_to_process[theme])

        print(f"\n--- {kb_name} ({len(theme_files)} files) ---")

        # Create KB
        try:
            kb_id = create_kb(base_url, token, kb_name, description)
            print(f"  Created KB: {kb_id}")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()[:300]
            print(f"  ERROR creating KB: HTTP {e.code}: {error_body}")
            results[theme] = {'status': 'create_failed', 'error': error_body}
            continue

        # Add files
        succeeded = 0
        failed = 0
        not_found = 0

        # Start with AIMA books if requested
        files_to_add = []
        if args.include_aima:
            files_to_add.extend(root_files)
        files_to_add.extend(theme_files)

        for i, filename in enumerate(files_to_add, 1):
            file_id = owui_files.get(filename)
            if not file_id:
                print(f"  [{i}/{len(files_to_add)}] {filename} — NOT FOUND in OWUI")
                not_found += 1
                continue

            try:
                print(f"  [{i}/{len(files_to_add)}] {filename}...", end=" ", flush=True)
                add_file_to_kb(base_url, token, kb_id, file_id)
                print("OK")
                succeeded += 1
            except urllib.error.HTTPError as e:
                error_body = e.read().decode()[:200]
                print(f"HTTP {e.code}: {error_body}")
                failed += 1
            except Exception as e:
                print(f"ERROR: {e}")
                failed += 1

            # Delay between additions
            if i < len(files_to_add):
                time.sleep(args.delay)

        results[theme] = {
            'status': 'ok',
            'kb_id': kb_id,
            'kb_name': kb_name,
            'succeeded': succeeded,
            'failed': failed,
            'not_found': not_found,
            'total': len(files_to_add)
        }
        print(f"  Result: {succeeded}/{len(files_to_add)} OK, {failed} failed, {not_found} not found")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total_ok = 0
    total_fail = 0
    for theme, r in sorted(results.items()):
        kb_name = THEMATIC_KBS[theme][0]
        if r['status'] == 'ok':
            total_ok += r['succeeded']
            total_fail += r['failed']
            print(f"  {kb_name}: {r['succeeded']}/{r['total']} OK (KB: {r['kb_id']})")
        else:
            print(f"  {kb_name}: FAILED ({r['error'][:50]})")
    print(f"\n  Total: {total_ok} files linked, {total_fail} failed")
    print("=" * 70)


if __name__ == '__main__':
    main()
