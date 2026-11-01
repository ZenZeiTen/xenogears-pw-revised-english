"""In-place menu string fixes (items, abilities, parts) on a raw disc image.

Menu strings are addressed by u16 offset tables, so strings never move: each fix
must be the same length or shorter, and the freed bytes become zeros after the
terminator. Targets are found by content (identical files on CD1/CD2 have
different indices), every copy is patched, containers are re-packed exactly
like the originals (LZSS archive / whole-file LZSS / raw).

  python menu_patch.py IN.bin OUT.bin
"""
import json
import shutil
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xgdisc

TABLE = {k: bytes.fromhex(v) for k, v in
         json.load(open(Path(__file__).parent / "fieldtext_table.json", encoding="utf-8")).items()
         if len(k) == 1}

FIXES = [  # (old, new, why)
    ("Nortune Gear-dock key", "Noatun Gear-dock key", "name table: Nortune -> Noatun"),
    ("Nortune sewer key", "Noatun sewer key", "name table: Nortune -> Noatun"),
    ("Jessie's", "Jesse's", "name table: Jessie -> Jesse"),
    ("Defence up", "Defense up", "US spelling"),
    ("on towards self", "on toward self", "US spelling"),
    ("Nulifies Eth weapons", "Nulls Eth weapons", "typo; 'Nulls' matches the sibling descriptions"),
    ("Chu-chu statue", "Chu-Chu statue", "name is Chu-Chu"),
    ("gears", "Gears", "Gear is capitalized throughout"),
    ("gear's", "Gear's", "Gear is capitalized throughout"),
    ("El Stier use.", "El-Stier use.", "hyphenate like El-Stier / El-Fenrir"),
    ("Toy gun", "Toy Gun", "title case for items"),
    ("Fei  Jr.Doll", "Fei Jr.Doll", "double space"),
    ("Godson  Ammo", "Godson Ammo", "double space"),
    ("Lowers Wind res", "Lower Wind res", "match 'Raise ... res' / 'Lower Water res'"),
    ("Lowers Earth res", "Lower Earth res", "match 'Raise ... res' / 'Lower Water res'"),
    ("Lowers Fire res", "Lower Fire res", "match 'Raise ... res' / 'Lower Water res'"),
    ("in Desert", "in desert", "match 'in water' / 'in snow'"),
    ("in Water", "in water", "match 'in water' / 'in snow'"),
]


def enc(s):
    return b"".join(TABLE[c] for c in s)


def is_menu_table(b):
    """u32 count c, then 2c+2 u16 entries (offsets + per-string values), then strings."""
    if len(b) < 8:
        return False
    c = struct.unpack_from("<I", b)[0]
    first = struct.unpack_from("<H", b, 4)[0]
    return first == 4 + 2 * (2 * c + 2) and first < len(b)


def fix_buffer(buf, log, where):
    if not is_menu_table(buf):
        return buf, 0          # never touch anything that isn't a validated string table
    buf = bytearray(buf)
    n_changes = 0
    for old, new, _ in FIXES:
        o, nw = enc(old), enc(new)
        assert len(nw) <= len(o), old
        is_letter = lambda x: 0x20 <= x <= 0x39 or 0x3D <= x <= 0x56
        i = buf.find(o)
        while i >= 0:
            if (i > 0 and is_letter(buf[i - 1])) or (i + len(o) < len(buf) and is_letter(buf[i + len(o)])):
                i = buf.find(o, i + 1)               # inside a longer word (e.g. "Xenogears")
                continue
            end = buf.index(0, i)                    # this string's terminator
            rec = bytes(buf[i:end])
            rec2 = nw + rec[len(o):]
            buf[i:end + 1] = rec2 + b"\0" * (len(rec) - len(rec2) + 1)
            n_changes += 1
            log.append(f"{where}: {old!r} -> {new!r}")
            i = buf.find(o, i + len(nw))
    return bytes(buf), n_changes


def containers(raw):
    """Return (kind, parts) where parts is a list of (is_lzss, bytes)."""
    n = struct.unpack_from("<I", raw)[0]
    if 0 < n < 512 and 4 + 4 * (n + 1) <= len(raw):
        offs = list(struct.unpack_from(f"<{n + 1}I", raw, 4))
        if offs[0] == 4 + 4 * (n + 1) and offs == sorted(offs) and offs[-1] == len(raw):
            parts = []
            for k in range(n):
                sec = raw[offs[k]:offs[k + 1]]
                m = struct.unpack_from("<I", sec)[0] if len(sec) >= 4 else 0
                if len(sec) >= 8 and len(sec) < m < 8 * len(sec):
                    out, used = xgdisc.lzss_decompress(sec)
                    if used >= len(sec) - 8 and xgdisc.lzss_compress(out)[:4] == sec[:4]:
                        parts.append((True, out, sec))
                        continue
                parts.append((False, sec, sec))
            return "archive", parts
    if len(raw) < n < 8 * len(raw):
        out, used = xgdisc.lzss_decompress(raw)
        if used >= len(raw) - 4:
            return "lzss", [(True, out, raw)]
    return "raw", [(False, raw, raw)]


def repack(kind, parts):
    blobs = []
    for is_lz, data, orig in parts:
        if data is None:
            blobs.append(orig)
        elif is_lz:
            c = xgdisc.lzss_compress(data)
            blobs.append(c + b"\0" * (-len(c) % 4) if kind == "archive" else c)
        else:
            blobs.append(data)
    if kind != "archive":
        return blobs[0]
    n = len(blobs)
    offs, pos = [], 4 + 4 * (n + 1)
    for b in blobs:
        offs.append(pos)
        pos += len(b)
    return struct.pack("<I", n) + struct.pack(f"<{n + 1}I", *offs, pos) + b"".join(blobs)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    if Path(src).resolve() == Path(dst).resolve():
        sys.exit("refusing to patch in place")
    disc = xgdisc.Disc(src)
    probe = [enc(o) for o, _, _ in FIXES]
    # candidate files: anything up to 400 KB that contains an encoded target after unpacking
    todo, log = {}, []
    for idx, (start, size) in enumerate(disc.entries):
        if start <= 0 or not 0 < size < 400_000:
            continue
        try:
            raw = disc.read_file(idx)
            kind, parts = containers(raw)
        except Exception:
            continue
        if not any(p in data for _, data, _ in parts for p in probe):
            continue
        new_parts, total = [], 0
        for k, (is_lz, data, orig) in enumerate(parts):
            fixed, c = fix_buffer(data, log, f"file {idx} {kind} part {k}")
            total += c
            new_parts.append((is_lz, fixed if c else None, orig))
        if total:
            todo[idx] = repack(kind, new_parts)
    disc.f.close()
    shutil.copyfile(src, dst) if src != dst else None
    for idx, data in todo.items():
        start, moved = xgdisc.write_file(dst, idx, data)
        log.append(f"file {idx}: written ({len(data)} bytes){' relocated' if moved else ''}")
    chk = xgdisc.Disc(dst)
    for idx, data in todo.items():
        assert chk.read_file(idx) == data
    print("\n".join(log))
    print(f"patched {len(todo)} file(s)")


if __name__ == "__main__":
    main()
