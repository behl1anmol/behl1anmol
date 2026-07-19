# SVG pipeline architecture

How the neofetch card and project cards are generated. Read this before
touching `scripts/generate_neofetch.py` or `scripts/generate_project_cards.py`.

## Neofetch card (`scripts/generate_neofetch.py`)

One SVG = whole card: portrait scene panel (left) + spec list (right) +
palette strip + prompt footer. Emitted twice: `assets/neofetch-dark.svg` and
`assets/neofetch-light.svg`, wired into README via `<picture>` +
`prefers-color-scheme`. Rationale: GitHub strips CSS/flex from README
markdown — only an SVG guarantees the two-column monospace layout.

### Portrait pipeline (order matters)

1. **Crop** `assets/source/profile-hd.jpg` (gitignored, local only) by `CROP`
   fractions → head-and-shoulders.
2. **Downsample** to grid: 176 cols (smooth, default) or 88 (`PIXEL_MODE=1`).
   `Image.BOX` filter — averages cells, no ringing.
3. **Classify** each cell transparent/kept (`_classify_transparent`): green
   foliage by hue, grey haze by low saturation + brightness (haze rule only
   near frame edges — it once ate a glasses-lens reflection and punched a
   hole in the face). Dark cells are kept as hair.
4. **Kurta gold ramp**: lower-region cream cells (hue 0.08–0.17) map to a
   4-step gold ramp by brightness instead of nearest-palette.
5. **Spatial clears along MEASURED polylines** — the critical part, see below.
6. **Morphology**: `_close_holes` (densify crown), `_erode_thin_debris`,
   `_keep_largest_component`, `_smooth_scalp` (median outlier trim).
7. `_fill_crown` (solid crown volume, measured top profile),
   `_fill_to_right_edge` (extend rows to measured edge — classifier
   under-fills 1–3 cells where hair mixes with background).
8. `_clear_above_top_edge` + `_clear_left_of_edge` + final
   `_keep_largest_component` — trims overshoot; runs LAST so nothing refills.
9. **Overrides**: `SMOOTH_OVERRIDES` (176 grid: ear crease/concha/lobe,
   sideburn), `OVERRIDES` (88 grid legacy: teeth, glasses).
10. **Render**: smooth mode rasterizes the grid to a soft-blurred RGBA PNG
    (PIL GaussianBlur 1.1, 4× upscale) embedded base64 in the SVG.
    Rationale: thousands of adjacent `<rect>`s under an SVG blur filter leak
    background through anti-aliasing seams (showed as a square pattern over
    the kurta). One bitmap = zero seams. Data-URIs inside SVG work through
    GitHub's camo proxy (same technique github-readme-stats uses).

### The measured polylines — MEASURE, DON'T GUESS

`RIGHT_EDGE`, `TOP_EDGE`, `LEFT_EDGE` are (fraction, fraction) polylines
tracing the head silhouette where the background is colour-identical to hair
(tree trunk, building shadow — verified: brightness 0.12 vs 0.18, both
near-zero saturation; sharpness/depth-of-field also fails, measured medians
5.1 vs 4.7). No algorithm can find this boundary. Every point was read off
gridded zoom renders of the photo.

**Never replace these with invented "anatomical" curves.** That was tried;
it amputated the ear (cols 106–115, rows 50–72 of the 176 grid — the bump in
RIGHT_EDGE at rows 0.26–0.36 IS the ear).

### Re-measuring for a NEW PHOTO (the only manual-heavy operation)

A new photo invalidates `CROP`, all three polylines, `SMOOTH_OVERRIDES`, and
possibly the classifier thresholds. Workflow:

1. Replace `assets/source/profile-hd.jpg` (stays gitignored).
2. Adjust `CROP` so head+shoulders fill the frame (~0.9 aspect).
3. Render the crop with a coordinate grid to measure against:
   downsample to the grid size, upscale ×5, draw labelled gridlines every
   5–10 cells (PIL ImageDraw; pattern used before — grid overlay + zoom crops
   of disputed regions at ×10–22 scale).
4. Read silhouette boundary cell values row-by-row from the overlays; update
   the polylines. Comment that values are measured, and from which overlay.
5. Iterate: regenerate, extract the embedded PNG
   (`re.search(r'base64,([A-Za-z0-9+/=]+)')` → decode), compare side-by-side
   with the photo crop at identical size, zoom any disputed region in BOTH
   images before changing numbers.
6. Redo `SMOOTH_OVERRIDES` (ear/sideburn cells are photo-specific).
7. `verify.py` + Artifact/preview gate before commit.

### Layout constants

Card 1010×532, portrait panel 372×420 at (36,36), spec column x=452.
Spec values max ~41 chars at 15px monospace (`set_spec.py` enforces).
Adding/removing SPECS lines shifts the palette strip — 11 spec lines +
header + underline fit; more requires raising `CARD_H`.

## Project cards (`scripts/generate_project_cards.py`)

Self-hosted 340×150 SVG cards (dark+light per repo) fetching live GitHub API
data at generation time. Exists because the public github-readme-stats pin
instance is dead (see `widgets.md`). `DESC_OVERRIDES` supplies descriptions
for repos with an empty GitHub description (sourced from their own README —
don't invent). Theme dicts are imported from `generate_neofetch.py`; palette
changes propagate automatically.

## Requirements

Pillow (`pip install pillow` / `--user --break-system-packages` on WSL
managed Python). Network for GitHub API + widget checks. Always run
generators from repo root.
