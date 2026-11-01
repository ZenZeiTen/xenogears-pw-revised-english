"""Apply script edits (written against disc-1 file ids) to disc 2.

Disc 2 numbers its files differently, so each edited disc-1 field file is matched by
content. A disc-2 file is a target when it has the same number of text blocks and at least
NEAR of them are byte-identical to the disc-1 file before editing; only edits whose own
block is byte-identical are applied there (the rest are reported). Edits go into the disc-2
file's own bytes (its other sections may differ), so nothing from disc 1 is copied over.

  python apply_cd2.py CD1_BEFORE.bin CD2_IN.bin CD2_OUT.bin edits.json
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fieldtext as F
import script_patch as SP
import xgdisc


NEAR = 0.9


def text_blocks(raw):
    try:
        return [b for _, b in F.split_section(F.text_section(raw)[:F.read_field(raw)[0][7]])]
    except Exception:
        return None


def main():
    cd1, src, dst, edits_path = sys.argv[1:5]
    if Path(src).resolve() == Path(dst).resolve():
        sys.exit("refusing to patch in place")
    edits = json.load(open(edits_path, encoding="utf-8"))
    by_file = {}
    for e in edits:
        by_file.setdefault(e["file"], []).append(e)
    d1 = xgdisc.Disc(cd1)
    want = {}                                   # block count -> [(disc-1 id, blocks)]
    for fid in by_file:
        bl = text_blocks(d1.read_file(int(fid)))
        want.setdefault(len(bl), []).append((fid, bl))
    d1.f.close()
    d2 = xgdisc.Disc(src)
    table, log, built, seen = SP.load_table(), [], {}, set()
    for idx, (start, size) in enumerate(d2.entries):
        if start <= 0 or not 0 < size < 1_000_000:
            continue
        try:
            raw = d2.read_file(idx)
        except Exception:
            continue
        bl = text_blocks(raw)
        if not bl or len(bl) not in want or (start, size) in seen:  # aliased table entries
            continue
        for fid, ref in want[len(bl)]:
            same = [x == y for x, y in zip(ref, bl)]
            if sum(same) >= NEAR * len(bl):
                break
        else:
            continue
        seen.add((start, size))
        es = [e for e in by_file[fid] if same[e["block"] - 1]]
        for e in by_file[fid]:
            if not same[e["block"] - 1]:
                print(f"skip cd1 {fid}#{e['block']} on cd2 {idx}: block differs on disc 2")
        if es:
            built[idx] = (SP.patch_field(raw, es, table, log), fid)
    d2.f.close()
    shutil.copyfile(src, dst)
    for idx, (data, fid) in sorted(built.items()):
        _, moved = xgdisc.write_file(dst, idx, data)
        print(f"cd1 {fid} -> cd2 {idx:04d}{' (relocated)' if moved else ''}")
    chk = xgdisc.Disc(dst)
    for idx, (data, _) in built.items():
        assert chk.read_file(idx) == data, idx
    mapped = {fid for _, fid in built.values()}
    print(f"patched {len(built)} disc-2 file(s); {len(by_file) - len(mapped)} edited disc-1 file(s) not on disc 2")


if __name__ == "__main__":
    main()
