"""Write per-file bilingual review bundles (PW block text + decoded Japanese) for unreviewed field files."""
import sys,json,glob,os,re,collections
sys.path.insert(0,os.path.dirname(__file__))
import xgdisc, fieldtext as F, jp_learn as J
JPDISC="../Xenogears Original Japanese version/extracted/Xenogears (Japan, Asia) (Disc 1)/Xenogears (Japan, Asia) (Disc 1).bin"
T={int(k,16):v for k,v in json.load(open("jp_table_full.json",encoding="utf-8")).items()}
NAMES={0:"フェイ",1:"エリィ",2:"シタン",3:"バルト",4:"ビリー",5:"リコ",6:"エメラダ",7:"チュチュ",8:"マリア"}
def dec(b):
    out=[]
    for t in J.tokens(b):
        if t[0]=="nl": out.append("\n")
        elif t[0]=="pg": out.append("<New>\n")
        elif t[0]=="name": out.append(NAMES.get(t[1],f"<name {t[1]}>"))
        elif t[1]>>8==0xff: continue
        else: out.append(T.get(t[1],"□"))
    return "".join(out)
if __name__=="__main__":
    jp=xgdisc.Disc(JPDISC)
    DONE={608,610,612,616,618,620,622,624,626,628,630,632,634,636,640,644,648,1974}
    DEBUG={606,1156,1158,1160,1164,1166,1168,1170,1172,1174,1988,2046,2048,2050,2052,2054,2056,2058,2060,2062,2064}
    BLOCK=re.compile(r"<TextBlock (\d+) w:\w+ h:\w+>\r?\n(.*?)<End of Block>",re.S)
    st=collections.Counter()
    for p in sorted(glob.glob("pw_repo/PerfectWorks_Script/field/*.txt")):
        n=os.path.basename(p)[:-4]
        if not n.isdigit() or int(n) in DONE|DEBUG: continue
        pw=[(int(m.group(1)),m.group(2).replace("\r\n","\n")) for m in BLOCK.finditer(open(p,encoding="latin-1").read())]
        try: r=jp.read_file(int(n)); jb=F.split_section(F.text_section(r)[:F.read_field(r)[0][7]])
        except Exception: continue
        if len(jb)!=len(pw): continue
        L=[f"# Field file {n}  ({len(pw)} blocks)\n"]
        for (num,body),(dims,b) in zip(pw,jb):
            j=dec(b); st["unk"]+=j.count("□"); st["chars"]+=len(j)
            L.append(f"## Block {num}\nPW:\n{body.replace('<Close>','').rstrip()}\nJP:\n{j.rstrip()}\n")
        open(f"bilingual2/{n}.md","w",encoding="utf-8").write("\n".join(L))
    print(f"unknown {st['unk']} of {st['chars']} chars ({st['unk']/st['chars']:.2%})")
