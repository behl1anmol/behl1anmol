#!/usr/bin/env python3
"""Generate synthwave project showcase cards for the profile README.

Self-hosted replacement for github-readme-stats pin cards (the public vercel
instance is paused/402 as of 2026-07). Pulls live repo data from the GitHub
API at generation time; re-run to refresh stars/descriptions.

Run from repo root: python3 scripts/generate_project_cards.py
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_neofetch import DARK, LIGHT, MONO, ROOT

REPOS = ["Noesis", "MediatorLite", "VideoStreamingFlask"]

# Repos without an API description get one sourced from their own README.
DESC_OVERRIDES = {
    "MediatorLite": "A lightweight, high-performance mediator library for "
                    ".NET, built with source generators for zero-reflection "
                    "dispatch and minimal allocations.",
}

LANG_COLORS = {"Python": "#3572A5", "C#": "#178600", "TypeScript": "#3178c6",
               "JavaScript": "#f1e05a", "C++": "#f34b7d", "HTML": "#e34c26"}

W, H = 340, 150


def fetch(repo):
    url = f"https://api.github.com/repos/behl1anmol/{repo}"
    with urllib.request.urlopen(url, timeout=30) as r:
        d = json.load(r)
    return {
        "name": d["name"],
        "desc": DESC_OVERRIDES.get(repo) or d.get("description") or "",
        "lang": d.get("language") or "",
        "stars": d.get("stargazers_count", 0),
    }


def wrap(text, width=46, max_lines=3):
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        if len(cur) + len(w_) + (1 if cur else 0) <= width:
            cur = f"{cur} {w_}".strip()
        else:
            lines.append(cur)
            cur = w_
            if len(lines) == max_lines:
                break
    if cur and len(lines) < max_lines:
        lines.append(cur)
        cur = ""
    if " ".join(lines) != text:                      # truncated -> ellipsis
        lines[-1] = lines[-1][:width - 1].rstrip() + "…"
    return lines


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def mini_sun(t, x, y, r=13):
    """Tiny banded sun, brand continuity with the neofetch card."""
    s = [f'<clipPath id="msun-{t["name"]}-{x}"><circle cx="{x}" cy="{y}" r="{r}"/></clipPath>',
         f'<circle cx="{x}" cy="{y}" r="{r}" fill="url(#sun-{t["name"]})"/>']
    band_y, band_h = y + 2, 1.6
    s.append(f'<g clip-path="url(#msun-{t["name"]}-{x})">')
    while band_y < y + r:
        s.append(f'<rect x="{x - r}" y="{band_y:.1f}" width="{r * 2}" '
                 f'height="{band_h:.1f}" fill="{t["card"]}"/>')
        band_y += band_h + 3.4
        band_h += 0.9
    s.append('</g>')
    return "".join(s)


def render(t, info):
    lines = wrap(esc(info["desc"]))
    lang_dot = LANG_COLORS.get(info["lang"], t["dim"])
    s = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="{esc(info["name"])} repository card">',
        f'''<defs><linearGradient id="sun-{t["name"]}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{t["sun_top"]}"/><stop offset="1" stop-color="{t["sun_bottom"]}"/>
</linearGradient></defs>''',
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="10" '
        f'fill="{t["card"]}" stroke="{t["grid_line"]}" stroke-opacity="0.45" stroke-width="1.5"/>',
        mini_sun(t, W - 28, 28),
        f'<g font-family="{MONO}">',
        f'<text x="20" y="34" font-size="16" font-weight="bold" '
        f'fill="{t["header"]}">{esc(info["name"])}</text>',
    ]
    y = 60
    for line in lines:
        s.append(f'<text x="20" y="{y}" font-size="11.5" fill="{t["value"]}">{line}</text>')
        y += 17
    fy = H - 20
    s.append(f'<circle cx="26" cy="{fy - 4}" r="5" fill="{lang_dot}"/>')
    s.append(f'<text x="38" y="{fy}" font-size="12" fill="{t["dim"]}">{esc(info["lang"])}</text>')
    if info["stars"]:
        s.append(f'<text x="{W - 20}" y="{fy}" font-size="12" text-anchor="end" '
                 f'fill="{t["sun_top"]}">★ {info["stars"]}</text>')
    s.append('</g></svg>')
    return "\n".join(s)


def main():
    for repo in REPOS:
        info = fetch(repo)
        for t in (DARK, LIGHT):
            path = os.path.join(ROOT, "assets", f"project-{repo.lower()}-{t['name']}.svg")
            with open(path, "w", encoding="utf-8") as f:
                f.write(render(t, info))
            print(f"wrote {path}")


if __name__ == "__main__":
    main()
