#!/usr/bin/env python3
"""makefun-news-image-20261122 v2 -- draws the 22 Nov 2026 front page from scratch.

Pure Python 3.13, standard library only. No network, no system fonts, no
randomness: the serif typeface, every illustration and the PNG encoder are
hand-written in this file, so two runs write byte-identical output.
"""
import math
import os
import struct
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- canvas ----
PAPER = (247, 243, 232)
INK = (26, 26, 30)
NAVY = (26, 43, 74)
NAVY2 = (18, 32, 58)
RED = (178, 34, 34)
REDBG = (150, 22, 22)
GREEN = (31, 122, 74)
AMBER = (176, 124, 18)
GREY = (110, 108, 100)
LGREY = (210, 206, 192)
WHITE = (255, 255, 255)

rows = [bytearray(PAPER[0:1] * 0) for _ in range(H)]
for _y in range(H):
    rows[_y] = bytearray(bytes(PAPER) * W)


def _cb(c):
    return bytes(c)


def rect(x, y, w, h, c):
    x = int(round(x)); y = int(round(y)); w = int(round(w)); h = int(round(h))
    if w <= 0 or h <= 0:
        return
    x0 = max(0, x); y0 = max(0, y)
    x1 = min(W, x + w); y1 = min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    b = _cb(c) * (x1 - x0)
    for yy in range(y0, y1):
        rows[yy][x0 * 3:x1 * 3] = b


def hline(x, y, w, c):
    rect(x, y, w, 1, c)


def vgrad(x, y, w, h, c1, c2):
    x = int(round(x)); y = int(round(y)); w = int(round(w)); h = int(round(h))
    if w <= 0 or h <= 0:
        return
    for i in range(h):
        t = i / max(1, h - 1)
        c = (round(c1[0] + (c2[0] - c1[0]) * t),
             round(c1[1] + (c2[1] - c1[1]) * t),
             round(c1[2] + (c2[2] - c1[2]) * t))
        yy = y + i
        if 0 <= yy < H:
            x0 = max(0, x); x1 = min(W, x + w)
            if x0 < x1:
                rows[yy][x0 * 3:x1 * 3] = _cb(c) * (x1 - x0)


def poly(pts, c):
    """Fill a polygon given as [(x, y), ...] in screen coords (y down)."""
    if len(pts) < 3:
        return
    ys = [p[1] for p in pts]
    y0 = max(0, int(math.ceil(min(ys))))
    y1 = min(H - 1, int(math.floor(max(ys))))
    n = len(pts)
    b = _cb(c)
    for yy in range(y0, y1 + 1):
        yc = yy + 0.5
        xs = []
        for i in range(n):
            x0, y0a = pts[i]
            x1, y1a = pts[(i + 1) % n]
            if y0a == y1a:
                continue
            lo, hi = (y0a, y1a) if y0a < y1a else (y1a, y0a)
            if lo <= yc < hi:
                xs.append(x0 + (yc - y0a) * (x1 - x0) / (y1a - y0a))
        if len(xs) < 2:
            continue
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            # pixel-centre coverage: fill pixels whose centre is in the span
            xa = max(0, int(math.ceil(xs[k] - 0.5)))
            xb = min(W - 1, int(math.floor(xs[k + 1] - 0.5)))
            if xa <= xb:
                rows[yy][xa * 3:(xb + 1) * 3] = b * (xb + 1 - xa)


def disc(cx, cy, r, c):
    r = float(r)
    if r <= 0:
        return
    y0 = max(0, int(math.floor(cy - r)))
    y1 = min(H - 1, int(math.ceil(cy + r)))
    b = _cb(c)
    for yy in range(y0, y1 + 1):
        dy = yy + 0.5 - cy
        dx = math.sqrt(max(0.0, r * r - dy * dy))
        xa = max(0, int(math.ceil(cx - dx - 0.5)))
        xb = min(W - 1, int(math.floor(cx + dx - 0.5)))
        if xa <= xb:
            rows[yy][xa * 3:(xb + 1) * 3] = b * (xb + 1 - xa)


def ellipse(cx, cy, rx, ry, c):
    y0 = max(0, int(math.floor(cy - ry)))
    y1 = min(H - 1, int(math.ceil(cy + ry)))
    b = _cb(c)
    for yy in range(y0, y1 + 1):
        dy = (yy + 0.5 - cy) / max(0.01, ry)
        if abs(dy) >= 1:
            continue
        dx = rx * math.sqrt(max(0.0, 1 - dy * dy))
        xa = max(0, int(math.ceil(cx - dx - 0.5)))
        xb = min(W - 1, int(math.floor(cx + dx - 0.5)))
        if xa <= xb:
            rows[yy][xa * 3:(xb + 1) * 3] = b * (xb + 1 - xa)


def ring(cx, cy, r, w, c):
    """Hollow circle: outer disc minus inner disc (drawn via poly ring)."""
    n = 28
    outer = [(cx + r * math.cos(2 * math.pi * i / n),
              cy + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    inner = [(cx + (r - w) * math.cos(2 * math.pi * i / n),
              cy + (r - w) * math.sin(2 * math.pi * i / n)) for i in range(n)]
    # fill outer, then punch inner with paper-coloured disc is wrong on
    # coloured backgrounds, so draw the ring as a polygon band instead:
    pts = outer + inner[::-1]
    poly(pts, c)


def thick_line(x0, y0, x1, y1, w, c):
    dx = x1 - x0; dy = y1 - y0
    L = math.hypot(dx, dy)
    if L < 0.01:
        disc(x0, y0, w / 2.0, c)
        return
    nx, ny = -dy / L * w / 2.0, dx / L * w / 2.0
    poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
          (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)


def arc_pts(cx, cy, rx, ry, a0, a1, n=24):
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def polyline(pts, w, c):
    for i in range(len(pts) - 1):
        thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w, c)
    for (px, py) in pts[1:-1]:
        disc(px, py, w / 2.0, c)


def star4(cx, cy, r, c):
    poly([(cx, cy - r), (cx + r * 0.22, cy - r * 0.22), (cx + r, cy),
          (cx + r * 0.22, cy + r * 0.22), (cx, cy + r),
          (cx - r * 0.22, cy + r * 0.22), (cx - r, cy),
          (cx - r * 0.22, cy - r * 0.22)], c)


def building(x, y, w, h, body, win, cols=3, rws=3, lit=True):
    rect(x, y, w, h, body)
    ww = w / (cols * 2 + 1)
    hh = h / (rws * 2 + 1)
    for ci in range(cols):
        for ri in range(rws):
            wx = x + ww * (ci * 2 + 1)
            wy = y + hh * (ri * 2 + 1)
            rect(wx, wy, ww * 0.9, hh * 0.9, win if lit else LGREY)


def flag(x, y, w, h, pole_c, c1, c2=None):
    rect(x, y, 2, h + 12, pole_c)
    rect(x + 2, y, w, h, c1)
    if c2 is not None:
        rect(x + 2, y + h // 2, w, h - h // 2, c2)


def cloud(x, y, s, c):
    disc(x, y, s * 0.55, c)
    disc(x + s * 0.5, y + s * 0.1, s * 0.45, c)
    disc(x - s * 0.5, y + s * 0.12, s * 0.42, c)
    rect(x - s, y, s * 2, s * 0.45, c)


# ---------------------------------------------------------------- PNG -------
def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def png_bytes():
    raw = bytearray()
    prev = bytearray(W * 3)
    for yy in range(H):
        cur = rows[yy]
        # filter 0 (none) vs filter 2 (up): pick the smaller residual
        s0 = sum(abs(b if b < 128 else b - 256) for b in cur)
        up = bytes(((cur[i] - prev[i]) & 0xFF) for i in range(W * 3))
        s2 = sum(abs(b if b < 128 else b - 256) for b in up)
        if s2 < s0:
            raw.append(2)
            raw += up
        else:
            raw.append(0)
            raw += cur
        prev = cur
    comp = zlib.compress(bytes(raw), 6)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
            _chunk(b"IDAT", comp) + _chunk(b"IEND", b""))


def write_png(path):
    data = png_bytes()
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)

# ------------------------------------------------------- serif typeface ----
# Hand-drawn proportional serif. Em = 1000 units, baseline y=0 (y up),
# cap height 700, x-height 480, descender -220. Stroke kinds:
#   ('l', x0,y0,x1,y1,w)  straight stem/bar
#   ('p', [(x,y),...], w) polyline (curves approximated by points)
#   ('a', cx,cy,rx,ry,a0,a1,w) elliptical arc, degrees, y up
#   ('d', cx,cy,r)     filled disc (dots)
# Thick verticals / thin horizontals give the Times-like contrast; the
# renderer adds small serif feet to stems that end on the baseline or
# at cap / x-height. Widths are proportional (i narrow, m/w wide).
def _ov(cx, cy, rx, ry, a0=0, a1=360, n=12):
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((round(cx + rx * math.cos(a)), round(cy + ry * math.sin(a))))
    return pts


GL = {}
# ---- uppercase ----
GL['A'] = (700, [('l', 70, 0, 350, 700, 85), ('l', 630, 0, 350, 700, 85),
                ('l', 190, 270, 510, 270, 40)])
GL['B'] = (640, [('l', 70, 0, 70, 700, 85),
                ('p', [(70, 700), (280, 700), (400, 670), (440, 580), (400, 490), (280, 460), (70, 460)], 58),
                ('p', [(70, 460), (300, 460), (430, 430), (470, 330), (440, 210), (340, 60), (180, 0), (70, 0)], 58)])
GL['C'] = (660, [('p', [(560, 600), (460, 690), (280, 700), (140, 660), (80, 540), (60, 350), (80, 160), (140, 60), (280, 20), (450, 40), (560, 140)], 60)])
GL['D'] = (700, [('l', 70, 0, 70, 700, 85),
                ('p', [(70, 700), (340, 700), (500, 640), (560, 480), (560, 260), (480, 80), (330, 0), (70, 0)], 60)])
GL['E'] = (600, [('l', 70, 0, 70, 700, 85), ('l', 70, 700, 540, 700, 40),
                ('l', 70, 360, 460, 360, 38), ('l', 70, 0, 540, 0, 40)])
GL['F'] = (580, [('l', 70, 0, 70, 700, 85), ('l', 70, 700, 520, 700, 40),
                ('l', 70, 360, 440, 360, 38)])
GL['G'] = (700, [('p', [(580, 580), (470, 690), (280, 700), (140, 660), (80, 540), (60, 350), (80, 160), (150, 60), (300, 20), (470, 50), (560, 150)], 60),
                ('l', 360, 320, 600, 320, 45), ('l', 600, 320, 600, 140, 45)])
GL['H'] = (700, [('l', 70, 0, 70, 700, 85), ('l', 630, 0, 630, 700, 85),
                ('l', 70, 350, 630, 350, 40)])
GL['I'] = (320, [('l', 160, 0, 160, 700, 85), ('l', 60, 700, 260, 700, 40),
                ('l', 60, 0, 260, 0, 40)])
GL['J'] = (540, [('l', 60, 700, 480, 700, 40), ('l', 440, 700, 440, 160, 80),
                ('p', [(440, 160), (420, 60), (340, 10), (240, 20), (180, 80)], 60)])
GL['K'] = (680, [('l', 70, 0, 70, 700, 85), ('l', 70, 340, 520, 700, 65),
                ('l', 200, 300, 560, 0, 65)])
GL['L'] = (580, [('l', 70, 0, 70, 700, 85), ('l', 70, 0, 520, 0, 40)])
GL['M'] = (820, [('l', 70, 0, 70, 700, 85), ('l', 750, 0, 750, 700, 85),
                ('l', 70, 700, 410, 120, 60), ('l', 750, 700, 410, 120, 60)])
GL['N'] = (720, [('l', 70, 0, 70, 700, 85), ('l', 650, 0, 650, 700, 85),
                ('l', 70, 700, 650, 0, 60)])
GL['O'] = (720, [('p', _ov(360, 350, 300, 350), 62)])
GL['P'] = (620, [('l', 70, 0, 70, 700, 85),
                ('p', [(70, 700), (300, 700), (440, 660), (480, 560), (440, 460), (300, 420), (70, 420)], 58)])
GL['Q'] = (740, [('p', _ov(360, 350, 300, 350), 62), ('l', 430, 160, 620, -10, 55)])
GL['R'] = (660, [('l', 70, 0, 70, 700, 85),
                ('p', [(70, 700), (300, 700), (440, 660), (480, 560), (440, 460), (300, 420), (70, 420)], 58),
                ('l', 290, 420, 600, 0, 62)])
GL['S'] = (620, [('p', [(520, 560), (470, 660), (330, 700), (190, 680), (120, 600), (120, 500), (180, 430), (320, 390), (450, 350), (520, 260), (500, 150), (400, 50), (260, 30), (140, 80)], 60)])
GL['T'] = (640, [('l', 60, 700, 580, 700, 40), ('l', 320, 0, 320, 700, 85)])
GL['U'] = (700, [('p', [(70, 700), (70, 180), (120, 70), (240, 20), (420, 20), (540, 70), (590, 180), (590, 700)], 62)])
GL['V'] = (680, [('l', 60, 700, 320, 0, 80), ('l', 620, 700, 320, 0, 80)])
GL['W'] = (940, [('l', 60, 700, 230, 0, 75), ('l', 230, 0, 470, 470, 75),
                ('l', 470, 470, 710, 0, 75), ('l', 710, 0, 880, 700, 75)])
GL['X'] = (680, [('l', 70, 700, 610, 0, 70), ('l', 610, 700, 70, 0, 70)])
GL['Y'] = (640, [('l', 60, 700, 320, 340, 75), ('l', 580, 700, 320, 340, 75),
                ('l', 320, 340, 320, 0, 80)])
GL['Z'] = (640, [('l', 70, 700, 570, 700, 40), ('l', 570, 700, 70, 0, 55),
                ('l', 70, 0, 570, 0, 40)])

# ---- lowercase ----
GL['a'] = (560, [('p', _ov(260, 240, 200, 235), 55), ('l', 470, 0, 470, 480, 58)])
GL['b'] = (580, [('l', 70, 0, 70, 700, 85), ('p', _ov(290, 240, 200, 230), 55)])
GL['c'] = (520, [('p', [(480, 380), (380, 460), (240, 480), (130, 420), (80, 300), (80, 180), (130, 70), (240, 20), (380, 40), (470, 120)], 55)])
GL['d'] = (580, [('p', _ov(270, 240, 200, 235), 55), ('l', 462, 0, 462, 700, 80)])
GL['e'] = (560, [('p', [(480, 220), (440, 360), (340, 460), (200, 470), (110, 400), (80, 280), (110, 150), (200, 60), (330, 40), (450, 90), (480, 180)], 55),
                ('l', 80, 240, 480, 240, 38)])
GL['f'] = (420, [('l', 250, 0, 250, 620, 70),
                ('p', [(250, 620), (270, 690), (330, 700), (370, 680)], 55),
                ('l', 130, 450, 390, 450, 38)])
GL['g'] = (560, [('p', _ov(260, 240, 200, 235), 55),
                ('p', [(462, 240), (462, -60), (440, -160), (360, -200), (270, -190), (230, -140)], 55)])
GL['h'] = (600, [('l', 70, 0, 70, 700, 85),
                ('p', [(70, 480), (180, 480), (300, 450), (370, 360), (390, 220), (390, 0)], 58)])
GL['i'] = (280, [('l', 140, 0, 140, 480, 70), ('d', 140, 590, 48)])
GL['j'] = (300, [('p', [(210, 480), (210, -80), (190, -160), (130, -190), (90, -160)], 60),
                ('d', 210, 590, 48)])
GL['k'] = (580, [('l', 70, 0, 70, 700, 85), ('l', 70, 260, 380, 480, 58),
                ('l', 180, 220, 420, 0, 58)])
GL['l'] = (280, [('l', 140, 0, 140, 700, 70)])
GL['m'] = (860, [('l', 70, 0, 70, 480, 80),
                ('p', [(70, 480), (170, 480), (260, 450), (300, 360), (310, 240), (310, 0)], 55),
                ('p', [(310, 480), (410, 480), (500, 450), (540, 360), (550, 240), (550, 0)], 55)])
GL['n'] = (600, [('l', 70, 0, 70, 480, 80),
                ('p', [(70, 480), (180, 480), (300, 450), (370, 360), (390, 220), (390, 0)], 58)])
GL['o'] = (560, [('p', _ov(280, 240, 200, 230), 55)])
GL['p'] = (580, [('l', 70, -220, 70, 480, 85), ('p', _ov(300, 240, 200, 230), 55)])
GL['q'] = (580, [('p', _ov(280, 240, 200, 230), 55), ('l', 462, -220, 462, 480, 80)])
GL['r'] = (440, [('l', 70, 0, 70, 480, 80),
                ('p', [(70, 480), (160, 480), (240, 450), (280, 390), (290, 330)], 55)])
GL['s'] = (520, [('p', [(440, 360), (400, 440), (300, 480), (190, 460), (140, 390), (150, 320), (220, 280), (330, 250), (400, 190), (390, 100), (320, 30), (210, 20), (130, 70)], 55)])
GL['t'] = (400, [('l', 200, -10, 200, 600, 65),
                ('p', [(200, 600), (220, 660), (270, 680)], 55),
                ('l', 90, 440, 330, 440, 38),
                ('p', [(200, -10), (260, -10), (300, 30)], 55)])
GL['u'] = (580, [('p', [(70, 480), (70, 140), (120, 50), (210, 20), (300, 20), (370, 60), (390, 140), (390, 480)], 58)])
GL['v'] = (540, [('l', 60, 480, 260, 0, 65), ('l', 480, 480, 260, 0, 65)])
GL['w'] = (780, [('l', 60, 480, 190, 0, 60), ('l', 190, 0, 390, 300, 60),
                ('l', 390, 300, 590, 0, 60), ('l', 590, 0, 720, 480, 60)])
GL['x'] = (520, [('l', 70, 480, 450, 0, 58), ('l', 450, 480, 70, 0, 58)])
GL['y'] = (540, [('l', 60, 480, 250, 0, 62), ('l', 480, 480, 250, 0, 62),
                ('p', [(250, 0), (250, -140), (220, -200), (160, -210)], 58)])
GL['z'] = (500, [('l', 70, 480, 430, 480, 38), ('l', 430, 480, 70, 0, 50),
                ('l', 70, 0, 430, 0, 38)])
# ---- digits ----
GL['0'] = (600, [('p', _ov(300, 350, 240, 350), 62)])
GL['1'] = (360, [('l', 200, 60, 200, 700, 80), ('p', [(200, 700), (120, 620)], 55),
                ('l', 90, 0, 330, 0, 40)])
GL['2'] = (600, [('p', [(140, 560), (180, 660), (300, 700), (420, 660), (440, 560), (400, 460), (300, 330), (140, 0), (480, 0)], 60)])
GL['3'] = (600, [('p', [(120, 700), (320, 700), (430, 650), (450, 560), (400, 470), (300, 440)], 58),
                ('p', [(300, 440), (430, 400), (470, 300), (440, 180), (360, 60), (220, 0), (110, 30)], 58)])
GL['4'] = (600, [('l', 430, 0, 430, 700, 80), ('l', 90, 260, 480, 260, 40),
                ('l', 430, 700, 100, 240, 60)])
GL['5'] = (600, [('l', 100, 700, 460, 700, 40), ('l', 100, 700, 100, 400, 60),
                ('p', [(100, 400), (300, 400), (430, 360), (470, 260), (440, 140), (340, 50), (200, 30), (110, 70)], 58)])
GL['6'] = (600, [('p', [(430, 620), (380, 690), (260, 700), (150, 640), (110, 520), (110, 360), (140, 200), (220, 60), (340, 20), (430, 70), (470, 160), (460, 280), (400, 380), (280, 400), (170, 360)], 58)])
GL['7'] = (600, [('l', 100, 700, 500, 700, 40), ('l', 500, 700, 180, 0, 60)])
GL['8'] = (600, [('p', _ov(300, 500, 200, 190), 58), ('p', _ov(300, 190, 220, 180), 58)])
GL['9'] = (600, [('p', _ov(300, 500, 210, 190), 58),
                ('p', [(480, 480), (480, 160), (430, 50), (330, 0), (230, 10)], 58)])
# ---- punctuation ----
GL[' '] = (300, [])
GL['.'] = (300, [('d', 250, 45, 52)])
GL[','] = (300, [('d', 250, 60, 48), ('p', [(250, 80), (230, 0), (200, -90), (150, -140)], 50)])
GL[':'] = (300, [('d', 250, 520, 52), ('d', 250, 120, 52)])
GL[';'] = (300, [('d', 250, 520, 50), ('d', 250, 60, 48),
                ('p', [(250, 80), (230, 0), (200, -90), (150, -140)], 50)])
GL["'"] = (300, [('p', [(280, 700), (240, 600), (230, 540)], 55)])
GL['"'] = (440, [('p', [(180, 700), (140, 600), (130, 540)], 55),
                ('p', [(380, 700), (340, 600), (330, 540)], 55)])
GL['!'] = (320, [('l', 250, 180, 250, 700, 75), ('d', 250, 80, 55)])
GL['?'] = (560, [('p', [(200, 520), (220, 640), (340, 700), (460, 640), (460, 540), (380, 460), (300, 400), (280, 300)], 55),
                ('d', 290, 80, 55)])
GL['-'] = (520, [('l', 60, 300, 460, 300, 45)])
GL['\u2013'] = (700, [('l', 60, 300, 640, 300, 45)])
GL['\u2014'] = (1000, [('l', 40, 300, 960, 300, 45)])
GL['('] = (420, [('p', [(420, 700), (300, 600), (240, 350), (300, 100), (420, 0)], 55)])
GL[')'] = (420, [('p', [(0, 700), (120, 600), (180, 350), (120, 100), (0, 0)], 55)])
GL['/'] = (520, [('l', 430, 700, 90, -20, 55)])
GL['%'] = (700, [('p', _ov(200, 540, 115, 115), 45), ('p', _ov(480, 160, 115, 115), 45),
                ('l', 560, 700, 120, 0, 50)])
GL['$'] = (600, [('p', [(480, 540), (430, 650), (300, 690), (180, 660), (140, 570), (180, 500), (300, 460), (430, 430), (480, 340), (450, 230), (350, 150), (220, 140), (130, 200)], 55),
                ('l', 310, 740, 310, -40, 45)])
GL['&'] = (640, [('p', [(430, 600), (380, 680), (270, 690), (200, 620), (220, 540), (330, 450), (470, 330), (490, 200), (430, 100), (310, 80), (210, 130)], 55),
                ('l', 470, 340, 170, 40, 50)])
GL['+'] = (600, [('l', 300, 80, 300, 620, 45), ('l', 80, 350, 520, 350, 45)])
GL['='] = (600, [('l', 80, 280, 520, 280, 40), ('l', 80, 460, 520, 460, 40)])
GL['\u00b7'] = (400, [('d', 300, 380, 55)])
GL['\u2022'] = (500, [('d', 300, 350, 90)])
GL['\u00d7'] = (600, [('l', 120, 560, 480, 140, 50), ('l', 480, 560, 120, 140, 50)])


# ------------------------------------------------------- text engine ------
def _tx(x, py, s, shear):
    return x + (py[0] + shear * py[1]) * s


def _ty(base, py, s):
    return base - py[1] * s


def _serif_bar(cx, cy, sw, sh, c):
    rect(cx - sw / 2.0, cy - sh / 2.0, sw, sh, c)


def _adv(ch, size):
    g = GL.get(ch)
    return ((g[0] if g else 300) - 70) * size / 1000.0


def draw_glyph(ch, x, base, size, col, bold=False, italic=False):
    """Draw one glyph with its left edge at x, baseline at base. Returns advance."""
    g = GL.get(ch)
    if g is None:
        return size * 0.23
    adv, strokes = g
    s = size / 1000.0
    shear = 0.16 if italic else 0.0
    bw = 1.35 if bold else 1.0
    # trim the wide side bearings of the hand-drawn glyphs so letters sit
    # close like real serif type instead of spaced-out blocks
    x = x - 35 * s
    # hinting: never let a stroke fall below ~1px, or small text vanishes
    min_stem = 1.3 if size < 30 else 0.0
    min_thin = 1.0 if size < 30 else 0.0
    for st in strokes:
        k = st[0]
        if k == 'd':
            _, cx, cy, r = st
            disc(_tx(x, (cx, cy), s, shear), _ty(base, (cx, cy), s),
                 max(r * s, 0.8), col)
        elif k == 'l':
            _, x0, y0, x1, y1, w = st
            wpx = w * bw * s
            wpx = max(wpx, min_stem if w >= 60 else min_thin)
            thick_line(_tx(x, (x0, y0), s, shear), _ty(base, (x0, y0), s),
                       _tx(x, (x1, y1), s, shear), _ty(base, (x1, y1), s), wpx, col)
            # serif feet: stems ending on baseline / cap / x-height
            if size >= 18 and abs(y1 - y0) > 1 and w >= 60:
                for (ex, ey) in ((x0, y0), (x1, y1)):
                    if ey in (0, 480, 700):
                        _serif_bar(_tx(x, (ex, ey), s, shear), _ty(base, (ex, ey), s),
                                   w * 2.6 * bw * s, w * 0.5 * bw * s, col)
                    elif ey == 0:
                        _serif_bar(_tx(x, (ex, ey), s, shear), _ty(base, (ex, ey), s),
                                   w * 2.0 * bw * s, w * 0.45 * bw * s, col)
        elif k == 'p':
            _, pts, w = st
            wpx = max(w * bw * s, min_stem if w >= 60 else min_thin)
            sp = [(_tx(x, p, s, shear), _ty(base, p, s)) for p in pts]
            polyline(sp, wpx, col)
        elif k == 'a':
            _, cx, cy, rx, ry, a0, a1, w = st
            wpx = max(w * bw * s, min_stem if w >= 60 else min_thin)
            sp = []
            for i in range(25):
                a = math.radians(a0 + (a1 - a0) * i / 24)
                px = cx + rx * math.cos(a)
                py = cy + ry * math.sin(a)
                sp.append((_tx(x, (px, py), s, shear), _ty(base, (px, py), s)))
            polyline(sp, wpx, col)
    return (adv - 70) * s


def text_w(t, size, bold=False, italic=False):
    tot = 0.0
    for ch in t:
        tot += _adv(ch, size)
    return tot + max(0, len(t) - 1) * size * 0.03


def draw_text(x, base, t, size, col, bold=False, italic=False, align='l'):
    if align != 'l':
        w = text_w(t, size, bold, italic)
        if align == 'c':
            x -= w / 2.0
        elif align == 'r':
            x -= w
    cx = x
    for ch in t:
        cx += draw_glyph(ch, cx, base, size, col, bold, italic) + size * 0.03
    return cx


def text_top(x, ytop, t, size, col, bold=False, italic=False, align='l'):
    """Draw text whose cap top sits at ytop; returns baseline used."""
    base = ytop + size * 0.72
    draw_text(x, base, t, size, col, bold, italic, align)
    return base


def wrap(t, size, maxw, bold=False):
    words = t.split(' ')
    lines = []
    cur = ''
    for wd in words:
        trial = wd if not cur else cur + ' ' + wd
        if text_w(trial, size, bold) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def para(x, ytop, w, t, size, col, bold=False, italic=False, lh=None):
    """Draw wrapped paragraph; returns y just below last line."""
    lh = lh or size * 1.28
    y = ytop
    for ln in wrap(t, size, w, bold):
        text_top(x, y, ln, size, col, bold, italic)
        y += lh
    return y


# ------------------------------------------------------- illustrations ----
# Every scene: vertical gradient sky + 2-4 drawn elements. No flat boxes.
def scene_cop31(x, y, w, h):
    vgrad(x, y, w, h, (243, 214, 158), (214, 164, 96))
    rect(x, y + h - 34, w, 34, (122, 74, 40))          # floor
    rect(x + 14, y + 8, w - 28, h - 46, (250, 240, 214))  # hall wall
    for i in range(4):                                  # windows
        rect(x + 26 + i * 74, y + 16, 52, 26, (168, 205, 225))
        rect(x + 26 + i * 74, y + 16, 52, 4, (120, 160, 180))
    # banner NO DEAL
    rect(x + w // 2 - 62, y + 12, 124, 20, WHITE)
    rect(x + w // 2 - 62, y + 12, 124, 20, RED)
    rect(x + w // 2 - 59, y + 15, 118, 14, WHITE)
    text_top(x + w // 2, y + 14, 'NO DEAL', 13, RED, bold=True, align='c')
    # long table + delegates
    rect(x + 20, y + h - 44, w - 40, 12, (94, 58, 32))
    rect(x + 20, y + h - 32, w - 40, 4, (70, 42, 22))
    cols = [(178, 34, 34), (26, 43, 74), (31, 122, 74), (176, 124, 18),
            (120, 60, 140), (30, 120, 130)]
    for i, c in enumerate(cols):
        cx = x + 44 + i * 46
        disc(cx, y + h - 52, 8, (232, 196, 160))       # head
        poly([(cx - 11, y + h - 44), (cx + 11, y + h - 44),
              (cx + 7, y + h - 62), (cx - 7, y + h - 62)], c)  # shoulders
        flag(cx - 4, y + h - 66, 9, 6, INK, c)          # tiny flag
    # gavel + papers on the table
    rect(x + w - 52, y + h - 58, 26, 12, WHITE)
    rect(x + w - 48, y + h - 55, 18, 2, LGREY)
    rect(x + w - 48, y + h - 51, 14, 2, LGREY)
    disc(x + 30, y + h - 56, 5, (60, 40, 20))


def scene_kyiv(x, y, w, h):
    vgrad(x, y, w, h, (10, 18, 38), (38, 62, 104))
    for sx, sy in [(30, 12), (90, 22), (160, 8), (230, 18), (290, 10), (200, 30), (60, 32)]:
        star4(x + sx, y + sy, 2.5, (230, 230, 200))
    disc(x + w - 34, y + 16, 11, (235, 228, 200))      # moon
    # searchlights
    poly([(x + 60, y + h), (x + 150, y + 6), (x + 170, y + 6), (x + 90, y + h)],
         (150, 175, 210))
    poly([(x + 250, y + h), (x + 300, y + 20), (x + 312, y + 20), (x + 272, y + h)],
         (140, 165, 200))
    # skyline, lit windows
    for bx, bw, bh in [(0, 52, 52), (54, 40, 68), (96, 58, 44), (156, 44, 76),
                       (202, 56, 50), (260, 68, 64)]:
        building(x + bx, y + h - bh, bw, bh, (16, 22, 40),
                 (255, 205, 90), cols=max(1, bw // 16), rws=max(2, bh // 16))
    # drones: small crosses with red lights
    for dx, dy in [(120, 26), (210, 44), (270, 30)]:
        thick_line(x + dx - 6, y + dy, x + dx + 6, y + dy, 2, (200, 200, 200))
        thick_line(x + dx, y + dy - 3, x + dx, y + dy + 3, 2, (200, 200, 200))
        disc(x + dx, y + dy, 2, (255, 60, 40))
    # fire glow + smoke over one block
    disc(x + 178, y + h - 78, 14, (255, 140, 40))
    disc(x + 178, y + h - 78, 8, (255, 220, 90))
    disc(x + 168, y + h - 92, 9, (90, 90, 100))
    disc(x + 188, y + h - 100, 11, (110, 110, 118))
    disc(x + 178, y + h - 112, 8, (130, 130, 138))


def scene_manama(x, y, w, h):
    vgrad(x, y, w, h, (58, 44, 96), (232, 145, 90))
    disc(x + w - 40, y + 18, 13, (250, 210, 130))       # low sun
    cloud(x + 60, y + 14, 16, (210, 170, 190))
    cloud(x + 200, y + 26, 12, (200, 160, 180))
    # industrial blocks + stacks
    building(x + 8, y + h - 40, 70, 40, (52, 44, 66), (255, 200, 110), cols=4, rws=2)
    building(x + 240, y + h - 34, 80, 34, (48, 40, 60), (255, 200, 110), cols=4, rws=2)
    rect(x + 92, y + h - 62, 10, 62, (40, 34, 52))
    rect(x + 108, y + h - 54, 10, 54, (40, 34, 52))
    disc(x + 97, y + h - 70, 8, (140, 140, 148))
    disc(x + 112, y + h - 62, 7, (150, 150, 158))
    # radar dish on a mast
    rect(x + 168, y + h - 46, 8, 46, (30, 30, 40))
    poly(arc_pts(x + 172, y + 52, 42, 26, 180, 360, 16) +
         arc_pts(x + 172, y + 52, 30, 16, 360, 180, 16), (220, 225, 235))
    disc(x + 172, y + 52, 5, (220, 225, 235))
    thick_line(x + 172, y + 52, x + 150, y + 78, 3, (30, 30, 40))
    # signal waves
    for r in (52, 66, 80):
        polyline(arc_pts(x + 172, y + 52, r, r * 0.62, 200, 340, 12), 2, (255, 240, 200))
    # red DENIED cross over the dish (kept clear of the DENIED label below)
    thick_line(x + 146, y + 14, x + 198, y + 66, 7, RED)
    thick_line(x + 198, y + 14, x + 146, y + 66, 7, RED)
    rect(x + w // 2 - 34, y + h - 22, 68, 14, RED)
    text_top(x + w // 2, y + h - 23, 'DENIED', 11, WHITE, bold=True, align='c')


# ---- small scenes (196 x 44) ----
def sc_icj(x, y, w, h):
    vgrad(x, y, w, h, (214, 228, 238), (178, 196, 210))
    rect(x + 28, y + 10, w - 56, 20, (250, 248, 240))
    poly([(x + 22, y + 10), (x + w // 2, y - 2), (x + w - 22, y + 10)], (200, 170, 130))
    for cx in (x + 48, x + w // 2, x + w - 48):
        rect(cx - 3, y + 12, 6, 20, (240, 236, 226))
    rect(x + 20, y + 32, w - 40, 5, (200, 170, 130))
    disc(x + w - 26, y + 12, 7, (200, 170, 90))
    thick_line(x + w - 26, y + 12, x + w - 26, y + 24, 2, (120, 100, 60))


def sc_benghazi(x, y, w, h):
    vgrad(x, y, w, h, (120, 160, 190), (40, 80, 130))
    rect(x, y + h - 14, w, 14, (30, 70, 120))
    poly([(x + 30, y + h - 14), (x + 150, y + h - 14), (x + 140, y + h - 26),
          (x + 46, y + h - 26)], (70, 80, 90))
    rect(x + 82, y + h - 40, 8, 16, (90, 100, 110))
    rect(x + 100, y + h - 36, 22, 10, (90, 100, 110))
    disc(x + 150, y + h - 30, 10, (255, 140, 40))
    disc(x + 150, y + h - 30, 5, (255, 220, 90))
    disc(x + 138, y + h - 40, 7, (120, 120, 130))
    thick_line(x + 60, y + 8, x + 66, y + 8, 2, (220, 220, 220))
    disc(x + 63, y + 8, 2, (255, 60, 40))


def sc_hk(x, y, w, h):
    vgrad(x, y, w, h, (250, 244, 228), (228, 210, 180))
    # ballot box + paper
    rect(x + 18, y + 14, 44, 26, (178, 34, 34))
    rect(x + 18, y + 14, 44, 5, (140, 22, 22))
    rect(x + 30, y + 4, 20, 12, WHITE)
    rect(x + 34, y + 7, 12, 2, LGREY)
    # donut turnout 98.79%
    cx, cy = x + w - 34, y + 22
    ring(cx, cy, 15, 5, (210, 205, 190))
    polyline(arc_pts(cx, cy, 15, 15, 90, 90 - 355, 24), 5, (31, 122, 74))
    text_top(cx, cy - 5, '99%', 8, INK, bold=True, align='c')
    # check mark
    polyline([(x + 74, y + 30), (x + 80, y + 36), (x + 92, y + 22)], 3, (31, 122, 74))


def sc_cricket(x, y, w, h):
    vgrad(x, y, w, h, (150, 200, 120), (60, 140, 70))
    rect(x + 60, y + 6, 76, h - 12, (214, 190, 140))    # pitch
    rect(x + 60, y + 6, 76, h - 12, (214, 190, 140))
    rect(x + 60, y + 6, 76, 3, WHITE)
    thick_line(x + 30, y + 12, x + 52, y + 30, 5, (150, 100, 50))  # bat
    disc(x + 150, y + 12, 4, (200, 40, 40))             # ball
    for sx in (x + 100, x + 106, x + 112):
        rect(sx, y + h - 12, 3, 9, (240, 220, 140))     # stumps
    text_top(x + 8, y + 2, '720/9', 11, WHITE, bold=True)


def sc_f1(x, y, w, h):
    vgrad(x, y, w, h, (40, 30, 70), (140, 60, 90))
    rect(x, y + h - 16, w, 16, (50, 50, 60))
    for i in range(8):
        rect(x + i * 26, y + h - 12, 14, 3, (240, 220, 60))
    # race car
    poly([(x + 60, y + 20), (x + 120, y + 20), (x + 132, y + 28), (x + 56, y + 28)],
         (210, 30, 30))
    rect(x + 84, y + 12, 26, 9, (30, 30, 40))
    disc(x + 74, y + 28, 6, (20, 20, 20))
    disc(x + 118, y + 28, 6, (20, 20, 20))
    # checkered flag
    for i in range(3):
        for j in range(3):
            rect(x + 150 + i * 7, y + 6 + j * 7, 7, 7,
                 (20, 20, 20) if (i + j) % 2 == 0 else WHITE)
    rect(x + 148, y + 6, 2, 30, (120, 100, 60))


def sc_nba(x, y, w, h):
    vgrad(x, y, w, h, (240, 180, 110), (200, 110, 50))
    rect(x + 120, y + 4, 52, 30, WHITE)                 # backboard
    rect(x + 120, y + 4, 52, 30, (240, 240, 240))
    ellipse(x + 146, y + 34, 14, 4, (230, 90, 30))      # rim
    polyline([(x + 132, y + 35), (x + 138, y + 43), (x + 154, y + 43), (x + 160, y + 35)],
             2, WHITE)
    disc(x + 40, y + 16, 10, (230, 120, 40))            # ball
    thick_line(x + 30, y + 16, x + 50, y + 16, 2, (120, 60, 20))
    thick_line(x + 40, y + 6, x + 40, y + 26, 2, (120, 60, 20))
    text_top(x + 8, y + 28, '50 PTS', 11, WHITE, bold=True)


def sc_house(x, y, w, h):
    vgrad(x, y, w, h, (200, 220, 235), (160, 185, 210))
    # capitol dome
    rect(x + 14, y + 22, 40, 16, WHITE)
    ellipse(x + 34, y + 22, 20, 12, WHITE)
    rect(x + 32, y + 4, 4, 8, (200, 170, 90))
    disc(x + 34, y + 4, 3, (200, 170, 90))
    # seats bar chart: 258 blue vs 177 red of 435
    rect(x + 70, y + 12, 116, 8, (190, 60, 60))
    rect(x + 70, y + 12, 69, 8, (40, 90, 180))
    text_top(x + 70, y + 24, '258 / 435', 10, INK, bold=True)
    text_top(x + 70, y + 2, 'HOUSE', 8, NAVY, bold=True)


def sc_ukeu(x, y, w, h):
    vgrad(x, y, w, h, (220, 228, 240), (180, 195, 215))
    # UK flag (simplified cross) + EU flag
    rect(x + 16, y + 10, 52, 26, (30, 50, 130))
    rect(x + 16, y + 20, 52, 6, WHITE)
    rect(x + 38, y + 10, 8, 26, WHITE)
    rect(x + 16, y + 22, 52, 2, (200, 40, 40))
    rect(x + 40, y + 10, 4, 26, (200, 40, 40))
    rect(x + 84, y + 10, 52, 26, (20, 40, 120))
    for i in range(8):
        a = 2 * math.pi * i / 8
        disc(x + 110 + 9 * math.cos(a), y + 23 + 8 * math.sin(a), 1.6, (250, 210, 60))
    rect(x + 150, y + 10, 2, 30, (120, 100, 60))
    rect(x + 150, y + 10, 2, 30, (120, 100, 60))
    # handshake bridge arc
    polyline(arc_pts(x + 98, y + 42, 46, 12, 180, 360, 12), 3, (31, 122, 74))


def sc_iran(x, y, w, h):
    vgrad(x, y, w, h, (60, 55, 80), (20, 18, 34))
    building(x + 10, y + 16, 46, 24, (24, 22, 36), (255, 200, 90), cols=3, rws=2)
    building(x + 130, y + 10, 56, 30, (28, 26, 42), (255, 200, 90), cols=3, rws=2)
    # pylon
    poly([(x + 92, y + 40), (x + 86, y + 6), (x + 98, y + 6)], (90, 95, 110))
    thick_line(x + 84, y + 12, x + 100, y + 12, 2, (90, 95, 110))
    # lightning bolt
    poly([(x + 118, y + 4), (x + 108, y + 22), (x + 116, y + 22), (x + 104, y + 40),
          (x + 124, y + 20), (x + 116, y + 20)], (255, 220, 60))
    text_top(x + 8, y + 2, '2h', 11, (255, 220, 60), bold=True)


def sc_bolsonaro(x, y, w, h):
    vgrad(x, y, w, h, (235, 240, 245), (200, 215, 225))
    rect(x + 14, y + 8, 60, 28, WHITE)
    rect(x + 38, y + 12, 12, 6, RED)
    rect(x + 41, y + 9, 6, 12, RED)
    # hospital bed
    rect(x + 96, y + 26, 70, 6, (120, 140, 160))
    rect(x + 96, y + 18, 6, 10, (120, 140, 160))
    rect(x + 100, y + 20, 22, 6, WHITE)
    disc(x + 110, y + 20, 5, (232, 196, 160))
    # monitor line
    polyline([(x + 176, y + 12), (x + 180, y + 18), (x + 184, y + 8), (x + 188, y + 18),
              (x + 192, y + 14)], 2, (31, 122, 74))


def sc_fbi(x, y, w, h):
    vgrad(x, y, w, h, (40, 55, 90), (18, 26, 50))
    rect(x + 14, y + 8, 52, 28, (30, 40, 60))
    for ri in range(3):
        for ci in range(4):
            disc(x + 24 + ci * 11, y + 15 + ri * 8, 2, (120, 200, 120) if (ri + ci) % 3 else (255, 200, 60))
    ring(x + 120, y + 20, 13, 4, (240, 240, 240))
    thick_line(x + 130, y + 30, x + 142, y + 40, 4, (240, 240, 240))
    poly([(x + 168, y + 8), (x + 182, y + 14), (x + 182, y + 30), (x + 175, y + 38),
          (x + 168, y + 30), (x + 168, y + 14)], (200, 170, 60))


def sc_cikande(x, y, w, h):
    vgrad(x, y, w, h, (90, 80, 80), (50, 40, 40))
    rect(x + 14, y + 20, 90, 20, (110, 110, 115))
    poly([(x + 14, y + 20), (x + 34, y + 8), (x + 54, y + 20)], (140, 140, 145))
    poly([(x + 54, y + 20), (x + 74, y + 8), (x + 94, y + 20)], (140, 140, 145))
    rect(x + 118, y + 10, 10, 30, (90, 90, 95))
    # flames + smoke
    poly([(x + 40, y + 20), (x + 52, y + 2), (x + 60, y + 12), (x + 70, y + 0), (x + 80, y + 20)],
         (255, 140, 30))
    poly([(x + 52, y + 20), (x + 58, y + 8), (x + 66, y + 20)], (255, 220, 90))
    disc(x + 122, y + 2, 8, (120, 120, 128))
    disc(x + 134, y + -2, 7, (135, 135, 142))
    disc(x + 150, y + 10, 6, (90, 90, 96))


def sc_gaza(x, y, w, h):
    vgrad(x, y, w, h, (235, 190, 140), (150, 110, 90))
    building(x + 10, y + 14, 44, 26, (90, 75, 65), (255, 210, 130), cols=3, rws=2)
    building(x + 60, y + 8, 40, 32, (80, 66, 58), (255, 210, 130), cols=2, rws=3)
    disc(x + 112, y + 8, 9, (110, 110, 118))
    disc(x + 124, y + 2, 7, (125, 125, 132))
    # ambulance
    rect(x + 128, y + 24, 52, 14, WHITE)
    rect(x + 128, y + 24, 14, 14, (220, 220, 220))
    rect(x + 150, y + 27, 10, 4, RED)
    rect(x + 153, y + 24, 4, 10, RED)
    disc(x + 140, y + 38, 4, (20, 20, 20))
    disc(x + 168, y + 38, 4, (20, 20, 20))


def sc_tennis(x, y, w, h):
    vgrad(x, y, w, h, (60, 110, 170), (30, 70, 130))
    rect(x, y + 22, w, 18, (40, 130, 90))               # court
    rect(x, y + 22, w, 2, WHITE)
    thick_line(x + w // 2, y + 6, x + w // 2, y + 40, 2, WHITE)  # net
    disc(x + 40, y + 12, 5, (220, 240, 60))             # ball
    # trophy
    poly([(x + 150, y + 6), (x + 168, y + 6), (x + 164, y + 20), (x + 154, y + 20)],
         (220, 180, 60))
    rect(x + 157, y + 20, 4, 8, (220, 180, 60))
    rect(x + 150, y + 28, 18, 3, (220, 180, 60))


def sc_sparta(x, y, w, h):
    vgrad(x, y, w, h, (140, 175, 200), (60, 100, 140))
    rect(x, y + h - 12, w, 12, (35, 75, 120))
    poly([(x + 20, y + h - 12), (x + 24, y + h - 12), (x + 30, y + h - 6),
          (x + 44, y + h - 6)], (200, 220, 235))
    # cargo ship + containers
    poly([(x + 70, y + 22), (x + 150, y + 22), (x + 142, y + 34), (x + 78, y + 34)],
         (60, 65, 75))
    rect(x + 84, y + 10, 18, 12, (200, 80, 60))
    rect(x + 104, y + 10, 18, 12, (60, 130, 90))
    rect(x + 126, y + 10, 14, 12, (220, 180, 60))
    disc(x + 146, y + 8, 7, (120, 120, 130))
    # tow line to tug
    thick_line(x + 70, y + 26, x + 40, y + 32, 2, (240, 230, 200))
    rect(x + 22, y + 28, 18, 8, (220, 140, 40))
    rect(x + 26, y + 22, 8, 6, (240, 240, 240))


SMALL_SCENES = {4: sc_icj, 5: sc_benghazi, 6: sc_hk, 7: sc_cricket, 8: sc_f1,
                9: sc_nba, 10: sc_house, 11: sc_ukeu, 12: sc_iran,
                13: sc_bolsonaro, 14: sc_fbi, 15: sc_cikande, 16: sc_gaza,
                17: sc_tennis, 18: sc_sparta}
LEAD_SCENES = {1: scene_cop31, 2: scene_kyiv, 3: scene_manama}

# ------------------------------------------------------- world map --------
# Rough flat continents (screen polygons on the map panel).
CONTINENTS = [
    [(22, 22), (52, 8), (86, 12), (96, 26), (78, 34), (66, 44), (48, 40), (28, 36)],   # N America
    [(72, 52), (92, 50), (100, 62), (92, 78), (80, 74), (70, 62)],                      # S America
    [(200, 30), (222, 18), (240, 24), (238, 44), (226, 58), (210, 52), (202, 40)],       # Europe
    [(228, 58), (252, 52), (268, 60), (272, 78), (252, 92), (236, 80), (228, 68)],       # Africa
    [(262, 16), (330, 8), (380, 14), (392, 30), (360, 44), (330, 52), (300, 40), (272, 30)],  # Asia
    [(382, 62), (404, 58), (414, 68), (400, 78), (386, 72)],                             # Oceania
]
# (story, lon, lat, label dx, dy) -- offsets keep the Europe / Middle East
# cluster readable with short leader lines.
PINS = [
    (1, 30.7, 36.9, 14, 12), (2, 30.5, 50.5, 10, -12), (3, 50.6, 26.2, 16, 8),
    (4, 4.3, 52.1, -8, -12), (5, 20.1, 32.1, 4, 12), (6, 114.2, 22.3, 10, 8),
    (7, 174.8, -41.3, -6, -12), (8, -115.1, 36.2, -10, -10), (9, -98.5, 29.4, -4, 12),
    (10, -77.0, 38.9, 12, -10), (11, -0.1, 51.5, -14, 6), (12, 51.4, 35.7, 12, -10),
    (13, -47.9, -15.8, -10, 10), (14, -77.0, 38.9, 22, 8), (15, 106.2, -6.3, 8, 10),
    (16, 34.5, 31.5, 14, -8), (17, 7.7, 45.1, -12, -12), (18, 24.0, 60.0, 6, -12),
]
REGION_COL = {'EUROPE': (31, 111, 139), 'MIDDLE EAST': (179, 57, 46),
              'NORTH AMERICA': (46, 90, 168), 'SOUTH AMERICA': (46, 125, 79),
              'EAST ASIA': (142, 68, 173), 'SOUTH ASIA': (211, 84, 0),
              'SOUTHEAST ASIA': (22, 160, 133), 'AFRICA': (183, 149, 11),
              'OCEANIA': (93, 109, 126), 'WORLD': (52, 73, 94)}
PIN_REGION = {1: 'WORLD', 2: 'EUROPE', 3: 'MIDDLE EAST', 4: 'WORLD',
              5: 'AFRICA', 6: 'EAST ASIA', 7: 'EAST ASIA', 8: 'NORTH AMERICA',
              9: 'NORTH AMERICA', 10: 'NORTH AMERICA', 11: 'EUROPE',
              12: 'MIDDLE EAST', 13: 'SOUTH AMERICA', 14: 'NORTH AMERICA',
              15: 'SOUTHEAST ASIA', 16: 'MIDDLE EAST', 17: 'EUROPE', 18: 'WORLD'}


def draw_map(x, y, w, h):
    rect(x, y, w, h, (220, 231, 238))
    for c in CONTINENTS:
        pts = [(x + px * w / 430.0, y + py * h / 100.0) for (px, py) in c]
        poly(pts, (232, 220, 192))
    # graticule
    for gx in range(1, 6):
        hline(x + gx * w // 6, y, 0, (0, 0, 0)) if False else None
    for num, lon, lat, dx, dy in PINS:
        px = x + (lon + 180.0) / 360.0 * w
        py = y + (85.0 - lat) / 145.0 * h
        lx, ly = px + dx, py + dy
        if dx or dy:
            thick_line(px, py, lx, ly, 1, (90, 90, 90))
        disc(lx, ly, 7, REGION_COL[PIN_REGION[num]])
        disc(lx, ly, 7, REGION_COL[PIN_REGION[num]])
        text_top(lx, ly - 5, str(num), 8, WHITE, bold=True, align='c')


# ------------------------------------------------------- content ---------
BADGE_COL = {'CONFIRMED': GREEN, 'CLAIM': (180, 80, 20),
             'REPORTED': (60, 90, 160), 'PENDING': GREY}

LEADS = [
    dict(num=1, loc='ANTALYA, TURKIYE · CLIMATE', badge='CONFIRMED',
         head='COP31 ends with no deal',
         body=('The EU and 130 nations reject a text that never names fossil '
               'fuels — the first COP since 2000 to end with no cover '
               'decision, after 44+ hours overtime. The draft admits a 1.5C '
               'overshoot and drops a $120bn adaptation target.'),
         src='(Reuters, BBC, UNFCCC)'),
    dict(num=2, loc='KYIV REGION, UKRAINE · WAR', badge='CONFIRMED',
         head='Russia fires 186 drones at Ukraine',
         body=('186 drones overnight — 72 jet-powered Shaheds among them — '
               'and 161 shot down or jammed, with hits at 18 sites. In '
               'Dymer, a five-storey block is hit at about 05:30; one '
               'stairwell collapses, 2 dead, 14 missing, 9 rescued.'),
         src='(Ukrainian Air Force via Reuters)'),
    dict(num=3, loc='MANAMA, BAHRAIN · IRAN', badge='CLAIM',
         head='Iran claims two US radars hit; Bahrain denies it',
         body=("The IRGC says it destroyed two US Patriot radars at "
               "Al-Riffa and Awali in an operation dubbed 'Ya Umm al-Banin'. "
               'Bahrain says a civilian industrial site in Sitra burned, 2 '
               'hurt. A US official tells CBS no US personnel or facilities '
               'were damaged.'),
         src='(IRGC, CBS, Al Jazeera)'),
]

SMALL = [
    (4, 'THE HAGUE · WORLD COURT', 'CONFIRMED', 'ICJ: Myanmar committed genocide',
     'Rohingya welcome it; want to go home.', '(Reuters, AP)'),
    (5, 'BENGHAZI, LIBYA · CONFLICT', 'REPORTED', 'Sea drones hit Russian warship at Benghazi',
     'Ukrainian drones strike a corvette.', '(Wires)'),
    (6, 'HONG KONG · ELECTION', 'CONFIRMED', 'Record turnout in committee polls',
     '5,640 of 5,709 voters; 856 candidates.', '(SCMP)'),
    (7, 'WELLINGTON, NZ · CRICKET', 'CONFIRMED', 'India declare on a record 720/9',
     'Highest Test total ever in NZ. Rahul 136.', '(ESPNcricinfo)'),
    (8, 'LAS VEGAS · FORMULA 1', 'CONFIRMED', 'Verstappen wins the Las Vegas GP',
     'Beats Norris on the Strip at night.', '(FIA)'),
    (9, 'SAN ANTONIO, USA · NBA', 'CONFIRMED', 'Wembanyama scores 50 as Spurs roll on',
     '50 pts, 19 rebounds, 5 blocks; 114-91.', '(AP)'),
    (10, 'WASHINGTON, USA · POLITICS', 'CONFIRMED', 'Democrats win biggest House majority since 1992',
     'Hubbard beats Foxx; Dems hold 258 seats.', '(AP)'),
    (11, 'LONDON · EUROPE', 'CONFIRMED', 'UK and EU strike post-Brexit deals',
     'Trade and travel deals rebuild ties.', '(AP, Reuters)'),
    (12, 'TEHRAN, IRAN · ENERGY', 'CONFIRMED', 'Iran begins rationing electricity',
     'Rolling cuts up to 2 hours a day.', '(Wires)'),
    (13, 'BRASILIA, BRAZIL · HEALTH', 'CONFIRMED', 'Bolsonaro in intensive care',
     'Acute bowel obstruction; stable. Age 71.', '(Reuters)'),
    (14, 'WASHINGTON, USA · CYBER', 'REPORTED', 'FBI probes apparent hack of its crime database',
     'State pauses gun-dealer checks.', '(AP)'),
    (15, 'CIKANDE, INDONESIA · FIRE', 'CONFIRMED', 'Candy-factory fire in Cikande: 3 dead; 36 missing',
     'Fire sweeps Bantam plant; search on.', '(Detiknews)'),
    (16, 'GAZA CITY · CONFLICT', 'REPORTED', 'Israeli fire kills four in Gaza',
     'Drone strike hits a food vehicle.', '(Gaza civil defence)'),
    (17, 'TURIN, ITALY · TENNIS', 'CONFIRMED', 'Alcaraz wins first ATP Finals',
     'Beats Zverev in the Turin final.', '(ATP)'),
    (18, 'GULF OF FINLAND · SEA', 'CONFIRMED', 'Sparta II towed home after drone strike',
     'Hit by a drone, towed to Russian waters.', '(Wires)'),
]

ALSO = [
    'Europe: Estonia to shut five Russia border crossings 1 Dec, after a sabotage bid (Reuters)',
    'Europe: Denmark expels a Russian attache over an alleged plot against a Ukrainian (Guardian)',
    'South Asia: Nepal PM Shah lands in Delhi on first visit; meets Modi Monday (IANS)',
    'East Asia: Chinese bomber turns back 170 km from Manila (AP)',
    'Southeast Asia: Philippines M5.9 quake, 898 km deep, off Palawan (EMSC)',
    'East Asia: Japan poll: record 52% feel friendly to South Korea (Ipsos)',
    'South Asia: India and China hold fresh military talks over Arunachal frontier (Wires)',
    'Africa: Somalia expels UAE ambassador, recalls its envoy (Wires)',
    'Africa: Sudan: RSF accused of killing civilians, incl. 3 children, in W. Kordofan (Claim)',
    'Africa: Kenya discharges its last Ebola patient (Wires)',
    'Africa: Drone strikes damage UN facility in Khartoum; 4 killed (Wires)',
    'Oceania: Marles rejects US report on AUKUS subs (ABC)',
    'Oceania: Melbourne — 70 years since the 1956 Olympics opened (ABC)',
    'North America: Trump seeks \'permanent\' Israel deal; Doha talks to mediators (Al Jazeera)',
    'Southeast Asia: EU and Indonesia sign trade deal after ten years (DW)',
    'Africa: Sudan army retakes ~30 towns in Kordofan (FT)',
    'South Asia: Bangladesh: 30 Awami League homes set on fire (Local)',
    'Middle East: Lebanon: Aoun demands Israel withdrawal (Al Jazeera)',
    'World: Scientists sequence a whale\'s full genome from breath collected by drone (Wires)',
    'Middle East: Saudi Arabia and Yemen\'s Houthis exchange fire (Wires)',
]

DATECHECK = [
    '400-drone, 110-missile barrage (19-20 Nov)',
    '148-drone night, Kryvyi Rih double-tap (20-21 Nov)',
    "'El Chapo Isidro' captured (Sat 21 Nov)",
    'Bayelsa boat capsizes, 24 dead (Fri 21 Nov)',
    'Gaza aid-van strike (Sat 21 Nov)',
    'Nvidia SEC probe first reported (Fri 20 Nov)',
    'Saudi strikes on Hodeidah (20-21 Nov)',
    'Peru earthquake (Fri 20 Nov)',
    'Copa Sudamericana final (Sat 21 Nov)',
    'BepiColombo enters Mercury orbit (Sat 21 Nov)',
    'Russian missiles entered Poland (Fri 20 Nov)',
    'Rugby: England beat NZ 37-12 (Sat 21 Nov)',
    'Arsenal 2-2 Newcastle; Leeds 4-1 Chelsea (Sat 21 Nov)',
]

REGIONS = [('EUROPE', 5), ('MIDDLE EAST', 5), ('NORTH AMERICA', 5),
           ('SOUTH AMERICA', 1), ('EAST ASIA', 3), ('SOUTH ASIA', 4),
           ('SOUTHEAST ASIA', 3), ('AFRICA', 6), ('OCEANIA', 2), ('WORLD', 4)]

NUMBERS = [('186', 'drones fired at Ukraine overnight'),
           ('161', 'downed or suppressed by air defence'),
           ('258', 'House seats, most since 1992'),
           ('$120bn', 'adaptation target dropped at COP31'),
           ('720/9', "India's record Test total in NZ"),
           ('98.79%', 'HK Election Committee turnout')]

TIMELINE = ('THE DAY IN UTC   01:00 HK polls open  ·  03:00 COP31 objections close  ·  '
            '05:11 Hamas seeks talks  ·  05:30 Las Vegas GP ends  ·  '
            '06:00 COP31 approval due  ·  07:30 Approval slips again')


# ------------------------------------------------------- compose --------
def compose():
    # top navy bar
    rect(0, 0, W, 16, NAVY)
    text_top(10, 3, 'THE WORLD IN ONE DAY', 10, WHITE, bold=True)
    draw_text(W - 10, 3 + 10 * 0.72,
              '38 STORIES · 10 REGIONS · EVERY ONE DATED SUNDAY 22 NOVEMBER 2026',
              10, WHITE, bold=True, align='r')
    # title, two lines
    text_top(W // 2, 20, 'Sunday 22 November 2026', 54, INK, bold=True, align='c')
    t2 = "No Deal in Antalya, 186 Drones Over Kyiv, and Hong Kong's 98.79% Vote"
    sz = 26
    while text_w(t2, sz, bold=True) > 1000 and sz > 18:
        sz -= 1
    text_top(W // 2, 76, t2, sz, INK, bold=True, align='c')
    # subhead, red italic serif
    text_top(W // 2, 106,
             "COP31 ends with no deal · 186 drones over Ukraine in the night · "
             "Iran's radar claim meets Bahrain's denial",
             14, RED, italic=True, align='c')
    hline(8, 124, 1008, INK)
    # numbers strip: 6 boxes
    bx = 8
    for num, lab in NUMBERS:
        rect(bx, 128, 165, 36, WHITE)
        rect(bx, 128, 165, 1, LGREY); rect(bx, 163, 165, 1, LGREY)
        rect(bx, 128, 1, 36, LGREY); rect(bx + 164, 128, 1, 36, LGREY)
        text_top(bx + 82, 130, num, 24, RED, bold=True, align='c')
        ll = wrap(lab, 9, 155)
        ly = 152
        for ln in ll[:1]:
            text_top(bx + 82, ly, ln, 9, INK, align='c')
        bx += 168
    # region tabs
    tx = 8
    widths = [text_w(n + ' ' + str(c), 9.5, bold=True) + 16 for n, c in REGIONS]
    tot = sum(widths)
    scale = 1008.0 / tot  # stretch the ten tabs to fill the full width
    for (name, cnt), wd in zip(REGIONS, widths):
        wd = wd * scale
        rect(tx, 168, wd, 17, REGION_COL[name])
        text_top(tx + wd / 2, 171, name + ' ' + str(cnt), 9.5, WHITE, bold=True, align='c')
        tx += wd
    # timeline strip
    rect(0, 188, W, 16, NAVY2)
    text_top(W // 2, 190, TIMELINE, 9.5, WHITE, align='c')
    # ---- 3 lead stories ----
    for i, L in enumerate(LEADS):
        x = 8 + i * 340
        w = 328
        LEAD_SCENES[L['num']](x, 206, w, 100)
        text_top(x, 309, str(L['num']) + ' · ' + L['loc'], 9.5, NAVY, bold=True)
        bw = text_w(L['badge'], 8.5, bold=True) + 10
        rect(x + w - bw, 308, bw, 13, BADGE_COL[L['badge']])
        text_top(x + w - bw / 2, 309, L['badge'], 8.5, WHITE, bold=True, align='c')
        yy = para(x, 324, w, L['head'], 20, INK, bold=True, lh=23)
        para(x, 372, w, L['body'], 11.5, INK, lh=14.5)
        text_top(x, 436, L['src'], 9, GREY, italic=True)
    hline(8, 450, 1008, LGREY)
    # ---- 15 small stories, 5 cols x 3 rows ----
    for idx, (num, loc, badge, head, body, src) in enumerate(SMALL):
        r = idx // 5
        c = idx % 5
        x = 8 + c * 204
        y = 454 + r * 106
        w = 196
        SMALL_SCENES[num](x, y, w, 42)
        text_top(x, y + 45, str(num) + ' ' + loc, 8.5, NAVY, bold=True)
        draw_text(x + w, y + 45 + 8.5 * 0.72, badge, 8, BADGE_COL[badge],
                  bold=True, align='r')
        para(x, y + 56, w, head, 12, INK, bold=True, lh=14)
        text_top(x, y + 85, body, 9.5, INK)
        text_top(x, y + 96, src, 8, GREY, italic=True)
    # ---- ALSO list ----
    text_top(8, 776, 'ALSO ON SUNDAY 22 NOVEMBER — 20 MORE STORIES', 12, NAVY, bold=True)
    hline(8, 792, 1008, INK)
    for i, item in enumerate(ALSO):
        col = i // 10
        row = i % 10
        x = 8 + col * 512
        y = 796 + row * 10
        n = str(19 + i)
        text_top(x, y, n, 9, RED, bold=True)
        nx = x + text_w(n, 9, bold=True) + 5
        text_top(nx, y, item, 9, INK)
    # ---- map + date check ----
    text_top(8, 898, 'WHERE IT HAPPENED', 10, NAVY, bold=True)
    draw_map(8, 910, 500, 76)
    rect(516, 896, 500, 90, WHITE)
    rect(516, 896, 500, 2, RED); rect(516, 984, 500, 2, RED)
    rect(516, 896, 2, 90, RED); rect(1014, 896, 2, 90, RED)
    text_top(524, 899, 'DATE CHECK — LEFT OUT ON PURPOSE: OTHER DAYS', 10, RED, bold=True)
    for i, item in enumerate(DATECHECK):
        col = i // 7
        row = i % 7
        x = 524 + col * 246
        y = 914 + row * 10
        text_top(x, y, 'x', 8, RED, bold=True)
        text_top(x + 9, y, item, 8, INK)
    # ---- footer ----
    hline(8, 992, 1008, LGREY)
    text_top(W // 2, 996,
             'Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, UNFCCC, '
             'Kyiv Post, SCMP, ESPNcricinfo, Detiknews',
             9, GREY, align='c')
    text_top(W // 2, 1007,
             "CONFIRMED = 2+ outlets  ·  CLAIM = one side's claim  ·  "
             'REPORTED = one source  ·  PENDING = not settled  ·  '
             'Scenes are drawn illustrations · Wires read to press time',
             8.5, GREY, align='c')


def main():
    compose()
    out = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    path = os.path.join(out, 'entry.png')
    n = write_png(path)
    print('wrote', path, n, 'bytes')


if __name__ == '__main__':
    main()
