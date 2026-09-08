#!/usr/bin/env python3
"""
circle_journal_manager.py — the CIRCLE_JOURNAL register. Block-1-facing circle identity:
one incrementally-revised, chain-linked entry per processed circle, folding the prior
CIRCLE_JOURNAL entry with this circle's own fresh CIRCLE_HISTORY entry and the high-salience
remember rows parts surfaced this circle — the same incremental-revision shape
part_mid_term_manager.py already uses one level down, at the part rather than the circle
(docs/MEMORY_DESIGN.md, "Circle-identity coalescing into Block 1"; D90/R454 named it, D92/R455
ruled B94 builds it now, ahead of the shared LEDGER/JOURNAL core, B105).

    python coordinator/circle_journal_manager.py            listing
    python coordinator/circle_journal_manager.py --init     write the empty register
    python coordinator/circle_journal_manager.py --show     newest entry, in full

circle_synthesis.py's SYNTHESIS pass calls circle_journal_new_render() at every live close
(B94 stage 4, 2026-09-04, the operator: "add it now" (R456), confirming the /review-item's
recommended answer after Claude's report of the standalone trial's findings —
work/ablations/2026-09-04/). group_context.group_context_block_render() reads the
newest entry into Block 1 (B94 stage 5, same day) — every part now sees it.

    id          "CJ-" DIGIT+, per-register high-water next_id, minted by the COORDINATOR
                after SYNTHESIS returns (R170's discipline), never the model.
    date        UTC ISO, microseconds.
    circle      the OT this entry is ABOUT.
    text        the folded prose — what this circle's identity now reads as, continuing the
                predecessor rather than restarting it. TARGET/CAP below; refused, never
                truncated, same reasoning circle_history_manager.py gives for its own pair —
                Block 1 has no use for an entry cut mid-sentence.
    chain       the predecessor CIRCLE_JOURNAL entry's id, set whenever one exists.
    provenance  segment-level origin for what `text` carries, one compact string per retained
                point — the shape docs/MEMORY_DESIGN.md asks for ("each retained point tagged
                with which circle, which part's remember row, or 'carried forward unchanged'
                produced it"), matching issues/*.toml's own per-evidence-row provenance in
                spirit. NOT a nested table: REGISTER_CLASS.register_dumps() renders a row's
                fields as scalars or lists-of-scalars only (read directly, 2026-09-04) — a
                genuine array-of-tables per row is the shared record-chain core's own job
                (PROMPT_LEDGER/PROMPT_JOURNAL, B105), deferred by D92/R455, not this register's
                to build early. Three prefixes, each a bare reference into a register that
                already carries the real record — NONE carries a MEM-/CH- id, unlike the
                stage-3 trial's own (unwired) convention: SYNTHESIS mints this circle's
                CIRCLE_JOURNAL entry in the SAME reply that produces its own fresh HISTORY and
                reads each part's fresh remember material, and none of those ids exist yet at
                that moment — the coordinator mints CJ-/CH-/MEM- ids only after parsing the
                reply (R170). `circle` (this entry's own field) plus `per_run_max: 1` on both
                parts/*/remember.toml and this register together make a bare reference
                unambiguous without an id:
                    "<part_dir>"            a fresh remember row THIS circle, from that part —
                                             at most one per part per circle, so the part's
                                             directory name alone identifies it
                    "history"               this circle's own fresh CIRCLE_HISTORY entry —
                                             `circle` says which
                    "carried:CJ-nnnn"       the predecessor entry — ITS id already exists
                                             (read before the call), so it is cited by id
                Optional — an entry with none is legal (e.g. the first entry a fresh install
                or a hand-rehearsed row ever gets), same as `chain`'s own absence on a first
                entry.

CAP/TARGET are this register's OWN sizing, not circle_history's imported (register_gate.py's
own rule for why a literal here would be a second source of truth applies the same way in
reverse: these numbers answer a different question). CIRCLE_JOURNAL reaches Block 1 — shared,
cached, paid on every part's prompt, every circle — while circle_history.toml reaches no
prompt block at all. A folded, deduplicated distillate should also run smaller than a raw
HISTORY entry by construction, not merely be capped the same. NOT MEASURED AGAINST MANY
CIRCLES YET, but stage 3's standalone trial (work/ablations/2026-09-04/, n=2 circles) is a
real first data point in favor: both circle-2 model-arm entries landed under both numbers
(3,519 / 3,440 chars) even with a predecessor folded in, no sign yet of unbounded growth.
Still setting-overridable, exactly as circle_synthesis.SYNTH_MAX_TOKENS is, and worth
revisiting once more than two circles exist to measure against.

ACCUMULATE, NEVER PRUNE. One record per processed circle at most; the register gate
(docs/REGISTER_GATE_DESIGN.md) enforces exactly that in paired mode. WRITER: the phase-2
driver (circle_synthesis.py's SYNTHESIS pass, staged by inter_circle.py, B94 stage 4) — this
module's own render function stays PURE, matching circle_history_manager.py and
circle_observation_manager.py's shape, so a caller can
stage a candidate without writing (Transaction's own contract).
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import REGISTER_CLASS as SS                                       # noqa: E402
import record_paths as _RP                                         # noqa: E402
import setting_manager as SET                                     # noqa: E402
import JOURNAL_CLASS                                               # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Rebindable for probes — test suites never write the live register.
PATH = _RP.CIRCLES_DIR / "circle_journal.toml"


@_RP.group_follow
def _path_rebind() -> None:
    """The CURRENT group's register — B117 stage 4 (2026-09-07)."""
    global PATH
    PATH = _RP.CIRCLES_DIR / "circle_journal.toml"

TABLE = "journal"
ORDER = ("id", "date", "circle", "text", "chain", "provenance")

# Own sizing — see the module docstring. Setting-overridable so stage 3's trial can move
# these without a code change; reasoned defaults until then, tighter than circle_history's
# 8000/7200 because this register is a folded, deduplicated distillate of raw HISTORY text,
# and because — unlike circle_history — every byte here is paid on every part's cached Block 1.
CAP = SET.setting_value_read("circle_journal_cap", 4000)
TARGET = SET.setting_value_read("circle_journal_target", 3600)

_PREAMBLE = (
    "CIRCLE_JOURNAL -- one incrementally-revised, chain-linked entry per processed circle: "
    "the prior entry folded with this circle's own fresh CIRCLE_HISTORY text and the "
    "high-salience remember rows parts surfaced, deduplicated. Reaches Block 1, shared and "
    "cached across every part. Accumulate, never prune; the register gate enforces "
    "append-only.")


def _rel() -> str:
    """PATH for printing. `PATH.relative_to(ROOT)` raises when PATH has been
    rebound to a temp file, which is exactly what the probe suite does to the
    constant above — so a module whose PATH is documented as rebindable must
    not assume PATH is still under ROOT. All three journal managers carry this
    fix now; circle_history_manager.py was the last, at B105."""
    try:
        return PATH.relative_to(ROOT).as_posix()
    except ValueError:
        return str(PATH)


# The shared LEDGER/JOURNAL core (B105, 2026-09-05 — JOURNAL_CLASS.py). LAMBDA, NOT A VALUE:
# path_fn re-reads PATH from THIS module's own globals on every call, so the probe suites' own
# rebind of `circle_journal_manager.PATH` keeps working exactly as it did before this existed.
_JC = JOURNAL_CLASS.JournalClass(
    table=TABLE, id_prefix="CJ-", cap=CAP, cap_label="CIRCLE_JOURNAL",
    register="circle_journal", preamble=_PREAMBLE, path_fn=lambda: PATH)


def _doc() -> dict:
    return _JC.doc()


def circle_journal_read() -> list[dict]:
    return _JC.read()


def circle_journal_latest_read() -> dict | None:
    return _JC.latest()


def circle_journal_new_render(doc: dict, circle: str, text: str,
                  provenance: list[str] | None = None) -> tuple[dict, dict]:
    """PURE — one new entry for the phase-2 driver, chained to the newest prior entry when
    one exists. REFUSES oversize (ValueError) rather than truncating; the caller reports and
    the prior entry stays current, same discipline as circle_history_new_render(). Row
    construction delegates to JOURNAL_CLASS.py's shared new_render() (B105); this module still
    owns its own text normalization and whether `provenance` is included."""
    text = " ".join(text.split())
    fields = {"circle": circle, "text": text}
    if provenance:
        fields["provenance"] = list(provenance)
    return _JC.new_render(doc, fields, chain=True)


def main() -> int:
    a = sys.argv[1:]
    if "--init" in a:
        if PATH.is_file():
            print(f"  {_rel()} already exists — untouched")
            return 0
        SS.register_write(PATH, _doc(), TABLE, ORDER)
        print(f"  wrote {_rel()} (empty register)")
        return 0
    if "--show" in a:
        rec = circle_journal_latest_read()
        if rec is None:
            print("  (no entries)")
            return 0
        print(f"  {rec['id']}  {rec.get('circle', '?')}  {rec['date']}")
        print(f"  {rec['text']}")
        if rec.get("provenance"):
            print("  provenance: " + ", ".join(rec["provenance"]))
        return 0
    es = circle_journal_read()
    print(f"  {len(es)} entr{'y' if len(es) == 1 else 'ies'}")
    for r in sorted(es, key=lambda x: x.get("date", "")):
        print(f"  {r['id']}  {r.get('circle', '?')}"
              + (f"  chain->{r['chain']}" if r.get("chain") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
