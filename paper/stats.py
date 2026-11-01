"""Collect every number used in the paper from the project's own files -> paper/stats.json."""
import collections, difflib, glob, json, os, re, sys
sys.path.insert(0, "tools")
import jp_bundles as JB, jp_match as M, xgdisc

TAG = re.compile(r"<[^>]*>")
WORD = re.compile(r"[A-Za-z0-9]+(?:['\-][A-Za-z0-9]+)*")
BLOCK = re.compile(r"<TextBlock (\d+) w:\w+ h:\w+>\r?\n(.*?)<End of Block>", re.S)

def en_words(s):
    s = s.replace("<-->", " ")
    return len(WORD.findall(TAG.sub(" ", s.split("<Close>")[0] if "<Close>" in s else s)))

def jp_chars(s):
    s = TAG.sub("", s)
    return sum(1 for ch in s if not ch.isspace() and ch != "□"), s.count("□")

S = {}
# ---- whole-script scope (mechanical QA) ----
tot_files = tot_blocks = tot_words = 0
for p in glob.glob("pw_repo/PerfectWorks_Script/**/*.txt", recursive=True):
    t = open(p, encoding="latin-1").read().replace("\r\n", "\n")
    bl = BLOCK.findall(t)
    if not bl: continue
    tot_files += 1; tot_blocks += len(bl); tot_words += sum(en_words(b) for _, b in bl)
S["script"] = {"files": tot_files, "blocks": tot_blocks, "en_words": tot_words}
menu = [l.split("\t", 2)[2] for l in open("menu_strings_cd1.tsv", encoding="utf-8").read().splitlines()[1:]]
S["menus"] = {"strings": len(menu), "en_words": sum(len(WORD.findall(m)) for m in menu)}

# ---- JP-aligned review scope ----
DONE = {608,610,612,616,618,620,622,624,626,628,630,632,634,636,640,644,648,1974}
jp = xgdisc.Disc(JB.JPDISC)
rows = []          # per reviewed file
for f in sorted(DONE):
    pw = BLOCK.findall(open(f"pw_repo/PerfectWorks_Script/field/{f:04d}.txt", encoding="latin-1").read().replace("\r\n","\n"))
    jb = M.blocks(jp, f) or []
    c = u = 0
    for b in jb:
        a, x = jp_chars(JB.dec(b)); c += a; u += x
    rows.append({"file": f"{f:04d}", "pass": 1, "blocks": len(pw), "en_words": sum(en_words(b) for _, b in pw), "jp_chars": c, "jp_unk": u})
for p in sorted(glob.glob("bilingual2/[0-9]*.md")):
    f = os.path.basename(p)[:-3]
    t = open(p, encoding="utf-8").read()
    parts = re.split(r"^## Block \d+\n", t, flags=re.M)[1:]
    c = u = w = 0
    for part in parts:
        pw, _, j = part.partition("\nJP:\n")
        w += en_words(pw.replace("PW:\n", "", 1))
        if not j.startswith("(no matching"):
            a, x = jp_chars(re.sub(r"\(Japanese-only box.*", "", j, flags=re.S)); c += a; u += x
    late = f in {"0874","1024","1324","1386","1514","1582","1640","1966","1968","1970","1972"}
    rows.append({"file": f, "pass": 3 if late else 2, "blocks": len(parts), "en_words": w, "jp_chars": c, "jp_unk": u})
S["review_files"] = rows
agg = collections.defaultdict(lambda: collections.Counter())
for r in rows:
    for k in ("blocks", "en_words", "jp_chars", "jp_unk"): agg[r["pass"]][k] += r[k]
    agg[r["pass"]]["files"] += 1
S["review_by_pass"] = {str(k): dict(v) for k, v in agg.items()}
T = collections.Counter()
for v in agg.values(): T.update(v)
S["review_total"] = dict(T)

# ---- proposals, vetting, acceptance ----
batches = []
for n in range(28):
    raw = json.load(open(f"bilingual2/proposals_{n:02d}.json", encoding="utf-8"))
    chk = json.load(open(f"bilingual2/proposals_{n:02d}.checked.json", encoding="utf-8"))
    acc = json.load(open(f"edits/jp2_{n:02d}.json", encoding="utf-8")) if os.path.exists(f"edits/jp2_{n:02d}.json") else []
    batches.append({"batch": n, "proposed": len(raw), "passed_checks": len(chk), "accepted": len(acc)})
S["batches"] = batches
first_prop = sum(len(json.load(open(f"bilingual/proposals_{x}.json", encoding="utf-8"))) for x in "ABC")
first_acc = json.load(open("edits/jp_A.json", encoding="utf-8")) + json.load(open("edits/jp_BC.json", encoding="utf-8"))
S["first_pass"] = {"proposed": first_prop, "accepted": len(first_acc)}

later = json.load(open("edits/second_pass_all.json", encoding="utf-8")) + json.load(open("edits/third_pass_all.json", encoding="utf-8"))
jp_edits = [dict(e, _pass=1) for e in first_acc] + [dict(e, _pass=2) for e in later]
S["jp_edits_total"] = len(jp_edits)
S["by_category"] = dict(collections.Counter(e["category"] for e in jp_edits))
S["by_confidence"] = dict(collections.Counter(e.get("confidence", "n/a") for e in jp_edits))
S["by_cat_conf"] = {f"{c}|{k}": v for (c, k), v in collections.Counter((e["category"], e.get("confidence", "n/a")) for e in jp_edits).items()}
S["files_touched_jp"] = len({e["file"] for e in jp_edits})
# edit size: words before/after, character-level change
sizes = []
for e in jp_edits:
    o, n = TAG.sub("", e["old"]), TAG.sub("", e["new"])
    sm = difflib.SequenceMatcher(None, o, n)
    changed = sum(max(i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal")
    sizes.append({"cat": e["category"], "w_old": len(WORD.findall(o)), "w_new": len(WORD.findall(n)), "chars_changed": changed})
S["edit_sizes"] = sizes

# ---- mechanical QA and builds ----
g = json.load(open("edits/global.json", encoding="utf-8"))
S["global_fixes"] = {"total": len(g), "by_category": dict(collections.Counter(e["category"] for e in g))}
S["width_refits"] = len(json.load(open("edits/refit_width.json", encoding="utf-8")))
qa = json.load(open("qa_findings.json", encoding="utf-8"))
S["qa_scan"] = {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in qa.items()}
S["menu_fix_rules"] = 18; S["menu_strings_fixed_per_disc"] = 69
S["jp_table_codes"] = len(json.load(open("jp_table_full.json", encoding="utf-8")))
sync = re.findall(r"cd2 (\d{4}) <- cd1 (\d{4}): (\d+) of (\d+)", open(sys.argv[1], encoding="utf-8").read()) if len(sys.argv) > 1 else []
S["disc2_sync"] = [{"cd2": a, "cd1": b, "stale": int(s), "blocks": int(n)} for a, b, s, n in sync]
json.dump(S, open("paper/stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
R = S["review_total"]
print("script", S["script"], "menus", S["menus"])
print("review", S["review_by_pass"], "total", R, f"undecoded {R['jp_unk']/(R['jp_chars']+R['jp_unk']):.2%}")
print("first", S["first_pass"], "batches proposed", sum(b["proposed"] for b in batches), "passed", sum(b["passed_checks"] for b in batches), "accepted", sum(b["accepted"] for b in batches))
print("jp edits", S["jp_edits_total"], S["by_category"], S["by_confidence"], "files", S["files_touched_jp"])
print("global", S["global_fixes"], "refits", S["width_refits"], "qa", S["qa_scan"], "table", S["jp_table_codes"], "sync", len(sync), sum(x["stale"] for x in S["disc2_sync"]))
