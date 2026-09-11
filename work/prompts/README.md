# work/prompts/

**Written by `coordinator/prompt_capture.py`, from circle open through
/close. Never by hand.**

`work/prompts/<OT>/`, one directory per circle, holding (since R277,
2026-08-21):

```
Block1_circle_identity.md          shared — written ONCE per circle
Block2_circle_objectives.md        shared — written ONCE per circle
Block3_<part>_identity.md          per part
Block4_<part>_objectives.md        per part
Per_turn_<part>_<time>_<seq>.json  one per API request sent on that
                                   part's behalf — the pre-warm, each
                                   statement and its retry, the /close
                                   short_term and its retry, and since
                                   R412 (2026-08-30) the /close-time
                                   calls made for that part: its
                                   dreaming, its mid_term refresh, and
                                   a short_term rebuilt from the
                                   transcript when its own was lost
Per_turn_<kind>_<time>_<seq>.json  the /close-time calls that speak for
                                   the whole circle: `synthesis` and
                                   `coalesce` since R412/R413
                                   (2026-08-30/31), and `capsule` — the
                                   room summary dreaming reads — since
                                   2026-09-04. These have no part, so
                                   the KIND fills that slot.
manifest.json
```

A Block file IS the block's bytes — no header, no delimiter, nothing to
slice. `manifest.json` records each Block file's sha256 and size, and one
entry per turn file; a turn file's own record of blocks 1-3 is BY
REFERENCE (same bytes, by sha256) to the Block files, with block 4 inline.
`prompt_capture.py --verify` re-hashes every Block file and confirms every
turn file's block references resolve.

**This directory is empty on purpose.** It fills as circles are held.

**These files inherit the privacy of what they capture.** A prompt
embeds the part's own identity file verbatim, and a turn file carries the
part's reply plus, since R386 (2026-08-29), a summary of what the model
reasoned. Treat this directory exactly as you treat `groups/ifs/parts/`.

That last part is yours to switch off: the reasoning summary is captured
only while the `record_thinking` setting is on, which it is by default.
It is a developer setting: in a circle opened with `--dev`,
`/settings-list` shows it and `/settings-update record_thinking no` stops
it being written. The rest of the capture is not optional — it is the
record R277 exists to keep.
