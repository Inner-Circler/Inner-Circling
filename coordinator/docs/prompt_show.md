# PROMPT_SHOW.PY(1)

## NAME
prompt_show.py — renders a part's (or the shared) system prompt exactly as `circle.py` would build it, without opening a circle, with placeholders marking what only a live circle would supply.

## SYNOPSIS
```
python coordinator/prompt_show.py circle              # the two shared blocks
python coordinator/prompt_show.py judge                 # judge's two per-part blocks
```

## DESCRIPTION
`prompts/<OT>/<part>.md` (written by `prompt_capture.py`) captures the exact
program a part was sent — but only for a circle that already ran. Between
circles there was previously no way to see what a part *would* be sent, so
every question about prompt content had to be answered by reading the
generator's source instead of its output. This tool exists to close that
gap, following the same 2026-08-01 principle stated in `prompt_capture.py`:
"check the emitted program, not only the inputs to the generator" —
available here before the program runs, not only after.

The four blocks are, in order, `circle_identity` and `circle_objectives`
(both SHARED across every part and cached), then `part_identity` and
`part_objectives` (both PER PART, with `part_identity` cached and
`part_objectives` not). Invoking with `circle` renders the two shared
blocks; invoking with a part name renders that part's two per-part blocks;
the other two positions are shown as placeholders in both cases, so the
reader always sees where all four slots sit even though only two are
rendered per invocation. This mirrors a specific instruction from Self
(2026-08-06) distinguishing what circle-level vs part-level invocations
should emit.

Self also drew a two-way distinction the placeholders encode by kind:
**TO BE SUPPLIED** — the circle will certainly fill this in (the working
set, the per-part briefing split, dream entries); and **MAY BE
SUPPLIED** — it depends on the evening (a mid-circle practice addition).
A third kind, **WIRED / NOT YET WIRED**, existed
2026-08-06 through 2026-08-12 to read — from `system_blocks()`'s own
source, never asserted — whether the ask fragments it audited actually
reached a part. Retired with the fragments themselves (`asks_extract.py`;
see `docs/BNF.md`).

The rendered header always names which mode (LIVE or MINIMAL) is showing
and prints the exact command to get the other one — added 2026-08-07 after
Self had to ask which he was looking at, since the two differ by an order
of magnitude (`part_identity` was 33,722 characters live vs 4,181 minimal;
that mode retired R360)
and size was the only prior tell.

## MAIN
```
read argv.
if (no arguments) then {
    print usage and return 2.
} else {
    determine target as the first non-flag argument, defaulting to
    "circle".
    if (target != "circle" and target is not a known roster part tag)
    then {
        print "no such part: <target>" and the list of valid parts;
        return 2.
    } else {
        print render(target) and return 0.
    }
}
```

## COMMAND-LINE ARGUMENTS
- `circle` (positional, default target) — render the two SHARED blocks (`circle_identity`, `circle_objectives`); the two per-part blocks are shown as placeholders.
- `<part>` (positional) — a roster part tag (e.g. `judge`); renders that part's two PER-PART blocks (`part_identity`, `part_objectives`); the two shared blocks are shown as placeholders.
- (`--minimal` retired with the practice mode, R360 2026-08-27 — the live rendering is the one rendering.)

## DEPENDENCIES
Standard library: `pathlib`, `sys`, `textwrap` (imported locally in `_box`). Sibling modules, imported locally where used: `circle` (as `C`, for `C.block_order()`, `C.PART_TAGS`, `C.load_shared()`, `C.build_briefing()`, `C.shared_block()`, `C.system_blocks()`). No third-party packages, no network access.

## EXTERNAL FILES
Read: nothing directly. Everything this file reads is read indirectly through `circle.py`'s own loader/builder functions (`load_shared()` for `process_core.md`; `build_briefing()` for circle_objectives — `issues/issue_model.md` and the live `issues/*.toml` graph), which pull in the project's objectives/core sources. The OC/open-concerns register is retired outright, 2026-08-13, and `self/issues_narrative.md` at B46, 2026-08-17; no successor source stands in either's place.

Written: none. This is a pure read-and-render tool.

## NETWORK ACCESS
None.

## HUMAN I/O
No stdin. Prints the rendered prompt (mode header, per-block headers with character counts and cache annotations, placeholder boxes, and the raw block text itself) or a usage/error message. Exit codes: 2 for no arguments or an unknown part, 0 otherwise.

## OPERATION

### _box(kind, name, body)
```
{
    Render a fixed-width (58-char) placeholder box: a rule, a
    "[[ kind · name ]]" header, the body text word-wrapped to 54
    columns and indented, and a closing rule.
}
```
Comment notes a fixed prior bug: the first version indented pre-wrapped text without re-wrapping, so any caller passing a longer interpolated note broke the fixed-width formatting; this version wraps every line itself.

### _head(pos, name, chars, note="")
Formats a block header: position, name, character count, and an optional note line, framed by `=`-rules.

### _mode(target)
```
{
    Build the mode banner: which mode is showing, what that mode means,
    and the exact command to invoke the other mode for the same target.
}
```

### render(target)
```
{
    Determine the block order for this mode via circle.block_order().
    Resolve "who" to render identity/objectives for: the target part,
    or (if target == "circle") an arbitrary first part, since the
    shared blocks are identical across parts anyway.
}
if (target is a part name and not a known roster tag) then {
    return "no such part: <target>".
} else {
    load core (process_core.md, via load_shared()) and circle_objectives
    (via build_briefing([]) — the same construction for every
    circle, differing only in how richly `## Issues`
    renders and whether the relations brief/narrative are included); if
    build the who's shared_block() and full system_blocks() exactly as
    circle.py would.
    start output with the mode banner.
    for each block position/name in order:
    determine whether it is a "part-level" block name.
    if ((target == "circle") == is_part) then {
        # this position doesn't belong to the current invocation
        emit a PLACEHOLDER box saying which command would render it.
        continue.
    } else {
        emit the block header (position, name, char count, and a
        cache annotation: "SHARED, identical... cached" /
        "PER PART · cached" / "PER PART · NOT cached — may vary
        freely"), call _notes() for any supplemental placeholder boxes
        specific to this block, then emit the actual rendered block
        text.
    }
}
return the assembled text.
```

### _notes(name, note, part)
```
if (name == "circle_identity") then {
    emit a MAY BE SUPPLIED box: a practice added mid-circle via
    /practice-add, the one shared cached block Self can change during a
    circle.
} else if (name == "circle_objectives") then {
    emit a TO BE SUPPLIED box for the working set (embedding the note
    text passed in, and explaining that this block IS the working-set
    issue projection and relations brief, built by build_briefing() —
    the same construction for every circle).
} else if (name == "part_identity") then {
    emit a TO BE SUPPLIED box for dream entries, noting dreaming
    appends to long_term.md after a circle, and that as of writing the
    three scheduled tasks are disabled so nothing changes on its own.
}
```
No branch fires for `part_objectives` — block 4 gets no supplemental placeholder box; only its header and rendered text.

## BUGS
None found beyond the one already fixed and documented in-line (the `_box` wrapping fix at line 95-96, which is history rather than an active defect).
