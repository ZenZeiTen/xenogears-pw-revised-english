"""Apply text edits to field files on a raw disc image and to the PW .txt sources.

Edits are JSON: [{"file": "0608", "block": 12, "old": "...", "new": "...", ...}]
(`old`/`new` use the .txt syntax: \\n line breaks and <Tags>).

Each edit is a byte-level replace inside the ORIGINAL block bytes on the disc, so
opcodes the .txt dump never exported survive untouched. Box size only grows.
A block can also be listed with "old" == "new" == "" to just refit its box.

  python script_patch.py IN.bin OUT.bin edits.json [--txt-root PerfectWorks_Script]
"""
import argparse
import json
import re
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fieldtext as F
import xgdisc

TABLE_PATH = Path(__file__).parent / "fieldtext_table.json"
NAME_LEN = {0x07: 7, 0x0B: 7, 0x0C: 9, 0x11: 5, 0x13: 8, 0x1A: 9, 0x80: 6, 0x81: 6, 0x82: 6}


def load_table():
    t = {k: bytes.fromhex(v) for k, v in json.load(open(TABLE_PATH, encoding="utf-8")).items()}
    t["_extra"] = {"1": b"\xfe", "2": b"\xff"}
    return t


def encode(snippet, table):
    return F.encode_block(snippet.replace("\r\n", "\n"), table)


def visible_pages(b):
    """Block bytes -> list of pages, each a list of line lengths (visible cells)."""
    pages, lines, cur, i = [], [], 0, 0
    while i < len(b):
        c = b[i]
        if c == 0x00:
            break
        if c == 0x01:
            lines.append(cur); cur = 0
        elif c == 0x02:
            lines.append(cur); pages.append(lines); lines, cur = [], 0
        elif c == 0x0F:
            if i + 2 < len(b) and b[i + 1] == 0x05:
                cur += NAME_LEN.get(b[i + 2], 6)
            i += 2
        elif c in (0xFE, 0xFF):
            i += 1
        else:
            cur += 1
        i += 1
    lines.append(cur)
    pages.append(lines)
    return pages


def fit(dims, b):
    w, h = dims
    pages = visible_pages(b)
    need_w = 2 * max(max(p) for p in pages)
    need_h = max(len(p) for p in pages)
    return (max(w, need_w), max(h, need_h))


def patch_field(raw, edits, table, log):
    sizes, offs = F.read_field(raw)
    sec7 = xgdisc.lzss_decompress(raw[offs[7]:offs[8]])[0][:sizes[7]]
    blocks = F.split_section(sec7)
    for e in edits:
        k = e["block"] - 1          # block numbers are positional; check_numbering() guards this
        dims, b = blocks[k]
        if e["old"] or e["new"]:
            old, new = encode(e["old"], table), encode(e["new"], table)
            if b.count(old) != 1:
                raise ValueError(f"{e['file']}#{e['block']}: old text found {b.count(old)}x in shipped bytes")
            b = b.replace(old, new)
        nd = fit(dims, b)
        if e.get("width_only"):
            nd = (nd[0], dims[1])
        if nd != dims:
            log.append(f"{e['file']}#{e['block']}: box {dims} -> {nd}")
        if max(nd) > 255:
            raise ValueError("box too large")
        blocks[k] = (nd, b)
    new7 = F.build_section(blocks)
    true_len = len(new7)
    new7 += b"\0" * (-len(new7) % 4)
    comp = xgdisc.lzss_compress(new7)
    comp += b"\0" * (-len(comp) % 4)
    delta = len(comp) - (offs[8] - offs[7])
    out = bytearray(raw[:offs[7]]) + comp + raw[offs[8]:]
    sizes[7] = true_len
    offs = offs[:8] + [o + delta if o else o for o in offs[8:]]
    struct.pack_into("<9I", out, F.SIZES_AT, *sizes)
    struct.pack_into("<9I", out, F.OFFS_AT, *offs)
    # self-check: the rebuilt file decodes back to what we built
    chk = F.split_section(xgdisc.lzss_decompress(bytes(out[offs[7]:offs[8]]))[0][:sizes[7]])
    assert chk == blocks, "rebuilt text section does not round-trip"
    return bytes(out)


def patch_txt(path, edits, dims_by_block):
    txt = open(path, encoding="latin-1", newline="").read()
    nl = "\r\n" if "\r\n" in txt else "\n"
    for e in edits:
        pat = re.compile(rf"<TextBlock {e['block']} w:\w+ h:\w+>\r?\n(.*?)<End of Block>", re.S)
        m = pat.search(txt)
        body = m.group(1)
        if e["old"] or e["new"]:
            old, new = e["old"].replace("\n", nl), e["new"].replace("\n", nl)
            if body.count(old) != 1:
                raise ValueError(f"{path}#{e['block']}: old text found {body.count(old)}x in .txt")
            body = body.replace(old, new)
        w, h = dims_by_block[e["block"]]
        txt = txt[:m.start()] + f"<TextBlock {e['block']} w:{w} h:{h}>{nl}{body}<End of Block>" + txt[m.end():]
    open(path, "w", encoding="latin-1", newline="").write(txt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst"); ap.add_argument("edits")
    ap.add_argument("--txt-root")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if Path(a.src).resolve() == Path(a.dst).resolve():
        sys.exit("refusing to patch in place")
    if Path(a.dst).exists() and not a.force:
        sys.exit(f"{a.dst} exists (use --force)")
    edits = json.load(open(a.edits, encoding="utf-8"))
    table = load_table()
    by_file = {}
    for e in edits:
        by_file.setdefault(e["file"], []).append(e)
    if a.txt_root:
        for fid in by_file:
            nums = [int(x) for x in re.findall(r"<TextBlock (\d+) ",
                    open(Path(a.txt_root) / "field" / f"{fid}.txt", encoding="latin-1").read())]
            if nums != list(range(1, len(nums) + 1)):
                sys.exit(f"{fid}.txt: block numbers are not 1..n in order; fix the labels first")
    src = xgdisc.Disc(a.src)
    built, log = {}, []
    for fid, es in sorted(by_file.items()):
        idx = int(fid)
        built[idx] = (patch_field(src.read_file(idx), es, table, log), es)
    src.f.close()
    shutil.copyfile(a.src, a.dst)
    for idx, (data, es) in built.items():
        start, moved = xgdisc.write_file(a.dst, idx, data)
        log.append(f"file {idx:04d}: {len(es)} edit(s), {len(data)} bytes{' (relocated)' if moved else ''}")
    chk = xgdisc.Disc(a.dst)
    for idx, (data, _) in built.items():
        assert chk.read_file(idx) == data, f"verify failed for {idx}"
    if a.txt_root:
        for fid, es in by_file.items():
            dims = {e["block"]: F.split_section(F.text_section(built[int(fid)][0]))[e["block"] - 1][0] for e in es}
            patch_txt(Path(a.txt_root) / "field" / f"{fid}.txt", es, dims)
    print("\n".join(log))
    print(f"patched {len(built)} file(s), {len(edits)} edit(s) -> {a.dst}")


if __name__ == "__main__":
    main()
