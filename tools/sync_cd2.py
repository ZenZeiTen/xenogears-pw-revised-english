"""Bring disc-2 copies of shared scenes up to date with their final disc-1 file.

Some US disc-2 field files still carry the 1998 localization (and the unmodified event
script) for scenes PW retranslated on disc 1. A disc-2 file is replaced with its disc-1
counterpart only when all of these hold:
  - same number of text blocks as the disc-1 file, and at least one block in common
    (so it is the same scene, not a lookalike);
  - the Japanese originals of the two files are byte-identical (JP disc 2 holds disc-1
    scenes shifted by JP_SHIFT), i.e. the original game used one file for both discs;
  - the US text differs.
The disc-2 file then becomes byte-identical to the final disc-1 file.

  python sync_cd2.py CD1_FINAL.bin CD2_IN.bin CD2_OUT.bin JP1.bin JP2.bin
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import jp_match as M
import xgdisc

US_SHIFT, JP_SHIFT = 5, 9          # disc-2 index = disc-1 index - shift


def main():
    cd1f, src, dst, jp1p, jp2p = sys.argv[1:6]
    if Path(src).resolve() == Path(dst).resolve():
        sys.exit("refusing to patch in place")
    u1f, u2 = xgdisc.Disc(cd1f), xgdisc.Disc(src)
    j1, j2 = xgdisc.Disc(jp1p), xgdisc.Disc(jp2p)
    plan = []
    for i2, (start, size) in enumerate(u2.entries):
        if start <= 0 or not 0 < size < 1_000_000:
            continue
        i1 = i2 + US_SHIFT
        b2, b1 = M.blocks(u2, i2), M.blocks(u1f, i1)
        if not b2 or not b1 or len(b1) != len(b2) or b1 == b2:
            continue
        if not any(x == y for x, y in zip(b1, b2)):
            continue
        ja, jb = M.blocks(j1, i1), M.blocks(j2, i1 - JP_SHIFT)
        if not ja or ja != jb:
            print(f"cd2 {i2}: differs from cd1 {i1} but JP copies differ too; left alone")
            continue
        same = sum(x == y for x, y in zip(b1, b2))
        plan.append((i2, i1, same, len(b2)))
    for d in (u2, j1, j2):
        d.f.close()
    shutil.copyfile(src, dst)
    for i2, i1, same, n in plan:
        data = u1f.read_file(i1)
        _, moved = xgdisc.write_file(dst, i2, data)
        print(f"cd2 {i2:04d} <- cd1 {i1:04d}: {n - same} of {n} blocks were stale{' (relocated)' if moved else ''}")
    chk = xgdisc.Disc(dst)
    for i2, i1, _, _ in plan:
        assert chk.read_file(i2) == u1f.read_file(i1), i2
    print(f"synced {len(plan)} disc-2 file(s)")


if __name__ == "__main__":
    main()
