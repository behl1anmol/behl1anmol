#!/usr/bin/env python3
"""Generate the neofetch-style profile card SVGs (dark + light).

Reads assets/source/profile-hd.jpg, quantizes it into a smooth posterized
synthwave portrait (set PIXEL_MODE=1 for the 16-bit pixel-art variant), composes it with a banded retro sun and a neon perspective grid,
and writes assets/neofetch-dark.svg and assets/neofetch-light.svg.

Requires Pillow: pip install pillow
Run from repo root: python3 scripts/generate_neofetch.py
"""

import base64
import colorsys
import io
import math
import os
import statistics
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "source", "profile-hd.jpg")
OUT_DARK = os.path.join(ROOT, "assets", "neofetch-dark.svg")
OUT_LIGHT = os.path.join(ROOT, "assets", "neofetch-light.svg")

# ---------------------------------------------------------------- portrait --

GRID_W = 88          # pixel-art columns
CELL = 4             # svg px per cell

# Head-and-shoulders crop of the HD photo, as (left, top, right, bottom)
# fractions of the full frame.
CROP = (0.20, 0.24, 0.80, 1.00)

# Outer right edge of the head, measured cell-by-cell from gridded zooms of
# the photo (tmp/crop-grid.png overview + tmp/ear-zoom.png closeup).
# (row fraction, col fraction), linearly interpolated. The bump at
# rows 0.26-0.36 is the EAR (cols 106-115) — do not flatten it.
RIGHT_EDGE = [(0.000, 0.580), (0.021, 0.595), (0.036, 0.607), (0.052, 0.617),
              (0.155, 0.623), (0.232, 0.630), (0.258, 0.653),
              (0.283, 0.658), (0.309, 0.653), (0.335, 0.647), (0.361, 0.641),
              (0.387, 0.619), (0.412, 0.613), (0.438, 0.607), (0.464, 0.602),
              (0.490, 0.590), (0.515, 0.579), (0.530, 0.579)]


def _edge_at(f):
    for (f0, c0), (f1, c1) in zip(RIGHT_EDGE, RIGHT_EDGE[1:]):
        if f0 <= f <= f1:
            return c0 + (c1 - c0) * (f - f0) / (f1 - f0)
    return RIGHT_EDGE[-1][1]


# Top hair edge across the crown, measured from tmp/p-top.png (col fraction,
# row fraction). The tree trunk behind the head is the same dark value as
# hair, so the classifier keeps it as an overshoot above this line; clear
# above the measured curve. Descends left->right (no flat plateau).
TOP_EDGE = [(0.386, 0.052), (0.443, 0.057), (0.466, 0.062), (0.500, 0.072),
            (0.534, 0.082), (0.568, 0.093), (0.602, 0.103), (0.625, 0.113),
            (0.636, 0.124)]

# Left hair/ear edge, measured from tmp/p-left.png (row fraction, col
# fraction). The blurred greenery is removed by colour, but sideburn cells
# mixed with it get kept, sticking out past the true hairline; clear left of
# this curve.
LEFT_EDGE = [(0.196, 0.256), (0.227, 0.261), (0.258, 0.261), (0.284, 0.267),
             (0.309, 0.273), (0.335, 0.278), (0.361, 0.295), (0.387, 0.307),
             (0.412, 0.318), (0.438, 0.318)]


def _interp(table, f):
    for (f0, v0), (f1, v1) in zip(table, table[1:]):
        if f0 <= f <= f1:
            return v0 + (v1 - v0) * (f - f0) / (f1 - f0)
    return None


def _clear_above_top_edge(grid, width):
    """Remove tree/background above the measured hair crown (TOP_EDGE)."""
    h = len(grid)
    c0 = int(width * TOP_EDGE[0][0])
    c1 = int(width * TOP_EDGE[-1][0])
    for col in range(c0, c1 + 1):
        top_f = _interp(TOP_EDGE, col / width)
        if top_f is None:
            continue
        for row in range(int(h * top_f)):
            grid[row][col] = None


def _clear_left_of_edge(grid, width):
    """Remove background/sideburn overshoot left of the measured LEFT_EDGE."""
    h = len(grid)
    r0 = int(h * LEFT_EDGE[0][0])
    r1 = int(h * LEFT_EDGE[-1][0])
    for row in range(r0, r1 + 1):
        left_f = _interp(LEFT_EDGE, row / h)
        if left_f is None:
            continue
        for col in range(int(width * left_f)):
            grid[row][col] = None

# Stylized synthwave palette the photo is quantized into (not photo-true).
PORTRAIT_PALETTE = [
    (18, 9, 32),      # 0  hair darkest
    (32, 20, 52),     # 1  hair
    (54, 34, 76),     # 2  hair sheen
    (46, 27, 56),     # 3  beard dark
    (74, 47, 74),     # 4  beard
    (94, 51, 80),     # 5  skin deepest shadow
    (143, 79, 87),    # 6  skin shadow
    (185, 106, 92),   # 7  skin dark mid
    (217, 136, 102),  # 8  skin mid
    (237, 165, 120),  # 9  skin light mid
    (255, 195, 154),  # 10 skin light
    (255, 224, 196),  # 11 skin highlight
    (194, 86, 104),   # 12 lips
    (255, 244, 234),  # 13 teeth / bright
    (255, 224, 138),  # 14 kurta highlight
    (255, 201, 77),   # 15 kurta gold
    (230, 172, 51),   # 16 kurta mid
    (192, 138, 36),   # 17 kurta shadow
    (255, 140, 59),   # 18 tilak orange
    (201, 203, 224),  # 19 glasses silver
]


def _rgb_hex(c):
    return "#%02x%02x%02x" % c


def _classify_transparent(r, g, b, upper, edge):
    """Background removal: green foliage + hazy desaturated sky drop out.

    `upper` = cell in top ~55% of the image, where only hair/face exist, so
    the rule is stricter there (yellow-green leaves, warm haze). The lower
    region is lenient so the yellow kurta (hue ~0.12) survives.
    `edge` = cell near the frame border, away from the face; the haze rule
    only runs there so it cannot eat bright glasses reflections.
    """
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    if upper:
        if v < 0.35 and s < 0.45:               # dark hair stays
            return False
        if 0.10 <= h <= 0.55 and s > 0.06:      # foliage incl. yellow-green
            return True
        if edge and s < 0.22 and v > 0.45:      # warm/grey haze
            return True
    else:
        if 0.17 <= h <= 0.50 and s > 0.12:      # green bushes at corners
            return True
    return False


def _nearest(c, palette):
    r, g, b = c
    return min(palette, key=lambda p: (p[0] - r) ** 2 + (p[1] - g) ** 2 + (p[2] - b) ** 2)


# Manual pixel fixes applied after auto-quantization: {(col, row): palette
# index or None for transparent}. Rows/cols are 0-based in the pixel grid.
OVERRIDES = {}

# brighten the smile: cell-averaging muddied the teeth into skin tones
for _c in range(36, 43):
    OVERRIDES[(_c, 39)] = 13
for _c in range(36, 42):
    OVERRIDES[(_c, 40)] = 13
OVERRIDES[(35, 39)] = 12
OVERRIDES[(43, 39)] = 12
OVERRIDES[(35, 40)] = 12

# lone skin pixel on the top-left hairline
OVERRIDES[(26, 8)] = 1

# Ear detailing for the smooth (176-col) grid: quantization flattens the ear
# into a featureless skin bump, so restore its structure — a shadow crease
# separating ear from head, the concha hollow, and lobe shading. Cell
# positions measured from tmp/ear-zoom.png.
SMOOTH_OVERRIDES = {}
for _r in range(52, 71):                     # sideburn hair in front of ear
    for _c in (104, 105, 106):
        SMOOTH_OVERRIDES[(_c, _r)] = 4
for _r in range(52, 63):
    SMOOTH_OVERRIDES[(103, _r)] = 4
for _r in range(52, 69):                     # crease between sideburn and ear
    SMOOTH_OVERRIDES[(107, _r)] = 6
for _r in range(54, 61):                     # concha hollow
    for _c in (109, 110, 111):
        SMOOTH_OVERRIDES[(_c, _r)] = 6
for _c, _r in ((111, 63), (111, 65), (110, 67), (109, 68)):  # lobe shading
    SMOOTH_OVERRIDES[(_c, _r)] = 6
OVERRIDES[(42, 40)] = 12


def build_portrait_grid(grid_w=GRID_W):
    im = Image.open(SRC).convert("RGB")
    w, h = im.size
    im = im.crop((int(CROP[0] * w), int(CROP[1] * h),
                  int(CROP[2] * w), int(CROP[3] * h)))
    w, h = im.size
    grid_h = round(grid_w * h / w)
    small = im.resize((grid_w, grid_h), Image.BOX)
    golds = (PORTRAIT_PALETTE[14], PORTRAIT_PALETTE[15],
             PORTRAIT_PALETTE[16], PORTRAIT_PALETTE[17])
    grid = []
    for row in range(grid_h):
        line = []
        upper = row < grid_h * 0.55
        for col in range(grid_w):
            c = small.getpixel((col, row))
            edge = col < grid_w * 0.20 or col > grid_w * 0.68 or row < grid_h * 0.10
            if _classify_transparent(*c, upper, edge):
                line.append(None)
                continue
            h, s, v = colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)
            if not upper and 0.08 <= h <= 0.17 and s > 0.12:
                # kurta cream -> gold ramp by brightness
                if v > 0.88:
                    line.append(golds[0])
                elif v > 0.76:
                    line.append(golds[1])
                elif v > 0.60:
                    line.append(golds[2])
                else:
                    line.append(golds[3])
            else:
                line.append(_nearest(c, PORTRAIT_PALETTE))
        grid.append(line)
    # The background right of the head (tree trunk, building shadow) is
    # colour-identical to hair, so colour rules cannot remove it and no local
    # signal (sharpness, hue) separates them either. The outer hair/beard
    # edge below was therefore MEASURED row by row from the photo with a
    # coordinate grid overlaid (see RIGHT_EDGE); everything right of the
    # measured line is background.
    for row in range(int(grid_h * RIGHT_EDGE[-1][0])):
        for col in range(int(grid_w * _edge_at(row / grid_h)), grid_w):
            grid[row][col] = None

    _close_holes(grid, width=grid_w, upper_rows=int(grid_h * 0.30))
    _erode_thin_debris(grid, upper_rows=int(grid_h * 0.6), width=grid_w)
    _keep_largest_component(grid, width=grid_w)
    _smooth_scalp(grid, width=grid_w)
    _fill_crown(grid, width=grid_w)
    _fill_to_right_edge(grid, width=grid_w)
    # Trim overshoot beyond the measured silhouette (tree above crown, sideburn
    # bar left of hairline). Run last so nothing refills past these edges.
    _clear_above_top_edge(grid, width=grid_w)
    _clear_left_of_edge(grid, width=grid_w)
    _keep_largest_component(grid, width=grid_w)
    if grid_w == GRID_W:                        # hand-tuned for this grid only
        for (col, row), val in OVERRIDES.items():
            grid[row][col] = None if val is None else PORTRAIT_PALETTE[val]
    if grid_w == GRID_W * 2:
        for (col, row), val in SMOOTH_OVERRIDES.items():
            if grid[row][col] is not None:   # only shade existing ear cells
                grid[row][col] = PORTRAIT_PALETTE[val]
    return grid


def _close_holes(grid, width, upper_rows, passes=2):
    """Morphological closing for the crown: the hair swoosh cells are mixed
    with green background at the boundary, so the colour rules punch holes in
    it and the later erosion then wipes the whole (real) swoosh. Filling
    transparent cells that have 5+ filled 8-neighbours densifies it first."""
    h = len(grid)
    for _ in range(passes):
        added = []
        for row in range(upper_rows):
            for col in range(width):
                if grid[row][col] is not None:
                    continue
                filled = []
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == dc == 0:
                            continue
                        r2, c2 = row + dr, col + dc
                        if 0 <= r2 < h and 0 <= c2 < width and grid[r2][c2] is not None:
                            filled.append(grid[r2][c2])
                if len(filled) >= 5:
                    added.append((row, col, filled[0]))
        if not added:
            break
        for row, col, val in added:
            grid[row][col] = val


def _fill_crown(grid, width):
    """Fill the top-right crown with solid hair volume. The photo's hair
    sweep there is so entangled with background greenery that classification
    leaves ragged fragments; a thin redrawn wisp floats or looks like an
    antenna at this stylization scale, so the crown is rebuilt as a full
    convex silhouette instead. Top profile measured from the gridded photo:
    (col fraction of span, row fraction of height)."""
    h = len(grid)
    hair = PORTRAIT_PALETTE[1]
    for row in range(int(h * 0.075)):
        for col in range(int(width * 0.45), width):
            grid[row][col] = None
    profile = [(0.00, 0.042), (0.40, 0.021), (0.65, 0.016), (0.85, 0.031),
               (1.00, 0.052)]
    c0, c1 = int(width * 0.477), int(width * 0.622)
    for col in range(c0, c1):
        t = (col - c0) / (c1 - c0)
        for (t0, r0), (t1, r1) in zip(profile, profile[1:]):
            if t0 <= t <= t1:
                top_f = r0 + (r1 - r0) * (t - t0) / (t1 - t0)
                break
        top = int(h * top_f)
        first = next((r for r in range(top, int(h * 0.30))
                      if grid[r][col] is not None), None)
        stop = first if first is not None else top
        for row in range(max(0, top), stop):
            grid[row][col] = hair


def _fill_to_right_edge(grid, width):
    """The classifier under-fills the right silhouette (hair/beard cells mixed
    with background get dropped), leaving it 1-3 cells short of the measured
    photo edge. Extend each row to the measured RIGHT_EDGE polyline using the
    row's own edge colour."""
    h = len(grid)
    for row in range(int(h * RIGHT_EDGE[-1][0])):
        target = int(width * _edge_at(row / h)) - 1
        rm = max((c for c in range(width) if grid[row][c] is not None), default=None)
        if rm is None or rm >= target:
            continue
        for col in range(rm + 1, target + 1):
            grid[row][col] = grid[row][rm]


def _smooth_scalp(grid, width):
    """Median-filter the top silhouette so stray hair tufts don't jut out of
    the head dome (they read as detached blobs against the sun)."""
    h = len(grid)
    tops = []
    for col in range(width):
        tops.append(next((r for r in range(h) if grid[r][col] is not None), None))
    win = max(4, width // 9)
    for col in range(width):
        if tops[col] is None or tops[col] > h * 0.35:
            continue
        window = [tops[c] for c in range(max(0, col - win), min(width, col + win + 1))
                  if tops[c] is not None]
        limit = int(statistics.median(window)) - 1
        for r in range(tops[col], min(limit, h)):
            grid[r][col] = None


def _round_scalp(grid, width):
    """Round the hair dome: clear cells above the moving average of the top
    silhouette, so the crown plateau blends into the sides instead of ending
    in a cliff that reads as a stray tuft."""
    h = len(grid)
    tops = []
    for col in range(width):
        tops.append(next((r for r in range(h) if grid[r][col] is not None), None))
    win = max(4, width // 20)
    for col in range(width):
        if tops[col] is None or tops[col] > h * 0.35:
            continue
        window = [tops[c] for c in range(max(0, col - win), min(width, col + win + 1))
                  if tops[c] is not None]
        limit = round(sum(window) / len(window)) - 1
        for r in range(tops[col], min(limit, h)):
            grid[r][col] = None


def _erode_thin_debris(grid, upper_rows, width=GRID_W, passes=3):
    """Strip 1-2px-wide leftovers (branches, trunks) in the upper region:
    repeatedly drop cells with fewer than 3 filled 4-neighbours."""
    h, w = len(grid), width
    for _ in range(passes):
        doomed = []
        for row in range(upper_rows):
            for col in range(w):
                if grid[row][col] is None:
                    continue
                n = 0
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    r2, c2 = row + dr, col + dc
                    if 0 <= r2 < h and 0 <= c2 < w and grid[r2][c2] is not None:
                        n += 1
                if n < 3:
                    doomed.append((row, col))
        if not doomed:
            break
        for row, col in doomed:
            grid[row][col] = None


def _keep_largest_component(grid, width=GRID_W):
    """Drop every filled region except the biggest (the person)."""
    h, w = len(grid), width
    seen = [[False] * w for _ in range(h)]
    best = []
    for row in range(h):
        for col in range(w):
            if grid[row][col] is None or seen[row][col]:
                continue
            comp, stack = [], [(row, col)]
            seen[row][col] = True
            while stack:
                r, c = stack.pop()
                comp.append((r, c))
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    r2, c2 = r + dr, c + dc
                    if (0 <= r2 < h and 0 <= c2 < w and not seen[r2][c2]
                            and grid[r2][c2] is not None):
                        seen[r2][c2] = True
                        stack.append((r2, c2))
            if len(comp) > len(best):
                best = comp
    keep = set(best)
    for row in range(h):
        for col in range(w):
            if grid[row][col] is not None and (row, col) not in keep:
                grid[row][col] = None


def debug_print(grid):
    chars = {None: "."}
    for i, p in enumerate(PORTRAIT_PALETTE):
        chars[p] = "0123456789abcdefghijklmnop"[i]
    for line in grid:
        print("".join(chars[c] for c in line))


def debug_png(grid, path, scale=10, bg=(20, 0, 46)):
    """Upscaled preview of the pixel portrait on the sky colour."""
    h = len(grid)
    gw = len(grid[0])
    im = Image.new("RGB", (gw * scale, h * scale), bg)
    px = im.load()
    for row in range(h):
        for col in range(gw):
            c = grid[row][col]
            if c is None:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    px[col * scale + dx, row * scale + dy] = c
    im.save(path)
    print(f"wrote {path}")


# ------------------------------------------------------------------ themes --

DARK = dict(
    name="dark",
    card="#160d24", card_border="#2c1b45",
    sky_top="#14002e", sky_mid="#3d0f66", sky_low="#7a1b6e",
    sun_top="#ffd75e", sun_bottom="#ff2d95",
    floor="#1c0b33", grid_line="#ff2d95",
    star="#9ff5ff",
    header="#5eead4", label="#ff2d95", value="#e8e3f0", dim="#8a7fa8",
    prompt="#c9b8ff", cursor="#ff9e64",
)

LIGHT = dict(
    name="light",
    card="#f6f1fb", card_border="#d9c8ef",
    sky_top="#cdb9f2", sky_mid="#f0a8d8", sky_low="#ffc9a3",
    sun_top="#ffb347", sun_bottom="#ff4da6",
    floor="#e6d6f5", grid_line="#d61f84",
    star="#ffffff",
    header="#0f766e", label="#c2186b", value="#2a1b3d", dim="#6b5a8a",
    prompt="#5b3fa8", cursor="#d97706",
)

# --------------------------------------------------------------- spec lines --

SPECS = [
    ("OS", "Senior Software Engineer"),
    ("Kernel", ".NET Core · C# · Python"),
    ("Uptime", "5+ years (since 2021)"),
    ("Packages", "52 public repos"),
    ("Shell", "bash · pwsh"),
    ("IDE", "Visual Studio · VS Code"),
    ("Frameworks", "ASP.NET Core · EF Core · WPF · FastAPI"),
    ("Cloud", "Azure · Functions · Durable · DevOps · AI"),
    ("GenAI", "Copilot · Claude · Codex · MCP · Agent Fw"),
    ("Arch", "SOLID · HLD/LLD · Serverless · Monolith"),
    ("DB", "SQL Server · MySQL"),
]

SWATCHES = ["#ff2d95", "#ff9e64", "#ffd75e", "#5eead4", "#9ff5ff",
            "#c9b8ff", "#7a1b6e", "#14002e"]

MONO = "'Cascadia Code','Courier New',ui-monospace,Menlo,monospace"

# ------------------------------------------------------------------ layout --

CARD_W, CARD_H = 1010, 532
PAD = 36
PANEL_W, PANEL_H = 372, 420          # portrait scene panel
TEXT_X = PAD + PANEL_W + 44


def portrait_png(grid, out_scale=4, blur=1.1):
    """Rasterize the quantized grid to a soft-blurred RGBA PNG (base64).

    Rendering the smooth portrait as one bitmap instead of thousands of
    <rect>s removes the hairline seams between rectangles that showed up as
    a square pattern over the kurta once a blur filter was involved.
    """
    h, w = len(grid), len(grid[0])
    im = Image.new("RGBA", (w * out_scale, h * out_scale), (0, 0, 0, 0))
    px = im.load()
    for row in range(h):
        for col in range(w):
            c = grid[row][col]
            if c is None:
                continue
            for dy in range(out_scale):
                for dx in range(out_scale):
                    px[col * out_scale + dx, row * out_scale + dy] = (*c, 255)
    im = im.filter(ImageFilter.GaussianBlur(blur))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def portrait_scene(t, grid, smooth=False):
    """The synthwave scene panel: sky, sun, stars, portrait, grid floor."""
    x0, y0 = PAD, PAD
    grid_h = len(grid)
    gw = len(grid[0])
    cell = (GRID_W * CELL) // gw
    art_w = gw * cell
    art_h = grid_h * cell
    ax = x0 + (PANEL_W - art_w) // 2
    ay = y0 + PANEL_H - art_h                    # torso sits on floor line
    floor_h = 104
    fy = y0 + PANEL_H - floor_h
    cx = x0 + PANEL_W / 2
    sun_cy, sun_r = y0 + 150, 118

    s = []
    s.append(f'<clipPath id="panel-{t["name"]}"><rect x="{x0}" y="{y0}" '
             f'width="{PANEL_W}" height="{PANEL_H}" rx="14"/></clipPath>')
    s.append(f'<g clip-path="url(#panel-{t["name"]})">')
    s.append(f'<rect x="{x0}" y="{y0}" width="{PANEL_W}" height="{PANEL_H}" '
             f'fill="url(#sky-{t["name"]})"/>')

    # stars (deterministic parametric scatter, upper sky only)
    for i in range(26):
        sx = x0 + (i * 67 + 23) % PANEL_W
        sy = y0 + (i * 41 + 11) % 150
        r = 1.6 if i % 5 == 0 else 1.0
        s.append(f'<circle cx="{sx}" cy="{sy}" r="{r}" fill="{t["star"]}" '
                 f'opacity="{0.35 + (i % 4) * 0.15:.2f}"/>')

    # banded sun with glow
    s.append(f'<g filter="url(#glow-{t["name"]})">'
             f'<circle cx="{cx}" cy="{sun_cy}" r="{sun_r}" fill="url(#sun-{t["name"]})"/></g>')
    s.append(f'<clipPath id="sun-clip-{t["name"]}">'
             f'<circle cx="{cx}" cy="{sun_cy}" r="{sun_r}"/></clipPath>')
    s.append(f'<g clip-path="url(#sun-clip-{t["name"]})">')
    band_y, band_h = sun_cy, 3.0
    while band_y < sun_cy + sun_r:
        s.append(f'<rect x="{cx - sun_r}" y="{band_y:.1f}" width="{sun_r * 2}" '
                 f'height="{band_h:.1f}" fill="url(#sky-{t["name"]})"/>')
        band_y += band_h + 11
        band_h += 2.2
    s.append('</g>')

    # neon perspective grid floor
    s.append(f'<rect x="{x0}" y="{fy}" width="{PANEL_W}" height="{floor_h}" '
             f'fill="{t["floor"]}"/>')
    s.append(f'<g stroke="{t["grid_line"]}" stroke-width="1.1" opacity="0.85" '
             f'filter="url(#glow-{t["name"]})">')
    gy, step = fy, 6.0
    while gy <= y0 + PANEL_H:
        s.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x0 + PANEL_W}" y2="{gy:.1f}"/>')
        gy += step
        step *= 1.45
    for i in range(-6, 7):
        s.append(f'<line x1="{cx + i * 34}" y1="{y0 + PANEL_H}" x2="{cx + i * 7}" y2="{fy}"/>')
    s.append('</g>')

    # portrait: smooth = one embedded soft bitmap; pixel = crisp rect runs
    if smooth:
        b64 = portrait_png(grid)
        s.append(f'<image x="{ax}" y="{ay}" width="{art_w}" height="{art_h}" '
                 f'href="data:image/png;base64,{b64}"/>')
        s.append('<g>')
    else:
        s.append('<g shape-rendering="crispEdges">')
    if not smooth:
        for row, line in enumerate(grid):
            col = 0
            while col < gw:
                c = line[col]
                if c is None:
                    col += 1
                    continue
                run = 1
                while col + run < gw and line[col + run] == c:
                    run += 1
                s.append(f'<rect x="{ax + col * cell}" y="{ay + row * cell}" '
                         f'width="{run * cell}" height="{cell}" fill="{_rgb_hex(c)}"/>')
                col += run
    s.append('</g>')

    s.append('</g>')  # end clip
    s.append(f'<rect x="{x0}" y="{y0}" width="{PANEL_W}" height="{PANEL_H}" '
             f'rx="14" fill="none" stroke="{t["grid_line"]}" stroke-width="1.5" opacity="0.6"/>')
    return "\n".join(s)


def spec_column(t):
    s = []
    y = PAD + 34
    lh = 27
    fs = 15
    s.append(f'<g font-family="{MONO}" font-size="{fs}">')
    s.append(f'<text x="{TEXT_X}" y="{y}" fill="{t["header"]}" font-weight="bold">'
             f'anmol@behl1anmol</text>')
    y += lh - 6
    s.append(f'<text x="{TEXT_X}" y="{y}" fill="{t["dim"]}">----------------</text>')
    y += lh
    label_w = 11  # widest label "Frameworks" + colon padding
    for label, value in SPECS:
        pad = " " * (label_w - len(label))
        s.append(f'<text x="{TEXT_X}" y="{y}"><tspan fill="{t["label"]}" '
                 f'font-weight="bold">{label}:</tspan><tspan fill="{t["value"]}">'
                 f'{pad}{value}</tspan></text>')
        y += lh
    s.append('</g>')

    # palette strip
    y += 6
    sw, sh = 34, 20
    for i, c in enumerate(SWATCHES):
        s.append(f'<rect x="{TEXT_X + i * sw}" y="{y}" width="{sw}" height="{sh}" fill="{c}"/>')
    return "\n".join(s)


def footer(t):
    y = CARD_H - 26
    return (
        f'<g font-family="{MONO}" font-size="15">'
        f'<text x="{PAD}" y="{y}" fill="{t["prompt"]}">anmol&#160;~/projects&#160;&gt;</text>'
        f'<rect x="{PAD + 168}" y="{y - 13}" width="9" height="17" fill="{t["cursor"]}">'
        f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" '
        f'dur="1.2s" repeatCount="indefinite"/></rect></g>'
    )


def render(t, grid, smooth=False):
    defs = f'''<defs>
<linearGradient id="sky-{t["name"]}" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{t["sky_top"]}"/>
  <stop offset="0.62" stop-color="{t["sky_mid"]}"/>
  <stop offset="1" stop-color="{t["sky_low"]}"/>
</linearGradient>
<linearGradient id="sun-{t["name"]}" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="{t["sun_top"]}"/>
  <stop offset="1" stop-color="{t["sun_bottom"]}"/>
</linearGradient>
<filter id="glow-{t["name"]}" x="-40%" y="-40%" width="180%" height="180%">
  <feGaussianBlur stdDeviation="2.4" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
</filter>
</defs>'''
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {CARD_W} {CARD_H}" '
        f'width="{CARD_W}" height="{CARD_H}" role="img" '
        f'aria-label="Anmol Behl - neofetch style profile card">',
        defs,
        f'<rect x="1" y="1" width="{CARD_W - 2}" height="{CARD_H - 2}" rx="18" '
        f'fill="{t["card"]}" stroke="{t["card_border"]}" stroke-width="2"/>',
        portrait_scene(t, grid, smooth),
        spec_column(t),
        footer(t),
        '</svg>',
    ]
    return "\n".join(parts)


def main():
    if os.environ.get("DEBUG_GRID"):
        grid = build_portrait_grid(int(os.environ.get("DEBUG_GRID_W", GRID_W)))
        debug_print(grid)
        debug_png(grid, os.environ.get("DEBUG_PNG", "/tmp/portrait_debug.png"))
        return
    pixel = bool(os.environ.get("PIXEL_MODE"))
    grid = build_portrait_grid(GRID_W if pixel else GRID_W * 2)
    for theme, path in ((DARK, OUT_DARK), (LIGHT, OUT_LIGHT)):
        svg = render(theme, grid, smooth=not pixel)
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"wrote {path} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
