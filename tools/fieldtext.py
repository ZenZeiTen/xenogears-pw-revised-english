"""Field text (section 7 of a field file) <-> Perfect Works .txt format.

Section 7 layout:
  u32 n                      number of blocks - 1
  u16 offset[n+1]            offset of each block from section start
  u8  w, h  [n+1]            box width / height
  text ...                   blocks, each ending in its <Close> bytes

Field file: 9 LZSS sections; u32 decompressed sizes at 0x10C, u32 offsets at 0x130.
"""
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xgdisc

SIZES_AT, OFFS_AT = 0x10C, 0x130
BLOCK = re.compile(r"<TextBlock (\d+) w:(\d+) h:(\d+)>\r?\n(.*?)<End of Block>", re.S)
TOKEN = re.compile(r"<[^<>\r\n]*>|\r?\n|.", re.S)

# Learned from the shipped files (see learn() / the round-trip test).
MAP = {"\n": b"\x01", " ": b"\x10", '"': b"\x58", "!": b"\x57", "?": b"\x60", ".": b"\x14",
       "<Close>": b"\x00", "<New>": b"\x02"}
for c in range(26):
    MAP[chr(65 + c)] = bytes([0x20 + c])
    MAP[chr(97 + c)] = bytes([0x3D + c])


def tokens(body):
    out = []
    for t in TOKEN.findall(body):
        t = "\n" if t in ("\r\n", "\n") else t
        if t == "\n" and out and out[-1] == "<New>":
            continue  # "<New>" is written on its own line; the break is part of the tag
        out.append(t)
    return out


def encode_token(t, table):
    if t in table:
        return table[t]
    m = re.fullmatch(r"<Delay (\d+)>", t)
    if m:
        return bytes([0x0F, 0x00, int(m.group(1))])
    m = re.fullmatch(r"<Opcode (\d+) (\d+)>", t)
    if m:
        return bytes([0x0F, int(m.group(1)), int(m.group(2))])
    m = re.fullmatch(r"<UNKNOWN CHUNK (\d+)>", t)
    if m:
        return bytes([int(m.group(1))])
    m = re.fullmatch(r"<Extra(\d) (\d+)>", t)
    if m and m.group(1) in table.get("_extra", {}):
        return table["_extra"][m.group(1)] + bytes([int(m.group(2))])
    raise KeyError(t)


def encode_block(body, table):
    return b"".join(encode_token(t, table) for t in tokens(body))


def read_field(raw):
    sizes = list(struct.unpack_from("<9I", raw, SIZES_AT))
    offs = list(struct.unpack_from("<9I", raw, OFFS_AT))
    return sizes, offs


def text_section(raw):
    _, offs = read_field(raw)
    end = offs[8] if offs[8] else len(raw)
    return xgdisc.lzss_decompress(raw[offs[7]:end])[0]


def split_section(sec):
    n = struct.unpack_from("<I", sec)[0]
    offs = list(struct.unpack_from(f"<{n + 1}H", sec, 4))
    dims = [(sec[4 + 2 * (n + 1) + 2 * i], sec[5 + 2 * (n + 1) + 2 * i]) for i in range(n + 1)]
    ends = offs[1:] + [len(sec)]
    return [(dims[i], sec[offs[i]:ends[i]]) for i in range(n + 1)]


def build_section(blocks, pad_to=None):
    """blocks: [((w, h), bytes)]. Returns section bytes."""
    n = len(blocks) - 1
    head = 4 + 2 * (n + 1) + 2 * (n + 1)
    offs, pos = [], head
    for _, b in blocks:
        offs.append(pos)
        pos += len(b)
    out = struct.pack("<I", n) + struct.pack(f"<{n + 1}H", *offs)
    out += b"".join(bytes([w, h]) for (w, h), _ in blocks)
    out += b"".join(b for _, b in blocks)
    return out
