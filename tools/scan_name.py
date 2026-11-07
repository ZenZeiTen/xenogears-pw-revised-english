"""Find field-text blocks on a disc that contain given words (encoded with the field table).

  python tools/scan_name.py DISC.bin [DISC2.bin ...] -w Alice -w Arle

Prints disc, file index, block index and word. Aliased files (same text section) are listed once.
Words containing DTE pairs (ar th ra ro ti la re er le) may also be stored DTE-compressed and
would be missed by this byte search; "Alice" has none, "Arle" contains "le".
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fieldtext as F
import script_patch as SP
import xgdisc

MAX_FILE = 2_000_000  # real field files are < 300 KB


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("discs", nargs="+")
    ap.add_argument("-w", "--word", action="append", required=True)
    ap.add_argument("--from", dest="start", type=int, default=0, help="resume at this file index")
    a = ap.parse_args()
    table = SP.load_table()
    pats = {w: SP.encode(w, table) for w in a.word}
    for path in a.discs:
        disc = xgdisc.Disc(path)
        seen = set()
        for i in range(a.start, len(disc.entries)):
            if i % 250 == 0:
                print(f"  .. {Path(path).name} file {i}/{len(disc.entries)}", file=sys.stderr, flush=True)
            if disc.entries[i][1] > MAX_FILE:  # bogus table entries span ~the whole disc
                continue
            try:
                sec = F.text_section(disc.read_file(i))
                blocks = F.split_section(sec)
            except Exception:
                continue
            if sec in seen:
                continue
            seen.add(sec)
            for b, (_, blk) in enumerate(blocks):
                for w, p in pats.items():
                    if p in blk:
                        print(Path(path).name, i, b, w, flush=True)


if __name__ == "__main__":
    main()
