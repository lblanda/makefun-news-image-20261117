#!/usr/bin/env python3
"""news-image-20261117: sum up the world news of Tuesday 17 November 2026
in one 1024x1024 editorial poster image.

Pure Python 3 standard library only (the grading sandbox installs nothing
and has no network): a tiny 5x7 bitmap font, a small vector canvas, and a
hand-rolled PNG encoder. All news content is baked into this file; the
program reads no files and fetches nothing at run time. It writes
entry.png into $MAKEFUN_OUTPUT_DIR (default /output) and is fully
deterministic: the same input always produces the same bytes.
"""

import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- font
# 5x7 bitmap font, one 35-character string per glyph (7 rows of 5 bits,
# row-major, "1" = ink). Only capitals, digits and common punctuation:
# all poster text is upper-cased before drawing.
FONT = {
    "A": "01110100011000111111100011000110001",
    "B": "11110100011000111110100011000111110",
    "C": "01110100011000010000100001000101110",
    "D": "11110100011000110001100011000111110",
    "E": "11111100001000011110100001000011111",
    "F": "11111100001000011110100001000010000",
    "G": "01110100011000010111100011000101111",
    "H": "10001100011000111111100011000110001",
    "I": "01110001000010000100001000010001110",
    "J": "00111000100001000010000101001001100",
    "K": "10001100101010011000101001001010001",
    "L": "10000100001000010000100001000011111",
    "M": "10001110111010110101100011000110001",
    "N": "10001110011010110011100011000110001",
    "O": "01110100011000110001100011000101110",
    "P": "11110100011000111110100001000010000",
    "Q": "01110100011000110001101011001001101",
    "R": "11110100011000111110101001001010001",
    "S": "01111100001000001110000010000111110",
    "T": "11111001000010000100001000010000100",
    "U": "10001100011000110001100011000101110",
    "V": "10001100011000110001100010101000100",
    "W": "10001100011000110101101011010101010",
    "X": "10001100010101000100010101000110001",
    "Y": "10001100010101000100001000010000100",
    "Z": "11111000010001000100010001000011111",
    "0": "01110100011001110101110011000101110",
    "1": "00100011000010000100001000010001110",
    "2": "01110100010000100110010001000011111",
    "3": "11111000100010000010000011000101110",
    "4": "00010001100101010010111110001000010",
    "5": "11111100001111000001000011000101110",
    "6": "00110010001000011110100011000101110",
    "7": "11111000010001000100010000100001000",
    "8": "01110100011000101110100011000101110",
    "9": "01110100011000101111000010001001100",
    " ": "00000000000000000000000000000000000",
    ".": "00000000000000000000000000110001100",
    ",": "00000000000000000000011000010001000",
    ":": "00000011000110000000011000110000000",
    ";": "00000011000110000000011000010001000",
    "!": "00100001000010000100001000000000100",
    "?": "01110100010000100110001000000000100",
    "-": "00000000000000001110000000000000000",
    "'": "00100001000100000000000000000000000",
    '"': "01010010100101000000000000000000000",
    "(": "00010001000100001000010000010000010",
    ")": "01000001000001000010000100010001000",
    "/": "00001000100001000100010000100010000",
    "%": "11001110100001000100010000101110011",
    "$": "00100011111010001110001011111000100",
    "&": "01100100101010001000101011001001101",
    "+": "00000001000010011111001000010000000",
    "=": "00000000001111100000111110000000000",
    "*": "00000101010111011111011101010100000",
    "•": "00000000000110001100011000000000000",
    "[": "01110010000100001000010000100001110",
    "]": "01110000100001000010000100001001110",
    "_": "00000000000000000000000000000011111",
}


def glyph_rows(ch):
    """Return the 7 rows of 5 bits for a character (unknown -> blank)."""
    bits = FONT.get(ch, FONT[" "])
    return [bits[i * 5:(i + 1) * 5] for i in range(7)]


# ---------------------------------------------------------------- canvas
class Canvas:
    """An RGB pixel buffer with simple filled drawing primitives."""

    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg * (w * h))

    def set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = color

    def rect(self, x, y, w, h, color):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:(x1 - x0) * 3 + i] = color * (x1 - x0)

    def hline(self, x, y, w, color, t=1):
        self.rect(x, y, w, t, color)

    def vline(self, x, y, h, color, t=1):
        self.rect(x, y, t, h, color)

    def line(self, x0, y0, x1, y1, color, t=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.rect(x0 - t // 2, y0 - t // 2, t, t, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, color, fill=True):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d2 = (xx - cx) ** 2 + (yy - cy) ** 2
                if fill and d2 <= r * r:
                    self.set(xx, yy, color)
                elif not fill and abs(d2 - r * r) <= r:
                    self.set(xx, yy, color)

    def triangle(self, pts, color):
        (x0, y0), (x1, y1), (x2, y2) = pts
        minx, maxx = min(x0, x1, x2), max(x0, x1, x2)
        miny, maxy = min(y0, y1, y2), max(y0, y1, y2)
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if d == 0:
            return
        for yy in range(miny, maxy + 1):
            for xx in range(minx, maxx + 1):
                a = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / d
                b = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / d
                c = 1 - a - b
                if a >= 0 and b >= 0 and c >= 0:
                    self.set(xx, yy, color)


# ---------------------------------------------------------------- text
def text_width(text, scale):
    return len(text) * 6 * scale - scale


def draw_text(cv, x, y, text, color, scale):
    """Draw upper-cased text; returns the x just past the last glyph."""
    for ch in text.upper():
        rows = glyph_rows(ch)
        for r in range(7):
            row = rows[r]
            for c in range(5):
                if row[c] == "1":
                    cv.rect(x + c * scale, y + r * scale, scale, scale, color)
        x += 6 * scale
    return x


def wrap_text(text, scale, max_width):
    """Greedy word wrap; returns a list of lines fitting max_width."""
    lines, cur = [], ""
    for word in text.upper().split(" "):
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, y, text, color, scale, max_width, leading=None):
    """Draw a wrapped paragraph; returns the y just below the last line."""
    leading = leading if leading is not None else 7 * scale + 4
    for line in wrap_text(text, scale, max_width):
        draw_text(cv, x, y, line, color, scale)
        y += leading
    return y


def draw_centered(cv, cx, y, text, color, scale):
    draw_text(cv, cx - text_width(text, scale) // 2, y, text, color, scale)


# ---------------------------------------------------------------- palette
PAPER = bytes((245, 239, 227))   # warm newsprint
INK = bytes((26, 26, 26))
NAVY = bytes((20, 38, 74))
NAVY2 = bytes((28, 52, 96))
GOLD = bytes((232, 196, 104))
RED = bytes((179, 39, 30))
WHITE = bytes((255, 255, 255))
CARD = bytes((255, 255, 255))
GREY = bytes((90, 90, 86))
TEAL = bytes((15, 94, 91))
OCHRE = bytes((176, 116, 28))
SLATE = bytes((61, 90, 128))
PLUM = bytes((109, 46, 70))
GREEN = bytes((47, 107, 58))
RUST = bytes((122, 74, 33))
SEA = bytes((58, 110, 145))
SAND = bytes((214, 186, 138))

# ---------------------------------------------------------------- stories
# Everything below was reported on Tuesday 17 November 2026. Each panel
# carries its own headline, place and facts so the image alone tells the day.
LEAD_KICKER = "LEAD  •  WAR IN WEST ASIA"
LEAD_HEAD = ["US JETS STRIKE IRAN,", "TEHRAN HITS BACK"]
LEAD_BODY = (
    "US jets hit a missile site on Qeshm Island after Iran fired drones "
    "at a US radar base in Bahrain, the third attack there in five days. "
    "A third US carrier, USS Theodore Roosevelt, has arrived in the "
    "region, and a tanker was attacked in the Strait of Hormuz."
)

PANELS = [
    dict(kicker="UKRAINE", color=SLATE,
         head=["KERCH BRIDGE", "HIT AGAIN"],
         body="Ukrainian drones hit the Crimea link again; a road span "
              "falls into the strait in a 1,300-drone barrage.",
         icon="bridge"),
    dict(kicker="ASIA SUMMIT", color=TEAL,
         head=["TRUMP IN MANILA", "FOR THE QUAD"],
         body="Leaders meet at the ASEAN summit; China confirms a "
              "Trump-Xi-Putin trilateral for 19 Nov.",
         icon="globe"),
    dict(kicker="MARKETS", color=RUST,
         head=["STOCKS SLIDE;", "NASDAQ IN CORRECTION"],
         body="Nasdaq falls 2.5%, the S&P 1.9%, the Dow 1.4%. Brent crude "
              "drops to $92.44; gold to $3,848.",
         icon="chart"),
    dict(kicker="TECH", color=PLUM,
         head=["NVIDIA: RECORD", "$115BN, NO COMEBACK"],
         body="Revenue doubles, but the board will not reinstate ousted "
              "chief Jensen Huang.",
         icon="chip"),
    dict(kicker="CYBERATTACK", color=GREEN,
         head=["178 TOP SITES HIT", "IN CRYPTO HEIST"],
         body="Code slipped in via Optimizely hit the BBC, CNN, Zoom and "
              "HSBC, stealing card and crypto data.",
         icon="bug"),
    dict(kicker="CLIMATE & HEALTH", color=OCHRE,
         head=["COP31: FAST EXIT", "FROM FOSSIL FUELS"],
         body="Draft deal: a fast exit from fossil fuels. Ebola in DR "
              "Congo passes 11,000 cases, 5,400 dead.",
         icon="leaf"),
]

TICKER = (
    "ALSO TODAY  •  CYCLONE AKVAN BEARS DOWN ON INDIA'S ANDHRA COAST  •  "
    "VULCAN ROCKET FAILS, 40 AMAZON SATELLITES LOST  •  FIVE EU STATES "
    "PLAN A RWANDA RETURNS HUB  •  NEPAL FIRST FOR UN LOSS-AND-DAMAGE "
    "CASH  •  ROBERT PATTINSON IS THE NEW JAMES BOND"
)

FOOTER = "THE WORLD IN ONE DAY  •  TUESDAY 17 NOVEMBER 2026  •  ALL STORIES REPORTED ON THE DAY"


# ---------------------------------------------------------------- icons
def draw_icon(cv, kind, x, y, s, color):
    """Small geometric pictogram, s = half-size in pixels."""
    if kind == "bridge":
        cv.rect(x - s, y + s // 2, 2 * s, 3, color)
        cv.rect(x - s, y - s, 3, 2 * s, color)
        cv.rect(x + s - 3, y - s, 3, 2 * s, color)
        cv.line(x - s, y + s // 2, x, y - s // 2, color, 2)
        cv.line(x + s, y + s // 2, x, y - s // 2, color, 2)
    elif kind == "globe":
        cv.circle(x, y, s, color, fill=False)
        cv.hline(x - s, y, 2 * s, color, 2)
        cv.vline(x, y - s, 2 * s, color, 2)
        cv.line(x - s + 4, y - s + 6, x + s - 4, y - s + 6, color, 2)
        cv.line(x - s + 4, y + s - 6, x + s - 4, y + s - 6, color, 2)
    elif kind == "chart":
        cv.hline(x - s, y + s, 2 * s, color, 3)
        cv.vline(x - s, y - s, 2 * s, color, 3)
        cv.line(x - s + 2, y - s + 6, x - s // 3, y - 2, color, 3)
        cv.line(x - s // 3, y - 2, x + s // 3, y + 2, color, 3)
        cv.line(x + s // 3, y + 2, x + s - 2, y + s - 4, color, 3)
    elif kind == "chip":
        cv.rect(x - s + 4, y - s + 4, 2 * s - 8, 2 * s - 8, color)
        cv.rect(x - s // 2, y - s // 2, s, s, PAPER)
        for dx in (-s - 3, -s // 2, 0, s // 2):
            cv.rect(x + dx, y - s - 3, 3, 3, color)
            cv.rect(x + dx, y + s, 3, 3, color)
    elif kind == "bug":
        cv.circle(x, y, s // 2, color)
        cv.circle(x, y - s // 2, s // 3, color)
        for dy in (-4, 2, 8):
            cv.line(x - s // 2, y + dy, x - s, y + dy - 4, color, 2)
            cv.line(x + s // 2, y + dy, x + s, y + dy - 4, color, 2)
    elif kind == "leaf":
        cv.circle(x, y - 2, s // 2, color)
        for k in range(8):
            ang = k * 3.14159 / 4
            import math
            ex = int(x + (s + 2) * math.cos(ang))
            ey = int(y - 2 + (s + 2) * math.sin(ang))
            cv.line(x, y - 2, ex, ey, color, 2)


def draw_lead_map(cv, x, y, w, h):
    """Stylised Gulf map: sea, land, Qeshm strike, Bahrain, Hormuz tanker."""
    cv.rect(x, y, w, h, NAVY2)
    # land masses (tan blocks, top-left and bottom-right)
    cv.rect(x, y, w // 2, h // 3, SAND)
    cv.rect(x + w // 2, y + 2 * h // 3, w // 2, h // 3, SAND)
    # Qeshm Island: small island + red strike starburst
    qx, qy = x + w // 2 + 26, y + h // 2 - 26
    cv.rect(qx - 16, qy - 5, 34, 10, SAND)
    for k in range(8):
        import math
        a = k * 3.14159 / 4
        cv.line(qx, qy, int(qx + 22 * math.cos(a)),
                int(qy + 22 * math.sin(a)), RED, 3)
    cv.circle(qx, qy, 7, RED)
    # Bahrain: white dot + label
    bx, by = x + w // 4, y + h // 2 + 8
    cv.circle(bx, by, 5, WHITE)
    cv.circle(bx, by, 2, RED)
    # tanker in the strait
    tx, ty = x + w // 2 + 4, y + h - 34
    cv.rect(tx - 26, ty, 52, 12, WHITE)
    cv.rect(tx + 8, ty - 10, 12, 10, WHITE)
    cv.line(tx - 26, ty + 12, tx + 26, ty + 12, GOLD, 2)
    # labels (all on the dark sea, for contrast)
    draw_text(cv, x + 10, y + h - 22, "PERSIAN GULF", WHITE, 1)
    draw_text(cv, qx + 28, qy - 4, "QESHM ISLAND", GOLD, 1)
    draw_text(cv, bx - 24, by + 12, "BAHRAIN", WHITE, 1)
    draw_text(cv, tx - 78, ty + 2, "HORMUZ", WHITE, 1)


# ---------------------------------------------------------------- layout
def build():
    cv = Canvas(W, H, PAPER)

    # --- masthead ------------------------------------------------------
    cv.rect(16, 16, W - 32, 104, NAVY)
    cv.rect(16, 16, W - 32, 4, GOLD)
    draw_centered(cv, W // 2, 30, "THE WORLD IN ONE DAY", GOLD, 2)
    draw_centered(cv, W // 2, 52, "TUESDAY, 17 NOVEMBER 2026", WHITE, 4)
    draw_centered(cv, W // 2, 92, "THE DAY'S BIGGEST STORIES, IN ONE PICTURE",
                  bytes((180, 196, 224)), 1)

    # --- lead story ----------------------------------------------------
    lx, ly, lw, lh = 16, 132, W - 32, 296
    cv.rect(lx, ly, lw, lh, CARD)
    cv.rect(lx, ly, 8, lh, RED)
    cv.rect(lx, ly, lw, 30, RED)
    draw_text(cv, lx + 20, ly + 8, LEAD_KICKER, WHITE, 2)
    # headline, left; map, right
    hx, hw = lx + 20, 560
    hy = ly + 48
    for line in LEAD_HEAD:
        draw_text(cv, hx, hy, line, INK, 4)
        hy += 36
    hy += 8
    draw_para(cv, hx, hy, LEAD_BODY, INK, 2, hw, leading=20)
    draw_lead_map(cv, lx + 620, ly + 42, 348, 232)

    # --- story grid: 2 columns x 3 rows -------------------------------
    gx, gy = 16, 440
    pw, ph, gap = 488, 152, 16
    for i, p in enumerate(PANELS):
        px = gx + (i % 2) * (pw + gap)
        py = gy + (i // 2) * (ph + gap)
        cv.rect(px, py, pw, ph, CARD)
        cv.rect(px, py, pw, 26, p["color"])
        draw_text(cv, px + 12, py + 6, p["kicker"], WHITE, 2)
        draw_icon(cv, p["icon"], px + pw - 30, py + 58, 16, p["color"])
        ty = py + 36
        for line in p["head"]:
            draw_text(cv, px + 12, ty, line, INK, 3)
            ty += 24
        draw_para(cv, px + 12, ty + 4, p["body"], GREY, 2, pw - 24,
                  leading=19)

    # --- ticker --------------------------------------------------------
    ty = 440 + 3 * 152 + 2 * 16
    cv.rect(16, ty, W - 32, 64, NAVY)
    draw_para(cv, 28, ty + 12, TICKER, GOLD, 1, W - 56, leading=13)

    # --- footer --------------------------------------------------------
    draw_centered(cv, W // 2, ty + 76, FOOTER, GREY, 1)
    return cv


# ---------------------------------------------------------------- png
def chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    out += struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return out


def write_png(cv, path):
    raw = bytearray()
    for y in range(cv.h):
        raw.append(0)  # filter: none
        raw += cv.px[y * cv.w * 3:(y + 1) * cv.w * 3]
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    size = write_png(build(), path)
    print(f"wrote {path} ({size} bytes, {W}x{H})")


if __name__ == "__main__":
    main()
