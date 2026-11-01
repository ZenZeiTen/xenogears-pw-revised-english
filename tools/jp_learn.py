"""Learn the Japanese disc's text encoding from chapters 1-6 (xenogears.us has those in Japanese).

Token rules (from inspection): 0x00 end, 0x01 newline, 0x02 page, 0x0F a b control
(0x0F 0x05 n = name pointer), bytes >= LEAD_MIN start a two-byte character, others
are one-byte characters. Each disc block is paired with the site block of the same
file whose length matches and whose known characters agree best; position-wise
pairs then vote for character mappings. Repeats until stable.

  python jp_learn.py <jp disc .bin> <xgus_scripts dir> <out table.json>
"""
import collections
import glob
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fieldtext as F
import xgdisc

LEAD_MIN = 0xF8


def tokens(b):
    """Block bytes -> list of tokens: ('c', code) characters, ('nl',) newline, ('pg',)."""
    out, i = [], 0
    while i < len(b):
        c = b[i]
        if c == 0x00:
            break
        if c == 0x01:
            out.append(("nl",))
        elif c == 0x02:
            out.append(("pg",))
        elif c == 0x0F:
            if b[i + 1] == 0x05:
                out.append(("name", b[i + 2]))
            i += 3
            continue
        elif c >= LEAD_MIN and i + 1 < len(b):
            out.append(("c", (c << 8) | b[i + 1]))
            i += 2
            continue
        else:
            out.append(("c", c))
        i += 1
    return out


def site_blocks(xgus_dir):
    """file id -> list of (speaker or None, text without newlines) from the site's JP chapters."""
    res = collections.defaultdict(list)
    for p in sorted(glob.glob(f"{xgus_dir}/*_JP_*.txt")):
        t = open(p, encoding="utf-8").read().replace("\r\n", "\n")
        parts = re.split(r"^—{5,}\n(.+?)\n—{5,}\n", t, flags=re.M)
        fid = None
        for i in range(1, len(parts), 2):
            m = re.search(r" - (\d{4})[a-z]? - \w+\s*$", parts[i])
            fid = m.group(1) if m else fid
            if not fid:
                continue
            for chunk in re.split(r"\n\s*\n", parts[i + 1].strip()):
                lines = [l for l in chunk.split("\n") if l.strip()]
                if not lines:
                    continue
                speaker = None
                if len(lines) > 1 and lines[1].startswith(("「", "\"", "（")) and not lines[0].startswith(("「", "　")):
                    speaker = lines[0]
                    lines = lines[1:]
                res[fid].append((speaker, "".join(lines)))
    return res


def char_tokens(blk):
    return [t[1] for t in blk if t[0] == "c"]


def main():
    disc = xgdisc.Disc(sys.argv[1])
    site = site_blocks(sys.argv[2])
    disc_blocks = {}
    for fid in site:
        raw = disc.read_file(int(fid))
        disc_blocks[fid] = [tokens(b) for _, b in F.split_section(F.text_section(raw)[:F.read_field(raw)[0][7]])]
    # seeds read by hand from 0634 blocks 1-2 (see notes)
    table = {0x5C: "「", 0x51: "。", 0x50: "、", 0x58: "…", 0x4F: "　", 0x81: "だ", 0x6D: "い",
             0x80: "た", 0x76: "こ", 0xA5: "ん", 0x89: "な", 0x87: "と", 0x71: "か", 0x9D: "よ",
             0x79: "し", 0x7E: "そ", 0xA1: "れ", 0x7A: "じ", 0x9A: "ゃ", 0x82: "ち", 0x9C: "ょ",
             0x83: "っ", 0x91: "ひ", 0x97: "み", 0x7B: "す", 0xA0: "る"}
    for rnd in range(12):
        votes = collections.defaultdict(collections.Counter)
        paired = 0
        for fid, dbl in disc_blocks.items():
            cands = site[fid]
            for blk in dbl:
                ct = char_tokens(blk)
                if not ct:
                    continue
                best, best_score = None, -1
                for spk, txt in cands:
                    if len(txt) != len(ct):
                        continue
                    known = [(table[c], ch) for c, ch in zip(ct, txt) if c in table]
                    if not known:
                        continue
                    score = sum(a == b for a, b in known) / len(known)
                    if score > best_score:
                        best, best_score = txt, score
                if best is None or best_score < 0.9:
                    continue
                paired += 1
                for c, ch in zip(ct, best):
                    votes[c][ch] += 1
        new = {}
        for c, cnt in votes.items():
            (ch, n), *rest = cnt.most_common(2)
            if n >= 1 and (not rest or n >= 3 * rest[0][1]):
                new[c] = ch
        added = {c: ch for c, ch in new.items() if table.get(c) != ch}
        table.update(new)
        print(f"round {rnd}: paired {paired} blocks, table {len(table)} (+{len(added)})")
        if not added:
            break
    json.dump({f"{k:04x}": v for k, v in sorted(table.items())}, open(sys.argv[3], "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
