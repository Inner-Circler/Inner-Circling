#!/usr/bin/env python3
"""
register_gate.py — the REGISTER gate: the one gate every write to the record passes.

MOVED OUT OF record_model.py, 2026-09-03 (cohesion re-homing stage 9, B99; the name is
docs/REGISTER_GATE_DESIGN.md's own). record_model.py keeps the structural MODEL of the memory
files — Finding, the primitives, entries, the long_term/headed/append-only comparisons — and
this module reads it as M. Every function below is the verbatim body it had there; only the
file moved. What lives here:

RENAMED AT THE MOVE (R436, R442 — 2026-09-03), the class word first, the bodies untouched:

    compare_trees        -> record_tree_compare     the RECORD's tree, baseline vs candidate
    selfcheck_tree       -> record_tree_verify      the same, single tree
    compare_register     -> register_compare        one TOML register, paired
    check_register_file  -> register_verify         one TOML register, single
    summarise, REGISTERS and every _private name    unchanged (summarise carries no class word:
                                                    the residue sweep's, B99 stage 19)

    _tree_files, record_tree_compare, record_tree_verify   the two drivers: baseline vs candidate at every
                                                 live /close (transaction.validate), and the
                                                 single-tree self-check (circle_audit --selfcheck)
    REGISTERS and the _*_cap/_*_order readers     the TOML arm's spec table — caps and orders
                                                 IMPORTED from each register's own module; a
                                                 literal copy only when that import fails
    register_verify, register_compare        the single-tree and paired register checks
    summarise                                    (FAIL, WARN, OK) counts over findings

It writes nothing, anywhere, ever. Read-only by construction, like the model it judges with.

USE
    import register_gate as RG
    findings = RG.record_tree_compare(baseline_dir, candidate_dir)
"""

from __future__ import annotations

import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import record_model as M                                          # noqa: E402  the file model
import record_paths as _RP                                         # noqa: E402
import proposal_manager as PR                                         # noqa: E402  REGISTERS reads ORDER
import practice_manager as PM                                  # noqa: E402  REGISTERS reads ORDER


# ---------------------------------------------------------------- tree compare
def _tree_files(root: pathlib.Path) -> list[pathlib.Path]:
    # relationships.md REMOVED 2026-08-15: converted to per-part
    # part_relationships.toml (coordinator/part_relationships.py, renamed
    # from relationships.py/.toml 2026-08-17, R220) and retired.
    # The gate does not cover the TOML successor — that is B37's already
    # open "no gate exists for any TOML register today", now one file
    # wider, not a new gap invented here.
    out = [_RP.record_dir(root, "parts") / p / "long_term.md" for p in M.PARTS]
    out += [_RP.record_dir(root, "self") / f for f in M.SELF_FILES]
    return out


def record_tree_compare(baseline: pathlib.Path, candidate: pathlib.Path,
                  today: str | None = None,
                  first_synthesis: bool = False) -> list[M.Finding]:
    """Every invariant in NIGHTLY_DESIGN §4, baseline vs candidate.

    `first_synthesis` — R348, the operator's
    "(a)" (2026-08-25): when NOTHING has ever been processed in this tree
    (inter_circle.circle_synthesis_is_first() is the one caller and the one
    test), self.md's shrink tolerance is waived — what the first synthesis
    replaces is the shipped seed, not a record this gate is protecting.
    Seen in the fresh install Inner-Circling-2026-08-25_1309, circle
    _1414: a valid same-headings replacement, 1,742 -> 1,115 bytes,
    refused the whole staged batch. The waiver is REPORTED (an OK
    FIRST-SYNTHESIS finding), never silent, and every later run keeps the
    full tolerance. Default False, so every other caller is unchanged."""
    today = today or datetime.date.today().isoformat()
    synth_ok = re.compile(rf"^## Dream synthesis {re.escape(today)}$")
    out: list[M.Finding] = []

    for bp in _tree_files(baseline):
        rel = bp.relative_to(baseline).as_posix()
        cp = candidate / rel
        bdata, cdata = M.record_bytes_read(bp), M.record_bytes_read(cp)
        if bdata is None:
            out.append(M._f("WARN", "NO-BASELINE", rel, "not in the baseline; skipped"))
            continue
        if cdata is None:
            out.append(M._f("FAIL", "MISSING", rel, "in baseline, absent from candidate"))
            continue
        ctext, cf = M.record_file_verify(rel, cdata)
        out += cf
        btext, _ = M.record_file_verify(rel, bdata)
        if ctext is None or btext is None:
            continue
        be, ce = M.record_line_endings_read(bdata), M.record_line_endings_read(cdata)
        if be != ce:
            out.append(M._f("FAIL", "LINE-ENDINGS", rel,
                          f"line endings changed {be} -> {ce}. Nothing in this "
                          f"pipeline rewrites line endings on purpose; the usual "
                          f"cause is git core.autocrlf converting on checkout, "
                          f"which breaks every sha256 and byte-identical check. "
                          f"See .gitattributes."))
        elif ce == "mixed":
            out.append(M._f("WARN", "LINE-ENDINGS", rel, "mixed CRLF and LF"))
        if bdata == cdata:
            out.append(M._f("OK", "UNCHANGED", rel, "byte-identical"))
            continue

        name = bp.name
        if name == "long_term.md":
            settling = any(f.code == "SETTLED" for f in
                           M.record_long_term_compare(rel, btext, ctext))
            out += M.record_size_verify(rel, bdata, cdata, allow_shrink=settling)
            out += M.record_long_term_compare(rel, btext, ctext)
        else:
            # M.SELF_FILES holds ONE member today: self.md, "structured".
            # "rewritten" went with circle_briefing.md (2026-08-11) and
            # "append_only" with narrative_arc.md (2026-08-24, the phantom
            # -- see M.SELF_FILES above). The append_only arm is KEPT rather
            # than deleted: it is the byte-prefix rule itself, the cheapest
            # guard this file has against a rewrite-instead-of-append, and
            # the next self/ document to need it should find it here rather
            # than re-derive it. It is UNREACHED while M.SELF_FILES has one
            # member, and no probe exercises M.record_append_only_compare() today --
            # so a future member must not assume this arm still works
            # without checking it.
            kind = M.SELF_FILES[name]
            out += M.record_size_verify(rel, bdata, cdata, allow_shrink=first_synthesis)
            if (first_synthesis and len(bdata)
                    and (len(cdata) - len(bdata)) / len(bdata)
                    < -M.SHRINK_TOLERANCE):
                out.append(M._f("OK", "FIRST-SYNTHESIS", rel,
                              "shrink past tolerance ACCEPTED — nothing has "
                              "ever been processed in this tree, so what this "
                              "replaces is the shipped seed, not a record "
                              "(R348)"))
            if kind == "append_only":
                out += M.record_append_only_compare(rel, btext, ctext)
            else:
                out += M.record_headed_compare(rel, btext, ctext, allow_new=synth_ok)

    # TOML registers — the PAIRED half of the register gate
    # (docs/REGISTER_GATE_DESIGN.md, R188). Iterated over BOTH trees so a
    # register staged into existence (circle_history's first run) is judged
    # with an empty baseline rather than skipped; a register absent from the
    # candidate was not part of the run and is skipped by register_compare.
    seen: set[str] = set()
    for tree in (baseline, candidate):
        for p, spec in _register_paths(tree):
            rel = p.relative_to(tree).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            out += register_compare(rel, M.record_bytes_read(baseline / rel),
                                    M.record_bytes_read(candidate / rel), spec)

    # narrative_<date>.md must be new, never an overwrite. Judge that on what the
    # run actually WRITES, not on what happens to exist: a run that stages no
    # narrative is unaffected by one already being there, and flagging it turns a
    # second look at an already-dreamed day into a phantom failure.
    nd = f"narrative_{today}.md"
    # a snapshot mirrors its tree's own shape: the group's under the real ROOT, flat in a probe
    self_rel = next((r for r in (_RP.record_rel("self"), "self")
                     if (baseline / r).is_dir() or (candidate / r).is_dir()),
                    _RP.record_rel("self"))
    bn, cn = baseline / self_rel / nd, candidate / self_rel / nd
    bdata, cdata = M.record_bytes_read(bn), M.record_bytes_read(cn)
    if cdata is None:
        pass                                   # this run writes no narrative
    elif bdata is None:
        t, cf = M.record_file_verify(f"self/{nd}", cdata)
        out += cf or [M._f("OK", "NARRATIVE-NEW", f"self/{nd}", "written")]
    elif bdata != cdata:
        out.append(M._f("FAIL", "NARRATIVE-OVERWRITE", f"self/{nd}",
                      f"already exists ({len(bdata):,} B) and this run would "
                      f"replace it ({len(cdata):,} B). One narrative per day; a "
                      f"second nightly for the same date must not clobber the "
                      f"first."))
    return out


def record_tree_verify(root: pathlib.Path) -> list[M.Finding]:
    """No baseline: prove the parser understands the real files, and that they
    satisfy the invariants that do not need a comparison. Run this first."""
    out: list[M.Finding] = []
    # TOML registers — the single-tree half of the register gate
    # (docs/REGISTER_GATE_DESIGN.md, R188).
    for p, spec in _register_paths(root):
        out += register_verify(p.relative_to(root).as_posix(),
                                   M.record_bytes_read(p), spec)
    for p in _tree_files(root):
        rel = p.relative_to(root).as_posix()
        data = M.record_bytes_read(p)
        text, cf = M.record_file_verify(rel, data)
        out += cf
        if text is None:
            continue
        if (le := M.record_line_endings_read(data)) == "mixed":
            out.append(M._f("WARN", "LINE-ENDINGS", rel,
                          "mixed CRLF and LF in one file"))
        elif le == "crlf":
            out.append(M._f("WARN", "LINE-ENDINGS", rel,
                          "CRLF; the rest of the tree is LF"))
        if p.name == "long_term.md":
            lt = M.LongTerm(text)
            if lt.preamble is None:
                out.append(M._f("FAIL", "NO-DREAM-SECTION", rel,
                              f"no '{M.IDENTITY_END}' delimiter"))
                continue
            for line in lt.unparsed:
                out.append(M._f("FAIL", "UNPARSED-ENTRY", rel,
                              f"'### ' line does not match the entry template and "
                              f"is invisible to every count and comparison: "
                              f"{line[:90]!r}"))
            dupes = [e.id for e in lt.dreams + lt.settled
                     if [x.id for x in lt.dreams + lt.settled].count(e.id) > 1]
            if dupes:
                out.append(M._f("FAIL", "DUPLICATE-ENTRY", rel,
                              f"entry id(s) appear twice: {sorted(set(dupes))}"))
            for e in lt.dreams:
                if e.is_tombstone:
                    out.append(M._f("WARN", "TOMBSTONE", rel,
                                  f"'{e.id}' has a header but no body -- the entry "
                                  f"itself was lost; only the marker remains"))
                    continue
                anchor, src = e.recency
                if src == "entry-date":
                    out.append(M._f("OK", "RECENCY-DERIVED", rel,
                                  f"'{e.id}' has no *Last mentioned:*; recency "
                                  f"anchored to its own dream date {anchor}"))
                if e.is_review and "review flagged" not in e.fields:
                    out.append(M._f("WARN", "NO-FIELD", rel,
                                  f"'{e.id}' is [review] but has no *Review flagged:*"))
            for e in lt.settled:
                if "settled" not in e.fields:
                    out.append(M._f("WARN", "NO-FIELD", rel,
                                  f"settled '{e.id}' has no *Settled:* field"))
            out.append(M._f("OK", "PARSED", rel,
                          f"{len(lt.headings)} sections, {len(lt.dreams)} dream + "
                          f"{len(lt.settled)} settled entries, "
                          f"{len([e for e in lt.dreams if e.is_review])} [review]"))
        else:
            out.append(M._f("OK", "PARSED", rel, f"{len(M.record_headings_read(text))} sections"))
    return out


# ---------------------------------------------------------- register gate
# docs/REGISTER_GATE_DESIGN.md, approved R188. The TOML arm of the ONE gate:
# record_tree_compare() gains register rows, record_tree_verify() gains their
# single-tree half. "Append-only, mutable-fields-only" for a TOML register
# is defined HERE, as data, not as a regex:
#
#   PAIRED (baseline vs candidate — the phase-2 transaction gate)
#     ZERO mutations, every register: candidate records[:len(baseline)]
#     must equal baseline's records exactly (value equality), the [doc]
#     preamble and every non-table scalar except a declared monotonic
#     counter must be untouched, and both sides must be dumps()
#     FIXED-POINTS — a baseline that does not re-render byte-identically
#     was hand-edited without a re-save, and that is a FINDING, never a
#     silent fallback to value comparison. The tail is then judged:
#     count, cap, id sequence, date order, chain target, state vocabulary.
#   SINGLE-TREE (selfcheck — no baseline, no intent)
#     parse, id uniqueness and prefix, ids below next_id, date order,
#     state vocabulary, caps. FIELD-CONDITIONAL: a check activates only
#     where the field exists (today's remember.toml has no id/chain;
#     circle_history may not exist yet). Fixed-point failures are WARN
#     here (a hand-edit indicator) and FAIL in paired mode (the
#     precondition). FROZEN is paired-only — no reference bytes exist
#     single-tree, and git already watches the file.
#
# The driver side (intent validation, writer-scope matrix) lives with the
# phase-2 driver; this arm never trusts intents — it judges the trees.
def _ch_cap() -> int:
    """circle_history.CAP, imported rather than duplicated. Late import: this
    module is imported by circle_history's own dependency chain, so a
    top-level import would be circular. Falls back to the ruled value only if
    the module cannot be loaded at all, and says so rather than guessing
    silently."""
    try:
        import circle_history_manager as _CH
        return _CH.CAP
    except Exception:
        return 8000        # R191's ruled value; see circle_history_manager.CAP


def _tp_cap() -> int:
    """topics.CAP, IMPORTED NOT COPIED — the last row in REGISTERS that still
    held a literal, while the dict's own comments prescribe the opposite twice
    (see _ch_cap below, whose row said 600 for weeks after R191 made it 8000,
    and the gate then enforced the stale number against correct records).

    Late import for the same reason _ch_cap is late: that module imports
    REGISTER_CLASS."""
    import topic_manager as _TP
    return _TP.CAP


def _tp_order() -> tuple[str, ...]:
    """topic_manager.ORDER, imported rather than duplicated — the same rule as _tp_cap()
    above, applied when B116 (R465) added `amended` to the row. Late for the same reason."""
    import topic_manager as _TP
    return _TP.ORDER


def _mem_cap() -> int:
    """remember.GATE_CHAR_CEILING, imported rather than duplicated — the rule
    _ch_cap() below already writes down, applied to the register that needed
    it and did not have it.

    THIS ROW SAID 600 AND WAS WRONG FROM R255 (2026-08-19). 600 is
    RECORD_CAP, the COORDINATOR's ceiling; a PART's own authored memory may
    run to 1000 WORDS, and this gate measures characters. It refused the
    first live close that produced one — 2026-08-20, all seven parts, after
    dreaming had already written the live tree — which is exactly the
    failure the circle_history row was rewritten to prevent.

    Late import for the same reason _ch_cap() is late."""
    try:
        import remember_manager as _RM
        return _RM.GATE_CHAR_CEILING
    except Exception:
        return 12000       # see remember_manager.GATE_CHAR_CEILING for the reasoning


def _mem_order() -> tuple[str, ...]:
    """remember_manager.ORDER, imported rather than duplicated — the same rule _so_order()
    below already writes down, applied to the register that most needed it.

    IT MUST EQUAL remember_manager.ORDER EXACTLY: _fixed_point() re-renders a candidate with
    this tuple, so a field the gate did not know to render back fails every staged DREAMING
    record as NOT-FIXED-POINT. A literal copy carried that requirement as a comment and no
    probe checked it; test_register_gate.py asserts the equality now.

    Late import for the same reason _ch_cap() is late."""
    try:
        import remember_manager as _RM
        return _RM.ORDER
    except Exception:
        return ("id", "date", "circle", "text", "chain", "class", "salience")


def _so_order() -> tuple[str, ...]:
    """circle_observation_log.ORDER, imported rather than duplicated. Late for
    the same reason _ch_cap() is late — that module imports REGISTER_CLASS,
    which this module's own dependency chain already pulls in.

    The fallback below is a copy, read only when that import fails. test_register_gate.py
    forces the failure and holds the copy equal to ORDER — this one, _mem_order()'s and
    _cj_order()'s."""
    try:
        import circle_observation_manager as _CO
        return _CO.ORDER
    except Exception:
        return ("id", "date", "circle", "text", "salience", "chain", "note",
                "source", "retired", "purged")


def _cj_cap() -> int:
    """circle_journal.CAP, imported rather than duplicated — same rule as
    _ch_cap() above, applied to B94's own register (2026-09-04). Late
    import for the same circularity reason."""
    try:
        import circle_journal_manager as _CJ
        return _CJ.CAP
    except Exception:
        return 4000        # circle_journal_manager.CAP's own reasoned default


def _cj_order() -> tuple[str, ...]:
    """circle_journal.ORDER, imported rather than duplicated — same rule as
    _so_order() above. Late for the same reason _cj_cap() is late."""
    try:
        import circle_journal_manager as _CJ
        return _CJ.ORDER
    except Exception:
        return ("id", "date", "circle", "text", "chain", "provenance")


REGISTERS: dict[str, dict] = {
    "parts/*/remember.toml": {
        "table": "remember",
        # ORDER AND CAP ARE BOTH IMPORTED, NOT COPIED — see _mem_order() and
        # _mem_cap(), and the circle_history row below, which learned it first.
        "order": _mem_order(),
        "id_prefix": "MEM-", "cap": _mem_cap(), "per_run_max": 1,
        "preamble": False, "chain": True,
    },
    # "parts/*/part_relationships.toml" RETIRED 2026-08-22 — the register,
    # its module (coordinator/part_relationships.py) and the seven files are
    # deleted (rulings/R309.toml, the entry after R308). It was the only register with
    # cap_exempt_first=True; that flag stays generic (see
    # register_verify()'s `start = 1 if spec.get("cap_exempt_first")`)
    # for any future register to opt into, even with no current user.
    "self/topics.toml": {
        "table": "topic",
        # ORDER IS IMPORTED, NOT COPIED (the rule the best_practices row below writes down),
        # since B116 added `amended` (R465, 2026-09-07). /topic-update is a hand edit between
        # circles — out of this gate's scope by design; it never widens the gate.
        "order": _tp_order(),
        "id_prefix": "TP-", "cap": _tp_cap(), "per_run_max": None,
        "preamble": True,
        "state_values": ("open",), "state_prefixes": ("closed by Self ",),
        "new_state": "open",
    },
    "self/proposals.toml": {
        "table": "proposal",
        # ORDER IS IMPORTED, NOT COPIED — see the circle_history entry
        # below for why a literal here would be a second source of truth.
        "order": PR.ORDER,
        # No file exists yet — no [propose ...] has ever converged to a
        # real row (R202, 2026-08-16). preamble=False: proposals.py's
        # _doc() writes {register, next_id, proposal}, no [doc] block —
        # unlike best_practices.toml, this register never had one.
        "id_prefix": "P-", "cap": None, "per_run_max": None,
        "preamble": False, "new_state": "proposed",
        # Same state shape as best_practices.toml (PROPOSE_CLASS.py is
        # the shared base for both): state_values/state_prefixes omitted
        # for the same reason that entry omits them — accepted/denied
        # carry free-form ISO timestamps, not a fixed vocabulary.
    },
    # self/ since 2026-08-16 — Self's memory/ ruling returned the
    # register to the user-owned record (it was coordinator/ from
    # 2026-08-11).
    "self/best_practices.toml": {
        "table": "practice",
        # ORDER IS IMPORTED, NOT COPIED — the same rule this dict already
        # wrote down for circle_history's cap, applied to itself
        # (2026-08-16, the phase-2 review's finding #2): a literal here
        # was a second source of truth for a tuple practice_manager
        # owns, and the proposals entry below had already shown the
        # correct form.
        "order": PM.ORDER,
        # A phase-2 write may STAGE a proposal, never rule on one — every
        # new row arrives state="proposed". No cap: a practice row's title
        # is Self's or a part's own words, ruled unlimited (R023).
        "id_prefix": "BP-", "cap": None, "per_run_max": None,
        "preamble": True, "new_state": "proposed",
        # /practice-update (B116, R465) is a hand edit between circles — out of this gate's
        # scope by design ("the gate does not police humans"); it never widens the gate.
        # _sync_tally keeps an "**Entries: N**" count inside this file's
        # own preamble — the one register whose [doc] legitimately moves
        # when a row lands. Everything else about it stays immutable;
        # the tally is that module's own truth-keeping, not an edit.
        "preamble_tally": True,
        # single-tree state sanity intentionally omitted: accepted/denied
        # states carry free-form timestamps and R-prose; parse + ids only.
    },
    "circles/circle_history.toml": {
        "table": "history",
        "order": ("id", "date", "circle", "text", "chain"),
        # CAP IS IMPORTED, NOT COPIED. This row said 600 until 2026-08-15 and
        # went on saying it after R191 raised circle_history_manager.CAP to 8000 —
        # two places asserting the same number, one of them stale, which the
        # gate then enforced against real records that were correct. A
        # literal here is a second source of truth for a value that already
        # has an owner.
        "id_prefix": "CH-", "cap": _ch_cap(), "per_run_max": 1,
        "preamble": True, "chain": True,
    },
    "circles/circle_observation_log.toml": {
        "table": "observation",
        # ORDER IS IMPORTED, NOT COPIED — the rule this dict already wrote
        # down for circle_history's cap and best_practices' order.
        "order": _so_order(),
        # NO CAP: nothing upstream bounds an OBSERVATION section, so a cap
        # here would fail on legitimate output rather than enforce a
        # contract. See circle_observation_manager.py's own note.
        # TWO PREFIXES, AND ONLY HERE — R481 (2026-09-07): CIRCLE_OBSERVATION became
        # CIRCLE_OBSERVATION and the id change is FORWARD-ONLY, so SO-0001..SO-0031 stay
        # as written and CO- is minted from the next close. The FIRST entry is what the
        # manager mints; the rest are accepted spellings. A single string still works
        # everywhere else and is the shape every other register uses.
        "id_prefix": ("CO-", "SO-"), "cap": None, "per_run_max": 1,
        "preamble": True,
    },
    "circles/circle_journal.toml": {
        "table": "journal",
        # ORDER IS IMPORTED, NOT COPIED — the rule this dict already wrote
        # down for circle_history's cap and best_practices' order.
        "order": _cj_order(),
        # CAP IS IMPORTED, NOT COPIED — see _cj_cap(). B94, 2026-09-04:
        # not circle_history's CAP — CIRCLE_JOURNAL reaches Block 1, paid
        # on every part's prompt, and should run smaller as a folded
        # distillate, not merely be capped the same as a raw entry.
        "id_prefix": "CJ-", "cap": _cj_cap(), "per_run_max": 1,
        "preamble": True, "chain": True,
    },
    "parts/*/dreams.toml": {
        # READ-ONLY since R178 — nothing writes it. Any paired delta is a
        # defect. Excluded from single-tree checks: its schema predates
        # this gate and part_mid_term_manager.py is its reader of record (recency.py,
        # a second, unreachable reader, was removed 2026-09-01 — D-d).
        "frozen": True,
    },
}


def _register_paths(root: pathlib.Path) -> list[tuple[pathlib.Path, dict]]:
    """(path, spec) for every register file matching REGISTERS under root —
    existing files only; an absent register (circle_history before its
    first run) is simply not iterated."""
    out = []
    for pat, spec in REGISTERS.items():
        top, _sep, rest = pat.partition("/")
        for p in sorted(_RP.record_dir(root, top).glob(rest)):
            if p.is_file():
                out.append((p, spec))
    return out


def _load_register(data: bytes) -> tuple[dict | None, str | None]:
    try:
        import tomllib
    except ModuleNotFoundError:                                # 3.10
        import tomli as tomllib                                # type: ignore
    try:
        return tomllib.loads(data.decode("utf-8")), None
    except Exception as e:                                     # parse = gate
        return None, f"{type(e).__name__}: {e}"


def _fixed_point(data: bytes, spec: dict) -> bool:
    """dumps(load(bytes)) == bytes — true only for files REGISTER_CLASS wrote."""
    import REGISTER_CLASS as SS
    doc, err = _load_register(data)
    if doc is None:
        return False
    try:
        return SS.register_dumps(doc, spec["table"], spec["order"]).encode("utf-8") \
            == data
    except Exception:
        return False


def _prefixes(prefix) -> tuple:
    """A spec's id_prefix as a tuple. A single string is the shape every register but
    CIRCLE_OBSERVATION uses; the FIRST entry is what the manager mints (R481, 2026-09-07)."""
    return (prefix,) if isinstance(prefix, str) else tuple(prefix)


def _idnum(rec: dict, prefix) -> int | None:
    """The numeric part of a record's id under any accepted prefix, else None.

    NOT `v.startswith(prefix)` with a raw tuple: str.startswith ACCEPTS a tuple and would
    pass, and then `v[len(prefix):]` slices by the tuple's LENGTH (2) rather than the
    matched prefix's — returning None for every id and reading as ID-SEQUENCE on every
    staged record. Found by test_inter_circle, not by inspection."""
    v = rec.get("id", "")
    if not isinstance(v, str):
        return None
    for p in _prefixes(prefix):
        if v.startswith(p) and v[len(p):].isdigit():
            return int(v[len(p):])
    return None


def register_verify(rel: str, data: bytes | None,
                        spec: dict) -> list[M.Finding]:
    """The SINGLE-TREE half. Field-conditional; must be 0 FAIL on the tree
    as it stands at merge (the design's own acceptance test)."""
    if spec.get("frozen"):
        return []
    if data is None:
        return [M._f("WARN", "NO-FILE", rel, "register absent")]
    out: list[M.Finding] = []
    doc, err = _load_register(data)
    if doc is None:
        return [M._f("FAIL", "UNPARSEABLE", rel, f"does not load: {err}")]
    # A hand edit can leave `doc` a scalar (`doc = 1` still parses as
    # TOML); .get on it crashed the whole gate with a traceback instead
    # of a finding (2026-08-18 review, tier 3 #30). Same for a non-int
    # next_id and a table of non-dict rows below — this gate exists to
    # catch hand-edit damage, so hand-edit damage must never crash it.
    dtab = doc.get("doc")
    if dtab is not None and not isinstance(dtab, dict):
        out.append(M._f("FAIL", "BAD-DOC", rel,
                      f"[doc] is {type(dtab).__name__}, not a table"))
        dtab = {}
    if spec.get("preamble") and not (dtab or {}).get("preamble"):
        out.append(M._f("WARN", "NO-PREAMBLE", rel, "no [doc] preamble"))
    recs = doc.get(spec["table"], [])
    if not isinstance(recs, list):
        return out + [M._f("FAIL", "BAD-TABLE", rel,
                         f"{spec['table']!r} is not an array of tables")]
    if any(not isinstance(r, dict) for r in recs):
        return out + [M._f("FAIL", "BAD-TABLE", rel,
                         f"{spec['table']!r} holds non-table entries")]
    pre = spec.get("id_prefix")
    if pre:
        ids = [r.get("id") for r in recs if "id" in r]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            out.append(M._f("FAIL", "DUPLICATE-ID", rel, f"reused: {dupes}"))
        # A SPEC MAY NAME SEVERAL ACCEPTED PREFIXES — R481 (2026-09-07), for
        # CIRCLE_OBSERVATION's forward-only SO- -> CO- change. Every prefix is
        # accepted on a row that already exists; the manager mints the first.
        pres = _prefixes(pre)
        bad = [i for i in ids
               if not (isinstance(i, str)
                       and any(i.startswith(p) and i[len(p):].isdigit() for p in pres))]
        if bad:
            out.append(M._f("FAIL", "BAD-ID", rel,
                          f"not {'/'.join(pres)}NNNN-shaped: {bad[:4]}"))
        if "next_id" in doc and not isinstance(doc["next_id"], int):
            out.append(M._f("FAIL", "BAD-NEXT-ID", rel,
                          f"next_id is {type(doc['next_id']).__name__} "
                          f"({doc['next_id']!r}), not an int"))
        elif "next_id" in doc and ids and not bad:
            top = max(int(i[len(pre):]) for i in ids)
            if top >= doc["next_id"]:
                out.append(M._f("FAIL", "NEXT-ID-BEHIND", rel,
                              f"max id {top} >= next_id {doc['next_id']} — "
                              f"the high-water counter has fallen behind"))
    dates = [r.get("date", "") for r in recs if r.get("date")]
    if any(a > b for a, b in zip(dates, dates[1:])):
        out.append(M._f("WARN", "DATE-ORDER", rel,
                      "record dates are not nondecreasing in file order"))
    cap = spec.get("cap")
    if cap:
        start = 1 if spec.get("cap_exempt_first") else 0
        over = [i for i, r in enumerate(recs[start:], start)
                if len(r.get("text", "")) > cap]
        if over:
            out.append(M._f("FAIL", "OVER-CAP", rel,
                          f"record(s) {over} exceed the {cap:,}-char cap"))
    sv = spec.get("state_values")
    if sv:
        okpre = spec.get("state_prefixes", ())
        bad = [r.get("id", "?") for r in recs
               if not (r.get("state") in sv
                       or any(str(r.get("state", "")).startswith(x)
                              for x in okpre))]
        if bad:
            out.append(M._f("FAIL", "BAD-STATE", rel,
                          f"state outside vocabulary: {bad}"))
    if not _fixed_point(data, spec):
        out.append(M._f("WARN", "NOT-FIXED-POINT", rel,
                      "does not re-render byte-identically — hand-edited "
                      "without a re-save? Paired mode will refuse this "
                      "baseline"))
    if not out:
        out.append(M._f("OK", "PARSED", rel, f"{len(recs)} record(s)"))
    return out


def register_compare(rel: str, base: bytes | None, cand: bytes | None,
                     spec: dict) -> list[M.Finding]:
    """The PAIRED half — the phase-2 transaction gate for one register."""
    out: list[M.Finding] = []
    if cand is None:
        return []                       # not part of this run; nothing staged
    if spec.get("frozen"):
        if base != cand:
            return [M._f("FAIL", "FROZEN", rel,
                       "read-only register changed — nothing may write it "
                       "(R178)")]
        return [M._f("OK", "UNCHANGED", rel, "frozen and byte-identical")]
    if base is not None and not _fixed_point(base, spec):
        return [M._f("FAIL", "NOT-FIXED-POINT", rel,
                   "baseline does not re-render byte-identically — "
                   "hand-edited without a re-save; normalize before phase 2 "
                   "(the design's named precondition)")]
    bdoc = ({spec["table"]: []} if base is None
            else _load_register(base)[0])
    cdoc, err = _load_register(cand)
    if bdoc is None or cdoc is None:
        return [M._f("FAIL", "UNPARSEABLE", rel, f"does not load: {err}")]
    if not _fixed_point(cand, spec):
        return [M._f("FAIL", "NOT-FIXED-POINT", rel,
                   "candidate is not a dumps() render — phase 2 stages "
                   "module-rendered bytes and nothing else")]
    if base is not None:
        # A register CREATED this run (base None) introduces its preamble
        # and scalars legitimately; an existing one may touch neither —
        # except best_practices' own "**Entries: N**" tally
        # (preamble_tally), which its module keeps true on every append.
        if bdoc.get("doc") != cdoc.get("doc"):
            # scalar-[doc] guard, same class as register_verify's
            # BAD-DOC (tier 3 #30): a hand-edited candidate must FAIL
            # here as PREAMBLE-CHANGED, never crash the paired gate.
            bd = bdoc.get("doc") if isinstance(bdoc.get("doc"), dict) else {}
            cd = cdoc.get("doc") if isinstance(cdoc.get("doc"), dict) else {}
            bpre = str(bd.get("preamble", ""))
            cpre = str(cd.get("preamble", ""))
            _tly = re.compile(r"\*\*Entries: \d+\*\*")
            tally_only = (spec.get("preamble_tally")
                          and dict(bd, preamble="") == dict(cd, preamble="")
                          and _tly.sub("#", bpre) == _tly.sub("#", cpre))
            if not tally_only:
                out.append(M._f("FAIL", "PREAMBLE-CHANGED", rel,
                              "[doc] differs — the preamble is immutable"))
        for k in set(bdoc) | set(cdoc):
            if k in (spec["table"], "doc", "next_id"):
                continue
            if bdoc.get(k) != cdoc.get(k):
                out.append(M._f("FAIL", "SCALAR-CHANGED", rel,
                              f"top-level {k!r} changed"))
    brecs = bdoc.get(spec["table"], [])
    crecs = cdoc.get(spec["table"], [])
    if crecs[:len(brecs)] != brecs:
        n = next((i for i, (a, b) in enumerate(zip(crecs, brecs)) if a != b),
                 min(len(crecs), len(brecs)))
        out.append(M._f("FAIL", "NOT-APPEND-ONLY", rel,
                      f"prior records are not a prefix of the candidate; "
                      f"first divergence at record {n}"))
        return out
    tail = crecs[len(brecs):]
    mx = spec.get("per_run_max")
    if mx is not None and len(tail) > mx:
        out.append(M._f("FAIL", "TOO-MANY", rel,
                      f"{len(tail)} new record(s); this register takes at "
                      f"most {mx} per run"))
    pre = spec.get("id_prefix")
    if pre:
        base_n = bdoc.get("next_id", 1)
        want = cdoc.get("next_id")
        # The counter may be ABSENT on both sides of an id-less register
        # (today's remember.toml, before its first dreamt write) — that is
        # the one shape where no expectation exists. Everywhere else —
        # a tail, or a counter on either side — the arithmetic is exact.
        if tail or "next_id" in bdoc or want is not None:
            if want != base_n + len(tail):
                out.append(M._f("FAIL", "NEXT-ID", rel,
                              f"next_id {want!r}; expected "
                              f"{base_n + len(tail)} "
                              f"(baseline {base_n} + {len(tail)} new)"))
        for i, r in enumerate(tail):
            if _idnum(r, pre) != base_n + i:
                out.append(M._f("FAIL", "ID-SEQUENCE", rel,
                              f"new record {i} has id {r.get('id')!r}; "
                              f"expected {_prefixes(pre)[0]}{base_n + i:04d}"))
    cap = spec.get("cap")
    newest_base = max((r.get("date", "") for r in brecs), default="")
    base_ids = {r.get("id") for r in brecs if "id" in r}
    for i, r in enumerate(tail):
        if cap and len(r.get("text", "")) > cap:
            out.append(M._f("FAIL", "OVER-CAP", rel,
                          f"new record {i}: {len(r.get('text', '')):,} chars "
                          f"over the {cap:,} cap — refuse upstream, never "
                          f"truncate here"))
        if r.get("date", "") < newest_base:
            out.append(M._f("FAIL", "DATE-REGRESSION", rel,
                          f"new record {i} predates the baseline's newest"))
        ns = spec.get("new_state")
        if ns and r.get("state") != ns:
            out.append(M._f("FAIL", "BAD-NEW-STATE", rel,
                          f"new record {i} arrives state={r.get('state')!r}; "
                          f"a phase-2 write may only stage {ns!r}"))
        if spec.get("chain") and r.get("chain") is not None \
                and r["chain"] not in base_ids:
            out.append(M._f("FAIL", "CHAIN-TARGET", rel,
                          f"new record {i} chains to {r['chain']!r}, which is "
                          f"not an id in THIS register — a chain never leaves "
                          f"its own file"))
    if not out:
        what = f"+{len(tail)} record(s)" if tail else "unchanged"
        out.append(M._f("OK", "REGISTER", rel, what))
    return out


def register_summarise(findings: list[M.Finding]) -> tuple[int, int, int]:
    f = sum(1 for x in findings if x.level == "FAIL")
    w = sum(1 for x in findings if x.level == "WARN")
    return f, w, len(findings) - f - w
