# Xenogears Perfect Works — Revised English Script

A translation-only revision of the English script in the
[Xenogears Perfect Works Build](https://github.com/NoharOSP/Perfect_Works_Build) 0.11.4,
checked box by box against the original Japanese game text.

It changes **text only**: no gameplay, reward, balance or quality-of-life changes beyond
what Perfect Works 0.11.4 already contains.

By **Ricardo Sandy Aries, SS**, independent linguist.

## What changed

| | Count |
|---|---|
| Japanese characters compared with the English script | 548,421 |
| English words reviewed against the Japanese | 219,330 (15,987 text boxes, 595 field files) |
| Revisions grounded in the Japanese | 498 (348 mistranslations, 74 typos, 43 omissions, 23 style, 10 speaker) |
| Script-wide typo and style fixes | 75, plus 30 text boxes widened to fit their text |
| Menu strings fixed (items, abilities, parts) | 69 per disc |
| Disc-2 scenes that still showed the 1998 script | 20 files, 376 text boxes, now match disc 1 |

Every change, with the Japanese line and the reason, is listed in
[`docs/translation_changes.md`](docs/translation_changes.md). The method and statistics are
written up in the paper [`paper/Aries_2026_Box_by_Box_Xenogears.pdf`](paper/Aries_2026_Box_by_Box_Xenogears.pdf).

## How to patch

You need your own **unmodified Perfect Works 0.11.4** disc images, made with the official
Perfect Works patcher:

| Disc | Size (bytes) | CRC32 |
|---|---|---|
| Disc 1 | 718,681,824 | `d825ed57` |
| Disc 2 | 688,637,376 | `80a89cd2` |

**Windows:** download `XenogearsPW_EN_Revised_Patcher.exe` from the
[Releases](../../releases) page and drag a disc's `.bin` or `.cue` onto it. It checks the
disc, then writes `<name>_EN_revised.bin` and a matching `.cue` next to it. Your original
image is never changed. Do disc 1 and disc 2 one after the other.

**Any OS:** apply the `.bps` patches from the release with a BPS-capable patcher such as
Floating IPS (flips) or beat. Patched images have these CRC32 values:
disc 1 `e6c6a23e`, disc 2 `012d1d6b`.

Load the new `.cue` in your emulator. Use a hard save (memory card) rather than a save
state when switching from an older build.

## Status and limits

- The patched discs pass byte-level checks: every changed sector belongs to an edited file
  or the file table, and sector error-correction codes are regenerated and verified.
  **They have not yet been play-tested from start to finish.** Please report anything odd.
- In five disc-2 scenes (disc-1 files 1258, 1260, 1264, 1428 and 1430), Perfect Works had
  updated the event script on disc 1 only. Disc 2 now uses the disc-1 version, as the
  original Japanese game does. These are the scenes most worth testing.
- Battle text was not revised. Three short boxes added in the US release (two elevator
  menus and a Yes/No prompt) have no Japanese source and were left as they are.
- The review was SI-assisted (Synthesized Intelligence): SI systems decoded and aligned the
  Japanese, proposed revisions under a conservative policy, and helped vet and build them.
  The revision policy and acceptance criteria are the author's.

## Repository layout

| Path | Contents |
|---|---|
| `tools/` | Python tools: disc and LZSS access, text encoding, byte-level script patching, menu fixes, cross-disc mapping and sync, Japanese decoding and alignment, BPS patch creation |
| `edits/` | Every accepted edit as JSON (box, old text, new text, category, Japanese line, reason) |
| `docs/` | Change log, the same changes as a diff against the Perfect Works script sources, reviewer instructions |
| `patcher/` | Source of the Windows patcher (.NET, single file) |
| `paper/` | The paper, its LaTeX source and the scripts that compute its numbers and figures |

To build the patcher: put the two `.bps` files in `patcher/patches/` and run
`dotnet publish -c Release` in `patcher/`.

## Credits and license

- *Xenogears* © 1998 Square Co., Ltd. This project distributes no game data; the patches
  only contain the changes and must be applied to your own disc images.
- The English script revised here is the work of the Perfect Works Build team
  (NoharOSP and contributors), released under the GNU GPL v3.
- This revision is released under the **GNU General Public License v3.0**; see
  [`LICENSE`](LICENSE).
