# Xenogears Perfect Works — Ultimate Redux

**Ultimate Redux v1.0** is a translation-only revision of the English script in the
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
| Disc text Perfect Works fixed in its script but never shipped | 4 boxes (e.g. "Alice" → Arle at the Black Moon Forest campfire) |
| Title screen | Caption reads "Ultimate Redux v.1.0" |

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

**Windows:** download `XenogearsPW_Ultimate_Redux_Patcher.exe` from the
[Releases](../../releases) page and drag a disc's `.bin` or `.cue` onto it. It checks the
disc, then writes `<name>_Ultimate_Redux.bin` and a matching `.cue` next to it. Your original
image is never changed. Do disc 1 and disc 2 one after the other.

**Any OS:** apply the `.bps` patches from the release with a BPS-capable patcher such as
Floating IPS (flips) or beat. Patched images have these CRC32 values:
disc 1 `034bcccb`, disc 2 `fc5115cb`.

Load the new `.cue` in your emulator. If your player cannot open a `.cue` with its `.bin`,
as some browser-based EmulatorJS players can't, open the `.bin` directly. A real PlayStation
BIOS is needed; with an emulator's built-in BIOS replacement the game shows a black screen.
Use a hard save (memory card) rather than a save state when switching from an older build.

> **Ultimate Redux v1.0** replaces the earlier "Revised English Script" releases (v1.0.0, which did
> not boot, and v1.0.1). Version numbers start again at 1.0 with the new name. Patch from your
> stock Perfect Works 0.11.4 discs, not from an earlier revision.

## Status and limits

- Both patched discs boot in an emulator with a real BIOS to the title screen; disc 1 was
  also run through New Game and the opening. They pass byte-level checks, and
  every re-encoded compressed stream passes an exact model of the game's own decompressor.
  **They have not yet been play-tested from start to finish.** Please report anything odd.
- **Why the first release (v1.0.0) did not boot.** The game's decompressor (`SLUS_006.64` at `0x80032EB4`)
  only checks for the end of the data between groups of eight tokens, with an exact-equality
  test. Streams re-encoded by v1.0.0 ended mid-group, so the decompressor ran past its buffer
  and the game hung at startup. Since v1.0.1 the build re-encodes every changed stream so that it ends on a
  group boundary, within the distances Square's encoder uses. No file grows and nothing is
  moved on the disc. See `tools/game_lzss.py` and `tools/compact_rebuild.py`.
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
| `tools/` | Python tools: disc and LZSS access (including an aligned optimal encoder), a model of the game's decompressor, text encoding, byte-level script patching, menu fixes, cross-disc mapping and sync, in-place disc rebuild and verification, Japanese decoding and alignment, BPS patch creation, a check for script/disc drift, the title-screen caption writer, a local emulator boot-test server, a small MIPS disassembler |
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
