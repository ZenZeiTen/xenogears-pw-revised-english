"""Bilingual bundles for field files whose PW and JP block counts differ.

Trailing empty blocks (the US build pads some files with 29 empty boxes) are dropped on
both sides, and so is a long JP-only tail (debug menus the US build removed). If the counts then agree, blocks pair 1:1. Otherwise they are aligned by
translation-proof fingerprints (script opcodes + length bucket, see jp_match.py); a PW
block with no Japanese partner says so, and Japanese-only boxes are listed after the
block they follow.

  python jp_bundles2.py fid [fid ...]   -> bilingual2/<fid>.md
"""
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import jp_bundles as JB
import jp_match as M
import xgdisc

BLOCK = re.compile(r"<TextBlock (\d+) w:\w+ h:\w+>\r?\n(.*?)<End of Block>", re.S)
US = "out/CD1_translated_v3.bin"


def length_align(a, c, gap=1.5):
    """Global alignment of PW and JP blocks by visible length (English ~2.5x the Japanese).
    Returns (pairs, extra) like main() uses. Only meant for counts a few blocks apart."""
    import math
    la = [math.log((x + 1) / 2.5) for x in a]
    lc = [math.log(x + 1) for x in c]
    n, m = len(a), len(c)
    D = [[0.0] * (m + 1) for _ in range(n + 1)]
    P = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        D[i][0], P[i][0] = D[i - 1][0] + gap, "u"
    for j in range(1, m + 1):
        D[0][j], P[0][j] = D[0][j - 1] + gap, "l"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i][j], P[i][j] = min((D[i - 1][j - 1] + abs(la[i - 1] - lc[j - 1]), "d"),
                                   (D[i - 1][j] + gap, "u"), (D[i][j - 1] + gap, "l"))
    pairs, extra, i, j = {}, {}, n, m
    while i or j:
        t = P[i][j]
        if t == "d":
            pairs[i - 1] = j - 1; i -= 1; j -= 1
        elif t == "u":
            i -= 1
        else:
            extra.setdefault(i - 1, []).insert(0, j - 1); j -= 1
    return pairs, extra


def strip_tail(xs, empty):
    n = len(xs)
    while n and empty(xs[n - 1]):
        n -= 1
    return xs[:n]


def main():
    jp, us = xgdisc.Disc(JB.JPDISC), xgdisc.Disc(US)
    for fid in sys.argv[1:]:
        pw = [(int(m.group(1)), m.group(2).replace("\r\n", "\n"))
              for m in BLOCK.finditer(open(f"pw_repo/PerfectWorks_Script/field/{fid}.txt", encoding="latin-1").read())]
        ub = M.blocks(us, int(fid))
        jb = M.blocks(jp, int(fid)) or []
        pw = strip_tail(pw, lambda x: not x[1].replace("<Close>", "").strip())
        ub = ub[:len(pw)]
        jb = strip_tail(jb, lambda b: not JB.dec(b).strip())
        if len(jb) - len(pw) >= 10:      # JP keeps a debug-menu tail the US build cut (e.g. 1582)
            jb = jb[:len(pw)]
        pairs = {}                       # PW index -> JP index
        extra = {}                       # PW index -> [JP-only indices after it]
        if len(jb) == len(pw):
            pairs = {k: k for k in range(len(pw))}
            how = "paired 1:1 after dropping empty padding boxes"
        elif abs(len(jb) - len(pw)) <= 3:
            pairs, extra = length_align([len(b) for b in ub],
                                        [len(JB.dec(b)) for b in jb])
            how = "ALIGNED by box length, not 1:1: check each pair makes sense before relying on it"
        else:
            a = [M.fingerprint(b, False) for b in ub]
            c = [M.fingerprint(b, True) for b in jb]
            sm = difflib.SequenceMatcher(None, a, c, autojunk=False)
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag in ("equal", "replace"):
                    for k in range(min(i2 - i1, j2 - j1)):
                        pairs[i1 + k] = j1 + k
                    if j2 - j1 > i2 - i1:
                        extra.setdefault(i2 - 1, []).extend(range(j1 + i2 - i1, j2))
                elif tag == "insert":
                    extra.setdefault(i1 - 1, []).extend(range(j1, j2))
            how = "ALIGNED by fingerprint, not 1:1: check each pair makes sense before relying on it"
        L = [f"# Field file {fid}  ({len(pw)} PW blocks, {len(jb)} JP blocks; {how})\n"]
        for k, (num, body) in enumerate(pw):
            j = JB.dec(jb[pairs[k]]).rstrip() if k in pairs else "(no matching Japanese box)"
            L.append(f"## Block {num}\nPW:\n{body.replace('<Close>', '').rstrip()}\nJP:\n{j}\n")
            for x in extra.get(k, []):
                L.append(f"(Japanese-only box, no PW counterpart):\n{JB.dec(jb[x]).rstrip()}\n")
        open(f"bilingual2/{fid}.md", "w", encoding="utf-8").write("\n".join(L))
        print(fid, len(pw), len(jb), how.split(",")[0], len(pairs), "paired")


if __name__ == "__main__":
    main()
