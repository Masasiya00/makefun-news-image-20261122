#!/usr/bin/env python3
"""makefun-news-image-20261122 -- draws "Sunday 22 November 2026: The World
in One Day" as a 1024x1024 newspaper front page, entirely in code.

Pure Python 3 standard library: hand-written rasterizer, hand-written 5x7
bitmap font, hand-written PNG encoder. No network, no files read, no clock,
no randomness -- two runs produce byte-identical output.
"""
import os
import struct
import zlib
from math import sqrt

W = 1024
H = 1024

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 232)
INK = (20, 20, 20)
NAVY = (26, 43, 74)
NAVY_DK = (18, 30, 54)
RED = (166, 30, 30)
RED_BR = (192, 57, 43)
GOLD = (212, 175, 105)
GRAY = (107, 107, 107)
GRAY_LT = (150, 145, 130)
RULE = (201, 194, 174)
CREAM = (238, 232, 214)
SEA = (215, 226, 230)
LAND = (168, 184, 154)
GREEN = (46, 110, 70)
TEAL = (31, 122, 109)
BLUE = (43, 94, 167)
ORANGE = (196, 122, 18)
PURPLE = (107, 74, 158)
AF_GREEN = (74, 122, 46)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


class Canvas:
    def __init__(self, w=W, h=H, bg=PAPER):
        self.w = w
        self.h = h
        self.px = bytearray(bg[0:1] * 3 * w * h)
        # bytearray(bg * w * h) would repeat the 3-byte pattern correctly
        # only if bg bytes repeat; build it properly:
        row = bytes(bg) * w
        self.px = bytearray(row * h)

    def rect(self, x, y, w, h, c):
        x0 = max(0, int(x)); y0 = max(0, int(y))
        x1 = min(self.w, int(x + w)); y1 = min(self.h, int(y + h))
        if x1 <= x0 or y1 <= y0:
            return
        span = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            off = (yy * self.w + x0) * 3
            self.px[off:off + len(span)] = span

    def hline(self, x, y, w, c, t=1):
        self.rect(x, y, w, t, c)

    def vline(self, x, y, h, c, t=1):
        self.rect(x, y, t, h, c)

    def line(self, x0, y0, x1, y1, c, t=1):
        dx = x1 - x0; dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        r = max(1, t // 2)
        for i in range(steps + 1):
            x = x0 + dx * i / steps
            y = y0 + dy * i / steps
            self.circle(int(round(x)), int(round(y)), r, c)

    def circle(self, cx, cy, r, c):
        r = int(r)
        if r <= 0:
            return
        for dy in range(-r, r + 1):
            dx = int(sqrt(r * r - dy * dy))
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def disc(self, cx, cy, r, c):
        self.circle(cx, cy, r, c)

    def ellipse(self, cx, cy, rx, ry, c):
        rx = int(rx); ry = int(ry)
        if rx <= 0 or ry <= 0:
            return
        for dy in range(-ry, ry + 1):
            f = 1.0 - (dy * dy) / float(ry * ry)
            dx = int(rx * sqrt(max(0.0, f)))
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, c, t=2):
        r = int(r)
        for dy in range(-r, r + 1):
            dxo = int(sqrt(r * r - dy * dy))
            ri = r - t
            if abs(dy) < ri:
                dxi = int(sqrt(ri * ri - dy * dy))
                self.rect(cx - dxo, cy + dy, dxo - dxi, 1, c)
                self.rect(cx + dxi + 1, cy + dy, dxo - dxi, 1, c)
            else:
                self.rect(cx - dxo, cy + dy, 2 * dxo + 1, 1, c)

    def poly(self, pts, c):
        """Scanline fill of a simple polygon."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, min(ys)); y1 = min(self.h - 1, max(ys))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x0, y0p = pts[i]
                x1, y1p = pts[(i + 1) % n]
                if (y0p <= y < y1p) or (y1p <= y < y0p):
                    if y1p != y0p:
                        x = x0 + (y - y0p) * (x1 - x0) / (y1p - y0p)
                        xs.append(x)
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = int(round(xs[k])); xb = int(round(xs[k + 1]))
                if xb >= xa:
                    self.rect(xa, y, xb - xa + 1, 1, c)

    def tri(self, x0, y0, x1, y1, x2, y2, c):
        self.poly([(x0, y0), (x1, y1), (x2, y2)], c)


# ------------------------------------------------------------- bitmap font
# 5x7 glyphs, each row a 5-bit value, bit 4 = leftmost pixel. Written by hand.
FONT = {
    'A': [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    'B': [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    'C': [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
    'D': [0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E],
    'E': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    'F': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    'G': [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F],
    'H': [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    'I': [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    'J': [0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C],
    'K': [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    'L': [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    'M': [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
    'N': [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
    'O': [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    'P': [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
    'Q': [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D],
    'R': [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    'S': [0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E],
    'T': [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    'U': [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    'V': [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
    'W': [0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11],
    'X': [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
    'Y': [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    'Z': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
    'a': [0x00, 0x00, 0x0E, 0x01, 0x0F, 0x11, 0x0F],
    'b': [0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x1E],
    'c': [0x00, 0x00, 0x0E, 0x10, 0x10, 0x10, 0x0E],
    'd': [0x01, 0x01, 0x0F, 0x11, 0x11, 0x11, 0x0F],
    'e': [0x00, 0x00, 0x0E, 0x11, 0x1F, 0x10, 0x0E],
    'f': [0x06, 0x08, 0x08, 0x1E, 0x08, 0x08, 0x08],
    'g': [0x00, 0x0F, 0x11, 0x11, 0x0F, 0x01, 0x0E],
    'h': [0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x11],
    'i': [0x04, 0x00, 0x0C, 0x04, 0x04, 0x04, 0x0E],
    'j': [0x02, 0x00, 0x06, 0x02, 0x02, 0x12, 0x0C],
    'k': [0x10, 0x10, 0x12, 0x14, 0x18, 0x14, 0x12],
    'l': [0x0C, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    'm': [0x00, 0x00, 0x1A, 0x15, 0x15, 0x15, 0x15],
    'n': [0x00, 0x00, 0x1E, 0x11, 0x11, 0x11, 0x11],
    'o': [0x00, 0x00, 0x0E, 0x11, 0x11, 0x11, 0x0E],
    'p': [0x00, 0x00, 0x1E, 0x11, 0x11, 0x1E, 0x10],
    'q': [0x00, 0x00, 0x0F, 0x11, 0x11, 0x0F, 0x01],
    'r': [0x00, 0x00, 0x16, 0x19, 0x10, 0x10, 0x10],
    's': [0x00, 0x00, 0x0F, 0x10, 0x0E, 0x01, 0x1E],
    't': [0x08, 0x08, 0x1E, 0x08, 0x08, 0x09, 0x06],
    'u': [0x00, 0x00, 0x11, 0x11, 0x11, 0x13, 0x0D],
    'v': [0x00, 0x00, 0x11, 0x11, 0x11, 0x0A, 0x04],
    'w': [0x00, 0x00, 0x11, 0x11, 0x15, 0x15, 0x0A],
    'x': [0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11],
    'y': [0x00, 0x00, 0x11, 0x11, 0x0F, 0x01, 0x0E],
    'z': [0x00, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F],
    '0': [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    '1': [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    '2': [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F],
    '3': [0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E],
    '4': [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    '5': [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    '6': [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E],
    '7': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
    '8': [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
    '9': [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C],
    ' ': [0, 0, 0, 0, 0, 0, 0],
    '.': [0, 0, 0, 0, 0, 0x0C, 0x0C],
    ',': [0, 0, 0, 0, 0x0C, 0x04, 0x08],
    ':': [0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0],
    ';': [0, 0x0C, 0x0C, 0, 0x0C, 0x04, 0x08],
    '!': [0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04],
    '?': [0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04],
    "'": [0x04, 0x04, 0x08, 0, 0, 0, 0],
    '"': [0x0A, 0x0A, 0x0A, 0, 0, 0, 0],
    '(': [0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02],
    ')': [0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08],
    '-': [0, 0, 0, 0x1F, 0, 0, 0],
    '%': [0x19, 0x19, 0x02, 0x04, 0x08, 0x13, 0x13],
    '/': [0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10],
    '$': [0x04, 0x0F, 0x14, 0x0E, 0x05, 0x1E, 0x04],
    '\u00b7': [0, 0, 0, 0x0C, 0x0C, 0, 0],
    '&': [0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D],
    '+': [0, 0x04, 0x04, 0x1F, 0x04, 0x04, 0],
    '=': [0, 0, 0x1F, 0, 0x1F, 0, 0],
    '*': [0, 0x04, 0x15, 0x0E, 0x15, 0x04, 0],
    '#': [0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A],
    '@': [0x0E, 0x11, 0x01, 0x0D, 0x15, 0x15, 0x0E],
    '<': [0x02, 0x04, 0x08, 0x10, 0x08, 0x04, 0x02],
    '>': [0x08, 0x04, 0x02, 0x01, 0x02, 0x04, 0x08],
    '_': [0, 0, 0, 0, 0, 0, 0x1F],
    '[': [0x0E, 0x08, 0x08, 0x08, 0x08, 0x08, 0x0E],
    ']': [0x0E, 0x02, 0x02, 0x02, 0x02, 0x02, 0x0E],
    '~': [0, 0, 0, 0x0E, 0x15, 0, 0],
    '\u00d7': [0, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0],
    '\u2022': [0, 0, 0x0C, 0x1E, 0x1E, 0x0C, 0],
}

ALIASES = {'\u2014': '-', '\u2013': '-', '\u2019': "'", '\u2018': "'",
           '\u201c': '"', '\u201d': '"', '\u00e9': 'e', '\u2212': '-'}


def norm_char(ch):
    return ALIASES.get(ch, ch)


def text_w(s, scale, track=6.0):
    return len(s) * track * scale


def draw_text(cv, x, y, s, scale, color, bold=False, track=6.0):
    """Draw text at (x, y) top-left; scale may be fractional."""
    cx = float(x)
    dx = 1 if bold else 0
    for ch in s:
        g = FONT.get(norm_char(ch))
        if g is None:
            g = FONT['?']
        for gy, row in enumerate(g):
            for gx in range(5):
                if (row >> (4 - gx)) & 1:
                    px0 = int(cx + gx * scale)
                    px1 = int(cx + (gx + 1) * scale)
                    py0 = int(y + gy * scale)
                    py1 = int(y + (gy + 1) * scale)
                    if px1 > px0 and py1 > py0:
                        cv.rect(px0, py0, px1 - px0, py1 - py0, color)
                        if dx:
                            cv.rect(px0 + dx, py0, px1 - px0, py1 - py0, color)
        cx += track * scale
    return cx


def draw_text_c(cv, cx, y, s, scale, color, bold=False, track=6.0):
    """Centered text."""
    w = text_w(s, scale, track)
    return draw_text(cv, cx - w / 2, y, s, scale, color, bold, track)


def wrap(s, max_w, scale, track=6.0):
    """Greedy word wrap; returns list of lines."""
    words = s.split(' ')
    lines = []
    cur = ''
    for wd in words:
        trial = wd if not cur else cur + ' ' + wd
        if text_w(trial, scale, track) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def draw_lines(cv, x, y, lines, scale, color, lh, bold=False, track=6.0):
    for i, ln in enumerate(lines):
        draw_text(cv, x, y + i * lh, ln, scale, color, bold, track)


# ------------------------------------------------------------- PNG encoder
def chunk(typ, data):
    out = struct.pack('>I', len(data)) + typ + data
    out += struct.pack('>I', zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def encode_png(cv):
    ihdr = struct.pack('>IIBBBBB', cv.w, cv.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]
    idat = zlib.compress(bytes(raw), 9)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) +
            chunk(b'IDAT', idat) + chunk(b'IEND', b''))


# ------------------------------------------------------------ illustrations
# Every scene is drawn from flat shapes. (x, y) = top-left of its box.

def tag(cv, x, y, s, bg=RED):
    """Small red tag label on top-left of an illustration."""
    w = int(text_w(s, 1.0, 5.5) + 10)
    cv.rect(x, y, w, 13, bg)
    draw_text(cv, x + 5, y + 3, s, 1.0, WHITE, bold=True, track=5.5)


def drone(cv, cx, cy, s=1.0):
    """Small quadcopter silhouette."""
    b = int(7 * s)
    cv.rect(cx - b, cy - 2, 2 * b, 4, (30, 30, 34))
    cv.rect(cx - b - 6, cy - 4, 6, 2, (30, 30, 34))
    cv.rect(cx + b, cy - 4, 6, 2, (30, 30, 34))
    cv.rect(cx - b - 6, cy + 3, 6, 2, (30, 30, 34))
    cv.rect(cx + b, cy + 3, 6, 2, (30, 30, 34))
    cv.circle(cx, cy, 2, (212, 175, 105))


def flames(cv, x, y, w, h):
    """Simple flame cluster inside box (x,y,w,h)."""
    n = max(2, w // 12)
    for i in range(n):
        fx = x + 3 + i * (w - 6) // max(1, n - 1)
        fh = h - (i % 2) * h // 3
        cv.tri(fx - 5, y + h, fx, y + h - fh, fx + 5, y + h,
               (232, 120, 20) if i % 2 else (240, 180, 30))
    cv.rect(x, y + h - 3, w, 3, (200, 60, 20))


def ill_lead1(cv, x, y, w, h):
    """Night sky over Kyiv: drones, apartment block, searchlight."""
    cv.rect(x, y, w, h, NAVY_DK)
    for sx, sy in [(18, 10), (60, 22), (120, 8), (180, 18), (240, 6),
                   (290, 24), (40, 40), (150, 32), (210, 40), (270, 12)]:
        cv.rect(x + sx, y + sy, 2, 2, (220, 220, 200))
    drone(cv, x + 70, y + 26, 1.2)
    drone(cv, x + 150, y + 16, 1.0)
    drone(cv, x + 235, y + 30, 1.3)
    drone(cv, x + 285, y + 14, 0.9)
    # searchlight beam
    cv.poly([(x + 300, y + h), (x + 262, y + 12), (x + 282, y + 12)],
            (200, 210, 230))
    # apartment block, damaged side
    cv.rect(x + 30, y + 42, 110, h - 42, (52, 58, 74))
    cv.poly([(x + 30, y + 42), (x + 140, y + 42), (x + 140, y + 58),
             (x + 118, y + 50), (x + 96, y + 62), (x + 74, y + 50),
             (x + 52, y + 60), (x + 30, y + 52)], (38, 42, 56))
    # lit windows, two rows
    for wy in range(2):
        for wx in range(5):
            cv.rect(x + 40 + wx * 20, y + 60 + wy * 12, 10, 8,
                    (255, 210, 90) if (wx + wy) % 3 else (90, 100, 120))
    # fire at the broken side
    flames(cv, x + 96, y + h - 22, 44, 22)
    # street
    cv.rect(x, y + h - 6, w, 6, (24, 26, 34))


def ill_lead2(cv, x, y, w, h):
    """COP31 hall: delegates at a long table, globe, COP31 podium."""
    cv.rect(x, y, w, h, (223, 232, 221))
    # globe top-left
    cv.circle(x + 34, y + 24, 20, (70, 130, 110))
    cv.circle(x + 34, y + 24, 13, (120, 180, 110))
    cv.ellipse(x + 34, y + 24, 20, 8, (70, 130, 110))
    # flags
    for i, fc in enumerate([(166, 30, 30), (43, 94, 167), (46, 110, 70),
                            (196, 122, 18), (107, 74, 158)]):
        fx = x + 90 + i * 44
        cv.rect(fx, y + 8, 2, 26, (90, 90, 90))
        cv.tri(fx + 2, y + 8, fx + 2, y + 20, fx + 16, y + 14, fc)
    # delegates: heads + shoulders behind table
    cols = [(120, 90, 90), (60, 90, 120), (90, 60, 90), (140, 110, 60),
            (80, 80, 140), (160, 90, 70), (70, 120, 120)]
    for i, cc in enumerate(cols):
        dx = x + 24 + i * 44
        cv.circle(dx + 12, y + 44, 9, (210, 175, 140))
        cv.rect(dx, y + 53, 24, 14, cc)
    # table
    cv.rect(x + 10, y + 66, w - 20, 10, (122, 86, 52))
    cv.rect(x + 10, y + 76, w - 20, 3, (96, 66, 40))
    for i in range(7):
        cv.rect(x + 22 + i * 44, y + 68, 18, 6, WHITE)
    # podium front centre with COP31
    cv.rect(x + w // 2 - 34, y + h - 20, 68, 20, NAVY)
    draw_text(cv, x + w // 2 - 24, y + h - 16, "COP31", 1.0, WHITE,
              bold=True, track=5.5)


def ill_lead3(cv, x, y, w, h):
    """Radar station at night: dishes, sweep beam, denial cross."""
    cv.rect(x, y, w, h, NAVY_DK)
    for sx, sy in [(20, 12), (90, 8), (170, 16), (250, 10), (300, 22),
                   (130, 26), (210, 30)]:
        cv.rect(x + sx, y + sy, 2, 2, (220, 220, 200))
    # radar towers
    for tx in (60, 200):
        cv.rect(x + tx, y + 46, 34, h - 46, (96, 104, 122))
        cv.rect(x + tx + 6, y + 40, 22, 8, (120, 128, 146))
        cv.circle(x + tx + 17, y + 34, 13, (190, 198, 210))
        cv.circle(x + tx + 17, y + 34, 8, (150, 160, 175))
        cv.line(x + tx + 17, y + 34, x + tx + 30, y + 22, (220, 230, 240), 2)
    # sweep beam (narrow)
    cv.poly([(x + 150, y + 62), (x + 138, y + 30), (x + 162, y + 30)],
            (90, 180, 120))
    # missile trail arc
    cv.line(x + 120, y + 14, x + 150, y + 8, (240, 180, 60), 2)
    cv.line(x + 150, y + 8, x + 180, y + 14, (240, 180, 60), 2)
    # denial cross over right tower
    cv.line(x + 196, y + 26, x + 238, y + 62, RED_BR, 4)
    cv.line(x + 238, y + 26, x + 196, y + 62, RED_BR, 4)
    # ground
    cv.rect(x, y + h - 8, w, 8, (24, 26, 34))
    flames(cv, x + 250, y + h - 26, 46, 18)


def ill_small(cv, x, y, w, h, n):
    """12 small flat illustrations, numbered 4..15."""
    if n == 4:  # ballot box
        cv.rect(x, y, w, h, (214, 226, 214))
        cv.rect(x + 52, y + 18, 58, 26, NAVY)
        cv.rect(x + 52, y + 12, 58, 6, (18, 30, 54))
        cv.rect(x + 72, y + 14, 18, 4, (40, 40, 40))
        cv.rect(x + 66, y + 2, 26, 12, WHITE)
        cv.line(x + 70, y + 8, x + 76, y + 12, GREEN, 2)
        cv.line(x + 76, y + 12, x + 88, y + 3, GREEN, 2)
        cv.circle(x + 128, y + 12, 8, (46, 110, 70))
        draw_text(cv, x + 125, y + 9, "V", 1.0, WHITE, bold=True)
    elif n == 5:  # cricket
        cv.rect(x, y, w, h, (150, 190, 130))
        cv.rect(x, y + 34, w, 18, (110, 160, 95))
        cv.rect(x + 20, y + 20, 3, 16, (240, 210, 90))
        cv.rect(x + 26, y + 20, 3, 16, (240, 210, 90))
        cv.rect(x + 32, y + 20, 3, 16, (240, 210, 90))
        cv.poly([(x + 90, y + 8), (x + 100, y + 10), (x + 84, y + 44),
                 (x + 76, y + 40)], (150, 110, 60))
        cv.circle(x + 128, y + 14, 7, (180, 40, 40))
        cv.circle(x + 128, y + 14, 7, (180, 40, 40))
    elif n == 6:  # F1 car
        cv.rect(x, y, w, h, (30, 34, 48))
        cv.rect(x, y + 30, w, 22, (60, 64, 78))
        cv.poly([(x + 30, y + 22), (x + 60, y + 14), (x + 105, y + 14),
                 (x + 130, y + 24), (x + 132, y + 30), (x + 30, y + 30)],
                (200, 40, 40))
        cv.rect(x + 22, y + 10, 10, 16, (200, 40, 40))
        cv.circle(x + 52, y + 32, 10, BLACK)
        cv.circle(x + 52, y + 32, 4, (160, 160, 160))
        cv.circle(x + 112, y + 32, 10, BLACK)
        cv.circle(x + 112, y + 32, 4, (160, 160, 160))
        cv.rect(x + 96, y + 18, 18, 6, (240, 210, 90))
    elif n == 7:  # basketball
        cv.rect(x, y, w, h, (226, 214, 190))
        cv.circle(x + 62, y + 26, 20, (232, 120, 40))
        cv.ring(x + 62, y + 26, 20, (120, 60, 20), 2)
        cv.line(x + 42, y + 26, x + 82, y + 26, (120, 60, 20), 2)
        cv.line(x + 62, y + 6, x + 62, y + 46, (120, 60, 20), 2)
        cv.rect(x + 118, y + 8, 30, 22, WHITE)
        cv.rect(x + 118, y + 8, 30, 22, (200, 200, 200))
        cv.rect(x + 124, y + 30, 18, 3, (220, 90, 30))
        cv.line(x + 126, y + 33, x + 126, y + 44, (220, 90, 30), 1)
        cv.line(x + 140, y + 33, x + 140, y + 44, (220, 90, 30), 1)
    elif n == 8:  # power pylon
        cv.rect(x, y, w, h, (200, 210, 224))
        cv.poly([(x + 66, y + 50), (x + 78, y + 6), (x + 90, y + 50)],
                (90, 100, 112))
        cv.line(x + 60, y + 16, x + 96, y + 16, (90, 100, 112), 3)
        cv.line(x + 52, y + 26, x + 104, y + 26, (90, 100, 112), 3)
        cv.poly([(x + 122, y + 6), (x + 112, y + 24), (x + 122, y + 24),
                 (x + 112, y + 44), (x + 130, y + 20), (x + 120, y + 20)],
                (240, 200, 40))
    elif n == 9:  # hospital
        cv.rect(x, y, w, h, (226, 232, 236))
        cv.rect(x + 46, y + 12, 70, 38, WHITE)
        cv.rect(x + 46, y + 12, 70, 38, (180, 190, 200))
        cv.rect(x + 76, y + 18, 10, 26, RED)
        cv.rect(x + 68, y + 26, 26, 10, RED)
        cv.rect(x + 56, y + 40, 8, 6, (120, 160, 200))
        cv.rect(x + 72, y + 40, 8, 6, (120, 160, 200))
        cv.rect(x + 88, y + 40, 8, 6, (120, 160, 200))
        cv.rect(x + 104, y + 40, 8, 6, (120, 160, 200))
        cv.rect(x + 122, y + 26, 26, 24, (200, 220, 230))
    elif n == 10:  # laptop + shield
        cv.rect(x, y, w, h, (214, 222, 232))
        cv.rect(x + 34, y + 8, 62, 30, (30, 40, 58))
        cv.rect(x + 38, y + 12, 54, 22, (90, 200, 140))
        cv.rect(x + 28, y + 38, 74, 5, (60, 70, 86))
        cv.poly([(x + 128, y + 6), (x + 148, y + 12), (x + 148, y + 28),
                 (x + 138, y + 44), (x + 128, y + 28), (x + 128, y + 12)],
                (43, 94, 167))
        cv.rect(x + 134, y + 22, 8, 8, WHITE)
        cv.rect(x + 136, y + 18, 4, 6, WHITE)
    elif n == 11:  # factory fire
        cv.rect(x, y, w, h, (220, 214, 200))
        cv.rect(x + 30, y + 22, 100, 28, (120, 124, 130))
        cv.poly([(x + 30, y + 22), (x + 45, y + 10), (x + 60, y + 22),
                 (x + 75, y + 10), (x + 90, y + 22), (x + 105, y + 10),
                 (x + 120, y + 22), (x + 130, y + 22)], (96, 100, 106))
        cv.rect(x + 40, y + 30, 10, 10, (255, 210, 90))
        cv.rect(x + 60, y + 30, 10, 10, (255, 210, 90))
        cv.rect(x + 80, y + 30, 10, 10, (255, 210, 90))
        cv.rect(x + 132, y + 8, 10, 42, (90, 92, 96))
        flames(cv, x + 100, y + 30, 34, 20)
        cv.circle(x + 138, y + 6, 5, (150, 150, 150))
        cv.circle(x + 146, y + 2, 4, (170, 170, 170))
    elif n == 12:  # drone over van, night
        cv.rect(x, y, w, h, NAVY_DK)
        cv.rect(x + 18, y + 10, 2, 2, WHITE)
        cv.rect(x + 60, y + 6, 2, 2, WHITE)
        cv.rect(x + 120, y + 12, 2, 2, WHITE)
        drone(cv, x + 118, y + 16, 1.1)
        cv.rect(x + 30, y + 30, 70, 16, (200, 200, 205))
        cv.rect(x + 30, y + 30, 70, 16, (160, 160, 165))
        cv.rect(x + 84, y + 24, 16, 6, (200, 200, 205))
        cv.rect(x + 36, y + 33, 12, 8, (90, 140, 190))
        cv.circle(x + 46, y + 47, 5, BLACK)
        cv.circle(x + 84, y + 47, 5, BLACK)
        cv.rect(x, y + 48, w, 4, (24, 26, 34))
    elif n == 13:  # tennis
        cv.rect(x, y, w, h, (120, 170, 110))
        cv.rect(x + 20, y + 10, 122, 32, (60, 130, 80))
        cv.line(x + 20, y + 26, x + 142, y + 26, WHITE, 2)
        cv.line(x + 81, y + 10, x + 81, y + 42, WHITE, 2)
        cv.circle(x + 128, y + 14, 7, (220, 230, 60))
        cv.poly([(x + 40, y + 44), (x + 52, y + 46), (x + 38, y + 50)],
                (220, 230, 60))
    elif n == 14:  # Olympic rings (Melbourne 1956, 70 years on)
        cv.rect(x, y, w, h, CREAM)
        cv.ring(x + 62, y + 24, 8, (0, 133, 199))
        cv.ring(x + 82, y + 24, 8, (30, 30, 30))
        cv.ring(x + 102, y + 24, 8, (224, 0, 32))
        cv.ring(x + 72, y + 35, 8, (252, 177, 49))
        cv.ring(x + 92, y + 35, 8, (0, 166, 81))
    elif n == 15:  # cargo ship ablaze
        cv.rect(x, y, w, h, (24, 40, 64))
        cv.rect(x, y + 34, w, 18, (40, 90, 120))
        cv.poly([(x + 20, y + 34), (x + 142, y + 34), (x + 132, y + 46),
                 (x + 30, y + 46)], (90, 96, 104))
        for i, cc in enumerate([(200, 60, 40), (60, 120, 160), (220, 170, 60)]):
            cv.rect(x + 44 + i * 26, y + 20, 22, 14, cc)
        flames(cv, x + 100, y + 8, 34, 14)
        cv.circle(x + 126, y + 4, 4, (150, 150, 150))


# ------------------------------------------------------------------- data
# Region assignment (one region per story; totals must match the tabs):
# EUROPE 5 (#2, #13, #16, #17, #30), MIDDLE EAST 5 (#3, #8, #12, #26,
# #31), AMERICAS 4 (#6, #7, #9, #10), ASIA-PACIFIC 9 (#4, #5, #11, #18, #19,
# #20, #21, #27, #29), AFRICA 5 (#15, #22, #23, #24, #28), OCEANIA 2 (#14,
# #25), WORLD 1 (#1 COP31 climate). Total 31.
REGIONS = [
    ("EUROPE", 5, TEAL), ("MIDDLE EAST", 5, RED), ("AMERICAS", 4, BLUE),
    ("ASIA-PACIFIC", 9, ORANGE), ("AFRICA", 5, AF_GREEN),
    ("OCEANIA", 2, PURPLE), ("WORLD", 1, (90, 90, 90)),
]

NUMBERS = [
    ("186", "DRONES FIRED"),
    ("161", "DRONES DOWNED"),
    ("35%", "CLEAN POWER BY 2035"),
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
]

LEADS = [
    dict(n=1, loc="KYIV REGION, UKRAINE", beat="WAR", badge="CONFIRMED",
         tag="186 DRONES OVERNIGHT",
         head="Russia fires 186 drones at Ukraine",
         body=("186 drones fired overnight (72 jet-powered Shahed). "
               "161 downed; hits in 18 places. In Dymer a five-storey "
               "block was hit at 05:30: 2 dead, 14 missing, 9 evacuated."),
         src="(Ukrainian Air Force via Kyiv Post)",
         ill=ill_lead1),
    dict(n=2, loc="ANTALYA, TURKIYE", beat="CLIMATE", badge="CONFIRMED",
         tag="NO DEAL AT COP31",
         head="COP31 ends with no deal",
         body=("EU and 130 countries refused a text with no mention of "
               "fossil fuels - the first COP since 2000 to end with no "
               "deal. Talks move to COP32 in Addis Ababa, Nov 2027."),
         src="(Reuters, BBC, The Guardian)",
         ill=ill_lead2),
    dict(n=3, loc="MANAMA, BAHRAIN", beat="IRAN", badge="CLAIM",
         tag="CLAIM VS DENIAL",
         head="Iran claims two US radars hit; Bahrain denies it",
         body=("IRGC claims it destroyed two US Patriot radars in Bahrain "
               "Saturday night. Bahrain: a civilian site in Sitra was hit, "
               "2 hurt. A US official told CBS no personnel or facilities "
               "were damaged."),
         src="(CBS, Al Jazeera, Reuters)",
         ill=ill_lead3),
]

# (n, location line, headline, body lines, tag, illustration no.)
SMALL = [
    (4, "HONG KONG - ELECTION", "Record turnout in committee polls",
     ["98.79% turnout (SCMP)", "856 candidates, 723 seats"],
     "98.79% TURNOUT", 4),
    (5, "WELLINGTON - CRICKET", "India declare on a record 720/9",
     ["Rahul 136, Pant 128;", "lead 352 (ESPNcricinfo)"],
     "720/9 DECLARED", 5),
    (6, "LAS VEGAS - FORMULA 1", "Verstappen wins the Las Vegas GP",
     ["Beats Norris in", "Las Vegas (FIA)"],
     "VERSTAPPEN WINS", 6),
    (7, "SAN ANTONIO - NBA", "Wemby scores 50 as Spurs roll on",
     ["50 pts, 19 reb, 5 blocks", "Spurs 114-91 Pelicans"],
     "50 POINTS", 7),
    (8, "TEHRAN - ENERGY", "Iran begins power rationing",
     ["Rolling cuts up to", "2 hours a day (Wires)"],
     "POWER CUTS", 8),
    (9, "BRASILIA - HEALTH", "Bolsonaro in intensive care",
     ["Acute bowel obstruction", "stable (Reuters)"],
     "IN INTENSIVE CARE", 9),
    (10, "WASHINGTON - CYBER", "FBI probes hack of its crime database",
     ["Washington State pauses", "gun-dealer checks (AP)"],
     "FBI PROBE", 10),
    (11, "CIKANDE - FIRE", "Candy-factory fire: 3 dead; 36 missing",
     ["Fire swept Bantam plant;", "search goes on (Detik)"],
     "3 DEAD, 36 MISSING", 11),
    (12, "GAZA CITY - CONFLICT", "Israeli fire kills four in Gaza",
     ["3 killed in drone strike", "on food vehicle (Wires)"],
     "4 DEAD", 12),
    (13, "TURIN - TENNIS", "Alcaraz wins first ATP Finals",
     ["Beats Zverev in the", "Turin final (ATP)"],
     "FIRST TITLE", 13),
    (14, "MELBOURNE - OLYMPICS", "70 years since Melbourne's Games",
     ["Opened 22 Nov 1956,", "70 years ago today (ABC)",
      "first in S. hemisphere"],
     "70 YEARS ON", 14),
    (15, "OFF BENGHAZI - SEA", "Sparta II still burning",
     ["Hit by drone Sat.;", "Finland rescue (Wires)"],
     "SHIP ABLAZE", 15),
]

ALSO = [
    (16, "Estonia to shut 5 Russia border crossings 1 Dec (Reuters)"),
    (17, "Denmark expels Russian attache over alleged plot (Guardian)"),
    (18, "Nepal PM Shah lands in Delhi; meets Modi Monday (IANS)"),
    (19, "Chinese bomber turns back 170 km from Manila (AP)"),
    (20, "Philippines M5.9 quake, 898 km deep, off Palawan (EMSC)"),
    (21, "Japan poll: record 52% feel friendly to S. Korea (Ipsos)"),
    (22, "Somalia expels UAE ambassador, recalls envoy (Wires)"),
    (23, "Sudan: RSF accused of killing civilians in W. Kordofan (Claim)"),
    (24, "Kenya discharges its last Ebola patient (Wires)"),
    (25, "Marles rejects US report on AUKUS subs (ABC)"),
    (26, "Trump seeks 'permanent' Israel deal; Doha talks (Al Jazeera)"),
    (27, "EU and Indonesia sign trade deal after 10 years (DW)"),
    (28, "Sudan army retakes ~30 towns in Kordofan (FT)"),
    (29, "Bangladesh: 30 Awami League homes set on fire (Local)"),
    (30, "Football: Liverpool thrash Man Utd 4-0; Hull 2-0 Brighton (Wires)"),
    (31, "Lebanon: Aoun demands Israel withdrawal (Al Jazeera)"),
]

DATECHECK = [
    "400-drone barrage (Thu 19-Fri 20 Nov)",
    "148-drone night (Fri 20-Sat 21 Nov)",
    "'El Chapo Isidro' captured (Sat 21)",
    "Bayelsa boat capsizes, 24 dead (Sat 21 Nov)",
    "Gaza aid-van strike (Sat 21 Nov)",
    "Arsenal 2-2; Leeds 4-1 Chelsea (Sat 21 Nov)",
    "Nvidia SEC probe first reported (Fri 20)",
    "Saudi strikes on Hodeidah (20-21 Nov)",
    "Peru earthquake (Fri 20 Nov)",
    "Copa Sudamericana final (Sat 21 Nov)",
    "Rugby: England beat NZ 37-12 (Sat 21 Nov)",
]

# pin positions on the map (local coords, map box 388 x 86)
PINS = {
    1: (236, 18), 2: (214, 16), 3: (256, 26), 4: (322, 30), 5: (372, 76),
    6: (55, 28), 7: (68, 36), 8: (266, 22), 9: (118, 62), 10: (88, 24),
    11: (304, 56), 12: (228, 36), 13: (198, 20), 14: (352, 70),
    15: (204, 34), 16: (220, 8), 17: (206, 6), 18: (292, 32),
    19: (330, 42), 20: (318, 52), 21: (348, 20), 22: (244, 50),
    23: (222, 50), 24: (232, 58), 25: (340, 64),
    26: (258, 40), 27: (296, 48), 28: (218, 44), 29: (302, 34),
    30: (184, 12), 31: (242, 32),
}

CONTINENTS = [
    [(28, 8), (95, 4), (120, 12), (108, 28), (95, 38), (70, 42),
     (45, 35), (25, 22)],                                     # N America
    [(120, 2), (135, 6), (130, 14), (118, 10)],               # Greenland
    [(105, 48), (130, 44), (140, 55), (128, 78), (112, 70),
     (100, 58)],                                               # S America
    [(185, 10), (215, 6), (225, 14), (212, 24), (195, 26),
     (182, 18)],                                               # Europe
    [(190, 30), (225, 28), (235, 40), (225, 62), (205, 66),
     (192, 48)],                                               # Africa
    [(225, 8), (360, 4), (375, 16), (355, 30), (330, 38), (300, 42),
     (280, 30), (250, 26), (228, 18)],                         # Asia
    [(296, 48), (308, 46), (312, 52), (300, 54)],              # SE Asia is.
    [(316, 52), (328, 50), (332, 56), (320, 58)],              # SE Asia is.
    [(320, 58), (365, 56), (372, 66), (350, 74), (325, 70)],   # Australia
    [(368, 72), (376, 78), (372, 80), (366, 74)],              # New Zealand
]


# ------------------------------------------------------------------ layout
def draw_header(cv):
    cv.rect(0, 0, W, 40, NAVY)
    draw_text(cv, 12, 12, "THE WORLD IN ONE DAY", 2.0, WHITE, bold=True)
    draw_text(cv, 1012 - text_w("31 STORIES - 7 REGIONS - EVERY ONE DATED "
                                "SUNDAY 22 NOVEMBER 2026", 1.5, 5.5), 13,
              "31 STORIES - 7 REGIONS - EVERY ONE DATED "
              "SUNDAY 22 NOVEMBER 2026", 1.5, (220, 225, 235), bold=True,
              track=5.5)


def draw_title(cv):
    draw_text_c(cv, W // 2, 46, "Sunday 22 November 2026", 7.0, INK,
                bold=True, track=6.0)
    draw_text_c(cv, W // 2, 104,
                "COP31 ends with no deal - 186 drones over Ukraine in the "
                "night -", 2.0, RED, bold=True, track=6.0)
    draw_text_c(cv, W // 2, 122,
                "Iran's radar claim meets Bahrain's denial", 2.0, RED,
                bold=True, track=6.0)
    cv.hline(12, 142, 1000, INK, 2)


def draw_numbers(cv):
    y = 148
    bw = (1000 - 5 * 6) // 6
    for i, (val, lab) in enumerate(NUMBERS):
        x = 12 + i * (bw + 6)
        cv.rect(x, y, bw, 52, CREAM)
        cv.rect(x, y, bw, 52, RULE)
        cv.rect(x, y, bw, 1, RULE)
        draw_text_c(cv, x + bw // 2, y + 6, val, 4.0, RED, bold=True,
                    track=5.5)
        lsc = 1.1 if len(lab) > 20 else 1.25
        draw_text_c(cv, x + bw // 2, y + 38, lab, lsc, INK, bold=True,
                    track=5.5)


def draw_tabs(cv):
    y = 206
    texts = ["%s %d" % (name, n) for name, n, _ in REGIONS]
    tws = [text_w(t, 1.5, 5.5) for t in texts]
    extra = (1000 - sum(tws)) / len(texts)
    x = 12
    for (name, n, col), t, tw in zip(REGIONS, texts, tws):
        w = int(tw + extra)
        cv.rect(x, y, w, 26, col)
        draw_text_c(cv, x + w // 2, y + 6, t, 1.5, WHITE, bold=True,
                    track=5.5)
        x += w


def draw_timeline(cv):
    y = 238
    cv.rect(12, y, 1000, 34, NAVY)
    draw_text(cv, 22, y + 10, "THE DAY IN UTC", 1.5, GOLD, bold=True,
              track=5.5)
    for row in range(2):
        items = TIMELINE[row * 3:(row + 1) * 3]
        s = "   ".join("%s  %s" % (t, d) for t, d in items)
        draw_text(cv, 170, y + 4 + row * 15, s, 1.25, WHITE, track=5.5)


def badge(cv, x, y, s, bg):
    w = int(text_w(s, 1.25, 5.5) + 10)
    cv.rect(x, y, w, 14, bg)
    draw_text(cv, x + 5, y + 3, s, 1.25, WHITE, bold=True, track=5.5)
    return w


def draw_leads(cv):
    y = 278
    cw = 324
    for i, ld in enumerate(LEADS):
        x = 12 + i * (cw + 14)
        ld["ill"](cv, x, y, cw, 90)
        tag(cv, x + 4, y + 4, ld["tag"])
        ly = y + 96
        draw_text(cv, x, ly, "%d %s - %s" % (ld["n"], ld["loc"], ld["beat"]),
                  1.5, INK, bold=True, track=5.5)
        bcol = GREEN if ld["badge"] == "CONFIRMED" else RED
        bw = int(text_w(ld["badge"], 1.25, 5.5) + 10)
        badge(cv, x + cw - bw, ly - 2, ld["badge"], bcol)
        # headline, up to 2 lines
        lines = wrap(ld["head"], cw, 2.0, 6.0)
        draw_lines(cv, x, ly + 20, lines[:2], 2.0, INK, 17, bold=True)
        # body, up to 5 lines
        blines = wrap(ld["body"], cw, 1.5, 5.5)
        draw_lines(cv, x, ly + 58, blines[:5], 1.5, (40, 40, 40), 12,
                   track=5.5)
        draw_text(cv, x, ly + 58 + 5 * 12 + 2, ld["src"], 1.25, GRAY,
                  track=5.5)


def draw_small(cv):
    y0 = 512
    cw = 162
    gap = 6
    for row in range(2):
        for col in range(6):
            idx = row * 6 + col
            n, loc, head, body, tg, illn = SMALL[idx]
            x = 12 + col * (cw + gap)
            y = y0 + row * 118
            ill_small(cv, x, y, cw, 52, illn)
            tag(cv, x + 3, y + 3, tg)
            draw_text(cv, x, y + 54, "%d %s" % (n, loc), 1.25, INK,
                      bold=True, track=5.5)
            hlines = wrap(head, cw, 1.5, 5.5)
            draw_lines(cv, x, y + 66, hlines[:2], 1.5, INK, 11, bold=True,
                       track=5.5)
            draw_lines(cv, x, y + 90, body[:3], 1.2, (40, 40, 40), 9,
                       track=5.5)
            if col < 5:
                cv.vline(x + cw + 3, y + 54, 63, RULE)


def draw_also(cv):
    y = 754
    draw_text(cv, 12, y, "ALSO ON SUNDAY 22 NOVEMBER - 16 MORE STORIES",
              2.0, INK, bold=True, track=6.0)
    cv.hline(12, y + 20, 1000, INK, 2)
    for i, (n, txt) in enumerate(ALSO):
        col = 0 if i < 9 else 1
        r = i % 9
        x = 12 if col == 0 else 512
        yy = y + 28 + r * 10
        num = "%d. " % n
        draw_text(cv, x, yy, num, 1.25, RED, bold=True, track=5.5)
        draw_text(cv, x + text_w(num, 1.25, 5.5), yy, txt, 1.25, INK,
                  track=5.5)


def draw_map(cv):
    mx, my = 12, 874
    mw, mh = 388, 112
    draw_text(cv, mx, my, "WHERE IT HAPPENED", 1.5, INK, bold=True,
              track=5.5)
    draw_text(cv, mx + 150, my + 1, "pins match story numbers", 1.25, GRAY,
              track=5.5)
    bx, by = mx, my + 18
    bw, bh = mw, 86
    cv.rect(bx, by, bw, bh, SEA)
    for pts in CONTINENTS:
        cv.poly([(bx + px, by + py) for px, py in pts], LAND)
    for n in range(1, 32):
        px, py = PINS[n]
        cv.circle(bx + px, by + py, 7, RED)
        cv.ring(bx + px, by + py, 7, WHITE, 1)
        s = str(n)
        tw = text_w(s, 1.0, 5.5)
        draw_text(cv, bx + px - tw / 2, by + py - 4, s, 1.0, WHITE,
                  bold=True, track=5.5)


def draw_datecheck(cv):
    x, y = 412, 874
    w, h = 600, 112
    cv.rect(x, y, w, h, PAPER)
    cv.rect(x, y, w, 2, RED)
    cv.rect(x, y + h - 2, w, 2, RED)
    cv.rect(x, y, 2, h, RED)
    cv.rect(x + w - 2, y, 2, h, RED)
    draw_text(cv, x + 10, y + 6, "DATE CHECK - NOT 22 NOVEMBER", 1.5, RED,
              bold=True, track=5.5)
    draw_text(cv, x + 10, y + 22,
              "Left out on purpose: these happened on other days.",
              1.25, GRAY, track=5.5)
    for i, item in enumerate(DATECHECK):
        col = 0 if i < 6 else 1
        r = i % 6
        xx = x + 12 if col == 0 else x + 312
        yy = y + 40 + r * 11
        draw_text(cv, xx, yy, "\u00d7 ", 1.25, RED, bold=True, track=5.5)
        draw_text(cv, xx + 8, yy, item, 1.2, INK, track=5.5)


def draw_footer(cv):
    y = 990
    cv.hline(12, y - 2, 1000, INK, 1)
    draw_text(cv, 12, y + 4,
              "Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, "
              "UNFCCC, Kyiv Post, SCMP, ESPNcricinfo, Detiknews",
              1.25, INK, track=5.5)
    draw_text(cv, 12, y + 15,
              "CERTAINTY: CONFIRMED = 2+ outlets - CLAIM = one side's "
              "account - REPORTED = one source - PENDING = not settled",
              1.25, INK, track=5.5)
    draw_text(cv, 12, y + 26,
              "Scenes are drawn illustrations - Wires read to press time - "
              "Sunday 22 November 2026 - One page",
              1.25, GRAY, track=5.5)


def build():
    cv = Canvas()
    draw_header(cv)
    draw_title(cv)
    draw_numbers(cv)
    draw_tabs(cv)
    draw_timeline(cv)
    draw_leads(cv)
    draw_small(cv)
    draw_also(cv)
    draw_map(cv)
    draw_datecheck(cv)
    draw_footer(cv)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = encode_png(build())
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)


if __name__ == "__main__":
    main()
