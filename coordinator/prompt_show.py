#!/usr/bin/env python3
"""
prompt_show.py — render a part's system prompt WITHOUT opening a circle.

    python coordinator/prompt_show.py circle
    python coordinator/prompt_show.py <part>

RULED 2026-08-06. Self:

    "'prompt-show circle' emits blocks 1 and 2:
     output placeholder text as needed where a
     fragment is to-be or may-be supplied in a
     circle; append placeholders for blocks 3
     and 4.
     'prompt-show [part name]' emits blocks 3
     and 4: output placeholder text as needed
     where a fragment is to-be or may-be
     supplied in a circle; prefix placeholders
     for blocks 1 and 2."

WHY IT EXISTS. `work/prompts/<OT>/Block*.md` captures the emitted program,
verbatim (the R277 layout, 2026-08-21) — but only for a circle that RAN. Between circles there was no way to read
what a part would be sent, so every question about the prompt was answered by
reading the generator instead of its output. Ruled 2026-08-01, after both
defects found that day were codegen bugs invisible from the sources:
**check the emitted program, not only the inputs to the generator.** This is
that check, available before the program is run rather than after.

**THE BLOCKS ARE NAMED, AND THE NAMES ARE THE ORDER** (R109). `circle` shows
the two every part shares; a part name shows the two that are its own:

    1 circle_identity    SHARED, cached
    2 circle_objectives  SHARED, cached
    3 part_identity      PER PART, cached
    4 part_objectives    PER PART, uncached

Every block prints its real position from `prompt_build.block_order()`, so a
reorder cannot mislabel this any more than it can mislabel a capture, and the
render is SLICED FROM `prompt_build.system_blocks()` rather than reassembled — a second
implementation of the thing this file exists to inspect would be worse than
no inspection at all.

PLACEHOLDERS, on the distinction Self drew:

    TO BE    the circle will certainly supply
             it — the working set, the per-part
             briefing split, dream entries.
    MAY BE   it depends on the evening — a
             practice added mid-circle.

A third kind, WIRED / NOT YET WIRED, existed 2026-08-06 through 2026-08-12 to
read — from `system_blocks()`'s own source, never asserted — whether the ask
fragments it audited actually reached a part. Retired with the fragments
themselves (asks_extract.py, see docs/BNF.md).

**THE HEADER NAMES THE MODE, and how to get the other one.** Ruled
2026-08-07, after Self had to ask which he was looking at. The two differ by
an order of magnitude — `part_identity` is 33,722 characters live and 4,181
minimal — and the only tell was the sizes (that mode retired R360).
"""

from __future__ import annotations

import pathlib
import sys

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)

RULE = "-" * 58


def _box(kind: str, name: str, body: str) -> str:
    """A placeholder, 58 wide, never mistakable for prompt text.

    WRAPS. The first version indented whatever it was handed and emitted a
    72-character line the moment a caller interpolated a note — R019 says a
    longer line soft-wraps back to column 0, under the label column."""
    import textwrap
    out = [f"\n{RULE}", f"[[ {kind} · {name} ]]"]
    for line in body.strip().splitlines():
        for w in (textwrap.wrap(line.strip(), 54) or [""]):
            out.append(f"   {w}")
    out.append(RULE)
    return "\n".join(out)


def _head(pos: int, name: str, chars: int, note: str = "") -> str:
    return (f"\n{'=' * 58}\nBLOCK {pos} · {name} · {chars:,} chars"
            + (f"\n{note}" if note else "") + f"\n{'=' * 58}\n")


def _mode(target: str) -> str:
    """WHICH PROMPT IS THIS. Ruled 2026-08-07, after Self had to ask —
    the two modes of that day differed by an order of magnitude and
    nothing said which had been rendered. --minimal retired with the
    practice mode (R360); the banner stays, because a rendering should
    still say which question it answered."""
    return "\n".join([
        "=" * 58,
        "MODE: LIVE — the prompt a real circle sends",
        "=" * 58])


def prompt_show_render(target: str) -> str:
    """The four blocks as `circle.py` would emit them, with placeholders.

    **BUILT FROM system_blocks(), NOT REIMPLEMENTED.** The first version
    assembled its own identity and standing text, which is a second
    implementation of the thing this file exists to inspect. It now calls the
    generator and slices the result by NAME."""
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    order = C.block_order()
    part_level = {"part_identity", "part_objectives"}
    who = target if target != "circle" else next(iter(C.PART_TAGS))
    if who not in C.PART_TAGS:
        return f"  no such part: {target}"

    core = C.group_shared_read()
    briefing, unknown = C.circle_briefing_build([])
    blocks, note = C.prompt_part_assemble(who, core, briefing)
    if target == "circle":
        # `note`'s block-4 figure is ONE part's, and this view has no part.
        # It read as a global until the roster went alphabetical (R123) and
        # the exemplar changed from a part with 120 per-part characters to
        # one with none — the number moved, nothing else did.
        note += f" (block-4 figure is {who}'s; shared figures are everyone's)"

    out: list[str] = [_mode(target)]
    for pos, (name, blk) in enumerate(zip(order, blocks), 1):
        is_part = name in part_level
        if (target != "circle") != is_part:
            out.append(_box("PLACEHOLDER", f"block {pos} · {name}",
                            f"rendered by `prompt-show "
                            f"{'<part>' if is_part else 'circle'}`"))
            continue
        text = blk["text"]
        out.append(_head(pos, name, len(text),
                         ("SHARED, identical for every part · cached"
                          if not is_part and blk.get("cache_control")
                          else "PER PART · cached" if blk.get("cache_control")
                          else "PER PART · NOT cached — it may vary freely")))
        out += _notes(name, note, who)
        out.append(text.rstrip("\n"))
    return "\n".join(out)


def _notes(name: str, note: str, part: str) -> list[str]:
    """What a circle supplies, or may supply, into this block."""
    out = []
    if name == "circle_identity":
        out.append(_box("MAY BE SUPPLIED", "a practice added mid-circle", """
            /practice-add writes best_practices.toml
            immediately and this block is its
            projection. It is the one SHARED cached
            block Self can change during a circle."""))
    elif name == "circle_objectives":
        out.append(_box("TO BE SUPPLIED", "the working set", f"""
            {note}

            This block IS the working-set issue
            projection and the relations brief, built
            from the nodes chosen at circle open —
            circle_briefing_build(), the same construction for
            every circle."""))
    elif name == "part_identity":
        out.append(_box("TO BE SUPPLIED", "dream entries", """
            audit-register.md #23: this box said
            dreaming was "NOT YET BUILT... NOTHING IS
            RUNNING" for weeks after it shipped.
            Dreaming runs automatically at every live
            /close (inter_circle.circle_process) and
            writes this part's parts/<part>/remember.toml
            (2026-08-12 ruling). mid_term.md below is
            the DISTILLATE — cached, and re-derived only
            when its source hash moves (step 8), so a
            circle that just ran may have written a new
            dream entry not yet reflected in the
            mid_term.md this render shows."""))
    return out


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print("  usage: prompt_show.py circle | <part>")
        return 2
    target = next((x for x in a if not x.startswith("-")), "circle")
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    if target != "circle" and target not in C.PART_TAGS:
        print(f"  no such part: {target}")
        print(f"  parts: {', '.join(C.PART_TAGS)}")
        return 2
    print(prompt_show_render(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
