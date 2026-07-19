# Content map — where every fact lives and comes from

Single lookup table for "I want to change X". Facts must stay grounded —
each has a provenance; don't restyle them into claims that aren't sourced.

## Neofetch card spec lines

Live in `SPECS` in `scripts/generate_neofetch.py`; edit via
`set_spec.py --label <L> --value <V>` (regenerates SVGs).

| Label      | Current source of truth |
|------------|------------------------|
| OS         | Job title (user-stated: Senior Software Engineer, as of 2026-07) |
| Kernel     | Primary stack (user's LinkedIn summary) |
| Uptime     | Professional since 2021 (Accenture). Protected memory `career-timeline`: college 2017, GitHub 2018, graduated+Accenture 2021, Aon 2026. Employer name intentionally NOT shown — user approved uptime math only. |
| Packages   | Public repo count (GitHub API snapshot at generation; refresh = re-run generator) |
| Shell/IDE/Frameworks/Cloud/GenAI/Arch/DB | User's LinkedIn skills list, verbatim-refined |

Header `anmol@behl1anmol`, palette strip, and prompt footer are layout
constants in the same file.

## README.md blocks (marker-delimited, script-editable)

| Block | Markers | Editor |
|-------|---------|--------|
| Summary paragraph | `SUMMARY:START/END` | `set_spec.py --summary "..."` |
| Project showcase | `PROJECT-CARDS:START/END` | `set_projects.py A B C` |
| Blog list | `BLOG-POST-LIST:START/END` | GitHub Action only — never hand-edit; `.github/workflows/blog-posts.yml` overwrites daily (03:00 UTC) from Medium RSS |

## Links row (`> cat ~/connect`)

Extensible by design: one badge = one line. Pattern:

```html
<a href="URL"><img src="https://img.shields.io/badge/LABEL-VALUE-160d24?style=for-the-badge&logo=LOGO&logoColor=5eead4&labelColor=ff2d95" alt="LABEL" /></a>
```

Current: LinkedIn (`https://www.linkedin.com/in/behlanmol/`), Resume
(Google Drive file), Medium (`@behl1anmol`). Logo slugs from simpleicons.org.
Curl-check any new badge URL before committing (see widgets.md).

## Palette (synthwave, use for any new themed widget)

| Token | Hex | Use |
|-------|-----|-----|
| card bg dark | `160d24` | widget bg_color / badge base |
| border | `2c1b45` | hide-able borders |
| pink accent | `ff2d95` | labels, lines, badge labelColor |
| cyan header | `5eead4` | titles, logoColor |
| fg text | `e8e3f0` | values |
| dim | `8a7fa8` | secondary text |
| gold | `ffd75e` | fire/star accents |
| sky mid | `3d0f66` | area fills |

Light-variant equivalents live in the `LIGHT` dict in `generate_neofetch.py`.

## Visitor badge

`komarev.com/ghpvc/?username=behl1anmol&style=flat-square&color=ff2d95&label=visitors`
— top of README, under the card.
