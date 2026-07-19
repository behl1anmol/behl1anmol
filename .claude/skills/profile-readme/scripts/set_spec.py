#!/usr/bin/env python3
"""Edit neofetch-card spec lines or the README summary paragraph.

Usage (from repo root):
    python3 .claude/skills/profile-readme/scripts/set_spec.py --list
    python3 .claude/skills/profile-readme/scripts/set_spec.py --label Uptime --value "6+ years (since 2021)"
    python3 .claude/skills/profile-readme/scripts/set_spec.py --summary "New summary markdown..."

--label/--value edits one SPECS tuple in scripts/generate_neofetch.py and
regenerates both card SVGs. Label must already exist (adding/removing lines
changes card layout height — do that by editing SPECS by hand and checking
the layout section of references/architecture.md).

--summary replaces the paragraph between SUMMARY markers in README.md.
Keep it 2-4 lines rendered; markdown bold allowed.
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
GEN = os.path.join(ROOT, "scripts", "generate_neofetch.py")
README = os.path.join(ROOT, "README.md")


def specs():
    src = open(GEN).read()
    m = re.search(r'SPECS = \[(.*?)\]\n', src, re.S)
    return re.findall(r'\("([^"]+)", "([^"]+)"\)', m.group(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--label")
    ap.add_argument("--value")
    ap.add_argument("--summary")
    a = ap.parse_args()

    if a.list:
        for label, value in specs():
            print(f"{label:<11} {value}")
        return

    if a.summary:
        readme = open(README).read()
        new = f"<!-- SUMMARY:START -->\n{a.summary.strip()}\n<!-- SUMMARY:END -->"
        readme, n = re.subn(r'<!-- SUMMARY:START -->.*?<!-- SUMMARY:END -->',
                            new, readme, flags=re.S)
        if n != 1:
            sys.exit("SUMMARY markers not found in README.md — aborting.")
        open(README, "w").write(readme)
        print("Summary updated.")
        return

    if not (a.label and a.value):
        sys.exit("Need --list, --summary, or --label with --value.")

    labels = [l for l, _ in specs()]
    if a.label not in labels:
        sys.exit(f"Label '{a.label}' not in SPECS ({', '.join(labels)}). "
                 "Adding new lines changes card layout — see architecture.md.")
    if len(a.value) > 41:
        sys.exit(f"Value too long ({len(a.value)} chars, max 41) — overflows "
                 "the card's right column at 15px monospace.")

    src = open(GEN).read()
    src, n = re.subn(r'\("%s", "[^"]*"\)' % re.escape(a.label),
                     f'("{a.label}", "{a.value}")', src, count=1)
    assert n == 1
    open(GEN, "w").write(src)
    subprocess.run([sys.executable, GEN], check=True, cwd=ROOT)
    print(f"{a.label} -> {a.value}. Cards regenerated; run verify.py.")


if __name__ == "__main__":
    main()
