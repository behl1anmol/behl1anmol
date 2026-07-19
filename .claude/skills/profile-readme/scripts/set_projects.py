#!/usr/bin/env python3
"""Swap the top-3 showcased repositories.

Usage (from repo root):
    python3 .claude/skills/profile-readme/scripts/set_projects.py Repo1 Repo2 Repo3
    python3 .claude/skills/profile-readme/scripts/set_projects.py --list

Does three things atomically:
1. Rewrites REPOS in scripts/generate_project_cards.py.
2. Runs that script (fetches live repo data, regenerates the 6 card SVGs).
3. Rewrites the PROJECT-CARDS block in README.md to reference the new cards.

Old card SVGs for dropped repos are deleted so assets/ never accumulates
stale files. Fails loudly if a repo doesn't exist on GitHub.
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
CARDS_SCRIPT = os.path.join(ROOT, "scripts", "generate_project_cards.py")
README = os.path.join(ROOT, "README.md")
OWNER = "behl1anmol"


def current_repos():
    src = open(CARDS_SCRIPT).read()
    m = re.search(r'REPOS = \[(.*?)\]', src, re.S)
    return re.findall(r'"([^"]+)"', m.group(1))


def repo_exists(name):
    try:
        with urllib.request.urlopen(
                f"https://api.github.com/repos/{OWNER}/{name}", timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def card_block(name, desc):
    low = name.lower()
    alt = f"{name} — {desc}" if desc else name
    alt = alt.replace('"', "&quot;")
    return (f'  <a href="https://github.com/{OWNER}/{name}"><picture>\n'
            f'    <source media="(prefers-color-scheme: dark)" srcset="assets/project-{low}-dark.svg">\n'
            f'    <source media="(prefers-color-scheme: light)" srcset="assets/project-{low}-light.svg">\n'
            f'    <img src="assets/project-{low}-dark.svg" alt="{alt}" width="290">\n'
            f'  </picture></a>')


def main():
    args = sys.argv[1:]
    if args == ["--list"]:
        print("Current showcased repos:", ", ".join(current_repos()))
        return
    if len(args) != 3:
        sys.exit("Need exactly 3 repo names (or --list).")

    # same description fallback as the card generator (DESC_OVERRIDES covers
    # repos whose GitHub description is empty)
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from generate_project_cards import DESC_OVERRIDES

    infos = {}
    for name in args:
        info = repo_exists(name)
        if info is None:
            sys.exit(f"Repo not found on GitHub: {OWNER}/{name}")
        infos[name] = DESC_OVERRIDES.get(name) or info.get("description") or ""

    old = current_repos()

    # 1. rewrite REPOS in the generator
    src = open(CARDS_SCRIPT).read()
    new_list = 'REPOS = [' + ", ".join(f'"{n}"' for n in args) + ']'
    src = re.sub(r'REPOS = \[.*?\]', new_list, src, count=1, flags=re.S)
    open(CARDS_SCRIPT, "w").write(src)

    # 2. regenerate cards (fetches fresh desc/stars; DESC_OVERRIDES may refine)
    subprocess.run([sys.executable, CARDS_SCRIPT], check=True, cwd=ROOT)

    # 3. rewrite README block between markers
    readme = open(README).read()
    blocks = "\n".join(card_block(n, infos[n]) for n in args)
    new_block = ('<!-- PROJECT-CARDS:START -->\n<p align="center">\n'
                 + blocks + '\n</p>\n<!-- PROJECT-CARDS:END -->')
    readme, n = re.subn(r'<!-- PROJECT-CARDS:START -->.*?<!-- PROJECT-CARDS:END -->',
                        new_block, readme, flags=re.S)
    if n != 1:
        sys.exit("PROJECT-CARDS markers not found in README.md — aborting.")
    open(README, "w").write(readme)

    # 4. drop stale card SVGs
    for name in set(old) - set(args):
        for variant in ("dark", "light"):
            p = os.path.join(ROOT, "assets", f"project-{name.lower()}-{variant}.svg")
            if os.path.exists(p):
                os.remove(p)
                print(f"removed stale {os.path.relpath(p, ROOT)}")

    print(f"Showcase now: {', '.join(args)}. Run verify.py before committing.")


if __name__ == "__main__":
    main()
