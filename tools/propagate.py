"""Copy each accepted edit to blocks in OTHER files whose PW text is identical to the edited block.

Only distinctive text is propagated (>= MIN_LEN visible chars) and never speaker edits: short
boxes like "..." recur everywhere with different speakers, and identical boxes inside one file
are usually deliberate variants (or a copy error the reviewer fixed in only one of them).
Writes edits/jp2_propagated.json; skips targets already covered by an accepted edit.
"""
import json,glob,re,sys,os
sys.path.insert(0,os.path.dirname(__file__))
import vet
MIN_LEN = 40
E=[e for p in sorted(glob.glob("edits/jp2_*.json")) if "propagated" not in p for e in json.load(open(p,encoding="utf-8"))]
covered={(e["file"],e["block"]) for e in E}
texts={}
for p in glob.glob(str(vet.TXT/"*.txt")):
    n=os.path.basename(p)[:-4]
    if not n.isdigit(): continue
    t=open(p,encoding="latin-1").read().replace("\r\n","\n")
    for m in vet.BLOCK.finditer(t): texts[(n,int(m.group(1)))]=m.group(2)
by_text={}
for k,v in texts.items(): by_text.setdefault(v,[]).append(k)
out=[]
for e in E:
    src=texts.get((e["file"],e["block"]))
    if src is None or e["category"]=="speaker" or len(src.strip())<MIN_LEN: continue
    for k in by_text.get(src,[]):
        if k[0]==e["file"] or k in covered: continue
        c=dict(e); c["file"],c["block"]=k; c["reason"]=f"Same text as {e['file']}#{e['block']}; same fix. "+e["reason"]
        out.append(c)
# de-duplicate identical (file,block,old)
seen=set(); res=[]
for c in out:
    key=(c["file"],c["block"],c["old"])
    if key not in seen: seen.add(key); res.append(c)
json.dump(res,open("edits/jp2_propagated.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(len(res),"propagated edits to identical blocks")
