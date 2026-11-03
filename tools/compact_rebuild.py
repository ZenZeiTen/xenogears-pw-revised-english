"""Rebuild a patched disc so that no file grows and nothing is relocated.

The game loads some files into fixed-size buffers, and the first builds re-encoded
changed sections with a greedy LZSS encoder that came out a little larger than Square's
own encoder (e.g. file 0029: 14,144 -> 14,178 bytes). Those discs did not boot.

This tool starts again from the BASE image and, for every file whose content differs in
FINAL, writes the final content back at the base file's own location:
  - field files (9 LZSS sections) and archives: unchanged sections keep the base bytes
    exactly; changed sections take the smaller of FINAL's bytes and an optimal re-encode;
  - whole-file LZSS: the smaller of the two; raw files: FINAL's bytes.
Every rebuilt file must be no larger than the base file, so it always fits in place.
All table entries that alias the same base data get the new size.

  python compact_rebuild.py BASE.bin FINAL.bin OUT.bin [menu file indices, comma-separated]
"""
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fieldtext as F
import menu_patch as MP
import game_lzss as G
import xgdisc as X


def safe_choice(*cands):
    """Smallest candidate the game's decoder reads back correctly (see game_lzss.py)."""
    ok = [c for c in cands if c is not None and G.safe(c)]
    if not ok:
        raise ValueError("no candidate is safe for the game's decoder")
    return min(ok, key=len)


def opt_or_none(data):
    try:
        return X.lzss_compress_optimal(data)
    except ValueError:
        return None

SIZE_LIMIT = 2_000_000
# Perfect Works keeps code in sector 25, inside the file table: the "entries" stored
# there are not files, and their bytes must never be written.
CODE_ENTRIES = range(2048 // 7 - 1, 4096 // 7 + 1)
MENU_FILES = {29, 2594, 2609, 3091, 3096, 3097}      # disc-1 indices patched by menu_patch.py


def is_field(raw):
    try:
        field_spans(raw)
        return True
    except Exception:
        return False


def pad4(b):
    return b + b"\0" * (-len(b) % 4)


def field_spans(raw):
    sizes, offs = F.read_field(raw)
    if not (0 < offs[0] <= len(raw)) or any(o and not offs[0] <= o <= len(raw) for o in offs):
        raise ValueError("not a field file")
    spans = []
    for k in range(9):
        end = next((o for o in offs[k + 1:] if o), len(raw)) if offs[k] else 0
        spans.append(raw[offs[k]:end] if offs[k] else None)
    return sizes, offs, spans


def section_content(size, span):
    return X.lzss_decompress(span)[0] if size and span else b""


def rebuild_field(base, final, squeeze=False):
    """squeeze=True also re-encodes unchanged sections when that is smaller; used only
    when a file would otherwise outgrow its base size."""
    sb, ob, spb = field_spans(base)
    sf, of_, spf = field_spans(final)
    out = bytearray(final[:of_[0]])
    new_offs = []
    for k in range(9):
        if not of_[k]:
            new_offs.append(0)
            continue
        new_offs.append(len(out))
        if spb[k] is not None and sb[k] == sf[k] and section_content(sb[k], spb[k]) == section_content(sf[k], spf[k]):
            seg = spb[k]                                   # unchanged: Square's bytes
            if squeeze and sb[k]:
                o = opt_or_none(section_content(sb[k], spb[k]))
                if o is not None:
                    seg = min(seg, pad4(o), key=len)
        elif not sf[k]:
            seg = spf[k]
        else:
            o = opt_or_none(section_content(sf[k], spf[k]))
            seg = safe_choice(spf[k], pad4(o) if o is not None else None)
        out += seg
    struct.pack_into("<9I", out, F.SIZES_AT, *sf)
    struct.pack_into("<9I", out, F.OFFS_AT, *new_offs)
    return bytes(out)


def rebuild_container(base, final):
    kb, pb = MP.containers(base)
    kf, pf = MP.containers(final)
    if kf != kb or len(pf) != len(pb):
        raise ValueError(f"container mismatch {kb}/{kf}")
    if kf == "raw":
        return final
    parts = []
    for (lzb, db, ob), (lzf, df, of_) in zip(pb, pf):
        if db == df:
            parts.append((False, ob, ob))                  # unchanged: keep exact bytes
        elif lzf:
            opt = opt_or_none(df)
            if opt is not None and kf == "archive":
                opt = pad4(opt)
            parts.append((False, safe_choice(of_, opt), of_))
        else:
            parts.append((False, df, of_))
    return MP.repack(kf, parts)


def rebuild(base, final):
    try:
        new = rebuild_field(base, final)
        if len(new) > len(base):
            new = rebuild_field(base, final, squeeze=True)
        return new, "field"
    except Exception:
        return rebuild_container(base, final), "container"


def write_in_place(path, start, data, base_size):
    """Overwrite a file's own sectors. Safe because data is never longer than the base
    file that occupied them; the rest of its last sector is zero-filled."""
    import cdsector
    assert len(data) <= base_size
    with open(path, "r+b") as f:
        for k in range((len(data) + X.DATA_LEN - 1) // X.DATA_LEN):
            f.seek((start + k) * X.SECTOR)
            sec = bytearray(f.read(X.SECTOR))
            sec[X.DATA_OFF:X.DATA_OFF + X.DATA_LEN] = data[k * X.DATA_LEN:(k + 1) * X.DATA_LEN].ljust(X.DATA_LEN, b"\0")
            cdsector.fix_mode2_form1(sec)
            f.seek((start + k) * X.SECTOR)
            f.write(sec)


def set_entry_size(path, idx, start, size):
    """Write one 7-byte table entry (start sector, size) and fix the touched sectors."""
    import cdsector
    with open(path, "r+b") as f:
        entry = bytes([start & 0xFF, (start >> 8) & 0xFF, (start >> 16) & 0xFF]) + struct.pack("<i", size)
        pos = idx * 7
        for i, b in enumerate(entry):
            s, o = 24 + (pos + i) // X.DATA_LEN, (pos + i) % X.DATA_LEN
            f.seek(s * X.SECTOR)
            sec = bytearray(f.read(X.SECTOR))
            sec[X.DATA_OFF + o] = b
            cdsector.fix_mode2_form1(sec)
            f.seek(s * X.SECTOR)
            f.write(sec)


def main():
    base_p, final_p, out_p = sys.argv[1:4]
    if Path(out_p).resolve() in (Path(base_p).resolve(), Path(final_p).resolve()):
        sys.exit("refusing to overwrite an input")
    bd, fd = X.Disc(base_p), X.Disc(final_p)
    groups = {}
    for i, (s, z) in enumerate(bd.entries):
        if s > 0 and 0 < z < SIZE_LIMIT and i not in CODE_ENTRIES:
            groups.setdefault((s, z), []).append(i)
    menu_files = {int(x) for x in sys.argv[4].split(",")} if len(sys.argv) > 4 else MENU_FILES
    plan, problems = [], []
    for (s, z), idxs in groups.items():
        base = bd.read_file(idxs[0])
        finals = []
        for i in idxs:
            fs, fz = fd.entries[i]
            if fs > 0 and 0 < fz < SIZE_LIMIT:
                f = fd.read_file(i)
                if f != base:
                    finals.append(f)
        if not finals:
            continue
        final = finals[0]
        entry_changed = any(fd.entries[i] != bd.entries[i] for i in idxs)
        if not (entry_changed or is_field(base) or set(idxs) & menu_files):
            continue      # a stray entry whose extent overlaps a changed file; not a file
        if any(f != final for f in finals[1:]):
            problems.append(f"{idxs}: aliases disagree")
            continue
        # self-test: rebuilding an unchanged file must reproduce it exactly
        if rebuild(base, base)[0] != base:
            problems.append(f"{idxs}: base does not round-trip")
            continue
        new, kind = rebuild(base, final)
        if len(new) > len(base):
            problems.append(f"{idxs}: still grows {len(base)} -> {len(new)}")
            continue
        plan.append((idxs, s, base, final, new, kind))
    for p in problems:
        print("PROBLEM", p)
    if problems:
        sys.exit("not writing: fix the problems above")
    shutil.copyfile(base_p, out_p)
    for idxs, s, base, final, new, kind in plan:
        write_in_place(out_p, s, new, len(base))
        for i in idxs:
            set_entry_size(out_p, i, s, len(new))
    od = X.Disc(out_p)
    for idxs, s, base, final, new, kind in plan:
        got = od.read_file(idxs[0])
        assert got == new, idxs
        # same decoded content as FINAL
        if kind == "field":
            sf, _, spf = field_spans(final)
            sg, _, spg = field_spans(got)
            assert all(section_content(sf[k], spf[k]) == section_content(sg[k], spg[k]) for k in range(9)), idxs
        else:
            assert [d for _, d, _ in MP.containers(got)[1]] == [d for _, d, _ in MP.containers(final)[1]], idxs
    grew = sum(1 for p in plan if len(p[4]) > len(p[2]))
    print(f"rebuilt {len(plan)} file(s) in place ({sum(len(p[0]) for p in plan)} table entries); "
          f"grew: {grew}; size change {sum(len(p[4]) - len(p[2]) for p in plan):+d} bytes; image size unchanged: "
          f"{Path(out_p).stat().st_size == Path(base_p).stat().st_size}")


if __name__ == "__main__":
    main()
