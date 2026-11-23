# makefun-news-image-20261122 — v4
# "Sunday 22 November 2026 — No Deal in Antalya, 186 Drones Over Kyiv,
#  and Hong Kong's 98.79% Vote"
# A one-image front page summing up the world news of Sunday 22 Nov 2026.
# Drawn entirely by this program: hand-made serif font (high thick-thin
# contrast, open counters), vector illustrations, data charts, world map.
# Python 3, standard library only. Deterministic: two runs write byte
# identical PNG files. No network, no timestamps inside the image.
import os
import struct
import zlib
from math import sqrt, cos, sin, pi

W = 1024
PH = 1024

# ---- palette -----------------------------------------------------------
PAPER   = (247, 243, 232)   # warm newsprint cream
INK     = (22, 22, 20)      # near-black ink
NAVY    = (26, 43, 74)      # header bar
NAVY2   = (34, 56, 96)
RED     = (178, 34, 34)     # accent red
RED_DK  = (140, 22, 22)
GOLD    = (201, 162, 39)
GREY    = (96, 92, 84)
GREY_LT = (214, 208, 194)
LINE    = (60, 56, 48)
WHITE   = (255, 255, 255)
CREAM2  = (238, 231, 214)
SKY_D   = (28, 38, 66)
SKY_L   = (122, 148, 196)
SEA     = (52, 96, 140)
GREEN   = (46, 110, 62)
ORANGE  = (214, 110, 40)
YELLOW  = (240, 200, 80)

# ---- canvas ------------------------------------------------------------
class Canvas:
    def __init__(self, w=W, h=PH):
        self.w = w
        self.h = h
        self.buf = bytearray(w * h * 3)

    def _row(self, y):
        return y * self.w * 3

    def rect(self, x, y, w, h, col):
        """Filled rectangle, clipped. x,y = top-left, ints."""
        x = int(x); y = int(y); w = int(w); h = int(h)
        if w <= 0 or h <= 0:
            return
        x0 = max(0, x); y0 = max(0, y)
        x1 = min(self.w, x + w); y1 = min(self.h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        fill = bytes(col) * (x1 - x0)
        for yy in range(y0, y1):
            i = self._row(yy) + x0 * 3
            self.buf[i:i + (x1 - x0) * 3] = fill

    def vgrad(self, x, y, w, h, c_top, c_bot):
        """Vertical gradient rectangle, clipped."""
        x = int(x); y = int(y); w = int(w); h = int(h)
        if w <= 0 or h <= 0:
            return
        x0 = max(0, x); y0 = max(0, y)
        x1 = min(self.w, x + w); y1 = min(self.h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        for yy in range(y0, y1):
            t = (yy - y) / max(1, h - 1)
            c = (int(c_top[0] + (c_bot[0] - c_top[0]) * t),
                 int(c_top[1] + (c_bot[1] - c_top[1]) * t),
                 int(c_top[2] + (c_bot[2] - c_top[2]) * t))
            i = self._row(yy) + x0 * 3
            self.buf[i:i + (x1 - x0) * 3] = bytes(c) * (x1 - x0)

    def hgrad(self, x, y, w, h, c_left, c_right):
        x = int(x); y = int(y); w = int(w); h = int(h)
        if w <= 0 or h <= 0:
            return
        x0 = max(0, x); y0 = max(0, y)
        x1 = min(self.w, x + w); y1 = min(self.h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        row = bytearray()
        for xx in range(x0, x1):
            t = (xx - x) / max(1, w - 1)
            row += bytes((int(c_left[0] + (c_right[0] - c_left[0]) * t),
                          int(c_left[1] + (c_right[1] - c_left[1]) * t),
                          int(c_left[2] + (c_right[2] - c_left[2]) * t)))
        for yy in range(y0, y1):
            i = self._row(yy) + x0 * 3
            self.buf[i:i + len(row)] = row

    def ellipse(self, cx, cy, rx, ry, col):
        """Filled ellipse, centre (cx,cy), radii rx,ry (floats ok)."""
        if rx <= 0 or ry <= 0:
            return
        y0 = max(0, int(cy - ry)); y1 = min(self.h - 1, int(cy + ry) + 1)
        for yy in range(y0, y1 + 1):
            dy = (yy + 0.5 - cy) / ry
            if abs(dy) >= 1:
                continue
            dx = rx * sqrt(1.0 - dy * dy)
            xa = max(0, int(cx - dx)); xb = min(self.w - 1, int(cx + dx))
            if xa > xb:
                continue
            i = self._row(yy) + xa * 3
            self.buf[i:i + (xb - xa + 1) * 3] = bytes(col) * (xb - xa + 1)

    def circle(self, cx, cy, r, col):
        self.ellipse(cx, cy, r, r, col)

    def poly(self, pts, col):
        """Filled polygon, pts = list of (x, y) floats."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(min(ys))); y1 = min(self.h - 1, int(max(ys)) + 1)
        n = len(pts)
        for yy in range(y0, y1 + 1):
            yc = yy + 0.5
            xs = []
            for i in range(n):
                x1, y1a = pts[i]
                x2, y2a = pts[(i + 1) % n]
                if (y1a <= yc < y2a) or (y2a <= yc < y1a):
                    xs.append(x1 + (yc - y1a) * (x2 - x1) / (y2a - y1a))
            if len(xs) < 2:
                continue
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = max(0, int(xs[k])); xb = min(self.w - 1, int(xs[k + 1]))
                if xa > xb:
                    continue
                i = self._row(yy) + xa * 3
                self.buf[i:i + (xb - xa + 1) * 3] = bytes(col) * (xb - xa + 1)

    def line(self, x0, y0, x1, y1, w, col):
        """Thick line as a quad."""
        dx = x1 - x0; dy = y1 - y0
        ln = sqrt(dx * dx + dy * dy)
        if ln == 0:
            return
        nx = -dy / ln * w / 2.0; ny = dx / ln * w / 2.0
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                   (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], col)

    def blend_px(self, x, y, col, a):
        """Alpha-blend one pixel. a in 0..255."""
        if a <= 0 or x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = self._row(y) + x * 3
        b = self.buf
        if a >= 255:
            b[i] = col[0]; b[i + 1] = col[1]; b[i + 2] = col[2]
        else:
            b[i] = (col[0] * a + b[i] * (255 - a)) // 255
            b[i + 1] = (col[1] * a + b[i + 1] * (255 - a)) // 255
            b[i + 2] = (col[2] * a + b[i + 2] * (255 - a)) // 255

    # -- PNG output ------------------------------------------------------
    def png_bytes(self):
        raw = bytearray()
        stride = self.w * 3
        for yy in range(self.h):
            raw.append(0)  # filter: none
            raw += self.buf[yy * stride:(yy + 1) * stride]
        comp = zlib.compress(bytes(raw), 9)

        def chunk(typ, data):
            c = struct.pack(">I", len(data)) + typ + data
            c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
            return c

        ihdr = struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                + chunk(b"IDAT", comp) + chunk(b"IEND", b""))

    def save(self, path):
        with open(path, "wb") as f:
            f.write(self.png_bytes())

# ---- hand-made serif font ----------------------------------------------
# Glyph space: cap height 40 units, x-height 28, baseline y=0,
# descender -12. Vertical stems 5-6 units, horizontal strokes 2 units
# (contrast >= 2.5:1). Counters are large: the hole inside 'a'/'d'/'o'
# is >= 40% of the glyph width. Curves taper: thick on the sides,
# thin on top and bottom (ring primitive: tv = side thickness,
# th = top/bottom thickness). Every glyph is a solid filled shape.
#
# Primitive tuples (all coordinates in glyph units, y up from baseline):
#   ("rect", x0, y0, x1, y1, erase)
#   ("ell",  cx, cy, rx, ry, erase)
#   ("ring", cx, cy, rx, ry, tv, th, clip, erase)
#        clip = (xmin, xmax, ymin, ymax) or None; ring = outer ellipse
#        minus inner ellipse, so sides are tv thick, top/bottom th thick.
#   ("poly", pts, erase)

def R(x0, y0, x1, y1):
    return ("rect", x0, y0, x1, y1, False)

def ER(x0, y0, x1, y1):
    return ("rect", x0, y0, x1, y1, True)

def EL(cx, cy, rx, ry):
    return ("ell", cx, cy, rx, ry, False)

def EE(cx, cy, rx, ry):
    return ("ell", cx, cy, rx, ry, True)

def RG(cx, cy, rx, ry, tv=5, th=2, clip=None, iox=0, ioy=0):
    return ("ring", cx, cy, rx, ry, tv, th, clip, False, iox, ioy)

def PG(pts):
    return ("poly", pts, False)

def ST(pts):
    """Calligraphic stroke: pts = [(x, y, r), ...] along a path.
    Drawn as overlapping circles of radius r — a single open stroke,
    used for S / s / $ so they can never read as a closed ring or a 2."""
    return ("stroke", pts)

def H(x0, x1, y, w=2):
    return ("rect", x0, y, x1, y + w, False)

def S(x, y0, y1, w=6):
    """Vertical stem with small bracketed serifs at both ends."""
    return [("rect", x, y0, x + w, y1, False),
            ("rect", x - 1.5, y0, x + w + 1.5, y0 + 2, False),
            ("rect", x - 1.5, y1 - 2, x + w + 1.5, y1, False)]

def _fill_span(rows, mw, y, xa, xb, val):
    if y < 0 or y >= len(rows):
        return
    xa = max(0, int(xa)); xb = min(mw - 1, int(xb))
    if xa > xb:
        return
    row = rows[y]
    if val:
        row[xa:xb + 1] = b"\x01" * (xb - xa + 1)
    else:
        row[xa:xb + 1] = b"\x00" * (xb - xa + 1)

def _mask_rows(prims, adv, size):
    """Render glyph primitives into a 3x supersampled mask (list of rows)."""
    k = size / 40.0 * 3.0          # mask pixels per glyph unit
    mw = int((adv + 6) * k) + 2
    mh = int(56 * k) + 2
    rows = [bytearray(mw) for _ in range(mh)]

    def mx(x):
        return (x + 3.0) * k
    def my(y):
        return (42.0 - y) * k

    for p in prims:
        kind = p[0]
        if kind == "rect":
            _, x0, y0, x1, y1, erase = p
            r0 = int(my(y1)); r1 = int(my(y0))
            for yy in range(max(0, r0), min(mh, r1 + 1)):
                _fill_span(rows, mw, yy, mx(x0), mx(x1) - 1, not erase)
        elif kind == "ell":
            _, cx, cy, rx, ry, erase = p
            r0 = max(0, int(my(cy + ry))); r1 = min(mh - 1, int(my(cy - ry)) + 1)
            for yy in range(r0, r1 + 1):
                gy = 42.0 - (yy + 0.5) / k
                d = (gy - cy) / ry
                if abs(d) >= 1:
                    continue
                dx = rx * sqrt(1.0 - d * d)
                _fill_span(rows, mw, yy, mx(cx - dx), mx(cx + dx) - 1, not erase)
        elif kind == "ring":
            _, cx, cy, rx, ry, tv, th, clip, erase = p[:9]
            iox = p[9] if len(p) > 9 else 0
            ioy = p[10] if len(p) > 10 else 0
            irx = rx - tv; iry = ry - th
            icx = cx + iox; icy = cy + ioy
            r0 = max(0, int(my(cy + ry))); r1 = min(mh - 1, int(my(cy - ry)) + 1)
            for yy in range(r0, r1 + 1):
                gy = 42.0 - (yy + 0.5) / k
                if clip is not None and not (clip[2] <= gy <= clip[3]):
                    continue
                d = (gy - cy) / ry
                if abs(d) >= 1:
                    continue
                dx = rx * sqrt(1.0 - d * d)
                xa = mx(cx - dx); xb = mx(cx + dx) - 1
                if clip is not None:
                    xa = max(xa, mx(clip[0])); xb = min(xb, mx(clip[1]) - 1)
                d2 = (gy - icy) / iry if iry > 0 else 2
                if abs(d2) < 1:
                    dx2 = irx * sqrt(1.0 - d2 * d2)
                    ia = mx(icx - dx2); ib = mx(icx + dx2) - 1
                    if clip is not None:
                        ia = max(ia, mx(clip[0])); ib = min(ib, mx(clip[1]) - 1)
                    _fill_span(rows, mw, yy, xa, ia - 1, not erase)
                    _fill_span(rows, mw, yy, ib + 1, xb, not erase)
                else:
                    _fill_span(rows, mw, yy, xa, xb, not erase)
        elif kind == "stroke":
            _, pts = p
            for i in range(len(pts) - 1):
                x1, y1, r1 = pts[i]
                x2, y2, r2 = pts[i + 1]
                dist = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                n = max(2, int(dist / 0.4) + 1)
                for j in range(n + 1):
                    t = j / n
                    ccx = x1 + (x2 - x1) * t
                    ccy = y1 + (y2 - y1) * t
                    rr = r1 + (r2 - r1) * t
                    rr0 = max(0, int(my(ccy + rr)))
                    rr1 = min(mh - 1, int(my(ccy - rr)) + 1)
                    for yy in range(rr0, rr1 + 1):
                        gy = 42.0 - (yy + 0.5) / k
                        d = (gy - ccy) / rr
                        if abs(d) >= 1:
                            continue
                        dx = rr * sqrt(1.0 - d * d)
                        _fill_span(rows, mw, yy, mx(ccx - dx),
                                   mx(ccx + dx) - 1, True)
        elif kind == "poly":
            _, pts, erase = p
            mpts = [(mx(x), my(y)) for (x, y) in pts]
            ys = [q[1] for q in mpts]
            r0 = max(0, int(min(ys))); r1 = min(mh - 1, int(max(ys)) + 1)
            n = len(mpts)
            for yy in range(r0, r1 + 1):
                yc = yy + 0.5
                xs = []
                for i in range(n):
                    x1, y1a = mpts[i]
                    x2, y2a = mpts[(i + 1) % n]
                    if (y1a <= yc < y2a) or (y2a <= yc < y1a):
                        xs.append(x1 + (yc - y1a) * (x2 - x1) / (y2a - y1a))
                if len(xs) < 2:
                    continue
                xs.sort()
                for j in range(0, len(xs) - 1, 2):
                    _fill_span(rows, mw, yy, xs[j], xs[j + 1] - 1, not erase)
    return rows, mw, mh

_MASK_CACHE = {}

def _glyph_mask(ch, size):
    """Return (sparse, out_w, out_h, ox0, oy_base, adv_px) for a glyph.
    sparse = list of (dx, dy, alpha 0..255) in output-pixel coords."""
    key = (ch, size)
    got = _MASK_CACHE.get(key)
    if got is not None:
        return got
    adv, prims = GLYPHS.get(ch, GLYPHS["?"])
    rows, mw, mh = _mask_rows(prims, adv, size)
    ow = (mw + 2) // 3; oh = (mh + 2) // 3
    sparse = []
    for oy in range(oh):
        for ox in range(ow):
            s = 0
            for dy in range(3):
                r = rows[oy * 3 + dy] if oy * 3 + dy < mh else None
                if r is None:
                    continue
                base = ox * 3
                s += (r[base] if base < mw else 0)
                s += (r[base + 1] if base + 1 < mw else 0)
                s += (r[base + 2] if base + 2 < mw else 0)
            if s:
                a = s * 255 // 9
                if a > 10:
                    sparse.append((ox, oy, a))
    ox0 = int(3.0 * size / 40.0)          # bitmap col of glyph x=0
    oy_base = int(42.0 * size / 40.0)     # bitmap row of the baseline
    adv_px = adv * size / 40.0
    out = (sparse, ow, oh, ox0, oy_base, adv_px)
    _MASK_CACHE[key] = out
    return out

CHMAP = {"\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
         "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
         "\u00e9": "e", "\u00fc": "u", "\u00f6": "o"}

def norm_char(ch):
    return CHMAP.get(ch, ch)

def text_width(s, size, track=0.8):
    w = 0.0
    tp = track * size / 40.0
    for ch in s:
        c = norm_char(ch)
        if c == " ":
            w += 9.0 * size / 40.0 + tp
            continue
        adv = GLYPHS.get(c, GLYPHS["?"])[0]
        w += adv * size / 40.0 + tp
    return w - (tp if s else 0.0)

def draw_text(cv, x, y_base, s, size, color, track=0.8, italic=False,
              align="left"):
    """Draw text; (x, y_base) = left edge / baseline of first line."""
    if align != "left":
        w = text_width(s, size, track)
        if align == "center":
            x -= w / 2.0
        elif align == "right":
            x -= w
    tp = track * size / 40.0
    buf = cv.buf; cw = cv.w; chh = cv.h
    r0, g0, b0 = color
    shear = 0.16 if italic else 0.0
    cx = x
    for ch in s:
        c = norm_char(ch)
        if c == " ":
            cx += 9.0 * size / 40.0 + tp
            continue
        sparse, ow, oh, ox0, oy_base, adv_px = _glyph_mask(c, size)
        x0 = int(round(cx - ox0))
        y0 = int(round(y_base - oy_base))
        for (dx, dy, a) in sparse:
            sh = int(shear * (oy_base - dy)) if shear else 0
            px = x0 + dx + sh
            py = y0 + dy
            if px < 0 or py < 0 or px >= cw or py >= chh:
                continue
            i = py * cw * 3 + px * 3
            if a >= 255:
                buf[i] = r0; buf[i + 1] = g0; buf[i + 2] = b0
            else:
                buf[i] = (r0 * a + buf[i] * (255 - a)) // 255
                buf[i + 1] = (g0 * a + buf[i + 1] * (255 - a)) // 255
                buf[i + 2] = (b0 * a + buf[i + 2] * (255 - a)) // 255
        cx += adv_px + tp
    return cx

def wrap_text(s, size, max_w, track=0.8):
    """Greedy word wrap. Returns list of (line, width)."""
    lines = []
    for para in s.split("\n"):
        words = para.split(" ")
        cur = ""
        for wd in words:
            trial = (cur + " " + wd) if cur else wd
            if text_width(trial, size, track) <= max_w or not cur:
                cur = trial
            else:
                lines.append((cur, text_width(cur, size, track)))
                cur = wd
        lines.append((cur, text_width(cur, size, track)))
    return lines

def draw_lines(cv, x, y_base, lines, size, color, leading, track=0.8,
                italic=False, align="left"):
    y = y_base
    for (ln, w) in lines:
        draw_text(cv, x, y, ln, size, color, track=track, italic=italic,
                  align=align)
        y += leading
    return y

# ---- glyph definitions (hand-drawn, see font notes above) --------------
# Format: char -> (advance_width, [primitives]). Cap height 40, x-height 28.
GLYPHS = {}

# -- UPPERCASE ------------------------------------------------------------
GLYPHS["A"] = (26, [PG([(0, 0), (6, 0), (16, 40), (10, 40)]),
                    PG([(26, 0), (20, 0), (16, 40), (10, 40)]),
                    H(7, 19, 12, 2), R(0, 0, 8, 2), R(18, 0, 26, 2)])
GLYPHS["B"] = (24, [EL(12, 29, 10, 11), EE(11, 29, 5, 7), ER(0, 18, 6, 40),
                    EL(12, 11, 10.5, 11.5), EE(11, 11, 5.5, 7.5),
                    ER(0, 0, 6, 18)] + S(0, 0, 40))
GLYPHS["C"] = (24, [RG(12, 20, 11, 20, 6, 2), ER(12, 12, 24, 28)])
GLYPHS["D"] = (25, [EL(11, 20, 13, 20), EE(10, 20, 7, 16), ER(0, 0, 6, 40)]
                    + S(0, 0, 40))
GLYPHS["E"] = (22, S(0, 0, 40) + [H(0, 21, 38, 2), H(0, 17, 19, 2),
                                   H(0, 21, 0, 2)])
GLYPHS["F"] = (20, S(0, 0, 40) + [H(0, 20, 38, 2), H(0, 16, 19, 2)])
GLYPHS["G"] = (25, [RG(12, 20, 11, 20, 6, 2), ER(12, 14, 25, 28),
                    H(13, 24, 16, 2), R(22, 16, 24, 26)])
GLYPHS["H"] = (25, S(0, 0, 40) + S(19, 0, 40) + [H(6, 19, 19, 2)])
GLYPHS["I"] = (12, S(3, 0, 40) + [R(0, 0, 12, 2), R(0, 38, 12, 40)])
GLYPHS["J"] = (20, [H(0, 18, 38, 2), R(12, 9, 18, 40),
                    RG(9, 9, 8, 9, 5, 2, clip=(0, 18, 0, 9))])
GLYPHS["K"] = (24, S(0, 0, 40) + [PG([(5, 18), (9, 21), (23, 40), (18, 40)]),
                                   PG([(5, 18), (9, 15), (23, 0), (18, 0)])])
GLYPHS["L"] = (21, S(0, 0, 40) + [H(0, 20, 0, 2)])
GLYPHS["M"] = (30, S(0, 0, 40) + S(24, 0, 40)
                    + [PG([(6, 40), (10, 40), (17, 2), (13, 2)]),
                       PG([(20, 40), (24, 40), (17, 2), (13, 2)])])
GLYPHS["N"] = (26, S(0, 0, 40) + S(20, 0, 40)
                    + [PG([(6, 40), (10, 40), (20, 0), (16, 0)])])
GLYPHS["O"] = (26, [RG(13, 20, 12, 20, 6, 2)])
GLYPHS["P"] = (23, [EL(12, 29, 10, 11), EE(11, 29, 5.5, 7), ER(0, 18, 6, 40)]
                    + S(0, 0, 40))
GLYPHS["Q"] = (27, [RG(13, 20, 12, 20, 6, 2),
                    PG([(16, 8), (20, 8), (26, 0), (22, 0)])])
GLYPHS["R"] = (24, [EL(12, 29, 10, 11), EE(11, 29, 5.5, 7), ER(0, 18, 6, 40),
                    PG([(10, 18), (14, 18), (24, 0), (19, 0)])] + S(0, 0, 40))
GLYPHS["S"] = (24, [ST([(19.0, 36.0, 2.0),
                        (17.0, 38.5, 1.7),
                        (13.0, 39.8, 1.6),
                        (8.5, 39.0, 1.7),
                        (5.0, 36.0, 2.2),
                        (3.5, 31.0, 3.0),
                        (3.5, 26.0, 3.2),
                        (5.5, 22.0, 3.0),
                        (9.5, 20.0, 2.7),
                        (13.5, 18.5, 2.7),
                        (17.5, 16.0, 3.0),
                        (19.5, 11.0, 3.2),
                        (19.5, 6.0, 3.0),
                        (17.0, 2.5, 2.2),
                        (12.5, 0.8, 1.7),
                        (7.5, 1.2, 1.7),
                        (4.0, 3.5, 2.0),
                        (2.5, 6.5, 2.2)])])
GLYPHS["T"] = (22, [H(0, 22, 38, 2)] + S(8, 0, 40))
GLYPHS["U"] = (26, S(0, 8, 40) + S(20, 8, 40)
                    + [RG(13, 9, 10, 9, 5, 2, clip=(0, 26, 0, 9))])
GLYPHS["V"] = (26, [PG([(0, 40), (6, 40), (16, 0), (10, 0)]),
                    PG([(26, 40), (20, 40), (16, 0), (10, 0)])])
GLYPHS["W"] = (34, [PG([(0, 40), (5, 40), (10, 0), (5, 0)]),
                    PG([(5, 0), (10, 0), (19, 30), (14, 30)]),
                    PG([(14, 30), (19, 30), (29, 0), (24, 0)]),
                    PG([(24, 0), (29, 0), (34, 40), (29, 40)])])
GLYPHS["X"] = (24, [PG([(0, 40), (6, 40), (24, 0), (18, 0)]),
                    PG([(24, 40), (18, 40), (6, 0), (0, 0)])])
GLYPHS["Y"] = (24, [PG([(0, 40), (5, 40), (13, 15), (9, 15)]),
                    PG([(24, 40), (19, 40), (15, 15), (11, 15)]),
                    R(9, 0, 15, 16), R(7.5, 0, 16.5, 2)])
GLYPHS["Z"] = (23, [H(0, 23, 38, 2), H(0, 23, 0, 2),
                    PG([(23, 38), (18, 38), (0, 2), (5, 2)])])

# -- lowercase ------------------------------------------------------------
GLYPHS["a"] = (21, [RG(10, 21, 10, 8, 5, 2, clip=(0, 22, 21, 30)),
                    RG(10, 13, 10, 12, 5, 2, clip=(0, 16, 0, 28))]
                    + S(15, 0, 28))
GLYPHS["b"] = (21, [RG(11, 14, 10, 13, 5, 2, clip=(6, 22, 0, 28))]
                    + S(0, 0, 40))
GLYPHS["c"] = (19, [RG(10, 14, 9, 13, 5, 2), ER(10, 10, 19, 18)])
GLYPHS["d"] = (21, [RG(10, 14, 10, 13, 5, 2, clip=(0, 15, 0, 28))]
                    + S(15, 0, 40))
GLYPHS["e"] = (20, [RG(10, 14, 9, 13, 5, 2), H(1, 19, 13, 2)])
GLYPHS["f"] = (15, [R(4, 0, 10, 40), R(2.5, 0, 11.5, 2),
                    RG(8, 33, 7, 8, 4, 2, clip=(1, 15, 30, 42)),
                    R(12, 26, 15, 32), H(0, 14, 20, 2)])
GLYPHS["g"] = (21, [RG(10, 14, 10, 13, 5, 2, clip=(0, 16, 0, 28)),
                    RG(10, -4, 9, 9, 5, 2, clip=(4, 22, -13, 0))]
                    + S(15, -12, 28))
GLYPHS["h"] = (21, [RG(11, 14, 9, 13, 5, 2, clip=(6, 21, 14, 28)),
                    R(15, 0, 21, 28), R(13.5, 0, 22.5, 2)] + S(0, 0, 40))
GLYPHS["i"] = (10, S(2, 0, 28) + [EL(5, 34, 3, 3)])
GLYPHS["j"] = (11, [R(5, 0, 11, 28), R(3.5, 0, 12.5, 2),
                    RG(6, -4, 5, 8, 4, 2, clip=(0, 12, -12, 0)),
                    EL(8, 34, 3, 3)])
GLYPHS["k"] = (21, S(0, 0, 40) + [PG([(6, 19), (9, 21), (20, 28), (16, 28)]),
                                   PG([(8, 18), (11, 18), (21, 0), (17, 0)])])
GLYPHS["l"] = (10, S(2, 0, 40))
GLYPHS["m"] = (30, [RG(11, 14, 9, 13, 5, 2, clip=(6, 16, 14, 28)),
                    R(15, 0, 21, 28), R(13.5, 0, 22.5, 2),
                    RG(21, 14, 9, 13, 5, 2, clip=(16, 30, 14, 28)),
                    R(24, 0, 30, 28), R(22.5, 0, 31.5, 2)] + S(0, 0, 28))
GLYPHS["n"] = (21, [RG(11, 14, 9, 13, 5, 2, clip=(6, 21, 14, 28)),
                    R(15, 0, 21, 28), R(13.5, 0, 22.5, 2)] + S(0, 0, 28))
GLYPHS["o"] = (20, [RG(10, 14, 10, 13, 5, 2)])
GLYPHS["p"] = (21, [RG(11, 14, 10, 13, 5, 2, clip=(6, 22, 0, 28))]
                    + S(0, -12, 28))
GLYPHS["q"] = (21, [RG(10, 14, 10, 13, 5, 2, clip=(0, 15, 0, 28))]
                    + S(15, -12, 28))
GLYPHS["r"] = (14, S(0, 0, 28) + [RG(9, 20, 7, 8, 4, 2, clip=(6, 15, 18, 28)),
                                   R(12, 12, 15, 22)])
GLYPHS["s"] = (19, [ST([(15.0, 25.0, 1.5),
                        (13.5, 27.0, 1.3),
                        (10.5, 27.8, 1.2),
                        (7.0, 27.2, 1.3),
                        (4.5, 25.0, 1.6),
                        (3.2, 21.5, 2.1),
                        (3.2, 18.0, 2.2),
                        (4.8, 15.2, 2.1),
                        (7.8, 13.8, 1.9),
                        (10.8, 12.5, 1.9),
                        (13.8, 10.5, 2.1),
                        (15.2, 7.0, 2.2),
                        (15.0, 3.8, 2.0),
                        (13.0, 1.5, 1.5),
                        (9.5, 0.5, 1.3),
                        (6.0, 0.8, 1.3),
                        (3.5, 2.5, 1.5),
                        (2.3, 5.0, 1.6)])])
GLYPHS["t"] = (14, [R(4, 0, 10, 36), R(2.5, 0, 11.5, 2),
                    RG(7, 5, 5, 6, 4, 2, clip=(4, 14, 0, 6)),
                    H(0, 13, 20, 2)])
GLYPHS["u"] = (21, S(0, 8, 28) + [R(15, 0, 21, 28), R(13.5, 0, 22.5, 2),
                                   RG(11, 9, 10, 9, 5, 2, clip=(0, 21, 0, 9))])
GLYPHS["v"] = (21, [PG([(0, 28), (6, 28), (13, 0), (8, 0)]),
                    PG([(21, 28), (15, 28), (13, 0), (8, 0)])])
GLYPHS["w"] = (29, [PG([(0, 28), (5, 28), (8, 0), (4, 0)]),
                    PG([(4, 0), (8, 0), (16, 20), (12, 20)]),
                    PG([(12, 20), (16, 20), (25, 0), (21, 0)]),
                    PG([(21, 0), (25, 0), (29, 28), (24, 28)])])
GLYPHS["x"] = (20, [PG([(0, 28), (5, 28), (20, 0), (15, 0)]),
                    PG([(20, 28), (15, 28), (5, 0), (0, 0)])])
GLYPHS["y"] = (21, [PG([(0, 28), (5, 28), (11, 0), (7, 0)]),
                    PG([(21, 28), (16, 28), (13, 0), (9, 0)]),
                    PG([(8, 2), (12, 2), (7, -9), (4, -9)])])
GLYPHS["z"] = (19, [H(0, 19, 26, 2), H(0, 19, 0, 2),
                    PG([(19, 26), (15, 26), (0, 2), (4, 2)])])

# -- digits -----------------------------------------------------------------
GLYPHS["0"] = (22, [RG(11, 20, 10, 20, 5, 2)])
GLYPHS["1"] = (13, [PG([(7, 40), (10, 40), (4, 33), (4, 30)]),
                    R(6, 0, 12, 40), R(4.5, 0, 13.5, 2), R(4.5, 38, 13.5, 40)])
GLYPHS["2"] = (22, [RG(11, 28, 10, 11, 5, 2, clip=(1, 22, 28, 40)),
                    PG([(20, 28), (16, 28), (3, 2), (7, 2)]), H(0, 22, 0, 2)])
GLYPHS["3"] = (22, [RG(11, 29, 10, 11, 5, 2, clip=(6, 22, 24, 40)),
                    RG(11, 11, 10, 11, 5, 2, clip=(6, 22, 0, 16)),
                    H(6, 17, 19, 2)])
GLYPHS["4"] = (23, [PG([(18, 40), (22, 40), (6, 8), (2, 8)]),
                    H(0, 22, 8, 2)] + S(16, 0, 40))
GLYPHS["5"] = (22, [H(0, 20, 38, 2), R(0, 26, 6, 40), H(0, 17, 24, 2),
                    RG(11, 12, 10, 12, 5, 2, clip=(2, 22, 2, 24))])
GLYPHS["6"] = (22, [RG(11, 14, 10, 13, 5, 2),
                    RG(11, 24, 10, 12, 5, 2, clip=(0, 11, 20, 40))])
GLYPHS["7"] = (21, [H(0, 21, 38, 2),
                    PG([(21, 38), (17, 38), (4, 0), (0, 0)])])
GLYPHS["8"] = (22, [RG(11, 29, 10, 11, 5, 2), RG(11, 11, 10, 12, 5, 2)])
GLYPHS["9"] = (22, [RG(11, 27, 10, 12, 5, 2), R(16, 0, 22, 40),
                    R(14.5, 0, 23.5, 2)])
GLYPHS["%"] = (30, [RG(7, 30, 6, 7, 3, 1.5), RG(23, 10, 6, 7, 3, 1.5),
                    PG([(26, 40), (22, 40), (4, 0), (8, 0)])])
GLYPHS["$"] = (22, [RG(14, 31, 9, 9, 3.5, 1.5, clip=(0, 26, 31, 42)),
                    RG(14, 31, 9, 9, 3.5, 1.5, clip=(19, 26, 24, 34)),
                    RG(14, 31, 9, 9, 3.5, 1.5, clip=(0, 9, 26, 34)),
                    RG(10, 9, 9, 9, 3.5, 1.5, clip=(0, 26, -2, 9)),
                    RG(10, 9, 9, 9, 3.5, 1.5, clip=(0, 6, 6, 16)),
                    RG(10, 9, 9, 9, 3.5, 1.5, clip=(15, 26, 6, 14)),
                    PG([(16, 26), (20, 24), (8, 14), (4, 16)]),
                    R(10, -4, 12, 44)])

# -- punctuation ------------------------------------------------------------
GLYPHS["."] = (10, [EL(5, 2, 2.5, 2.5)])
GLYPHS[","] = (10, [EL(5, 2, 2.5, 2.5), PG([(3, 4), (7, 4), (5, -8), (2, -8)])])
GLYPHS[":"] = (10, [EL(5, 10, 2.5, 2.5), EL(5, 24, 2.5, 2.5)])
GLYPHS[";"] = (10, [EL(5, 10, 2.5, 2.5), EL(5, 24, 2.5, 2.5),
                    PG([(3, 8), (7, 8), (5, -8), (2, -8)])])
GLYPHS["!"] = (11, [R(4, 12, 8, 40), EL(6, 4, 2.5, 2.5)])
GLYPHS["?"] = (20, [RG(10, 30, 9, 9, 4, 2, clip=(2, 19, 26, 40)),
                    PG([(15, 28), (18, 24), (12, 16), (8, 17)]),
                    EL(10, 4, 2.5, 2.5)])
GLYPHS["'"] = (10, [PG([(6, 40), (10, 40), (7, 28), (4, 28)])])
GLYPHS['"'] = (16, [PG([(2, 40), (6, 40), (3, 28), (0, 28)]),
                    PG([(10, 40), (14, 40), (11, 28), (8, 28)])])
GLYPHS["("] = (13, [RG(14, 20, 12, 20, 4, 2, clip=(0, 8, 0, 40))])
GLYPHS[")"] = (13, [RG(10, 20, 12, 20, 4, 2, clip=(16, 24, 0, 40))])
GLYPHS["-"] = (15, [H(0, 14, 19, 2)])
GLYPHS["/"] = (16, [PG([(14, 40), (18, 40), (6, 0), (2, 0)])])
GLYPHS["&"] = (22, [RG(10, 26, 8, 9, 4, 2), RG(10, 10, 8, 8, 4, 2),
                    PG([(16, 14), (19, 11), (6, -2), (3, 1)])])
GLYPHS["\u00b7"] = (10, [EL(5, 20, 2, 2)])          # middot
GLYPHS["\u2022"] = (12, [EL(6, 20, 4, 4)])          # bullet
GLYPHS["+"] = (18, [H(2, 16, 19, 2), R(8, 12, 10, 26)])
GLYPHS["="] = (18, [H(2, 16, 16, 2), H(2, 16, 24, 2)])
GLYPHS["_"] = (18, [H(0, 18, -2, 2)])
GLYPHS["\u00b0"] = (12, [RG(6, 34, 4, 4, 2, 1.5)])  # degree
GLYPHS["|"] = (8, [R(3, 0, 5, 40)])
GLYPHS["#"] = (24, [R(8, 0, 11, 40), R(15, 0, 18, 40),
                    H(0, 24, 26, 2), H(0, 24, 12, 2)])
GLYPHS["*"] = (16, [PG([(7, 40), (9, 40), (9, 0), (7, 0)]),
                    PG([(0, 34), (2, 37), (16, 6), (14, 3)]),
                    PG([(16, 34), (14, 37), (0, 6), (2, 3)])])
GLYPHS["?"] = GLYPHS["?"]  # keep linter quiet; '?' defined above

# ---- font test -----------------------------------------------------------
def font_test():
    """Render the title at 2x zoom plus a full alphabet sheet, for the
    mandatory font check (SPEC section 4a point 10)."""
    cv = Canvas(1024, 640)
    cv.rect(0, 0, 1024, 640, PAPER)
    # Title line 1 at display size, and the same line zoomed 2x below it.
    draw_text(cv, 40, 90, "Sunday 22 November 2026", 58, INK, track=0.8)
    draw_text(cv, 40, 150, "No Deal in Antalya, 186 Drones", 30, INK, track=0.8)
    # 2x zoom: render at 116px and crop-zoom is simulated by big size.
    draw_text(cv, 40, 300, "Sunday", 116, INK, track=0.8)
    draw_text(cv, 40, 430, "aod 186 %", 116, INK, track=0.8)
    draw_text(cv, 40, 520, "ABCDEFGHIJKLM abcdefghijklm", 30, INK, track=0.8)
    draw_text(cv, 40, 560, "NOPQRSTUVWXYZ nopqrstuvwxyz", 30, INK, track=0.8)
    draw_text(cv, 40, 600, "0123456789 $%.,:;!?()'\"-/", 30, INK, track=0.8)
    out = os.environ.get("FONT_TEST_OUT", "/tmp/fonttest/font-test.png")
    cv.save(out)
    print("font test ->", out)

# ---- page content (all facts from SPEC v4 section 3) --------------------
TITLE_L1 = "Sunday 22 November 2026"
TITLE_L2 = "No Deal in Antalya, 186 Drones Over Kyiv, and Hong Kong's 98.79% Vote"
HEADER_BAR = ("THE WORLD IN ONE DAY  \u00b7  38 STORIES  \u00b7  10 REGIONS  \u00b7  "
              "EVERY ONE DATED SUNDAY 22 NOVEMBER 2026")
SUBHEAD = ("COP31 ends with no deal  \u00b7  186 drones over Ukraine in the night  "
           "\u00b7  Iran's radar claim meets Bahrain's denial")

NUMBERS = [
    ("186", "DRONES FIRED AT UKRAINE"),
    ("161", "DRONES DOWNED"),
    ("258", "HOUSE SEATS FOR DEMOCRATS"),
    ("$120bn", "ADAPTATION TARGET DROPPED"),
    ("720/9", "INDIA'S RECORD TEST TOTAL"),
    ("98.79%", "HONG KONG TURNOUT"),
]

REGIONS = [("EUROPE", 5), ("MIDDLE EAST", 5), ("NORTH AMERICA", 5),
           ("SOUTH AMERICA", 1), ("EAST ASIA", 3), ("SOUTH ASIA", 4),
           ("SOUTHEAST ASIA", 3), ("AFRICA", 6), ("OCEANIA", 2),
           ("WORLD", 4)]
REGION_COLORS = [(178, 34, 34), (26, 43, 74), (46, 110, 62), (120, 72, 20),
                 (140, 40, 90), (180, 110, 20), (40, 120, 110), (90, 60, 140),
                 (60, 90, 160), (96, 92, 84)]

TIMELINE = [("01:00", "HK POLLS OPEN"), ("03:00", "COP31 OBJECTIONS CLOSE"),
            ("05:11", "HAMAS SEEKS TALKS"), ("05:30", "LAS VEGAS GP ENDS"),
            ("06:00", "COP31 APPROVAL DUE"), ("07:30", "APPROVAL SLIPS AGAIN"),
            ("09:45", "PRESS TIME")]

# (number, location, topic, badge, headline, body, source)
LEADS = [
    (1, "ANTALYA, T\u00dcRKIYE", "CLIMATE", "CONFIRMED",
     "COP31 ends with no deal",
     "EU + 130 nations reject a text that never mentions fossil fuels \u2014 "
     "the first COP to end with no cover decision since 2000, after 44+ hours "
     "overtime. Talks move to COP32 in Addis Ababa, Nov 2027.",
     "UNFCCC / Reuters"),
    (2, "KYIV REGION, UKRAINE", "WAR", "CONFIRMED",
     "Russia fires 186 drones at Ukraine",
     "186 drones overnight \u2014 72 jet-powered Shaheds plus decoys; 161 shot "
     "down, hits in 18 places. In Dymer, a block is hit at 05:30: 2 killed, "
     "14 missing, 9 evacuated.",
     "Kyiv Post / Reuters"),
    (3, "MANAMA, BAHRAIN", "IRAN", "CLAIM",
     "Iran claims two US radars hit; Bahrain denies it",
     "The IRGC claims it destroyed two US Patriot radars at Al-Riffa and "
     "Awali. Bahrain says the target was a civilian facility; a US official "
     "tells CBS no US damage.",
     "Reuters / CBS"),
]

# (number, location, topic, badge, headline, body, source, art key)
SMALL = [
    (4, "THE HAGUE", "WORLD COURT", "CONFIRMED",
     "ICJ: Myanmar committed genocide",
     "Myanmar committed genocide. (Reuters / AP)",
     "Reuters / AP", "court"),
    (5, "BENGHAZI, LIBYA", "CONFLICT", "REPORTED",
     "Sea drones hit Russian warship at Benghazi",
     "Sea drones hit Russian corvette. (Wires)",
     "Wires", "sea"),
    (6, "HONG KONG", "ELECTION", "CONFIRMED",
     "Record turnout in committee polls",
     "98.79% turnout; 856 for 723 seats. (SCMP)",
     "SCMP", "ballot"),
    (7, "WELLINGTON, NZ", "CRICKET", "CONFIRMED",
     "India declare on a record 720/9",
     "Record Test total in NZ. (ESPNcricinfo)",
     "ESPNcricinfo", "cricket"),
    (8, "LAS VEGAS", "FORMULA 1", "CONFIRMED",
     "Verstappen wins the Las Vegas GP",
     "Verstappen beats Norris. (Wires)",
     "Wires", "f1"),
    (9, "SAN ANTONIO, USA", "NBA", "CONFIRMED",
     "Wembanyama scores 50 as Spurs roll on",
     "50 pts, 19 reb, 5 blk. (AP)",
     "AP", "nba"),
    (10, "WASHINGTON, USA", "POLITICS", "CONFIRMED",
     "Democrats win biggest House majority since 1992",
     "Dems hold 258+ seats. (AP)",
     "AP", "house"),
    (11, "LONDON", "EUROPE", "CONFIRMED",
     "UK and EU strike post-Brexit deals",
     "UK, EU agree trade deals. (AP)",
     "AP / Reuters", "handshake"),
    (12, "TEHRAN, IRAN", "ENERGY", "CONFIRMED",
     "Iran begins rationing electricity",
     "Blackouts up to 2 hrs a day. (Wires)",
     "Wires", "power"),
    (13, "BRAS\u00cdLIA, BRAZIL", "HEALTH", "CONFIRMED",
     "Bolsonaro in intensive care",
     "Bowel obstruction; stable. (Wires)",
     "Wires", "hospital"),
    (14, "WASHINGTON, USA", "CYBER", "REPORTED",
     "FBI probes apparent hack of its crime database",
     "Gun-dealer checks paused. (Wires)",
     "Wires", "cyber"),
    (15, "CIKANDE, INDONESIA", "FIRE", "CONFIRMED",
     "Candy-factory fire in Cikande: 3 dead; 36 missing",
     "Bantam factory fire. (Detiknews)",
     "Detiknews", "fire"),
    (16, "GAZA CITY", "CONFLICT", "REPORTED",
     "Israeli fire kills four in Gaza",
     "Three killed in drone strike. (Wires)",
     "Wires", "gaza"),
    (17, "TURIN, ITALY", "TENNIS", "CONFIRMED",
     "Alcaraz wins first ATP Finals",
     "Alcaraz beats Zverev. (Wires)",
     "Wires", "tennis"),
    (18, "GULF OF FINLAND", "SEA", "CONFIRMED",
     "Sparta II towed home after drone strike",
     "Russian ship towed home. (Wires)",
     "Wires", "ship"),
]

ALSO = [
    ("Europe", "Estonia to shut 5 Russia crossings 1 Dec, after sabotage bid", "Reuters"),
    ("Europe", "Denmark expels Russian attach\u00e9 over alleged plot vs Ukrainian", "Guardian"),
    ("South Asia", "Nepal PM Shah lands in Delhi; meets Modi Monday", "IANS"),
    ("East Asia", "Chinese bomber turns back 170 km from Manila", "AP"),
    ("Southeast Asia", "Philippines M5.9 quake, 898 km deep, off Palawan", "EMSC"),
    ("East Asia", "Japan poll: record 52% feel friendly to S. Korea", "Ipsos"),
    ("South Asia", "India, China hold fresh military talks on Arunachal", "Wires"),
    ("Africa", "Somalia expels UAE ambassador, recalls envoy", "Wires"),
    ("Africa", "Sudan: RSF accused of killing civilians in W. Kordofan", "Claim"),
    ("Africa", "Kenya discharges its last Ebola patient", "Wires"),
    ("Africa", "Drone strikes damage UN facility in Khartoum; 4 killed", "Wires"),
    ("Oceania", "Marles rejects US report on AUKUS subs", "ABC"),
    ("Oceania", "Melbourne \u2014 70 years since 1956 Olympics opened", "ABC"),
    ("North America", "Trump seeks 'permanent' Israel deal; Doha talks", "Al Jazeera"),
    ("Southeast Asia", "EU, Indonesia sign trade deal after ten years", "DW"),
    ("Africa", "Sudan army retakes ~30 towns in Kordofan", "FT"),
    ("South Asia", "Bangladesh: 30 Awami League homes set on fire", "Local"),
    ("Middle East", "Lebanon: Aoun demands Israel withdrawal", "Al Jazeera"),
    ("World", "Scientists sequence whale genome from drone breath", "Wires"),
    ("Middle East", "Saudi Arabia, Yemen's Houthis exchange fire", "Wires"),
]

DATE_CHECK = [
    "400-drone, 110-missile barrage (Thu 19\u2013Fri 20 Nov)",
    "148-drone night, Kryvyi Rih double-tap (Fri 20\u2013Sat 21 Nov)",
    "'El Chapo Isidro' captured (Sat 21 Nov)",
    "Bayelsa boat capsizes, 24 dead (Fri 21 Nov)",
    "Gaza aid-van strike (Sat 21 Nov)",
    "Nvidia SEC probe first reported (Fri 20 Nov)",
    "Saudi strikes on Hodeidah (20\u201321 Nov)",
    "Peru earthquake (Fri 20 Nov)",
    "Copa Sudamericana final (Sat 21 Nov)",
    "BepiColombo enters Mercury orbit (Sat 21 Nov)",
    "Russian missiles entered Poland (Fri 20 Nov)",
    "Rugby: England beat NZ 37-12 (Sat 21 Nov)",
    "Arsenal 2-2 Newcastle; Leeds 4-1 Chelsea (Sat 21 Nov)",
]

SOURCES = ("Sources: Reuters, BBC, AP, AFP, Al Jazeera, The Guardian, UNFCCC, "
           "Kyiv Post, SCMP, ESPNcricinfo, Detiknews")
LEGEND = ("CONFIRMED \u2014 verified by multiple wires   \u00b7   CLAIM \u2014 one side's "
          "claim, disputed   \u00b7   REPORTED \u2014 single-source report")
FOOT_NOTE = "Scenes are drawn illustrations  \u00b7  Wires read to press time 09:45 UTC"

# map pins: (story no, x, y) in map-box coordinates (0..1), region colour idx
MAP_PINS = [(1, 0.47, 0.30), (2, 0.58, 0.24), (3, 0.60, 0.44),
            (4, 0.46, 0.22), (5, 0.52, 0.48), (6, 0.83, 0.42),
            (7, 0.93, 0.82), (8, 0.16, 0.38), (9, 0.20, 0.44),
            (10, 0.24, 0.36), (11, 0.45, 0.20), (12, 0.62, 0.40),
            (13, 0.33, 0.66), (14, 0.24, 0.36), (15, 0.79, 0.58),
            (16, 0.59, 0.42), (17, 0.48, 0.26), (18, 0.55, 0.16)]

# ---- illustration helpers ------------------------------------------------
BADGE_COL = {"CONFIRMED": (46, 110, 62), "CLAIM": (178, 90, 20),
             "REPORTED": (60, 90, 160), "PENDING": (96, 92, 84)}

def badge(cv, x, y, text, kind="CONFIRMED"):
    col = BADGE_COL.get(kind, (96, 92, 84))
    w = int(text_width(text, 9, 0.6)) + 10
    cv.rect(x, y, w, 13, col)
    draw_text(cv, x + 5, y + 10, text, 9, WHITE, track=0.6)
    return w

def mini_bg(cv, x, y, w, h, c1, c2):
    cv.vgrad(x, y, w, h, c1, c2)

def person(cv, x, y, s, shirt, skin=(214, 178, 140)):
    cv.circle(x + s // 2, y + int(s * 0.28), max(2, int(s * 0.22)), skin)
    cv.rect(x, y + int(s * 0.52), s, int(s * 0.48), shirt)

def flag(cv, x, y, w, h, cols):
    cv.line(x, y, x, y + h + 8, 1, LINE)
    n = len(cols)
    for i, c in enumerate(cols):
        cv.rect(x + 1, y + i * h // n, w, h // n + 1, c)

def building(cv, x, y, w, h, col, lit=True, win=(240, 200, 80)):
    cv.rect(x, y, w, h, col)
    if lit:
        for wy in range(y + 4, y + h - 3, 7):
            for wx in range(x + 3, x + w - 3, 8):
                if (wx * 7 + wy * 13) % 5 < 3:
                    cv.rect(wx, wy, 3, 4, win)

def cloud(cv, x, y, s, col=(255, 255, 255)):
    cv.ellipse(x, y, s, s * 0.55, col)
    cv.ellipse(x + s * 0.7, y + s * 0.1, s * 0.7, s * 0.45, col)
    cv.ellipse(x - s * 0.7, y + s * 0.15, s * 0.6, s * 0.4, col)

def smoke(cv, x, y, s, col=(200, 196, 188)):
    cv.circle(x, y, s, col)
    cv.circle(x + s, y - s, int(s * 0.8), col)
    cv.circle(x + int(s * 1.8), y - int(s * 1.8), int(s * 0.6), col)

def arc_line(cv, cx, cy, rx, ry, a0, a1, w, col, steps=20):
    px = py = None
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        x = cx + rx * cos(a)
        y = cy - ry * sin(a)
        if px is not None:
            cv.line(int(px), int(py), int(x), int(y), w, col)
        px, py = x, y

def pie_wedge(cv, cx, cy, r0, r1, a0, a1, col, steps=24):
    pts = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        pts.append((cx + r1 * cos(a), cy - r1 * sin(a)))
    for i in range(steps, -1, -1):
        a = a0 + (a1 - a0) * i / steps
        pts.append((cx + r0 * cos(a), cy - r0 * sin(a)))
    cv.poly(pts, col)

# ---- lead illustrations (322 x 120) --------------------------------------
def art_cop31(cv, x, y, w, h):
    mini_bg(cv, x, y, w, h, (232, 222, 196), (206, 190, 158))
    # windows with sky
    for wx in (x + 18, x + w // 2 - 30, x + w - 78):
        cv.vgrad(wx, y + 8, 56, 44, (150, 180, 215), (210, 225, 240))
        cv.line(wx + 28, y + 8, wx + 28, y + 52, 2, (120, 110, 90))
        cv.line(wx, y + 30, wx + 56, y + 30, 2, (120, 110, 90))
    # wall clock
    cv.circle(x + w - 26, y + 22, 11, WHITE)
    cv.line(x + w - 26, y + 22, x + w - 20, y + 16, 2, INK)
    cv.line(x + w - 26, y + 22, x + w - 26, y + 13, 2, INK)
    # NO DEAL banner
    cv.rect(x + w // 2 - 62, y + 12, 124, 22, RED)
    draw_text(cv, x + w // 2, y + 28, "NO DEAL", 15, WHITE, track=0.8,
              align="center")
    # long table
    cv.rect(x + 8, y + 78, w - 16, 34, (122, 84, 48))
    cv.rect(x + 8, y + 78, w - 16, 4, (150, 108, 62))
    # delegates behind the table
    shirts = [(178, 34, 34), (26, 43, 74), (46, 110, 62), (120, 72, 20),
              (140, 40, 90), (40, 120, 110)]
    for i, sh in enumerate(shirts):
        person(cv, x + 22 + i * 48, y + 46, 30, sh)
    # small flags + papers on the table
    for i, cols in enumerate([[(178, 34, 34), (255, 255, 255)],
                              [(26, 43, 74), (255, 255, 255)],
                              [(46, 110, 62), (255, 255, 255)],
                              [(201, 162, 39), (178, 34, 34)]]):
        flag(cv, x + 40 + i * 70, y + 84, 16, 10, cols)
    for i in range(4):
        cv.rect(x + 30 + i * 72, y + 100, 22, 8, WHITE)

def art_kyiv(cv, x, y, w, h):
    mini_bg(cv, x, y, w, h, (16, 22, 44), (58, 58, 96))
    # stars
    for sx, sy in [(20, 12), (60, 26), (110, 10), (160, 20), (210, 8),
                   (260, 24), (300, 12), (90, 34), (180, 36), (240, 30)]:
        cv.rect(x + sx, y + sy, 2, 2, WHITE)
    # searchlights
    cv.poly([(x + 60, y + h), (x + 90, y + h), (x + 150, y + 6),
             (x + 138, y + 6)], (240, 220, 140))
    cv.poly([(x + 250, y + h), (x + 272, y + h), (x + 210, y + 10),
             (x + 200, y + 10)], (240, 220, 140))
    # skyline, 5 buildings with lit windows
    for i, (bw, bh) in enumerate([(52, 62), (44, 84), (58, 54), (40, 74),
                                  (48, 58)]):
        bx = x + 12 + i * 62
        building(cv, bx, y + h - bh, bw, bh, (24, 26, 40))
    # drones: 3 silhouettes with red dots
    for dx, dy in [(120, 26), (200, 40), (260, 18)]:
        cv.ellipse(x + dx, y + dy, 9, 3, (10, 10, 14))
        cv.rect(x + dx - 1, y + dy - 1, 2, 2, RED)
    # fire glow + smoke at the hit building
    cv.ellipse(x + 150, y + h - 8, 34, 12, ORANGE)
    cv.ellipse(x + 150, y + h - 6, 20, 8, YELLOW)
    smoke(cv, x + 150, y + h - 46, 9, (120, 116, 110))
    smoke(cv, x + 170, y + h - 60, 7, (140, 136, 130))

def art_manama(cv, x, y, w, h):
    mini_bg(cv, x, y, w, h, (214, 110, 60), (96, 60, 130))
    # sun low on the horizon
    cv.circle(x + w - 70, y + 58, 16, (240, 180, 90))
    # sea
    cv.vgrad(x, y + h - 22, w, 22, (52, 96, 140), (30, 60, 100))
    # industrial buildings with chimneys + smoke
    for i, (bw, bh) in enumerate([(56, 34), (44, 46), (62, 30)]):
        bx = x + 14 + i * 66
        by = y + h - 22 - bh
        cv.rect(bx, by, bw, bh, (70, 66, 80))
        cv.rect(bx + bw - 12, by - 18, 8, 18, (60, 56, 70))
        smoke(cv, bx + bw - 8, by - 24, 5)
        for wy in range(by + 6, by + bh - 4, 9):
            cv.rect(bx + 6, wy, 8, 5, (240, 200, 80))
    # big radar dish + waves
    dx, dy = x + 235, y + 52
    cv.line(dx, dy, dx, y + h - 22, 4, (40, 40, 48))
    cv.ellipse(dx, dy - 6, 34, 12, (220, 220, 225))
    cv.ellipse(dx, dy - 8, 34, 10, (160, 160, 168))
    cv.line(dx - 20, dy - 14, dx + 26, dy - 26, 2, (60, 60, 70))
    for r in (46, 58, 70):
        arc_line(cv, dx + 8, dy - 10, r, r * 0.55, -0.5, 1.1, 2,
                 (255, 255, 255))
    # DENIED cross
    cv.line(x + 18, y + 14, x + 46, y + 42, 4, RED)
    cv.line(x + 46, y + 14, x + 18, y + 42, 4, RED)
    draw_text(cv, x + 32, y + 58, "DENIED", 12, RED, track=0.8, align="center")

# ---- small illustrations (192 x 50) --------------------------------------
def art_small(cv, x, y, w, h, key):
    if key == "court":
        mini_bg(cv, x, y, w, h, (190, 200, 220), (150, 160, 190))
        cv.rect(x + 30, y + 16, w - 60, h - 16, (235, 230, 220))
        cv.poly([(x + 24, y + 16), (x + w - 24, y + 16), (x + w // 2, y + 2)],
                (178, 34, 34))
        for cx in (x + 44, x + w // 2 - 4, x + w - 52):
            cv.rect(cx, y + 20, 7, h - 20, (120, 110, 95))
        cloud(cv, x + 30, y + 8, 7)
        cv.circle(x + w - 26, y + 9, 6, (240, 200, 80))
    elif key == "sea":
        mini_bg(cv, x, y, w, h, (150, 180, 210), (52, 96, 140))
        cv.rect(x, y + h - 12, w, 12, (30, 60, 100))
        cv.poly([(x + 40, y + h - 12), (x + 130, y + h - 12),
                 (x + 118, y + h - 2), (x + 52, y + h - 2)], (60, 60, 70))
        cv.rect(x + 78, y + h - 34, 4, 22, (60, 60, 70))
        cv.rect(x + 82, y + h - 34, 22, 12, (178, 34, 34))
        cv.ellipse(x + 150, y + 14, 8, 3, (20, 20, 26))
        cv.line(x + 20, y + h - 6, x + w - 20, y + h - 6, 1, WHITE)
        smoke(cv, x + 120, y + h - 40, 5)
    elif key == "ballot":
        mini_bg(cv, x, y, w, h, (200, 200, 220), (150, 150, 180))
        # ballot box + paper
        cv.rect(x + 14, y + 18, 44, h - 18, (26, 43, 74))
        cv.rect(x + 22, y + 14, 28, 6, (26, 43, 74))
        cv.rect(x + 26, y + 2, 20, 14, WHITE)
        cv.line(x + 30, y + 6, x + 42, y + 6, 1, RED)
        # bar chart
        for i, bh in enumerate([10, 16, 22]):
            cv.rect(x + 76 + i * 16, y + h - bh, 11, bh, RED if i == 2 else
                    (120, 120, 130))
        # donut 98.79%
        dx, dy = x + w - 34, y + h // 2 + 2
        cv.circle(dx, dy, 15, RED)
        pie_wedge(cv, dx, dy, 0, 15, 1.62, 1.69, CREAM2)
        cv.circle(dx, dy, 8, CREAM2)
        draw_text(cv, dx, dy + 3, "99%", 8, RED, track=0.4, align="center")
        draw_text(cv, x + 76, y + 10, "98.79%", 11, RED, track=0.4)
    elif key == "cricket":
        mini_bg(cv, x, y, w, h, (120, 190, 130), (46, 110, 62))
        cv.rect(x + 30, y + 14, w - 60, h - 14, (210, 190, 140))
        cv.rect(x + w // 2 - 3, y + 18, 2, 12, (240, 240, 230))
        cv.rect(x + w // 2 + 3, y + 18, 2, 12, (240, 240, 230))
        cv.line(x + 40, y + h - 12, x + 70, y + h - 26, 4, (150, 110, 60))
        cv.circle(x + 150, y + 16, 5, RED)
        draw_text(cv, x + w - 8, y + 14, "720/9", 13, WHITE, track=0.4,
                  align="right")
        cv.circle(x + 26, y + 10, 5, (240, 200, 80))
    elif key == "f1":
        mini_bg(cv, x, y, w, h, (40, 40, 60), (90, 60, 120))
        cv.poly([(x, y + h - 8), (x + w, y + h - 20), (x + w, y + h - 6),
                 (x, y + h)], (60, 60, 66))
        cv.rect(x + 60, y + h - 26, 52, 10, (200, 30, 30))
        cv.circle(x + 70, y + h - 14, 5, (20, 20, 20))
        cv.circle(x + 102, y + h - 14, 5, (20, 20, 20))
        for i in range(4):
            for j in range(2):
                cv.rect(x + 150 + i * 6, y + 8 + j * 6, 6, 6,
                        WHITE if (i + j) % 2 == 0 else INK)
        cv.circle(x + 26, y + 12, 6, (240, 200, 80))
        cv.circle(x + w - 30, y + 10, 4, WHITE)
    elif key == "nba":
        mini_bg(cv, x, y, w, h, (220, 140, 60), (160, 90, 40))
        cv.rect(x + 20, y + 10, 3, 26, WHITE)
        cv.ellipse(x + 34, y + 32, 12, 4, (200, 40, 40))
        cv.circle(x + 130, y + 22, 11, (230, 120, 40))
        cv.line(x + 130, y + 11, x + 130, y + 33, 1, INK)
        cv.rect(x + 140, y + 6, 34, 16, (26, 43, 74))
        draw_text(cv, x + 157, y + 18, "50", 12, WHITE, track=0.4,
                  align="center")
        cv.line(x + 60, y + h - 4, x + 120, y + h - 4, 2, WHITE)
    elif key == "house":
        mini_bg(cv, x, y, w, h, (190, 200, 220), (150, 160, 190))
        # capitol dome
        cv.rect(x + 20, y + 22, 50, h - 22, (235, 230, 220))
        cv.ellipse(x + 45, y + 20, 22, 12, (235, 230, 220))
        cv.rect(x + 43, y + 6, 4, 6, (120, 110, 95))
        for cx in (x + 28, x + 42, x + 56):
            cv.rect(cx, y + 28, 5, h - 28, (120, 110, 95))
        # 258/435 bar
        cv.rect(x + 90, y + 14, 84, 9, (200, 200, 205))
        cv.rect(x + 90, y + 14, 50, 9, (26, 43, 74))
        draw_text(cv, x + 90, y + 34, "258 / 435", 11, NAVY, track=0.4)
        draw_text(cv, x + 90, y + 46, "DEMOCRATS", 8, GREY, track=0.4)
    elif key == "handshake":
        mini_bg(cv, x, y, w, h, (200, 210, 230), (160, 170, 200))
        # UK flag
        cv.rect(x + 16, y + 10, 40, 24, (26, 43, 120))
        cv.rect(x + 32, y + 10, 8, 24, WHITE)
        cv.rect(x + 16, y + 20, 40, 6, WHITE)
        cv.rect(x + 34, y + 10, 4, 24, RED)
        cv.rect(x + 16, y + 22, 40, 3, RED)
        # EU flag
        cv.rect(x + w - 56, y + 10, 40, 24, (26, 43, 120))
        for i in range(6):
            a = i * pi / 3
            cv.rect(x + w - 36 + int(11 * cos(a)) - 1,
                    y + 22 + int(8 * sin(a)) - 1, 2, 2, (240, 200, 80))
        # handshake arc + check
        arc_line(cv, x + w // 2, y + h - 4, 30, 16, 0.3, 2.8, 3, GREEN)
        cv.poly([(x + w // 2 - 4, y + h - 18), (x + w // 2 + 2, y + h - 26),
                 (x + w // 2 + 12, y + h - 36), (x + w // 2 + 16, y + h - 32),
                 (x + w // 2 + 6, y + h - 22), (x + w // 2 + 2, y + h - 14)],
                GREEN)
    elif key == "power":
        mini_bg(cv, x, y, w, h, (60, 60, 80), (20, 20, 36))
        cv.line(x + 30, y + h, x + 44, y + 6, 2, (150, 150, 160))
        cv.line(x + 58, y + h, x + 44, y + 6, 2, (150, 150, 160))
        cv.line(x + 34, y + 22, x + 54, y + 22, 2, (150, 150, 160))
        cv.line(x + 28, y + 12, x + 60, y + 12, 2, (150, 150, 160))
        cv.poly([(x + 96, y + 4), (x + 84, y + 24), (x + 92, y + 24),
                 (x + 82, y + 42), (x + 100, y + 20), (x + 92, y + 20)],
                (240, 200, 80))
        cv.circle(x + 150, y + 10, 7, (240, 230, 200))
        cv.rect(x + 130, y + h - 16, 40, 16, (30, 30, 44))
        cv.rect(x + 136, y + h - 12, 4, 4, (240, 200, 80))
    elif key == "hospital":
        mini_bg(cv, x, y, w, h, (200, 220, 230), (170, 190, 210))
        cv.rect(x + 30, y + 10, w - 90, h - 10, WHITE)
        cv.rect(x + 52, y + 16, 12, 4, RED)
        cv.rect(x + 56, y + 12, 4, 12, RED)
        for wy in range(y + 30, y + h - 4, 8):
            cv.rect(x + 36, wy, 8, 5, (150, 180, 210))
        cv.rect(x + w - 56, y + h - 18, 44, 14, (240, 240, 240))
        cv.rect(x + w - 50, y + h - 15, 8, 3, RED)
        cv.rect(x + w - 47, y + h - 18, 3, 8, RED)
        cv.circle(x + w - 46, y + h - 4, 3, INK)
        cv.circle(x + w - 20, y + h - 4, 3, INK)
        cv.circle(x + 18, y + 12, 6, GREEN)
    elif key == "cyber":
        mini_bg(cv, x, y, w, h, (30, 36, 50), (60, 70, 100))
        cv.rect(x + 16, y + 8, 90, 30, (20, 28, 44))
        draw_text(cv, x + 22, y + 20, "01001101", 10, (80, 220, 120),
                  track=0.4)
        draw_text(cv, x + 22, y + 33, "FBI.DB", 10, (240, 200, 80),
                  track=0.4)
        cv.ellipse(x + w - 36, y + 16, 11, 11, (200, 200, 210))
        cv.ellipse(x + w - 36, y + 16, 8, 8, (30, 36, 50))
        cv.line(x + w - 27, y + 24, x + w - 18, y + 33, 3, (200, 200, 210))
        cv.poly([(x + 130, y + h - 6), (x + 150, y + h - 6),
                 (x + 140, y + h - 22)], (200, 40, 40))
        draw_text(cv, x + 140, y + h - 10, "!", 10, WHITE, track=0.4,
                  align="center")
    elif key == "fire":
        mini_bg(cv, x, y, w, h, (90, 70, 70), (40, 30, 30))
        cv.rect(x + 20, y + 20, 90, h - 20, (120, 110, 100))
        cv.rect(x + 96, y + 4, 10, 18, (100, 90, 84))
        smoke(cv, x + 101, y + 2, 6, (90, 86, 80))
        cv.poly([(x + 30, y + h), (x + 46, y + h - 22), (x + 54, y + h - 8),
                 (x + 62, y + h - 26), (x + 78, y + h), ], ORANGE)
        cv.poly([(x + 40, y + h), (x + 50, y + h - 14), (x + 60, y + h)],
                YELLOW)
        cv.rect(x + 130, y + h - 14, 46, 10, (200, 40, 40))
        cv.circle(x + 140, y + h - 4, 4, INK)
        cv.circle(x + 166, y + h - 4, 4, INK)
    elif key == "gaza":
        mini_bg(cv, x, y, w, h, (200, 190, 170), (150, 140, 125))
        for i, (bw, bh) in enumerate([(36, 26), (30, 34), (40, 22)]):
            cv.rect(x + 16 + i * 48, y + h - bh, bw, bh, (120, 112, 100))
        smoke(cv, x + 60, y + 10, 8, (110, 106, 100))
        smoke(cv, x + 90, y + 18, 6, (130, 126, 120))
        cv.rect(x + 140, y + h - 18, 36, 16, WHITE)
        cv.rect(x + 154, y + h - 15, 10, 3, RED)
        cv.rect(x + 158, y + h - 18, 3, 9, RED)
        cv.ellipse(x + 30, y + 12, 22, 7, ORANGE)
    elif key == "tennis":
        mini_bg(cv, x, y, w, h, (120, 190, 130), (46, 110, 62))
        cv.rect(x + 20, y + 10, w - 40, h - 10, (90, 160, 100))
        cv.line(x, y + h // 2 + 4, x + w, y + h // 2 + 4, 2, WHITE)
        cv.circle(x + 40, y + 16, 6, (200, 230, 80))
        cv.circle(x + 150, y + h - 14, 6, (200, 230, 80))
        cv.rect(x + w - 44, y + 8, 16, 12, GOLD)
        cv.rect(x + w - 47, y + 10, 3, 8, GOLD)
        cv.rect(x + w - 25, y + 10, 3, 8, GOLD)
        cv.rect(x + w - 40, y + 20, 8, 3, GOLD)
    elif key == "ship":
        mini_bg(cv, x, y, w, h, (150, 180, 210), (52, 96, 140))
        cv.rect(x, y + h - 14, w, 14, (30, 60, 100))
        cv.poly([(x + 30, y + h - 14), (x + 150, y + h - 14),
                 (x + 140, y + h - 2), (x + 40, y + h - 2)], (70, 70, 80))
        for i, c in enumerate([(200, 40, 40), (240, 200, 80), (40, 120, 90)]):
            cv.rect(x + 48 + i * 26, y + h - 34, 22, 20, c)
        cv.rect(x + 132, y + h - 30, 14, 16, (230, 230, 230))
        smoke(cv, x + 140, y + h - 36, 5)
        cv.line(x + 20, y + h - 8, x + w - 20, y + h - 8, 1, WHITE)
        cloud(cv, x + 40, y + 8, 6)

# ---- world map -----------------------------------------------------------
def draw_map(cv, x, y, w, h):
    cv.rect(x, y, w, h, (214, 228, 238))
    land = (222, 210, 178)
    # rough flat continents
    cv.poly([(x + w * 0.06, y + h * 0.30), (x + w * 0.12, y + h * 0.08),
             (x + w * 0.26, y + h * 0.10), (x + w * 0.30, y + h * 0.26),
             (x + w * 0.24, y + h * 0.42), (x + w * 0.16, y + h * 0.44),
             (x + w * 0.10, y + h * 0.52), (x + w * 0.05, y + h * 0.38)],
            land)  # North America
    cv.poly([(x + w * 0.27, y + h * 0.52), (x + w * 0.36, y + h * 0.52),
             (x + w * 0.38, y + h * 0.68), (x + w * 0.33, y + h * 0.88),
             (x + w * 0.29, y + h * 0.80), (x + w * 0.26, y + h * 0.64)],
            land)  # South America
    cv.poly([(x + w * 0.44, y + h * 0.16), (x + w * 0.52, y + h * 0.10),
             (x + w * 0.56, y + h * 0.20), (x + w * 0.52, y + h * 0.30),
             (x + w * 0.45, y + h * 0.28), (x + w * 0.43, y + h * 0.20)],
            land)  # Europe
    cv.poly([(x + w * 0.45, y + h * 0.34), (x + w * 0.58, y + h * 0.32),
             (x + w * 0.60, y + h * 0.48), (x + w * 0.55, y + h * 0.66),
             (x + w * 0.48, y + h * 0.62), (x + w * 0.44, y + h * 0.46)],
            land)  # Africa
    cv.poly([(x + w * 0.56, y + h * 0.08), (x + w * 0.95, y + h * 0.10),
             (x + w * 0.94, y + h * 0.34), (x + w * 0.82, y + h * 0.44),
             (x + w * 0.72, y + h * 0.40), (x + w * 0.64, y + h * 0.46),
             (x + w * 0.58, y + h * 0.30), (x + w * 0.55, y + h * 0.16)],
            land)  # Asia
    cv.poly([(x + w * 0.82, y + h * 0.62), (x + w * 0.94, y + h * 0.60),
             (x + w * 0.95, y + h * 0.72), (x + w * 0.86, y + h * 0.76),
             (x + w * 0.81, y + h * 0.68)], land)  # Australia
    # pins with leader lines for the dense Europe / Middle East cluster
    leaders = {1: (-34, -16), 2: (16, -18), 3: (24, 6), 4: (-40, 2),
               11: (-30, 14), 12: (26, -14), 16: (20, 16), 17: (-6, -20),
               18: (10, -22)}
    for (n, px, py) in MAP_PINS:
        cx = x + int(w * px); cy = y + int(h * py)
        col = RED if n <= 3 else (60, 90, 160)
        if n in leaders:
            lx, ly = leaders[n]
            cv.line(cx, cy, cx + lx, cy + ly, 1, (90, 86, 78))
            cx, cy = cx + lx, cy + ly
        cv.circle(cx, cy, 7, col)
        draw_text(cv, cx, cy + 3, str(n), 8, WHITE, track=0.4, align="center")

# ---- page assembly -------------------------------------------------------
MX = 16            # side margin
CW = 992           # content width (16..1008)
WARN = []

def _check(cond, msg):
    if not cond:
        WARN.append(msg)

def _rule(cv, x, y, w, col=LINE, h=1):
    cv.rect(x, y, w, h, col)

def draw_page():
    cv = Canvas()
    cv.rect(0, 0, W, PH, PAPER)

    # ---- header bar ------------------------------------------------------
    cv.rect(0, 0, W, 28, NAVY)
    draw_text(cv, W // 2, 19, HEADER_BAR, 13, WHITE, track=0.6,
              align="center")

    # ---- title -----------------------------------------------------------
    draw_text(cv, W // 2, 88, TITLE_L1, 58, INK, track=0.8, align="center")
    draw_text(cv, W // 2, 136, TITLE_L2, 28, INK, track=0.8, align="center")
    draw_text(cv, W // 2, 160, SUBHEAD, 15, RED, track=0.6, italic=True,
              align="center")

    # ---- numbers strip ---------------------------------------------------
    bx = MX
    bw = (CW - 5 * 8) // 6
    for i, (num, lab) in enumerate(NUMBERS):
        x0 = bx + i * (bw + 8)
        w0 = bw if i < 5 else (MX + CW) - x0
        cv.rect(x0, 170, w0, 48, WHITE)
        _rule(cv, x0, 170, w0, RED, 2)
        draw_text(cv, x0 + w0 // 2, 206, num, 36, RED, track=0.6,
                  align="center")
        draw_text(cv, x0 + w0 // 2, 215, lab, 9, GREY, track=0.5,
                  align="center")

    # ---- region tabs -----------------------------------------------------
    tw = (CW - 9 * 4) // 10
    for i, (name, cnt) in enumerate(REGIONS):
        x0 = MX + i * (tw + 4)
        col = REGION_COLORS[i]
        dark = (col[0] * 3 // 4, col[1] * 3 // 4, col[2] * 3 // 4)
        cv.rect(x0, 222, tw, 20, dark)
        draw_text(cv, x0 + tw // 2, 237, name + " \u00b7 " + str(cnt), 9,
                  WHITE, track=0.4, align="center")

    # ---- timeline --------------------------------------------------------
    draw_text(cv, MX, 260, "THE DAY IN UTC", 10, NAVY, track=0.6)
    ex = 150
    ew = (MX + CW - ex - 8) // 7
    for i, (t, lab) in enumerate(TIMELINE):
        x0 = ex + i * ew
        if i == 6:
            cv.rect(x0 - 4, 246, ew - 4, 18, RED)
            draw_text(cv, x0 + 2, 260, t, 10, WHITE, track=0.4)
            draw_text(cv, x0 + 30, 260, lab, 9, WHITE, track=0.4)
        else:
            draw_text(cv, x0, 260, t, 10, RED, track=0.4)
            draw_text(cv, x0 + 30, 260, lab, 9, INK, track=0.4)

    # ---- 3 lead stories --------------------------------------------------
    lead_w = 322
    lead_art = {"COP31 ends with no deal": art_cop31,
                "Russia fires 186 drones at Ukraine": art_kyiv,
                "Iran claims two US radars hit; Bahrain denies it": art_manama}
    for i, (num, loc, topic, badge_kind, head, body, src) in enumerate(LEADS):
        x0 = MX + i * (lead_w + 12)
        lead_art[head](cv, x0, 268, lead_w, 94)
        _rule(cv, x0, 268, lead_w, LINE, 1)
        _rule(cv, x0, 362, lead_w, LINE, 1)
        _rule(cv, x0, 268, 1, LINE, 94)
        _rule(cv, x0 + lead_w - 1, 268, 1, LINE, 94)
        draw_text(cv, x0, 376, str(num) + ". " + loc + " \u00b7 " + topic, 11,
                  GREY, track=0.5)
        bw2 = int(text_width(badge_kind, 9, 0.6)) + 10
        badge(cv, x0 + lead_w - bw2, 366, badge_kind, badge_kind)
        lines = wrap_text(head, 25, lead_w, track=0.8)
        _check(len(lines) <= 2, "lead %d headline wraps to %d lines"
               % (num, len(lines)))
        draw_lines(cv, x0, 406, lines[:2], 25, INK, 33, track=0.8)
        blines = wrap_text(body, 11, lead_w, track=0.5)
        _check(len(blines) <= 3, "lead %d body wraps to %d lines"
               % (num, len(blines)))
        draw_lines(cv, x0, 458, blines[:3], 11, INK, 15, track=0.5)
        draw_text(cv, x0, 502, "Source: " + src, 9, GREY, track=0.4)

    # ---- 15 small stories, 5 x 3 ----------------------------------------
    cell_w = 192
    for idx, (num, loc, topic, badge_kind, head, body, src, art) in enumerate(SMALL):
        r, c = divmod(idx, 5)
        x0 = MX + c * (cell_w + 8)
        y0 = 512 + r * 92
        art_small(cv, x0, y0, cell_w, 36, art)
        _rule(cv, x0, y0, cell_w, LINE, 1)
        _rule(cv, x0, y0 + 36, cell_w, LINE, 1)
        _rule(cv, x0, y0, 1, LINE, 36)
        _rule(cv, x0 + cell_w - 1, y0, 1, LINE, 36)
        draw_text(cv, x0, y0 + 46, str(num) + ". " + loc, 9, GREY, track=0.4)
        bw3 = int(text_width(badge_kind, 9, 0.6)) + 10
        badge(cv, x0 + cell_w - bw3, y0 + 37, badge_kind, badge_kind)
        hlines = wrap_text(head, 11, cell_w, track=0.5)
        _check(len(hlines) <= 2, "small %d headline wraps to %d lines"
               % (num, len(hlines)))
        draw_lines(cv, x0, y0 + 60, hlines[:2], 11, INK, 15, track=0.5)
        _check(text_width(body, 9, 0.4) <= cell_w,
               "small %d body too wide: %.0f" % (num, text_width(body, 9, 0.4)))
        draw_text(cv, x0, y0 + 88, body, 9, INK, track=0.4)

    # ---- ALSO list -------------------------------------------------------
    draw_text(cv, MX, 800, "ALSO ON SUNDAY 22 NOVEMBER \u2014 20 MORE STORIES",
              11, RED, track=0.6)
    _rule(cv, MX, 804, CW, RED, 1)
    for i, (region, text, src) in enumerate(ALSO):
        col = i % 2
        row = i // 2
        x0 = MX + col * 498
        yb = 814 + row * 10
        item = "%d. %s (%s)" % (19 + i, text, src)
        _check(text_width(item, 9.5, 0.4) <= 494,
               "also %d too wide: %.0f" % (19 + i, text_width(item, 9.5, 0.4)))
        draw_text(cv, x0, yb, "%d." % (19 + i), 9.5, RED, track=0.4)
        draw_text(cv, x0 + 22, yb, text + " ", 9.5, INK, track=0.4)
        twd = text_width(text, 9.5, 0.4)
        draw_text(cv, x0 + 22 + twd, yb, "(" + src + ")", 9.5, GREY,
                  track=0.4)

    # ---- map + date check ------------------------------------------------
    draw_text(cv, MX, 918, "WHERE IT HAPPENED", 11, NAVY, track=0.6)
    draw_map(cv, MX, 922, 490, 76)
    # date check box
    dx0, dy0, dw, dh = 514, 910, 494, 88
    cv.rect(dx0, dy0, dw, dh, (253, 240, 238))
    _rule(cv, dx0, dy0, dw, RED, 2)
    _rule(cv, dx0, dy0 + dh - 1, dw, RED, 1)
    _rule(cv, dx0, dy0, 1, RED, dh)
    _rule(cv, dx0 + dw - 1, dy0, 1, RED, dh)
    draw_text(cv, dx0 + 8, 922, "DATE CHECK \u2014 NOT 22 NOVEMBER", 11, RED,
              track=0.6)
    for i, item in enumerate(DATE_CHECK):
        col = i % 2
        row = i // 2
        x0 = dx0 + 8 + col * 246
        yb = 930 + row * 10
        _check(text_width(item, 8.5, 0.4) <= 240,
               "datecheck %d too wide: %.0f" % (i, text_width(item, 8.5, 0.4)))
        draw_text(cv, x0, yb, "\u00d7", 8.5, RED, track=0.4)
        draw_text(cv, x0 + 10, yb, item, 8.5, INK, track=0.4)

    # ---- footer ----------------------------------------------------------
    _rule(cv, MX, 1000, CW, LINE, 1)
    draw_text(cv, MX, 1010, SOURCES, 10, INK, track=0.4)
    draw_text(cv, MX, 1020, LEGEND + "   \u00b7   " + FOOT_NOTE, 9, GREY,
              track=0.4)

    for wmsg in WARN:
        print("WARN:", wmsg)
    return cv

def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    cv = draw_page()
    path = os.path.join(outdir, "entry.png")
    cv.save(path)
    print("wrote", path)

if __name__ == "__main__":
    if os.environ.get("FONT_TEST"):
        font_test()
    else:
        main()
