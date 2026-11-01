"""Draw the data figures from stats.json and print the derived numbers quoted in the text."""
import collections, json, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

S = json.load(open("stats.json", encoding="utf-8"))
ACC, ACC2, GRAY, LIGHT, INK = "#584b9a", "#9d93cf", "#8a8a95", "#d9d6ea", "#16151c"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7.5, "axes.edgecolor": GRAY,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
                     "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
D = {}

def label(ax, bars, fmt="{:,}", dy=0.01, inside=False):
    top = ax.get_ylim()[1]
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + top * dy, fmt.format(h), ha="center", va="bottom", fontsize=6.5)

# ---------- Figure 2: scope and funnel ----------
P = S["review_by_pass"]
names = {"1": "Pass 1", "2": "Pass 2", "3": "Pass 3"}
fig, ax = plt.subplots(1, 3, figsize=(6.6, 2.15), gridspec_kw={"width_ratios": [1.1, 1.1, 1.3]})
ks = ["1", "2", "3"]
b = ax[0].bar([names[k] for k in ks], [P[k]["jp_chars"] for k in ks], color=[ACC2, ACC, ACC2])
ax[0].set_ylim(0, 600000); label(ax[0], b); ax[0].set_ylabel("Japanese characters"); ax[0].set_title("a", loc="left", fontweight="bold")
b = ax[1].bar([names[k] for k in ks], [P[k]["en_words"] for k in ks], color=[ACC2, ACC, ACC2])
ax[1].set_ylim(0, 240000); label(ax[1], b); ax[1].set_ylabel("English words"); ax[1].set_title("b", loc="left", fontweight="bold")
for a in ax[:2]:
    a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: f"{int(x/1000)}k"))
B = S["batches"]; F = S["first_pass"]
stages = ["Proposed", "Passed\ngate 1", "Accepted"]
first = [F["proposed"], 0, F["accepted"]]        # pass 1 kept no record of a separate mechanical stage
later = [sum(x["proposed"] for x in B), sum(x["passed_checks"] for x in B), sum(x["accepted"] for x in B)]
x = range(3)
b1 = ax[2].bar([i - 0.2 for i in x], later, 0.4, color=ACC, label="Passes 2–3")
b2 = ax[2].bar([i + 0.2 for i in x], first, 0.4, color=ACC2, label="Pass 1")
ax[2].set_xticks(list(x)); ax[2].set_xticklabels(stages); ax[2].set_ylim(0, 640)
label(ax[2], b1); label(ax[2], [b for b in b2 if b.get_height()]); ax[2].text(1.2, 12, "n/r", ha="center", fontsize=6.3, color=GRAY)
ax[2].set_ylabel("Proposals"); ax[2].legend(frameon=False, fontsize=6.5, loc="upper center", ncol=2, bbox_to_anchor=(0.5, 1.02))
ax[2].set_title("c", loc="left", fontweight="bold")
fig.tight_layout(); fig.savefig("fig_scope.pdf"); plt.close(fig)
D["funnel_later"] = later; D["funnel_first"] = first

# ---------- Figure 3: categories x confidence, edit size ----------
cats = ["mistranslation", "omission", "speaker", "typo", "style"]
cc = S["by_cat_conf"]
hi = [cc.get(f"{c}|high", 0) for c in cats]; md = [cc.get(f"{c}|medium", 0) for c in cats]
fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.3), gridspec_kw={"width_ratios": [1.15, 1]})
ax[0].barh(cats[::-1], hi[::-1], color=ACC, label="high confidence")
ax[0].barh(cats[::-1], md[::-1], left=hi[::-1], color=ACC2, label="medium confidence")
for i, (h, m) in enumerate(zip(hi[::-1], md[::-1])):
    ax[0].text(h + m + 4, i, f"{h + m}", va="center", fontsize=6.5)
ax[0].set_xlim(0, 400); ax[0].set_xlabel("Accepted Japanese-grounded revisions"); ax[0].legend(frameon=False, fontsize=6.5, loc="lower right")
ax[0].set_title("a", loc="left", fontweight="bold")
sizes = S["edit_sizes"]
ch = [min(s["chars_changed"], 120) for s in sizes]
ax[1].hist(ch, bins=range(0, 125, 5), color=ACC, edgecolor="white", linewidth=0.4)
med = statistics.median(s["chars_changed"] for s in sizes)
ax[1].axvline(med, color=INK, lw=0.8, ls="--"); ax[1].text(med + 2, ax[1].get_ylim()[1] * 0.9, f"median {med:.0f}", fontsize=6.5)
ax[1].set_xlabel("Characters changed per revision (capped at 120)"); ax[1].set_ylabel("Revisions")
ax[1].set_title("b", loc="left", fontweight="bold")
fig.tight_layout(); fig.savefig("fig_categories.pdf"); plt.close(fig)
D["median_chars"] = med
D["share_le_20"] = sum(1 for s in sizes if s["chars_changed"] <= 20) / len(sizes)
D["share_gt_60"] = sum(1 for s in sizes if s["chars_changed"] > 60) / len(sizes)
D["words_old"] = sum(s["w_old"] for s in sizes); D["words_new"] = sum(s["w_new"] for s in sizes)
D["by_cat_median"] = {c: statistics.median([s["chars_changed"] for s in sizes if s["cat"] == c]) for c in cats}

# ---------- Figure 4: density along the game ----------
rows = S["review_files"]
edits_per_file = collections.Counter()
for e in json.load(open("../edits/jp_A.json", encoding="utf-8")) + json.load(open("../edits/jp_BC.json", encoding="utf-8")) \
        + json.load(open("../edits/second_pass_all.json", encoding="utf-8")) + json.load(open("../edits/third_pass_all.json", encoding="utf-8")):
    edits_per_file[e["file"]] += 1
band = lambda f: (int(f) - 600) // 150
bw = collections.Counter(); bj = collections.Counter(); be = collections.Counter(); bf = collections.Counter()
for r in rows:
    k = band(r["file"]); bw[k] += r["en_words"]; bj[k] += r["jp_chars"]; be[k] += edits_per_file[r["file"]]; bf[k] += 1
ks = sorted(bw)
labels = [f"{600 + 150 * k}–{600 + 150 * k + 149}" for k in ks]
dens = [1000 * be[k] / bw[k] for k in ks]
fig, ax = plt.subplots(figsize=(6.6, 2.2))
ax2 = ax.twinx()
ax2.bar(range(len(ks)), [bj[k] / 1000 for k in ks], color=LIGHT, width=0.75)
ax2.set_ylabel("Japanese characters (thousands)", color=GRAY); ax2.spines["top"].set_visible(False)
ax.set_zorder(ax2.get_zorder() + 1); ax.patch.set_visible(False)
ax.plot(range(len(ks)), dens, color=ACC, marker="o", ms=3.5, lw=1.4)
for i, d in enumerate(dens):
    ax.text(i, d + 0.18, f"{d:.1f}", ha="center", fontsize=6.3, color=ACC)
ax.set_xticks(range(len(ks))); ax.set_xticklabels(labels, rotation=0, fontsize=6.3)
ax.set_xlabel("Field-file index band (approximate game order)"); ax.set_ylabel("Revisions per 1,000 English words", color=ACC)
ax.set_ylim(0, max(dens) * 1.35)
fig.tight_layout(); fig.savefig("fig_density.pdf"); plt.close(fig)
D["bands"] = [{"band": l, "files": bf[k], "en_words": bw[k], "jp_chars": bj[k], "edits": be[k], "density": round(d, 2)} for l, k, d in zip(labels, ks, dens)]

# ---------- Figure 5: disc-2 drift ----------
sync = sorted(S["disc2_sync"], key=lambda r: -r["stale"])
fig, ax = plt.subplots(figsize=(6.6, 2.0))
xs = range(len(sync))
ax.bar(xs, [r["blocks"] for r in sync], color=LIGHT, label="boxes in file")
ax.bar(xs, [r["stale"] for r in sync], color=ACC, label="boxes still on the 1998 text")
for i, r in enumerate(sync):
    ax.text(i, r["blocks"] + 1.5, str(r["stale"]), ha="center", fontsize=6.0, color=ACC)
ax.set_xticks(list(xs)); ax.set_xticklabels([r["cd1"] for r in sync], rotation=90, fontsize=6.3)
ax.set_xlabel("Field file (disc-1 index)"); ax.set_ylabel("Text boxes"); ax.legend(frameon=False, fontsize=6.5)
fig.tight_layout(); fig.savefig("fig_drift.pdf"); plt.close(fig)
D["sync_files"] = len(sync); D["sync_stale"] = sum(r["stale"] for r in sync); D["sync_blocks"] = sum(r["blocks"] for r in sync)

R = S["review_total"]
D["edits_per_1k_words"] = 1000 * S["jp_edits_total"] / R["en_words"]
D["edits_per_10k_jp"] = 1e4 * S["jp_edits_total"] / R["jp_chars"]
D["jp_per_word"] = R["jp_chars"] / R["en_words"]
D["decoded_share"] = R["jp_chars"] / (R["jp_chars"] + R["jp_unk"])
D["files_with_edits"] = sum(1 for r in rows if edits_per_file[r["file"]])
D["files_reviewed"] = len(rows)
json.dump(D, open("derived.json", "w"), indent=1)
print(json.dumps(D, indent=1, ensure_ascii=False))
