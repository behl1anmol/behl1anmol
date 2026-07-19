# Widget endpoint status and verification procedure

Public README-widget instances die without warning. **Rule: curl-check every
external image URL before adding it or pushing changes** — `verify.py` does
this for everything already referenced in README.md.

## Status (verified 2026-07-19)

### Dead — do not use

| Host | Symptom | Consequence |
|------|---------|-------------|
| `github-readme-stats.vercel.app` (pin cards, stats, top-langs) | `DEPLOYMENT_PAUSED` text body | Replaced by self-generated cards (`scripts/generate_project_cards.py`) |
| `github-profile-trophy.vercel.app` | HTTP 402 payment required | Trophies dropped from README entirely |

If pin cards are wanted again: self-host github-readme-stats on own Vercel
account, or keep the local generator (preferred — palette-matched, no
third-party dependency).

### Alive and in use

| Host | Used for |
|------|----------|
| `komarev.com/ghpvc` | visitor counter badge |
| `streak-stats.demolab.com` | contribution streak card |
| `github-readme-activity-graph.vercel.app` | contribution line graph |
| `img.shields.io` | link badges |

All themed with palette hexes from `content-map.md`, `hide_border=true`.

## Verification procedure for a NEW widget

1. `curl -sL --max-time 30 "<url>" | head -c 200` — expect SVG/PNG bytes,
   not an error string. Vercel failures return 200-ish HTML/text bodies, so
   check CONTENT, not just status code.
2. Confirm it accepts custom colors (pass palette hexes) or has a theme
   close to synthwave.
3. Add to README, run `verify.py`, then check the rendered profile page
   after push — GitHub camo-proxies images and can behave differently from
   direct curl.

## Notes

- Blog list is not a widget: GitHub Action (`blog-posts.yml`,
  gautamkrishnar/blog-post-workflow) commits directly into README markers.
  Test via `gh workflow run blog-posts.yml` then `git pull`.
- Committed SVGs must contain NO external URL references (camo blocks them);
  embedded `data:image/png` URIs are fine. `verify.py` enforces.
