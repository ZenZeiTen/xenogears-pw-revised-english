"""Mechanical vetting of reviewer proposals before human judgment.

Checks: `old` occurs exactly once in the current .txt block; the edit applies to the
current translated disc's bytes; line/page limits hold. Prints a compact digest of
the proposals that pass, for reading against the Japanese.

  python vet.py proposals_XX.json [...]  -> writes <name>.checked.json next to each
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import script_patch as SP
import xgdisc

ROOT = Path(__file__).parents[1]
TXT = ROOT / "pw_repo" / "PerfectWorks_Script" / "field"
DISC = ROOT / "out" / "CD1_translated_v3.bin"   # the build new edits will be applied to
BLOCK = re.compile(r"<TextBlock (\d+) w:\w+ h:\w+>\r?\n(.*?)<End of Block>", re.S)
TAGLEN = re.compile(r"<(Delay \d+|Opcode \d+ \d+|Close|Wait|New|UNKNOWN CHUNK \d+|Extra\d \d+)>")


def vis_len(line):
    line = TAGLEN.sub("", line).replace("<-->", "-")
    return len(re.sub(r"<([^>]+)>", r"\1", line))


def pages(body):
    return [[l for l in p.strip("\n").split("\n")] for p in body.split("<New>")]


def check(e, blocks, table, disc):
    body = blocks.get(e["block"])
    if body is None:
        return "no such block"
    if body.count(e["old"]) != 1:
        return f"old found {body.count(e['old'])}x in .txt"
    new_body = body.replace(e["old"], e["new"])
    old_max = max(vis_len(l) for p in pages(body) for l in p)
    old_lines = max(len(p) for p in pages(body))
    for p in pages(new_body):
        for l in p:
            if vis_len(l) > max(28, old_max):
                return f"line too long ({vis_len(l)}): {l!r}"
        if len(p) > max(4, old_lines):
            return f"page has {len(p)} lines"
    try:
        SP.patch_field(disc.read_file(int(e["file"])), [e], table, [])
    except Exception as ex:
        return f"disc: {ex}"
    return None


def main():
    table = SP.load_table()
    disc = xgdisc.Disc(str(DISC))
    for path in sys.argv[1:]:
        props = json.load(open(path, encoding="utf-8"))
        ok, bad = [], []
        cache = {}
        for e in props:
            if e["file"] not in cache:
                t = open(TXT / f"{e['file']}.txt", encoding="latin-1").read().replace("\r\n", "\n")
                cache[e["file"]] = {int(m.group(1)): m.group(2) for m in BLOCK.finditer(t)}
            err = check(e, cache[e["file"]], table, disc)
            (bad if err else ok).append((e, err))
        out = Path(path).with_suffix(".checked.json")
        json.dump([e for e, _ in ok], open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{Path(path).name}: {len(ok)} pass, {len(bad)} fail")
        for e, err in bad:
            print(f"   FAIL {e['file']}#{e['block']}: {err}")


if __name__ == "__main__":
    main()
