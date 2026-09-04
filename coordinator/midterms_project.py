#!/usr/bin/env python3
"""
midterms_project.py — THE RUN. How seven distillates get made, and by what.

    python coordinator/midterms_project.py           the plan, and what is stale
    python coordinator/midterms_project.py --prompt  the derivation, verbatim
    python coordinator/midterms_project.py --pack <part>
    python coordinator/midterms_project.py --verify

RULED 2026-08-07. Self: *"Create a coordinator/midterms-project.py to capture
the above run process, including my preferred prompt - suggest improvements to
the prompt."*

**THE FIRST SEVEN WERE MADE BY HAND.** The sandbox has no route to the API, so
each distillate was produced by reading a part's sources in conversation and
writing the result. That worked, and it is not repeatable: a process that lives
in a transcript cannot be re-run, checked, or handed to a nightly. This file is
the process written down — the ordered steps, the prompt they use, and the
checks that say a run was sound.

THE RUN, in order:

    1 SURVEY    part_mid_term_manager.py -> which parts are
                stale, absent, legacy or locked,
                and how many source chars each
                has. A `locked` part is Self's
                and is skipped.
    2 PACK      per part: long_term.md (settled
                stripped), dreams.toml, every
                `## Dreamt` section newest first,
                and the remember chain — exactly
                the bytes the hash covers.
                part_relationships.toml DROPPED as
                a source 2026-08-22 (mid_term.py
                PROMPT v7).
    3 DERIVE    one call per stale part, with
                SYSTEM from part_mid_term_manager.py.
    4 WRITE     part_mid_term_manager.part_mid_term_write() stamps the
                source hash, model and prompt
                version into the front matter.
    5 VERIFY    every part reads `fresh`; block 3
                carries the distillate and not
                the raw corpus; a part with no
                distillate still has an identity.

WHAT A RUN COSTS, measured 2026-08-07 across all seven:

    input   54,479 tok   $0.109
    output   ~7,000 tok  $0.070
    total                $0.179
    saves                $0.116 per circle open

**IT SHOULD ALMOST NEVER RUN.** Staleness is a content hash, so an unchanged
day costs nothing and makes no call. The trigger is a source moving — which in
practice means a circle closed and dreaming wrote a `## Dreamt` section.
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

# ---------------------------------------------------------------- the prompt
#
# THE OPERATOR'S PREFERRED PROMPT, verbatim, as he gave it on 2026-08-07 — the second
# form, after he had seen the first output and tightened it:
#
#     "summarize actionable semantic content (as
#      defined by suitability for usefulness in a
#      future prompt context) for this text.
#      Ignore episodic narrative, affective state
#      formulas, provenance metadata, rationales,
#      derivations, self-assessments, relationship
#      histories, and all non-actionable elements.
#      Report only actionable semantic content."
#
# and the constraint he added when it became the identity path:
#
#     "I do not want to lose the semantics of prior
#      relationships or dreaming."
#
# That pair is the whole specification. `part_mid_term_manager.SYSTEM` is it, expanded into
# the operational form the derivation actually runs.
SELF_PROMPT = """\
summarize actionable semantic content (as defined by suitability for usefulness
in a future prompt context) for this text. Ignore episodic narrative, affective
state formulas, provenance metadata, rationales, derivations, self-assessments,
relationship histories, and all non-actionable elements. Report only actionable
semantic content."""


# ------------------------------------------------------- suggested improvements
#
# Moved to coordinator/improvements.toml 2026-08-09 — this was a hardcoded
# data list (status, title, why) with no code shape to it, exactly what
# sanitize.py's embedded-data check now flags. See that file for the
# LANDED / DENIED / DEFERRED semantics and every entry.
def _improvements() -> list[tuple[str, str, str]]:
    try:
        import tomllib
    except ModuleNotFoundError:                              # 3.10 and older
        import tomli as tomllib                              # type: ignore
    doc = tomllib.loads((HERE / "improvements.toml").read_text(encoding="utf-8"))
    return [(e["status"], e["title"], e["why"]) for e in doc["improvement"]]


def part_mid_term_survey() -> list[tuple[str, str, int, int]]:
    import part_mid_term_manager as MT
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    out = []
    for p in C.PART_TAGS:
        st, info = MT.part_mid_term_state_read(p)
        out.append((p, st, info["chars"], info["dreamt"]))
    return out


def part_mid_term_pack(part: str) -> str:
    """Exactly the bytes the hash covers, ready to paste into a call."""
    import part_mid_term_manager as MT
    return MT.part_mid_term_sources_read(part)["text"]


def part_mid_term_project_verify() -> int:
    """Was the run sound? Reads the tree, asserts nothing about intent.

    STALE IS NOT A FAILURE — it is a queue. The first version reported seven
    deliberately-staged parts as seven failures, which would have made a
    healthy tree look broken every time a prompt version was bumped. What
    fails is STRUCTURAL: an empty identity block, or raw corpus reaching a
    prompt. Those cannot be intended."""
    import part_mid_term_manager as MT
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    # role_context.py, IMPORTED DIRECTLY, until 2026-09-02: asked directly
    # to make prompt_build.py the one executor of all four sole assemblers.
    # C.part_context_block_render is that module's own re-export of role_context.
    # block, added the same day.
    # PRE-EXISTING BREAK, fixed 2026-08-12: load_shared() stopped returning a
    # 3-tuple (concerns/briefing both retired from it, see its own docstring)
    # some time before this file's own last edit; nothing had executed
    # part_mid_term_project_verify() since, so system_lint_verify.py's compile-only pass never caught it.
    #
    # BROKE AGAIN, fixed 2026-09-01 (audit-register.md Tier 1 #2, mirrors the
    # identical fix in circle_audit.py:668): R360 dropped build_briefing()'s
    # trailing `minimal` parameter; this call's trailing `False` was not
    # updated to match.
    #
    # BROKE A THIRD TIME, fixed 2026-09-02: shared_block()/system_blocks()'s
    # old two-step dance retired the same day (docs/CIRCLE_TYPES_DESIGN.md) —
    # role_context.part_context_block_render(p) IS Block 3's identity text directly now, the
    # first element of its own (identity, cutoff, narrowcast_chars) return.
    # core/briefing/order existed here only to feed the retired call.
    fails, pending = [], []
    for p in C.PART_TAGS:
        st, _i = MT.part_mid_term_state_read(p)
        if st in ("stale", "absent", "legacy"):
            pending.append(f"{p} ({st})")
        idt, _cutoff, _mine_len = C.part_context_block_render(p)
        if not idt.strip():
            fails.append(f"{p}: EMPTY part_identity")
        import ifs_model as IFS          # IDENTITY_END — the long_term.md boundary
        if IFS.IDENTITY_END in idt and st not in ("absent",):
            fails.append(f"{p}: '{IFS.IDENTITY_END}' reached the prompt — "
                         f"material past the identity boundary was not stripped")
    print(f"  {len(C.PART_TAGS)} part(s) checked")
    for f in fails:
        print(f"    FAIL  {f}")
    if pending:
        print(f"    pending derivation: {', '.join(pending)}")
    print("  PASS — nothing structural is broken" if not fails
          else f"  {len(fails)} FAILURE(S)")
    return 1 if fails else 0


def main() -> int:
    a = sys.argv[1:]
    if a and a[0] == "--prompt":
        import part_mid_term_manager as MT
        print("SELF PROMPT, verbatim\n" + "-" * 58)
        print(SELF_PROMPT)
        print("\nAS RUN (part_mid_term_manager.SYSTEM, prompt version "
              f"{MT.PROMPT})\n" + "-" * 58)
        print(MT.SYSTEM.replace("{budget}", str(MT.BUDGET)))
        print("\nSUGGESTED IMPROVEMENTS\n" + "-" * 58)
        import textwrap
        for status, title, why in _improvements():
            print(f"\n[{status}] {title}")
            for l in textwrap.wrap(" ".join(why.split()), 56):
                print(f"    {l}")
        return 0
    if a and a[0] == "--pack":
        print(part_mid_term_pack(a[1]))
        return 0
    if a and a[0] == "--verify":
        return part_mid_term_project_verify()

    import part_mid_term_manager as MT
    rows = part_mid_term_survey()
    print(f"  {'part':<14}{'state':<9}{'sources':>9}{'dreams':>8}")
    for p, st, c, d in rows:
        print(f"  {p:<14}{st:<9}{c:>9,}{d:>8}")
    todo = [p for p, st, _c, _d in rows if st in ("stale", "absent", "legacy")]
    tot = sum(c for _p, _s, c, _d in rows)
    print(f"\n  {len(todo)} to derive"
          + (f": {', '.join(todo)}" if todo else " — nothing to do")
          + f"\n  {tot:,} source chars, ~{tot//4:,} input tokens"
          f"\n  prompt version {MT.PROMPT}, budget {MT.BUDGET} chars each")
    if todo:
        print("\n  1 survey · 2 pack · 3 derive · 4 write · 5 verify"
              "\n  --pack <part> emits the exact source text for one call")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
