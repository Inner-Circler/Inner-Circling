#!/usr/bin/env python3
"""
self_observation_manager.py — the SELF_OBSERVATION register. SYNTHESIS's note to
(self_observation_log.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)
Self about the CIRCLE as a working body: its pace, what it avoided, where it
went easily. Addressed to Self, about the room, never about Self.

    python coordinator/self_observation_manager.py            listing
    python coordinator/self_observation_manager.py --init     write the empty register
    python coordinator/self_observation_manager.py --show     newest entry, in full

RULED R256, 2026-08-19, closing B14's DESIGNED half. The log was
`self/self_observation_log.md` and B14 called it an INERT designed datastore —
"nothing writes them today (synthesis is off)". That premise had been false
since 2026-08-15: B3/R189 wired inter_circle.py into `/close`, and R179 had
already ruled SYNTHESIS writes this file. It is a LIVE append target, so it
converts; `self/self.md` does not, because SYNTHESIS reads it back as prompt
input and replaces it whole — a document's shape, not a register's.

    id      "SO-" DIGIT+, per-register high-water next_id, minted by the
            COORDINATOR after SYNTHESIS returns (R170's discipline).
    date    UTC ISO, microseconds. The 29 DAY-SCOPED migrated records carry
            midnight UTC of the day their own header line names — the only
            precision the .md ever held. SO-0030 carries its commit time.
    circle  the OT this entry is ABOUT. ABSENT on 29 of the 30 migrated
            records: the retired nightly ran per NIGHT over whatever circles
            had accumulated, so those entries are day-scoped, not
            circle-scoped. Every record written from here on has one.
    text    the OBSERVATION section, VERBATIM. Multi-line prose, never
            whitespace-collapsed — this is the one place circle_history_manager.py's
            template does not transfer: its `" ".join(text.split())` holds one
            paragraph, while an observation carries "Patterns:" / "Relationship
            dynamics:" / "Opportunities:" structure that flattening destroys.
    note    an annotation ABOUT the record rather than part of it. Present
            only where one is owed — the 2026-08-19 migration set it on the
            single record whose own header line had already been lost.

NO CAP, deliberately. circle_history's CAP/TARGET pair exists because SYNTHESIS
is *asked* for a bounded HISTORY (R191/R192) and the register refuses a breach;
nothing upstream bounds OBSERVATION, so a cap here would be a gate failing on
legitimate output rather than a contract being enforced. Same reasoning
self/best_practices.toml records for its own `cap: None`.

ACCUMULATE, NEVER PRUNE. At most one record per processed circle; the register
gate (docs/REGISTER_GATE_DESIGN.md) enforces that in paired mode. WRITERS: the
phase-2 driver (inter_circle.py), and circle_audit.py's --stage-synthetic,
which mints one real record to rehearse phases 6-9.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import REGISTER_CLASS as SS                                       # noqa: E402
import JOURNAL_CLASS                                               # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Rebindable for probes — test suites never write the live register.
PATH = ROOT / "self" / "self_observation_log.toml"

TABLE = "observation"
ORDER = ("id", "date", "circle", "text", "salience", "chain", "note",
         "source", "retired", "purged")
# salience + chain ADDED 2026-08-26 (R358): SYNTHESIS follows the dreaming
# model — its OBSERVATION is shown the most recent record here and may
# CONTINUE it, with self-assessed SALIENCE, exactly as a part's dreaming
# pass does with its remember chain. Records written before R358 carry
# neither field, which is the same shape remember.toml's pre-DESIGN_V2
# records have: absent, not empty.
#
# source/retired/purged ADDED for the CRUD build (the operator, 2026-09-01):
# APPENDED, same reasoning as salience above — an old record without them
# must keep dumping byte-identical. `source` is "synthesis" on every new
# SYNTHESIS record from here on, "self" on one Self added directly via
# /observation-add or /observation-continue; absent means "written before
# this field existed," not "unknown." `retired`/`purged` are present only
# when true — see self_observation_retire()/self_observation_purge() below.
#
# THESE THREE ARE ALL LIVE-WINDOW WRITES, deliberately outside the phase-2
# register gate's paired-mode scope (docs/REGISTER_GATE_DESIGN.md: "Live-
# window writes are OUT of this gate's scope... land BEFORE the phase-2
# baseline snapshot" — the same carve-out /remember, /practice-add and
# /topic-close already use). The gate only ever validates SYNTHESIS's own
# phase-2 delta against a baseline taken at /close time; a command-pane
# write completes and is committed before that baseline is ever read, so
# it is simply part of the baseline by the time phase-2 runs — never a
# delta the gate has to reason about. self_observation_retire()/self_observation_purge() below DO mutate an
# existing record, which is exactly what "accumulate, never prune" forbids
# SYNTHESIS's own automated writes from doing — the doctrine is a promise
# about the MACHINE's write path, not a blanket ban on Self ever touching
# the record by hand. No change to register_gate.py's REGISTERS spec table or
# the gate itself is needed or made.

# GENERIC, and it must stay generic: packaging/scaffold/self/README.md's own
# rule is that each delegate is byte-equivalent to the document its reader
# builds when the file is absent — which is _doc()'s output, this string
# included. The live register's own preamble is LONGER (it carries the
# 2026-08-19 migration's account of itself); _doc() reads the file whenever
# one exists, so that text persists and only a fresh install ever sees this.
_PREAMBLE = (
    "SELF_OBSERVATION -- what SYNTHESIS noticed about the CIRCLE as a "
    "working body: its pace, what it avoided, where it went easily. "
    "Addressed to Self, about the room, never about Self. One record per "
    "processed circle; accumulate, never prune. No cap: nothing upstream "
    "bounds an OBSERVATION, so this register does not refuse one either.")


def _rel() -> str:
    """PATH for printing. `PATH.relative_to(ROOT)` raises when PATH has been
    rebound to a temp file, which is exactly what the probe suite does to the
    constant above — so a module whose PATH is documented as rebindable must
    not assume PATH is still under ROOT."""
    try:
        return PATH.relative_to(ROOT).as_posix()
    except ValueError:
        return str(PATH)


# The shared LEDGER/JOURNAL core (B105, 2026-09-05 — JOURNAL_CLASS.py). LAMBDA, NOT A VALUE:
# path_fn re-reads PATH from THIS module's own globals on every call, so the probe suites' own
# rebind of `self_observation_manager.PATH` keeps working exactly as it did before this existed.
# NO CAP, deliberately — see the module docstring's own note, unchanged by this.
_JC = JOURNAL_CLASS.JournalClass(
    table=TABLE, id_prefix="SO-", cap=None,
    register="self_observation", preamble=_PREAMBLE, path_fn=lambda: PATH)


def _doc() -> dict:
    return _JC.doc()


def self_observation_read() -> list[dict]:
    return _JC.read()


def self_observation_latest_read() -> dict | None:
    return _JC.latest()


def self_observation_new_render(doc: dict, circle: str, text: str,
               note: str | None = None, salience: str | None = None,
               continues: bool = False) -> tuple[dict, dict]:
    """PURE — one new entry for the phase-2 driver.

    VERBATIM but for an outer strip. A trailing newline would survive into
    `text` and then not survive `_lit()`'s own `rstrip`, so save()'s
    round-trip guard would refuse the write; stripping here is what keeps the
    record and its rendering the same bytes.

    `salience` and `continues` are R358's dreaming-model fields:
    `continues` chains the new record to the most recent one already in
    `doc` — every SO record carries an id, so unlike remember_manager.py's chain
    there is no id-less record to step over. Row construction delegates to
    JOURNAL_CLASS.py's shared new_render() (B105); this function still owns which
    optional fields to include and under what condition."""
    text = text.strip()
    if not text:
        raise ValueError("empty OBSERVATION — nothing to record")
    fields = {"circle": circle, "text": text, "source": "synthesis"}
    if salience:
        fields["salience"] = salience
    if note:
        fields["note"] = note
    return _JC.new_render(doc, fields, chain=continues)


def self_observation_manual_render(doc: dict, text: str,
                  circle: str | None = None) -> tuple[dict, dict]:
    """PURE — one new entry Self adds directly (`/observation-add`), not
    SYNTHESIS's own write. Same id/date/append discipline as self_observation_new_render(),
    but `circle` is optional (a manual note need not be about one
    particular circle — matches the day-scoped shape the 29 migrated
    records already carry) and `source` is "self", never "synthesis". Row construction
    delegates to JOURNAL_CLASS.py's shared new_render() (B105); never chains — a manual
    note stands on its own unless /observation-continue names it explicitly."""
    text = text.strip()
    if not text:
        raise ValueError("empty OBSERVATION — nothing to record")
    fields = {"text": text, "source": "self"}
    if circle:
        fields["circle"] = circle
    return _JC.new_render(doc, fields, chain=False)


def self_observation_continue_render(doc: dict, target_id: str,
                    text: str) -> tuple[dict, dict]:
    """PURE — chains a NEW record onto `target_id` (`/observation-continue`).
    The same CONTINUES shape SYNTHESIS's own `continues=True` uses, but
    Self-authored and naming exactly what it continues rather than
    implicitly meaning "the most recent record." Never mutates
    `target_id`'s own record — that stays exactly as written, which is
    what keeps this an append, not an edit. Row construction delegates to
    JOURNAL_CLASS.py's shared new_render() (B105); the existence check on
    `target_id` stays here — new_render() trusts an explicit chain target,
    never re-validates it."""
    text = text.strip()
    if not text:
        raise ValueError("empty OBSERVATION — nothing to record")
    if not any(r.get("id") == target_id for r in doc.get(TABLE, [])):
        raise ValueError(f"{target_id} not found — nothing to continue")
    fields = {"text": text, "source": "self"}
    return _JC.new_render(doc, fields, chain=target_id)


def self_observation_retire(doc: dict, target_id: str) -> dict:
    """MUTATES the named record: `retired = True`. Soft delete — the
    record stays in the file (and in git history) untouched otherwise,
    just excluded from `/observation-list`'s default view. This is a
    live-window write like every command-pane edit to this register: the
    phase-2 gate never sees it as a delta, because it lands (and is
    committed) before any future phase-2 baseline is ever read — see the
    note above ORDER. `next_id` and every id are untouched."""
    import copy
    doc = copy.deepcopy(doc)
    for r in doc.get(TABLE, []):
        if r.get("id") == target_id:
            r["retired"] = True
            return doc
    raise ValueError(f"{target_id} not found")


def self_observation_purge(doc: dict, target_id: str) -> dict:
    """MUTATES the named record: `text` is replaced with a short
    redaction marker and `purged = True` is set. The record SHELL
    survives — id, date, circle, and (unlike self_observation_retire()) `chain`, since
    another record may point at this id and a chain target that vanished
    would be a worse defect than the content being gone. This is the one
    place this register lets content actually disappear: the operator's own
    choice (2026-09-01) over a soft-delete-only design, because this file
    is the one place in the project explicitly meant to hold material he
    may need genuinely gone (personal/PII material addressed to Self —
    see the module docstring). Irreversible in the live file; the
    pre-purge text still exists in git history at the prior commit, which
    is the same recoverability every other register in this project
    relies on for a mistaken edit — purge does not attempt to be more
    permanent than that."""
    import copy
    doc = copy.deepcopy(doc)
    for r in doc.get(TABLE, []):
        if r.get("id") == target_id:
            r["text"] = f"[purged {SS.register_now()[:10]} by Self]"
            r["purged"] = True
            return doc
    raise ValueError(f"{target_id} not found")


def self_observation_list(include_retired: bool = False) -> str:
    """`/observation-list` (bare) — numbered, positional (the same
    contract `/practice-list` keeps: the number shifts if what's shown
    changes). Retired records are hidden by default; `include_retired`
    (the `--all` flag) shows everything, retired and purged alike."""
    es = self_observation_read()
    if not include_retired:
        es = [r for r in es if not r.get("retired")]
    if not es:
        return "  (no entries)"
    out = [f"  {len(es)} entr{'y' if len(es) == 1 else 'ies'}"
           + ("" if include_retired
              else " (retired hidden — `/observation-list --all` shows them)")]
    for i, r in enumerate(es, 1):
        marker = ""
        if r.get("purged"):
            marker = "  [purged]"
        elif r.get("retired"):
            marker = "  [retired]"
        src = f"  [{r['source']}]" if r.get("source") else ""
        out.append(f"  {i:>3}. {r['id']}  {r['date'][:10]}  "
                   f"{r.get('circle', '(day-scoped)')}  "
                   f"{len(r.get('text', '')):,} chars{src}{marker}")
    return "\n".join(out)


def self_observation_show(n: int, include_retired: bool = True) -> str:
    """`/observation-list <n>` — one whole record, every field present.
    Numbered against the SAME set `self_observation_list()` would show for the same
    `include_retired` value — pass the matching flag if a caller wants
    `<n>` to line up with a prior `--all` listing."""
    es = self_observation_read()
    if not include_retired:
        es = [r for r in es if not r.get("retired")]
    if not 1 <= n <= len(es):
        return f"  {n} is not in 1..{len(es)} — /observation-list lists them"
    r = es[n - 1]
    out = [f"  {n}. of {len(es)}"]
    for k in ("id", "date", "circle", "chain", "salience", "source",
              "retired", "purged", "note"):
        v = r.get(k)
        if v:
            out.append(f"     {k:<8} {v}")
    out.append("")
    for line in (r.get("text", "") or "(empty)").splitlines() or [""]:
        out.append(f"     {line}")
    return "\n".join(out)


# --------------------------------------------------------------- commands
# Impure load/mutate/save wrappers around the pure render_*()/self_observation_retire()/
# self_observation_purge() functions above — the command-pane's entry points, matching
# remember_manager.py's add() (load, mutate, save, return the record). The
# render_*() functions stay pure because inter_circle.py's phase-2 driver
# needs to stage a candidate without writing (Transaction's own contract);
# nothing here is reachable from that path.

def self_observation_manual_add(text: str, circle: str | None = None) -> dict:
    """/observation-add <text>."""
    doc, rec = self_observation_manual_render(_doc(), text, circle)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    SS.register_write(PATH, doc, TABLE, ORDER)
    return rec


def self_observation_continue_add(target_id: str, text: str) -> dict:
    """/observation-continue <id> <text>."""
    doc, rec = self_observation_continue_render(_doc(), target_id, text)
    PATH.parent.mkdir(parents=True, exist_ok=True)
    SS.register_write(PATH, doc, TABLE, ORDER)
    return rec


def self_observation_retire_now(target_id: str) -> dict:
    """/observation-retire <id>."""
    doc = self_observation_retire(_doc(), target_id)
    SS.register_write(PATH, doc, TABLE, ORDER)
    return next(r for r in doc[TABLE] if r["id"] == target_id)


def self_observation_purge_now(target_id: str) -> dict:
    """/observation-purge <id> <id> — caller has already checked the two
    ids match before reaching here (commands.py's own confirmation step)."""
    doc = self_observation_purge(_doc(), target_id)
    SS.register_write(PATH, doc, TABLE, ORDER)
    return next(r for r in doc[TABLE] if r["id"] == target_id)


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
        rec = self_observation_latest_read()
        if rec is None:
            print("  (no entries)")
            return 0
        print(f"  {rec['id']}  {rec.get('circle', '(day-scoped)')}  "
              f"{rec['date']}")
        print(f"  {rec['text']}")
        return 0
    es = self_observation_read()
    print(f"  {len(es)} entr{'y' if len(es) == 1 else 'ies'}")
    for r in sorted(es, key=lambda x: x.get("date", "")):
        print(f"  {r['id']}  {r['date'][:10]}  "
              f"{r.get('circle', '(day-scoped)')}  {len(r.get('text', '')):,}"
              f" chars" + ("  [note]" if r.get("note") else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
