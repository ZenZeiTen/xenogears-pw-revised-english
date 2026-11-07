"""Replace the title-screen caption ("Perfect Works 0.11.4") with new text in the same pixel font.

Title file (disc 1 file 1587, disc 2 file 1582, uncompressed): header 0x800, then a VRAM block
1024 x 88 of 16-bit pixels. The 320 x 225 screen is stored row-interleaved across three 320-wide
columns: screen row R = column (R % 3), block row (R // 3). The caption occupies screen rows 7..13,
x 195..310, right-aligned; each row has one shade (white at the top to grey at the bottom).

Glyphs t e 0 1 . are copied from the original caption; the others are drawn to match it
(7 rows, 2-px left stems, lowercase letters 5 rows tall, 1 column between letters, 4 between words).

  python tools/title_text.py IN.bin OUT.bin FILE_INDEX "Ultimate Redux v.1.0" [--preview p.png]
"""
import argparse
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xgdisc
from title_noversion import write_same_size

HDR, VW, BG = 0x800, 1024, 0x8000
SHADES = [0x7FFF, 0x77BD, 0x6F7B, 0x6739, 0x5EF7, 0x56B5, 0x4E73]   # screen rows 7..13
TOP, RIGHT = 7, 310                                                 # caption baseline box
CLEAR_X = (180, 320)                                                # area wiped before drawing
LETTER_GAP, WORD_GAP = 1, 4

G = {
    # from the original caption
    "t": [".##..", ".##..", "#####", ".##..", ".##..", ".##..", "..###"],
    "e": [".....", ".....", ".###.", "##..#", "#####", "##...", ".###."],
    "0": [".#####.", "##...##", "##...##", "##...##", "##...##", "##...##", ".#####."],
    "1": [".##.", "###.", ".##.", ".##.", ".##.", ".##.", "####"],
    ".": ["..", "..", "..", "..", "..", "##", "##"],
    # drawn to match
    "U": ["##...##", "##...##", "##...##", "##...##", "##...##", "##...##", ".#####."],
    # leg drawn 2 px thick: a 1-px leg made the R read as "F" on screen (boot test, v8)
    "R": ["######.", "##....#", "##....#", "######.", "##.##..", "##..##.", "##...##"],
    "l": ["##", "##", "##", "##", "##", "##", "##"],
    "i": ["##", "..", "##", "##", "##", "##", "##"],
    "m": [".......", ".......", "######.", "##.#..#", "##.#..#", "##.#..#", "##.#..#"],
    "a": [".....", ".....", ".###.", "....#", ".####", "##..#", ".####"],
    "d": ["....##", "....##", ".#####", "##..##", "##..##", "##..##", ".#####"],
    "u": [".....", ".....", "##..#", "##..#", "##..#", "##..#", ".####"],
    "x": ["......", "......", "##...#", ".##.#.", "..##..", ".##.#.", "##...#"],
    "v": ["......", "......", "##...#", "##...#", ".##.#.", ".##.#.", "..##.."],
}


def off(x, row):
    """Byte offset of screen pixel (x, row) inside the file."""
    return HDR + ((row // 3) * VW + 320 * (row % 3) + x) * 2


def layout(text):
    cols, x = [], 0
    for word_i, word in enumerate(text.split(" ")):
        if word_i:
            x += WORD_GAP - LETTER_GAP
        for ch in word:
            if ch not in G:
                raise KeyError(f"no glyph for {ch!r}")
            g = G[ch]
            for gy, line in enumerate(g):
                for gx, p in enumerate(line):
                    if p == "#":
                        cols.append((x + gx, gy))
            x += len(g[0]) + LETTER_GAP
    return cols, x - LETTER_GAP


def patch(raw, text):
    if len(raw) != 182272 or struct.unpack_from("<H", raw, 12)[0] != 320:
        raise ValueError("not the PW title-screen file")
    out = bytearray(raw)
    # wipe the old caption: every pixel in the caption rows that has that row's shade
    wiped = 0
    for i, row in enumerate(range(TOP, TOP + 7)):
        for x in range(*CLEAR_X):
            o = off(x, row)
            if struct.unpack_from("<H", out, o)[0] == SHADES[i]:
                struct.pack_into("<H", out, o, BG)
                wiped += 1
    pix, width = layout(text)
    x0 = RIGHT + 1 - width
    if x0 < CLEAR_X[0]:
        raise ValueError(f"text too wide ({width} px)")
    for gx, gy in pix:
        struct.pack_into("<H", out, off(x0 + gx, TOP + gy), SHADES[gy])
    return bytes(out), wiped, len(pix), (x0, RIGHT)


def screen_png(raw, path, crop=None, scale=1):
    from PIL import Image
    im = Image.new("RGB", (320, 225))
    for R in range(225):
        for x in range(320):
            c = struct.unpack_from("<H", raw, off(x, R))[0]
            im.putpixel((x, R), ((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3))
    if crop:
        im = im.crop(crop)
    im.resize((im.width * scale, im.height * scale), Image.NEAREST).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("index", type=int); ap.add_argument("text")
    ap.add_argument("--preview")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("refusing to patch in place")
    src = xgdisc.Disc(a.src)
    raw, entry = src.read_file(a.index), src.entries[a.index]
    src.f.close()
    new, wiped, drawn, span = patch(raw, a.text)
    if a.preview:
        screen_png(new, a.preview, scale=2)
        screen_png(new, a.preview.replace(".png", "_zoom.png"), crop=(170, 0, 320, 24), scale=5)
    shutil.copyfile(a.src, a.dst)
    write_same_size(a.dst, a.index, new)
    chk = xgdisc.Disc(a.dst)
    assert chk.entries[a.index] == entry, "table entry changed"
    assert chk.read_file(a.index) == new
    print(f"file {a.index}: wiped {wiped} px, drew {drawn} px of {a.text!r} at x {span[0]}..{span[1]} -> {a.dst}")


if __name__ == "__main__":
    main()
