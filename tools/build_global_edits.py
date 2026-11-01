"""Turn the review's high-confidence script findings into edits.json entries."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])          # PerfectWorks_Script
OUT = sys.argv[2]

# (file, block or None for "find the unique block", old, new, category, reason)
FIXES = [
    ("1198", 15, "capabilties", "capabilities", "typo", "spelling"),
    ("1186", 118, "cordinates", "coordinates", "typo", "spelling"),
    ("1840", 13, "did'n't", "didn't", "typo", "spelling"),
    ("0812", 98, "disinguished", "distinguished", "typo", "spelling"),
    ("1326", 1, "minuite", "minute", "typo", "spelling"),
    ("0696", 8, "orginally", "originally", "typo", "spelling"),
    ("0782", 9, "possiblity", "possibility", "typo", "spelling"),
    ("0900", 20, "rememberance", "remembrance", "typo", "spelling"),
    ("0764", 66, "responsiblities", "responsibilities", "typo", "spelling"),
    ("1152", 91, "significiance", "significance", "typo", "spelling"),
    ("0896", 7, "tyrany", "tyranny", "typo", "spelling"),
    ("0998", 74, "unbelieveable", "unbelievable", "typo", "spelling"),
    ("0758", 41, "unidentifed", "unidentified", "typo", "spelling"),
    ("2034", 31, "trascends", "transcends", "typo", "spelling"),
    ("1198", None, "Mechior", "Melchior", "typo", "name spelling (Melchior, one of the Three Magi)"),
    ("0800", 67, "Bartholemew", "Bartholomew", "typo", "name spelling"),
    ("0658", 9, "tags of\nof the", "tags of\nthe", "typo", "doubled word across a line break"),
    ("1032", 192, "when you\nyou are", "when you\nare", "typo", "doubled word across a line break"),
    ("1048", 76, "to to", "to", "typo", "doubled word"),
    ("1408", 15, "examination at\nat the", "examination at\nthe", "typo", "doubled word across a line break"),
    ("0964", 8, "cancelled", "canceled", "style", "US spelling (style guide)"),
    ("1194", 29, "cancelled", "canceled", "style", "US spelling (style guide)"),
    ("1076", 8, "rumours", "rumors", "style", "US spelling (style guide)"),
    ("1840", 3, "dreamt", "dreamed", "style", "US spelling (style guide)"),
    ("1840", 10, "dreamt", "dreamed", "style", "US spelling (style guide)"),
    ("1930", 11, "behaviour", "behavior", "style", "US spelling (style guide)"),
    ("2034", 31, "programme", "program", "style", "US spelling (style guide)"),
    ("2034", 38, "programme", "program", "style", "US spelling (style guide)"),
    ("1208", 46, "all right", "alright", "style", "'Alright rather than all right' (style guide)"),
    ("1048", 134, "Start button", "START button", "style", "TRC button casing (style guide)"),
    ("1036", 1, "15 years ago", "Fifteen years ago", "style", "numbers 1-100 spelled out (style guide)"),
    ("0648", None, "Huh....!?", "Huh...!?", "typo", "four-dot ellipsis"),
    ("1982", None, "a....", "a...", "typo", "four-dot ellipsis"),
    ("1182", None, "back..?", "back...?", "typo", "two-dot ellipsis"),
    ("1496", None, "open..", "open...", "typo", "two-dot ellipsis"),
    ("1944", None, "Well..", "Well...", "typo", "two-dot ellipsis"),
    ("2006", None, "boosted..", "boosted...", "typo", "two-dot ellipsis"),
    ("1466", None, ' "', '"', "typo", "stray space before closing quote"),
    ("1906", None, '... "', '..."', "typo", "stray space before closing quote"),
]

BLOCK = re.compile(r"<TextBlock (\d+) w:\w+ h:\w+>\r?\n(.*?)<End of Block>", re.S)


def blocks(fid):
    txt = open(ROOT / "field" / f"{fid}.txt", encoding="latin-1").read()
    return {int(m.group(1)): m.group(2).replace("\r\n", "\n") for m in BLOCK.finditer(txt)}


edits = []
for fid, blk, old, new, cat, why in FIXES:
    bl = blocks(fid)
    targets = [blk] if blk else [n for n, b in bl.items() if old in b]
    for n in targets:
        body = bl[n]
        if body.count(old) != 1:
            # widen with surrounding context until unique
            i = body.find(old)
            if i < 0:
                print("MISSING", fid, n, old); continue
            k = 1
            while body.count(body[max(0, i - k):i + len(old)]) > 1 and k < 40:
                k += 1
            ctx = body[max(0, i - k):i]
            old2, new2 = ctx + old, ctx + new
        else:
            old2, new2 = old, new
        edits.append({"file": fid, "block": n, "old": old2, "new": new2, "category": cat, "reason": why})

# missing closing quotes: blocks from the review list
for line in open(sys.argv[3], encoding="utf-8"):
    m = re.match(r"/?field/(\d{4})\.txt#(\d+):", line)
    if not m:
        continue
    fid, n = m.group(1), int(m.group(2))
    body = blocks(fid)[n]
    core = re.match(r"(.*?)((?:<(?:Delay|Opcode|Wait)[^>]*>)*<Close>.*)$", body, re.S)
    text, tail = core.group(1), core.group(2)
    last = text.split("\n")[-1]
    if not last or last.endswith('"'):
        continue
    old = last + tail.split("<Close>")[0] + "<Close>"
    if body.count(old) != 1:
        print("AMBIG", fid, n); continue
    new = last + '"' + tail.split("<Close>")[0] + "<Close>"
    edits.append({"file": fid, "block": n, "old": old, "new": new, "category": "style",
                  "reason": "missing closing quote on named dialogue (style guide)"})

json.dump(edits, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(edits), "edits")
