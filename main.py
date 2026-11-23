#!/usr/bin/env python3
"""News-image 22 Nov 2026 - v6. Front-page newspaper, drawn from scratch.

Pure Python 3.13 stdlib. Draws a 1024x1024 PNG of Sunday 22 November 2026
world news (38 stories, 10 regions, 13 numbered) and writes it to
$MAKEFUN_OUTPUT_DIR/entry.png (fallback /output/entry.png).
Deterministic: no time, no randomness, no network.
"""
import os
import struct
import zlib
from math import cos, sin, pi, sqrt

W = 1024
H = 1024

PAPER = (247, 243, 232)
INK = (22, 22, 22)
NAVY = (26, 43, 74)
NAVY2 = (38, 58, 96)
RED = (176, 32, 32)
RED2 = (198, 52, 44)
GREY = (96, 90, 80)
LGREY = (120, 114, 102)
RULE = (180, 172, 156)
WHITE = (255, 255, 255)
CREAM = (252, 249, 240)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w=W, h=H, bg=PAPER):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)
        r, g, b = bg
        for i in range(0, len(self.px), 3):
            self.px[i] = r
            self.px[i + 1] = g
            self.px[i + 2] = b

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = c[0]
            self.px[i + 1] = c[1]
            self.px[i + 2] = c[2]

    def blend(self, x, y, c, a):
        """Blend colour c with coverage a (0..1) onto pixel."""
        if a <= 0.0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a >= 1.0:
            self.set(x, y, c)
            return
        i = (y * self.w + x) * 3
        self.px[i] = int(c[0] * a + self.px[i] * (1 - a))
        self.px[i + 1] = int(c[1] * a + self.px[i + 1] * (1 - a))
        self.px[i + 2] = int(c[2] * a + self.px[i + 2] * (1 - a))

    def rect(self, x, y, w, h, c):
        x0 = max(0, int(x))
        y0 = max(0, int(y))
        x1 = min(self.w, int(x + w))
        y1 = min(self.h, int(y + h))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def hline(self, x, y, w, c, th=1):
        self.rect(x, y, w, th, c)

    def vgrad(self, x, y, w, h, top, bot):
        """Vertical gradient rectangle."""
        if h <= 0 or w <= 0:
            return
        for yy in range(int(y), int(y + h)):
            t = (yy - y) / max(1, h - 1)
            c = (int(top[0] + (bot[0] - top[0]) * t),
                 int(top[1] + (bot[1] - top[1]) * t),
                 int(top[2] + (bot[2] - top[2]) * t))
            self.rect(x, yy, w, 1, c)

    def circle(self, cx, cy, r, c):
        r = int(r)
        for dy in range(-r, r + 1):
            dx = int(sqrt(max(0, r * r - dy * dy)))
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def disc(self, cx, cy, r, c):
        self.circle(cx, cy, r, c)

    def ellipse(self, cx, cy, rx, ry, c):
        rx = int(rx)
        ry = int(ry)
        for dy in range(-ry, ry + 1):
            t = 1 - (dy * dy) / max(1, ry * ry)
            dx = int(rx * sqrt(max(0, t)))
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, th, c):
        for dy in range(-r, r + 1):
            dx = int(sqrt(max(0, r * r - dy * dy)))
            dx2 = int(sqrt(max(0, (r - th) * (r - th) - dy * dy))) if abs(dy) < r - th else 0
            self.rect(cx - dx, cy + dy, dx - dx2, 1, c)
            self.rect(cx + dx2 + 1, cy + dy, dx - dx2, 1, c)

    def poly(self, pts, c):
        """Scanline fill of a polygon (list of (x, y))."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(min(ys)))
        y1 = min(self.h - 1, int(max(ys)) + 1)
        n = len(pts)
        for yy in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1a = pts[i]
                x2, y2a = pts[(i + 1) % n]
                if (y1a <= yy < y2a) or (y2a <= yy < y1a):
                    t = (yy - y1a) / (y2a - y1a) if y2a != y1a else 0
                    xs.append(x1 + t * (x2 - x1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                self.rect(int(xs[k]), yy, max(1, int(xs[k + 1]) - int(xs[k])), 1, c)

    def thick_line(self, x1, y1, x2, y2, th, c):
        dx = x2 - x1
        dy = y2 - y1
        ln = sqrt(dx * dx + dy * dy) or 1
        nx = -dy / ln * th / 2
        ny = dx / ln * th / 2
        self.poly([(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
                   (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)], c)

    def frame(self, x, y, w, h, c, th=1):
        self.rect(x, y, w, th, c)
        self.rect(x, y + h - th, w, th, c)
        self.rect(x, y, th, h, c)
        self.rect(x + w - th, y, th, h, c)


def png_bytes(cv):
    raw = bytearray()
    for yy in range(cv.h):
        raw.append(0)
        i = yy * cv.w * 3
        raw += cv.px[i:i + cv.w * 3]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(kind, data):
        out = struct.pack(">I", len(data)) + kind + data
        out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


# ---------------------------------------------------------------- font
# Hand-built stroke serif. Cap height = 1.0 em. y: 0 = cap top, 1 = baseline,
# 1.28 = descender bottom, 0.30 = x-height top.
# Thickness (em): vertical TV = 0.155, horizontal TH = 0.105  -> ratio 1.48.
# Diagonal TD = 0.13. Serifs are short horizontal ticks (0.055 thick).
TV = 0.155
TH = 0.105
TD = 0.13
SS = 4  # supersampling factor (v6: 4x, up from 3x)

# A stroke: (kind, data, thick) where thick may be a float or ("var", tv, th)
# for arcs whose thickness varies with angle (thick at sides, thin top/bottom).
#   L: (x1, y1, x2, y2)          straight line
#   B: (x1,y1, cx1,cy1, cx2,cy2, x2,y2)  cubic bezier spine
#   A: (cx, cy, rx, ry, a0, a1)  arc, angles in degrees, 0 = east, ccw negative y
#   D: (cx, cy, r)               filled disc


def _bez(p0, p1, p2, p3, n=22):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


def _arc_pts(cx, cy, rx, ry, a0, a1, n=28):
    pts = []
    steps = max(4, int(abs(a1 - a0) / 9) + 2)
    for i in range(steps + 1):
        a = (a0 + (a1 - a0) * i / steps) * pi / 180.0
        pts.append((cx + rx * cos(a), cy - ry * sin(a)))
    return pts


def _flatten(stroke):
    """Return list of (x, y, thick) points along the stroke spine."""
    kind, data, th = stroke
    if kind == "L":
        x1, y1, x2, y2 = data
        return [(x1, y1, th), (x2, y2, th)]
    if kind == "B":
        pts = _bez((data[0], data[1]), (data[2], data[3]),
                   (data[4], data[5]), (data[6], data[7]))
        return [(x, y, th) for x, y in pts]
    if kind == "A":
        cx, cy, rx, ry, a0, a1 = data
        raw = _arc_pts(cx, cy, rx, ry, a0, a1)
        out = []
        for (x, y) in raw:
            if isinstance(th, tuple):  # ("var", tv, th)
                ang = 0.0
                # thickness by direction from centre: sides thick, top thin
                dx = (x - cx) / max(rx, 1e-6)
                w = abs(dx)  # 1 at sides, 0 at top/bottom
                t = th[2] + (th[1] - th[2]) * w
            else:
                t = th
            out.append((x, y, t))
        return out
    if kind == "D":
        return [(data[0], data[1], data[2] * 2)]
    return []


def _serif(x, y, wdt=0.09):
    """Small horizontal serif tick centred on x at height y."""
    return ("L", (x - wdt, y, x + wdt, y), 0.055)


_glyph_cache = {}


def render_glyph(ch, size):
    """Return (mask, w_px, h_px, xoff, yoff): mask is rows of 0..1 floats at
    display resolution (already downsampled from SS). yoff = top of tile
    relative to cap top (negative for ascenders handled by caller)."""
    key = (ch, size)
    if key in _glyph_cache:
        return _glyph_cache[key]
    spec = GLYPHS.get(ch)
    if spec is None:
        spec = GLYPHS["?"]
    gw, strokes = spec
    s = float(size)  # cap height in px
    # tile in subpixels
    tw = max(1, int((gw + 0.06) * s * SS))
    th = max(1, int(1.34 * s * SS))
    buf = [0.0] * (tw * th)
    # rasterise each stroke segment into the subpixel buffer
    for stroke in strokes:
        pts = _flatten(stroke)
        if stroke[0] == "D":
            cx, cy, r = stroke[1]
            rr = r * s * SS
            ccx = (cx + 0.03) * s * SS
            ccy = cy * s * SS
            x0 = max(0, int(ccx - rr - 1))
            x1 = min(tw - 1, int(ccx + rr + 1))
            y0 = max(0, int(ccy - rr - 1))
            y1 = min(th - 1, int(ccy + rr + 1))
            for yy in range(y0, y1 + 1):
                for xx in range(x0, x1 + 1):
                    dx = (xx + 0.5 - ccx) / max(rr, 1e-6)
                    dy = (yy + 0.5 - ccy) / max(rr, 1e-6)
                    if dx * dx + dy * dy <= 1.0:
                        buf[yy * tw + xx] = 1.0
            continue
        for i in range(len(pts) - 1):
            x1, y1, t1 = pts[i]
            x2, y2, t2 = pts[i + 1]
            px1 = (x1 + 0.03) * s * SS
            py1 = y1 * s * SS
            px2 = (x2 + 0.03) * s * SS
            py2 = y2 * s * SS
            half = max(t1, t2) * s * SS / 2.0
            bx0 = max(0, int(min(px1, px2) - half - 1))
            bx1 = min(tw - 1, int(max(px1, px2) + half + 1))
            by0 = max(0, int(min(py1, py2) - half - 1))
            by1 = min(th - 1, int(max(py1, py2) + half + 1))
            dx = px2 - px1
            dy = py2 - py1
            ln2 = dx * dx + dy * dy
            for yy in range(by0, by1 + 1):
                cy2 = yy + 0.5
                for xx in range(bx0, bx1 + 1):
                    cx2 = xx + 0.5
                    if ln2 <= 1e-9:
                        d = sqrt((cx2 - px1) ** 2 + (cy2 - py1) ** 2)
                    else:
                        t = ((cx2 - px1) * dx + (cy2 - py1) * dy) / ln2
                        t = 0.0 if t < 0 else (1.0 if t > 1 else t)
                        qx = px1 + t * dx
                        qy = py1 + t * dy
                        d = sqrt((cx2 - qx) ** 2 + (cy2 - qy) ** 2)
                    # per-point thickness (linear interp along segment)
                    tt = (t1 + (t2 - t1) * t) * s * SS / 2.0 if ln2 > 1e-9 else t1 * s * SS / 2.0
                    if d <= tt:
                        buf[yy * tw + xx] = 1.0
    # downsample SS x SS -> display mask
    dw = (tw + SS - 1) // SS
    dh = (th + SS - 1) // SS
    mask = []
    for yy in range(dh):
        row = []
        for xx in range(dw):
            tot = 0.0
            cnt = 0
            for sy in range(SS):
                for sx in range(SS):
                    ix = xx * SS + sx
                    iy = yy * SS + sy
                    if ix < tw and iy < th:
                        tot += buf[iy * tw + ix]
                        cnt += 1
            row.append(tot / max(1, cnt))
        mask.append(row)
    res = (mask, dw, dh, 0, 0)
    _glyph_cache[key] = res
    return res


def glyph_width(ch, size):
    spec = GLYPHS.get(ch, GLYPHS["?"])
    return spec[0] * size


def text_width(text, size, tracking=0.0):
    w = 0.0
    for ch in text:
        if ch == " ":
            w += size * 0.30
        else:
            w += glyph_width(ch, size) + tracking
    return w - tracking if text else 0.0


def draw_text(cv, x, y, text, size, color, tracking=0.0, italic=False,
              align="left"):
    """Draw text; y = top of cap height. Returns width drawn."""
    if align == "center":
        x -= text_width(text, size, tracking) / 2
    elif align == "right":
        x -= text_width(text, size, tracking)
    cx = float(x)
    for ch in text:
        if ch == " ":
            cx += size * 0.30 + tracking
            continue
        mask, dw, dh, _, _ = render_glyph(ch, size)
        for yy in range(dh):
            shear = int(0.16 * size * (yy / max(1, dh))) if italic else 0
            for xx in range(dw):
                a = mask[yy][xx]
                if a > 0.0:
                    cv.blend(int(cx) + xx + shear, int(y) + yy, color, a)
        cx += glyph_width(ch, size) + tracking
    return cx - x


def wrap_text(text, size, max_w, tracking=0.0):
    """Greedy wrap into lines fitting max_w. Returns list of lines."""
    words = text.split(" ")
    lines = []
    cur = ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if text_width(trial, size, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- glyphs
def _v(x, y0=0.0, y1=1.0, t=TV):
    return ("L", (x, y0, x, y1), t)


def _h(x0, x1, y, t=TH):
    return ("L", (x0, y, x1, y), t)


def _d(x1, y1, x2, y2, t=TD):
    return ("L", (x1, y1, x2, y2), t)


def _a(cx, cy, rx, ry, a0, a1, t=("var", TV, TH)):
    return ("A", (cx, cy, rx, ry, a0, a1), t)


def _b(x1, y1, c1x, c1y, c2x, c2y, x2, y2, t=TD):
    return ("B", (x1, y1, c1x, c1y, c2x, c2y, x2, y2), t)


def _o(cx, cy, rx, ry):
    return ("A", (cx, cy, rx, ry, 0, 360), ("var", TV, TH))


def _dot(cx, cy, r=0.07):
    return ("D", (cx, cy, r), 0)


# S spine (critical): two curved lobes, upper smaller than lower.
# Each lobe is an arc (thick, uniform) joined by a diagonal sweep.
S_TOP = [
    _a(0.36, 0.26, 0.24, 0.20, 30, 230, 0.12),
    _b(0.21, 0.41, 0.30, 0.50, 0.42, 0.48, 0.51, 0.56, 0.12),
    _a(0.36, 0.74, 0.26, 0.22, 55, -175, 0.12),
]
S_LOW = [
    _a(0.32, 0.48, 0.21, 0.17, 30, 230, 0.10),
    _b(0.19, 0.61, 0.26, 0.68, 0.36, 0.66, 0.45, 0.65, 0.10),
    _a(0.32, 0.80, 0.22, 0.18, 55, -175, 0.10),
]

GLYPHS = {}
# ---- capitals
GLYPHS["A"] = (0.78, [_d(0.10, 1.0, 0.39, 0.0), _d(0.68, 1.0, 0.39, 0.0),
                     _h(0.24, 0.54, 0.68), _serif(0.10, 1.0), _serif(0.68, 1.0)])
GLYPHS["B"] = (0.68, [_v(0.12), _serif(0.12, 0.0), _serif(0.12, 1.0),
                      _a(0.34, 0.25, 0.24, 0.25, -90, 90, ("var", TV, TH)),
                      _a(0.36, 0.75, 0.26, 0.25, -90, 90, ("var", TV, TH)),
                      _h(0.12, 0.36, 0.50, TH)])
GLYPHS["C"] = (0.72, [_a(0.38, 0.50, 0.32, 0.50, 55, 305)])
GLYPHS["D"] = (0.74, [_v(0.12), _serif(0.12, 0.0), _serif(0.12, 1.0),
                      _a(0.14, 0.50, 0.34, 0.50, -90, 90, ("var", TV, TH)),
                      _h(0.12, 0.20, 0.0, TH), _h(0.12, 0.20, 1.0, TH)])
GLYPHS["E"] = (0.62, [_v(0.12), _serif(0.12, 0.0), _serif(0.12, 1.0),
                      _h(0.12, 0.56, 0.0), _h(0.12, 0.48, 0.50), _h(0.12, 0.56, 1.0)])
GLYPHS["F"] = (0.58, [_v(0.12), _serif(0.12, 0.0), _serif(0.12, 1.0),
                      _h(0.12, 0.54, 0.0), _h(0.12, 0.46, 0.50)])
GLYPHS["G"] = (0.76, [_a(0.40, 0.50, 0.33, 0.50, 55, 305),
                      _h(0.42, 0.70, 0.58, TH), _v(0.66, 0.58, 0.86, TV)])
GLYPHS["H"] = (0.74, [_v(0.12), _v(0.62), _serif(0.12, 0.0), _serif(0.12, 1.0),
                      _serif(0.62, 0.0), _serif(0.62, 1.0), _h(0.12, 0.62, 0.52)])
GLYPHS["I"] = (0.34, [_v(0.17), _h(0.06, 0.28, 0.0, 0.06), _h(0.06, 0.28, 1.0, 0.06)])
GLYPHS["J"] = (0.52, [_h(0.14, 0.46, 0.0, 0.06), _v(0.36, 0.0, 0.82),
                      _a(0.24, 0.82, 0.12, 0.16, -90, 180, TD)])
GLYPHS["K"] = (0.70, [_v(0.12), _serif(0.12, 0.0), _serif(0.12, 1.0),
                      _d(0.42, 0.52, 0.14, 0.52, TD), _d(0.36, 0.48, 0.66, 1.0, TD)])
GLYPHS["L"] = (0.58, [_v(0.12), _serif(0.12, 0.0), _h(0.12, 0.54, 1.0)])
GLYPHS["M"] = (0.88, [_v(0.10), _v(0.78), _d(0.10, 0.0, 0.44, 0.52, TD),
                      _d(0.78, 0.0, 0.44, 0.52, TD), _serif(0.10, 1.0), _serif(0.78, 1.0)])
GLYPHS["N"] = (0.76, [_v(0.12), _v(0.64), _d(0.12, 0.0, 0.64, 1.0, TD),
                      _serif(0.12, 1.0), _serif(0.64, 1.0)])
GLYPHS["O"] = (0.80, [_o(0.40, 0.50, 0.34, 0.50)])
GLYPHS["P"] = (0.64, [_v(0.12), _serif(0.12, 0.0), _serif(0.12, 1.0),
                      _a(0.14, 0.27, 0.26, 0.27, -90, 90, ("var", TV, TH)),
                      _h(0.12, 0.16, 0.54, TH)])
GLYPHS["Q"] = (0.80, [_o(0.40, 0.50, 0.34, 0.50), _d(0.58, 0.78, 0.74, 1.02, TD)])
GLYPHS["R"] = (0.68, [_v(0.12), _serif(0.12, 0.0), _serif(0.12, 1.0),
                      _a(0.14, 0.27, 0.26, 0.27, -90, 90, ("var", TV, TH)),
                      _h(0.12, 0.16, 0.54, TH), _d(0.38, 0.52, 0.66, 1.0, TD)])
GLYPHS["S"] = (0.70, S_TOP)
GLYPHS["T"] = (0.66, [_h(0.06, 0.60, 0.0), _v(0.33), _serif(0.33, 1.0)])
GLYPHS["U"] = (0.74, [_v(0.12, 0.0, 0.78), _v(0.62, 0.0, 0.78),
                      _a(0.37, 0.78, 0.25, 0.22, 180, 360, ("var", TH, TH)),
                      _serif(0.12, 0.0), _serif(0.62, 0.0)])
GLYPHS["V"] = (0.74, [_d(0.08, 0.0, 0.37, 1.0, TD), _d(0.66, 0.0, 0.37, 1.0, TD),
                      _serif(0.08, 0.0), _serif(0.66, 0.0)])
GLYPHS["W"] = (0.96, [_d(0.06, 0.0, 0.26, 1.0, TD), _d(0.26, 1.0, 0.48, 0.0, TD),
                      _d(0.48, 0.0, 0.70, 1.0, TD), _d(0.70, 1.0, 0.90, 0.0, TD)])
GLYPHS["X"] = (0.70, [_d(0.10, 0.0, 0.60, 1.0, TD), _d(0.60, 0.0, 0.10, 1.0, TD)])
GLYPHS["Y"] = (0.68, [_d(0.08, 0.0, 0.34, 0.52, TD), _d(0.60, 0.0, 0.34, 0.52, TD),
                      _v(0.34, 0.52, 1.0), _serif(0.34, 1.0)])
GLYPHS["Z"] = (0.66, [_h(0.08, 0.58, 0.0), _h(0.08, 0.58, 1.0),
                      _d(0.58, 0.0, 0.08, 1.0, TD)])
# ---- lowercase (x-height top 0.30, baseline 1.0)
GLYPHS["a"] = (0.60, [_o(0.29, 0.65, 0.23, 0.35), _v(0.54, 0.30, 1.0),
                      _h(0.28, 0.54, 0.32, TH), _serif(0.54, 1.0)])
GLYPHS["b"] = (0.58, [_v(0.12, 0.0, 1.0), _o(0.32, 0.65, 0.22, 0.35),
                      _serif(0.12, 1.0)])
GLYPHS["c"] = (0.56, [_a(0.30, 0.65, 0.24, 0.35, 55, 305)])
GLYPHS["d"] = (0.58, [_o(0.26, 0.65, 0.22, 0.35), _v(0.50, 0.0, 1.0),
                      _serif(0.50, 1.0)])
GLYPHS["e"] = (0.58, [_a(0.30, 0.68, 0.25, 0.32, -35, 295),
                      _h(0.07, 0.55, 0.68, TH)])
GLYPHS["f"] = (0.40, [_v(0.22, 0.10, 1.0), _a(0.22, 0.18, 0.12, 0.16, 0, 180, TD),
                      _h(0.08, 0.34, 0.55, TH)])
GLYPHS["g"] = (0.60, [_o(0.29, 0.65, 0.23, 0.35), _v(0.54, 0.30, 1.24),
                      _a(0.42, 1.24, 0.12, 0.10, 180, 360, TD)])
GLYPHS["h"] = (0.56, [_v(0.12, 0.0, 1.0), _v(0.44, 0.52, 1.0),
                      _a(0.28, 0.52, 0.16, 0.22, 0, 180, ("var", TV, TH)),
                      _serif(0.12, 1.0)])
GLYPHS["i"] = (0.28, [_v(0.14, 0.30, 1.0), _dot(0.14, 0.14, 0.065), _serif(0.14, 1.0)])
GLYPHS["j"] = (0.32, [_v(0.16, 0.30, 1.16), _a(0.10, 1.16, 0.08, 0.10, 180, 360, TD),
                      _dot(0.16, 0.14, 0.065)])
GLYPHS["k"] = (0.56, [_v(0.12, 0.0, 1.0), _d(0.40, 0.62, 0.14, 0.62, TD),
                      _d(0.34, 0.60, 0.52, 1.0, TD), _serif(0.12, 1.0)])
GLYPHS["l"] = (0.28, [_v(0.14, 0.0, 1.0), _serif(0.14, 1.0)])
GLYPHS["m"] = (0.84, [_v(0.10, 0.30, 1.0), _v(0.40, 0.52, 1.0), _v(0.72, 0.52, 1.0),
                      _a(0.25, 0.52, 0.15, 0.22, 0, 180, ("var", TV, TH)),
                      _a(0.56, 0.52, 0.16, 0.22, 0, 180, ("var", TV, TH))])
GLYPHS["n"] = (0.56, [_v(0.12, 0.30, 1.0), _v(0.44, 0.52, 1.0),
                      _a(0.28, 0.52, 0.16, 0.22, 0, 180, ("var", TV, TH)),
                      _serif(0.12, 1.0)])
GLYPHS["o"] = (0.58, [_o(0.29, 0.65, 0.23, 0.35)])
GLYPHS["p"] = (0.58, [_v(0.12, 0.30, 1.28), _o(0.32, 0.65, 0.22, 0.35)])
GLYPHS["q"] = (0.58, [_o(0.26, 0.65, 0.22, 0.35), _v(0.50, 0.30, 1.28)])
GLYPHS["r"] = (0.42, [_v(0.12, 0.30, 1.0), _a(0.24, 0.52, 0.12, 0.20, 0, 160, TD),
                      _serif(0.12, 1.0)])
GLYPHS["s"] = (0.58, S_LOW)
GLYPHS["t"] = (0.40, [_v(0.20, 0.08, 1.0), _h(0.06, 0.34, 0.55, TH),
                      _a(0.20, 0.92, 0.10, 0.10, 180, 270, TD), _serif(0.20, 0.0)])
GLYPHS["u"] = (0.56, [_v(0.12, 0.30, 0.82), _v(0.44, 0.30, 0.82),
                      _a(0.28, 0.82, 0.16, 0.18, 180, 360, ("var", TH, TH)),
                      _serif(0.44, 0.30)])
GLYPHS["v"] = (0.56, [_d(0.08, 0.30, 0.28, 1.0, TD), _d(0.48, 0.30, 0.28, 1.0, TD)])
GLYPHS["w"] = (0.80, [_d(0.06, 0.30, 0.21, 1.0, TD), _d(0.21, 1.0, 0.40, 0.30, TD),
                      _d(0.40, 0.30, 0.59, 1.0, TD), _d(0.59, 1.0, 0.74, 0.30, TD)])
GLYPHS["x"] = (0.54, [_d(0.08, 0.30, 0.46, 1.0, TD), _d(0.46, 0.30, 0.08, 1.0, TD)])
GLYPHS["y"] = (0.56, [_d(0.08, 0.30, 0.28, 0.82, TD), _d(0.48, 0.30, 0.28, 0.82, TD),
                      _d(0.28, 0.82, 0.14, 1.28, TD)])
GLYPHS["z"] = (0.52, [_h(0.08, 0.46, 0.30, TH), _h(0.08, 0.46, 1.0, TH),
                      _d(0.46, 0.30, 0.08, 1.0, TD)])
# ---- digits
GLYPHS["0"] = (0.66, [_o(0.33, 0.50, 0.27, 0.50)])
GLYPHS["1"] = (0.40, [_d(0.12, 0.22, 0.24, 0.02, TD), _v(0.24, 0.02, 1.0),
                      _h(0.10, 0.36, 1.0, 0.06)])
GLYPHS["2"] = (0.64, [_b(0.12, 0.52, 0.08, 0.08, 0.30, -0.02, 0.50, 0.10, TD),
                      _b(0.50, 0.10, 0.62, 0.22, 0.50, 0.44, 0.30, 0.62, TD),
                      _d(0.30, 0.62, 0.08, 1.0, TD), _h(0.08, 0.58, 1.0, TH)])
GLYPHS["3"] = (0.64, [_a(0.34, 0.26, 0.24, 0.26, -80, 110, ("var", TV, TH)),
                      _a(0.34, 0.74, 0.26, 0.26, -80, 110, ("var", TV, TH))])
GLYPHS["4"] = (0.66, [_d(0.48, 0.0, 0.10, 0.68, TD), _h(0.08, 0.56, 0.68, TH),
                      _v(0.44, 0.0, 1.0)])
GLYPHS["5"] = (0.62, [_h(0.10, 0.54, 0.0, TH), _v(0.12, 0.0, 0.52),
                      _a(0.34, 0.74, 0.24, 0.26, 160, 380, ("var", TV, TH))])
GLYPHS["6"] = (0.64, [_b(0.52, 0.02, 0.28, 0.08, 0.10, 0.30, 0.12, 0.58, TD),
                      _a(0.32, 0.68, 0.24, 0.30, 90, 430, ("var", TV, TH))])
GLYPHS["7"] = (0.62, [_h(0.08, 0.56, 0.0, TH), _d(0.56, 0.0, 0.22, 1.0, TD)])
GLYPHS["8"] = (0.66, [_o(0.33, 0.27, 0.24, 0.27), _o(0.33, 0.73, 0.26, 0.27)])
GLYPHS["9"] = (0.64, [_a(0.32, 0.38, 0.26, 0.38, 0, 320, ("var", TV, TH)),
                      _v(0.56, 0.30, 1.0)])
# ---- punctuation
GLYPHS["."] = (0.30, [_dot(0.15, 0.94, 0.075)])
GLYPHS[","] = (0.30, [_dot(0.15, 0.92, 0.07),
                      _b(0.20, 0.94, 0.18, 1.06, 0.10, 1.12, 0.06, 1.22, 0.07)])
GLYPHS[":"] = (0.30, [_dot(0.15, 0.36, 0.07), _dot(0.15, 0.86, 0.07)])
GLYPHS[";"] = (0.30, [_dot(0.15, 0.36, 0.07), _dot(0.15, 0.86, 0.07),
                      _b(0.20, 0.90, 0.18, 1.04, 0.10, 1.10, 0.06, 1.20, 0.07)])
GLYPHS["'"] = (0.28, [_d(0.16, 0.02, 0.10, 0.30, 0.09)])
GLYPHS['"'] = (0.44, [_d(0.14, 0.02, 0.08, 0.30, 0.09), _d(0.34, 0.02, 0.28, 0.30, 0.09)])
GLYPHS["%"] = (0.92, [_o(0.22, 0.24, 0.14, 0.24), _o(0.70, 0.76, 0.14, 0.24),
                      _d(0.78, 0.02, 0.14, 0.98, 0.09)])
GLYPHS["$"] = (0.62, [_a(0.31, 0.28, 0.19, 0.19, 30, 230, 0.11),
                      _b(0.18, 0.43, 0.26, 0.50, 0.36, 0.48, 0.44, 0.54, 0.11),
                      _a(0.31, 0.70, 0.21, 0.20, 55, -175, 0.11),
                      _v(0.31, -0.08, 1.08, 0.09)])
GLYPHS["/"] = (0.44, [_d(0.36, 0.0, 0.08, 1.0, TD)])
GLYPHS["-"] = (0.44, [_h(0.06, 0.38, 0.52, TH)])
GLYPHS["("] = (0.34, [_a(0.30, 0.50, 0.16, 0.50, 60, 300, TD)])
GLYPHS[")"] = (0.34, [_a(0.04, 0.50, 0.16, 0.50, -120, 120, TD)])
GLYPHS["."] = (0.30, [_dot(0.15, 0.94, 0.075)])
GLYPHS["\u00b7"] = (0.30, [_dot(0.15, 0.48, 0.07)])
GLYPHS["\u2014"] = (0.90, [_h(0.04, 0.86, 0.52, TH)])
GLYPHS["!"] = (0.30, [_v(0.15, 0.0, 0.72, TV), _dot(0.15, 0.92, 0.07)])
GLYPHS["?"] = (0.56, [_a(0.28, 0.28, 0.22, 0.26, -40, 220, TD),
                      _b(0.28, 0.50, 0.28, 0.62, 0.24, 0.68, 0.24, 0.76, 0.11),
                      _dot(0.24, 0.92, 0.07)])
GLYPHS["+"] = (0.56, [_h(0.06, 0.50, 0.50, TH), _v(0.28, 0.24, 0.76, TV)])
GLYPHS["="] = (0.56, [_h(0.06, 0.50, 0.38, TH), _h(0.06, 0.50, 0.66, TH)])
GLYPHS["?"] = (0.56, [_a(0.28, 0.28, 0.22, 0.26, -40, 220, TD),
                      _b(0.28, 0.50, 0.28, 0.62, 0.24, 0.68, 0.24, 0.76, 0.11),
                      _dot(0.24, 0.92, 0.07)])


# ---------------------------------------------------------------- illustrations
def _arc_seg(cv, cx, cy, r, a0, a1, th, c):
    """Thick arc segment (angles deg, 0=east, 90=up in screen coords)."""
    import math
    n = max(4, int(abs(a1 - a0) / 6) + 1)
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
    for i in range(len(pts) - 1):
        cv.thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], th, c)


def _windows(cv, x, y, w, h, cols, rows, lit, c=(250, 210, 90)):
    cw = w / cols
    chh = h / rows
    for r in range(rows):
        for cc in range(cols):
            if (r * cols + cc) % 3 != 2 or lit:
                cv.rect(x + cc * cw + 2, y + r * chh + 2,
                        max(2, cw - 4), max(2, chh - 4), c)


def hero_cop31(cv, x, y, w, h):
    cv.vgrad(x, y, w, 40, (96, 84, 66), (120, 106, 84))          # ceiling
    cv.vgrad(x, y + 40, w, h - 40, (236, 226, 202), (214, 200, 172))  # wall
    for lx in (x + w * 0.25, x + w * 0.75):                       # lamps
        cv.thick_line(lx, y + 2, lx, y + 22, 2, (60, 50, 40))
        cv.circle(lx, y + 28, 7, (255, 220, 120))
        cv.circle(lx, y + 28, 4, (255, 240, 170))
    cv.circle(x + w - 26, y + 52, 11, (252, 249, 240))            # clock
    cv.thick_line(x + w - 26, y + 52, x + w - 26, y + 44, 2, INK)
    cv.thick_line(x + w - 26, y + 52, x + w - 20, y + 52, 2, INK)
    cv.rect(x + 14, y + 48, w - 28, 26, RED)                      # NO DEAL banner
    draw_text(cv, x + w / 2, y + 51, "NO DEAL", 20, WHITE, align="center")
    for i, fx in enumerate((0.14, 0.32, 0.68, 0.86)):             # flags
        px = x + w * fx
        cv.thick_line(px, y + 78, px, y + 104, 2, (70, 60, 50))
        cv.rect(px, y + 78, 16, 10, [(30, 90, 160), (200, 40, 40),
                                     (40, 140, 60), (240, 200, 40)][i])
    cv.rect(x + 8, y + 108, w - 16, h - 108, (122, 88, 56))       # table
    cv.rect(x + 8, y + 108, w - 16, 4, (150, 112, 70))
    skins = [(232, 190, 150), (190, 140, 100), (240, 200, 160),
             (200, 150, 110), (235, 195, 155), (180, 130, 95)]
    suits = [(30, 50, 90), (90, 30, 30), (40, 90, 50),
             (120, 90, 30), (70, 70, 110), (30, 90, 90)]
    for i in range(6):
        cx = x + w * (0.10 + i * 0.16)
        cv.circle(cx, y + 96, 7, skins[i])
        cv.poly([(cx - 11, y + 104), (cx + 11, y + 104),
                 (cx + 8, y + 120), (cx - 8, y + 120)], suits[i])
        cv.rect(cx - 6, y + 112, 12, 5, WHITE)
    cv.rect(x + w * 0.42, y + 128, 34, 10, WHITE)                # papers
    cv.rect(x + w * 0.42, y + 131, 28, 1, GREY)


def hero_kyiv(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (8, 14, 36), (46, 56, 96))
    for sx, sy in ((0.08, 0.10), (0.22, 0.06), (0.38, 0.14), (0.52, 0.05),
                   (0.66, 0.12), (0.80, 0.07), (0.92, 0.16), (0.15, 0.22),
                   (0.45, 0.20), (0.72, 0.22), (0.30, 0.03), (0.86, 0.26)):
        cv.disc(x + w * sx, y + h * sy, 1, WHITE)
    cv.circle(x + w * 0.85, y + 22, 11, (240, 236, 210))          # moon
    cv.circle(x + w * 0.85, y + 22, 8, (250, 248, 232))
    for dx, dy in ((0.30, 0.30), (0.55, 0.22), (0.78, 0.32)):     # drones
        cx, cy = x + w * dx, y + h * dy
        cv.ellipse(cx, cy, 7, 2, (10, 10, 14))
        cv.disc(cx, cy, 1, (255, 60, 50))
    for bx, by in ((0.62, 0.18), (0.88, 0.12)):                   # searchlights
        cv.poly([(x + w * bx, y + h * 0.95), (x + w * (bx - 0.10), y + h * 0.30),
                 (x + w * (bx - 0.04), y + h * 0.30)], (150, 170, 210))
    bld = [(0.02, 0.55, 0.16, 0.45), (0.20, 0.42, 0.18, 0.58),
           (0.40, 0.48, 0.16, 0.52), (0.58, 0.36, 0.18, 0.64),
           (0.78, 0.50, 0.20, 0.50)]
    for bx, by, bw, bh in bld:
        cv.rect(x + w * bx, y + h * by, w * bw, h * bh, (16, 18, 30))
        _windows(cv, x + w * bx + 4, y + h * by + 6, w * bw - 8, h * bh - 12,
                 3, 5, False)
    cv.ellipse(x + w * 0.49, y + h * 0.92, 34, 10, (255, 120, 30))  # fire glow
    cv.poly([(x + w * 0.44, y + h * 0.98), (x + w * 0.49, y + h * 0.78),
             (x + w * 0.54, y + h * 0.98)], (255, 90, 20))
    cv.poly([(x + w * 0.47, y + h * 0.98), (x + w * 0.49, y + h * 0.86),
             (x + w * 0.51, y + h * 0.98)], (255, 210, 60))
    for sx, sy, sr in ((0.47, 0.70, 9), (0.51, 0.60, 12), (0.46, 0.50, 10)):
        cv.circle(x + w * sx, y + h * sy, sr, (90, 90, 100))
    cv.rect(x, y + h - 4, w, 4, (8, 10, 20))


def hero_manama(cv, x, y, w, h):
    cv.vgrad(x, y, w, h - 26, (244, 150, 84), (128, 74, 142))
    cv.circle(x + w * 0.78, y + 30, 13, (255, 226, 150))          # sun
    cv.rect(x, y + h - 26, w, 26, (28, 78, 128))                  # sea
    cv.hline(x + 8, y + h - 18, 60, (120, 170, 220), 2)
    cv.hline(x + w - 80, y + h - 12, 70, (120, 170, 220), 2)
    cv.hline(x + w * 0.4, y + h - 8, 50, (90, 140, 200), 2)
    for bx, bw, bh in ((0.03, 0.20, 0.42), (0.26, 0.16, 0.34), (0.44, 0.18, 0.38)):
        cv.rect(x + w * bx, y + h * (0.98 - bh) - 26, w * bw, h * bh + 26,
                (52, 44, 60))
        cv.rect(x + w * (bx + bw * 0.6), y + h * (0.98 - bh) - 40, 6, 18,
                (52, 44, 60))
        cv.circle(x + w * (bx + bw * 0.6) + 3, y + h * (0.98 - bh) - 46, 6,
                  (150, 140, 150))
    cv.thick_line(x + w * 0.72, y + h * 0.30, x + w * 0.72, y + h * 0.78, 5,
                  (200, 200, 205))                                 # radar pole
    cv.ellipse(x + w * 0.72, y + h * 0.30, 34, 20, (225, 225, 230))  # dish
    cv.ellipse(x + w * 0.72, y + h * 0.30, 26, 14, (180, 185, 195))
    cv.disc(x + w * 0.72, y + h * 0.30, 5, (120, 125, 135))
    for r in (48, 62, 76):
        _arc_seg(cv, x + w * 0.72, y + h * 0.30, r, 20, 160, 2, (255, 255, 255))
    cv.rect(x + w * 0.62, y + h * 0.78, w * 0.20, 8, (90, 95, 105))
    cv.frame(x + w - 92, y + 8, 84, 24, RED, 2)                     # DENIED stamp
    draw_text(cv, x + w - 50, y + 12, "DENIED", 14, RED, align="center")


def thumb_icj(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (196, 214, 232), (226, 230, 236))
    cv.rect(x + w * 0.18, y + h * 0.42, w * 0.64, h * 0.50, (248, 246, 240))
    cv.poly([(x + w * 0.12, y + h * 0.44), (x + w * 0.50, y + h * 0.16),
             (x + w * 0.88, y + h * 0.44)], (226, 220, 204))
    for i in range(5):
        cx = x + w * (0.24 + i * 0.13)
        cv.rect(cx, y + h * 0.46, 7, h * 0.42, (210, 204, 188))
    cv.rect(x + w * 0.14, y + h * 0.90, w * 0.72, 4, (180, 172, 156))
    cv.disc(x + w * 0.08, y + h * 0.20, 5, (250, 220, 90))
    cv.disc(x + w * 0.92, y + h * 0.24, 4, (250, 220, 90))


def thumb_hk(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (240, 236, 222), (214, 206, 188))
    cv.rect(x + w * 0.06, y + h * 0.42, w * 0.34, h * 0.48, (176, 32, 32))
    cv.rect(x + w * 0.06, y + h * 0.42, w * 0.34, 6, (140, 24, 24))
    cv.rect(x + w * 0.18, y + h * 0.30, 4, 14, WHITE)
    cv.rect(x + w * 0.16, y + h * 0.22, 8, 10, WHITE)
    draw_text(cv, x + w * 0.23, y + h * 0.58, "VOTE", 11, WHITE, align="center")
    cx, cy, r = x + w * 0.72, y + h * 0.42, 24
    _arc_seg(cv, cx, cy, r, 90, 90 + 355, 9, (176, 32, 32))
    _arc_seg(cv, cx, cy, r, 90 + 355, 450, 9, (190, 182, 166))
    cv.disc(cx, cy, 12, (240, 236, 222))
    draw_text(cv, cx, y + h * 0.80, "98.79%", 11, RED, align="center")


def thumb_cricket(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (150, 200, 240), (120, 180, 220))
    cv.rect(x, y + h * 0.45, w, h * 0.55, (70, 160, 70))
    cv.ellipse(x + w * 0.50, y + h * 0.72, w * 0.42, h * 0.20, (110, 190, 90))
    cv.rect(x + w * 0.42, y + h * 0.52, w * 0.16, h * 0.38, (222, 198, 150))
    cv.rect(x + w * 0.30, y + h * 0.30, 5, h * 0.30, (120, 90, 50))  # stumps
    cv.rect(x + w * 0.36, y + h * 0.30, 5, h * 0.30, (120, 90, 50))
    cv.rect(x + w * 0.42, y + h * 0.30, 5, h * 0.30, (120, 90, 50))
    cv.circle(x + w * 0.62, y + h * 0.42, 7, (240, 200, 160))       # batsman
    cv.thick_line(x + w * 0.62, y + h * 0.48, x + w * 0.60, y + h * 0.72, 5,
                  (30, 60, 140))
    cv.thick_line(x + w * 0.60, y + h * 0.52, x + w * 0.72, y + h * 0.66, 4,
                  (200, 170, 110))
    cv.disc(x + w * 0.80, y + h * 0.80, 4, (200, 40, 40))            # ball
    cv.rect(x + w * 0.68, y + h * 0.06, w * 0.28, 16, INK)
    draw_text(cv, x + w * 0.82, y + h * 0.06 + 2, "720/9", 12, WHITE, align="center")


def thumb_f1(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (30, 20, 60), (90, 60, 120))
    for i in range(6):
        cv.disc(x + w * (0.1 + i * 0.16), y + h * 0.10, 2, (255, 220, 120))
    cv.rect(x, y + h * 0.55, w, h * 0.45, (60, 60, 68))
    cv.rect(x, y + h * 0.55, w, 3, WHITE)
    cv.rect(x, y + h * 0.82, w, 3, (255, 220, 60))
    cv.rect(x + w * 0.18, y + h * 0.62, w * 0.42, 14, (20, 60, 180))  # car
    cv.poly([(x + w * 0.30, y + h * 0.62), (x + w * 0.38, y + h * 0.52),
             (x + w * 0.50, y + h * 0.52), (x + w * 0.54, y + h * 0.62)],
            (20, 60, 180))
    cv.disc(x + w * 0.26, y + h * 0.76, 7, INK)
    cv.disc(x + w * 0.52, y + h * 0.76, 7, INK)
    cv.disc(x + w * 0.26, y + h * 0.76, 3, (200, 200, 200))
    cv.disc(x + w * 0.52, y + h * 0.76, 3, (200, 200, 200))
    for i in range(3):                                                # flag
        for j in range(2):
            cv.rect(x + w * (0.74 + i * 0.05), y + h * (0.14 + j * 0.08), 9, 7,
                    INK if (i + j) % 2 == 0 else WHITE)
    cv.thick_line(x + w * 0.72, y + h * 0.12, x + w * 0.72, y + h * 0.44, 2, INK)


def thumb_nba(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (240, 230, 210), (220, 200, 170))
    cv.rect(x, y + h * 0.55, w, h * 0.45, (205, 130, 60))
    cv.hline(x, y + h * 0.72, w, WHITE, 2)
    cv.thick_line(x + w * 0.78, y + h * 0.10, x + w * 0.78, y + h * 0.55, 4, INK)
    cv.rect(x + w * 0.68, y + h * 0.08, 5, h * 0.30, INK)
    cv.rect(x + w * 0.60, y + h * 0.06, 16, 22, WHITE)
    cv.frame(x + w * 0.60, y + h * 0.06, 16, 22, RED, 2)
    cv.ring(x + w * 0.68, y + h * 0.32, 7, 2, RED)
    cv.circle(x + w * 0.30, y + h * 0.30, 9, (30, 60, 140))           # player
    cv.thick_line(x + w * 0.30, y + h * 0.38, x + w * 0.28, y + h * 0.62, 6,
                  (30, 60, 140))
    cv.circle(x + w * 0.52, y + h * 0.42, 8, (240, 110, 40))          # ball
    cv.rect(x + w * 0.06, y + h * 0.06, w * 0.34, 16, INK)
    draw_text(cv, x + w * 0.23, y + h * 0.06 + 2, "50 PTS", 12, WHITE, align="center")


def thumb_house(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (200, 216, 236), (232, 236, 240))
    cv.rect(x + w * 0.08, y + h * 0.48, w * 0.34, h * 0.44, (248, 246, 240))
    cv.ellipse(x + w * 0.25, y + h * 0.48, w * 0.17, h * 0.16, (248, 246, 240))
    cv.rect(x + w * 0.25, y + h * 0.26, 2, h * 0.10, INK)
    cv.rect(x + w * 0.25, y + h * 0.26, 12, 7, (30, 60, 140))
    for i in range(4):
        cv.rect(x + w * (0.12 + i * 0.08), y + h * 0.54, 5, h * 0.30, (210, 204, 188))
    cv.rect(x + w * 0.06, y + h * 0.90, w * 0.38, 4, (180, 172, 156))
    bx, by = x + w * 0.52, y + h * 0.30
    cv.rect(bx, by + 34, 26, 26, (30, 90, 180))                       # 258 bar
    cv.rect(bx + 32, by + 46, 26, 14, (200, 60, 60))                  # 177 bar
    draw_text(cv, bx + 13, by + 6, "258", 13, (30, 90, 180), align="center")
    draw_text(cv, bx + 45, by + 20, "177", 11, (200, 60, 60), align="center")
    draw_text(cv, bx + 26, by + 64, "435 seats", 10, INK, align="center")


def thumb_ukeu(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (210, 222, 238), (236, 234, 226))
    for i, (fx, col) in enumerate(((0.10, None), (0.52, None))):
        px = x + w * fx
        cv.thick_line(px, y + h * 0.14, px, y + h * 0.72, 3, (90, 80, 70))
        if i == 0:                                                     # Union Jack
            cv.rect(px, y + h * 0.14, 52, 30, (20, 50, 140))
            cv.rect(px, y + h * 0.14 + 12, 52, 6, WHITE)
            cv.rect(px + 23, y + h * 0.14, 6, 30, WHITE)
            cv.rect(px, y + h * 0.14 + 13, 52, 4, (200, 40, 40))
            cv.rect(px + 24, y + h * 0.14, 4, 30, (200, 40, 40))
        else:                                                          # EU flag
            cv.rect(px, y + h * 0.14, 52, 30, (20, 50, 140))
            for sx in range(6):
                cv.disc(px + 10 + sx * 7, y + h * 0.14 + 15, 2, (255, 220, 60))
    cv.circle(x + w * 0.38, y + h * 0.78, 8, (232, 190, 150))         # handshake
    cv.circle(x + w * 0.62, y + h * 0.78, 8, (200, 150, 110))
    cv.thick_line(x + w * 0.30, y + h * 0.70, x + w * 0.70, y + h * 0.86, 7,
                  (232, 190, 150))
    cv.thick_line(x + w * 0.70, y + h * 0.70, x + w * 0.30, y + h * 0.86, 7,
                  (200, 150, 110))


def thumb_energy(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (60, 70, 90), (30, 34, 52))
    for i, px in enumerate((0.14, 0.50, 0.84)):
        cv.thick_line(x + w * px, y + h * 0.30, x + w * px, y + h * 0.92, 4, INK)
        cv.thick_line(x + w * (px - 0.08), y + h * 0.34, x + w * (px + 0.08),
                      y + h * 0.34, 3, INK)
    cv.thick_line(x + w * 0.06, y + h * 0.32, x + w * 0.94, y + h * 0.44, 1, GREY)
    cv.rect(x + w * 0.30, y + h * 0.55, w * 0.40, h * 0.37, (20, 22, 34))
    _windows(cv, x + w * 0.32, y + h * 0.58, w * 0.36, h * 0.30, 4, 2, False,
             (250, 210, 90))
    cv.poly([(x + w * 0.82, y + h * 0.10), (x + w * 0.72, y + h * 0.38),
             (x + w * 0.79, y + h * 0.38), (x + w * 0.70, y + h * 0.62),
             (x + w * 0.84, y + h * 0.34), (x + w * 0.77, y + h * 0.34)],
            (255, 220, 60))


def thumb_hospital(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (220, 232, 238), (240, 242, 244))
    cv.rect(x + w * 0.10, y + h * 0.30, w * 0.50, h * 0.60, (248, 248, 250))
    cv.rect(x + w * 0.10, y + h * 0.30, w * 0.50, 6, (200, 60, 60))
    cv.rect(x + w * 0.62, y + h * 0.14, 22, 22, WHITE)                # red cross
    cv.frame(x + w * 0.62, y + h * 0.14, 22, 22, RED, 2)
    cv.rect(x + w * 0.62 + 9, y + h * 0.14 + 3, 4, 16, RED)
    cv.rect(x + w * 0.62 + 3, y + h * 0.14 + 9, 16, 4, RED)
    _windows(cv, x + w * 0.14, y + h * 0.44, w * 0.42, h * 0.34, 3, 2, False,
             (140, 190, 220))
    cv.rect(x + w * 0.66, y + h * 0.62, w * 0.28, h * 0.28, (200, 210, 220))
    cv.thick_line(x + w * 0.66, y + h * 0.70, x + w * 0.72, y + h * 0.70, 2, RED)
    cv.thick_line(x + w * 0.72, y + h * 0.70, x + w * 0.76, y + h * 0.62, 2, RED)
    cv.thick_line(x + w * 0.76, y + h * 0.62, x + w * 0.80, y + h * 0.76, 2, RED)
    cv.thick_line(x + w * 0.80, y + h * 0.76, x + w * 0.86, y + h * 0.70, 2, RED)


def thumb_fire(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (240, 200, 140), (200, 110, 60))
    cv.rect(x + w * 0.10, y + h * 0.50, w * 0.55, h * 0.42, (90, 80, 74))
    cv.rect(x + w * 0.10, y + h * 0.50, w * 0.55, 6, (120, 110, 100))
    cv.rect(x + w * 0.58, y + h * 0.30, 8, h * 0.62, (90, 80, 74))     # chimney
    for sx, sy, sr in ((0.62, 0.22, 10), (0.66, 0.12, 12), (0.58, 0.06, 9)):
        cv.circle(x + w * sx, y + h * sy, sr, (120, 116, 112))
    cv.poly([(x + w * 0.16, y + h * 0.92), (x + w * 0.24, y + h * 0.52),
             (x + w * 0.32, y + h * 0.92)], (255, 90, 20))
    cv.poly([(x + w * 0.34, y + h * 0.92), (x + w * 0.42, y + h * 0.58),
             (x + w * 0.50, y + h * 0.92)], (255, 140, 30))
    cv.poly([(x + w * 0.50, y + h * 0.92), (x + w * 0.56, y + h * 0.66),
             (x + w * 0.62, y + h * 0.92)], (255, 210, 60))
    cv.rect(x + w * 0.72, y + h * 0.70, w * 0.24, 14, (200, 40, 40))   # truck
    cv.disc(x + w * 0.77, y + h * 0.86, 5, INK)
    cv.disc(x + w * 0.90, y + h * 0.86, 5, INK)


# ---------------------------------------------------------------- content
LEADS = [
    dict(num=1, loc="ANTALYA, TURKIYE", tag="CLIMATE", badge="CONFIRMED",
         head=["COP31 ends with no deal"], hsize=26,
         body=["EU and 130 nations reject a text with no mention",
               "of fossil fuels; first COP with no deal since 2000."],
         src="Reuters · AP · UNFCCC", scene=hero_cop31),
    dict(num=2, loc="KYIV REGION, UKRAINE", tag="WAR", badge="CONFIRMED",
         head=["Russia fires 186 drones", "at Ukraine"], hsize=24,
         body=["186 drones in the night, 161 downed; a block of",
               "flats hit in Dymer, 2 dead, 14 missing, 9 rescued."],
         src="Kyiv Post · Reuters", scene=hero_kyiv),
    dict(num=3, loc="MANAMA, BAHRAIN", tag="IRAN", badge="CLAIM",
         head=["Iran claims two US radars", "hit; Bahrain denies it"], hsize=24,
         body=["IRGC says it hit two US Patriot radars; Bahrain",
               "says a civilian site burned, 2 hurt; US denies."],
         src="CBS · Reuters · Fars", scene=hero_manama),
]

SMALL = [
    dict(num=4, loc="THE HAGUE · WORLD COURT", head=["ICJ: Myanmar committed", "genocide"],
         body="Rohingya welcome verdict. (Reuters)", scene=thumb_icj),
    dict(num=5, loc="HONG KONG · ELECTION", head=["Record turnout in", "committee polls"],
         body="98.79% voted; 856 for 723 (SCMP)", scene=thumb_hk),
    dict(num=6, loc="WELLINGTON, NZ · CRICKET", head=["India declare on a", "record 720/9"],
         body="Rahul 136, Pant 128, Gill 98. (ESPN)", scene=thumb_cricket),
    dict(num=7, loc="LAS VEGAS · FORMULA 1", head=["Verstappen wins the", "Las Vegas GP"],
         body="Beats Norris under the lights. (F1)", scene=thumb_f1),
    dict(num=8, loc="SAN ANTONIO · NBA", head=["Wembanyama scores 50", "as Spurs roll on"],
         body="50 pts, 19 reb, 5 blk; 114-91. (NBA)", scene=thumb_nba),
    dict(num=9, loc="WASHINGTON · POLITICS", head=["Democrats win biggest", "House majority since 1992"],
         body="Hubbard beats Foxx; 258 seats. (AP)", scene=thumb_house),
    dict(num=10, loc="LONDON · EUROPE", head=["UK and EU strike post-", "Brexit deals"],
         body="Trade and travel pacts agreed. (AP)", scene=thumb_ukeu),
    dict(num=11, loc="TEHRAN · ENERGY", head=["Iran begins rationing", "electricity"],
         body="Rolling cuts up to 2 hours. (Wires)", scene=thumb_energy),
    dict(num=12, loc="BRASILIA · HEALTH", head=["Bolsonaro in intensive", "care"],
         body="Bowel blockage, 71, stable. (Wires)", scene=thumb_hospital),
    dict(num=13, loc="CIKANDE, INDONESIA · FIRE", head=["Candy-factory fire in", "Cikande: 3 dead"],
         body="36 missing as search goes on. (Detik)", scene=thumb_fire),
]

ALSO = [
    (14, "Benghazi: Sea drones hit Russian warship at Benghazi. (Wires)"),
    (15, "Washington: FBI probes hack of its crime database. (AP)"),
    (16, "Gaza City: Israeli fire kills four in Gaza. (Gaza civil defence)"),
    (17, "Turin: Alcaraz wins first ATP Finals, beats Zverev. (ATP)"),
    (18, "Gulf of Finland: Sparta II towed home after drone strike. (Wires)"),
    (19, "Europe: Estonia to shut five Russia border crossings 1 Dec. (Reuters)"),
    (20, "Europe: Denmark expels a Russian attache over alleged plot. (Guardian)"),
    (21, "South Asia: Nepal PM Shah lands in Delhi; meets Modi Monday. (IANS)"),
    (22, "East Asia: Chinese bomber turns back 170 km from Manila. (AP)"),
    (23, "SE Asia: Philippines M5.9 quake, 898 km deep, off Palawan. (EMSC)"),
    (24, "East Asia: Japan poll: record 52% feel friendly to South Korea. (Ipsos)"),
    (25, "South Asia: India and China hold fresh military talks. (Wires)"),
    (26, "Africa: Somalia expels UAE ambassador, recalls its envoy. (Wires)"),
    (27, "Africa: Sudan: RSF accused of killing civilians in W. Kordofan. (Claim)"),
    (28, "Africa: Kenya discharges its last Ebola patient. (Wires)"),
    (29, "Africa: Drone strikes damage UN facility in Khartoum; 4 killed. (Wires)"),
    (30, "Oceania: Marles rejects US report on AUKUS subs. (ABC)"),
    (31, "Oceania: Melbourne, 70 years since the 1956 Olympics opened. (ABC)"),
    (32, "N. America: Trump seeks 'permanent' Israel deal; Doha talks. (Al Jazeera)"),
    (33, "SE Asia: EU and Indonesia sign trade deal after ten years. (DW)"),
    (34, "Africa: Sudan army retakes ~30 towns in Kordofan. (FT)"),
    (35, "South Asia: Bangladesh: 30 Awami League homes set on fire. (Local)"),
    (36, "Middle East: Lebanon: Aoun demands Israel withdrawal. (Al Jazeera)"),
    (37, "World: Scientists sequence whale genome from breath by drone. (Wires)"),
    (38, "Middle East: Saudi Arabia and Yemen's Houthis exchange fire. (Wires)"),
]

REGIONS = [("EUROPE", 5, (60, 90, 150)), ("MIDDLE EAST", 5, (150, 60, 60)),
           ("NORTH AMERICA", 5, (40, 110, 110)), ("SOUTH AMERICA", 1, (110, 140, 50)),
           ("EAST ASIA", 3, (180, 80, 40)), ("SOUTH ASIA", 4, (150, 110, 30)),
           ("SOUTHEAST ASIA", 3, (60, 130, 80)), ("AFRICA", 6, (170, 120, 60)),
           ("OCEANIA", 2, (70, 110, 170)), ("WORLD", 4, (100, 100, 100))]

NUMBERS = [("186", "DRONES FIRED"), ("161", "DRONES DOWNED"),
           ("258", "HOUSE SEATS · DEM"), ("$120bn", "ADAPTATION TARGET"),
           ("720/9", "INDIA TEST TOTAL"), ("98.79%", "HK TURNOUT")]

DATE_CHECK = [
    "400-drone barrage (19-20 Nov)", "148-drone night, Kryvyi Rih (20-21 Nov)",
    "'El Chapo Isidro' captured (21 Nov)", "Bayelsa boat capsizes, 24 dead (21 Nov)",
    "Gaza aid-van strike (21 Nov)", "Nvidia SEC probe first reported (20 Nov)",
    "Saudi strikes on Hodeidah (20-21 Nov)", "Peru earthquake (20 Nov)",
    "Copa Sudamericana final (21 Nov)", "BepiColombo enters Mercury orbit (21 Nov)",
    "Russian missiles entered Poland (20 Nov)", "Rugby: England beat NZ 37-12 (21 Nov)",
    "Football: Arsenal 2-2 Newcastle (21 Nov)",
]

# pin positions (fraction of map inner box) for stories 1-13
PINS = {1: (0.56, 0.30), 2: (0.565, 0.20), 3: (0.615, 0.40), 4: (0.505, 0.18),
        5: (0.81, 0.40), 6: (0.93, 0.78), 7: (0.13, 0.32), 8: (0.17, 0.42),
        9: (0.23, 0.30), 10: (0.485, 0.15), 11: (0.635, 0.34),
        12: (0.30, 0.62), 13: (0.775, 0.56)}
PIN_OFF = {1: (10, -12), 2: (12, -14), 3: (12, 8), 4: (-16, -12), 5: (10, -12),
           6: (10, 6), 7: (-16, -8), 8: (-16, 10), 9: (10, -14), 10: (-16, 8),
           11: (14, -10), 12: (10, 10), 13: (10, -12)}


def draw_map(cv, x, y, w, h):
    cv.rect(x, y, w, h, (228, 232, 226))
    cv.frame(x, y, w, h, RULE, 1)
    draw_text(cv, x + 8, y + 3, "WHERE IT HAPPENED", 10, INK)
    mx, my, mw, mh = x + 6, y + 14, w - 12, h - 18
    land = (196, 188, 164)
    conts = [
        [(0.02, 0.28), (0.09, 0.12), (0.19, 0.08), (0.26, 0.16), (0.22, 0.30),
         (0.17, 0.42), (0.10, 0.40), (0.03, 0.32)],
        [(0.28, 0.06), (0.31, 0.04), (0.32, 0.09), (0.29, 0.11)],
        [(0.24, 0.50), (0.30, 0.45), (0.34, 0.54), (0.32, 0.68), (0.28, 0.82),
         (0.25, 0.68), (0.23, 0.56)],
        [(0.47, 0.12), (0.53, 0.07), (0.58, 0.12), (0.56, 0.20), (0.51, 0.22),
         (0.47, 0.17)],
        [(0.48, 0.34), (0.56, 0.31), (0.60, 0.38), (0.58, 0.50), (0.54, 0.62),
         (0.50, 0.52), (0.47, 0.42)],
        [(0.58, 0.08), (0.72, 0.04), (0.86, 0.08), (0.92, 0.18), (0.88, 0.28),
         (0.80, 0.32), (0.70, 0.30), (0.62, 0.22), (0.58, 0.14)],
        [(0.82, 0.64), (0.90, 0.61), (0.94, 0.68), (0.90, 0.75), (0.84, 0.72)],
    ]
    for pts in conts:
        # vertical stretch so the schematic map reads less flat
        cv.poly([(mx + px * mw,
                  my + (0.5 + (py - 0.5) * 1.35) * mh) for px, py in pts], land)
    for ix, iy in ((0.775, 0.44), (0.805, 0.48), (0.83, 0.44)):
        cv.ellipse(mx + ix * mw, my + (0.5 + (iy - 0.5) * 1.35) * mh, 4, 3, land)
    for n, (fx, fy) in PINS.items():
        fy2 = 0.5 + (fy - 0.5) * 1.35
        px, py = mx + fx * mw, my + fy2 * mh
        ox, oy = PIN_OFF.get(n, (0, 0))
        cv.disc(px, py, 4, RED)
        cv.ring(px, py, 4, 1, WHITE)
        lx, ly = px + ox, py + oy
        cv.thick_line(px, py, lx, ly, 1, RED)
        draw_text(cv, lx - (6 if ox < 0 else 0), ly - 5, str(n), 9, RED)


def build():
    cv = Canvas()
    # ---- header bar
    cv.rect(0, 0, W, 20, NAVY)
    draw_text(cv, 14, 4, "THE WORLD IN ONE DAY", 12, WHITE)
    draw_text(cv, 1010, 4, "38 STORIES · 10 REGIONS · EVERY ONE DATED SUNDAY 22 NOVEMBER 2026",
              11, WHITE, align="right")
    # ---- titles
    draw_text(cv, 512, 21, "Sunday 22 November 2026", 56, INK, align="center")
    draw_text(cv, 512, 94, "No Deal in Antalya, 186 Drones Over Kyiv, and Hong Kong's 98.79% Vote",
              28, INK, align="center")
    draw_text(cv, 512, 136,
              "COP31 ends with no deal · 186 drones over Ukraine in the night · Iran's radar claim meets Bahrain's denial",
              13, RED, italic=True, align="center")
    # ---- numbers strip
    y = 151
    bw, gap = 160, 7
    for i, (val, lab) in enumerate(NUMBERS):
        bx = 18 + i * (bw + gap)
        cv.rect(bx, y, bw, 44, CREAM)
        cv.frame(bx, y, bw, 44, RULE, 1)
        cv.rect(bx, y, bw, 3, RED)
        draw_text(cv, bx + bw / 2, y + 2, val, 30, RED, align="center")
        draw_text(cv, bx + bw / 2, y + 35, lab, 8, GREY, align="center")
    # ---- region tabs
    y = 197
    tw = 96
    for i, (name, cnt, col) in enumerate(REGIONS):
        tx = 18 + i * (tw + 2)
        cv.rect(tx, y, tw, 15, col)
        draw_text(cv, tx + tw / 2, y + 3, "%s %d" % (name, cnt), 9, WHITE, align="center")
    # ---- timeline
    y = 214
    tl = "THE DAY IN UTC  01:00 HK polls open · 03:00 COP31 objections close · 05:11 Hamas seeks talks · 05:30 Las Vegas GP ends · 06:00 COP31 approval due · 07:30 Approval slips again · 09:45 "
    draw_text(cv, 18, y, tl, 10, GREY)
    px = 18 + text_width(tl, 10)
    draw_text(cv, px, y, "PRESS TIME", 10, RED)
    cv.hline(18, y + 14, 988, RULE, 1)
    # ---- leads
    y = 230
    colw, colgap = 324, 8
    for i, L in enumerate(LEADS):
        lx = 18 + i * (colw + colgap)
        L["scene"](cv, lx, y, colw, 153)
        my = y + 156
        draw_text(cv, lx, my, "%d · %s — %s" % (L["num"], L["loc"], L["tag"]), 11, INK)
        bc = (40, 120, 60) if L["badge"] == "CONFIRMED" else (200, 120, 20)
        cv.rect(lx + colw - 66, my - 1, 66, 13, bc)
        draw_text(cv, lx + colw - 33, my + 1, L["badge"], 8, WHITE, align="center")
        hy = my + 15
        for j, hl in enumerate(L["head"]):
            draw_text(cv, lx, hy + j * 23, hl, L["hsize"], INK)
        by = hy + 46
        for j, bl in enumerate(L["body"]):
            draw_text(cv, lx, by + j * 14, bl, 12, INK)
        draw_text(cv, lx, by + 28, L["src"], 10, GREY)
    # ---- small stories
    y = 491
    sw, sgap = 194, 7
    for row in range(2):
        for col in range(5):
            s = SMALL[row * 5 + col]
            sx = 13 + col * (sw + sgap)
            sy = y + row * 144
            s["scene"](cv, sx, sy, sw, 85)
            ly = sy + 87
            draw_text(cv, sx, ly, "%d " % s["num"], 10, RED)
            draw_text(cv, sx + text_width("%d " % s["num"], 10), ly, s["loc"], 9, GREY)
            hy = ly + 11
            for j, hl in enumerate(s["head"]):
                draw_text(cv, sx, hy + j * 16, hl, 13, INK)
            draw_text(cv, sx, hy + 33, s["body"], 10, INK)
    # ---- ALSO list
    y = 781
    draw_text(cv, 18, y, "ALSO ON SUNDAY 22 NOVEMBER — 25 MORE STORIES", 12, INK)
    cv.hline(18, y + 15, 988, RULE, 1)
    ay = y + 17
    for k, (n, txt) in enumerate(ALSO):
        col = k // 13
        r = k % 13
        ax = 18 + col * 500
        ry = ay + r * 9.8
        draw_text(cv, ax, ry, "%d. " % n, 9.5, RED)
        draw_text(cv, ax + text_width("%d. " % n, 9.5), ry, txt, 9.5, INK)
    # ---- map + date check
    y = 930
    draw_map(cv, 18, y, 600, 70)
    dx = 626
    cv.rect(dx, y, 380, 70, (252, 246, 238))
    cv.frame(dx, y, 380, 70, RED, 2)
    draw_text(cv, dx + 8, y + 3, "DATE CHECK — NOT 22 NOVEMBER", 10, RED)
    for k, item in enumerate(DATE_CHECK):
        col = k // 7
        r = k % 7
        ix = dx + 10 + col * 190
        iy = y + 12 + r * 8.0
        draw_text(cv, ix, iy, "· " + item, 8, INK)
    # ---- footer
    y = 1000
    draw_text(cv, 18, y, "Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, UNFCCC, Kyiv Post, SCMP, ESPNcricinfo, Detiknews",
              9, GREY)
    draw_text(cv, 18, y + 11, "CONFIRMED = verified  ·  CLAIM = reported claim, not verified  ·  Scenes are drawn illustrations  ·  Wires read to press time 09:45 UTC",
              9, GREY)
    print("layout end y:", y + 22)
    return cv


def main():
    out = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out, exist_ok=True)
    cv = build()
    data = png_bytes(cv)
    with open(os.path.join(out, "entry.png"), "wb") as f:
        f.write(data)
    print("wrote", len(data), "bytes")


if __name__ == "__main__":
    main()
