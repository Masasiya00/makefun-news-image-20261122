#!/usr/bin/env python3
"""makefun news-image-20261122 - v7 entry.
Draws the 1024x1024 front page from scratch: hand-made serif font,
scanline rasterizer with 4x supersampling, PNG encoder. Stdlib only.
Deterministic: no time, no randomness, no network.
"""
import math
import os
import struct
import zlib

W = H = 1024

# ---------------------------------------------------------------- PNG ----
def png_bytes(rgb, w, h):
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(t, data):
        c = t + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


# -------------------------------------------------------------- canvas ----
def hx(s):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(hx(bg)) * (w * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i], self.px[i + 1], self.px[i + 2] = c

    def blend(self, x, y, c, a):
        """a: 0..255 coverage of color c over existing pixel."""
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        i = (y * self.w + x) * 3
        if a >= 255:
            self.px[i], self.px[i + 1], self.px[i + 2] = c
            return
        ia = 255 - a
        self.px[i] = (c[0] * a + self.px[i] * ia) >> 8
        self.px[i + 1] = (c[1] * a + self.px[i + 1] * ia) >> 8
        self.px[i + 2] = (c[2] * a + self.px[i + 2] * ia) >> 8

    def rect(self, x0, y0, x1, y1, c):
        x0 = max(0, int(math.floor(x0))); y0 = max(0, int(math.floor(y0)))
        x1 = min(self.w, int(math.ceil(x1))); y1 = min(self.h, int(math.ceil(y1)))
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = c
        for y in range(y0, y1):
            i = (y * self.w + x0) * 3
            n = x1 - x0
            self.px[i:i + n * 3] = bytes((r, g, b)) * n

    def vgrad(self, x0, y0, x1, y1, ctop, cbot):
        """Vertical linear gradient rectangle."""
        x0 = max(0, int(math.floor(x0))); y0 = max(0, int(math.floor(y0)))
        x1 = min(self.w, int(math.ceil(x1))); y1 = min(self.h, int(math.ceil(y1)))
        hgt = max(1, y1 - y0)
        for y in range(y0, y1):
            t = (y - y0) / hgt
            c = tuple(int(ctop[k] + (cbot[k] - ctop[k]) * t) for k in range(3))
            self.rect(x0, y, x1, y + 1, c)

    def hgrad(self, x0, y0, x1, y1, cleft, cright):
        x0 = max(0, int(math.floor(x0))); y0 = max(0, int(math.floor(y0)))
        x1 = min(self.w, int(math.ceil(x1))); y1 = min(self.h, int(math.ceil(y1)))
        wdt = max(1, x1 - x0)
        for x in range(x0, x1):
            t = (x - x0) / wdt
            c = tuple(int(cleft[k] + (cright[k] - cleft[k]) * t) for k in range(3))
            self.rect(x, y0, x + 1, y1, c)

    def disc(self, cx, cy, r, c):
        """Filled circle, 1px AA on the rim."""
        r = float(r)
        y0 = max(0, int(math.floor(cy - r - 1))); y1 = min(self.h, int(math.ceil(cy + r + 1)))
        for y in range(y0, y1):
            dy = y + 0.5 - cy
            dx = math.sqrt(max(0.0, r * r - dy * dy))
            x0 = int(math.floor(cx - dx)); x1 = int(math.ceil(cx + dx))
            for x in range(max(0, x0), min(self.w, x1)):
                d = math.hypot(x + 0.5 - cx, y + 0.5 - cy)
                if d <= r - 0.5:
                    self.set(x, y, c)
                elif d < r + 0.5:
                    self.blend(x, y, c, int(255 * (r + 0.5 - d)))

    def ellipse(self, cx, cy, rx, ry, c):
        y0 = max(0, int(math.floor(cy - ry - 1))); y1 = min(self.h, int(math.ceil(cy + ry + 1)))
        for y in range(y0, y1):
            dy = (y + 0.5 - cy) / ry
            if abs(dy) >= 1:
                continue
            dx = rx * math.sqrt(1.0 - dy * dy)
            x0 = int(math.floor(cx - dx)); x1 = int(math.ceil(cx + dx))
            for x in range(max(0, x0), min(self.w, x1)):
                d = ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2
                if d <= 0.92:
                    self.set(x, y, c)
                elif d < 1.08:
                    self.blend(x, y, c, int(255 * (1.08 - d) / 0.16))

    def ring(self, cx, cy, r_out, r_in, c):
        """Filled annulus."""
        y0 = max(0, int(math.floor(cy - r_out - 1))); y1 = min(self.h, int(math.ceil(cy + r_out + 1)))
        for y in range(y0, y1):
            dy = y + 0.5 - cy
            for x in range(max(0, int(math.floor(cx - r_out))), min(self.w, int(math.ceil(cx + r_out)))):
                d = math.hypot(x + 0.5 - cx, dy)
                if r_in + 0.4 <= d <= r_out - 0.4:
                    self.set(x, y, c)
                elif r_in - 0.4 < d < r_in + 0.4 or r_out - 0.4 < d < r_out + 0.4:
                    a = 255 - int(255 * abs(d - r_out) / 0.8) if d > (r_out + r_in) / 2 else \
                        255 - int(255 * abs(d - r_in) / 0.8)
                    self.blend(x, y, c, max(0, min(255, a)))

    def poly(self, pts, c):
        """Filled polygon, even-odd scanline, 1px vertical AA approx."""
        if len(pts) < 3:
            return
        edges = []
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]; x1, y1 = pts[(i + 1) % n]
            if y0 == y1:
                continue
            edges.append((x0, y0, x1, y1))
        if not edges:
            return
        y0 = max(0, int(math.floor(min(p[1] for p in pts))))
        y1 = min(self.h, int(math.ceil(max(p[1] for p in pts))))
        for y in range(y0, y1):
            yc = y + 0.5
            xs = []
            for x0, yy0, x1, yy1 in edges:
                if (yy0 <= yc < yy1) or (yy1 <= yc < yy0):
                    xs.append(x0 + (yc - yy0) * (x1 - x0) / (yy1 - yy0))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = int(math.ceil(xs[k])); xb = int(math.floor(xs[k + 1]))
                for x in range(max(0, xa), min(self.w, xb + 1)):
                    self.set(x, y, c)

    def line(self, x0, y0, x1, y1, wdt, c):
        """Thick line as a polygon."""
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L * wdt / 2.0, dx / L * wdt / 2.0
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                   (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)

    def hline(self, x0, x1, y, wdt, c):
        self.rect(x0, y - wdt / 2.0, x1, y + wdt / 2.0, c)


# ------------------------------------------------- font path helpers ----
# Glyph space: y down, cap top y=0, baseline y=70, descender bottom y=92,
# x-height top y=20. One em = 70 units of cap height.
# A subpath is a list of segments: ('M',x,y) move, ('L',x,y) line,
# ('C',x1,y1,x2,y2,x3,y3) cubic bezier, ('A',cx,cy,rx,ry,a0,a1) arc
# (angles in degrees, x=cx+rx*cos, y=cy+ry*sin, increasing = clockwise).
# Fill rule is NONZERO: outer contours clockwise, counters counter-clockwise.

def rect_p(x0, y0, x1, y1):
    return [("M", x0, y0), ("L", x1, y0), ("L", x1, y1), ("L", x0, y1)]


def stem_p(x, y0, y1, w, fl=1.8):
    """Vertical stem with flared (serif) ends, clockwise."""
    f = fl
    return [("M", x - f, y0), ("L", x + w + f, y0), ("L", x + w, y0 + 6),
            ("L", x + w, y1 - 6), ("L", x + w + f, y1), ("L", x - f, y1),
            ("L", x, y1 - 6), ("L", x, y0 + 6)]


def ell_p(cx, cy, rx, ry, ccw=False):
    return [("M", cx + rx, cy), ("A", cx, cy, rx, ry, 0, -360 if ccw else 360)]


def arc_p(cx, cy, rx, ry, a0, a1):
    return [("M", cx + rx * math.cos(math.radians(a0)), cy + ry * math.sin(math.radians(a0))),
            ("A", cx, cy, rx, ry, a0, a1)]


def bez_pts(p0, p1, p2, p3, n=14):
    out = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0]
        y = mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1]
        out.append((x, y))
    return out


def catmull(pts, n=10):
    """Catmull-Rom spline through control points -> dense polyline."""
    if len(pts) < 3:
        return list(pts)
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i + 1], P[i + 2], P[i + 3]
        for j in range(n):
            t = j / n
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(pts[-1])
    return out


def spine_poly(pts, hw):
    """Stroke a centerline polyline with varying half-width -> closed polygon.
    hw: scalar or list of half-widths per point. Width varies smoothly."""
    n = len(pts)
    if isinstance(hw, (int, float)):
        hw = [hw] * n
    left, right = [], []
    for i in range(n):
        x, y = pts[i]
        x0, y0 = pts[max(0, i - 1)]
        x1, y1 = pts[min(n - 1, i + 1)]
        tx, ty = x1 - x0, y1 - y0
        L = math.hypot(tx, ty) or 1.0
        tx, ty = tx / L, ty / L
        nx, ny = -ty, tx
        h = hw[i]
        left.append((x + nx * h, y + ny * h))
        right.append((x - nx * h, y - ny * h))
    return left + right[::-1]


def spine_hw(pts, thick=5.0, thin=3.3):
    """Half-width per spine point: thick where tangent is vertical, thin
    where horizontal -> light contrast ~1.5:1, like a serif text face."""
    out = []
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[max(0, i - 1)]
        x1, y1 = pts[min(n - 1, i + 1)]
        tx, ty = x1 - x0, y1 - y0
        L = math.hypot(tx, ty) or 1.0
        out.append(thin + (thick - thin) * abs(ty) / L)
    return out


def flatten_subpath(sp):
    """Subpath segments -> list of (x, y) points (closed implicitly)."""
    pts = []
    cur = None
    for seg in sp:
        if seg[0] == "M":
            cur = (seg[1], seg[2])
            pts.append(cur)
        elif seg[0] == "L":
            cur = (seg[1], seg[2])
            pts.append(cur)
        elif seg[0] == "C":
            p0 = cur
            p1 = (seg[1], seg[2]); p2 = (seg[3], seg[4]); p3 = (seg[5], seg[6])
            bp = bez_pts(p0, p1, p2, p3, 12)
            pts.extend(bp[1:])
            cur = p3
        elif seg[0] == "A":
            _, cx, cy, rx, ry, a0, a1 = seg
            sweep = a1 - a0
            steps = max(4, int(abs(sweep) / 9))
            for i in range(1, steps + 1):
                a = math.radians(a0 + sweep * i / steps)
                pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
            cur = pts[-1]
    return pts


def flatten_glyph(subpaths):
    return [flatten_subpath(sp) for sp in subpaths]

# ------------------------------------------- glyph construction helpers ----
def poly_p(pts):
    return [("M", pts[0][0], pts[0][1])] + [("L", x, y) for x, y in pts[1:]]


def ring_p(cx, cy, rxo, ryo, rxi, ryi):
    """Closed ring: outer ellipse clockwise, inner counter-clockwise."""
    return [ell_p(cx, cy, rxo, ryo), ell_p(cx, cy, rxi, ryi, ccw=True)]


def ring_seg(cx, cy, rxo, ryo, rxi, ryi, a0, a1):
    """Ring segment from angle a0 to a1 (clockwise sweep), e.g. C, U, ( )."""
    ox0 = cx + rxo * math.cos(math.radians(a0)); oy0 = cy + ryo * math.sin(math.radians(a0))
    ix1 = cx + rxi * math.cos(math.radians(a1)); iy1 = cy + ryi * math.sin(math.radians(a1))
    return [("M", ox0, oy0), ("A", cx, cy, rxo, ryo, a0, a1),
            ("L", ix1, iy1), ("A", cx, cy, rxi, ryi, a1, a0)]


def bowl_r(cx, cy, rxo, ryo, rxi, ryi):
    """Right bowl for D/B: outer arc -90..90 + chord; inner counter CCW."""
    outer = [("M", cx, cy - ryo), ("A", cx, cy, rxo, ryo, -90, 90)]
    inner = [("M", cx, cy + ryi), ("A", cx, cy, rxi, ryi, 90, -90)]
    return [outer, inner]


def bowl_top(cx, cy, rxo, ryo, rxi, ryi, a_end=60):
    """Upper bowl for P/R: outer arc -90..a_end, inner counter CCW.
    Stem left edge is at x = cx-10."""
    ex = cx + rxo * math.cos(math.radians(a_end)); ey = cy + ryo * math.sin(math.radians(a_end))
    ix = cx + rxi * math.cos(math.radians(a_end)); iy = cy + ryi * math.sin(math.radians(a_end))
    outer = [("M", cx, cy - ryo), ("A", cx, cy, rxo, ryo, -90, a_end),
             ("L", cx - 10, ey), ("L", cx - 10, cy - ryo)]
    inner = [("M", ix, iy), ("A", cx, cy, rxi, ryi, a_end, -90),
             ("L", cx, iy)]
    return [outer, inner]


def arch_p(cx, cy, rxo, ryo, rxi, ryi, yb):
    """Inverted-U arch for n/m/h: outer arc 180..360, inner back, legs to yb."""
    return [("M", cx - rxo, yb), ("L", cx - rxo, cy),
            ("A", cx, cy, rxo, ryo, 180, 360), ("L", cx + rxo, yb),
            ("L", cx + rxi, yb), ("L", cx + rxi, cy),
            ("A", cx, cy, rxi, ryi, 360, 180), ("L", cx - rxi, yb)]


def bar(x0, x1, y, h):
    return rect_p(x0, y, x1, y + h)


# S spine control points (cap box 0..70). Two lobes, upper smaller.
S_CTRL = [(46, 9), (38, 2), (26, 1), (15, 6), (11, 15), (13, 24), (20, 30),
          (29, 34), (38, 38), (45, 45), (47, 54), (42, 63), (33, 68),
          (22, 69), (12, 64)]


def s_paths(ctrl=S_CTRL, thick=5.0, thin=3.3):
    pts = catmull(ctrl, 8)
    return [poly_p(spine_poly(pts, spine_hw(pts, thick, thin)))]


# ------------------------------------------------------- uppercase glyphs ----
# Each entry: (advance width, [subpaths]). Stem 10, bar 6.5 -> ratio 1.54:1.
U = {}
U["A"] = (60, [poly_p([(26, 0), (33, 0), (14, 70), (4, 70)]),
               poly_p([(26, 0), (33, 0), (55, 70), (45, 70)]),
               rect_p(13, 44, 46, 50.5)])
U["B"] = (58, [stem_p(6, 0, 70, 10)] + bowl_r(16, 19, 30, 19, 20.5, 12.5)
          + bowl_r(16, 50, 33, 20, 23, 13))
U["C"] = (58, [ring_seg(30, 35, 29, 35, 19, 28.5, 52, 308)])
U["D"] = (58, [stem_p(6, 0, 70, 10)] + bowl_r(16, 35, 36, 35, 26, 28.5))
U["E"] = (56, [stem_p(6, 0, 70, 10), bar(6, 58, 0, 6.5), bar(6, 46, 31.5, 6.5),
               bar(6, 58, 63.5, 6.5)])
U["F"] = (54, [stem_p(6, 0, 70, 10), bar(6, 56, 0, 6.5), bar(6, 46, 31.5, 6.5)])
U["G"] = (60, [ring_seg(30, 35, 29, 35, 19, 28.5, 52, 308),
               rect_p(30, 40, 56, 46.5), rect_p(48.5, 40, 56, 58)])
U["H"] = (60, [stem_p(6, 0, 70, 10), stem_p(44, 0, 70, 10), bar(16, 44, 31.5, 6.5)])
U["I"] = (34, [stem_p(12, 0, 70, 10), bar(3, 31, 0, 6.5), bar(3, 31, 63.5, 6.5)])
U["J"] = (52, [bar(20, 58, 0, 6.5),
               poly_p(spine_poly(catmull([(49, 4), (49, 30), (48, 46), (43, 58),
                                           (34, 64), (24, 62), (18, 54)], 8),
                                  spine_hw(catmull([(49, 4), (49, 30), (48, 46), (43, 58),
                                                    (34, 64), (24, 62), (18, 54)], 8),
                                           5.0, 3.6)))])
U["K"] = (60, [stem_p(6, 0, 70, 10),
               poly_p([(16, 38), (26, 32), (58, 0), (48, 0)]),
               poly_p([(30, 38), (38, 44), (58, 70), (48, 70)])])
U["L"] = (54, [stem_p(6, 0, 70, 10), bar(6, 56, 63.5, 6.5)])
U["M"] = (66, [stem_p(6, 0, 70, 10), stem_p(50, 0, 70, 10),
               poly_p([(16, 0), (24, 0), (36, 44), (28, 44)]),
               poly_p([(42, 0), (50, 0), (36, 44), (28, 44)])])
U["N"] = (60, [stem_p(6, 0, 70, 10), stem_p(44, 0, 70, 10),
               poly_p([(16, 0), (26, 0), (54, 70), (44, 70)])])
U["O"] = (60, ring_p(30, 35, 29, 35, 19, 28.5))
U["P"] = (56, [stem_p(6, 0, 70, 10)] + bowl_top(16, 20, 32, 20, 22, 13.5, 60))
U["Q"] = (62, ring_p(30, 35, 29, 35, 19, 28.5)
          + [poly_p([(42, 50), (50, 46), (62, 68), (55, 70)])])
U["R"] = (58, [stem_p(6, 0, 70, 10)] + bowl_top(16, 20, 32, 20, 22, 13.5, 60)
          + [poly_p([(36, 36), (46, 40), (60, 70), (50, 70)])])
U["S"] = (58, s_paths())
U["T"] = (58, [bar(4, 58, 0, 6.5), stem_p(24, 0, 70, 10)])
U["U"] = (60, [stem_p(6, 0, 48, 10), stem_p(44, 0, 48, 10),
               ring_seg(30, 46, 24, 24, 15, 17.5, 0, 180)])
U["V"] = (58, [poly_p([(6, 0), (17, 0), (37, 70), (26, 70)]),
               poly_p([(47, 0), (58, 0), (37, 70), (26, 70)])])
U["W"] = (80, [poly_p([(6, 0), (15, 0), (29, 70), (20, 70)]),
               poly_p([(35, 0), (44, 0), (29, 70), (20, 70)]),
               poly_p([(35, 0), (44, 0), (59, 70), (50, 70)]),
               poly_p([(65, 0), (74, 0), (59, 70), (50, 70)])])
U["X"] = (58, [poly_p([(6, 0), (16, 0), (58, 70), (48, 70)]),
               poly_p([(48, 0), (58, 0), (16, 70), (6, 70)])])
U["Y"] = (58, [poly_p([(6, 0), (17, 0), (37, 40), (26, 40)]),
               poly_p([(47, 0), (58, 0), (37, 40), (26, 40)]),
               stem_p(26, 36, 70, 10)])
U["Z"] = (56, [bar(6, 58, 0, 6.5), bar(6, 58, 63.5, 6.5),
               poly_p([(50, 6.5), (58, 6.5), (14, 63.5), (6, 63.5)])])

# ------------------------------------------------------- lowercase glyphs ----
# x-height 20..70, ascender 0, descender 92. Stem 9, bar 6 -> ratio 1.5:1.
L = {}
L["a"] = (54, ring_p(30, 47, 21, 23, 12, 17) + [stem_p(45, 20, 70, 9),
               poly_p(spine_poly(catmull([(50, 23), (42, 20), (32, 20), (24, 24)], 8),
                                  spine_hw(catmull([(50, 23), (42, 20), (32, 20), (24, 24)], 8),
                                           3.8, 3.0)))])
L["b"] = (54, [stem_p(6, 0, 70, 9)] + ring_p(31, 48, 20, 22, 11.5, 16))
L["c"] = (52, [ring_seg(30, 45, 21, 25, 12, 19, 50, 310)])
L["d"] = (54, ring_p(27, 48, 20, 22, 11.5, 16) + [stem_p(45, 0, 70, 9)])
L["e"] = (54, ring_p(30, 47, 21, 23, 12.5, 17) + [rect_p(10, 43, 50, 49.5)])
L["f"] = (40, [stem_p(26, 6, 70, 9),
               poly_p(spine_poly(catmull([(28, 12), (30, 2), (38, -1), (45, 4),
                                           (47, 12)], 8),
                                  spine_hw(catmull([(28, 12), (30, 2), (38, -1), (45, 4),
                                                    (47, 12)], 8), 4.5, 3.0))),
               rect_p(14, 32, 48, 38)])
L["g"] = (54, ring_p(29, 46, 20, 22, 11.5, 16) + [stem_p(44, 20, 70, 9),
               poly_p(spine_poly(catmull([(48, 64), (50, 78), (46, 88), (36, 92),
                                           (25, 90), (19, 83)], 8),
                                  spine_hw(catmull([(48, 64), (50, 78), (46, 88), (36, 92),
                                                    (25, 90), (19, 83)], 8),
                                           5.0, 3.2)))])
L["h"] = (54, [stem_p(6, 0, 70, 9), arch_p(30, 34, 20, 15, 11, 9.5, 70)])
L["i"] = (30, [stem_p(11, 20, 70, 9), ell_p(15.5, 8.5, 4.5, 4.5)])
L["j"] = (32, [ell_p(16, 2, 4.5, 4.5), stem_p(11, 10, 86, 9),
               poly_p(spine_poly(catmull([(15, 82), (13, 90), (6, 92), (0, 86)], 8),
                                  spine_hw(catmull([(15, 82), (13, 90), (6, 92), (0, 86)], 8),
                                           4.5, 3.0)))])
L["k"] = (54, [stem_p(6, 0, 70, 9),
               poly_p([(15, 40), (23, 34), (45, 20), (37, 20)]),
               poly_p([(28, 42), (36, 46), (50, 70), (42, 70)])])
L["l"] = (32, [stem_p(11, 0, 70, 9), rect_p(7, 65, 25, 70)])
L["m"] = (78, [stem_p(6, 20, 70, 9), arch_p(26, 34, 16, 15, 8, 9.5, 70),
               arch_p(54, 34, 16, 15, 8, 9.5, 70)])
L["n"] = (54, [stem_p(6, 20, 70, 9), arch_p(30, 34, 20, 15, 11, 9.5, 70)])
L["o"] = (54, ring_p(30, 45, 21, 25, 12, 19))
L["p"] = (54, [stem_p(6, 20, 92, 9)] + ring_p(31, 48, 20, 22, 11.5, 16))
L["q"] = (54, ring_p(27, 48, 20, 22, 11.5, 16) + [stem_p(45, 20, 92, 9)])
L["r"] = (38, [stem_p(6, 20, 70, 9),
               poly_p(spine_poly(catmull([(14, 26), (22, 20), (32, 21), (38, 28),
                                           (40, 36)], 8),
                                  spine_hw(catmull([(14, 26), (22, 20), (32, 21), (38, 28),
                                                    (40, 36)], 8), 4.5, 3.0)))])
L["s"] = (50, s_paths([(42, 23), (34, 19), (23, 20), (14, 26), (13, 34), (19, 40),
                       (29, 43), (38, 47), (42, 54), (40, 61), (33, 67), (22, 68),
                       (13, 63)], 4.8, 3.2))
L["t"] = (38, [stem_p(14, 8, 70, 9), rect_p(4, 30, 34, 36),
               poly_p(spine_poly(catmull([(18, 62), (20, 69), (26, 71), (32, 66)], 8),
                                  spine_hw(catmull([(18, 62), (20, 69), (26, 71), (32, 66)], 8),
                                           4.5, 3.0)))])
L["u"] = (54, [stem_p(6, 20, 48, 9), stem_p(39, 20, 48, 9),
               ring_seg(27, 46, 21, 24, 12.5, 18, 0, 180)])
L["v"] = (52, [poly_p([(6, 20), (15, 20), (33, 70), (24, 70)]),
               poly_p([(41, 20), (50, 20), (33, 70), (24, 70)])])
L["w"] = (72, [poly_p([(6, 20), (14, 20), (26, 70), (18, 70)]),
               poly_p([(22, 20), (30, 20), (26, 70), (18, 70)]),
               poly_p([(30, 20), (38, 20), (50, 70), (42, 70)]),
               poly_p([(46, 20), (54, 20), (50, 70), (42, 70)])])
L["x"] = (52, [poly_p([(6, 20), (14, 20), (50, 70), (42, 70)]),
               poly_p([(42, 20), (50, 20), (14, 70), (6, 70)])])
L["y"] = (52, [poly_p([(6, 20), (14, 20), (30, 66), (22, 66)]),
               poly_p([(42, 20), (50, 20), (30, 66), (22, 66)]),
               poly_p(spine_poly(catmull([(28, 62), (30, 74), (28, 84), (22, 90),
                                           (15, 88)], 8),
                                  spine_hw(catmull([(28, 62), (30, 74), (28, 84), (22, 90),
                                                    (15, 88)], 8), 4.5, 3.0)))])
L["z"] = (50, [rect_p(8, 20, 50, 26), rect_p(8, 64, 50, 70),
               poly_p([(44, 26), (50, 26), (14, 64), (8, 64)])])

# ------------------------------------------------------------ digits 0-9 ----
D = {}
D["0"] = (58, ring_p(29, 35, 26, 35, 16, 28.5))
D["1"] = (40, [stem_p(20, 0, 70, 10),
               poly_p([(4, 20), (12, 10), (22, 4), (22, 12)]),
               rect_p(8, 63.5, 38, 70)])
D["2"] = (56, [poly_p(spine_poly(catmull([(12, 16), (16, 4), (28, 0), (40, 4),
                                           (44, 14), (38, 24), (24, 40), (14, 58),
                                           (12, 64)], 8),
                                  spine_hw(catmull([(12, 16), (16, 4), (28, 0), (40, 4),
                                                    (44, 14), (38, 24), (24, 40), (14, 58),
                                                    (12, 64)], 8), 5.0, 3.3))),
               rect_p(10, 63.5, 48, 70)])
D["3"] = (56, [poly_p(spine_poly(catmull([(14, 8), (24, 2), (36, 4), (44, 12),
                                           (42, 22), (34, 28), (40, 32), (46, 40),
                                           (46, 52), (38, 64), (24, 68), (12, 64)], 8),
                                  spine_hw(catmull([(14, 8), (24, 2), (36, 4), (44, 12),
                                                    (42, 22), (34, 28), (40, 32), (46, 40),
                                                    (46, 52), (38, 64), (24, 68), (12, 64)], 8),
                                           5.0, 3.3)))])
D["4"] = (58, [poly_p([(38, 0), (46, 0), (14, 54), (6, 54)]),
               stem_p(36, 0, 70, 10), rect_p(6, 44, 48, 50.5)])
D["5"] = (56, [rect_p(10, 0, 48, 6.5), rect_p(10, 0, 19.5, 32),
               poly_p(spine_poly(catmull([(14, 30), (20, 32), (32, 32), (42, 38),
                                           (44, 50), (38, 62), (26, 68), (14, 64)], 8),
                                  spine_hw(catmull([(14, 30), (20, 32), (32, 32), (42, 38),
                                                    (44, 50), (38, 62), (26, 68), (14, 64)], 8),
                                           5.0, 3.3)))])
D["6"] = (56, ring_p(29, 50, 20, 20, 11, 13.5)
          + [poly_p(spine_poly(catmull([(44, 4), (38, 8), (28, 16), (20, 26),
                                         (15, 36)], 8),
                                spine_hw(catmull([(44, 4), (38, 8), (28, 16), (20, 26),
                                                  (15, 36)], 8), 5.0, 3.3)))])
D["7"] = (56, [rect_p(10, 0, 50, 6.5),
               poly_p([(44, 6.5), (50, 6.5), (22, 70), (14, 70)])])
D["8"] = (58, ring_p(29, 20, 22, 20, 13, 13.5) + ring_p(29, 50, 25, 20, 15.5, 13.5))
D["9"] = (56, ring_p(29, 20, 20, 20, 11, 13.5)
          + [poly_p(spine_poly(catmull([(14, 66), (20, 62), (30, 54), (38, 44),
                                         (43, 34)], 8),
                                spine_hw(catmull([(14, 66), (20, 62), (30, 54), (38, 44),
                                                  (43, 34)], 8), 5.0, 3.3)))])

# ----------------------------------------------------------- punctuation ----
P = {}
P[" "] = (26, [])
P["."] = (30, [ell_p(15, 66, 4.8, 4.8)])
P[","] = (30, [ell_p(15, 66, 4.8, 4.8),
               poly_p(spine_poly(catmull([(15, 68), (13, 76), (9, 82)], 8),
                                  spine_hw(catmull([(15, 68), (13, 76), (9, 82)], 8),
                                           4.5, 3.0)))])
P[":"] = (30, [ell_p(15, 30, 4.8, 4.8), ell_p(15, 66, 4.8, 4.8)])
P[";"] = (30, [ell_p(15, 30, 4.8, 4.8), ell_p(15, 66, 4.8, 4.8),
               poly_p(spine_poly(catmull([(15, 68), (13, 76), (9, 82)], 8),
                                  spine_hw(catmull([(15, 68), (13, 76), (9, 82)], 8),
                                           4.5, 3.0)))])
P["'"] = (26, [poly_p([(11, 0), (18, 0), (14, 16), (7, 16)])])
P['"'] = (44, [poly_p([(5, 0), (12, 0), (8, 16), (1, 16)]),
               poly_p([(22, 0), (29, 0), (25, 16), (18, 16)])])
P["!"] = (36, [stem_p(13, 0, 54, 10), ell_p(18, 65, 5, 5)])
P["?"] = (52, [poly_p(spine_poly(catmull([(16, 14), (20, 4), (30, 0), (40, 4),
                                           (44, 14), (38, 24), (30, 30), (28, 40)], 8),
                                  spine_hw(catmull([(16, 14), (20, 4), (30, 0), (40, 4),
                                                    (44, 14), (38, 24), (30, 30), (28, 40)], 8),
                                           5.0, 3.3))),
               rect_p(24, 42, 33, 52), ell_p(28.5, 65, 5, 5)])
P["-"] = (52, [rect_p(8, 32, 44, 38.5)])
P["–"] = (60, [rect_p(6, 32, 54, 38.5)])
P["—"] = (64, [rect_p(4, 32, 58, 38.5)])
P["·"] = (30, [ell_p(15, 35, 4.5, 4.5)])
P["%"] = (62, [ell_p(20, 18, 9, 9), ell_p(20, 18, 5, 5, ccw=True),
               ell_p(42, 52, 9, 9), ell_p(42, 52, 5, 5, ccw=True),
               poly_p([(50, 4), (56, 4), (10, 66), (4, 66)])])
P["$"] = (52, s_paths([(38, 8), (30, 2), (20, 3), (14, 10), (13, 18), (18, 25),
                       (28, 29), (36, 34), (39, 42), (36, 52), (28, 58), (18, 59),
                       (11, 54)], 5.0, 3.3) + [rect_p(24, -2, 32, 72)])
P["/"] = (48, [poly_p([(38, 0), (46, 0), (20, 70), (12, 70)])])
P["("] = (30, [ring_seg(38, 35, 16, 35, 9, 28.5, 110, 250)])
P[")"] = (30, [ring_seg(14, 35, 16, 35, 9, 28.5, -70, 70)])
P["+"] = (60, [rect_p(8, 30, 52, 40), rect_p(25, 13, 35, 57)])
P["="] = (60, [rect_p(8, 26, 52, 32.5), rect_p(8, 44, 52, 50.5)])
P["°"] = (34, [ell_p(17, 8, 7, 7), ell_p(17, 8, 3.5, 3.5, ccw=True)])
P["•"] = (30, [ell_p(15, 35, 6, 6)])
P["~"] = (52, [poly_p(spine_poly(catmull([(6, 38), (14, 30), (22, 38), (30, 30),
                                           (38, 38), (46, 30)], 8),
                                  spine_hw(catmull([(6, 38), (14, 30), (22, 38), (30, 30),
                                                    (38, 38), (46, 30)], 8), 3.2, 2.6)))])
P["’"] = P["'"]
P["“"] = P['"']
P["”"] = P['"']

GLYPHS = {}
GLYPHS.update(U)
GLYPHS.update(L)
GLYPHS.update(D)
GLYPHS.update(P)

# ------------------------------------------------------- font rasterizer ----
_SS = 4  # supersampling factor (px per glyph unit in canonical tiles)
_canonical = {}   # char -> (w, h, minx, miny, alpha bytes, sat)
_resampled = {}   # (char, cap_px, italic) -> (w, h, alpha bytes, dx, dy)
_missing = set()


def _rasterize_glyph(ch):
    """Render one glyph to a canonical binary tile at 4 px per unit.
    Nonzero winding fill. Returns (w, h, minx, miny, alpha, sat)."""
    adv, subpaths = GLYPHS[ch]
    polys = flatten_glyph(subpaths)
    if not polys:
        return (0, 0, 0.0, 0.0, b"", None)
    xs = [x for p in polys for x, y in p]
    ys = [y for p in polys for x, y in p]
    minx, maxx = min(xs) - 1.0, max(xs) + 1.0
    miny, maxy = min(ys) - 1.0, max(ys) + 1.0
    w = int(math.ceil((maxx - minx) * _SS))
    h = int(math.ceil((maxy - miny) * _SS))
    alpha = bytearray(w * h)
    # edges in tile-pixel coords
    buckets = [[] for _ in range(h)]
    for poly in polys:
        n = len(poly)
        for i in range(n):
            x0, y0 = poly[i]; x1, y1 = poly[(i + 1) % n]
            if y0 == y1:
                continue
            px0 = (x0 - minx) * _SS; py0 = (y0 - miny) * _SS
            px1 = (x1 - minx) * _SS; py1 = (y1 - miny) * _SS
            r0 = max(0, int(math.floor(min(py0, py1))))
            r1 = min(h, int(math.ceil(max(py0, py1))))
            for r in range(r0, r1):
                buckets[r].append((px0, py0, px1, py1))
    for r in range(h):
        yc = r + 0.5
        ev = buckets[r]
        if not ev:
            continue
        cross = []
        for px0, py0, px1, py1 in ev:
            if (py0 <= yc < py1) or (py1 <= yc < py0):
                cross.append((px0 + (yc - py0) * (px1 - px0) / (py1 - py0),
                              1 if py1 > py0 else -1))
        if not cross:
            continue
        cross.sort()
        wind = 0
        start = None
        for x, d in cross:
            prev = wind
            wind += d
            if prev == 0 and wind != 0:
                start = x
            elif prev != 0 and wind == 0 and start is not None:
                xa = max(0, int(math.ceil(start))); xb = min(w, int(math.floor(x)) + 1)
                base = r * w
                for xx in range(xa, xb):
                    alpha[base + xx] = 255
                start = None
    # summed-area table for fast box resampling
    sat = [[0] * (w + 1) for _ in range(h + 1)]
    for y in range(h):
        rowsum = 0
        arow = alpha[y * w:(y + 1) * w]
        srow = sat[y + 1]; sprow = sat[y]
        for x in range(w):
            rowsum += arow[x]
            srow[x + 1] = sprow[x + 1] + rowsum
    return (w, h, minx, miny, bytes(alpha), sat)


def _sat_sum(sat, x0, y0, x1, y1):
    return sat[y1][x1] - sat[y0][x1] - sat[y1][x0] + sat[y0][x0]


def _get_tile(ch, cap, italic):
    """Resampled alpha tile for (char, cap height px, italic). Returns
    (w, h, alpha bytes, dx, dy): blit at (pen_x + dx, baseline_y + dy)."""
    key = (ch, cap, italic)
    t = _resampled.get(key)
    if t is not None:
        return t
    if ch not in GLYPHS:
        t = (0, 0, b"", 0.0, 0.0)
        _resampled[key] = t
        return t
    if ch not in _canonical:
        _canonical[ch] = _rasterize_glyph(ch)
    cw, chh, minx, miny, _alpha, sat = _canonical[ch]
    if cw == 0:
        t = (0, 0, b"", 0.0, 0.0)
        _resampled[key] = t
        return t
    scale = cap / 70.0
    k = _SS / scale  # canonical px per output px
    ow = max(1, int(round(cw / k)))
    oh = max(1, int(round(chh / k)))
    shear = 0.16 if italic else 0.0
    base_c = (0.0 - miny) * _SS  # baseline row in canonical px
    out = bytearray(ow * oh)
    for j in range(oh):
        yc = (j + 0.5) * k
        shift = shear * (base_c - yc)
        sy0 = int(max(0, math.floor(j * k))); sy1 = int(min(chh, math.ceil((j + 1) * k)))
        for i in range(ow):
            sx0 = i * k + shift; sx1 = (i + 1) * k + shift
            x0 = int(max(0, math.floor(sx0))); x1 = int(min(cw, math.ceil(sx1)))
            if x1 <= x0 or sy1 <= sy0:
                continue
            s = _sat_sum(sat, x0, sy0, x1, sy1)
            area = (x1 - x0) * (sy1 - sy0)
            a = int(round(255.0 * s / (255.0 * area)))
            if a:
                out[j * ow + i] = a if a < 255 else 255
    t = (ow, oh, bytes(out), minx * scale, miny * scale)
    _resampled[key] = t
    return t


def glyph_adv(ch):
    g = GLYPHS.get(ch)
    if g is None:
        if ch not in _missing:
            _missing.add(ch)
            print("WARN missing glyph for", repr(ch))
        return 26.0
    return g[0]


def text_width(s, cap, tracking=0.0):
    w = 0.0
    for ch in s:
        w += glyph_adv(ch) * cap / 70.0 + tracking
    return w - tracking if s else 0.0


def draw_text(cv, s, x, y_top, cap, color, align="left", tracking=0.0,
              italic=False, max_w=None):
    """Draw text; y_top = top of cap-height box. Returns (width used, right x)."""
    w = text_width(s, cap, tracking)
    if align == "center":
        x = x - w / 2.0
    elif align == "right":
        x = x - w
    if max_w is not None and w > max_w:
        # shrink tracking only, never below cap (caller must size text)
        pass
    scale = cap / 70.0
    baseline = y_top + cap
    pen = x
    for ch in s:
        if ch == " ":
            pen += glyph_adv(ch) * scale + tracking
            continue
        tw, th, alpha, dx, dy = _get_tile(ch, cap, italic)
        if tw:
            bx = int(round(pen + dx)); by = int(round(y_top + dy))
            for j in range(th):
                row = j * tw
                yy = by + j
                if yy < 0 or yy >= cv.h:
                    continue
                for i in range(tw):
                    a = alpha[row + i]
                    if a:
                        cv.blend(bx + i, yy, color, a)
        pen += glyph_adv(ch) * scale + tracking
    return w, pen


def wrap_text(s, cap, max_w, tracking=0.0):
    """Greedy word wrap. Returns list of lines (strings)."""
    words = s.split(" ")
    lines = []
    cur = ""
    for wd in words:
        trial = wd if not cur else cur + " " + wd
        if text_width(trial, cap, tracking) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, s, x, y_top, cap, color, max_w, line_h, tracking=0.0,
              italic=False, align="left", max_lines=None):
    """Draw wrapped paragraph. Returns bottom y (after last line)."""
    lines = wrap_text(s, cap, max_w, tracking)
    if max_lines is not None:
        lines = lines[:max_lines]
    y = y_top
    for ln in lines:
        draw_text(cv, ln, x, y, cap, color, align=align, tracking=tracking,
                  italic=italic)
        y += line_h
    return y

# ------------------------------------------------------------- scenes ----
INK = hx("#141414")
PAPER = hx("#f7f3e8")
NAVY = hx("#1a2b4a")
RED = hx("#a32c22")
GOLD = hx("#c9a227")
GREY = hx("#6b6b66")


def sky(cv, x, y, w, h, c1, c2, c3=None):
    if c3 is None:
        cv.vgrad(x, y, x + w, y + h, c1, c2)
    else:
        cv.vgrad(x, y, x + w, y + h * 0.55, c1, c2)
        cv.vgrad(x, y + h * 0.55, x + w, y + h, c2, c3)


def building(cv, x, y, w, h, c, win, lit=0.7):
    cv.rect(x, y, x + w, y + h, c)
    for wy in range(int(y + 5), int(y + h - 4), 9):
        for wx in range(int(x + 4), int(x + w - 4), 8):
            if ((wx * 7 + wy * 13) % 10) < int(lit * 10):
                cv.rect(wx, wy, wx + 3, wy + 4, win)


def person(cv, x, y, s, c):
    cv.disc(x, y - 3.2 * s, 1.6 * s, c)
    cv.rect(x - 1.4 * s, y - 1.6 * s, x + 1.4 * s, y + 2.6 * s, c)


def flag(cv, x, y, w, h, c1, c2=None):
    cv.rect(x, y, x + 1.2, y + h + 6, INK)
    cv.rect(x + 1.2, y, x + w, y + h * 0.55, c1)
    if c2:
        cv.rect(x + 1.2, y + h * 0.55, x + w, y + h, c2)


def cloud(cv, x, y, s, c):
    cv.disc(x, y, 2.2 * s, c)
    cv.disc(x + 2.4 * s, y + 0.6 * s, 1.8 * s, c)
    cv.disc(x - 2.4 * s, y + 0.7 * s, 1.7 * s, c)


def smoke(cv, x, y, s, c):
    cv.disc(x, y, 3.0 * s, c)
    cv.disc(x + 2.5 * s, y - 2.5 * s, 2.2 * s, c)
    cv.disc(x + 5 * s, y - 5 * s, 1.8 * s, c)


def star(cv, x, y, r=1.2):
    cv.disc(x, y, r, hx("#fff6d8"))


def drone(cv, x, y, s, c):
    cv.ellipse(x, y, 2.6 * s, 1.1 * s, c)
    cv.disc(x - 2.8 * s, y - 1.2 * s, 0.9 * s, c)
    cv.disc(x + 2.8 * s, y - 1.2 * s, 0.9 * s, c)
    cv.disc(x, y + 1.6 * s, 0.8 * s, hx("#ff5a3c"))


def arc_strip(cv, cx, cy, r, wdt, a0, a1, c, n=48):
    """Thick arc as a polygon strip (for donut charts)."""
    pts_o, pts_i = [], []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts_o.append((cx + (r + wdt / 2) * math.cos(a), cy + (r + wdt / 2) * math.sin(a)))
        pts_i.append((cx + (r - wdt / 2) * math.cos(a), cy + (r - wdt / 2) * math.sin(a)))
    cv.poly(pts_o + pts_i[::-1], c)


def donut(cv, cx, cy, r, pct, c, bgc):
    cv.ring(cx, cy, r, r - 5, bgc)
    arc_strip(cv, cx, cy, r - 2.5, 5, -90, -90 + 360 * pct / 100.0, c)


def scene_cop31(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#dfe9f2"), hx("#f2e7c9"), hx("#e8d9a8"))
    # ceiling lamps
    for lx in (x + w * 0.2, x + w * 0.5, x + w * 0.8):
        cv.line(lx, y, lx, y + 10, 1.5, INK)
        cv.ellipse(lx, y + 13, 9, 3.5, hx("#ffd97a"))
    # wall clock
    cv.disc(x + w - 22, y + 16, 8, PAPER)
    cv.ring(x + w - 22, y + 16, 8, 6.5, INK)
    cv.line(x + w - 22, y + 16, x + w - 18, y + 12, 1.2, INK)
    # long table + delegates
    ty = y + h - 34
    cv.rect(x + 8, ty, x + w - 8, ty + 22, hx("#7a4a2b"))
    cv.rect(x + 8, ty, x + w - 8, ty + 4, hx("#9a6a3b"))
    cols = [hx("#1a2b4a"), hx("#a32c22"), hx("#2a6b3c"), hx("#c9a227"),
            hx("#5b3a7a"), hx("#2b7a8c")]
    for i, c in enumerate(cols):
        px = x + 22 + i * (w - 44) / 5
        person(cv, px, ty - 2, 3.2, c)
        cv.rect(px - 6, ty - 26, px + 6, ty - 24, PAPER)
    # flags behind
    for i, c in enumerate([hx("#1a2b4a"), hx("#a32c22"), hx("#2a6b3c"), hx("#c9a227")]):
        flag(cv, x + 30 + i * 62, y + h - 78, 16, 9, c, PAPER)
    # NO DEAL banner
    cv.rect(x + w * 0.32, y + 30, x + w * 0.68, y + 48, RED)
    draw_text(cv, "NO DEAL", x + w * 0.5, y + 32, 13, PAPER, align="center", tracking=0.5)


def scene_kyiv(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#0d1530"), hx("#2a2a55"), hx("#4a2a4a"))
    for i in range(9):
        sx = x + 12 + (i * 37) % (w - 24)
        sy = y + 8 + (i * 23) % 34
        star(cv, sx, sy, 1.1)
    cv.disc(x + w - 30, y + 16, 9, hx("#f2e6b8"))
    # searchlights
    cv.poly([(x + 60, y + h - 8), (x + 52, y + h - 8), (x + 30, y + 6)], hx("#ffe9a8"))
    cv.poly([(x + w - 70, y + h - 8), (x + w - 62, y + h - 8), (x + w - 30, y + 8)], hx("#ffe9a8"))
    # buildings
    bw = [52, 44, 60, 40, 48]
    bx = x + 6
    for i, bwid in enumerate(bw):
        bh = 52 + ((i * 17) % 30)
        building(cv, bx, y + h - 8 - bh, bwid, bh, hx("#141c33"),
                 hx("#ffd97a"), lit=0.65)
        bx += bwid + 4
    # fire glow + smoke on one building
    cv.disc(x + w * 0.62, y + h - 46, 12, hx("#ff7a2a"))
    cv.disc(x + w * 0.62, y + h - 46, 6, hx("#ffd23c"))
    smoke(cv, x + w * 0.62, y + h - 62, 2.2, hx("#8a8a92"))
    drone(cv, x + w * 0.25, y + 26, 1.6, hx("#c8c8d8"))
    drone(cv, x + w * 0.5, y + 18, 1.4, hx("#c8c8d8"))
    drone(cv, x + w * 0.78, y + 30, 1.5, hx("#c8c8d8"))


def scene_manama(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#e8783c"), hx("#b04a72"), hx("#5a3a6e"))
    cv.disc(x + w - 40, y + 22, 11, hx("#ffd9a0"))
    # radar dish
    cx, cy = x + w * 0.34, y + 58
    cv.line(cx, cy, cx - 8, y + h - 22, 3, INK)
    cv.line(cx, cy, cx + 8, y + h - 22, 3, INK)
    cv.ellipse(cx, cy, 34, 12, hx("#d8d8e0"))
    cv.ellipse(cx, cy, 34, 12, hx("#d8d8e0"))
    cv.line(cx - 34, cy, cx + 34, cy, 1.5, hx("#8a8a96"))
    for r in (42, 52):
        arc_strip(cv, cx, cy, r, 2, -160, -20, hx("#ffe9a8"), 24)
    # industrial buildings + chimneys
    for i, (bx, bw, bh) in enumerate([(x + w * 0.58, 46, 44), (x + w * 0.76, 40, 56),
                                      (x + w * 0.9, 34, 36)]):
        cv.rect(bx, y + h - 22 - bh, bx + bw, y + h - 22, hx("#3a2a3c"))
        cv.rect(bx + bw * 0.6, y + h - 22 - bh - 16, bx + bw * 0.75, y + h - 22 - bh, hx("#3a2a3c"))
        smoke(cv, bx + bw * 0.68, y + h - 22 - bh - 22, 1.6, hx("#c8c8d8"))
    # sea
    cv.rect(x, y + h - 22, x + w, y + h, hx("#2a4a6e"))
    cv.hline(x + 12, x + w - 12, y + h - 12, 1.5, hx("#7aa8d8"))
    # DENIED cross
    dx, dy = x + w * 0.68, y + 30
    cv.line(dx - 10, dy - 10, dx + 10, dy + 10, 4, RED)
    cv.line(dx + 10, dy - 10, dx - 10, dy + 10, 4, RED)


def scene_icj(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#cfe0ee"), hx("#f2e7c9"))
    cv.rect(x + w * 0.18, y + 18, x + w * 0.82, y + h - 14, hx("#e8e0c8"))
    cv.poly([(x + w * 0.14, y + 20), (x + w * 0.5, y + 6), (x + w * 0.86, y + 20)], hx("#c8b888"))
    for i in range(5):
        cx = x + w * (0.22 + i * 0.14)
        cv.rect(cx, y + 24, cx + 7, y + h - 18, hx("#f7f3e8"))
    cv.rect(x + w * 0.16, y + h - 16, x + w * 0.84, y + h - 12, hx("#c8b888"))
    flag(cv, x + w * 0.06, y + 12, 14, 8, hx("#1a2b4a"), PAPER)
    flag(cv, x + w * 0.88, y + 12, 14, 8, hx("#2a6b3c"), PAPER)
    person(cv, x + w * 0.5, y + h - 8, 2.6, NAVY)


def scene_hk(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#d8e8f2"), hx("#f2e7c9"))
    # ballot box
    cv.rect(x + 14, y + h - 42, x + 62, y + h - 8, hx("#a32c22"))
    cv.rect(x + 10, y + h - 48, x + 66, y + h - 42, hx("#7a1e16"))
    cv.rect(x + 30, y + h - 56, x + 46, y + h - 46, PAPER)
    cv.line(x + 38, y + h - 56, x + 38, y + h - 46, 1, INK)
    # ballot paper flying in
    cv.poly([(x + 52, y + 14), (x + 66, y + 10), (x + 62, y + 30), (x + 48, y + 32)], PAPER)
    cv.line(x + 54, y + 18, x + 62, y + 16, 1, INK)
    # donut 98.79%
    donut(cv, x + w - 52, y + h // 2 + 2, 26, 98.79, hx("#2a6b3c"), hx("#d8d8d8"))
    draw_text(cv, "98.79%", x + w - 52, y + h // 2 - 3, 9, INK, align="center")
    # voters queue dots
    for i, c in enumerate([NAVY, RED, hx("#2a6b3c")]):
        person(cv, x + 84 + i * 16, y + h - 10, 2.4, c)


def scene_cricket(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#bfe0f2"), hx("#e8f2d8"))
    cv.rect(x, y + h - 34, x + w, y + h, hx("#3a8a3c"))
    cv.rect(x + w * 0.32, y + h - 34, x + w * 0.68, y + h, hx("#d8c89a"))
    # stumps
    for sx in (x + w * 0.42, x + w * 0.45, x + w * 0.48):
        cv.rect(sx, y + h - 30, sx + 1.6, y + h - 18, hx("#f2d23c"))
    # bat + ball
    cv.line(x + w * 0.62, y + h - 40, x + w * 0.72, y + h - 14, 4, hx("#c89a5a"))
    cv.disc(x + w * 0.78, y + h - 44, 4, RED)
    # scoreboard
    cv.rect(x + 8, y + 8, x + 78, y + 26, NAVY)
    draw_text(cv, "720/9", x + 43, y + 10, 13, PAPER, align="center")
    cloud(cv, x + w * 0.8, y + 12, 2.2, PAPER)
    person(cv, x + w * 0.2, y + h - 8, 2.6, PAPER)


def scene_f1(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#f2d8a8"), hx("#e8b878"))
    # track
    cv.poly([(x, y + h - 26), (x + w, y + h - 40), (x + w, y + h - 12), (x, y + h - 6)],
            hx("#3a3a40"))
    cv.poly([(x, y + h - 20), (x + w, y + h - 34), (x + w, y + h - 30), (x, y + h - 16)],
            hx("#f2f2f2"))
    # race car
    cx, cy = x + w * 0.42, y + h - 44
    cv.poly([(cx - 26, cy + 6), (cx - 20, cy - 4), (cx + 8, cy - 6), (cx + 26, cy + 2),
             (cx + 26, cy + 8), (cx - 26, cy + 8)], RED)
    cv.disc(cx - 16, cy + 9, 5, INK)
    cv.disc(cx + 16, cy + 9, 5, INK)
    cv.rect(cx + 24, cy - 10, cx + 30, cy + 2, INK)
    # speed lines
    for i in range(3):
        cv.hline(x + w * 0.62, x + w * 0.92, y + 14 + i * 8, 2, PAPER)
    # chequered flag
    for i in range(4):
        for j in range(2):
            cv.rect(x + w - 30 + i * 6, y + 8 + j * 6, x + w - 24 + i * 6, y + 14 + j * 6,
                    INK if (i + j) % 2 == 0 else PAPER)
    cv.rect(x + w - 31, y + 8, x + w - 30, y + 34, INK)


def scene_nba(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#f2e0c8"), hx("#d8b888"))
    cv.rect(x, y + h - 30, x + w, y + h, hx("#c86a2a"))
    cv.ellipse(x + w * 0.5, y + h - 8, 46, 7, hx("#e8a85a"))
    # hoop
    cv.rect(x + w - 34, y + 10, x + w - 8, y + 34, PAPER)
    cv.rect(x + w - 34, y + 10, x + w - 8, y + 34, INK) if False else None
    cv.ellipse(x + w - 21, y + 38, 9, 3, hx("#d84a1a"))
    cv.line(x + w - 28, y + 40, x + w - 26, y + 52, 1, PAPER)
    cv.line(x + w - 14, y + 40, x + w - 16, y + 52, 1, PAPER)
    # ball + player
    cv.disc(x + w * 0.3, y + 22, 7, hx("#e87a2a"))
    cv.line(x + w * 0.3 - 7, y + 22, x + w * 0.3 + 7, y + 22, 1, INK)
    person(cv, x + w * 0.55, y + h - 12, 3.4, NAVY)
    # scoreboard 50
    cv.rect(x + 8, y + 8, x + 56, y + 26, NAVY)
    draw_text(cv, "50 PTS", x + 32, y + 10, 12, PAPER, align="center")


def scene_dpr(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#d8e2f2"), hx("#f2e7c9"))
    # capitol dome
    cv.rect(x + w * 0.3, y + 26, x + w * 0.7, y + h - 12, hx("#f2efe2"))
    cv.ellipse(x + w * 0.5, y + 26, 26, 14, hx("#f2efe2"))
    cv.rect(x + w * 0.48, y + 8, x + w * 0.52, y + 16, hx("#c9a227"))
    for i in range(4):
        cx = x + w * (0.34 + i * 0.11)
        cv.rect(cx, y + 34, cx + 4, y + h - 14, hx("#c8b888"))
    # bar chart 258 / 435
    bx = x + w * 0.74
    cv.rect(bx, y + h - 40, bx + 12, y + h - 12, hx("#2a5a9a"))
    cv.rect(bx + 16, y + h - 30, bx + 28, y + h - 12, hx("#a32c22"))
    draw_text(cv, "258", bx + 6, y + h - 54, 11, hx("#2a5a9a"), align="center")
    draw_text(cv, "435", bx + 34, y + h - 54, 9, GREY, align="center")


def scene_ukeu(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#d8e2f2"), hx("#f2e7c9"))
    # bridge arc
    arc_strip(cv, x + w * 0.5, y + h - 6, 58, 5, 180, 360, hx("#8a8a92"), 32)
    cv.rect(x + 8, y + h - 26, x + 14, y + h - 6, hx("#6b6b66"))
    cv.rect(x + w - 14, y + h - 26, x + w - 8, y + h - 6, hx("#6b6b66"))
    # UK flag
    fx, fy = x + 16, y + 12
    cv.rect(fx, fy, fx + 34, fy + 20, hx("#1a2b6e"))
    cv.line(fx, fy, fx + 34, fy + 20, 3, PAPER)
    cv.line(fx + 34, fy, fx, fy + 20, 3, PAPER)
    cv.line(fx + 15, fy, fx + 19, fy + 20, 3, PAPER)
    cv.line(fx, fy + 8, fx + 34, fy + 12, 3, PAPER)
    cv.line(fx, fy, fx + 34, fy + 20, 1.2, RED)
    cv.line(fx + 34, fy, fx, fy + 20, 1.2, RED)
    # EU flag
    ex, ey = x + w - 52, y + 12
    cv.rect(ex, ey, ex + 34, ey + 20, hx("#1a3a8c"))
    for i in range(8):
        a = math.radians(i * 45)
        cv.disc(ex + 17 + 8 * math.cos(a), ey + 10 + 6.5 * math.sin(a), 1.3, hx("#ffd23c"))
    # handshake: two hands meeting
    cv.disc(x + w * 0.5 - 8, y + h - 34, 6, hx("#d8a878"))
    cv.disc(x + w * 0.5 + 8, y + h - 34, 6, hx("#b88858"))
    cv.rect(x + w * 0.5 - 14, y + h - 40, x + w * 0.5 + 14, y + h - 28, hx("#d8a878"))


def scene_iran(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#2a2a44"), hx("#5a3a44"))
    # dark city, few lit windows
    for i, (bx, bw, bh) in enumerate([(x + 6, 34, 40), (x + 46, 28, 52), (x + 80, 36, 34),
                                      (x + 122, 30, 46), (x + 156, 26, 30)]):
        building(cv, bx, y + h - 6 - bh, bw, bh, hx("#1a1a28"), hx("#ffd97a"), lit=0.25)
    # lightning bolt
    cv.poly([(x + w * 0.52, y + 8), (x + w * 0.44, y + 30), (x + w * 0.5, y + 30),
             (x + w * 0.42, y + 52), (x + w * 0.56, y + 26), (x + w * 0.5, y + 26)],
            hx("#ffd23c"))
    # clock "2h"
    cv.disc(x + w - 26, y + 16, 11, PAPER)
    cv.ring(x + w - 26, y + 16, 11, 9, INK)
    draw_text(cv, "2h", x + w - 26, y + 10, 10, INK, align="center")
    star(cv, x + 16, y + 12, 1.1)
    star(cv, x + w - 60, y + 8, 1.1)


def scene_bolsonaro(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#d8e8f2"), hx("#f2e7c9"))
    cv.rect(x + 12, y + 16, x + w - 12, y + h - 8, hx("#f2f2f2"))
    cv.rect(x + 12, y + 16, x + w - 12, y + 22, hx("#c8d8e8"))
    # red cross
    cx, cy = x + w * 0.5, y + 36
    cv.rect(cx - 12, cy - 4, cx + 12, cy + 4, RED)
    cv.rect(cx - 4, cy - 12, cx + 4, cy + 12, RED)
    # windows
    for wy in (y + 48, y + 60):
        for wx in range(int(x + 22), int(x + w - 22), 16):
            cv.rect(wx, wy, wx + 8, wy + 6, hx("#9ab8d8"))
    # bed + patient
    cv.rect(x + 22, y + h - 16, x + 62, y + h - 10, hx("#8a8a92"))
    cv.rect(x + 22, y + h - 22, x + 62, y + h - 16, PAPER)
    cv.disc(x + 28, y + h - 24, 3.5, hx("#d8a878"))
    person(cv, x + w - 30, y + h - 8, 2.6, hx("#2a6b3c"))


def scene_fire(cv, x, y, w, h):
    sky(cv, x, y, w, h, hx("#3a2a3c"), hx("#8a3a2a"))
    # factory
    cv.rect(x + 10, y + 30, x + w - 60, y + h - 8, hx("#5a4a42"))
    cv.rect(x + 10, y + 30, x + w - 60, y + 36, hx("#3a2e28"))
    for wx in range(int(x + 18), int(x + w - 68), 14):
        cv.rect(wx, y + 44, wx + 7, y + 52, hx("#ffd97a"))
    cv.rect(x + w - 56, y + 18, x + w - 46, y + h - 8, hx("#4a3a32"))
    smoke(cv, x + w - 51, y + 10, 2.0, hx("#9a9aa2"))
    # flames
    for i, (fx, fs) in enumerate([(x + 30, 1.0), (x + 58, 1.3), (x + 88, 1.0), (x + 118, 0.8)]):
        cv.poly([(fx - 10 * fs, y + h - 8), (fx, y + h - 34 * fs), (fx + 10 * fs, y + h - 8)],
                hx("#ff7a2a"))
        cv.poly([(fx - 5 * fs, y + h - 8), (fx, y + h - 22 * fs), (fx + 5 * fs, y + h - 8)],
                hx("#ffd23c"))
    # fire truck
    cv.rect(x + w - 52, y + h - 20, x + w - 8, y + h - 8, RED)
    cv.disc(x + w - 42, y + h - 6, 3.5, INK)
    cv.disc(x + w - 16, y + h - 6, 3.5, INK)


SCENES = [scene_cop31, scene_kyiv, scene_manama, scene_icj, scene_hk,
          scene_cricket, scene_f1, scene_nba, scene_dpr, scene_ukeu,
          scene_iran, scene_bolsonaro, scene_fire]


# -------------------------------------------------------------- map ----
# Rough continent outlines in a 0..100 x 0..50 grid (equirectangular).
CONTINENTS = [
    [(4, 8), (10, 4), (20, 3), (28, 6), (30, 10), (26, 14), (22, 18), (18, 22),
     (14, 20), (10, 16), (6, 12)],
    [(26, 28), (30, 26), (34, 28), (33, 36), (29, 44), (26, 38), (24, 32)],
    [(46, 6), (52, 4), (56, 7), (54, 11), (50, 13), (46, 11)],
    [(46, 20), (54, 18), (58, 22), (56, 30), (52, 36), (48, 32), (45, 26)],
    [(58, 4), (75, 3), (90, 5), (96, 9), (92, 14), (86, 18), (80, 20), (74, 24),
     (68, 22), (62, 18), (58, 14), (56, 10)],
    [(82, 32), (90, 30), (94, 33), (90, 38), (84, 37)],
]
# Pin positions (grid coords) for stories 1..13.
PINS = {1: (50, 10), 2: (56, 7), 3: (60, 14), 4: (47, 8), 5: (84, 16),
        6: (91, 36), 7: (12, 15), 8: (16, 14), 9: (18, 12), 10: (48, 7),
        11: (62, 13), 12: (28, 34), 13: (80, 20)}


LABEL_OFF = {1: (-42, 22), 2: (-14, 26), 3: (16, 26), 4: (-58, 10),
             10: (38, 22), 11: (58, 8), 7: (-26, 18), 8: (2, 22), 9: (28, 16)}


def draw_map(cv, x, y, w, h):
    cv.rect(x, y, x + w, y + h, hx("#e8f0e8"))
    sx = w / 100.0
    sy = h / 50.0
    for poly in CONTINENTS:
        cv.poly([(x + px * sx, y + py * sy) for px, py in poly], hx("#b8c8a8"))
    for num, (gx, gy) in PINS.items():
        px = x + gx * sx
        py = y + gy * sy
        if num in LABEL_OFF:
            dx, dy = LABEL_OFF[num]
            lx, ly = px + dx, py + dy
            cv.line(px, py, lx, ly, 1, GREY)
            cv.disc(px, py, 2.5, RED)
            px, py = lx, ly
        cv.disc(px, py, 6, RED)
        draw_text(cv, str(num), px, py - 4.5, 8.5, PAPER, align="center")

# ---------------------------------------------------------------- data ----
LEADS = [
    dict(scene=scene_cop31, loc="ANTALYA, TURKIYE", cat="CLIMATE", badge="CONFIRMED",
         headline="COP31 ends with no deal",
         body="EU + 130 nations reject a text with no fossil-fuel mention; no deal.",
         source="UNFCCC / Reuters"),
    dict(scene=scene_kyiv, loc="KYIV REGION, UKRAINE", cat="WAR", badge="CONFIRMED",
         headline="Russia fires 186 drones at Ukraine",
         body="186 drones overnight; 161 downed. Dymer block hit: 2 dead, 14 missing.",
         source="Kyiv Post"),
    dict(scene=scene_manama, loc="MANAMA, BAHRAIN", cat="IRAN", badge="CLAIM",
         headline="Iran claims two US radars hit",
         body="IRGC claims two US radars hit; Bahrain says a civilian site burned.",
         source="CBS / Fars"),
]

SMALL = [
    dict(num=4, scene=scene_icj, loc="THE HAGUE", cat="WORLD COURT",
         headline="ICJ: Myanmar committed genocide",
         body="UN court rules Myanmar committed genocide.",
         source="Reuters / AP"),
    dict(num=5, scene=scene_hk, loc="HONG KONG", cat="ELECTION",
         headline="Record turnout in committee polls",
         body="98.79% turnout; 856 candidates, 723 seats.",
         source="SCMP"),
    dict(num=6, scene=scene_cricket, loc="WELLINGTON, NZ", cat="CRICKET",
         headline="India declare on a record 720/9",
         body="Rahul 136, Pant 128, Gill 98; NZ 368.",
         source="ESPNcricinfo"),
    dict(num=7, scene=scene_f1, loc="LAS VEGAS", cat="FORMULA 1",
         headline="Verstappen wins the Las Vegas GP",
         body="Verstappen beats Norris in Las Vegas.",
         source="F1 / AP"),
    dict(num=8, scene=scene_nba, loc="SAN ANTONIO, USA", cat="NBA",
         headline="Wembanyama scores 50 as Spurs roll on",
         body="50 pts, 19 rebounds, 5 blocks; 114-91.",
         source="NBA / AP"),
    dict(num=9, scene=scene_dpr, loc="WASHINGTON, USA", cat="POLITICS",
         headline="Democrats win biggest House majority",
         body="Biggest since 1992: at least 258 seats.",
         source="AP"),
    dict(num=10, scene=scene_ukeu, loc="LONDON", cat="EUROPE",
         headline="UK and EU strike post-Brexit deals",
         body="UK and EU agree post-Brexit trade deals.",
         source="AP / Reuters"),
    dict(num=11, scene=scene_iran, loc="TEHRAN, IRAN", cat="ENERGY",
         headline="Iran begins rationing electricity",
         body="Iran rations electricity, up to 2 hours a day.",
         source="Wires"),
    dict(num=12, scene=scene_bolsonaro, loc="BRASILIA, BRAZIL", cat="HEALTH",
         headline="Bolsonaro in intensive care",
         body="Bolsonaro in intensive care; stable.",
         source="Reuters"),
    dict(num=13, scene=scene_fire, loc="CIKANDE, INDONESIA", cat="FIRE",
         headline="Candy-factory fire in Cikande",
         body="3 dead and 36 missing in a Bantam factory fire.",
         source="Detiknews"),
]

ALSO = [
    (14, "Benghazi: Sea drones hit Russian warship (Wires)"),
    (15, "FBI probes apparent hack of its crime database (AP)"),
    (16, "Israeli fire kills four in Gaza (Gaza civil defence)"),
    (17, "Alcaraz wins first ATP Finals (ATP)"),
    (18, "Sparta II towed home after drone strike (Wires)"),
    (19, "Estonia shuts five Russia crossings 1 Dec (Reuters)"),
    (20, "Denmark expels Russian attache over plot (Guardian)"),
    (21, "Nepal PM Shah lands in Delhi on first visit (IANS)"),
    (22, "Chinese bomber turns back 170 km from Manila (AP)"),
    (23, "Philippines M5.9 quake off Palawan (EMSC)"),
    (24, "Japan: record 52% feel friendly to S. Korea (Ipsos)"),
    (25, "India and China hold fresh military talks (Wires)"),
    (26, "Somalia expels UAE ambassador, recalls envoy (Wires)"),
    (27, "Sudan: RSF accused of killing civilians (Claim)"),
    (28, "Kenya discharges its last Ebola patient (Wires)"),
    (29, "Drone strikes damage UN facility in Khartoum (Wires)"),
    (30, "Marles rejects US report on AUKUS subs (ABC)"),
    (31, "Melbourne marks 70 years since 1956 Olympics (ABC)"),
    (32, "Trump seeks 'permanent' Israel deal (Al Jazeera)"),
    (33, "EU and Indonesia sign trade deal after ten years (DW)"),
    (34, "Sudan army retakes ~30 towns in Kordofan (FT)"),
    (35, "Bangladesh: 30 Awami League homes burned (Local)"),
    (36, "Lebanon: Aoun demands Israel withdrawal (Al Jazeera)"),
    (37, "Whale genome sequenced from breath by drone (Wires)"),
    (38, "Saudi Arabia and Houthis exchange fire (Wires)"),
]

DATECHECK = [
    "400-drone barrage (19-20)",
    "148-drone night (20-21)",
    "'El Chapo Isidro' held (21)",
    "Bayelsa boat, 24 dead (21)",
    "Gaza aid-van strike (21)",
    "Nvidia SEC probe (20)",
    "Saudi strikes Hodeidah (20)",
    "Peru earthquake (20)",
    "Copa Sudamericana final (21)",
    "BepiColombo at Mercury (21)",
    "Missiles entered Poland (20)",
    "England beat NZ 37-12 (21)",
    "Arsenal 2-2, Leeds 4-1 (21)",
]

REGIONS = [
    ("EUROPE", 5, hx("#1a2b4a")), ("MIDDLE EAST", 5, hx("#a32c22")),
    ("NORTH AMERICA", 5, hx("#2a5a9a")), ("SOUTH AMERICA", 1, hx("#2a6b3c")),
    ("EAST ASIA", 3, hx("#b03a6e")), ("SOUTH ASIA", 4, hx("#c86a1a")),
    ("SOUTHEAST ASIA", 3, hx("#2b7a8c")), ("AFRICA", 6, hx("#6b4a2a")),
    ("OCEANIA", 2, hx("#5b3a7a")), ("WORLD", 4, hx("#4a4a4a")),
]

NUMBERS = [
    ("186", "DRONES FIRED"), ("161", "DOWNED"), ("258", "HOUSE SEATS"),
    ("$120bn", "ADAPTATION TARGET"), ("720/9", "INDIA'S RECORD TOTAL"),
    ("98.79%", "HK TURNOUT"),
]

BADGE_COL = {"CONFIRMED": hx("#2a6b3c"), "CLAIM": hx("#a32c22"),
             "REPORTED": hx("#6b6b66"), "PENDING": hx("#c9a227")}

MX = 12           # side margin
CW = W - 2 * MX   # content width = 1000


def fit_text(s, cap, max_w, min_cap=None, tracking=0.0):
    """Largest cap (<= cap) + tracking that fits max_w; returns (cap, tracking)."""
    c = cap
    while c > (min_cap or cap * 0.6) and text_width(s, c, tracking) > max_w:
        c -= 0.5
    tr = tracking
    while text_width(s, c, tr) > max_w and tr > -2.5:
        tr -= 0.25
    return c, tr


def draw_page(cv):
    y = 0
    # ---- header bar ----
    cv.rect(0, y, W, y + 22, NAVY)
    draw_text(cv, "THE WORLD IN ONE DAY", MX + 4, y + 5, 12, PAPER, tracking=0.5)
    draw_text(cv, "38 STORIES · 10 REGIONS · SUNDAY 22 NOVEMBER 2026",
              W - MX - 4, y + 5, 12, PAPER, align="right", tracking=0.5)
    y += 22
    # ---- title line 1 ----
    t1 = "Sunday 22 November 2026"
    c1, tr1 = fit_text(t1, 58, CW)
    draw_text(cv, t1, W / 2, y + 1, c1, INK, align="center", tracking=tr1)
    y += 76
    # ---- title line 2 (one line, as large as fits) ----
    t2 = "No Deal in Antalya, 186 Drones Over Kyiv, and Hong Kong's 98.79% Vote"
    c2, tr2 = fit_text(t2, 28, CW, min_cap=16)
    draw_text(cv, t2, W / 2, y + 1, c2, INK, align="center", tracking=tr2)
    y += int(c2) + 12
    # ---- subhead (italic red, one line) ----
    sh = "COP31 ends with no deal · 186 drones over Ukraine in the night · Iran's radar claim meets Bahrain's denial"
    c3, tr3 = fit_text(sh, 15, CW, min_cap=11)
    draw_text(cv, sh, W / 2, y + 1, c3, RED, align="center", tracking=tr3, italic=True)
    y += int(c3) + 5
    # ---- numbers strip ----
    bw = CW / 6.0
    for i, (val, lab) in enumerate(NUMBERS):
        bx = MX + i * bw
        cv.rect(bx + 2, y, bx + bw - 2, y + 45, hx("#fdfbf2"))
        cv.hline(bx + 2, bx + bw - 2, y, 1, RED)
        vc, vtr = fit_text(val, 36, bw - 12, min_cap=30)
        draw_text(cv, val, bx + bw / 2, y + 2, vc, RED, align="center", tracking=vtr)
        draw_text(cv, lab, bx + bw / 2, y + 37, 9, GREY, align="center", tracking=0.3)
    y += 45
    y += 2
    # ---- region tabs ----
    tw = CW / 10.0
    for i, (name, n, col) in enumerate(REGIONS):
        tx = MX + i * tw
        cv.rect(tx + 1, y, tx + tw - 1, y + 18, col)
        draw_text(cv, "%s %d" % (name, n), tx + tw / 2, y + 5, 8, PAPER,
                  align="center", tracking=0)
    y += 18
    y += 2
    # ---- timeline ----
    cv.rect(MX, y, MX + 108, y + 12, NAVY)
    draw_text(cv, "THE DAY IN UTC", MX + 54, y + 2, 9, PAPER, align="center", tracking=0.3)
    tl = ("01:00 HK polls open · 03:00 COP31 objections close · 05:11 Hamas seeks talks · "
          "05:30 Las Vegas GP ends · 06:00 Approval due · 07:30 Slips again")
    tl_cap, tl_tr = fit_text(tl, 9, W - MX - 122 - MX - 114, min_cap=7.5)
    if text_width(tl, tl_cap, tl_tr) > W - MX - 122 - MX - 114:
        tl = ("01:00 HK polls open · 03:00 COP31 objections close · "
              "05:30 Las Vegas GP ends · 06:00 Approval due · 07:30 Slips again")
        tl_cap, tl_tr = fit_text(tl, 9, W - MX - 122 - MX - 114, min_cap=7.5)
    draw_text(cv, tl, MX + 114, y + 2, tl_cap, INK, tracking=tl_tr)
    draw_text(cv, "PRESS TIME 09:45 UTC", W - MX, y + 2, 9, RED, align="right", tracking=0.3)
    y += 12
    y += 3
    # ---- 3 leads ----
    colw = (CW - 2 * 14) / 3.0
    hero_h = 120
    lead_top = y
    for i, ld in enumerate(LEADS):
        lx = MX + i * (colw + 14)
        ld["scene"](cv, lx + 8, y, colw - 16, hero_h)
        yy = y + hero_h + 3
        draw_text(cv, "%s · %s" % (ld["loc"], ld["cat"]), lx, yy, 11, RED, tracking=0.2)
        bw_txt = " %s " % ld["badge"]
        bwid = text_width(bw_txt, 9, 0.4) + 8
        cv.rect(lx + colw - bwid, yy - 1, lx + colw, yy + 11, BADGE_COL[ld["badge"]])
        draw_text(cv, ld["badge"], lx + colw - bwid / 2, yy + 1, 9, PAPER,
                  align="center", tracking=0.4)
        yy += 13
        yy = draw_para(cv, ld["headline"], lx, yy, 24, INK, colw, 25, max_lines=2)
        yy = draw_para(cv, ld["body"], lx, yy + 1, 12.5, INK, colw, 13, max_lines=2)
        draw_text(cv, ld["source"], lx, yy + 1, 10, GREY)
        ld["_bottom"] = yy + 10
    y = max(ld["_bottom"] for ld in LEADS)
    y += 2
    # ---- 10 small stories, 5 x 2 ----
    scolw = (CW - 4 * 10) / 5.0
    thumb_h = 70
    row_tops = []
    for row in range(2):
        row_tops.append(y)
        for col in range(5):
            st = SMALL[row * 5 + col]
            sx = MX + col * (scolw + 10)
            st["scene"](cv, sx + 1, y, scolw - 2, thumb_h)
            yy = y + thumb_h + 2
            draw_text(cv, "%d  %s · %s" % (st["num"], st["loc"], st["cat"]),
                      sx, yy, 9.5, RED, tracking=0.1)
            yy += 10
            yy = draw_para(cv, st["headline"], sx, yy, 12.5, INK, scolw, 13,
                           max_lines=2)
            yy = draw_para(cv, st["body"], sx, yy + 1, 11.5, INK, scolw, 12,
                           max_lines=2)
            draw_text(cv, st["source"], sx, yy + 1, 9, GREY)
            st["_bottom"] = yy + 8
        y = max(SMALL[row * 5 + c]["_bottom"] for c in range(5))
        y += 3
    # ---- ALSO list ----
    draw_text(cv, "ALSO ON SUNDAY 22 NOVEMBER — 25 MORE STORIES", MX, y, 13, NAVY,
              tracking=0.3)
    y += 15
    colw2 = (CW - 16) / 2.0
    for i, (num, txt) in enumerate(ALSO):
        ax = MX + (i // 13) * (colw2 + 16)
        ay = y + (i % 13) * 10
        draw_text(cv, "%d. %s" % (num, txt), ax, ay, 10, INK)
    y += 13 * 10
    # ---- map + DATE CHECK row ----
    map_w = 580
    dc_x = MX + map_w + 16
    dc_w = W - MX - dc_x
    row_h = 110
    draw_text(cv, "WHERE IT HAPPENED", MX, y, 12, NAVY, tracking=0.3)
    draw_map(cv, MX, y + 15, map_w, row_h - 15)
    cv.rect(dc_x, y, dc_x + dc_w, y + row_h, hx("#fdf6f0"))
    # red border (4 thin rects)
    cv.rect(dc_x, y, dc_x + dc_w, y + 1.5, RED)
    cv.rect(dc_x, y + row_h - 1.5, dc_x + dc_w, y + row_h, RED)
    cv.rect(dc_x, y, dc_x + 1.5, y + row_h, RED)
    cv.rect(dc_x + dc_w - 1.5, y, dc_x + dc_w, y + row_h, RED)
    draw_text(cv, "DATE CHECK — NOT 22 NOVEMBER", dc_x + 8, y + 4, 10, RED,
              tracking=0.2)
    dc_colw = (dc_w - 16) / 2.0
    for i, item in enumerate(DATECHECK):
        ix = dc_x + 8 + (i // 7) * dc_colw
        iy = y + 18 + (i % 7) * 11
        draw_text(cv, "· " + item, ix, iy, 8.5, INK)
    y += row_h
    # ---- footer ----
    cv.hline(MX, W - MX, y, 1, INK)
    y += 3
    draw_text(cv, "Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, UNFCCC, "
                  "Kyiv Post, SCMP, ESPNcricinfo, Detiknews",
              MX, y, 9, GREY)
    y += 10
    draw_text(cv, "CONFIRMED = verified by several sources · CLAIM = single-source claim · "
                  "Scenes are drawn illustrations · Wires read to press time 09:45 UTC",
              MX, y, 9, GREY)
    y += 10
    return y


def main():
    import time
    t0 = time.time()
    cv = Canvas(W, H, "#f7f3e8")
    bottom = draw_page(cv)
    print("page bottom y =", bottom, "of", H)
    print("title L1 cap/track:", fit_text("Sunday 22 November 2026", 58, CW))
    print("title L2 cap/track:", fit_text(
        "No Deal in Antalya, 186 Drones Over Kyiv, and Hong Kong's 98.79% Vote", 28, CW, min_cap=16))
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    data = png_bytes(cv.px, W, H)
    with open(os.path.join(outdir, "entry.png"), "wb") as f:
        f.write(data)
    print("wrote", os.path.join(outdir, "entry.png"), len(data), "bytes in %.1fs"
          % (time.time() - t0))


if __name__ == "__main__":
    main()
