# REMEMBER(1)

## NAME

remember_manager.py — the REMEMBER register: a part's own note to its future self, private to that part.

## SYNOPSIS

    python coordinator/remember_manager.py --part <part>              every record on file
    python coordinator/remember_prompt_projection.py --part <part>    what the part is shown

(As a library: `remember_read(part)`, `remember_add(part, guard, text, ...)`, `remember_has_written(part, guard)` here; the projection — `remember_project(part)`, `remember_settled_render(part, cutoff)` for BLOCK 3 and `remember_tail_render(part, cutoff)` for BLOCK 4 — is `coordinator/remember_prompt_projection.py` since 2026-09-03 (B99 stage 17b). This page said `--project` was a flag of this file until 2026-09-04; it never was after the split, and `remember_manager.py` reads `--part` and nothing else.)

## DESCRIPTION

A part writes `[remember: "<text>"]` and those words are kept, verbatim, as its own note to its own future self. At most one per circle.

**Nothing here is ever vetted.** Unlike a proposal or a practice, a remember is not staged, approved, denied, or seen by Self at all. It never reaches the circle, another part, or the screen. It reaches exactly one place: this part's own future prompt. That privacy is the point of the register — a part needs somewhere to put something without it becoming everyone's business.

**It is normally written at close**, in the same reply that carries the part's four short-note sections. The in-round path still works, and a part that knows something now need not hold it — but the close is what the part is taught to use, because by then it has the whole circle to draw on rather than the part of it that had happened yet. One allowance covers both routes: spending it in a round leaves none at close.

**Two projections, two blocks.** What a part has remembered reaches it in two places, split at the moment its distillate was last derived:

    settled     everything on file as of that part's last identity refresh —
                BLOCK 3, alongside who the part is
    the tail    everything written since — BLOCK 4, as material that has not
                yet been folded into identity

The two headers deliberately share no literal text, so the two blocks can never be confused for one another.

**The projection is a recency window with a stated budget.** Records are rendered newest first up to a character budget, under a header that tells the part how many are on file, how many are shown and how many are out of view — so a part can decide for itself whether writing another is worth pushing an older one out of sight. **Nothing is ever dropped from the file**, only from the view, and an omitted memory returns once newer ones age past it.

**This projection is load-bearing.** The distillation stage drops a fresh single-source record by instruction, and that is harmless only because this projection carries every fresh record verbatim into the part's prompt until reinforcement consolidates it. The prompt capture asserts that invariant at every live circle.

### The fields

    date      when it was written, UTC.
    circle    the circle it was written in. Not in the original two-field
              design — added because the annotation is stripped from the
              transcript at write time (it must never reach a future prompt
              or another part), which means "has this part already used its
              one remember this circle?" cannot be answered by re-reading
              the transcript. This field is that answer, and it survives a
              resume: the same answer comes back off disk.
    text      the part's own words, truncated to a character cap. Stored
              VERBATIM and never re-wrapped — a hard wrap can land inside a
              quoted span and unwrapping does not perfectly reverse it.
    class     present only on a record migrated in from somewhere else,
              never on a part's own. Not read by the projection at all: a
              marker for a human or a future filter.
    salience  one of passing, notable, charged or resolved — PART-AUTHORED
              only, through the part's own reflective pass. The coordinator
              never scores one, by ruling: no external mechanism grades what
              a part said. Absent on older records and on a live annotation,
              both of which count as "passing" at render time. An absent or
              unreadable answer coerces to "passing" rather than failing the
              whole dreaming call over one bad tag.

## MAIN

    Read the command line.
    if (no --part was given) then { print that it is required; return 1. }
    print how many records the part has, then each one — newest first —
    with its date, its circle, and its text.
    return 0.

(The rendered projection — what the part is actually shown — is
`remember_prompt_projection.py --part <part>`'s to print, not this file's.)

## COMMAND-LINE ARGUMENTS

    --part <name>   required. The part directory name, e.g. mourner.

No other flag. (`--project` was documented here until 2026-09-04 with a
default; the module never read it after the projection left for
`remember_prompt_projection.py`, whose own `--part` prints what the part is
shown.)

## DEPENDENCIES

`REGISTER_CLASS` for load, save and timestamps; `setting_manager` for the caps; `record_paths` (`ROOT`, `SANDBOX`); the write guard arrives as the `guard` argument. The refresh cutoff that splits settled from tail is `part_mid_term_manager`'s (`mid_term` until 2026-09-03), read by `remember_prompt_projection`, not here. `pathlib`, `re`, `sys`.

## EXTERNAL FILES

    parts/<name>/remember.toml    READ by every verb; WRITTEN by remember_add().
    self/remember.toml            the same register for Self's own reflexive
                                  records — the path resolution sends "self"
                                  here rather than to a parts/ directory that
                                  does not exist.

Reads are always of the real file, even under a write guard pointed elsewhere, so "has this part already remembered this circle" cannot be answered from a scratch copy.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout; reads no input.

## OPERATION

### remember_read(part)
Every record on file for that part, unordered. Always the real file.

### remember_has_written(part, guard)
Whether this part has already used its one remember in the current circle, read back off disk by the circle field.

### remember_add(part, guard, text, cls=None, word_cap=None)
Appends one record. **It never checks the allowance itself** — the caller decides whether this is the part's one use; this only writes. Passing a word cap selects the authored ceiling, which is what makes a record the part's own words rather than a coordinator-minted summary of them.

The four below MOVED to `remember_prompt_projection.py` 2026-09-03 (B99 stage 17b) — kept here as they
were, because the design reasoning is theirs; the names are that module's.

### _window(entries)
    Walk the already-ordered records, rendering each as one bullet.
    if (adding the next one would exceed the budget) then { STOP. }
    Return the rendered text, how many were shown, and how much budget was used.

It stops rather than skipping. Skipping an over-budget newer record to go on rendering older ones would be packing the window while every header says the omitted ones are older — and recency is the priority lever here.

### remember_project(part)
The whole register as the part sees it: sorted newest first, reordered within bounds by salience and chain depth, windowed to the budget, under a header stating what is on file, what is shown, what is omitted and how much of the budget is spent.

### _split(part, cutoff)
Splits the records at the part's last identity refresh: strictly earlier is settled, everything else — including a same-second write — is the tail. With no cutoff at all, everything is tail: nothing has been distilled yet, so nothing can be called settled.

### remember_settled_render(part, cutoff) / remember_tail_render(part, cutoff)
The two projections, for BLOCK 3 and BLOCK 4 respectively, each with its own header text
(`remember_settled_project`/`remember_tail_project` select the records; the `_render` pair adds the
header).

## BUGS

None found. One thing that reads as an omission and is not: `remember_add()` does not enforce the one-per-circle allowance. That check belongs to the caller, and centralising it here would have put it below the two different call sites that need to answer it differently.
