"""Check that OUT decodes to the same content as FINAL for every file, and that OUT differs
from BASE only inside rebuilt files and the file table (never sector 25).

  python verify_rebuild.py BASE.bin FINAL.bin OUT.bin
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import compact_rebuild as C, menu_patch as MP, xgdisc as X

def decoded(raw):
    if C.is_field(raw):
        s, _, sp = C.field_spans(raw)
        return ("field", tuple(C.section_content(s[k], sp[k]) for k in range(9)))
    try:
        k, parts = MP.containers(raw)
        return (k, tuple(d for _, d, _ in parts))
    except Exception:
        return ("raw", raw)

import game_lzss as G

def unsafe_streams(raw):
    """LZSS streams in this file that the game's own decoder would not stop on."""
    bad = 0
    if C.is_field(raw):
        s, _, sp = C.field_spans(raw)
        bad += sum(1 for k in range(9) if s[k] and sp[k] and not G.safe(sp[k]))
    else:
        try:
            for lz, _, orig in MP.containers(raw)[1]:
                bad += bool(lz and not G.safe(orig))
        except Exception:
            pass
    return bad

base_p, final_p, out_p = sys.argv[1:4]
bd, fd, od = X.Disc(base_p), X.Disc(final_p), X.Disc(out_p)
mism, checked, extents = [], 0, set()
unsafe = rebuilt = 0
seen = set()
for i, (s, z) in enumerate(bd.entries):
    if s <= 0 or not 0 < z < C.SIZE_LIMIT or i in C.CODE_ENTRIES or (s, z) in seen:
        continue
    seen.add((s, z))
    f, o = fd.read_file(i), od.read_file(i)
    if o != bd.read_file(i):                     # rebuilt: its sectors may change
        extents.update(range(s, s + (z + 2047) // 2048))
        unsafe += unsafe_streams(o)
        rebuilt += 1
    checked += 1
    if f != o and decoded(f) != decoded(o):
        mism.append(i)
print(f"files compared: {checked}; decoded differences OUT vs FINAL: {len(mism)} {mism[:10]}")
print(f"rebuilt files: {rebuilt}; compressed streams the game's decoder would not stop on: {unsafe}")
SEC = 2352
fb, fo = open(base_p, "rb"), open(out_p, "rb")
n = os.path.getsize(base_p) // SEC
changed = stray = 0
s25 = False
for blk in range(0, n, 4096):
    cnt = min(4096, n - blk)
    A, B = fb.read(SEC * cnt), fo.read(SEC * cnt)
    if A == B:
        continue
    for k in range(cnt):
        if A[k * SEC:(k + 1) * SEC] != B[k * SEC:(k + 1) * SEC]:
            sn = blk + k
            changed += 1
            if sn == 25:
                s25 = True
            elif not (24 <= sn <= 38 or sn in extents):
                stray += 1
print(f"sectors changed vs BASE: {changed}; outside rebuilt files/table: {stray}; sector 25 touched: {s25}; "
      f"image size same as BASE: {os.path.getsize(base_p) == os.path.getsize(out_p)}")
