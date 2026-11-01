"""Write a BPS patch (beat format) that turns one disc image into another, plus a verifier.

The encoder works sector by sector. Unchanged sectors become SourceRead. A changed sector
is matched first against the same position in the source (SourceRead), then against the
original extent of the file that owns it in the target's file table (SourceCopy), and
only what remains is stored literally (TargetRead): new text, sector headers, EDC/ECC.
Relocated files therefore cost little: their unchanged sections are copied from where
they used to be.

  python make_bps.py SOURCE.bin TARGET.bin OUT.bps ["metadata text"]
  python make_bps.py --apply SOURCE.bin PATCH.bps OUT.bin
"""
import mmap
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xgdisc

SEC = 2352
MIN_SAME, MIN_COPY, KEY = 8, 12, 12
MAX_WINDOW = 512 * 1024           # index at most this much of a file's original extent


def vint(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def owners(disc, nsec):
    """target sector -> file index that occupies it. Some table entries are bogus and span
    much of the disc, so when entries overlap the smallest one wins."""
    own = {}
    ents = [(size, i, start) for i, (start, size) in enumerate(disc.entries) if start > 0 and size > 0]
    for size, i, start in sorted(ents, reverse=True):
        for s in range(start, start + (size + 2047) // 2048):
            own[s] = i
    return own


def mapped(path):
    """Read-only memory map, so two 700 MB images do not have to fit in RAM."""
    f = open(path, "rb")
    return mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)


def encode(src_path, tgt_path, out_path, meta=""):
    src = mapped(src_path)
    tgt = mapped(tgt_path)
    sd, td = xgdisc.Disc(src_path), xgdisc.Disc(tgt_path)
    own = owners(td, len(tgt) // SEC)
    out = bytearray(b"BPS1" + vint(len(src)) + vint(len(tgt)) + vint(len(meta.encode())) + meta.encode())
    pending_lit = bytearray()
    src_rel = 0                   # BPS source-relative cursor for SourceCopy
    stats = {"sourceread": 0, "sourcecopy": 0, "literal": 0}
    windows = {}                  # file index -> (base offset, index dict)

    def flush_lit():
        if pending_lit:
            out.extend(vint(((len(pending_lit) - 1) << 2) | 1))
            out.extend(pending_lit)
            stats["literal"] += len(pending_lit)
            pending_lit.clear()

    def source_read(n):
        flush_lit()
        out.extend(vint(((n - 1) << 2) | 0))
        stats["sourceread"] += n

    def source_copy(at, n):
        nonlocal src_rel
        flush_lit()
        d = at - src_rel
        out.extend(vint(((n - 1) << 2) | 2))
        out.extend(vint((abs(d) << 1) | (d < 0)))
        src_rel = at + n
        stats["sourcecopy"] += n

    def window(fi):
        if fi not in windows:
            start, size = sd.entries[fi] if fi < len(sd.entries) else (0, 0)
            if start <= 0 or size <= 0 or size > MAX_WINDOW:
                windows[fi] = None    # big files: rely on same-position matching
            else:
                base = start * SEC
                data = src[base:base + ((size + 2047) // 2048) * SEC]
                idx = {}
                for p in range(len(data) - KEY + 1):
                    idx.setdefault(data[p:p + KEY], p)
                windows[fi] = (base, data, idx)
            if len(windows) > 8:
                windows.pop(next(iter(windows)))
        return windows[fi]

    nsec = len(tgt) // SEC
    s, run = 0, 0
    while s < nsec:
        a = s * SEC
        if a + SEC <= len(src) and src[a:a + SEC] == tgt[a:a + SEC]:
            run += SEC
            s += 1
            continue
        if run:
            source_read(run)
            run = 0
        T = tgt[a:a + SEC]
        win = window(own[s]) if s in own else None
        i = 0
        while i < SEC:
            # same position in the source
            j = 0
            while i + j < SEC and a + i + j < len(src) and src[a + i + j] == T[i + j]:
                j += 1
            if j >= MIN_SAME:
                source_read(j)
                i += j
                continue
            # the owning file's original extent
            if win and i + KEY <= SEC:
                p = win[2].get(T[i:i + KEY])
                if p is not None:
                    data = win[1]
                    j = KEY
                    while i + j < SEC and p + j < len(data) and data[p + j] == T[i + j]:
                        j += 1
                    if j >= MIN_COPY:
                        source_copy(win[0] + p, j)
                        i += j
                        continue
            pending_lit.append(T[i])
            i += 1
        s += 1
    if run:
        source_read(run)
    flush_lit()
    out.extend(zlib.crc32(src).to_bytes(4, "little"))
    out.extend(zlib.crc32(tgt).to_bytes(4, "little"))
    out.extend(zlib.crc32(bytes(out)).to_bytes(4, "little"))
    open(out_path, "wb").write(out)
    return stats, len(out)


def apply(src_path, patch_path, out_path):
    src = mapped(src_path)
    p = open(patch_path, "rb").read()
    assert p[:4] == b"BPS1", "not a BPS patch"
    if zlib.crc32(p[:-4]) != int.from_bytes(p[-4:], "little"):
        raise ValueError("patch is corrupt (CRC mismatch)")
    if zlib.crc32(src) != int.from_bytes(p[-12:-8], "little"):
        raise ValueError("source image does not match the patch (CRC mismatch)")
    pos = 4

    def rd():
        nonlocal pos
        n, shift = 0, 1
        while True:
            x = p[pos]
            pos += 1
            n += (x & 0x7F) * shift
            if x & 0x80:
                return n
            shift <<= 7
            n += shift

    ssz, tsz, msz = rd(), rd(), rd()
    pos += msz
    tgt = bytearray(tsz)
    o = src_rel = tgt_rel = 0
    end = len(p) - 12
    while pos < end:
        d = rd()
        mode, n = d & 3, (d >> 2) + 1
        if mode == 0:
            tgt[o:o + n] = src[o:o + n]
        elif mode == 1:
            tgt[o:o + n] = p[pos:pos + n]
            pos += n
        elif mode == 2:
            r = rd()
            src_rel += -(r >> 1) if r & 1 else (r >> 1)
            tgt[o:o + n] = src[src_rel:src_rel + n]
            src_rel += n
        else:
            r = rd()
            tgt_rel += -(r >> 1) if r & 1 else (r >> 1)
            for k in range(n):
                tgt[o + k] = tgt[tgt_rel + k]
            tgt_rel += n
        o += n
    if zlib.crc32(tgt) != int.from_bytes(p[-8:-4], "little"):
        raise ValueError("output CRC mismatch")
    open(out_path, "wb").write(tgt)


if __name__ == "__main__":
    if sys.argv[1] == "--apply":
        apply(*sys.argv[2:5])
        print("ok:", sys.argv[4])
    else:
        st, size = encode(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "")
        print(f"{sys.argv[3]}: {size:,} bytes; source-read {st['sourceread']:,}, source-copy {st['sourcecopy']:,}, literal {st['literal']:,}")
