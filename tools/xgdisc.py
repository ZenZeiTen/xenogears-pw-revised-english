"""Xenogears disc helpers: file table, file extraction, LZSS (de)compression."""
import struct
import sys

SECTOR = 2352
DATA_OFF = 24
DATA_LEN = 2048


class Disc:
    def __init__(self, path, mode="rb"):
        self.path = path
        self.f = open(path, mode)
        self.entries = self._read_table()

    def sector(self, n):
        self.f.seek(n * SECTOR + DATA_OFF)
        return self.f.read(DATA_LEN)

    def _read_table(self):
        # Table lives at sectors 24..38, 7-byte entries: s24 start sector, s32 size.
        # (Perfect Works reuses sector 25 for code; those entries are unused.)
        raw = b"".join(self.sector(24 + i) for i in range(15))
        ents = []
        for i in range(len(raw) // 7):
            e = raw[i * 7:i * 7 + 7]
            s = e[0] | e[1] << 8 | e[2] << 16
            if s & 0x800000:
                s -= 0x1000000
            ents.append((s, struct.unpack("<i", e[3:7])[0]))
        return ents

    def read_file(self, idx):
        start, size = self.entries[idx]
        if start <= 0 or size <= 0:
            raise ValueError(f"entry {idx} is not a file: {start},{size}")
        n = (size + DATA_LEN - 1) // DATA_LEN
        return b"".join(self.sector(start + i) for i in range(n))[:size]

    def file_offset(self, idx, off):
        """Raw .bin byte offset for byte `off` inside file `idx`."""
        start, _ = self.entries[idx]
        return (start + off // DATA_LEN) * SECTOR + DATA_OFF + off % DATA_LEN


def lzss_decompress(src):
    """Xenogears LZSS.

    u32 decompressed size, then a flag byte per 8 tokens, LSB first.
    bit=0: literal byte.  bit=1: 2 bytes b0,b1 -> distance = (b1&0xF)<<8 | b0,
    length = (b1>>4)+3.  References before the start read a zero-filled window.
    """
    out_len = struct.unpack("<I", src[:4])[0]
    out = bytearray()
    p = 4
    while len(out) < out_len and p < len(src):
        flags = src[p]
        p += 1
        for bit in range(8):
            if len(out) >= out_len or p >= len(src):
                break
            if flags & (1 << bit):
                b0, b1 = src[p], src[p + 1]
                p += 2
                length = (b1 >> 4) + 3
                dist = ((b1 & 0x0F) << 8) | b0
                for _ in range(length):
                    out.append(out[-dist] if 0 < dist <= len(out) else 0)
            else:
                out.append(src[p])
                p += 1
    out.extend(bytes(max(0, out_len - len(out))))
    return bytes(out[:out_len]), p


MAX_DIST = 0xFEE   # 4078: the largest distance Square's own encoder ever emits


def lzss_compress_optimal(data, chain=256):
    """Encode `data` so the GAME's decoder reads it back exactly, as small as possible.

    The game's decoder (SLUS_006.64 @ 0x80032EB4, modelled in game_lzss.py) decodes whole
    groups of 8 tokens and only stops when the output length EQUALS the header size at a
    group boundary. A stream whose last group is short makes it write past its buffer and
    never stop, which hung the game at boot with the first builds. So the total number of
    tokens must be a multiple of 8.

    Dynamic programming over (position, tokens mod 8) finds the smallest such parse: a
    literal costs 9 bits and a match 17, so minimizing bits minimizes bytes. Distances stay
    within Square's own range (<= 4078) and never reach before the start of the data.
    Raises ValueError when no aligned parse exists (very short data)."""
    n = len(data)
    best_len = [0] * n
    best_dist = [0] * n
    heads = {}
    for i in range(n):
        maxl = min(18, n - i)
        if maxl >= 3:
            key = data[i:i + 3]
            cands = heads.get(key)
            bl = bd = 0
            if cands:
                for j in reversed(cands[-chain:]):
                    d = i - j
                    if d > MAX_DIST:
                        break
                    L = 3
                    while L < maxl and data[j + L] == data[i + L]:
                        L += 1
                    if L > bl:
                        bl, bd = L, d
                        if L == maxl:
                            break
            best_len[i], best_dist[i] = bl, bd
            heads.setdefault(key, []).append(i)
    INF = 1 << 60
    cost = [None] * (n + 1)
    cost[n] = [0] + [INF] * 7                     # cost[i][r]: suffix i..n in t tokens, t % 8 == r
    choice = bytearray(8 * n)                     # 0 = literal, else match length
    for i in range(n - 1, -1, -1):
        nxt = cost[i + 1]
        row = [nxt[(r - 1) & 7] + 9 for r in range(8)]
        ch = [0] * 8
        for L in range(3, best_len[i] + 1):
            nl = cost[i + L]
            for r in range(8):
                v = nl[(r - 1) & 7] + 17
                if v < row[r]:
                    row[r], ch[r] = v, L
        cost[i] = row
        choice[8 * i:8 * i + 8] = bytes(ch)
        if i + 19 <= n:
            cost[i + 19] = None                   # no longer needed (matches reach <= 18 ahead)
    if cost[0][0] >= INF:
        raise ValueError("no token-aligned encoding exists for this data")
    out = bytearray(struct.pack("<I", n))
    i, r = 0, 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            L = choice[8 * i + r]
            r = (r - 1) & 7
            if L:
                d = best_dist[i]
                flags |= 1 << bit
                out += bytes([d & 0xFF, ((L - 3) << 4) | (d >> 8)])
                i += L
            else:
                out.append(data[i])
                i += 1
        out[flag_pos] = flags
    assert r == 0 and i == n
    return bytes(out)


def lzss_compress(data):
    """Inverse of lzss_decompress. Greedy longest match over a 4095-byte window;
    never references bytes before the start, so it doesn't rely on the zero window."""
    n = len(data)
    out = bytearray(struct.pack("<I", n))
    heads = {}  # 3-byte prefix -> list of positions (most recent last)
    i = 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len, best_dist = 0, 0
            key = data[i:i + 3]
            if len(key) == 3:
                cands = heads.get(key, ())
                for j in reversed(cands[-64:]):
                    dist = i - j
                    if dist > 0xFFF:
                        break
                    L = 3
                    while L < 18 and i + L < n and data[j + L] == data[i + L]:
                        L += 1
                    if L > best_len:
                        best_len, best_dist = L, dist
                        if L == 18:
                            break
            if best_len >= 3:
                flags |= 1 << bit
                out += bytes([best_dist & 0xFF, ((best_len - 3) << 4) | (best_dist >> 8)])
                step = best_len
            else:
                out.append(data[i])
                step = 1
            for k in range(i, min(i + step, n - 2)):
                heads.setdefault(data[k:k + 3], []).append(k)
            i += step
        out[flag_pos] = flags
    return bytes(out)


def write_file(path, idx, data, entries_cache=None):
    """Write file `idx` into a raw .bin image in place (copy the image first).

    Reuses the file's own sectors when the new data fits before the next file
    starts; otherwise appends it after the last sector of the image. Updates the
    7-byte table entry (sectors 24..39) and regenerates EDC/ECC for every touched
    sector. Returns (start_sector, relocated?).
    """
    import cdsector
    with open(path, "r+b") as f:
        def rd_sector(n):
            f.seek(n * SECTOR)
            return bytearray(f.read(SECTOR))

        def wr_sector(n, sec):
            cdsector.fix_mode2_form1(sec)
            f.seek(n * SECTOR)
            f.write(sec)

        disc = Disc.__new__(Disc)
        disc.f = f
        entries = disc._read_table()
        start, size = entries[idx]
        later = sorted(s for s, z in entries if s > start)
        limit = (later[0] - start) * DATA_LEN if later else None
        need = (len(data) + DATA_LEN - 1) // DATA_LEN
        relocated = limit is None or len(data) > limit
        if relocated:
            f.seek(0, 2)
            start = f.tell() // SECTOR
            template = rd_sector(start - 1)  # copy a data sector's header layout
        for k in range(need):
            n = start + k
            chunk = data[k * DATA_LEN:(k + 1) * DATA_LEN].ljust(DATA_LEN, b"\0")
            if relocated:
                sec = bytearray(template)
                m, s_, fr = (n + 150) // 4500, (n + 150) // 75 % 60, (n + 150) % 75
                sec[12:15] = bytes(int(str(v), 16) for v in (m, s_, fr))  # BCD MSF
                sec[16:24] = bytes([0, 0, 0x08, 0, 0, 0, 0x08, 0])
            else:
                sec = rd_sector(n)
            sec[DATA_OFF:DATA_OFF + DATA_LEN] = chunk
            wr_sector(n, sec)
        # table entry
        pos = idx * 7
        tsec, toff = 24 + pos // DATA_LEN, pos % DATA_LEN
        entry = bytes([start & 0xFF, (start >> 8) & 0xFF, (start >> 16) & 0xFF]) + struct.pack("<i", len(data))
        for b_i, b in enumerate(entry):
            s_n, o = 24 + (pos + b_i) // DATA_LEN, (pos + b_i) % DATA_LEN
            sec = rd_sector(s_n)
            sec[DATA_OFF + o] = b
            wr_sector(s_n, sec)
    return start, relocated


if __name__ == "__main__":
    d = Disc(sys.argv[1])
    for i in map(int, sys.argv[2:]):
        print(i, d.entries[i])
