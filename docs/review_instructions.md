# Review task: Xenogears "Perfect Works" English vs. original Japanese

You are reviewing the English script of the Perfect Works (PW) fan retranslation of Xenogears
against the original Japanese game text. You PROPOSE edits as JSON; you never edit game or
script files.

## Inputs (all under E:\RE\binaries\xenogears\work)
- `bilingual2\<file>.md` — one per field file. Each `## Block N` shows the PW text (`PW:`) and
  the Japanese text of the SAME text box (`JP:`), already paired 1:1 by position. Trust the pairing.
- In `JP:`, □ is a character that could not be decoded. Main-character names come from name
  pointers and are shown as plain names. `<New>` is a page break in both languages.
- `pw_wiki\Game-Script-Style-Guide.md` — the project's style rules. Follow them.
- `pw_wiki\Script-Changes.md` — the project's deliberate name/term choices (Elehayym, Karellen,
  Myyah, Av, Breidablik, Noatun, Verus, Siebzehn, surface dweller, etc.). Never undo them, and
  never "correct" a PW term back to a romanization of the Japanese that the page rejects.

## What to propose (be conservative — PW is a deliberate, mostly good retranslation)
1. **Mistranslation**: the English states something the Japanese doesn't, or gets the meaning,
   who/what, a fact, number, relationship, cause/effect or polarity wrong.
2. **Omission**: a meaningful part of the Japanese is missing (a fact, a clue, a joke, a reason) —
   not filler, particles or interjections.
3. **Speaker**: the speaker line is wrong or missing.
4. **Typo/style**: clear typos, doubled words, missing closing quotes, style-guide violations you
   happen to see.

Do NOT propose: stylistic rewrites, tone or register changes, "more literal" renderings of lines
whose meaning is already right, localized jokes/idioms that convey the same intent, or anything
you are unsure of. Many minor-NPC lines are still the 1998 localization and are loose; leave them
unless they are actually wrong about something. If a key word in the JP is □, don't base an edit
on guessing it. Debug/test text: skip.

## Layout limits for every edited block
- At most 28 visible characters per line (count quotes and punctuation; tags count 0, `<-->` = 1,
  name pointers like `<Chu-Chu>` = the name's length). Pages that already use longer lines may keep
  their current longest length.
- At most 4 lines per page counting the speaker name line on the first page — unless that page
  already has more lines, in which case don't add lines.
- Keep every tag (`<Delay n>`, `<Opcode a b>`, `<New>`, `<-->`, name pointers) unless your edit
  is about it. You may re-break lines within a page. Only add/remove `<New>` if needed to fit, and
  say so.

## Output
Write a JSON array (UTF-8) to the path given in your task. Each item:
{"file": "0712", "block": 12, "old": "<exact substring of that block's PW text, verbatim, \n for
line breaks>", "new": "<replacement>", "category": "mistranslation|omission|speaker|typo|style",
"confidence": "high|medium", "jp": "<the Japanese it is based on>", "reason": "<1-2 sentences:
what the Japanese says and why>"}
- `old` must occur exactly once in that block's PW text; keep it as small as is unambiguous.
- Verify with Python before finishing: every `old` is found exactly once in its block (parse the
  .md), and every edited line respects the limits above.

Final message: counts by category and confidence, and the 5 most important proposals in one line
each. Don't paste the JSON.
