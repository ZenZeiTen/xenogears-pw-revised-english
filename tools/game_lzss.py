"""Exact model of the game's LZSS decoder (SLUS_006.64 @ 0x80032EB4).

It allocates `size` bytes, then decodes whole groups of 8 tokens and only checks for the
end between groups, with an equality test (out == start + size). A stream is safe only
if decoding reaches exactly `size` bytes at the end of a group; otherwise the real decoder
writes past its buffer and never stops.
"""
import struct


def game_decode(src, max_overrun=64):
    """Return (data, consumed, status) with status 'ok' or 'overrun'."""
    size = struct.unpack_from("<I", src)[0]
    out = bytearray()
    p = 4
    rd = lambda i: src[i] if i < len(src) else 0
    while True:
        flags = rd(p); p += 1
        if len(out) == size:
            return bytes(out), p - 1, "ok"
        if len(out) > size + max_overrun:
            return bytes(out[:size]), p, "overrun"
        for bit in range(8):
            b0 = rd(p); p += 1
            if flags >> bit & 1:
                b1 = rd(p); p += 1
                d = ((b1 & 0xF) << 8) | b0
                for _ in range((b1 >> 4) + 3):
                    out.append(out[len(out) - d] if 0 < d <= len(out) else 0)
            else:
                out.append(b0)


def safe(src):
    data, _, status = game_decode(src)
    return status == "ok"
