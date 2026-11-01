"""accept.py NN [reject idx,...] [--fix idx=new text]: copy vetted proposals into edits/jp2_NN.json"""
import json,sys
nn=sys.argv[1]; rej=set(int(x) for x in sys.argv[2].split(",") if x) if len(sys.argv)>2 else set()
P=json.load(open(f"bilingual2/proposals_{nn}.checked.json",encoding="utf-8"))
out=[e for i,e in enumerate(P) if i not in rej]
json.dump(out,open(f"edits/jp2_{nn}.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print(f"batch {nn}: accepted {len(out)} of {len(P)}")
