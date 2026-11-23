#!/usr/bin/env python3
"""makefun news-image-20261122 entry v8 — "Sunday 22 November 2026".

Draws a one-page newspaper front page summing up the world's news of
Sunday 22 November 2026, entirely in pure Python (stdlib only): a
hand-built serif font (light contrast, open counters, 4x supersampled),
hand-drawn illustrations, a dotted world map, and a hand-written PNG
encoder. Deterministic: two runs write byte-identical files.

Run:  mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
"""
import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 232)
INK = (26, 26, 24)
NAVY = (26, 43, 74)
NAVY2 = (16, 30, 56)
RED = (178, 34, 34)
RED_DK = (140, 22, 22)
GOLD = (201, 162, 39)
CREAM = (250, 246, 236)
GREY = (90, 88, 80)
LGREY = (120, 118, 108)
RULE = (180, 172, 150)
MAPDOT = (34, 84, 52)
MAPDOT2 = (26, 60, 110)
WHITE = (255, 255, 255)
BLACK = (10, 10, 10)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w=W, h=H, bg=PAPER):
        self.w = w
        self.h = h
        self.pix = bytearray(w * h * 3)
        self.fill_rect(0, 0, w, h, bg)

    def _clip(self, x0, y0, x1, y1):
        x0 = max(0, int(x0)); y0 = max(0, int(y0))
        x1 = min(self.w, int(x1)); y1 = min(self.h, int(y1))
        return x0, y0, x1, y1

    def fill_rect(self, x, y, w, h, c):
        x0, y0, x1, y1 = self._clip(x, y, x + w, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            o = (yy * self.w + x0) * 3
            self.pix[o:o + (x1 - x0) * 3] = row

    def hline(self, x, y, w, c):
        self.fill_rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill_rect(x, y, 1, h, c)

    def rect_outline(self, x, y, w, h, c, t=1):
        self.fill_rect(x, y, w, t, c)
        self.fill_rect(x, y + h - t, w, t, c)
        self.fill_rect(x, y, t, h, c)
        self.fill_rect(x + w - t, y, t, h, c)

    def vgrad(self, x, y, w, h, c1, c2):
        """Vertical linear gradient, top c1 -> bottom c2."""
        if h <= 0:
            return
        for i in range(h):
            t = i / max(1, h - 1)
            c = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
            self.fill_rect(x, y + i, w, 1, c)

    def hgrad(self, x, y, w, h, c1, c2):
        if w <= 0:
            return
        for i in range(w):
            t = i / max(1, w - 1)
            c = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
            self.fill_rect(x + i, y, 1, h, c)

    def set_px(self, x, y, c):
        x = int(x); y = int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            o = (y * self.w + x) * 3
            self.pix[o:o + 3] = bytes(c)

    def blend_px(self, x, y, c, a):
        """Blend colour c over pixel with alpha a (0..255)."""
        x = int(x); y = int(y)
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        if a >= 255:
            self.set_px(x, y, c)
            return
        o = (y * self.w + x) * 3
        inv = 255 - a
        self.pix[o] = (c[0] * a + self.pix[o] * inv) // 255
        self.pix[o + 1] = (c[1] * a + self.pix[o + 1] * inv) // 255
        self.pix[o + 2] = (c[2] * a + self.pix[o + 2] * inv) // 255

    def fill_poly(self, pts, c):
        """Scanline fill of a polygon (even-odd rule, handles holes)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        ymin = max(0, int(math.floor(min(ys))))
        ymax = min(self.h - 1, int(math.ceil(max(ys))))
        n = len(pts)
        for yy in range(ymin, ymax + 1):
            yc = yy + 0.5
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    t = (yc - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                x0 = max(0, int(math.ceil(xs[k])))
                x1 = min(self.w - 1, int(math.floor(xs[k + 1])))
                if x1 >= x0:
                    o = (yy * self.w + x0) * 3
                    self.pix[o:o + (x1 - x0 + 1) * 3] = bytes(c) * (x1 - x0 + 1)

    def circle(self, cx, cy, r, c):
        if r <= 0:
            return
        self.ellipse(cx, cy, r, r, c)

    def ellipse(self, cx, cy, rx, ry, c):
        if rx <= 0 or ry <= 0:
            return
        pts = []
        n = max(16, int(2 * math.pi * max(rx, ry) / 2.5))
        for i in range(n):
            a = 2 * math.pi * i / n
            pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
        self.fill_poly(pts, c)

    def ring(self, cx, cy, r_out, r_in, c):
        """Filled ring (outer circle minus inner circle)."""
        pts = []
        n = max(24, int(2 * math.pi * r_out / 2.5))
        for i in range(n):
            a = 2 * math.pi * i / n
            pts.append((cx + r_out * math.cos(a), cy + r_out * math.sin(a)))
        m = max(16, int(2 * math.pi * r_in / 2.5))
        for i in range(m):
            a = 2 * math.pi * i / m
            pts.append((cx + r_in * math.cos(a), cy + r_in * math.sin(a)))
        self.fill_poly(pts, c)

    def arc_ring(self, cx, cy, r_out, r_in, a0deg, a1deg, c):
        """Ring sector from a0 to a1 degrees (y-down angles)."""
        pts = []
        n = 28
        for i in range(n + 1):
            a = math.radians(a0deg + (a1deg - a0deg) * i / n)
            pts.append((cx + r_out * math.cos(a), cy + r_out * math.sin(a)))
        for i in range(n + 1):
            a = math.radians(a1deg - (a1deg - a0deg) * i / n)
            pts.append((cx + r_in * math.cos(a), cy + r_in * math.sin(a)))
        self.fill_poly(pts, c)

    def thick_line(self, x0, y0, x1, y1, w, c):
        dx, dy = x1 - x0, y1 - y0
        L = (dx * dx + dy * dy) ** 0.5 or 1.0
        nx, ny = -dy / L * w / 2, dx / L * w / 2
        self.fill_poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                        (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)

    def blit_alpha(self, x, y, w, h, alpha, c):
        """Blit a greyscale alpha tile in colour c at (x, y)."""
        for yy in range(h):
            cy = y + yy
            if cy < 0 or cy >= self.h:
                continue
            row = alpha[yy * w:(yy + 1) * w]
            for xx in range(w):
                a = row[xx]
                if a:
                    self.blend_px(x + xx, cy, c, a)


# ---------------------------------------------------------------- PNG writer
def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.pix[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ================================================================ FONT
# Hand-built serif, light contrast (vertical : horizontal ~1.47:1),
# wide open counters, bracketed slab serifs, 4x supersampling.
# Unit space: cap height 28, baseline y=28, x-height top y=8,
# descender bottom y=35. All glyphs are polygons in this space.
# ================================================================
VW = 5.0   # vertical stem width (units)
HW = 3.4   # horizontal stroke width (units) -> ratio 1.47:1


def R(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def arc_pts(cx, cy, rx, ry, a0, a1, n=14):
    """Points along an ellipse arc, angles in degrees, y-down.
    Interpolates a0 -> a1 directly (decreasing when a1 < a0)."""
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def ell_pts(cx, cy, rx, ry, n=28):
    return arc_pts(cx, cy, rx, ry, 0, 360, n)


def stem(x, y0, y1, w=VW, serif=True):
    """Vertical stem with small bracketed slab serifs at both ends."""
    polys = [R(x - w / 2, y0, x + w / 2, y1)]
    if serif:
        polys.append(R(x - w / 2 - 1.4, y0, x + w / 2 + 1.4, y0 + 1.7))
        polys.append(R(x - w / 2 - 1.4, y1 - 1.7, x + w / 2 + 1.4, y1))
    return polys


def bar(x0, x1, y, h=HW):
    return [R(x0, y, x1, y + h)]


def diag(x0, y0, x1, y1, w=VW):
    dx, dy = x1 - x0, y1 - y0
    L = (dx * dx + dy * dy) ** 0.5 or 1.0
    nx, ny = -dy / L * w / 2, dx / L * w / 2
    return [[(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
             (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]]


def stroke(pts, wv=VW, wh=HW, closed=False):
    """Thick centreline stroke -> one filled polygon.
    Width varies smoothly with tangent angle: vertical tangents get wv,
    horizontal tangents get wh (light Didone-like contrast, ~1.47:1).
    Open strokes get round caps."""
    n = len(pts)
    left = []
    right = []
    for i in range(n):
        if closed:
            x0, y0 = pts[i - 1]
            x1, y1 = pts[(i + 1) % n]
        else:
            x0, y0 = pts[i - 1] if i > 0 else pts[i]
            x1, y1 = pts[i + 1] if i < n - 1 else pts[i]
        dx, dy = x1 - x0, y1 - y0
        L = (dx * dx + dy * dy) ** 0.5
        if L < 1e-6:
            dx, dy, L = 1.0, 0.0, 1.0
        s = abs(dy) / L
        hw = (wh + (wv - wh) * s) / 2.0
        nx, ny = -dy / L, dx / L
        x, y = pts[i]
        left.append((x + nx * hw, y + ny * hw))
        right.append((x - nx * hw, y - ny * hw))
    poly = left[:]
    if not closed:
        # round cap at end: semicircle from normal angle, through tangent
        x, y = pts[-1]
        x0, y0 = pts[-2]
        dx, dy = x - x0, y - y0
        L = (dx * dx + dy * dy) ** 0.5 or 1.0
        tx, ty = dx / L, dy / L
        hw = (wh + (wv - wh) * abs(ty)) / 2.0
        a_n = math.atan2(tx, -ty)  # angle of normal (-ty, tx)
        for k in range(1, 9):
            a = a_n - k * math.pi / 8
            poly.append((x + hw * math.cos(a), y + hw * math.sin(a)))
        poly += right[::-1]
        # round cap at start: semicircle through -tangent
        x, y = pts[0]
        x1, y1 = pts[1]
        dx, dy = x1 - x, y1 - y
        L = (dx * dx + dy * dy) ** 0.5 or 1.0
        tx, ty = dx / L, dy / L
        hw = (wh + (wv - wh) * abs(ty)) / 2.0
        a_n = math.atan2(tx, -ty)
        for k in range(1, 9):
            a = a_n + math.pi + k * math.pi / 8
            poly.append((x + hw * math.cos(a), y + hw * math.sin(a)))
    else:
        poly += right[::-1]
    return [poly]


def ring(cx, cy, rx, ry, wv=VW, wh=HW):
    return stroke(ell_pts(cx, cy, rx, ry), wv, wh, closed=True)


def arc(cx, cy, rx, ry, a0, a1, wv=VW, wh=HW, n=14):
    return stroke(arc_pts(cx, cy, rx, ry, a0, a1, n), wv, wh)


def circ(cx, cy, r):
    return [ell_pts(cx, cy, r, r, 16)]


# ------------------------------------------------------------ glyph table
# Each entry: (advance_width, [polygons...])
def _g():
    G = {}
    # ---- uppercase ----
    G["A"] = (24, diag(4, 28, 12, 0, 5) + diag(20, 28, 12, 0, 5)
              + bar(7.5, 16.5, 17.5))
    G["B"] = (20, stem(4, 0, 28) + arc(11, 8.5, 7, 7.5, -90, 90)
              + arc(11, 20, 7.5, 7.5, -90, 90)
              + bar(4, 11.5, 0.5) + bar(4, 12, 13) + bar(4, 11.5, 24.6))
    G["C"] = (22, arc(11, 14, 10, 13.5, 55, 305, n=20))
    G["D"] = (22, stem(4, 0, 28) + arc(6, 14, 13, 13.5, -90, 90, n=18)
              + bar(4, 12, 0) + bar(4, 12, 24.6))
    G["E"] = (19, stem(4, 0, 28) + bar(4, 18, 0) + bar(4, 15, 12.3)
              + bar(4, 18, 24.6))
    G["F"] = (18, stem(4, 0, 28) + bar(4, 17, 0) + bar(4, 14.5, 12.3))
    G["G"] = (23, arc(11.5, 14, 10, 13.5, 55, 300, n=20)
              + bar(14, 21.5, 14) + [R(18, 14, 21.4, 23)])
    G["H"] = (22, stem(4, 0, 28) + stem(18, 0, 28) + bar(4, 18, 12.3))
    G["I"] = (10, stem(5, 0, 28))
    G["J"] = (18, stem(14, 0, 20) + arc(9, 19, 6.5, 7.5, 0, 180)
              + bar(9, 18, 0))
    G["K"] = (21, stem(4, 0, 28) + diag(7, 14, 19, 0, 4.5)
              + diag(7, 15, 19, 28, 4.5))
    G["L"] = (18, stem(4, 0, 28) + bar(4, 17, 24.6))
    G["M"] = (26, stem(3.5, 0, 28) + stem(22.5, 0, 28)
              + diag(3.5, 0, 13, 21, 4.5) + diag(22.5, 0, 13, 21, 4.5))
    G["N"] = (22, stem(3.5, 0, 28) + stem(18.5, 0, 28)
              + diag(3.5, 0, 18.5, 28, 4.5))
    G["O"] = (24, ring(12, 14, 10.5, 13.5))
    G["P"] = (19, stem(4, 0, 28) + arc(10.5, 8, 7.5, 7.5, -90, 90)
              + bar(4, 11, 12.3))
    G["Q"] = (24, ring(12, 14, 10.5, 13.5) + diag(16, 20, 22, 28, 4))
    G["R"] = (20, stem(4, 0, 28) + arc(10.5, 8, 7.5, 7.5, -90, 90)
              + bar(4, 11, 12.3) + diag(10, 15, 19, 28, 4.5))
    s_top = arc_pts(10.5, 9, 8, 6.5, 325, 155, 12)
    s_bot = arc_pts(10.5, 20, 8.5, 6.5, -25, 145, 12)
    G["S"] = (21, stroke(s_top + s_bot))
    G["T"] = (20, bar(1, 19, 0) + stem(10, 0, 28))
    G["U"] = (22, stem(4, 0, 20) + stem(18, 0, 20)
              + arc(11, 20, 7, 7, 0, 180))
    G["V"] = (22, diag(2, 0, 11, 28, 5) + diag(20, 0, 11, 28, 5))
    G["W"] = (30, diag(2, 0, 8, 28, 4.5) + diag(15, 0, 8, 28, 4.5)
              + diag(15, 0, 22, 28, 4.5) + diag(28, 0, 22, 28, 4.5))
    G["X"] = (21, diag(2, 0, 19, 28, 4.5) + diag(19, 0, 2, 28, 4.5))
    G["Y"] = (21, diag(2, 0, 10.5, 14, 4.5) + diag(19, 0, 10.5, 14, 4.5)
              + stem(10.5, 14, 28))
    G["Z"] = (20, bar(2, 18, 0) + bar(2, 18, 24.6)
              + diag(18, 0, 2, 28, 4.5))
    # ---- lowercase ----
    G["a"] = (18, ring(9, 18, 7.5, 9.5) + stem(16.5, 8, 28)
              + arc(11, 11, 6, 5, 180, 360))
    G["b"] = (17, stem(3.5, 0, 28) + ring(10, 18, 6.5, 9.5))
    G["c"] = (16, arc(8, 18, 7.5, 9.5, 55, 305, n=18))
    G["d"] = (17, ring(8, 18, 6.5, 9.5) + stem(15.5, 0, 28))
    G["e"] = (16, arc(8, 18, 7.5, 9.5, -30, 210, n=18)
              + bar(1, 15, 16.5, 3.2))
    G["f"] = (13, stem(7, 0, 28) + arc(7, 4.5, 4.5, 4.5, 180, 360)
              + bar(2, 12, 12, 3.2))
    G["g"] = (17, ring(8, 18, 7, 9.5) + stem(15, 18, 31)
              + arc(9.5, 31, 5.5, 4, 0, 180))
    G["h"] = (17, stem(3.5, 0, 28) + arc(10, 17.5, 6.5, 9, 180, 360)
              + stem(16.5, 17.5, 28))
    G["i"] = (8, circ(4, 4.5, 2.6) + stem(4, 12, 28))
    G["j"] = (9, circ(5, 3, 2.6) + stem(5, 8, 28)
              + arc(5, 28, 4.5, 5, 0, 180))
    G["k"] = (16, stem(3.5, 0, 28) + diag(7, 19, 15, 8, 4)
              + diag(6.5, 20, 15, 28, 4))
    G["l"] = (8, stem(4, 0, 28))
    G["m"] = (24, stem(3.5, 8, 28) + arc(8.25, 17.5, 4.75, 9, 180, 360)
              + stem(13, 17.5, 28) + arc(17.75, 17.5, 4.75, 9, 180, 360)
              + stem(22.5, 17.5, 28))
    G["n"] = (16, stem(3.5, 8, 28) + arc(10, 17.5, 6.5, 9, 180, 360)
              + stem(16.5, 17.5, 28))
    G["o"] = (16, ring(8, 18, 7, 9.5))
    G["p"] = (17, stem(3.5, 8, 35) + ring(10, 18, 6.5, 9.5))
    G["q"] = (17, ring(8, 18, 6.5, 9.5) + stem(15.5, 8, 35))
    G["r"] = (13, stem(3.5, 8, 28) + arc(8.5, 13.5, 4.5, 5, 180, 360))
    s2_top = arc_pts(7.5, 13.5, 6.5, 5, 325, 155, 12)
    s2_bot = arc_pts(7.5, 22.5, 7, 5.5, -25, 145, 12)
    G["s"] = (15, stroke(s2_top + s2_bot))
    G["t"] = (12, stem(6, 3, 28) + bar(2, 11, 12, 3.2)
              + arc(6, 28, 4, 3, 0, 90))
    G["u"] = (16, stem(3.5, 8, 22) + stem(12.5, 8, 22)
              + arc(8, 22, 4.5, 5.5, 0, 180))
    G["v"] = (15, diag(2, 8, 7.5, 28, 4.5) + diag(13, 8, 7.5, 28, 4.5))
    G["w"] = (22, diag(2, 8, 6, 28, 4) + diag(11, 8, 6, 28, 4)
              + diag(11, 8, 16, 28, 4) + diag(20, 8, 16, 28, 4))
    G["x"] = (15, diag(2, 8, 13, 28, 4) + diag(13, 8, 2, 28, 4))
    G["y"] = (15, diag(2, 8, 7.5, 20, 4.5) + diag(13, 8, 7.5, 20, 4.5)
              + stem(7.5, 20, 35))
    G["z"] = (14, bar(2, 12, 8, 3.2) + bar(2, 12, 24.8, 3.2)
              + diag(12, 8, 2, 28, 4))
    # ---- digits ----
    G["0"] = (18, ring(9, 14, 8, 13.5))
    G["1"] = (12, diag(2, 7, 7, 1, 4) + stem(7, 1, 28)
              + bar(3, 11, 24.6))
    G["2"] = (18, arc(9, 9, 7.5, 7.5, 180, 360)
              + diag(16.5, 9, 2, 28, 4.5) + bar(2, 16, 24.6))
    G["3"] = (18, arc(9, 8, 7, 7, -90, 90) + arc(9, 20, 7.5, 7.5, -90, 90)
              + bar(3, 11, 0.5) + bar(3, 12, 12.5, 3.2))
    G["4"] = (18, diag(13, 0, 3, 20, 4.5) + bar(2, 16, 17)
              + stem(13, 0, 28))
    G["5"] = (18, bar(2, 16, 0) + stem(4.5, 0, 14)
              + arc(9, 20, 7.5, 7.5, -90, 90) + bar(4, 12, 12.5, 3.2))
    G["6"] = (18, ring(9, 19, 7.5, 8) + arc(9, 10, 6, 6.5, 300, 90))
    G["7"] = (18, bar(2, 16, 0) + diag(15, 0, 7, 28, 4.5))
    G["8"] = (18, ring(9, 9, 6.5, 7.5) + ring(9, 20, 7.5, 8))
    G["9"] = (18, ring(9, 9, 7.5, 8) + arc(9, 19, 6.5, 6.5, 270, 90))
    # ---- punctuation ----
    G["."] = (9, circ(4, 26, 2.4))
    G[","] = (9, circ(4, 25, 2.4) + diag(6, 26, 3, 31, 3))
    G[":"] = (9, circ(4, 10, 2.4) + circ(4, 24, 2.4))
    G[";"] = (9, circ(4, 10, 2.4) + circ(4, 24, 2.4)
              + diag(6, 25, 3, 30, 3))
    G["'"] = (8, diag(7, 0, 4, 8, 3.2))
    G['"'] = (14, diag(5, 0, 2.5, 8, 3) + diag(11, 0, 8.5, 8, 3))
    G["!"] = (10, stem(4.5, 0, 20, w=4.5) + circ(4.5, 25, 2.6))
    G["?"] = (16, arc(7, 9, 6.5, 6.5, 200, 340)
              + diag(12.5, 12.5, 8, 18, 4) + circ(7.5, 25, 2.6))
    G["%"] = (20, ring(5, 7, 3.5, 3.5, wv=3.5, wh=2.6)
              + ring(15, 21, 3.5, 3.5, wv=3.5, wh=2.6)
              + diag(17, 2, 3, 26, 3.2))
    G["$"] = (18, stroke(arc_pts(9, 9, 7, 6, 325, 155, 12)
                         + arc_pts(9, 19, 7.5, 6, -25, 145, 12))
              + stem(9, 0, 28, w=3.4, serif=False))
    G["/"] = (14, diag(14, 0, 4, 28, 3.4))
    G["("] = (12, arc(13, 14, 6, 13, 60, 300, n=18))
    G[")"] = (12, arc(-1, 14, 6, 13, 240, 120, n=18))
    G["-"] = (13, bar(1, 12, 13, 3.2))
    G["–"] = (17, bar(1, 16, 13, 3.2))
    G["—"] = (21, bar(0, 20, 13, 3.2))
    G["·"] = (10, circ(5, 12, 2.4))
    G["&"] = (20, ring(8, 9, 5.5, 6) + diag(12.5, 14, 3, 28, 4)
              + arc(8, 21, 5.5, 6, 0, 180))
    G["+"] = (16, bar(2, 14, 12.3, 3.2) + stem(8, 6, 22, w=3.4,
                                               serif=False))
    G["="] = (16, bar(2, 14, 11, 3.2) + bar(2, 14, 18, 3.2))
    G["*"] = (16, diag(8, 1, 8, 15, 3) + diag(2, 5, 14, 11, 3)
              + diag(14, 5, 2, 11, 3))
    G["ü"] = (16, stem(3.5, 8, 22) + stem(12.5, 8, 22)
              + arc(8, 22, 4.5, 5.5, 0, 180)
              + circ(4.5, 4, 2.2) + circ(11.5, 4, 2.2))
    G["Ü"] = (22, stem(4, 0, 20) + stem(18, 0, 20)
              + arc(11, 20, 7, 7, 0, 180)
              + circ(7, -3.5, 2.4) + circ(15, -3.5, 2.4))
    G[" "] = (8, [])
    G["’"] = G["'"]
    G["“"] = G['"']
    G["”"] = G['"']
    G["~"] = (16, arc(8, 16, 5, 3.5, 180, 360))
    return G


GLYPHS = _g()
SS = 4  # supersampling factor


class Font:
    def __init__(self):
        self.cache = {}

    def _tile(self, ch, size, italic):
        key = (ch, size, italic)
        if key in self.cache:
            return self.cache[key]
        adv, polys = GLYPHS.get(ch, GLYPHS["?"])
        s = size / 28.0
        # shear for italic: top leans right
        sp = []
        for poly in polys:
            if italic:
                sp.append([(x + 0.14 * (28 - y), y) for (x, y) in poly])
            else:
                sp.append(poly)
        if not sp:
            tile = (adv * s, 0, 0, 0, 0, bytes())
            self.cache[key] = tile
            return tile
        minx = min(p[0] for poly in sp for p in poly)
        maxx = max(p[0] for poly in sp for p in poly)
        miny = min(p[1] for poly in sp for p in poly)
        maxy = max(p[1] for poly in sp for p in poly)
        # tile in display px, with 1px pad
        tx0 = math.floor(minx * s) - 1
        tx1 = math.ceil(maxx * s) + 1
        ty0 = math.floor(miny * s) - 1
        ty1 = math.ceil(maxy * s) + 1
        tw, th = tx1 - tx0, ty1 - ty0
        wss, hss = tw * SS, th * SS
        buf = bytearray(wss * hss)
        for poly in sp:
            pts = [((x * s - tx0) * SS, (y * s - ty0) * SS) for (x, y) in poly]
            self._fill_ss(buf, wss, hss, pts)
        # downsample 4x4 -> alpha
        alpha = bytearray(tw * th)
        for oy in range(th):
            for ox in range(tw):
                tot = 0
                for dy in range(SS):
                    row = (oy * SS + dy) * wss + ox * SS
                    tot += sum(buf[row:row + SS])
                alpha[oy * tw + ox] = tot * 255 // (SS * SS)
        # tile origin relative to baseline: baseline is y=28 units
        # tile top (in px) = ty0; baseline px = 28*s -> dy = ty0 - 28*s
        tile = (adv * s, tw, th, tx0, ty0 - 28 * s, bytes(alpha))
        self.cache[key] = tile
        return tile

    @staticmethod
    def _fill_ss(buf, wss, hss, poly):
        if len(poly) < 3:
            return
        ys = [p[1] for p in poly]
        ymin = max(0, int(math.floor(min(ys))))
        ymax = min(hss - 1, int(math.ceil(max(ys))))
        n = len(poly)
        one = b"\x01"
        for yy in range(ymin, ymax + 1):
            yc = yy + 0.5
            xs = []
            for i in range(n):
                x0, y0 = poly[i]
                x1, y1 = poly[(i + 1) % n]
                if (y0 <= yc < y1) or (y1 <= yc < y0):
                    t = (yc - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                x0 = max(0, int(math.ceil(xs[k])))
                x1 = min(wss - 1, int(math.floor(xs[k + 1])))
                if x1 >= x0:
                    buf[yy * wss + x0:yy * wss + x1 + 1] = one * (x1 - x0 + 1)

    def width(self, text, size, italic=False, tracking=1.0):
        w = 0.0
        for ch in text:
            w += self._tile(ch, size, italic)[0] * tracking
        return w

    def draw(self, cv, x, baseline, text, size, color, italic=False,
             tracking=1.0):
        cx = x
        for ch in text:
            adv, tw, th, tx0, dy, alpha = self._tile(ch, size, italic)
            if tw and th:
                cv.blit_alpha(int(round(cx)) + tx0, int(round(baseline)) + int(round(dy)),
                              tw, th, alpha, color)
            cx += adv * tracking
        return cx

    def draw_centered(self, cv, cx, baseline, text, size, color, italic=False,
                      tracking=1.0):
        w = self.width(text, size, italic, tracking)
        return self.draw(cv, cx - w / 2, baseline, text, size, color, italic,
                         tracking)


def wrap(font, text, size, max_w, italic=False, tracking=1.0):
    """Greedy word wrap -> list of lines (each fits max_w)."""
    words = text.split(" ")
    lines = []
    cur = ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if font.width(trial, size, italic, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines

# ================================================================ ILLUSTRATIONS
def _stars(cv, x, y, w, h, n, seed=7):
    import random
    rnd = random.Random(seed)
    for _ in range(n):
        sx = x + rnd.randint(2, w - 3)
        sy = y + rnd.randint(2, h // 2)
        r = rnd.choice([1, 1, 1, 2])
        cv.circle(sx, sy, r, (255, 244, 200))


def _building(cv, x, y, w, h, c, win_c=(255, 210, 110), lit=0.55, seed=3):
    import random
    rnd = random.Random(seed)
    cv.fill_rect(x, y, w, h, c)
    rows = max(1, h // 12)
    cols = max(1, w // 10)
    for r in range(rows):
        for cc in range(cols):
            if rnd.random() < lit:
                cv.fill_rect(x + 3 + cc * 10, y + 4 + r * 12, 5, 6, win_c)


def _smoke(cv, x, y, n=3, seed=5):
    import random
    rnd = random.Random(seed)
    for i in range(n):
        cv.circle(x + rnd.randint(-6, 6), y - i * 7, 5 + i * 2,
                  (200, 198, 190))


def hero_cop31(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (64, 46, 96), (238, 128, 84))
    cv.circle(x + w - 52, y + 26, 15, (255, 176, 90))
    cv.fill_poly([(x, y + h), (x + 70, y + 62), (x + 150, y + h)], (52, 34, 84))
    cv.fill_poly([(x + 120, y + h), (x + 210, y + 58), (x + w, y + h)], (44, 30, 74))
    # hall
    cv.fill_rect(x + 14, y + 40, w - 28, h - 40, (122, 92, 62))
    cv.fill_rect(x + 14, y + 40, w - 28, 4, (150, 118, 80))
    # windows with dusk light
    for wx in (x + 26, x + w - 62):
        cv.fill_rect(wx, y + 46, 36, 22, (250, 190, 110))
        cv.vline(wx + 18, y + 46, 22, (122, 92, 62))
    # flags on poles
    for i, fc in enumerate([(40, 80, 160), (178, 34, 34), (30, 120, 60),
                            (230, 190, 40)]):
        fx = x + 30 + i * 14
        cv.vline(fx, y + 46, 18, (240, 235, 220))
        cv.fill_rect(fx, y + 46, 11, 7, fc)
    # ceiling lamps
    for lx in (x + 70, x + 150, x + 230):
        cv.circle(lx, y + 46, 4, (255, 220, 130))
    # delegates (6) behind long table
    cols = [(180, 60, 60), (60, 90, 160), (40, 140, 70), (200, 140, 40),
            (120, 60, 140), (90, 90, 90)]
    for i, c in enumerate(cols):
        dx = x + 40 + i * 40
        cv.fill_rect(dx - 7, y + 74, 14, 12, c)
        cv.circle(dx, y + 70, 6, (232, 196, 160))
        cv.fill_rect(dx - 8, y + 63, 16, 3, (40, 40, 40))
    # long table
    cv.fill_rect(x + 24, y + 86, w - 48, 9, (80, 52, 30))
    cv.fill_rect(x + 24, y + 86, w - 48, 2, (150, 110, 70))
    # wall clock
    cv.circle(x + w - 24, y + 56, 9, (245, 240, 225))
    cv.thick_line(x + w - 24, y + 56, x + w - 24, y + 50, 1.5, INK)
    cv.thick_line(x + w - 24, y + 56, x + w - 19, y + 58, 1.5, INK)
    # NO DEAL banner
    cv.fill_rect(x + 96, y + 50, 108, 16, RED)
    f = FONT
    f.draw_centered(cv, x + 150, y + 62, "NO DEAL", 11, WHITE)


def hero_kyiv(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (6, 12, 36), (26, 44, 84))
    _stars(cv, x, y, w, h, 14, seed=11)
    cv.circle(x + w - 46, y + 22, 11, (252, 240, 200))
    cv.circle(x + w - 50, y + 19, 9, (230, 216, 170))
    # searchlights
    cv.fill_poly([(x + 60, y + 88), (x + 30, y + 10), (x + 96, y + 10)],
                 (200, 215, 240))
    cv.fill_poly([(x + 210, y + 92), (x + 186, y + 8), (x + 240, y + 8)],
                 (200, 215, 240))
    # skyline: 5 buildings, lit windows
    _building(cv, x + 8, y + 62, 52, h - 62, (14, 20, 44), seed=21)
    _building(cv, x + 66, y + 44, 46, h - 44, (18, 26, 52), seed=22)
    _building(cv, x + 118, y + 70, 58, h - 70, (12, 18, 40), seed=23)
    _building(cv, x + 182, y + 52, 48, h - 52, (16, 24, 48), seed=24)
    _building(cv, x + 236, y + 66, 56, h - 66, (14, 20, 44), seed=25)
    # fire glow + smoke on one building
    cv.circle(x + 96, y + 46, 12, (255, 120, 30))
    cv.circle(x + 96, y + 48, 7, (255, 200, 60))
    _smoke(cv, x + 96, y + 34, n=3, seed=26)
    # drones (3 silhouettes)
    for dx, dy in ((x + 150, y + 22), (x + 200, y + 34), (x + 120, y + 14)):
        cv.thick_line(dx - 7, dy - 4, dx + 7, dy + 4, 2, (20, 20, 24))
        cv.thick_line(dx - 7, dy + 4, dx + 7, dy - 4, 2, (20, 20, 24))
        cv.circle(dx, dy, 2, (255, 60, 40))


def hero_manama(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (238, 118, 58), (96, 52, 112))
    cv.circle(x + 250, y + 30, 13, (255, 210, 120))
    # sea
    cv.vgrad(x, y + h - 24, w, 24, (40, 70, 120), (18, 34, 70))
    cv.hline(x, y + h - 24, w, (220, 200, 160))
    # industrial buildings with chimneys + smoke
    for bx, bw, bh in ((x + 14, 54, 34), (x + 76, 62, 44), (x + 146, 50, 30)):
        cv.fill_rect(bx, y + h - 24 - bh, bw, bh, (52, 44, 52))
        cv.fill_rect(bx + bw - 12, y + h - 24 - bh - 16, 8, 16, (40, 34, 40))
        _smoke(cv, bx + bw - 8, y + h - 24 - bh - 18, n=2, seed=bx)
        for wy in range(3):
            cv.fill_rect(bx + 6 + wy * 16, y + h - 24 - bh + 8, 8, 6,
                         (255, 190, 90))
    # radar dish + waves
    dx, dy = x + 216, y + 52
    cv.fill_poly([(dx - 34, dy - 26), (dx + 34, dy - 26), (dx + 26, dy + 6),
                  (dx - 26, dy + 6)], (210, 214, 220))
    cv.ellipse(dx, dy - 26, 34, 12, (228, 232, 238))
    cv.thick_line(dx, dy + 6, dx, dy + 34, 4, (70, 74, 80))
    cv.thick_line(dx - 16, dy + 34, dx + 16, dy + 34, 4, (70, 74, 80))
    for i, r in enumerate((44, 56, 68)):
        cv.arc_ring(dx + 30, dy - 20, r, r - 2, -60, 60, (255, 240, 200))
    # red DENIED cross
    cx, cy = x + 150, y + 30
    cv.ring(cx, cy, 15, 12, RED)
    cv.thick_line(cx - 9, cy - 9, cx + 9, cy + 9, 4, RED)
    cv.thick_line(cx + 9, cy - 9, cx - 9, cy + 9, 4, RED)


def _tag(cv, x, y, text):
    f = FONT
    tw = f.width(text, 8) + 10
    cv.fill_rect(x, y, int(tw), 11, RED)
    f.draw(cv, x + 5, y + 9, text, 8, WHITE)


def thumb_icj(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (210, 200, 180), (120, 108, 92))
    # court building: pediment + columns
    cv.fill_poly([(x + 30, y + 12), (x + 160, y + 12), (x + 95, y + 30)],
                 (240, 234, 220))
    cv.circle(x + 95, y + 20, 5, GOLD)
    for cx in range(x + 36, x + 160, 22):
        cv.fill_rect(cx, y + 30, 8, 26, (245, 240, 228))
    cv.fill_rect(x + 28, y + 56, 134, 5, (245, 240, 228))
    cv.fill_rect(x + 20, y + 61, 150, 4, (60, 52, 44))
    # scales of justice
    sx, sy = x + 168, y + 22
    cv.vline(sx, sy - 8, 20, GOLD)
    cv.thick_line(sx - 12, sy - 8, sx + 12, sy - 8, 2, GOLD)
    cv.circle(sx - 12, sy + 2, 4, GOLD)
    cv.circle(sx + 12, sy + 2, 4, GOLD)


def thumb_hk(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (196, 52, 52), (120, 30, 40))
    # ballot box + paper
    cv.fill_rect(x + 16, y + 30, 52, 28, (245, 240, 228))
    cv.fill_rect(x + 12, y + 26, 60, 5, (200, 40, 40))
    cv.fill_poly([(x + 46, y + 12), (x + 62, y + 12), (x + 56, y + 30),
                  (x + 42, y + 30)], (255, 255, 255))
    cv.thick_line(x + 46, y + 26, x + 54, y + 16, 2, RED)
    cv.thick_line(x + 54, y + 16, x + 60, y + 24, 2, RED)
    # donut 98.79%
    cx, cy = x + 132, y + 32
    cv.ring(cx, cy, 22, 14, (250, 246, 236))
    cv.arc_ring(cx, cy, 22, 14, -90, 264, GOLD)
    cv.arc_ring(cx, cy, 22, 14, 264, 270, RED)
    FONT.draw_centered(cv, cx, cy + 4, "98.8%", 10, WHITE)
    # crowd dots
    for i, px in enumerate((x + 88, x + 100, x + 112, x + 124)):
        cv.circle(px, y + 56, 3, (255, 220, 180))
        cv.fill_rect(px - 4, y + 58, 8, 6, (40, 60, 120))


def thumb_cricket(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (120, 190, 90), (40, 120, 50))
    cv.fill_rect(x + 60, y + 8, 70, h - 16, (232, 210, 160))
    cv.vline(x + 95, y + 8, h - 16, (255, 255, 255))
    # stumps
    for sx in (x + 68, x + 72, x + 76):
        cv.vline(sx, y + 14, 10, (250, 220, 120))
    for sx in (x + 114, x + 118, x + 122):
        cv.vline(sx, y + h - 24, 10, (250, 220, 120))
    # bat + ball
    cv.thick_line(x + 130, y + 40, x + 152, y + 20, 6, (210, 170, 110))
    cv.circle(x + 158, y + 18, 4, (200, 40, 40))
    # scoreboard
    cv.fill_rect(x + 8, y + 8, 52, 16, (20, 30, 40))
    FONT.draw(cv, x + 12, y + 20, "720/9", 10, (255, 220, 90))


def thumb_f1(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (20, 24, 60), (70, 40, 110))
    _stars(cv, x, y, w, h, 8, seed=31)
    # track
    cv.fill_poly([(x, y + 44), (x + w, y + 36), (x + w, y + 58), (x, y + 64)],
                 (40, 40, 48))
    cv.thick_line(x, y + 50, x + w, y + 44, 1.5, (255, 220, 90))
    # race car
    cx, cy = x + 88, y + 42
    cv.fill_poly([(cx - 34, cy + 6), (cx - 20, cy - 4), (cx + 12, cy - 6),
                  (cx + 34, cy + 2), (cx + 30, cy + 8), (cx - 30, cy + 8)],
                 (200, 30, 30))
    cv.circle(cx - 18, cy + 8, 6, BLACK)
    cv.circle(cx + 18, cy + 8, 6, BLACK)
    cv.circle(cx - 18, cy + 8, 2, (180, 180, 180))
    cv.circle(cx + 18, cy + 8, 2, (180, 180, 180))
    # checkered flag
    fx, fy = x + 158, y + 12
    for r in range(2):
        for cc in range(3):
            if (r + cc) % 2 == 0:
                cv.fill_rect(fx + cc * 6, fy + r * 6, 6, 6, BLACK)
            else:
                cv.fill_rect(fx + cc * 6, fy + r * 6, 6, 6, WHITE)
    cv.vline(fx, fy, 22, (200, 200, 200))


def thumb_nba(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (220, 140, 60), (140, 70, 30))
    # court floor
    cv.fill_poly([(x, y + 40), (x + w, y + 36), (x + w, y + h), (x, y + h)],
                 (190, 110, 50))
    cv.ellipse(x + 95, y + 52, 46, 8, (255, 255, 255))
    # hoop
    cv.fill_rect(x + 150, y + 8, 5, 30, (220, 220, 220))
    cv.fill_rect(x + 146, y + 8, 26, 16, (240, 240, 240))
    cv.ring(x + 159, y + 30, 9, 7, (200, 40, 40))
    # ball
    cv.circle(x + 60, y + 30, 12, (230, 110, 40))
    cv.thick_line(x + 48, y + 30, x + 72, y + 30, 1.5, (120, 50, 10))
    cv.thick_line(x + 60, y + 18, x + 60, y + 42, 1.5, (120, 50, 10))
    # scoreboard
    cv.fill_rect(x + 8, y + 8, 44, 16, (20, 30, 40))
    FONT.draw(cv, x + 12, y + 20, "50 PTS", 10, (255, 220, 90))


def thumb_capitol(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (140, 170, 210), (70, 100, 150))
    # capitol dome
    cv.fill_rect(x + 16, y + 34, 60, 26, (245, 242, 235))
    cv.ellipse(x + 46, y + 34, 30, 16, (245, 242, 235))
    cv.fill_rect(x + 44, y + 12, 4, 8, (245, 242, 235))
    cv.circle(x + 46, y + 11, 2, GOLD)
    for cx in range(x + 22, x + 72, 10):
        cv.vline(cx, y + 40, 20, (180, 175, 165))
    # bar chart 258/435
    bx, by = x + 96, y + 52
    cv.fill_rect(bx, by - 34, 18, 34, (30, 90, 180))
    cv.fill_rect(bx + 24, by - 46, 18, 46, (200, 60, 50))
    cv.fill_rect(bx, by, 66, 2, (245, 242, 235))
    FONT.draw(cv, bx + 2, by - 40, "258", 9, WHITE)
    FONT.draw(cv, bx + 26, by - 52, "435", 9, WHITE)


def thumb_flags(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (150, 180, 220), (90, 120, 170))
    # UK flag (simplified): blue + white/red cross
    cv.fill_rect(x + 14, y + 12, 62, 34, (30, 60, 140))
    cv.fill_rect(x + 40, y + 12, 10, 34, WHITE)
    cv.fill_rect(x + 14, y + 25, 62, 8, WHITE)
    cv.fill_rect(x + 43, y + 12, 4, 34, RED)
    cv.fill_rect(x + 14, y + 27, 62, 4, RED)
    # EU flag: blue + gold stars circle
    cv.fill_rect(x + 96, y + 12, 62, 34, (20, 40, 120))
    for k in range(8):
        a = 2 * math.pi * k / 8 - math.pi / 2
        cv.circle(int(x + 127 + 11 * math.cos(a)),
                  int(y + 29 + 11 * math.sin(a)), 2, GOLD)
    # handshake: two sleeves meeting
    cv.fill_poly([(x + 60, y + 58), (x + 95, y + 50), (x + 95, y + 60),
                  (x + 60, y + 64)], (40, 80, 160))
    cv.fill_poly([(x + 130, y + 58), (x + 95, y + 50), (x + 95, y + 60),
                  (x + 130, y + 64)], (178, 34, 34))
    cv.circle(x + 95, y + 55, 6, (232, 196, 160))


def thumb_tehran(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (16, 20, 44), (60, 50, 90))
    _stars(cv, x, y, w, h, 8, seed=41)
    cv.circle(x + 160, y + 16, 9, (250, 240, 200))
    # dark buildings, few lit windows
    _building(cv, x + 10, y + 34, 40, h - 34, (10, 12, 26), lit=0.15, seed=42)
    _building(cv, x + 56, y + 26, 44, h - 26, (12, 14, 30), lit=0.1, seed=43)
    _building(cv, x + 106, y + 38, 46, h - 38, (10, 12, 26), lit=0.12,
              seed=44)
    # power pylon + lightning bolt
    px = x + 168
    cv.thick_line(px, y + 20, px, y + 58, 3, (180, 180, 190))
    cv.thick_line(px - 12, y + 26, px + 12, y + 26, 2, (180, 180, 190))
    cv.thick_line(px - 8, y + 34, px + 8, y + 34, 2, (180, 180, 190))
    cv.fill_poly([(x + 138, y + 12), (x + 128, y + 30), (x + 136, y + 30),
                  (x + 126, y + 48), (x + 142, y + 26), (x + 134, y + 26)],
                 (255, 220, 60))


def thumb_hospital(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (190, 210, 225), (120, 150, 180))
    # hospital building + red cross
    cv.fill_rect(x + 20, y + 20, 90, 38, (245, 245, 240))
    cv.fill_rect(x + 52, y + 8, 26, 12, (245, 245, 240))
    cv.fill_rect(x + 122, y + 30, 46, 28, (225, 225, 220))
    for wx in range(x + 28, x + 104, 14):
        cv.fill_rect(wx, y + 30, 8, 8, (120, 180, 210))
    cv.fill_rect(x + 128, y + 14, 8, 20, RED)
    cv.fill_rect(x + 122, y + 20, 20, 8, RED)
    # heart monitor line
    pts = [(x + 14, y + 62), (x + 60, y + 62), (x + 70, y + 52),
           (x + 80, y + 62), (x + 88, y + 58), (x + 96, y + 62),
           (x + 176, y + 62)]
    for i in range(len(pts) - 1):
        cv.thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                      2, RED)


def thumb_fire(cv, x, y, w, h):
    cv.vgrad(x, y, w, h, (60, 50, 60), (180, 70, 40))
    # factory + chimney
    cv.fill_rect(x + 14, y + 30, 80, 30, (70, 60, 66))
    cv.fill_rect(x + 94, y + 22, 14, 38, (60, 52, 56))
    cv.fill_rect(x + 108, y + 34, 56, 26, (80, 68, 70))
    for wx in range(x + 22, x + 88, 16):
        cv.fill_rect(wx, y + 38, 8, 8, (255, 190, 90))
    _smoke(cv, x + 101, y + 16, n=3, seed=51)
    # flames
    for fx, fr in ((x + 30, 12), (x + 52, 16), (x + 76, 11), (x + 120, 13),
                   (x + 142, 10)):
        cv.circle(fx, y + 58, fr, (255, 120, 20))
        cv.circle(fx, y + 60, fr // 2, (255, 210, 80))
    # fire truck hint
    cv.fill_rect(x + 150, y + 48, 32, 12, (200, 30, 30))
    cv.circle(x + 158, y + 60, 4, BLACK)
    cv.circle(x + 174, y + 60, 4, BLACK)


FONT = Font()

# ================================================================ DATA (SPEC §3)
LEADS = [
    {"num": 1, "loc": "ANTALYA, TÜRKIYE", "cat": "WORLD · CLIMATE",
     "badge": "CONFIRMED", "badge_c": (28, 120, 62),
     "tag": "COP31: FINAL TEXT", "hero": hero_cop31,
     "headline": "COP31 ends with no deal",
     "body": "EU + 130 nations reject a text with no fossil-fuel mention "
             "— the first COP since 2000 to end with no deal. Kurum: "
             "'no agreement on this text.' (UNFCCC / Reuters)"},
    {"num": 2, "loc": "KYIV REGION, UKRAINE", "cat": "EUROPE · WAR",
     "badge": "CONFIRMED", "badge_c": (28, 120, 62),
     "tag": "186 DRONES OVERNIGHT", "hero": hero_kyiv,
     "headline": "Russia fires 186 drones at Ukraine",
     "body": "186 drones fired overnight (72 jet-powered); 161 downed or "
             "jammed. A five-storey block in Dymer was hit — 2 dead, "
             "14 missing. (Kyiv Post)"},
    {"num": 3, "loc": "MANAMA, BAHRAIN", "cat": "MIDDLE EAST · IRAN",
     "badge": "CLAIM", "badge_c": (178, 34, 34),
     "tag": "CLAIM VS DENIAL", "hero": hero_manama,
     "headline": "Iran claims two US radars hit",
     "body": "IRGC says it destroyed two Patriot radars on Saturday "
             "night; Bahrain says a civilian site burned — a fire, no "
             "injuries. (CBS / Fars)"},
]

# Small-story bodies are condensed to fit exactly 2 lines in a 192px
# column (SPEC §3 texts are ~120 chars; a 192px column holds ~70).
# Every body keeps its one specific number/fact + source.
SMALL = [
    {"num": 4, "loc": "THE HAGUE", "cat": "WORLD COURT",
     "headline": "ICJ: Myanmar committed genocide",
     "body": "UN court: Myanmar committed genocide of the Rohingya. "
             "(Reuters)",
     "thumb": thumb_icj, "tag": "ICJ RULING"},
    {"num": 5, "loc": "HONG KONG", "cat": "ELECTION",
     "headline": "Record turnout in committee polls",
     "body": "98.79% turnout, 5,640 of 5,709 voters; 856 for 723 seats. "
             "(SCMP)",
     "thumb": thumb_hk, "tag": "98.79% TURNOUT"},
    {"num": 6, "loc": "WELLINGTON, NZ", "cat": "CRICKET",
     "headline": "India declare on a record 720/9",
     "body": "Highest Test total ever in NZ, passing 715/6; Rahul 136. "
             "(ESPNcricinfo)",
     "thumb": thumb_cricket, "tag": "720/9 DECLARED"},
    {"num": 7, "loc": "LAS VEGAS", "cat": "FORMULA 1",
     "headline": "Verstappen wins the Las Vegas GP",
     "body": "Verstappen beats Norris under the lights on the Strip. "
             "(FIA / AP)",
     "thumb": thumb_f1, "tag": "VERSTAPPEN WINS"},
    {"num": 8, "loc": "SAN ANTONIO, USA", "cat": "NBA",
     "headline": "Wembanyama scores 50 as Spurs roll on",
     "body": "50 pts, 19 rebounds, 5 blocks; Spurs beat Pelicans 114–91. "
             "(NBA / AP)",
     "thumb": thumb_nba, "tag": "50 POINTS"},
    {"num": 9, "loc": "WASHINGTON, USA", "cat": "POLITICS",
     "headline": "Democrats win biggest House majority",
     "body": "Democrats hold at least 258 House seats — biggest since "
             "1992. (AP)",
     "thumb": thumb_capitol, "tag": "258 SEATS"},
    {"num": 10, "loc": "LONDON", "cat": "EUROPE",
     "headline": "UK and EU strike post-Brexit deals",
     "body": "Britain and the EU agree deals on trade and travel. "
             "(AP / Reuters)",
     "thumb": thumb_flags, "tag": "UK–EU DEAL"},
    {"num": 11, "loc": "TEHRAN, IRAN", "cat": "ENERGY",
     "headline": "Iran begins rationing electricity",
     "body": "Rolling blackouts up to 2 hours a day as war damage bites. "
             "(Wires)",
     "thumb": thumb_tehran, "tag": "POWER CUTS"},
    {"num": 12, "loc": "BRASILIA, BRAZIL", "cat": "HEALTH",
     "headline": "Bolsonaro in intensive care",
     "body": "Acute bowel obstruction, stable; surgery possible, age 71. "
             "(Reuters)",
     "thumb": thumb_hospital, "tag": "IN INTENSIVE CARE"},
    {"num": 13, "loc": "CIKANDE, INDONESIA", "cat": "FIRE",
     "headline": "Candy-factory fire in Cikande: 3 dead; 36 missing",
     "body": "Fire rips through the Bantam factory; 3 dead, 36 missing. "
             "(Detiknews)",
     "thumb": thumb_fire, "tag": "3 DEAD, 36 MISSING"},
]

# ALSO items condensed to one line each in a ~490px column.
ALSO = [
    (14, "Benghazi: Sea drones hit Russian warship; second ship targeted. (Wires)"),
    (15, "Washington: FBI probes apparent hack of its crime database. (AP)"),
    (16, "Gaza City: Israeli fire kills four; 3 in a strike on a food vehicle. (Gaza civil defence)"),
    (17, "Turin: Alcaraz wins first ATP Finals, beats Zverev. (ATP)"),
    (18, "Gulf of Finland: Sparta II towed home after drone strike. (Wires)"),
    (19, "Europe: Estonia to shut five Russia border crossings 1 Dec. (Reuters)"),
    (20, "Europe: Denmark expels a Russian attaché over an alleged plot. (Guardian)"),
    (21, "South Asia: Nepal PM Shah lands in Delhi; meets Modi Monday. (IANS)"),
    (22, "East Asia: Chinese bomber turns back 170 km from Manila. (AP)"),
    (23, "Southeast Asia: Philippines M5.9 quake, 898 km deep, off Palawan. (EMSC)"),
    (24, "East Asia: Japan poll: record 52% feel friendly to South Korea. (Ipsos)"),
    (25, "South Asia: India and China hold fresh military talks. (Wires)"),
    (26, "Africa: Somalia expels UAE ambassador, recalls its envoy. (Wires)"),
    (27, "Africa: Sudan: RSF accused of killing civilians in W. Kordofan. (Claim)"),
    (28, "Africa: Kenya discharges its last Ebola patient. (Wires)"),
    (29, "Africa: Drone strikes damage UN facility in Khartoum; 4 killed. (Wires)"),
    (30, "Oceania: Marles rejects US report on AUKUS subs. (ABC)"),
    (31, "Oceania: Melbourne — 70 years since the 1956 Olympics opened. (ABC)"),
    (32, "North America: Trump seeks 'permanent' Israel deal. (Al Jazeera)"),
    (33, "Southeast Asia: EU and Indonesia sign trade deal after ten years. (DW)"),
    (34, "Africa: Sudan army retakes ~30 towns in Kordofan. (FT)"),
    (35, "South Asia: Bangladesh: 30 Awami League homes set on fire. (Local)"),
    (36, "Middle East: Lebanon: Aoun demands Israel withdrawal. (Al Jazeera)"),
    (37, "World: Scientists sequence a whale's genome from breath by drone. (Wires)"),
    (38, "Middle East: Saudi Arabia and Yemen's Houthis exchange fire. (Wires)"),
]

DATE_CHECK = [
    "400-drone, 110-missile barrage (Thu 19–Fri 20 Nov)",
    "148-drone night, Kryvyi Rih double-tap (Fri 20–Sat 21)",
    "'El Chapo Isidro' captured (Sat 21 Nov)",
    "Bayelsa boat capsizes, 24 dead (Fri 21 Nov)",
    "Gaza aid-van strike (Sat 21 Nov)",
    "Nvidia SEC probe first reported (Fri 20 Nov)",
    "Saudi strikes on Hodeidah (20–21 Nov)",
    "Peru earthquake (Fri 20 Nov)",
    "Copa Sudamericana final (Sat 21 Nov)",
    "BepiColombo enters Mercury orbit (Sat 21 Nov)",
    "Russian missiles entered Poland (Fri 20 Nov)",
    "Rugby: England beat NZ 37-12 (Sat 21 Nov)",
    "Arsenal 2-2 Newcastle; Leeds 4-1 Chelsea (Sat 21)",
]

REGIONS = [
    ("EUROPE", 5, (26, 90, 160)),
    ("MIDDLE EAST", 5, (178, 34, 34)),
    ("NORTH AMERICA", 5, (20, 120, 110)),
    ("SOUTH AMERICA", 1, (200, 120, 30)),
    ("EAST ASIA", 3, (110, 60, 150)),
    ("SOUTH ASIA", 4, (40, 140, 70)),
    ("SOUTHEAST ASIA", 3, (150, 90, 40)),
    ("AFRICA", 6, (210, 90, 20)),
    ("OCEANIA", 2, (60, 110, 140)),
    ("WORLD", 4, (90, 88, 80)),
]

NUMBERS = [
    ("186", "DRONES FIRED"),
    ("161", "DOWNED"),
    ("258", "HOUSE SEATS"),
    ("$120bn", "ADAPTATION TARGET DROPPED"),
    ("720/9", "INDIA'S RECORD TOTAL"),
    ("98.79%", "HONG KONG TURNOUT"),
]

TIMELINE = [
    ("01:00", "HK polls open"),
    ("03:00", "COP31 objections close"),
    ("05:11", "Hamas seeks talks"),
    ("05:30", "Las Vegas GP ends"),
    ("06:00", "COP31 approval due"),
    ("07:30", "Approval slips again"),
    ("09:45", "PRESS TIME"),
]

# Dotted world map, 48 cols x 16 rows (SPEC §4b). '#' = land.
MAP_GRID = [
    "     #####    #             ###   #######       ",
    "   ##############      ##  ##################   ",
    "    ###########      # ######################   ",
    "     #########       #####################      ",
    "      #######        ################## #       ",
    "      #######         ###############           ",
    "        ####          ##############            ",
    "          ##           ############             ",
    "           ####         #########               ",
    "           #####        ########                ",
    "           #####         #####     ########     ",
    "            ###          ####          ####     ",
    "            ###          ###           #### #   ",
    "            ##           ##             ##      ",
    "            ##           #                      ",
    "            #                                   ",
]
# (story, col, row) — true positions; display positions shift when pins
# would overlap, with a thin leader line to the true spot.
PINS = [
    (1, 28, 4), (2, 28, 3), (3, 31, 6), (4, 25, 3), (5, 39, 7),
    (6, 46, 14), (7, 9, 5), (8, 11, 6), (9, 14, 4), (10, 24, 3),
    (11, 31, 5), (12, 14, 11), (13, 38, 10),
]
PIN_SHIFT = {1: (-1, 1), 11: (1, -1), 4: (0, -1)}


# ================================================================ LAYOUT
# Cursor discipline: y always points at the TOP of the current block.
# A text line of size S has baseline = top + S (S = cap height) and
# occupies down to baseline + 0.25*S (descenders). Every block below
# accounts for that; nothing overlaps.
def draw_page(cv):
    f = FONT
    y = 0
    # ---- header bar (16) ----
    cv.fill_rect(0, y, W, 16, NAVY)
    f.draw_centered(cv, W / 2, y + 12,
                    "THE WORLD IN ONE DAY  ·  38 STORIES – 10 REGIONS – "
                    "EVERY ONE DATED SUNDAY 22 NOVEMBER 2026",
                    10, (240, 238, 230))
    y += 16
    # ---- title line 1, 58px (75) ----
    f.draw_centered(cv, W / 2, y + 1 + 58, "Sunday 22 November 2026", 58, INK)
    y += 75
    # ---- title line 2, 28px, one line (38) ----
    l2_full = ("No Deal in Antalya, 186 Drones Over Kyiv, and Hong Kong's "
               "98.79% Vote")
    l2_short = "No Deal in Antalya · 186 Drones Over Kyiv · 98.79% in Hong Kong"
    l2 = l2_full if f.width(l2_full, 28) <= 1000 else l2_short
    f.draw_centered(cv, W / 2, y + 1 + 28, l2, 28, INK)
    y += 37
    # ---- subhead, red italic 14px (20) ----
    f.draw_centered(cv, W / 2, y + 1 + 14,
                    "COP31 ends with no deal · 186 drones over Ukraine in "
                    "the night · Iran's radar claim meets Bahrain's denial",
                    14, RED, italic=True)
    y += 20
    # ---- numbers strip (48) ----
    strip_y = y
    cv.hline(0, strip_y, W, RULE)
    box_w = 1000 / 6
    for i, (num, lab) in enumerate(NUMBERS):
        bx = 12 + i * box_w
        if i:
            cv.vline(int(bx), strip_y + 4, 40, RULE)
        f.draw_centered(cv, bx + box_w / 2, strip_y + 36.5, num, 36, RED)
        f.draw_centered(cv, bx + box_w / 2, strip_y + 46, lab, 8.5, GREY)
    cv.hline(0, strip_y + 47, W, RULE)
    y += 47
    # ---- region tabs (13) ----
    tab_y = y
    total_w = sum(f.width(name + " " + str(n), 10) + 22
                  for name, n, _ in REGIONS)
    tx = 12
    for name, n, c in REGIONS:
        tw = (f.width(name + " " + str(n), 10) + 22) * 1000 / total_w
        cv.fill_rect(int(tx), tab_y, int(tw) - 1, 13, c)
        f.draw_centered(cv, tx + tw / 2, tab_y + 10.5,
                        name + " " + str(n), 10, WHITE)
        tx += tw
    y += 13
    # ---- timeline (12) ----
    tl_y = y
    cv.fill_rect(0, tl_y, W, 12, NAVY2)
    tx = 12
    f.draw(cv, tx, tl_y + 10, "THE DAY IN UTC  ", 9.5, GOLD)
    tx += f.width("THE DAY IN UTC  ", 9.5)
    for j, (tm, ev) in enumerate(TIMELINE):
        f.draw(cv, tx, tl_y + 10, tm + " ", 9.5, GOLD)
        tx += f.width(tm + " ", 9.5)
        tail = ev if j == len(TIMELINE) - 1 else ev + "  ·  "
        f.draw(cv, tx, tl_y + 10, tail, 9.5, (235, 232, 224))
        tx += f.width(tail, 9.5)
    y += 12
    # ---- 3 leads (228) ----
    lead_y = y
    col_w = 328
    for i, ld in enumerate(LEADS):
        lx = 12 + i * (col_w + 8)
        ly = lead_y
        ld["hero"](cv, lx, ly, col_w, 115)
        _tag(cv, lx, ly, ld["tag"])
        ly += 116
        f.draw(cv, lx, ly + 10.5,
               "%d · %s · %s" % (ld["num"], ld["loc"], ld["cat"]), 10.5, INK)
        bw = f.width(ld["badge"], 8.5) + 10
        cv.fill_rect(lx + col_w - bw, ly, bw, 11, ld["badge_c"])
        f.draw(cv, lx + col_w - bw + 5, ly + 9, ld["badge"], 8.5, WHITE)
        ly += 12
        hl = wrap(f, ld["headline"], 26, col_w)
        assert len(hl) <= 2, "lead %d headline %d lines" % (ld["num"], len(hl))
        for ln in hl:
            f.draw(cv, lx, ly + 26, ln, 26, INK)
            ly += 26
        ly += 2
        bl = wrap(f, ld["body"], 12, col_w, tracking=0.95)
        assert len(bl) == 3, "lead %d body wraps to %d lines: %r" % (
            ld["num"], len(bl), bl)
        for ln in bl:
            f.draw(cv, lx, ly + 12, ln, 12, INK, tracking=0.95)
            ly += 14.5
        # source is already cited in the body text itself
    y += 226
    # ---- 10 small stories, 5 cols x 2 rows (274) ----
    sm_y = y
    scol_w = 192
    for r in range(2):
        for c in range(5):
            st = SMALL[r * 5 + c]
            sx = 12 + c * (scol_w + 10)
            sy = sm_y + r * 136
            st["thumb"](cv, sx, sy, scol_w, 65)
            _tag(cv, sx, sy, st["tag"])
            yy = sy + 66
            f.draw(cv, sx, yy + 9.5,
                   "%d · %s · %s" % (st["num"], st["loc"], st["cat"]),
                   9.5, INK)
            yy += 11
            hl = wrap(f, st["headline"], 13, scol_w)
            assert len(hl) <= 2, "small %d headline %d lines" % (
                st["num"], len(hl))
            for ln in hl:
                f.draw(cv, sx, yy + 13, ln, 13, INK)
                yy += 14.5
            yy += 1
            bl = wrap(f, st["body"], 10.5, scol_w, tracking=0.9)
            assert len(bl) == 2, "small %d body wraps to %d lines: %r" % (
                st["num"], len(bl), bl)
            for ln in bl:
                f.draw(cv, sx, yy + 10.5, ln, 10.5, INK, tracking=0.9)
                yy += 13
            # source is already cited in the body text itself
    y += 272
    # ---- ALSO list (148) ----
    also_y = y
    f.draw(cv, 12, also_y + 11, "ALSO ON SUNDAY 22 NOVEMBER — 25 MORE STORIES",
           11, INK)
    cv.hline(12, also_y + 14, 1000, RULE)
    ay = also_y + 14.5
    for i, (num, text) in enumerate(ALSO):
        col = i // 13
        row = i % 13
        ax = 12 if col == 0 else 512
        by = ay + row * 10.7
        f.draw(cv, ax, by + 8.5, "%d " % num, 8.5, RED)
        f.draw(cv, ax + f.width("38 ", 8.5), by + 8.5, text, 8.5, INK)
    y += 154
    # ---- bottom: dotted map + DATE CHECK (141) ----
    bot_y = y
    cv.hline(0, bot_y, W, RULE)
    map_x, map_w = 12, 452
    map_h = 134
    f.draw(cv, map_x, bot_y + 8.5, "WHERE IT HAPPENED", 10, INK)
    f.draw(cv, map_x + f.width("WHERE IT HAPPENED ", 10), bot_y + 8.5,
           "— pins match story numbers", 9, GREY)
    dots_y0 = bot_y + 10
    dx = map_w / 48.0
    dy = map_h / 16.0
    for r, row in enumerate(MAP_GRID):
        assert len(row) == 48, "map row %d len %d" % (r, len(row))
        for cc, ch in enumerate(row):
            if ch == "#":
                cv.circle(int(map_x + cc * dx + dx / 2),
                          int(dots_y0 + r * dy + dy / 2), 2.5, MAPDOT)
    for (num, pc, pr) in PINS:
        dc, dr = PIN_SHIFT.get(num, (0, 0))
        px = int(map_x + (pc + dc) * dx + dx / 2)
        py = int(dots_y0 + (pr + dr) * dy + dy / 2)
        txp = int(map_x + pc * dx + dx / 2)
        typ = int(dots_y0 + pr * dy + dy / 2)
        if (dc, dr) != (0, 0):
            cv.thick_line(px, py, txp, typ, 1, RED)
        cv.circle(px, py, 7, RED)
        f.draw_centered(cv, px, py + 3, str(num), 8, WHITE)
    dc_x, dc_w = 482, 530
    cv.rect_outline(dc_x, bot_y + 2, dc_w, 139, RED, 2)
    f.draw(cv, dc_x + 8, bot_y + 11, "DATE CHECK", 10, RED)
    f.draw(cv, dc_x + 8 + f.width("DATE CHECK ", 10), bot_y + 11,
           "— left out on purpose: these happened on other days", 9, GREY)
    for i, item in enumerate(DATE_CHECK):
        col = i // 7
        row = i % 7
        ix = dc_x + 8 + col * 262
        iy = bot_y + 15 + row * 15
        f.draw(cv, ix, iy + 9.5, "· " + item, 9.5, INK)
    f.draw(cv, dc_x + 8, bot_y + 131,
           "CONFIRMED verified by multiple sources · CLAIM one side's "
           "claim, contested · REPORTED single-source report", 8, GREY)
    y += 143
    # ---- footer (8) ----
    cv.hline(0, y, W, RULE)
    f.draw_centered(cv, W / 2, y + 6.5,
                    "Sources: Reuters, BBC, AP, AFP, Al Jazeera, The "
                    "Guardian, UNFCCC, Kyiv Post, SCMP, ESPNcricinfo, "
                    "Detiknews · Scenes are drawn illustrations · Wires "
                    "read to press time 09:45 UTC", 8, GREY)
    y += 8
    return y


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = Canvas()
    final_y = draw_page(cv)
    if final_y > H:
        print("WARNING: layout overflow, final_y=%d" % final_y, file=sys.stderr)
    path = os.path.join(out_dir, "entry.png")
    size = write_png(cv, path)
    print("wrote %s (%d bytes), final_y=%d" % (path, size, final_y))


if __name__ == "__main__":
    main()
