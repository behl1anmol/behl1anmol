#!/usr/bin/env python3
"""Pre-push verification for the profile README. Run from repo root.

    python3 .claude/skills/profile-readme/scripts/verify.py

Checks, in order:
1. Every committed SVG in assets/ parses as XML and contains no external
   URL references (GitHub's camo proxy blocks them silently).
2. README references only asset files that exist, and every PNG-embedding
   SVG's portrait extracts cleanly (written to /tmp/profile-readme-verify/
   so a human or agent can eyeball it).
3. Every external widget/badge URL in README.md answers HTTP < 400.
   Rationale: public widget instances die (github-readme-stats pin cards
   returned DEPLOYMENT_PAUSED, trophy 402 — see references/widgets.md);
   never push a README without curl-checking them.

Exit 0 = all pass. Non-zero = failures listed on stdout.
"""

import base64
import glob
import os
import re
import sys
import urllib.request
import xml.dom.minidom

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
OUT = "/tmp/profile-readme-verify"
failures = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        failures.append(msg)


def main():
    os.makedirs(OUT, exist_ok=True)

    svgs = sorted(glob.glob(os.path.join(ROOT, "assets", "*.svg")))
    check(bool(svgs), f"assets/*.svg present ({len(svgs)} files)")
    for p in svgs:
        rel = os.path.relpath(p, ROOT)
        try:
            xml.dom.minidom.parse(p)
            src = open(p).read()
            clean = (src.replace("http://www.w3.org/2000/svg", "")
                        .replace("http://www.w3.org/1999/xlink", "")
                        .replace("data:image/png", ""))
            check("http" not in clean, f"{rel}: no external refs")
            m = re.search(r'data:image/png;base64,([A-Za-z0-9+/=]+)', src)
            if m:
                png = base64.b64decode(m.group(1))
                out = os.path.join(OUT, os.path.basename(p) + ".portrait.png")
                open(out, "wb").write(png)
                check(png[:4] == b"\x89PNG", f"{rel}: embedded portrait extracts -> {out}")
        except Exception as e:
            check(False, f"{rel}: {e}")

    readme = open(os.path.join(ROOT, "README.md")).read()

    for rel in re.findall(r'(?:src|srcset)="(assets/[^"]+)"', readme):
        check(os.path.exists(os.path.join(ROOT, rel)), f"README asset exists: {rel}")

    # src= URLs render as images -> hard failures. href= URLs are navigation
    # for humans -> warn only (LinkedIn answers bots with HTTP 999 by design).
    img_urls = set(re.findall(r'src="(https://[^"]+)"', readme))
    link_urls = set(re.findall(r'href="(https://[^"]+)"', readme)) - img_urls
    for url in sorted(img_urls) + sorted(link_urls):
        hard = url in img_urls
        host = url.split("/")[2]
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "readme-verify"})
            with urllib.request.urlopen(req, timeout=30) as r:
                ok = r.status < 400
        except Exception as e:
            ok, r = False, None
            err = str(e)
        msg = f"{host}: {'HTTP %d' % r.status if r else err} ({url[:70]}...)"
        if hard or ok:
            check(ok, ("img " if hard else "link ") + msg)
        else:
            print("WARN link " + msg + " — bot-blocked or down; check by hand")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S) — do not push.")
        sys.exit(1)
    print("All checks passed. Safe to commit/push.")


if __name__ == "__main__":
    main()
