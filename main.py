#!/usr/bin/env python3
"""makefun news-image-20261122 v3 — "Sunday 22 November 2026".

Draws the whole front page itself (rasterizer + PNG encoder + a hand-made
bold serif font) with the Python 3.13 standard library only, no network.
Deterministic: two runs write byte-identical files.

Layout (1024x1024, cream newspaper front page):
  navy header bar | 2-line title | red italic subhead | numbers strip |
  10 region tabs | UTC timeline + PRESS TIME 09:45 UTC | 3 lead stories |
  15 small illustrated stories (5x3) | ALSO 19-38 | world map + DATE CHECK |
  footer sources + certainty legend.
38 stories, 10 regions, 13 DATE CHECK items. All facts hardcoded from the
verified spec; no new facts are invented.
"""

import os
import struct
import zlib

W = H = 1024

# ---------------------------------------------------------------- canvas ---
buf = bytearray(W * H * 3)

PAPER = (247, 243, 232)
INK = (26, 26, 26)
NAVY = (26, 43, 74)
RED = (178, 34, 34)
DRED = (140, 20, 20)
GRAY = (90, 86, 78)
LGRAY = (210, 205, 190)


def _clip(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def fill_rect(x, y, w, h, c):
    x0 = max(0, int(x)); y0 = max(0, int(y))
    x1 = min(W, int(x + w)); y1 = min(H, int(y + h))
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(c) * (x1 - x0)
    for yy in range(y0, y1):
        i = (yy * W + x0) * 3
        buf[i:i + (x1 - x0) * 3] = row


def vgrad(x, y, w, h, c0, c1):
    """Vertical gradient rectangle."""
    x0 = max(0, int(x)); y0 = max(0, int(y))
    x1 = min(W, int(x + w)); y1 = min(H, int(y + h))
    if x1 <= x0 or y1 <= y0 or h <= 0:
        return
    for yy in range(y0, y1):
        t = (yy - y) / max(1.0, h - 1)
        c = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
        i = (yy * W + x0) * 3
        buf[i:i + (x1 - x0) * 3] = bytes(c) * (x1 - x0)


def hgrad(x, y, w, h, c0, c1):
    x0 = max(0, int(x)); y0 = max(0, int(y))
    x1 = min(W, int(x + w)); y1 = min(H, int(y + h))
    if x1 <= x0 or y1 <= y0 or w <= 0:
        return
    for xx in range(x0, x1):
        t = (xx - x) / max(1.0, w - 1)
        c = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
        for yy in range(y0, y1):
            i = (yy * W + xx) * 3
            buf[i:i + 3] = bytes(c)


def _scanline_fill(cx, cy, rx, ry, c, rows):
    """Fill an ellipse given as (cy -> half-width) rows. rows: dict y->(x0,x1)."""
    for yy, (x0, x1) in rows.items():
        if 0 <= yy < H:
            a = max(0, int(x0)); b = min(W, int(x1))
            if b > a:
                i = (yy * W + a) * 3
                buf[i:i + (b - a) * 3] = bytes(c) * (b - a)


def ellipse(cx, cy, rx, ry, c):
    """Filled ellipse."""
    if rx <= 0 or ry <= 0:
        return
    rows = {}
    for yy in range(int(cy - ry), int(cy + ry) + 1):
        dy = (yy - cy) / ry
        if abs(dy) > 1:
            continue
        dx = rx * (1 - dy * dy) ** 0.5
        rows[yy] = (cx - dx, cx + dx + 1)
    _scanline_fill(cx, cy, rx, ry, c, rows)


def circle(cx, cy, r, c):
    ellipse(cx, cy, r, r, c)


def ring(cx, cy, r0, r1, c, bg):
    """Ring: outer circle r1 in c, inner circle r0 in bg."""
    circle(cx, cy, r1, c)
    circle(cx, cy, r0, bg)


def poly(pts, c):
    """Filled polygon (even-odd scanline). pts: list of (x, y)."""
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0 = max(0, int(min(ys))); y1 = min(H - 1, int(max(ys)) + 1)
    n = len(pts)
    for yy in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = pts[i]
            x2, y2p = pts[(i + 1) % n]
            if (y1p <= yy < y2p) or (y2p <= yy < y1p):
                t = (yy - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            a = max(0, int(xs[k])); b = min(W, int(xs[k + 1]) + 1)
            if b > a:
                i = (yy * W + a) * 3
                buf[i:i + (b - a) * 3] = bytes(c) * (b - a)


def line(x0, y0, x1, y1, c, w=1):
    """Thick line as a chain of small discs."""
    dx = x1 - x0; dy = y1 - y0
    steps = max(1, int((abs(dx) + abs(dy)) / 1.5) + 1)
    r = w / 2.0
    for s in range(steps + 1):
        t = s / steps
        ellipse(x0 + dx * t, y0 + dy * t, r, r, c)


def hline(x, y, w, c, h=1):
    fill_rect(x, y, w, h, c)


# ------------------------------------------------------------ PNG encoder ---
def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def _raw_rows(filt):
    rows = []
    prev = bytearray(W * 3)
    for yy in range(H):
        row = bytes(buf[yy * W * 3:(yy + 1) * W * 3])
        if filt == 0:
            rows.append(b"\x00" + row)
        else:  # Sub filter
            d = bytearray(W * 3)
            for i in range(3):
                d[i] = row[i]
            for i in range(3, W * 3):
                d[i] = (row[i] - row[i - 3]) & 0xFF
            rows.append(b"\x01" + bytes(d))
        prev = row
    return b"".join(rows)


def write_png(path):
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    best = None
    for filt in (0, 1):
        raw = _raw_rows(filt)
        comp = zlib.compress(raw, 9)
        if best is None or len(comp) < len(best):
            best = comp
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", best)
    png += _chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------- bold serif font ----
# Hand-drawn glyphs on a 100-unit em: baseline y=0, cap height 70,
# x-height 50, descender -22. Strokes are THICK and SOLID (bold newspaper
# serif): vertical stems 15-16 units (~1/4.4 of cap height), horizontal
# strokes 10-12 units. Letters are solid fills; counters are clean holes
# cut out of the solid shape. Never outlines.
#
# Shape tuples:
#   ('R', x0,y0,x1,y1)        filled rect
#   ('X', x0,y0,x1,y1)        cut rect (counter)
#   ('E', cx,cy,rx,ry)        filled ellipse
#   ('Y', cx,cy,rx,ry)        cut ellipse
#   ('P', [(x,y),...])        filled polygon
#   ('Q', [(x,y),...])        cut polygon
#   ('S', x0,y0,x1,y1,top,bot) vertical stem with serif slabs at top/bot
#
# Each glyph: (advance, [shapes]).

def R(x0, y0, x1, y1):
    return ('R', x0, y0, x1, y1)


def XR(x0, y0, x1, y1):
    return ('X', x0, y0, x1, y1)


def E(cx, cy, rx, ry):
    return ('E', cx, cy, rx, ry)


def XE(cx, cy, rx, ry):
    return ('Y', cx, cy, rx, ry)


def P(pts):
    return ('P', pts)


def Q(pts):
    return ('Q', pts)


def S(x0, y0, x1, y1, top=0, bot=0):
    return ('S', x0, y0, x1, y1, top, bot)


GLYPH = {}

# --- capitals ---
GLYPH['A'] = (72, [P([(26, 70), (42, 70), (16, 0), (0, 0)]),
                  P([(30, 70), (46, 70), (72, 0), (56, 0)]),
                  R(14, 24, 58, 34), Q([(36, 58), (22, 34), (50, 34)])])
GLYPH['B'] = (66, [S(8, 0, 24, 70, 1, 1),
                   E(38, 52, 25, 18), XE(38, 52, 12, 9),
                   E(40, 18, 27, 19), XE(40, 18, 13, 10)])
GLYPH['C'] = (68, [E(35, 35, 30, 35), XE(35, 35, 18, 25), XR(34, 26, 70, 44)])
GLYPH['D'] = (70, [S(8, 0, 24, 70, 1, 1),
                   E(34, 35, 28, 35), XE(34, 35, 16, 25), XR(0, 0, 8, 70)])
GLYPH['E'] = (62, [S(8, 0, 24, 70, 1, 1),
                   R(8, 59, 60, 70), R(8, 29, 52, 40), R(8, 0, 60, 11)])
GLYPH['F'] = (58, [S(8, 0, 24, 70, 1, 0), R(8, 59, 58, 70), R(8, 29, 50, 40)])
GLYPH['G'] = (70, [E(35, 35, 30, 35), XE(35, 35, 18, 25), XR(36, 26, 70, 44),
                   R(38, 26, 64, 36), R(54, 0, 64, 36)])
GLYPH['H'] = (72, [S(8, 0, 24, 70, 1, 1), S(48, 0, 64, 70, 1, 1),
                   R(24, 29, 48, 41)])
GLYPH['I'] = (34, [S(11, 0, 23, 70, 0, 0), R(4, 64, 30, 70), R(4, 0, 30, 6)])
GLYPH['J'] = (56, [E(32, 16, 24, 16), XE(32, 16, 13, 8),
                   XR(32, 0, 70, 70), XR(0, 16, 70, 70), R(28, 0, 50, 10),
                   S(36, 14, 50, 70, 0, 0), R(28, 64, 56, 70)])
GLYPH['K'] = (68, [S(8, 0, 24, 70, 1, 1), R(22, 26, 40, 40),
                   P([(24, 34), (36, 42), (64, 70), (52, 70)]),
                   P([(34, 32), (46, 28), (66, 0), (54, 0)])])
GLYPH['L'] = (60, [S(8, 0, 24, 70, 1, 1), R(8, 0, 58, 11)])
GLYPH['M'] = (84, [S(6, 0, 20, 70, 1, 1), S(64, 0, 78, 70, 1, 1),
                   P([(18, 70), (28, 70), (42, 26), (34, 22)]),
                   P([(56, 70), (66, 70), (50, 22), (42, 26)])])
GLYPH['N'] = (74, [S(8, 0, 24, 70, 1, 1), S(50, 0, 66, 70, 1, 1),
                   P([(22, 70), (34, 70), (54, 0), (42, 0)])])
GLYPH['O'] = (72, [E(36, 35, 30, 35), XE(36, 35, 17, 24)])
GLYPH['P'] = (64, [S(8, 0, 24, 70, 1, 1), E(38, 52, 25, 19), XE(38, 52, 12, 9)])
GLYPH['Q'] = (74, [E(36, 35, 30, 35), XE(36, 35, 17, 24),
                   P([(48, 10), (58, 16), (70, -4), (60, -8)])])
GLYPH['R'] = (66, [S(8, 0, 24, 70, 1, 1), E(38, 52, 25, 19), XE(38, 52, 12, 9),
                   R(22, 26, 40, 40), P([(34, 32), (46, 28), (66, 0), (54, 0)])])
GLYPH['S'] = (64, [E(33, 17, 26, 17), XE(33, 17, 14, 8), XR(7, 17, 59, 34),
                   E(33, 53, 26, 17), XE(33, 53, 14, 8), XR(7, 36, 59, 53),
                   P([(4, 50), (16, 56), (62, 20), (50, 14)])])
GLYPH['T'] = (64, [R(4, 59, 60, 70), S(26, 0, 38, 70, 0, 1)])
GLYPH['U'] = (72, [E(36, 16, 28, 16), XE(36, 16, 15, 8), XR(0, 16, 70, 70),
                   S(8, 14, 24, 70, 1, 0), S(48, 14, 64, 70, 1, 0)])
GLYPH['V'] = (70, [P([(4, 70), (18, 70), (36, 0), (24, 0)]),
                   P([(34, 0), (46, 0), (66, 70), (52, 70)])])
GLYPH['W'] = (94, [P([(2, 70), (14, 70), (28, 0), (18, 0)]),
                   P([(22, 0), (32, 0), (48, 36), (40, 34)]),
                   P([(40, 34), (48, 36), (68, 0), (58, 0)]),
                   P([(58, 0), (68, 0), (92, 70), (80, 70)])])
GLYPH['X'] = (68, [P([(6, 70), (18, 70), (62, 0), (50, 0)]),
                   P([(50, 70), (62, 70), (18, 0), (6, 0)])])
GLYPH['Y'] = (66, [P([(4, 70), (16, 70), (30, 28), (22, 24)]),
                   P([(50, 70), (62, 70), (36, 24), (30, 28)]),
                   S(27, 0, 39, 30, 0, 1)])
GLYPH['Z'] = (64, [R(6, 59, 58, 70), P([(50, 70), (58, 70), (14, 0), (6, 0)]),
                   R(6, 0, 58, 11)])
GLYPH['Ü'] = (72, [E(36, 16, 28, 16), XE(36, 16, 15, 8), XR(0, 16, 70, 70),
                   S(8, 14, 24, 70, 1, 0), S(48, 14, 64, 70, 1, 0),
                   E(20, 76, 5, 5), E(44, 76, 5, 5)])

# --- digits ---
GLYPH['0'] = (60, [E(30, 35, 26, 35), XE(30, 35, 14, 25)])
GLYPH['1'] = (46, [S(24, 0, 38, 70, 0, 0), P([(12, 44), (24, 70), (38, 70), (38, 54)]),
                   R(12, 0, 46, 7)])
GLYPH['2'] = (60, [E(30, 53, 25, 17), XE(30, 53, 13, 8), XR(0, 0, 62, 53),
                   P([(48, 52), (58, 46), (16, 4), (8, 10)]), R(6, 0, 56, 10)])
GLYPH['3'] = (60, [E(32, 52, 24, 18), XE(32, 52, 12, 9), XR(0, 0, 26, 70),
                   E(32, 18, 26, 18), XE(32, 18, 13, 9), XR(0, 0, 26, 70),
                   R(22, 30, 48, 40)])
GLYPH['4'] = (62, [P([(8, 14), (18, 22), (54, 70), (44, 70)]),
                   S(44, 0, 58, 70, 0, 0), R(6, 16, 58, 26)])
GLYPH['5'] = (60, [E(33, 17, 25, 17), XE(33, 17, 13, 8), XR(0, 17, 70, 70),
                   R(8, 60, 56, 70), S(8, 34, 22, 70, 0, 0), R(8, 14, 22, 36)])
GLYPH['6'] = (60, [E(30, 52, 23, 16), XE(30, 52, 12, 8), XR(30, 0, 70, 70),
                   E(30, 18, 25, 18), XE(30, 18, 13, 9), S(7, 32, 21, 72, 0, 0)])
GLYPH['7'] = (60, [R(6, 60, 56, 70), P([(46, 70), (58, 70), (24, 0), (12, 0)])])
GLYPH['8'] = (60, [E(30, 52, 23, 18), XE(30, 52, 11, 9),
                   E(30, 18, 25, 19), XE(30, 18, 12, 9)])
GLYPH['9'] = (60, [E(30, 18, 23, 16), XE(30, 18, 12, 8), XR(0, 18, 70, 70),
                   XR(0, 0, 30, 70),
                   E(30, 52, 25, 18), XE(30, 52, 13, 9), S(39, 0, 53, 38, 0, 0)])

# --- lowercase ---
GLYPH['a'] = (58, [E(29, 25, 23, 25), XE(29, 25, 11, 14), S(42, 0, 56, 50, 0, 1)])
GLYPH['b'] = (58, [S(8, 0, 22, 70, 0, 1), E(35, 25, 23, 25), XE(35, 25, 11, 14)])
GLYPH['c'] = (54, [E(28, 25, 24, 25), XE(28, 25, 13, 15), XR(28, 18, 56, 32)])
GLYPH['d'] = (58, [E(28, 25, 23, 25), XE(28, 25, 11, 14), S(42, 0, 56, 70, 0, 1)])
GLYPH['e'] = (56, [E(29, 25, 24, 25), R(6, 26, 52, 34), XE(28, 14, 11, 8),
                   XR(36, 34, 58, 52)])
GLYPH['f'] = (40, [E(27, 60, 14, 11), XE(27, 60, 6, 5),
                   XR(0, 0, 27, 70), XR(0, 0, 70, 60),
                   S(20, 0, 34, 70, 0, 1), R(6, 42, 38, 50)])
GLYPH['g'] = (58, [E(34, -12, 20, 11), XE(34, -12, 11, 5), XR(0, -12, 70, 0),
                   E(29, 25, 23, 25), XE(29, 25, 11, 14), S(42, -20, 56, 50, 0, 0)])
GLYPH['h'] = (58, [E(35, 25, 21, 25), XE(35, 25, 10, 15), XR(0, 0, 70, 25),
                   S(8, 0, 22, 70, 0, 1), S(46, 0, 58, 50, 0, 1)])
GLYPH['i'] = (30, [S(11, 0, 23, 50, 0, 1), E(17, 62, 6, 6)])
GLYPH['j'] = (32, [E(16, -12, 16, 10), XE(16, -12, 8, 5),
                   XR(0, -12, 70, 0), XR(16, -30, 70, 10),
                   S(12, -18, 24, 50, 0, 0), E(18, 62, 6, 6)])
GLYPH['k'] = (56, [S(8, 0, 22, 50, 0, 1), R(20, 24, 36, 34),
                   P([(22, 26), (30, 32), (50, 50), (42, 50)]),
                   P([(30, 26), (38, 22), (54, 0), (44, 0)])])
GLYPH['l'] = (32, [S(12, 0, 24, 70, 0, 1)])
GLYPH['m'] = (86, [E(30, 25, 17, 25), XE(30, 25, 8, 15), XR(0, 0, 70, 25),
                   E(60, 25, 17, 25), XE(60, 25, 8, 15), XR(0, 0, 70, 25),
                   S(6, 0, 20, 50, 0, 1), S(38, 0, 50, 50, 0, 1), S(68, 0, 80, 50, 0, 1)])
GLYPH['n'] = (58, [E(35, 25, 21, 25), XE(35, 25, 10, 15), XR(0, 0, 70, 25),
                   S(8, 0, 22, 50, 0, 1), S(46, 0, 58, 50, 0, 1)])
GLYPH['o'] = (56, [E(28, 25, 24, 25), XE(28, 25, 12, 14)])
GLYPH['p'] = (58, [S(8, -20, 22, 50, 0, 0), E(35, 25, 23, 25), XE(35, 25, 11, 14)])
GLYPH['q'] = (58, [E(28, 25, 23, 25), XE(28, 25, 11, 14), S(42, -20, 56, 50, 0, 0)])
GLYPH['r'] = (40, [P([(22, 50), (30, 50), (46, 42), (44, 34), (28, 38)]),
                   S(8, 0, 22, 50, 0, 1)])
GLYPH['s'] = (52, [E(27, 13, 21, 13), XE(27, 13, 10, 6), XR(6, 13, 48, 26),
                   E(27, 37, 21, 13), XE(27, 37, 10, 6), XR(6, 24, 48, 37),
                   P([(8, 34), (16, 40), (46, 16), (38, 12)])])
GLYPH['t'] = (38, [S(14, 0, 26, 62, 0, 1), R(4, 42, 36, 50)])
GLYPH['u'] = (58, [E(29, 16, 21, 16), XE(29, 16, 10, 8), XR(0, 16, 70, 70),
                   S(8, 14, 22, 50, 1, 0), S(36, 14, 50, 50, 1, 0)])
GLYPH['v'] = (56, [P([(4, 50), (16, 50), (30, 0), (20, 0)]),
                   P([(26, 0), (36, 0), (52, 50), (40, 50)])])
GLYPH['w'] = (80, [P([(2, 50), (12, 50), (24, 0), (16, 0)]),
                   P([(20, 0), (28, 0), (40, 34), (34, 34)]),
                   P([(34, 34), (40, 34), (52, 0), (44, 0)]),
                   P([(48, 0), (56, 0), (78, 50), (68, 50)])])
GLYPH['x'] = (54, [P([(6, 50), (16, 50), (48, 0), (38, 0)]),
                   P([(38, 50), (48, 50), (16, 0), (6, 0)])])
GLYPH['y'] = (56, [P([(4, 50), (14, 50), (28, 6), (20, 2)]),
                   P([(28, 4), (38, 0), (50, 50), (40, 50)]),
                   P([(26, 4), (36, 0), (34, -20), (24, -20)])])
GLYPH['z'] = (52, [R(6, 40, 50, 50), P([(44, 50), (52, 50), (12, 0), (4, 0)]),
                   R(6, 0, 50, 10)])
GLYPH['ü'] = (58, [E(29, 16, 21, 16), XE(29, 16, 10, 8), XR(0, 16, 70, 70),
                   S(8, 14, 22, 50, 1, 0), S(36, 14, 50, 50, 1, 0),
                   E(20, 60, 5, 5), E(38, 60, 5, 5)])

# --- punctuation ---
GLYPH['.'] = (28, [E(14, 5, 6, 6)])
GLYPH[','] = (28, [E(14, 5, 6, 6), P([(14, 6), (20, 6), (16, -12), (10, -12)])])
GLYPH[':'] = (28, [E(14, 36, 6, 6), E(14, 10, 6, 6)])
GLYPH[';'] = (28, [E(14, 36, 6, 6), E(14, 5, 6, 6),
                   P([(14, 6), (20, 6), (16, -12), (10, -12)])])
GLYPH['!'] = (32, [S(13, 22, 21, 70, 0, 0), E(17, 6, 6, 6)])
GLYPH['?'] = (56, [E(28, 52, 20, 16), XE(28, 52, 10, 8), XR(0, 0, 70, 52),
                   S(38, 28, 50, 52, 0, 0), P([(38, 28), (48, 28), (34, 12), (26, 16)]),
                   E(30, 5, 6, 6)])
GLYPH['-'] = (40, [R(6, 28, 34, 36)])
GLYPH['–'] = (52, [R(4, 28, 48, 36)])
GLYPH['—'] = (64, [R(2, 28, 62, 36)])
GLYPH['('] = (34, [E(30, 35, 18, 35), XE(30, 35, 10, 28), XR(30, 0, 70, 70)])
GLYPH[')'] = (34, [E(4, 35, 18, 35), XE(4, 35, 10, 28), XR(0, 0, 4, 70)])
GLYPH['%'] = (78, [E(20, 52, 12, 12), XE(20, 52, 6, 6),
                   E(58, 16, 12, 12), XE(58, 16, 6, 6),
                   P([(52, 66), (60, 66), (18, 4), (10, 4)])])
GLYPH['$'] = (60, [E(30, 17, 22, 16), XE(30, 17, 11, 8), XR(8, 17, 52, 33),
                   E(30, 53, 22, 16), XE(30, 53, 11, 8), XR(8, 37, 52, 53),
                   P([(10, 50), (18, 54), (50, 20), (42, 16)]), S(26, -4, 34, 74, 0, 0)])
GLYPH['/'] = (44, [P([(30, 70), (40, 70), (14, 0), (4, 0)])])
GLYPH['·'] = (28, [E(14, 38, 5, 5)])
GLYPH['+'] = (56, [R(6, 28, 50, 38), R(23, 11, 33, 55)])
GLYPH['='] = (56, [R(6, 42, 50, 50), R(6, 20, 50, 28)])
GLYPH['°'] = (32, [E(16, 60, 9, 9), XE(16, 60, 4, 4)])
GLYPH["'"] = (26, [P([(12, 70), (20, 70), (14, 52), (8, 54)])])
GLYPH['"'] = (44, [P([(8, 70), (16, 70), (10, 52), (4, 54)]),
                   P([(28, 70), (36, 70), (30, 52), (24, 54)])])
GLYPH['•'] = (28, [E(14, 32, 8, 8)])
GLYPH['_'] = (56, [R(4, -2, 52, 4)])
GLYPH[' '] = (30, [])

# ------------------------------------------------- glyph rasterizer (3x) ----
# Unit space: baseline y=0 (up positive), cap 70, top margin 78, bottom -26.
# Supersampled mask -> 3x3 average -> coverage bytes 0..255.
_GLYPH_CACHE = {}


def _shape_polys(shape, slant):
    """One shape -> list of (points, cut). Points in unit space, y up."""
    kind = shape[0]
    out = []

    def shear(pts):
        if slant == 0:
            return pts
        return [(x + slant * (74.0 - y), y) for (x, y) in pts]

    if kind == 'R':
        _, x0, y0, x1, y1 = shape
        out.append((shear([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), False))
    elif kind == 'X':
        _, x0, y0, x1, y1 = shape
        out.append((shear([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), True))
    elif kind in ('E', 'Y'):
        _, cx, cy, rx, ry = shape
        pts = []
        n = 40
        for i in range(n):
            import math as _m
            a = 2 * _m.pi * i / n
            pts.append((cx + rx * _m.cos(a), cy + ry * _m.sin(a)))
        out.append((shear(pts), kind == 'Y'))
    elif kind in ('P', 'Q'):
        out.append((shear(list(shape[1])), kind == 'Q'))
    elif kind == 'S':
        _, x0, y0, x1, y1, top, bot = shape
        out.append((shear([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]), False))
        if top:
            out.append((shear([(x0 - 3.5, y1), (x1 + 3.5, y1),
                               (x1, y1 - 4.5), (x0, y1 - 4.5)]), False))
        if bot:
            out.append((shear([(x0 - 3.5, y0), (x1 + 3.5, y0),
                               (x1, y0 + 4.5), (x0, y0 + 4.5)]), False))
    return out


def _fill_poly_mask(mask, mw, mh, pts, k3, val):
    """Scanline-fill a polygon (unit coords, y up) into the supersampled mask."""
    # to supersampled pixel coords: px=(x+8)*k3, py=(78-y)*k3
    sp = [((x + 8.0) * k3, (78.0 - y) * k3) for (x, y) in pts]
    ys = [p[1] for p in sp]
    y0 = max(0, int(min(ys)))
    y1 = min(mh - 1, int(max(ys)) + 1)
    n = len(sp)
    for yy in range(y0, y1 + 1):
        xs = []
        for i in range(n):
            x1, y1p = sp[i]
            x2, y2p = sp[(i + 1) % n]
            if (y1p <= yy < y2p) or (y2p <= yy < y1p):
                t = (yy - y1p) / (y2p - y1p)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        base = yy * mw
        for k in range(0, len(xs) - 1, 2):
            a = max(0, int(xs[k]))
            b = min(mw, int(xs[k + 1]) + 1)
            for xx in range(a, b):
                mask[base + xx] = val


def render_glyph(ch, size, slant=0.0):
    """Return (cov bytes, w, h, top_px): coverage bitmap at 1x, top_px is the
    distance from the glyph bitmap top to the baseline, in px."""
    key = (ch, round(size * 2) / 2.0, round(slant, 2))
    got = _GLYPH_CACHE.get(key)
    if got is not None:
        return got
    adv, shapes = GLYPH.get(ch, GLYPH[' '])
    k = size / 70.0            # px per unit at 1x
    k3 = 3.0 * k               # px per unit at 3x
    out_w = max(1, int(round((adv + 16) * k)))
    out_h = max(1, int(round(104 * k)))
    mw, mh = out_w * 3, out_h * 3
    mask = bytearray(mw * mh)
    for shape in shapes:
        for pts, cut in _shape_polys(shape, slant):
            _fill_poly_mask(mask, mw, mh, pts, k3, 0 if cut else 1)
    # downsample 3x3 -> coverage 0..255
    cov = bytearray(out_w * out_h)
    for oy in range(out_h):
        r0 = mask[(oy * 3) * mw:(oy * 3 + 1) * mw]
        r1 = mask[(oy * 3 + 1) * mw:(oy * 3 + 2) * mw]
        r2 = mask[(oy * 3 + 2) * mw:(oy * 3 + 3) * mw]
        a0 = [r0[i] + r0[i + 1] + r0[i + 2] for i in range(0, mw - 2, 3)]
        a1 = [r1[i] + r1[i + 1] + r1[i + 2] for i in range(0, mw - 2, 3)]
        a2 = [r2[i] + r2[i + 1] + r2[i + 2] for i in range(0, mw - 2, 3)]
        row = bytes(((x + y + z) * 255 // 9) for x, y, z in zip(a0, a1, a2))
        cov[oy * out_w:(oy + 1) * out_w] = row[:out_w]
    top = 78.0 * k
    res = (bytes(cov), out_w, out_h, top)
    _GLYPH_CACHE[key] = res
    return res


def _blit(cov, w, h, x0, y0, color):
    x0 = int(round(x0)); y0 = int(round(y0))
    r0, g0, b0 = color
    for yy in range(h):
        cy = y0 + yy
        if cy < 0 or cy >= H:
            continue
        row = cov[yy * w:(yy + 1) * w]
        base = cy * W * 3
        for xx in range(w):
            a = row[xx]
            if a == 0:
                continue
            cx = x0 + xx
            if cx < 0 or cx >= W:
                continue
            i = base + cx * 3
            if a == 255:
                buf[i] = r0; buf[i + 1] = g0; buf[i + 2] = b0
            else:
                ia = 255 - a
                buf[i] = (r0 * a + buf[i] * ia) // 255
                buf[i + 1] = (g0 * a + buf[i + 1] * ia) // 255
                buf[i + 2] = (b0 * a + buf[i + 2] * ia) // 255


def text_width(s, size, slant=0.0, tracking=0.0):
    k = size / 70.0
    w = 0.0
    for ch in s:
        adv = GLYPH.get(ch, GLYPH[' '])[0]
        w += adv * k + tracking
    return w


def draw_text(x, y, s, size, color, align='left', slant=0.0, tracking=0.0):
    """Draw text; (x, y) is the baseline start (or centre/right per align)."""
    if align != 'left':
        w = text_width(s, size, slant, tracking)
        if align == 'center':
            x -= w / 2.0
        elif align == 'right':
            x -= w
    k = size / 70.0
    pen = x
    for ch in s:
        if ch == ' ':
            pen += GLYPH[' '][0] * k + tracking
            continue
        cov, gw, gh, top = render_glyph(ch, size, slant)
        # bitmap x origin is -8 units left of the glyph origin
        _blit(cov, gw, gh, pen - 8.0 * k, y - top, color)
        pen += GLYPH.get(ch, GLYPH[' '])[0] * k + tracking
    return pen


def wrap_text(s, size, maxw, slant=0.0):
    """Greedy word wrap; returns list of lines."""
    words = s.split(' ')
    lines = []
    cur = ''
    for wd in words:
        trial = wd if not cur else cur + ' ' + wd
        if text_width(trial, size, slant) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines

# ------------------------------------------------------- illustration kit ---
# Every scene: gradient background + at least 3-4 detail elements.
# Coordinates are absolute canvas px; each scene gets its own (x, y, w, h).

def arc_line(cx, cy, r, a0, a1, c, w=2):
    """Arc as a chain of short thick line segments. Angles in radians."""
    import math as _m
    n = max(4, int(abs(a1 - a0) * r / 6) + 1)
    px = py = None
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        x = cx + r * _m.cos(a); y = cy + r * _m.sin(a)
        if px is not None:
            line(px, py, x, y, c, w)
        px, py = x, y


def windows(x, y, w, h, cols, rows, c, lit=None):
    """Grid of small windows on a building face."""
    cw = w / cols; ch = h / rows
    for r in range(rows):
        for cc in range(cols):
            col = lit[(r * cols + cc) % len(lit)] if lit else c
            fill_rect(x + cc * cw + cw * 0.22, y + r * ch + ch * 0.22,
                      cw * 0.56, ch * 0.56, col)


def person(x, y, s, skin, shirt, hair):
    """Seated delegate: head + shoulders. (x, y) = centre of head."""
    circle(x, y, int(s * 0.42), skin)
    fill_rect(x - int(s * 0.42), y - int(s * 0.55), int(s * 0.84), int(s * 0.28), hair)
    poly([(x - int(s * 0.95), y + int(s * 1.35)), (x + int(s * 0.95), y + int(s * 1.35)),
          (x + int(s * 0.55), y + int(s * 0.35)), (x - int(s * 0.55), y + int(s * 0.35))], shirt)


def mini_flag(x, y, w, h, c1, c2=None, c3=None):
    fill_rect(x, y, w, h, c1)
    if c2:
        fill_rect(x, y + h // 3, w, h // 3, c2)
    if c3:
        fill_rect(x, y + 2 * h // 3, w, h // 3, c3)
    line(x, y + h, x, y + h + 12, (60, 50, 40), 1)


def flames(x, y, w, h):
    """Stylised flames: layered triangles, orange/yellow/red."""
    poly([(x, y + h), (x + w * 0.25, y + h * 0.1), (x + w * 0.45, y + h),
          (x + w * 0.6, y), (x + w * 0.8, y + h), (x + w, y + h * 0.4),
          (x + w, y + h)], (232, 90, 20))
    poly([(x + w * 0.2, y + h), (x + w * 0.4, y + h * 0.35), (x + w * 0.55, y + h),
          (x + w * 0.7, y + h * 0.3), (x + w * 0.85, y + h)], (245, 180, 30))
    poly([(x + w * 0.35, y + h), (x + w * 0.48, y + h * 0.55), (x + w * 0.62, y + h)],
         (255, 230, 90))


def smoke_puffs(x, y, n, c=(120, 118, 112)):
    for i in range(n):
        circle(x + i * 9 - n * 4, y - i * 7, 7 + (i % 3) * 2, c)


def drone_shape(x, y, s, c=(20, 20, 26)):
    line(x - s, y - s * 0.4, x + s, y + s * 0.4, c, 2)
    line(x - s, y + s * 0.4, x + s, y - s * 0.4, c, 2)
    circle(x, y, max(2, s // 3), (200, 40, 40))


# ------------------------------------------------------------- lead scenes --
def scene_cop31(x, y, w, h):
    """COP31 hall: delegates, flags, NO DEAL banner, clock, windows."""
    vgrad(x, y, w, h, (232, 214, 178), (214, 192, 150))
    # back windows with sky
    for i, wx in enumerate((x + 12, x + 130, x + 200)):
        vgrad(wx, y + 6, 60, 30, (140, 180, 210), (210, 225, 235))
        fill_rect(wx, y + 6, 60, 30, (140, 180, 210))
        line(wx + 30, y + 6, wx + 30, y + 36, (120, 100, 70), 2)
        line(wx, y + 21, wx + 60, y + 21, (120, 100, 70), 2)
        fill_rect(wx - 3, y + 3, 66, 3, (90, 70, 45))
        fill_rect(wx - 3, y + 36, 66, 3, (90, 70, 45))
    # wall clock (top right, clear of the banner)
    circle(x + w - 30, y + 24, 11, (250, 246, 236))
    ring(x + w - 30, y + 24, 9, 11, (60, 50, 40), (250, 246, 236))
    line(x + w - 30, y + 24, x + w - 30, y + 16, (40, 40, 40), 2)
    line(x + w - 30, y + 24, x + w - 24, y + 27, (40, 40, 40), 2)
    # hanging lamps
    for lx in (x + 95, x + 240):
        line(lx, y + 6, lx, y + 14, (90, 70, 45), 1)
        ellipse(lx, y + 18, 9, 4, (255, 220, 120))
    # NO DEAL banner
    fill_rect(x + 10, y + 38, w - 20, 18, (178, 34, 34))
    draw_text(x + w // 2, y + 52, "NO DEAL", 14, (255, 255, 255), align='center')
    # long table
    fill_rect(x + 6, y + h - 22, w - 12, 20, (122, 84, 48))
    fill_rect(x + 6, y + h - 24, w - 12, 3, (150, 110, 66))
    # delegates (6, varied colours)
    skins = [(232, 190, 150), (190, 140, 100), (240, 200, 165),
             (200, 150, 110), (235, 195, 155), (180, 130, 95)]
    shirts = [(30, 60, 120), (150, 30, 30), (40, 110, 60),
              (120, 80, 160), (200, 140, 40), (40, 90, 110)]
    hairs = [(40, 30, 25), (20, 20, 20), (120, 120, 120),
             (60, 40, 30), (30, 30, 30), (200, 200, 200)]
    for i in range(6):
        px = x + 28 + i * (w - 56) // 5
        person(px, y + h - 36, 11, skins[i], shirts[i], hairs[i])
    # 4 mini flags on the table
    for i, (c1, c2) in enumerate((((30, 60, 120), (255, 255, 255)),
                                  ((200, 30, 30), (255, 255, 255)),
                                  ((40, 110, 60), (255, 220, 60)),
                                  ((220, 120, 30), (255, 255, 255)))):
        mini_flag(x + 40 + i * 72, y + h - 44, 16, 10, c1, c2)


def scene_kyiv(x, y, w, h):
    """Kyiv night: skyline, lit windows, searchlights, drones, fire, smoke."""
    vgrad(x, y, w, h, (16, 22, 48), (8, 10, 26))
    # stars
    for sx, sy, sr in ((x + 20, y + 10, 1), (x + 70, y + 18, 1), (x + 130, y + 8, 2),
                       (x + 190, y + 14, 1), (x + 240, y + 9, 1), (x + 290, y + 20, 2),
                       (x + 160, y + 26, 1), (x + 40, y + 30, 1), (x + 260, y + 30, 1)):
        circle(sx, sy, sr, (235, 235, 220))
    # moon
    circle(x + w - 40, y + 18, 9, (240, 238, 220))
    # buildings (5) with lit windows
    blds = [(x + 6, 66, 52, 44), (x + 62, 52, 46, 58), (x + 112, 70, 56, 40),
            (x + 172, 58, 50, 52), (x + 226, 66, 48, 44), (x + 278, 74, 46, 36)]
    for bx, by, bw, bh in blds:
        fill_rect(bx, y + h - bh, bw, bh, (24, 28, 44))
        lit = [(250, 200, 80), (250, 200, 80), (60, 60, 80), (250, 200, 80)]
        windows(bx + 4, y + h - bh + 5, bw - 8, bh - 10, 3, 3, (60, 60, 80), lit)
    # damaged block: collapsed stair section (gap + rubble)
    fill_rect(x + 112, y + h - 40, 18, 40, (10, 10, 16))
    poly([(x + 112, y + h), (x + 130, y + h), (x + 121, y + h - 18)], (40, 38, 50))
    # fire glow + flames at the damaged block
    ellipse(x + 121, y + h - 6, 26, 10, (240, 120, 30))
    ellipse(x + 121, y + h - 4, 16, 6, (255, 200, 60))
    flames(x + 108, y + h - 26, 26, 22)
    smoke_puffs(x + 128, y + h - 52, 3, (90, 88, 96))
    # searchlights (2 beams)
    poly([(x + 30, y + h), (x + 44, y + h), (x + 150, y + 6), (x + 128, y + 6)],
         (200, 210, 235))
    poly([(x + 250, y + h), (x + 262, y + h), (x + 210, y + 10), (x + 196, y + 10)],
         (200, 210, 235))
    # drones (3)
    drone_shape(x + 90, y + 22, 7)
    drone_shape(x + 180, y + 14, 6)
    drone_shape(x + 235, y + 34, 7)


def scene_manama(x, y, w, h):
    """Manama: sunset, radar dish + waves, industrial buildings, DENIED."""
    vgrad(x, y, w, h, (250, 150, 70), (90, 60, 120))
    # sun (top left, clear of the DENIED stamp)
    circle(x + 40, y + 22, 12, (255, 220, 120))
    # sea at bottom
    vgrad(x, y + h - 22, w, 22, (30, 60, 110), (20, 40, 80))
    for wx in range(x + 6, x + w - 6, 26):
        line(wx, y + h - 12, wx + 14, y + h - 12, (140, 180, 220), 1)
    # industrial buildings (3) with chimneys + smoke
    for i, (bx, bw, bh) in enumerate(((x + 8, 62, 34), (x + 200, 56, 40), (x + 262, 58, 30))):
        fill_rect(bx, y + h - 22 - bh, bw, bh, (90, 88, 96))
        fill_rect(bx + bw - 12, y + h - 22 - bh - 16, 8, 16, (70, 68, 76))
        smoke_puffs(bx + bw - 8, y + h - 22 - bh - 22, 2, (150, 145, 140))
        windows(bx + 5, y + h - 22 - bh + 6, bw - 10, bh - 12, 3, 2,
                (250, 200, 90), [(250, 200, 90), (90, 88, 96)])
    # radar dish: pedestal + big dish + signal arcs
    dx, dy = x + 138, y + h - 22
    poly([(dx - 8, dy), (dx + 8, dy), (dx + 4, dy - 34), (dx - 4, dy - 34)], (110, 108, 116))
    ellipse(dx, dy - 40, 42, 16, (200, 198, 205))
    ellipse(dx, dy - 44, 42, 16, (225, 223, 230))
    ellipse(dx, dy - 44, 30, 10, (160, 158, 165))
    line(dx, dy - 40, dx + 26, dy - 62, (120, 118, 125), 2)
    for r in (52, 62, 72):
        arc_line(dx + 30, dy - 66, r, -0.9, 0.9, (255, 240, 180), 2)
    # red DENIED cross + stamp
    line(dx - 34, dy - 78, dx + 34, dy - 18, (200, 30, 30), 4)
    line(dx + 34, dy - 78, dx - 34, dy - 18, (200, 30, 30), 4)
    fill_rect(x + w - 96, y + 8, 88, 18, (178, 34, 34))
    draw_text(x + w - 52, y + 22, "DENIED", 12, (255, 255, 255), align='center')

# ------------------------------------------------------- small illustrations
# Each draws inside (x, y, w, h) — a wide strip ~196x44.

def ill_icj(x, y, w, h):
    vgrad(x, y, w, h, (170, 200, 225), (225, 232, 238))
    fill_rect(x + w // 2 - 62, y + 8, 124, 6, (240, 236, 222))       # roof slab
    poly([(x + w // 2 - 62, y + 8), (x + w // 2 + 62, y + 8),
          (x + w // 2, y - 2)], (250, 246, 232))                     # pediment
    circle(x + w // 2, y + 4, 4, (200, 170, 60))                     # emblem
    for i in range(4):                                                # columns
        fill_rect(x + w // 2 - 52 + i * 32, y + 14, 8, h - 18, (245, 242, 230))
    fill_rect(x + w // 2 - 66, y + h - 5, 132, 5, (200, 195, 180))    # steps
    line(x + 16, y + 6, x + 16, y + h - 8, (90, 80, 60), 1)           # flag pole
    mini_flag(x + 16, y + 6, 14, 9, (40, 90, 170), (255, 255, 255))
    fill_rect(x + w - 34, y + h - 16, 22, 5, (150, 110, 60))          # gavel
    fill_rect(x + w - 26, y + h - 22, 5, 7, (150, 110, 60))


def ill_benghazi(x, y, w, h):
    vgrad(x, y, w, h, (30, 70, 120), (16, 40, 80))
    circle(x + w - 24, y + 10, 7, (240, 238, 220))
    poly([(x + 30, y + 26), (x + 150, y + 26), (x + 142, y + 38),
          (x + 38, y + 38)], (120, 122, 128))                        # warship hull
    fill_rect(x + 84, y + 12, 10, 14, (140, 142, 148))                # bridge
    fill_rect(x + 58, y + 18, 6, 8, (140, 142, 148))                  # funnel
    line(x + 89, y + 12, x + 89, y + 4, (160, 162, 168), 2)           # mast
    poly([(x + 158, y + 30), (x + 178, y + 30), (x + 172, y + 38),
          (x + 162, y + 38)], (200, 200, 205))                       # drone boat
    line(x + 158, y + 38, x + 148, y + 40, (200, 220, 235), 1)        # wake
    line(x + 178, y + 38, x + 188, y + 40, (200, 220, 235), 1)
    poly([(x + 44, y + 26), (x + 50, y + 12), (x + 56, y + 26)], (255, 180, 40))
    poly([(x + 48, y + 26), (x + 52, y + 18), (x + 55, y + 26)], (255, 230, 90))
    smoke_puffs(x + 52, y + 8, 2, (150, 150, 155))


def ill_hk(x, y, w, h):
    vgrad(x, y, w, h, (200, 215, 230), (235, 238, 240))
    for i, bh in enumerate((18, 26, 14, 22, 16)):                     # skyline
        fill_rect(x + 8 + i * 13, y + h - bh - 6, 10, bh, (120, 130, 145))
    fill_rect(x + 78, y + h - 24, 34, 24, (178, 34, 34))              # ballot box
    fill_rect(x + 84, y + h - 27, 22, 3, (120, 20, 20))               # slot
    poly([(x + 92, y + h - 34), (x + 104, y + h - 34), (x + 102, y + h - 26),
          (x + 94, y + h - 26)], (255, 255, 255))                     # ballot paper
    line(x + 96, y + h - 32, x + 101, y + h - 28, (178, 34, 34), 2)   # tick
    fill_rect(x + 122, y + 4, 66, h - 8, (255, 255, 255))             # donut card
    ring(x + 140, y + h // 2, 11, 16, (178, 34, 34), (255, 255, 255))
    ring(x + 140, y + h // 2, 11, 16, (200, 200, 200), (255, 255, 255))
    # red arc for 98.79% (almost full circle): draw red ring, then a tiny
    # paper-coloured wedge at top for the remaining 1.21%
    ring(x + 140, y + h // 2, 11, 16, (178, 34, 34), (255, 255, 255))
    poly([(x + 140, y + h // 2 - 16), (x + 143, y + h // 2 - 16),
          (x + 140, y + h // 2)], (255, 255, 255))
    draw_text(x + 166, y + h // 2 + 3, "98.79%", 10, (140, 20, 20), align='center')
    draw_text(x + 166, y + h // 2 + 13, "turnout", 7, (90, 86, 78), align='center')


def ill_cricket(x, y, w, h):
    vgrad(x, y, w, h, (120, 190, 110), (70, 140, 70))
    fill_rect(x + w // 2 - 26, y + 4, 52, h - 8, (225, 200, 150))     # pitch
    for sx in (x + w // 2 - 20, x + w // 2 + 14):                     # stumps
        for i in range(3):
            fill_rect(sx + i * 3, y + 8, 2, 10, (240, 210, 60))
    line(x + 30, y + h - 10, x + 52, y + 12, (150, 110, 60), 4)       # bat
    circle(x + 58, y + 14, 4, (200, 40, 40))                         # ball
    fill_rect(x + w - 62, y + 6, 54, 20, (20, 30, 50))                # scoreboard
    draw_text(x + w - 35, y + 21, "720/9", 13, (255, 255, 255), align='center')
    ellipse(x + 18, y + h - 8, 14, 3, (60, 120, 60))                  # shadow


def ill_f1(x, y, w, h):
    vgrad(x, y, w, h, (40, 30, 80), (16, 12, 40))
    for sx, sy in ((x + 14, y + 8), (x + 60, y + 12), (x + 120, y + 7),
                   (x + 170, y + 12), (x + 90, y + 6)):
        circle(sx, sy, 2, (255, 220, 100))                           # city lights
    fill_rect(x, y + h - 14, w, 14, (50, 50, 55))                     # track
    for tx in range(x + 4, x + w - 4, 18):
        fill_rect(tx, y + h - 8, 10, 2, (240, 240, 240))             # dashes
    poly([(x + 62, y + h - 26), (x + 138, y + h - 26), (x + 132, y + h - 14),
          (x + 68, y + h - 14)], (200, 30, 30))                      # car body
    poly([(x + 96, y + h - 32), (x + 118, y + h - 32), (x + 114, y + h - 26),
          (x + 100, y + h - 26)], (160, 20, 20))                     # cockpit
    circle(x + 76, y + h - 14, 6, (15, 15, 18))                       # wheels
    circle(x + 126, y + h - 14, 6, (15, 15, 18))
    circle(x + 76, y + h - 14, 2, (180, 180, 185))
    circle(x + 126, y + h - 14, 2, (180, 180, 185))
    for i in range(3):                                                # chequered flag
        for j in range(2):
            fill_rect(x + w - 26 + i * 6, y + 6 + j * 6, 6, 6,
                      (20, 20, 20) if (i + j) % 2 == 0 else (255, 255, 255))
    line(x + w - 26, y + 6, x + w - 26, y + 26, (90, 80, 60), 1)


def ill_nba(x, y, w, h):
    vgrad(x, y, w, h, (245, 190, 120), (210, 130, 60))
    fill_rect(x, y + h - 12, w, 12, (180, 110, 50))                   # court floor
    line(x + 20, y + h - 12, x + 60, y + 8, (255, 255, 255), 1)
    fill_rect(x + 14, y + 6, 26, 18, (255, 255, 255))                 # backboard
    fill_rect(x + 16, y + 8, 22, 14, (230, 230, 230))
    ellipse(x + 27, y + 26, 8, 3, (220, 90, 20))                      # rim
    line(x + 21, y + 27, x + 24, y + 36, (240, 240, 240), 1)          # net
    line(x + 33, y + 27, x + 30, y + 36, (240, 240, 240), 1)
    line(x + 24, y + 36, x + 30, y + 36, (240, 240, 240), 1)
    circle(x + 120, y + 22, 11, (230, 120, 40))                       # ball
    arc_line(x + 120, y + 22, 11, -0.6, 0.9, (120, 60, 20), 1)
    line(x + 109, y + 22, x + 131, y + 22, (120, 60, 20), 1)
    fill_rect(x + w - 58, y + 6, 50, 20, (20, 30, 50))                # scoreboard
    draw_text(x + w - 33, y + 21, "50 PTS", 12, (255, 255, 255), align='center')


def ill_capitol(x, y, w, h):
    vgrad(x, y, w, h, (180, 205, 230), (230, 235, 240))
    fill_rect(x + 8, y + h - 14, 66, 14, (245, 242, 232))             # base
    for i in range(4):
        fill_rect(x + 14 + i * 14, y + h - 30, 6, 16, (250, 248, 240))
    ellipse(x + 41, y + h - 30, 20, 12, (250, 248, 240))              # dome
    fill_rect(x + 38, y + h - 46, 6, 6, (250, 248, 240))
    circle(x + 41, y + h - 48, 3, (200, 170, 60))
    fill_rect(x + 88, y + 4, 100, h - 8, (255, 255, 255))             # chart card
    draw_text(x + 138, y + 13, "HOUSE 258 / 435", 8, (90, 86, 78), align='center')
    fill_rect(x + 96, y + 30, 34, 8, (30, 60, 160))                   # D bar
    fill_rect(x + 96, y + 30, 20, 8, (30, 60, 160))
    fill_rect(x + 134, y + 30, 14, 8, (200, 40, 40))
    draw_text(x + 113, y + 28, "258", 8, (30, 60, 160), align='center')
    draw_text(x + 141, y + 28, "177", 8, (200, 40, 40), align='center')
    fill_rect(x + 96, y + 18, 84, 2, (200, 195, 180))
    fill_rect(x + 96, y + 18, 50, 2, (30, 60, 160))


def ill_uk_eu(x, y, w, h):
    vgrad(x, y, w, h, (190, 210, 230), (235, 238, 240))
    fill_rect(x + 10, y + 8, 52, 28, (20, 40, 110))                   # UK flag
    line(x + 10, y + 22, x + 62, y + 22, (255, 255, 255), 5)
    line(x + 36, y + 8, x + 36, y + 36, (255, 255, 255), 5)
    line(x + 10, y + 22, x + 62, y + 22, (200, 30, 40), 2)
    line(x + 36, y + 8, x + 36, y + 36, (200, 30, 40), 2)
    fill_rect(x + 70, y + 8, 52, 28, (30, 60, 160))                   # EU flag
    for i in range(8):
        import math as _m
        a = 2 * _m.pi * i / 8
        circle(x + 96 + int(9 * _m.cos(a)), y + 22 + int(8 * _m.sin(a)), 1,
               (255, 220, 60))
    poly([(x + 132, y + 14), (x + 158, y + 22), (x + 152, y + 30),
          (x + 128, y + 24)], (40, 70, 130))                         # left sleeve
    poly([(x + 188, y + 14), (x + 162, y + 22), (x + 168, y + 30),
          (x + 192, y + 24)], (60, 60, 70))                          # right sleeve
    circle(x + 160, y + 24, 5, (235, 195, 155))                      # clasped hands
    poly([(x + 156, y + 8), (x + 160, y + 2), (x + 164, y + 8)], (255, 220, 60))


def ill_iran_power(x, y, w, h):
    vgrad(x, y, w, h, (90, 80, 140), (40, 35, 70))
    for i, bh in enumerate((16, 22, 13, 19)):                        # dark city
        fill_rect(x + 96 + i * 24, y + h - bh - 4, 20, bh, (25, 25, 35))
        fill_rect(x + 100 + i * 24, y + h - bh + 2, 4, 4, (250, 200, 80))
        fill_rect(x + 108 + i * 24, y + h - bh + 10, 4, 4, (60, 60, 80))
    poly([(x + 18, y + h - 4), (x + 34, y + h - 4), (x + 42, y + 8),
          (x + 52, y + 8), (x + 30, y + h - 4)], (30, 30, 38))        # pylon legs
    line(x + 26, y + h - 4, x + 44, y + 8, (30, 30, 38), 2)
    line(x + 18, y + 14, x + 52, y + 14, (30, 30, 38), 2)             # cross arms
    line(x + 14, y + 20, x + 56, y + 20, (30, 30, 38), 2)
    line(x + 14, y + 20, x + 8, y + 30, (90, 85, 95), 1)              # wires
    line(x + 56, y + 20, x + 62, y + 30, (90, 85, 95), 1)
    poly([(x + 78, y + 6), (x + 70, y + 20), (x + 78, y + 20), (x + 72, y + 34),
          (x + 86, y + 16), (x + 79, y + 16)], (255, 220, 60))        # bolt


def ill_bolsonaro(x, y, w, h):
    vgrad(x, y, w, h, (225, 235, 240), (200, 215, 225))
    fill_rect(x + 8, y + h - 16, 110, 12, (255, 255, 255))            # bed
    fill_rect(x + 8, y + h - 16, 4, 12, (180, 180, 185))
    ellipse(x + 22, y + h - 18, 12, 5, (240, 245, 250))               # pillow
    circle(x + 28, y + h - 22, 5, (235, 195, 155))                    # head
    poly([(x + 34, y + h - 18), (x + 90, y + h - 18), (x + 90, y + h - 6),
          (x + 34, y + h - 6)], (90, 160, 200))                      # blanket
    fill_rect(x + 128, y + 6, 58, 30, (20, 30, 40))                   # monitor
    line(x + 132, y + 24, x + 142, y + 24, (80, 220, 120), 1)
    line(x + 142, y + 24, x + 148, y + 12, (80, 220, 120), 1)
    line(x + 148, y + 12, x + 154, y + 30, (80, 220, 120), 1)
    line(x + 154, y + 30, x + 162, y + 24, (80, 220, 120), 1)
    line(x + 162, y + 24, x + 182, y + 24, (80, 220, 120), 1)
    line(x + 128, y + 36, x + 128, y + h - 4, (120, 120, 125), 1)     # IV stand
    fill_rect(x + 122, y + 10, 8, 12, (200, 225, 240))                # IV bag
    fill_rect(x + 186, y + h - 14, 10, 10, (255, 255, 255))           # cross sign
    fill_rect(x + 189, y + h - 17, 4, 16, (200, 40, 40))
    fill_rect(x + 183, y + h - 11, 16, 4, (200, 40, 40))


def ill_fbi(x, y, w, h):
    vgrad(x, y, w, h, (25, 35, 60), (15, 20, 40))
    fill_rect(x + 14, y + 8, 76, 26, (10, 12, 20))                    # laptop screen
    fill_rect(x + 10, y + 34, 84, 4, (40, 45, 60))                    # laptop base
    for i, ln in enumerate(((18, 14), (18, 20), (18, 26))):
        fill_rect(x + ln[0], y + ln[1], 26 + (i % 2) * 12, 2, (80, 220, 120))
    fill_rect(x + 60, y + 12, 24, 3, (220, 180, 60))
    poly([(x + 128, y + 6), (x + 158, y + 6), (x + 158, y + 30),
          (x + 143, y + 40), (x + 128, y + 30)], (50, 110, 200))      # shield
    line(x + 136, y + 22, x + 142, y + 28, (255, 255, 255), 2)
    line(x + 150, y + 22, x + 142, y + 28, (255, 255, 255), 2)
    poly([(x + 172, y + 8), (x + 188, y + 8), (x + 180, y + 26)], (240, 200, 40))
    draw_text(x + 180, y + 22, "!", 12, (20, 20, 20), align='center')  # warning


def ill_cikande(x, y, w, h):
    vgrad(x, y, w, h, (250, 160, 70), (200, 90, 40))
    fill_rect(x + 10, y + h - 22, 120, 22, (120, 118, 122))           # factory
    poly([(x + 10, y + h - 22), (x + 30, y + h - 32), (x + 50, y + h - 22),
          (x + 70, y + h - 32), (x + 90, y + h - 22), (x + 110, y + h - 32),
          (x + 130, y + h - 22)], (90, 88, 92))                      # sawtooth roof
    fill_rect(x + 140, y + h - 40, 10, 40, (90, 88, 92))              # chimney
    smoke_puffs(x + 145, y + h - 46, 3, (110, 108, 112))
    flames(x + 30, y + h - 30, 70, 26)
    fill_rect(x + 160, y + h - 18, 30, 12, (200, 40, 40))             # fire truck
    circle(x + 168, y + h - 6, 4, (20, 20, 22))
    circle(x + 182, y + h - 6, 4, (20, 20, 22))


def ill_gaza(x, y, w, h):
    vgrad(x, y, w, h, (240, 220, 180), (210, 180, 130))
    circle(x + w - 22, y + 10, 8, (255, 210, 110))                    # sun
    fill_rect(x + 16, y + h - 26, 78, 20, (250, 248, 240))            # food truck
    fill_rect(x + 16, y + h - 26, 78, 6, (200, 60, 50))
    circle(x + 32, y + h - 6, 5, (20, 20, 22))
    circle(x + 78, y + h - 6, 5, (20, 20, 22))
    smoke_puffs(x + 108, y + h - 30, 3, (120, 115, 108))
    poly([(x + 120, y + h), (x + 140, y + h), (x + 132, y + h - 14)], (150, 130, 100))
    poly([(x + 146, y + h), (x + 168, y + h), (x + 158, y + h - 10)], (140, 120, 95))
    fill_rect(x + 176, y + h - 20, 14, 20, (120, 110, 95))            # broken wall


def ill_tennis(x, y, w, h):
    vgrad(x, y, w, h, (70, 120, 190), (50, 90, 160))
    fill_rect(x, y + h - 12, w, 12, (60, 160, 90))                    # court
    line(x, y + h - 12, x + w, y + h - 12, (255, 255, 255), 1)
    line(x + w // 2, y + 6, x + w // 2, y + h - 12, (255, 255, 255), 2)  # net
    fill_rect(x + w // 2 - 2, y + 6, 4, 3, (240, 240, 240))
    circle(x + 34, y + 16, 6, (210, 230, 60))                         # ball
    arc_line(x + 34, y + 16, 6, -1.2, 1.2, (255, 255, 255), 1)
    poly([(x + 150, y + 8), (x + 168, y + 8), (x + 166, y + 18),
          (x + 160, y + 26), (x + 156, y + 18)], (220, 180, 60))      # trophy
    fill_rect(x + 156, y + 26, 8, 3, (220, 180, 60))
    ellipse(x + 70, y + 26, 9, 11, (240, 240, 245))                   # racket
    ellipse(x + 70, y + 26, 6, 8, (70, 120, 190))
    line(x + 70, y + 34, x + 78, y + h - 4, (150, 110, 60), 3)


def ill_sparta(x, y, w, h):
    vgrad(x, y, w, h, (150, 190, 220), (90, 140, 190))
    fill_rect(x, y + h - 10, w, 10, (40, 90, 150))                    # sea
    for wx in range(x + 6, x + w - 6, 24):
        line(wx, y + h - 6, wx + 12, y + h - 6, (200, 225, 245), 1)
    poly([(x + 20, y + h - 22), (x + 130, y + h - 22), (x + 122, y + h - 10),
          (x + 28, y + h - 10)], (60, 62, 68))                       # cargo hull
    fill_rect(x + 30, y + h - 38, 70, 16, (180, 60, 40))              # containers
    fill_rect(x + 34, y + h - 38, 20, 16, (200, 80, 50))
    fill_rect(x + 58, y + h - 38, 20, 16, (40, 90, 160))
    fill_rect(x + 82, y + h - 38, 14, 16, (220, 180, 60))
    fill_rect(x + 106, y + h - 34, 16, 12, (220, 222, 225))           # bridge
    smoke_puffs(x + 114, y + h - 40, 2, (120, 118, 115))
    poly([(x + 148, y + h - 18), (x + 178, y + h - 18), (x + 174, y + h - 10),
          (x + 152, y + h - 10)], (220, 120, 30))                     # tugboat
    fill_rect(x + 156, y + h - 26, 12, 8, (240, 240, 245))
    line(x + 130, y + h - 16, x + 148, y + h - 14, (200, 200, 200), 1)  # tow line
    flames(x + 60, y + h - 46, 22, 10)


SMALL_ILL = {4: ill_icj, 5: ill_benghazi, 6: ill_hk, 7: ill_cricket,
             8: ill_f1, 9: ill_nba, 10: ill_capitol, 11: ill_uk_eu,
             12: ill_iran_power, 13: ill_bolsonaro, 14: ill_fbi,
             15: ill_cikande, 16: ill_gaza, 17: ill_tennis, 18: ill_sparta}

# ------------------------------------------------------------------ data ----
REGIONS = [("EUROPE", 5, (14, 116, 144)), ("MID EAST", 5, (185, 28, 28)),
           ("N. AMERICA", 5, (29, 78, 216)), ("S. AMERICA", 1, (21, 128, 61)),
           ("EAST ASIA", 3, (194, 65, 12)), ("SOUTH ASIA", 4, (124, 58, 237)),
           ("SE ASIA", 3, (161, 98, 7)), ("AFRICA", 6, (22, 101, 52)),
           ("OCEANIA", 2, (3, 105, 161)), ("WORLD", 4, (51, 65, 85))]
REGION_COLOR = {name: c for name, _, c in REGIONS}

NUMBERS = [("186", "DRONES FIRED AT UKRAINE"),
           ("161", "SHOT DOWN OR JAMMED"),
           ("258", "DEMOCRAT HOUSE SEATS"),
           ("$120bn", "ADAPTATION TARGET CUT"),
           ("720/9", "INDIA'S RECORD TEST TOTAL"),
           ("98.79%", "HONG KONG TURNOUT")]

BADGE_COLOR = {"CONFIRMED": (22, 101, 52), "CLAIM": (180, 120, 10),
               "REPORTED": (29, 78, 180)}

LEADS = [
    dict(n=1, loc="ANTALYA, TÜRKIYE · CLIMATE", badge="CONFIRMED",
         head="COP31 ends with no deal",
         body="EU + 130 nations reject a text that never names fossil fuels — "
              "the first COP since 2000 with no cover decision, after 44+ hours.",
         src="Reuters, BBC, The Guardian", scene=scene_cop31),
    dict(n=2, loc="KYIV REGION, UKRAINE · WAR", badge="CONFIRMED",
         head="Russia fires 186 drones at Ukraine",
         body="186 drones overnight, 72 jet-powered; 161 shot down or jammed, "
              "hits in 18 places. In Dymer a block is hit: 2 dead, 14 missing.",
         src="Ukrainian Air Force, Reuters", scene=scene_kyiv),
    dict(n=3, loc="MANAMA, BAHRAIN · IRAN", badge="CLAIM",
         head="Iran claims two US radars hit; Bahrain denies it",
         body="IRGC says it destroyed two US Patriot radars; Bahrain says a "
              "civilian site in Sitra was hit. A US official: no US assets damaged.",
         src="IRGC · Bahrain Interior Ministry · CBS", scene=scene_manama),
]

SMALL = [
    dict(n=4, loc="THE HAGUE · WORLD COURT", src="Reuters/AP", badge="CONFIRMED",
         head="ICJ: Myanmar committed genocide",
         body="Top UN court rules Myanmar committed genocide."),
    dict(n=5, loc="BENGHAZI · CONFLICT", src="Wires", badge="REPORTED",
         head="Sea drones hit Russian warship at Benghazi",
         body="Suspected Ukrainian sea drones hit a Russian corvette."),
    dict(n=6, loc="HONG KONG · ELECTION", src="SCMP", badge="CONFIRMED",
         head="Record turnout in committee polls",
         body="98.79% turnout; 856 candidates for 723 seats."),
    dict(n=7, loc="WELLINGTON · CRICKET", src="ESPNcricinfo", badge="CONFIRMED",
         head="India declare on a record 720/9",
         body="Highest Test total ever in NZ; Rahul 136, Pant 128."),
    dict(n=8, loc="LAS VEGAS · FORMULA 1", src="FIA", badge="CONFIRMED",
         head="Verstappen wins the Las Vegas GP",
         body="Beats Norris under the lights on the Strip."),
    dict(n=9, loc="SAN ANTONIO · NBA", src="NBA", badge="CONFIRMED",
         head="Wembanyama scores 50 as Spurs roll on",
         body="50 pts, 19 reb, 5 blocks; Spurs 114-91 Pelicans."),
    dict(n=10, loc="WASHINGTON · POLITICS", src="AP", badge="CONFIRMED",
         head="Dems win biggest House majority since 1992",
         body="Hubbard beats Foxx after a recount; Dems hold 258+."),
    dict(n=11, loc="LONDON · EUROPE", src="AP/Reuters", badge="CONFIRMED",
         head="UK and EU strike post-Brexit deals",
         body="UK and EU agree trade and travel deals post-Brexit."),
    dict(n=12, loc="TEHRAN · ENERGY", src="Wires", badge="CONFIRMED",
         head="Iran begins rationing electricity",
         body="Rolling blackouts up to 2 hours a day as war bites."),
    dict(n=13, loc="BRASÍLIA · HEALTH", src="Reuters", badge="CONFIRMED",
         head="Bolsonaro in intensive care",
         body="Acute bowel obstruction, stable; surgery possible."),
    dict(n=14, loc="WASHINGTON · CYBER", src="AP", badge="REPORTED",
         head="FBI probes apparent hack of its crime database",
         body="Washington State pauses gun-dealer checks."),
    dict(n=15, loc="CIKANDE · FIRE", src="Detiknews", badge="CONFIRMED",
         head="Cikande factory fire: 3 dead, 36 missing",
         body="Fire engulfs the Bantam factory; search goes on."),
    dict(n=16, loc="GAZA CITY · CONFLICT", src="Civil defence", badge="REPORTED",
         head="Israeli fire kills four in Gaza",
         body="Three killed in a drone strike on a food vehicle."),
    dict(n=17, loc="TURIN · TENNIS", src="ATP", badge="CONFIRMED",
         head="Alcaraz wins first ATP Finals",
         body="Beats Zverev in the Turin final."),
    dict(n=18, loc="GULF OF FINLAND · SEA", src="Wires", badge="CONFIRMED",
         head="Sparta II towed home after drone strike",
         body="Hit by a drone, the ship is towed home."),
]

ALSO = [
    (19, "Europe", "Estonia to shut five Russia border crossings 1 Dec (Reuters)"),
    (20, "Europe", "Denmark expels Russian attaché over alleged plot (Guardian)"),
    (21, "South Asia", "Nepal PM Shah lands in Delhi; meets Modi Monday (IANS)"),
    (22, "East Asia", "Chinese bomber turns back 170 km from Manila (AP)"),
    (23, "Southeast Asia", "Philippines M5.9 quake, 898 km deep, off Palawan (EMSC)"),
    (24, "East Asia", "Japan poll: record 52% feel friendly to South Korea (Ipsos)"),
    (25, "South Asia", "India, China hold fresh military talks over Arunachal (Wires)"),
    (26, "Africa", "Somalia expels UAE ambassador, recalls envoy (Wires)"),
    (27, "Africa", "Sudan: RSF accused of killing civilians in W. Kordofan (Claim)"),
    (28, "Africa", "Kenya discharges its last Ebola patient (Wires)"),
    (29, "Africa", "Drone strikes damage UN facility in Khartoum; 4 killed (Wires)"),
    (30, "Oceania", "Marles rejects US report on AUKUS subs (ABC)"),
    (31, "Oceania", "Melbourne — 70 years since the 1956 Olympics opened (ABC)"),
    (32, "North America", "Trump seeks 'permanent' Israel deal; Doha talks (Al Jazeera)"),
    (33, "Southeast Asia", "EU and Indonesia sign trade deal after ten years (DW)"),
    (34, "Africa", "Sudan army retakes ~30 towns in Kordofan (FT)"),
    (35, "South Asia", "Bangladesh: 30 Awami League homes set on fire (Local)"),
    (36, "Middle East", "Lebanon: Aoun demands Israel withdrawal (Al Jazeera)"),
    (37, "World", "Whale genome sequenced from breath caught by drone (Wires)"),
    (38, "Middle East", "Saudi Arabia and Yemen's Houthis exchange fire (Wires)"),
]

DATE_CHECK = [
    "400-drone, 110-missile barrage (19–20 Nov)",
    "148-drone night, Kryvyi Rih (20–21 Nov)",
    "El Chapo Isidro captured (Sat 21 Nov)",
    "Bayelsa boat capsizes, 24 dead (Fri 21)",
    "Gaza aid-van strike (Sat 21 Nov)",
    "Nvidia SEC probe reported (Fri 20 Nov)",
    "Saudi strikes on Hodeidah (20–21 Nov)",
    "Peru earthquake (Fri 20 Nov)",
    "Copa Sudamericana final (Sat 21 Nov)",
    "BepiColombo at Mercury (Sat 21 Nov)",
    "Russian missiles in Poland (Fri 20 Nov)",
    "Rugby: England 37-12 NZ (Sat 21 Nov)",
    "Football: Arsenal 2-2 Newcastle (Sat 21)",
]

# World map: simplified continents, (lon, lat) polygons.
CONTINENTS = [
    [(-168, 66), (-145, 70), (-125, 71), (-110, 68), (-95, 69), (-85, 69), (-75, 72),
     (-65, 62), (-55, 52), (-60, 46), (-68, 44), (-70, 42), (-74, 39), (-76, 35),
     (-80, 32), (-81, 26), (-84, 30), (-89, 21), (-91, 19), (-95, 16), (-97, 16),
     (-105, 20), (-110, 23), (-114, 28), (-120, 34), (-124, 40), (-124, 48),
     (-130, 55), (-140, 60), (-150, 61), (-160, 58), (-168, 60)],
    [(-78, 8), (-80, 2), (-81, -4), (-80, -6), (-77, -12), (-72, -18), (-70, -23),
     (-70, -30), (-65, -35), (-65, -41), (-68, -47), (-69, -52), (-70, -54),
     (-73, -50), (-73, -44), (-73, -37), (-71, -30), (-70, -20), (-70, -18),
     (-75, -15), (-79, -8), (-81, -3), (-80, 4), (-77, 7)],
    [(-10, 36), (-9, 38), (-9, 43), (-2, 44), (-1, 46), (-4, 48), (-1, 50), (2, 51),
     (5, 53), (8, 55), (8, 57), (10, 59), (13, 56), (18, 56), (21, 55), (24, 58),
     (28, 59), (30, 60), (25, 60), (24, 65), (20, 70), (18, 69), (12, 71), (5, 70),
     (5, 62), (0, 58), (-3, 58), (-5, 56), (-5, 53), (-10, 52), (-10, 48),
     (-10, 43), (-10, 38)],
    [(-5, 50), (-3, 53), (-5, 56), (-2, 58), (-1, 57), (0, 53), (-1, 51)],
    [(-17, 15), (-16, 20), (-15, 25), (-10, 29), (-6, 33), (-1, 35), (5, 37),
     (10, 37), (15, 32), (20, 32), (25, 31), (30, 31), (32, 31), (35, 28),
     (38, 22), (40, 18), (43, 12), (48, 11), (51, 11), (51, 5), (48, 0),
     (44, -2), (40, -8), (38, -12), (35, -18), (32, -26), (28, -32), (24, -34),
     (19, -35), (16, -32), (14, -28), (13, -22), (12, -18), (12, -12), (10, -5),
     (9, -1), (9, 4), (4, 6), (-2, 5), (-8, 4), (-13, 8), (-16, 11)],
    [(30, 60), (35, 62), (40, 66), (45, 68), (55, 68), (65, 69), (75, 72),
     (85, 74), (95, 76), (105, 77), (115, 76), (125, 72), (135, 72), (145, 71),
     (155, 70), (165, 69), (175, 67), (178, 66), (172, 64), (170, 60), (162, 56),
     (158, 52), (150, 59), (142, 55), (140, 50), (138, 45), (135, 43), (130, 42),
     (128, 38), (126, 35), (122, 30), (120, 25), (115, 22), (110, 20), (108, 15),
     (105, 10), (103, 8), (100, 7), (98, 10), (97, 15), (95, 16), (92, 21),
     (90, 22), (88, 22), (86, 20), (83, 17), (80, 13), (77, 8), (75, 10),
     (72, 20), (68, 22), (65, 25), (61, 25), (58, 26), (55, 26), (52, 27),
     (50, 29), (48, 30), (48, 29), (44, 29), (40, 31), (38, 36), (36, 36),
     (33, 36), (30, 36), (30, 38), (28, 40), (27, 41), (30, 46), (30, 50),
     (28, 55), (30, 58)],
    [(95, -5), (100, -2), (105, -5), (110, -6), (115, -8), (120, -9), (125, -8),
     (130, -4), (135, -5), (140, -8), (141, -8), (138, -6), (132, -2), (128, -1),
     (125, 1), (120, 1), (115, 0), (110, -1), (105, -3), (100, -4)],
    [(130, 31), (132, 33), (134, 34), (136, 35), (138, 36), (140, 38), (141, 40),
     (141, 43), (143, 44), (142, 42), (140, 38), (137, 35), (134, 33), (131, 32)],
    [(113, -22), (114, -28), (115, -33), (118, -35), (124, -33), (129, -32),
     (132, -32), (135, -35), (138, -35), (140, -38), (145, -38), (147, -39),
     (150, -37), (153, -32), (153, -27), (150, -22), (146, -19), (142, -15),
     (142, -11), (139, -15), (136, -12), (132, -11), (129, -13), (126, -14),
     (123, -16), (120, -19), (117, -20)],
    [(167, -45), (169, -43), (172, -41), (174, -39), (176, -38), (177, -38),
     (175, -40), (173, -42), (170, -44), (168, -46)],
]

# Map pins: (story, region, true lon/lat, label x, label y).
# Label positions are nudged off the true spot where the cluster is dense;
# a thin leader line joins each label to its true dot.
MAP_X0, MAP_Y0, MAP_W, MAP_H = 8, 884, 496, 104
MAP_LON0, MAP_LAT0 = -170, 78


def _ll(lon, lat):
    return (MAP_X0 + (lon - MAP_LON0) / 360.0 * MAP_W,
            MAP_Y0 + (MAP_LAT0 - lat) / 136.0 * MAP_H)


PINS = [
    (1, "WORLD", 30.7, 36.9, 274, 906), (2, "EUROPE", 30.5, 50.4, 286, 898),
    (3, "MID EAST", 50.6, 26.2, 320, 910), (4, "WORLD", 4.3, 52.1, 234, 890),
    (5, "AFRICA", 20.1, 32.1, 258, 906), (6, "EAST ASIA", 114.2, 22.3, 396, 912),
    (7, "SOUTH ASIA", 174.8, -41.3, 484, 970), (8, "N. AMERICA", -115.1, 36.2, 84, 916),
    (9, "N. AMERICA", -98.5, 29.4, 107, 921), (10, "N. AMERICA", -77.0, 38.9, 132, 906),
    (11, "EUROPE", -0.1, 51.5, 230, 906), (12, "MID EAST", 51.4, 35.7, 310, 898),
    (13, "S. AMERICA", -47.9, -15.8, 176, 956), (14, "N. AMERICA", -77.0, 38.9, 146, 916),
    (15, "SE ASIA", 106.2, -6.2, 382, 942), (16, "MID EAST", 34.5, 31.5, 280, 922),
    (17, "EUROPE", 7.7, 45.1, 248, 918), (18, "WORLD", 24.5, 59.8, 274, 890),
    (19, "EUROPE", 24.8, 59.4, 294, 888), (20, "EUROPE", 12.6, 55.7, 260, 892),
    (21, "SOUTH ASIA", 77.2, 28.6, 342, 908), (22, "EAST ASIA", 121.0, 14.6, 412, 918),
    (23, "SE ASIA", 118.7, 9.8, 404, 934), (24, "EAST ASIA", 139.7, 35.7, 436, 904),
    (25, "SOUTH ASIA", 94.7, 28.2, 370, 906), (26, "AFRICA", 45.3, 2.0, 306, 938),
    (27, "AFRICA", 28.5, 12.0, 272, 930), (28, "AFRICA", 36.8, -1.3, 296, 948),
    (29, "AFRICA", 32.5, 15.6, 288, 924), (30, "OCEANIA", 149.1, -35.3, 448, 962),
    (31, "OCEANIA", 145.0, -37.8, 436, 972), (32, "N. AMERICA", 51.5, 25.3, 328, 920),
    (33, "SE ASIA", 106.8, -6.2, 396, 954), (34, "AFRICA", 30.0, 13.0, 272, 942),
    (35, "SOUTH ASIA", 90.4, 23.8, 360, 920), (36, "MID EAST", 35.5, 33.9, 294, 900),
    (37, "WORLD", -30.0, 0.0, 201, 944), (38, "MID EAST", 45.0, 15.0, 310, 932),
]


def _fit_size(s, size, maxw, slant=0.0):
    while size > 6 and text_width(s, size, slant) > maxw:
        size -= 0.5
    return size


# ----------------------------------------------------------------- layout ---
def draw_page():
    fill_rect(0, 0, W, H, PAPER)

    # --- navy header bar ---
    fill_rect(0, 0, W, 36, NAVY)
    draw_text(512, 24, "THE WORLD IN ONE DAY  ·  38 STORIES – 10 REGIONS  ·  "
                       "EVERY ONE DATED SUNDAY 22 NOVEMBER 2026",
              12, (255, 255, 255), align='center')

    # --- title, 2 lines ---
    draw_text(512, 86, "Sunday 22 November 2026", 50, INK, align='center')
    t2 = "No Deal in Antalya, 186 Drones Over Kyiv, and Hong Kong's 98.79% Vote"
    s2 = _fit_size(t2, 27, 1000)
    draw_text(512, 118, t2, s2, INK, align='center')

    # --- red italic subhead ---
    sub = ("COP31 ends with no deal · 186 drones over Ukraine in the night · "
           "Iran's radar claim meets Bahrain's denial")
    ss = _fit_size(sub, 15, 1000)
    draw_text(512, 138, sub, ss, RED, align='center', slant=0.18)

    # --- numbers strip ---
    for i, (num, label) in enumerate(NUMBERS):
        bx = 8 + i * 169
        fill_rect(bx, 144, 163, 50, (252, 250, 244))
        fill_rect(bx, 144, 163, 1, LGRAY)
        fill_rect(bx, 193, 163, 1, LGRAY)
        fill_rect(bx, 144, 1, 50, LGRAY)
        fill_rect(bx + 162, 144, 1, 50, LGRAY)
        ns = _fit_size(num, 32, 150)
        draw_text(bx + 81, 174, num, ns, RED, align='center')
        ls = _fit_size(label, 9, 155)
        draw_text(bx + 81, 189, label, ls, GRAY, align='center')

    # --- region tabs ---
    for i, (name, count, c) in enumerate(REGIONS):
        tx = 8 + i * 101
        fill_rect(tx, 198, 97, 22, c)
        draw_text(tx + 48, 213, "%s %d" % (name, count), 9, (255, 255, 255),
                  align='center')

    # --- UTC timeline + press time ---
    fill_rect(8, 224, 1008, 22, NAVY)
    draw_text(14, 239, "THE DAY IN UTC", 9, (255, 220, 120))
    tl = ("01:00 HK polls open  ·  03:00 COP31 objections close  ·  "
          "05:11 Hamas seeks talks  ·  05:30 Vegas GP ends  ·  "
          "06:00 COP31 approval due")
    ts = _fit_size(tl, 9.5, 716)
    draw_text(124, 239, tl, ts, (255, 255, 255))
    fill_rect(852, 224, 164, 22, RED)
    draw_text(934, 239, "PRESS TIME 09:45 UTC", 11, (255, 255, 255), align='center')

    # --- 3 lead stories ---
    for i, lead in enumerate(LEADS):
        x = 8 + i * 338
        lead["scene"](x, 250, 330, 100)
        fill_rect(x, 250, 330, 1, (180, 175, 160))
        fill_rect(x, 349, 330, 1, (180, 175, 160))
        draw_text(x, 366, lead["loc"], 10, INK)
        bc = BADGE_COLOR[lead["badge"]]
        bw = int(text_width(lead["badge"], 8) + 12)
        fill_rect(x + 330 - bw, 354, bw, 14, bc)
        draw_text(x + 330 - bw // 2, 365, lead["badge"], 8, (255, 255, 255),
                  align='center')
        lines = wrap_text(lead["head"], 17, 330)
        for j, ln in enumerate(lines[:2]):
            draw_text(x, 384 + j * 18, ln, 17, INK)
        blines = wrap_text(lead["body"], 10, 330)
        for j, ln in enumerate(blines[:3]):
            draw_text(x, 416 + j * 12, ln, 10, (60, 58, 52))
        draw_text(x, 452, lead["src"], 8.5, GRAY)

    # --- 15 small stories, 5 cols x 3 rows ---
    for idx, st in enumerate(SMALL):
        col = idx % 5
        row = idx // 5
        x = 8 + col * 202
        y0 = 456 + row * 102
        SMALL_ILL[st["n"]](x, y0, 196, 46)
        bc = BADGE_COLOR[st["badge"]]
        bw = int(text_width(st["badge"], 7.5) + 10)
        fill_rect(x, y0, bw, 12, bc)
        draw_text(x + bw // 2, y0 + 9, st["badge"], 7.5, (255, 255, 255),
                  align='center')
        loc = "%d · %s" % (st["n"], st["loc"])
        ls = _fit_size(loc, 9, 196)
        draw_text(x, y0 + 57, loc, ls, INK)
        hlines = wrap_text(st["head"], 11, 196)
        for j, ln in enumerate(hlines[:2]):
            draw_text(x, y0 + 70 + j * 12, ln, 11, INK)
        blines = wrap_text(st["body"], 9, 196)
        for j, ln in enumerate(blines[:2]):
            draw_text(x, y0 + 91 + j * 10, ln, 9, (60, 58, 52))

    # --- ALSO: 20 more stories, 2 columns ---
    draw_text(8, 776, "ALSO ON SUNDAY 22 NOVEMBER — 20 MORE STORIES", 12, INK)
    hline(8, 782, 1008, (180, 175, 160), 1)
    for i, (n, region, text) in enumerate(ALSO):
        col = i // 10
        r = i % 10
        cx = 8 + col * 504
        draw_text(cx, 794 + r * 10, "%d. %s: %s" % (n, region, text), 8.5, INK)

    # --- world map ---
    fill_rect(8, 884, 496, 104, (214, 228, 232))
    for cont in CONTINENTS:
        poly([_ll(lon, lat) for lon, lat in cont], (232, 222, 196))
    draw_text(16, 898, "WHERE IT HAPPENED", 10, INK)
    draw_text(496, 898, "pins = story numbers", 8, GRAY, align='right')
    for (n, region, lon, lat, lx, ly) in PINS:
        tx, ty = _ll(lon, lat)
        if abs(lx - tx) > 3 or abs(ly - ty) > 3:
            line(lx, ly, tx, ty, (120, 115, 105), 1)
            circle(tx, ty, 2, (60, 58, 52))
        circle(lx, ly, 5, REGION_COLOR[region])
        ring(lx, ly, 4, 5, (255, 255, 255), REGION_COLOR[region])
        draw_text(lx, ly + 2.5, str(n), 6.5, (255, 255, 255), align='center')

    # --- DATE CHECK ---
    fill_rect(512, 884, 504, 104, (252, 248, 242))
    fill_rect(512, 884, 504, 2, RED)
    fill_rect(512, 986, 504, 2, RED)
    fill_rect(512, 884, 2, 104, RED)
    fill_rect(1014, 884, 2, 104, RED)
    fill_rect(520, 890, 74, 14, RED)
    draw_text(557, 901, "DATE CHECK", 9, (255, 255, 255), align='center')
    draw_text(602, 901, "LEFT OUT ON PURPOSE — THESE HAPPENED ON OTHER DAYS",
              9, DRED)
    for i, item in enumerate(DATE_CHECK):
        col = 0 if i < 7 else 1
        r = i if i < 7 else i - 7
        cx = 522 + col * 252
        draw_text(cx, 918 + r * 11.5, "•  " + item, 7.5, (90, 40, 40))

    # --- footer ---
    hline(8, 992, 1008, (180, 175, 160), 1)
    draw_text(8, 1004, "Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, "
                       "UNFCCC, Kyiv Post, SCMP, ESPNcricinfo, Detiknews",
              9, GRAY)
    draw_text(8, 1016, "CERTAINTY:  CONFIRMED = verified  ·  CLAIM = one side's claim  ·  "
                       "REPORTED = reported, not fully verified  ·  "
                       "Scenes are drawn illustrations  ·  Wires read to press time 09:45 UTC",
              8, GRAY)


def main():
    draw_page()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    size = write_png(path)
    print("wrote %s (%d bytes)" % (path, size))


if __name__ == "__main__":
    main()
