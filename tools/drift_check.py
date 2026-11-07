"""List field-text blocks where the disc bytes differ from the Perfect Works .txt.

  python tools/drift_check.py DISC.bin PW_FIELD_DIR [--json OUT.json]

For each NNNN.txt, every <TextBlock k> is encoded with the field table and compared with block k
of disc file NNNN. Prints file, block, and both texts (disc decoded). Blocks the table cannot
encode are reported as 'unencodable'. Block-count mismatches are reported per file.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fieldtext as F
import script_patch as SP
import xgdisc


def decoder(table):
    rev = {v: k for k, v in table.items() if isinstance(v, bytes) and k != "_extra"}
    maxl = max(len(k) for k in rev)

    def dec(b):
        out, i = [], 0
        while i < len(b):
            if b[i] == 0x0F and i + 2 < len(b):
                out.append(f"<Delay {b[i+2]}>" if b[i + 1] == 0 else f"<Opcode {b[i+1]} {b[i+2]}>")
                i += 3
                continue
            for L in range(maxl, 0, -1):
                if b[i:i + L] in rev:
                    out.append(rev[b[i:i + L]]); i += L; break
            else:
                out.append(f"<UNKNOWN CHUNK {b[i]}>"); i += 1
        return "".join(out)
    return dec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("disc"); ap.add_argument("pwdir"); ap.add_argument("--json")
    a = ap.parse_args()
    table = SP.load_table()
    dec = decoder(table)
    disc = xgdisc.Disc(a.disc)
    out = []
    for txt in sorted(Path(a.pwdir).glob("*.txt")):
        if not txt.stem.isdigit():
            print(f"{txt.stem}: skipped (non-numeric name)")
            continue
        idx = int(txt.stem)
        src = open(txt, encoding="latin-1", newline="").read()
        pw = {int(m.group(1)): m.group(4) for m in F.BLOCK.finditer(src)}
        try:
            raw = disc.read_file(idx)
            blocks = F.split_section(F.text_section(raw)[:F.read_field(raw)[0][7]])
        except Exception as ex:
            print(f"{txt.stem}: cannot read disc file ({ex})")
            continue
        if len(pw) != len(blocks):
            print(f"{txt.stem}: block count pw={len(pw)} disc={len(blocks)}")
        for k, body in sorted(pw.items()):
            if k - 1 >= len(blocks):
                continue
            disc_b = blocks[k - 1][1]
            try:
                pw_b = F.encode_block(body.replace("\r\n", "\n"), table)
            except KeyError as ex:
                out.append({"file": txt.stem, "block": k, "kind": "unencodable", "token": str(ex)})
                continue
            if pw_b != disc_b:
                out.append({"file": txt.stem, "block": k, "kind": "differs",
                            "pw": body.replace("\r\n", "\n"), "disc": dec(disc_b)})
    for d in out:
        print(f"== {d['file']}#{d['block']} {d['kind']}")
        if d["kind"] == "differs":
            print("-- PW:\n" + d["pw"] + "\n-- DISC:\n" + d["disc"])
        else:
            print("   token " + d["token"])
    print(f"{sum(d['kind'] == 'differs' for d in out)} differing, "
          f"{sum(d['kind'] == 'unencodable' for d in out)} unencodable", file=sys.stderr)
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
