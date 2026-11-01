"""Find which Japanese field file corresponds to a US/PW field file whose block count differs.

Each block is reduced to a fingerprint that survives translation: its script opcodes (0F a b
other than delays and name pointers) plus a coarse length bucket (English is ~2.5x the
Japanese character count). Candidates on either JP disc are ranked by a sequence alignment
of those fingerprints.

  python jp_match.py JP1.bin JP2.bin US.bin fid [fid ...]
"""
import difflib
import math
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fieldtext as F
import xgdisc

CACHE = Path(__file__).parent / "__pycache__" / "jp_index.pkl"


def blocks(d, i):
    try:
        r = d.read_file(i)
        return [b for _, b in F.split_section(F.text_section(r)[:F.read_field(r)[0][7]])]
    except Exception:
        return None


def fingerprint(b, jp):
    ops, chars, i = [], 0, 0
    while i < len(b):
        c = b[i]
        if c == 0:
            break
        if c == 0x0F:
            if b[i + 1] not in (0, 5):
                ops.append((b[i + 1], b[i + 2]))
            i += 3
            continue
        if c >= 0xF8 if jp else c in (0xFE, 0xFF):
            i += 2
        else:
            i += 1
        chars += 1
    if not jp:
        chars /= 2.5
    return (tuple(ops), round(math.log2(chars + 1)))


def index(paths):
    if CACHE.exists():
        return pickle.load(open(CACHE, "rb"))
    idx = {}
    for tag, p in paths.items():
        d = xgdisc.Disc(p)
        for i, (start, size) in enumerate(d.entries):
            if start > 0 and 0 < size < 1_000_000:
                bl = blocks(d, i)
                if bl:
                    idx[(tag, i)] = [fingerprint(b, True) for b in bl]
    pickle.dump(idx, open(CACHE, "wb"))
    return idx


def main():
    jp1, jp2, us = sys.argv[1:4]
    idx = index({"jp1": jp1, "jp2": jp2})
    d = xgdisc.Disc(us)
    for fid in sys.argv[4:]:
        a = [fingerprint(b, False) for b in blocks(d, int(fid))]
        scored = []
        for key, c in idx.items():
            if abs(len(c) - len(a)) > max(3, len(a) // 5):
                continue
            r = difflib.SequenceMatcher(None, a, c, autojunk=False).ratio()
            scored.append((r, key, len(c)))
        scored.sort(reverse=True)
        print(fid, len(a), [(f"{k[0]}:{k[1]}", n, round(r, 2)) for r, k, n in scored[:4]])


if __name__ == "__main__":
    main()
