"""Blank the Perfect Works version number ("0.11.4") on the title screen; keep "Perfect Works".

The title-screen file (disc 1 file 1587, disc 2 file 1582; PW gamefiles/title_screen/1587.raw1) is
uncompressed: a 0x800-byte header, then a VRAM block 1024 x 88 of 16-bit pixels. It holds three
320-wide copies of the logo; each has "Perfect Works 0.11.4" in rows 2-4, starting at x = 195, 515
and 835. The version sits 85-115 px after that start. This sets those pixels to the background
colour 0x8000, after checking that the box holds nothing but grey text and background.

  python tools/title_noversion.py IN.bin OUT.bin FILE_INDEX [--preview out.png]
"""
import argparse
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xgdisc

HDR, W, BG = 0x800, 1024, 0x8000
STARTS = (195, 515, 835)          # x where "Perfect" begins in each logo copy
DX0, DX1 = 83, 118                # version box relative to that start (inclusive / exclusive)
Y0, Y1 = 1, 6                     # rows (text uses 2..4)
EXPECT_LEN = 182272


def grey(c):
    r, g, b = c & 31, (c >> 5) & 31, (c >> 10) & 31
    return max(r, g, b) - min(r, g, b) <= 6


def patch(raw):
    if len(raw) != EXPECT_LEN or struct.unpack_from("<HH", raw, 0) != (0x1200, 0) or struct.unpack_from("<H", raw, 12)[0] != 320:
        raise ValueError("not the PW title-screen file")
    out = bytearray(raw)
    changed = 0
    for s in STARTS:
        for y in range(Y0, Y1):
            for x in range(s + DX0, s + DX1):
                o = HDR + (y * W + x) * 2
                c = struct.unpack_from("<H", out, o)[0]
                if c != BG and not grey(c):
                    raise ValueError(f"unexpected non-text pixel {c:#06x} at ({x},{y})")
                if c != BG:
                    struct.pack_into("<H", out, o, BG)
                    changed += 1
    if changed == 0:
        raise ValueError("no version pixels found (already patched?)")
    return bytes(out), changed


def write_same_size(path, idx, data):
    """Overwrite a file's own sectors in place; the table entry is not touched.

    xgdisc.write_file is not used: it measures free space up to the next table entry, and the
    bogus entries that span the disc can start inside this file, which makes it relocate.
    """
    import cdsector
    start, size = xgdisc.Disc(path).entries[idx]
    if len(data) != size:
        raise ValueError("size changed")
    with open(path, "r+b") as f:
        for k in range((size + xgdisc.DATA_LEN - 1) // xgdisc.DATA_LEN):
            chunk = data[k * xgdisc.DATA_LEN:(k + 1) * xgdisc.DATA_LEN]
            f.seek((start + k) * xgdisc.SECTOR)
            sec = bytearray(f.read(xgdisc.SECTOR))
            sec[xgdisc.DATA_OFF:xgdisc.DATA_OFF + len(chunk)] = chunk
            cdsector.fix_mode2_form1(sec)
            f.seek((start + k) * xgdisc.SECTOR)
            f.write(sec)


def preview(raw, path):
    from PIL import Image
    px = raw[HDR:]
    h = len(px) // (W * 2)
    v = struct.unpack_from(f"<{W * h}H", px)
    im = Image.new("RGB", (W, h))
    im.putdata([((c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3) for c in v])
    im.crop((0, 0, W, 20)).resize((W * 2, 40), Image.NEAREST).save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("index", type=int)
    ap.add_argument("--preview")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("refusing to patch in place")
    raw = xgdisc.Disc(a.src).read_file(a.index)
    new, n = patch(raw)
    if a.preview:
        preview(new, a.preview)
    shutil.copyfile(a.src, a.dst)
    write_same_size(a.dst, a.index, new)
    chk = xgdisc.Disc(a.dst)
    assert chk.entries[a.index] == xgdisc.Disc(a.src).entries[a.index], "table entry changed"
    assert chk.read_file(a.index) == new
    print(f"file {a.index}: {n} version pixels blanked -> {a.dst}")


if __name__ == "__main__":
    main()
