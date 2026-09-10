#!/usr/bin/env python3
"""
circle_close_verify.py — circle-close verifier (circle_close.py until 2026-09-03: the
_verify suffix is R435's, and the bare name now belongs to the close step itself,
cohesion re-homing stage 12).

MOVED FROM scripts/ TO coordinator/ 2026-08-18. It had sat in scripts/ since the
agent-teams era, read as leftover tooling, and was twice assessed as a candidate
for archiving — but it is not leftover: it is the close step's VERIFIER (the step
itself is circle_close.py since stage 12). Two live
callers, both in this directory, both by subprocess:

    transcript_store.circle_close_verifier_run()   --short-term-only --write-report, at every
                                      live close; writes work/logs/close_<OT>.json
    circle_audit.py  phase 2          --reconcile, per unprocessed circle

The one sweep in scripts/ that WAS still general — preflight_check.py's
NUL/UTF-8/JSON corruption sweep — moved the same day to record_verify.py and is
now a gate at circle open. The nightly SKILL prompts were retired and scripts/
itself removed (2026-08-19).

WHAT IS LIVE HERE, AND WHAT IS VESTIGIAL. --short-term-only and --reconcile are
the load-bearing modes. The team-state checks below (1, 2, 4) and --prune belong
to the retired agent-teams runtime: coordinator/circle.py drives the parts as
direct Messages API calls, so there are no teammates to tear down and no
~/.claude/teams state to orphan. They are kept, not deleted, because they are
self-skipping when their subject is absent and because a tree archived from that
era still verifies against them. Nothing schedules them and no live path runs
them. Retiring them is Self's call.

Historic role, for reading the checks below: run by the Coordinator at circle close,
AFTER shutting the teammates down, to confirm the team was actually torn down and
no orphaned or bloated team state remains.

Also deletes every parts/*/statement_temp.md unconditionally (not gated behind
--prune — this is a routine close step, not a rare-orphan cleanup). process.md's
dual-delivery protocol has always said "delete all temp files at close," but it
was only ever a Coordinator habit with no script backing it; skipping it once left
four stale files sitting for two hours and cost a full liveness-canary
investigation before anyone could confirm they were harmless leftovers rather
than live interference (2026-07-02).

The agent-teams runtime is *supposed* to remove ~/.claude/teams/session-<id>/ when
the session ends, but in practice it often does not. A leftover team dir silently
accretes members across circles — the failure that reached 26 members spanning
four circles before it was noticed. This guard makes that loud.

The CURRENT session's own team dir is the exception: the harness creates it once
at session startup and is not expected to remove it until the session itself
ends, so its mere presence after a circle close is normal, not a leftover — it
is checked for bloat but is never a deletion candidate (see
circle_close_team_dir_read() below; deleting it breaks spawning for the rest of the
session, unrecoverable short of starting a new one).

Checks (evaluated against the state that REMAINS after any --prune):
  1. Leftover team dir   — any OTHER session's ~/.claude/teams/session-*/ still
                           present after close (current session's own excluded)
  2. Bloat               — any team config (current session's own included) whose
                           members array exceeds 8 (7 parts + the lead), i.e. a
                           part was re-spawned (part-2, ...) instead of messaged
  3. Today's transcript  — a circles/circle_<today>_*.md exists (close step 2 ran)
  4. Orphaned tasks dirs — any ~/.claude/tasks/session-*/ with NO corresponding
                           team dir at all (current session's own excluded).
                           These accumulate silently even when team-dir teardown
                           *succeeds* — cleaning a leftover team dir has only ever
                           deleted its matching tasks dir, never the reverse, so a
                           tasks dir whose team dir vanished on its own (runtime
                           cleanup, or an earlier prune before this check existed)
                           is left behind forever. Found 15 such dirs spanning
                           2026-06-16 through 2026-06-23 at first check (2026-07-02).
                           This is clutter, not interference — an orphaned tasks
                           dir has no mechanism to affect a live circle — so it is
                           reported as a WARN, not a FAIL.
  5. Missing short_terms  — every part that SPOKE (>=1 statement in the transcript)
                           must have a well-formed short_term_<open-time>.toml (.md before
                           2026-09-04, R434; either suffix is found). Under the
                           lead-writes-short_terms close contract the LEAD authors each
                           file from the part's reply (the lead's own writes persist
                           where teammate writes did not); a reply that drops (#43706)
                           is retried, then transcript-backfilled. Silent parts
                           (uncalled) are exempt. Needs --open-time (or
                           a single today's transcript). Prints a parseable
                           "MISSING-SHORT-TERM: <part>,..." line for the /circle_close
                           retry loop. Fails CLOSED if the transcript can't be resolved
                           (a stale mount must not vacuously pass the check).

Close report + reconcile (durability across the close->reconcile gap, #69866):
  --short-term-only --write-report  writes work/logs/close_<open-time>.json recording
      each speaking part's short_term size+sha256 — the durable manifest of what
      existed at close.
  --reconcile --open-time <ot>      the audit's pre-dreaming guard
      (circle_audit.py phase 2): re-reads the
      on-disk short_terms and compares to that report. A write that vanished between
      close and reconcile (sandbox mount not flushing to the durable store) is caught as
      "RECONCILE-DRIFT: <parts>" (exit 1) against a known expectation, so it is
      backfilled from the transcript instead of silently read as no-engagement — the
      exact "clean close, empty reconcile" contradiction that this closes.

Exit 0 = clean: no leftover (other-session) team dir, no bloat, transcript present,
            every speaking part wrote a well-formed short_term.
            (Orphaned tasks dirs alone do not fail the check — see #4 above.)
Exit 1 = action needed: leftover/bloat remains, today's transcript is missing, or a
            part that spoke has no (or a malformed) short_term.

With --prune:
  - leftover OTHER-session team dirs (and their matching
    ~/.claude/tasks/session-*/) are deleted first;
  - then any remaining orphaned ~/.claude/tasks/session-*/ with no team dir at
    all (current session's own excluded) are deleted too.
The checks then run against what remains. The current session's own team dir
and own tasks dir are never touched by --prune.

Usage:
  python coordinator/circle_close_verify.py
  python coordinator/circle_close_verify.py --prune
  python coordinator/circle_close_verify.py --short-term-only --open-time YYYY-MM-DD_HHMM --write-report
  python coordinator/circle_close_verify.py --reconcile --open-time YYYY-MM-DD_HHMM   # audit guard
  python coordinator/circle_close_verify.py --claude-home /path/to/.claude   # for testing
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "coordinator"))
import part_roster as R                                             # noqa: E402
import record_paths as _RP                                         # noqa: E402

# 8 named parts + the lead. Raised from 8 on 2026-08-07 with the ruling
# that a circle STARTS AT TWO and grows through part-initialisation as
# parts surface — so the roster is not a fixed seven with a spare slot, it
# is whatever has been met so far.
#
# THIS IS A BLOAT GUARD, NOT A ROSTER. It exists to catch a part being
# re-spawned as `part-2` instead of messaged, which once reached 26
# members across four circles before anyone noticed. Raise it when the
# roster genuinely grows; leaving it low turns a real circle into a failed
# close, and raising it far ahead of the roster turns the guard off.
MAX_MEMBERS = 9

# Transcript speaker tag -> parts/ subdir name. Self's own tag is
# intentionally absent: Self is not a part and writes no short_term, so this
# map is exactly the set of speakers that owe one. The Coordinator writes the
# transcript, so its tags are the ground truth for who spoke.
#
# THAT ABSENCE IS ALSO WHY PERSONALISING THE TAG IS SAFE HERE. Self's
# display name is configurable (identity.py) and has been written three ways
# across the corpus; none of them appears in this map, so none of them can
# affect which parts are found to have spoken.
# B29: derived from part_roster.py. BOTH SPELLINGS (DIR_BY_TAG_ALL, not
# DIR_BY_TAG) — the tag was renamed 2026-08-07 and 56 lines across the
# corpus carry the earlier one and are the record, so this reader (which
# walks historical transcripts, unlike circle_audit.py's STATEMENT_RE) still
# needs to resolve it. Read as R.DIR_BY_TAG_ALL at each use; the local
# TAG_TO_DIR alias went 2026-09-03.

# The four canonical short_term sections (process_core.md) — IMPORTED from
# record_model, the copy the register gate and the audit already share, so a
# schema edit lands once (2026-08-19, review tier 3 #35: this was the third
# hand copy; llm_client.py keeps its own by its transport-only charter, and
# test_register_gate asserts the two spellings agree). A dropped/truncated
# write is caught by a missing section, not only by an absent file.
from record_model import SHORT_TERM_SECTIONS  # noqa: E402

# A real statement line: "[Part]:" or "[Part] [To: X]:" at line start —
# part_roster.statement_re, the one grammar (see its docstring; this file's own
# copy accepted ANY second bracket and had drifted from nightly's). Coordinator
# annotations like "[Child has now spoken twice ...]" still do not match.
_STATEMENT_RE = R.statement_re(R.DIR_BY_TAG_ALL)


@_RP.group_follow
def _grammar_rebind() -> None:
    """The CURRENT group's Tags, historical spellings included — B117 stage 5 (2026-09-07)."""
    global _STATEMENT_RE
    _STATEMENT_RE = R.statement_re(R.DIR_BY_TAG_ALL)


def circle_close_team_dir_read() -> str | None:
    """Name of the CURRENT session's own team dir, e.g. 'session-8858292d'.

    The harness creates this dir at session startup (before any agent is
    spawned) and only removes it "when the session ends" — not per-circle,
    and never recreates it mid-session. It must never be PRUNED (deleted)
    while this session is still alive: doing so deletes the only team file
    this session can spawn into, unrecoverable short of starting a new
    session (observed 2026-07-02 — a Coordinator pruned its own not-yet-torn-down
    team dir on a false-positive "unclosed circle" match and lost the
    ability to spawn any part for the rest of that session). It IS still
    checked for bloat below — re-spawning within the live session is a real
    failure — just never deleted.
    """
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    return f"session-{sid.split('-')[0]}" if sid else None


def circle_close_team_dirs_read(teams_root: Path) -> list[Path]:
    return sorted(teams_root.glob("session-*")) if teams_root.is_dir() else []


def circle_close_task_dirs_read(tasks_root: Path) -> list[Path]:
    return sorted(tasks_root.glob("session-*")) if tasks_root.is_dir() else []


def circle_close_members_read(cfg: Path) -> tuple[list[str] | None, str | None]:
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return None, f"unreadable config.json ({e})"
    members = data.get("members", [])
    return [m.get("name", "?") for m in members], None


def circle_close_bloat_describe(names: list[str]) -> str:
    """Name the parts that were re-spawned (base name appears more than once)."""
    bases = Counter(n.split("-")[0] for n in names)
    dupes = sorted(f"{b}×{c}" for b, c in bases.items() if c > 1)
    return ", ".join(dupes) if dupes else ", ".join(sorted(names))


def parts_that_spoke(transcript: Path) -> dict[str, int]:
    """Map parts/ subdir name -> statement count, from the transcript's tags."""
    counts: Counter = Counter()
    try:
        text = transcript.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    for line in text.splitlines():
        m = _STATEMENT_RE.match(line)
        if m:
            counts[R.DIR_BY_TAG_ALL[m.group(1)]] += 1
    return dict(counts)


def short_term_status(path: Path | None) -> tuple[bool, str]:
    """(ok, reason). ok=True means present, non-empty, all four sections present
    and each with something under it. `path` is what short_term_manager.short_term_locate()
    found — None when the part has no record of this circle in either format.

    THROUGH THE ONE READER since B96 (R434, 2026-09-04): a .toml that does not
    parse, or parses without its four keys, is "malformed" exactly as a .md
    missing a heading is; an empty section is malformed too — the shape B54
    exists for, present on disk and read downstream as no engagement."""
    if path is None or not path.is_file():
        return False, "missing"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return False, f"unreadable ({e})"
    if not text.strip():
        return False, "empty"
    import short_term_manager as STM
    try:
        rec = STM.short_term_parse(path.name, text)
    except Exception as e:                                      # noqa: BLE001
        return False, f"malformed (does not parse: {e})"
    gone = STM.short_term_sections_missing(rec)
    absent = [h[3:] for h in SHORT_TERM_SECTIONS if h in gone]
    if absent:
        return False, "malformed (no section: " + "; ".join(absent) + ")"
    return True, ""


def record_file_digest(path: Path) -> tuple[int | None, str | None]:
    """(bytes, sha256_hex) for a file, or (None, None) if absent/unreadable."""
    try:
        data = path.read_bytes()
    except OSError:
        return None, None
    return len(data), hashlib.sha256(data).hexdigest()


def circle_close_report_write(root: Path, ot: str, transcript: Path,
                       records: list[dict], missing: list[str]) -> Path:
    """Persist work/logs/close_<ot>.json — the durable close manifest reconcile
    (circle_audit.py --reconcile, hand-invoked) verifies against. Records what
    SHOULD be on disk (per speaking part: size + sha256), so a later total
    loss (#69866) is caught as a MISSING against a known expectation instead
    of silently read as no-engagement."""
    logs = root / "work" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    report = {
        "open_time": ot,
        "checked_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "transcript": transcript.relative_to(root).as_posix(),
        "verifier": "circle_close_verify.py check #5",
        "result": "fail" if missing else "pass",
        "missing": sorted(missing),
        "note": ("Hashes are the close-time on-disk view, read through the sandbox "
                 "mount, which can cache/stale (#45433/#69866). Reconcile "
                 "re-reads the durable store and treats any MISSING/DRIFT as a lost "
                 "write to backfill — absence is caught unambiguously regardless."),
        "parts": records,
    }
    path = logs / f"close_{ot}.json"
    # newline="\n": text mode defaults to CRLF on Windows, and this file is a
    # durability record under git. Content is JSON so line endings never affected
    # parsing, but the report should not change shape depending on which machine
    # wrote it. (2026-07-26)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def circle_transcript_resolve(circles: Path, open_time: str | None):
    """Return (transcript_path_or_None, open_time_or_None, warn_or_None)."""
    if open_time:
        cand = circles / f"circle_{open_time}.md"
        return (cand if cand.is_file() else None), open_time, None
    today = date.today().strftime("%Y-%m-%d")
    todays = sorted(circles.glob(f"circle_{today}_*.md")) if circles.is_dir() else []
    if len(todays) == 1:
        return todays[0], todays[0].stem[len("circle_"):], None
    if len(todays) > 1:
        return None, None, ("multiple transcripts today; pass --open-time "
                            "YYYY-MM-DD_HHMM for the short_term check")
    return None, None, None


# ------------------------------------------- the close report as a postcondition

CLOSE_CONTRACT = Path(__file__).resolve().parent / "close_contract.toml"

_PC_TYPES = {"int": int, "str": str, "bool": bool, "list": list, "dict": dict}


def circle_close_contract_read() -> dict:
    """close_contract.toml, or {} when absent. A MISSING CONTRACT IS SAID OUT
    LOUD by the caller, never passed over — R368.

    ONE OF THREE IDENTICAL BODIES, deliberately: circling_verify.circling_contract_read()
    and prompt_capture.prompt_capture_contract_read() are the others. Each verifier owns
    its own CONTRACT constant and sits at a different layer, so a shared helper would need
    a home none of the three has and would buy one import edge per module for ten lines of
    tomllib boilerplate. Same trade record_ro_read() states, and the same answer."""
    try:
        import tomllib as _toml
    except ModuleNotFoundError:                              # pragma: no cover
        import tomli as _toml                                # type: ignore
    try:
        with CLOSE_CONTRACT.open("rb") as fh:
            return _toml.load(fh)
    except (OSError, ValueError):
        return {}


def _pc_shape(where: str, obj: dict, spec: dict, out: list) -> None:
    for key in spec.get("required", []):
        if key not in obj:
            out.append(where + ": missing required key " + repr(key))
    if spec.get("closed"):
        allowed = set(spec.get("required", [])) | set(spec.get("optional", []))
        for key in sorted(set(obj) - allowed):
            out.append(where + ": unexpected key " + repr(key)
                       + " — the contract is closed")
    for key, want in (spec.get("types") or {}).items():
        if key not in obj:
            continue
        cls = _PC_TYPES.get(want)
        if cls is None:
            continue
        if cls is int and isinstance(obj[key], bool):
            out.append(where + ": " + key + " is a bool, contract says int")
        elif not isinstance(obj[key], cls):
            out.append(where + ": " + key + " is "
                       + type(obj[key]).__name__ + ", contract says " + want)
    for key, allowed in (spec.get("values") or {}).items():
        if key in obj and obj[key] not in allowed:
            out.append(where + ": " + key + " is " + repr(obj[key])
                       + ", contract says one of " + repr(allowed))


def circle_close_group_of(path: Path) -> "str | None":
    """The group whose tree holds `path`, or None. Derived from
    record_paths.group_present_read(), so only a folder carrying a group.toml
    (R468) can ever be returned — never a string parsed out of the path."""
    for g in _RP.group_present_read():
        try:
            path.relative_to(_RP.group_tree(g))
        except ValueError:
            continue
        return g
    return None


def circle_close_transcript_resolve(root: Path, rel: object
                        ) -> "tuple[Path | None, str | None, str | None, str | None]":
    """(path, group, note, failure) for the transcript ONE close report names.
    Distinct from circle_transcript_resolve(), which finds TODAY's transcript
    for a live close; this reads a report that may be months old.

    A THE-TREE-MOVED IS NOT A DEFECT, for the same reason a renamed parts/
    directory is not (close_contract.toml [era]). A report records the
    transcript's path as it stood at the close, and B117 (R467, 2026-09-07)
    took every circle from `circles/` to `groups/<name>/circles/` — eleven
    reports written between 2026-07-26 and 2026-08-21 carry the older path and
    were TRUE WHEN WRITTEN.

    So a path that is not on disk is looked for by BASENAME in every group's
    circles/: exactly one match resolves it and is NOTED, none fails as
    before, and more than one FAILS rather than guessing which circle the
    report closed. Derived from the groups present — no hand-kept date, no old
    path written down, so the next move is absorbed without an edit here."""
    if not isinstance(rel, str) or not rel:
        return None, None, None, "names " + repr(rel) + ", which is not a path"
    p = root / rel
    if p.is_file():
        return p, circle_close_group_of(p), None, None

    base = rel.replace("\\", "/").rsplit("/", 1)[-1]
    hits = [(_RP.group_tree(g) / "circles" / base, g)
            for g in _RP.group_present_read()
            if (_RP.group_tree(g) / "circles" / base).is_file()]
    if len(hits) == 1:
        found, g = hits[0]
        return found, g, ("names '" + rel + "', which the tree moved to '"
                          + found.relative_to(root).as_posix()
                          + "' — the report was true when written"), None
    if len(hits) > 1:
        return None, None, None, (
            "names " + repr(rel) + ", which is not on disk, and "
            + str(len(hits)) + " groups hold a circle by that name ("
            + ", ".join(g for _f, g in hits) + ") — which circle the report "
            "closed cannot be derived")
    return None, None, None, ("names " + repr(rel) + ", which is not on disk")


def circle_close_postcondition_verify(name: str, report: dict, root: Path,
                        contract: dict) -> "tuple[list[str], str]":
    """Every rule in close_contract.toml against ONE close report. Returns
    (failures, note). A sandbox report yields no failures and a note: it is a
    different artefact in a different shape, and refusing it would turn a
    legitimate record into a red gate."""
    out: list[str] = []
    if not contract:
        return out, ""
    marker = (contract.get("era") or {}).get("sandbox_report_marker")
    if marker and marker in report:
        return out, (name + ": a sandbox close report — a different shape, "
                     "naming a circle under work/sandbox/; not checked")

    _pc_shape(name, report, contract.get("report", {}), out)
    parts = report.get("parts")
    if not isinstance(parts, list):
        return out, ""
    for row in parts:
        if not isinstance(row, dict):
            out.append(name + ": a parts row is not an object")
            continue
        _pc_shape(name + " parts[" + str(row.get("part")) + "]", row,
                  contract.get("part", {}), out)

    ot = report.get("open_time")
    rel = report.get("transcript")
    tpath, tgroup, moved, tfail = circle_close_transcript_resolve(root, rel)

    # names_its_own_transcript
    if tfail or tpath is None:
        out.append(name + " [names_its_own_transcript]: "
                   + (tfail or ("names " + repr(rel) + ", which is not on disk")))
        return out, ""
    if isinstance(ot, str) and isinstance(rel, str) and ot not in rel:
        out.append(name + " [names_its_own_transcript]: open_time " + ot
                   + " is not the transcript it names, " + rel)

    # EVERY REPORT IS READ WITH ITS OWN GROUP'S ROSTER — B117 stage 3's
    # mechanism, which this sweep never called. The speaker grammar and
    # DIR_NAMES below are the CURRENT group's; a band report read with the
    # IFS roster finds no speaker at all and fails every row it carries.
    # Restored in `finally`: a sweep must not leave the process bound to
    # the last report's group.
    bound = _RP.group_read()
    try:
        if tgroup and tgroup != bound:
            _RP.group_set(tgroup)
        # THE ONE READER of a transcript's speaker tags — never a second regex
        spoke = parts_that_spoke(tpath)
        roster = list(R.DIR_NAMES)
    finally:
        if _RP.group_read() != bound:
            _RP.group_set(bound)
    rows = {r.get("part"): r for r in parts if isinstance(r, dict)}

    # A DIRECTORY RENAME IS NOT A DEFECT (see close_contract.toml). A row
    # naming a directory today's roster does not have is PAIRED with an
    # unmatched speaker when their counts agree, and both leave the
    # name-based checks. Derived from the roster and the counts; no date
    # and no old name is written down anywhere.
    renamed: list[str] = []
    renamed_rows: set = set()
    paired_speakers: set = set()
    unmatched = {p: n for p, n in spoke.items() if p not in rows}
    for part in [p for p in rows if p not in roster]:
        n = rows[part].get("statements")
        mate = next((s for s, m in unmatched.items() if m == n), None)
        if mate is None:
            continue
        renamed.append(str(part) + " -> " + mate + " (" + str(n)
                       + " statement(s))")
        del unmatched[mate]
        # THE ROW STAYS IN `rows`. Only the two NAME-based rules skip
        # it; the digest, the missing/present agreement and the shape
        # checks all still run, which is what close_contract.toml
        # promises. Popping it here made a rename an exemption from
        # everything, and test_close_postcondition caught that.
        renamed_rows.add(part)
        paired_speakers.add(mate)

    # statements_agree_with_the_transcript
    for part, row in rows.items():
        if part in renamed_rows:
            continue
        want = spoke.get(part)
        if want is None:
            out.append(name + " [statements_agree_with_the_transcript]: "
                       + str(part) + " has a row but does not speak in the "
                       "transcript")
        elif row.get("statements") != want:
            out.append(name + " [statements_agree_with_the_transcript]: "
                       + str(part) + " recorded " + repr(row.get("statements"))
                       + " statement(s), the transcript shows " + str(want))

    # every_speaking_part_has_a_row
    for part in sorted(set(spoke) - set(rows) - paired_speakers):
        out.append(name + " [every_speaking_part_has_a_row]: " + part
                   + " spoke " + str(spoke[part]) + "× and has no row at all "
                   "— not recorded absent, simply unmentioned")

    # result_agrees_with_missing
    missing = report.get("missing")
    if isinstance(missing, list) and isinstance(report.get("result"), str):
        want = "pass" if not missing else "fail"
        if report["result"] != want:
            out.append(name + " [result_agrees_with_missing]: result is "
                       + repr(report["result"]) + " while missing is "
                       + repr(missing))

    # missing_agrees_with_present
    if isinstance(missing, list):
        absent = {p for p, r in rows.items() if r.get("present") is False}
        for p in sorted(absent - set(missing)):
            out.append(name + " [missing_agrees_with_present]: " + str(p)
                       + " is recorded absent but is not in `missing`")
        for p in sorted(set(missing) - absent):
            out.append(name + " [missing_agrees_with_present]: " + str(p)
                       + " is in `missing` but no row records it absent")

    # a_present_part_carries_its_digest
    for part, row in rows.items():
        if row.get("present") is not True:
            continue
        sha = row.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            out.append(name + " [a_present_part_carries_its_digest]: "
                       + str(part) + " is present but its sha256 is "
                       + repr(sha))
        if not isinstance(row.get("bytes"), int):
            out.append(name + " [a_present_part_carries_its_digest]: "
                       + str(part) + " is present but its byte count is "
                       + repr(row.get("bytes")))

    # The dispositions ride out AFTER every rule has run: only the two
    # NAME-based postconditions skipped the paired rows, which is what
    # close_contract.toml says happens. A report can carry both — a circle
    # that moved trees AND a part directory renamed since.
    tail: list[str] = []
    if moved:
        tail.append(moved)
    if renamed:
        tail.append(", ".join(renamed)
                    + " — a parts/ directory renamed since the close; "
                      "the report was true when written")
    return out, ((name + ": " + "; ".join(tail)) if tail else "")


def circle_close_postcondition_sweep(root: Path, open_time: "str | None" = None) -> int:
    """`--postcondition`: every close report read against the transcript it
    names. With --open-time, one report."""
    print("Close-report postcondition check (R368)")
    contract = circle_close_contract_read()
    if not contract:
        print("  FAIL  " + CLOSE_CONTRACT.name + " is missing or unreadable — "
              "nothing was checked")
        return 1

    logs = root / "work" / "logs"
    reports = ([logs / ("close_" + open_time + ".json")] if open_time
               else sorted(logs.glob("close_*.json")))
    reports = [p for p in reports if p.is_file()]
    if not reports:
        print("  no close reports found — nothing to check")
        return 0

    fails: list[str] = []
    notes: list[str] = []
    checked = 0
    for p in reports:
        try:
            report = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            fails.append(p.name + ": unreadable — " + str(e))
            continue
        bad, note = circle_close_postcondition_verify(p.name, report, root, contract)
        if note:
            notes.append(note)
        # A NOTE IS NOT AN EXEMPTION. A sandbox report returns no
        # failures because it is a different artefact; a renamed
        # directory returns whatever the other rules found. Both are
        # counted as read, so the printed total is the real one.
        checked += 1
        fails.extend(bad)

    # THE CENSUS, both ways. A transcript older than the OLDEST report predates
    # close reporting and is out of scope — derived from the reports themselves,
    # never a hand-kept date.
    stamps = sorted(p.name[len("close_"):-len(".json")] for p in reports)
    if stamps and open_time is None:
        oldest = stamps[0]
        seen = set(stamps)
        # EVERY GROUP'S CIRCLES, not the bound one's — B129, 2026-09-09. This
        # walked `record_dir(root, "circles")`, so a circle in any OTHER group
        # that closed after close reporting began and has NO close report was
        # invisible to the census. The reports themselves were already read
        # group-blind until the same day's fix; this is the other half, and
        # the half that asks the question the other direction.
        #
        # Derived from group_present_read(), so a new group is censused
        # without an edit. Measured before wiring: on 2026-09-09 neither group
        # had a transcript in scope without a report, so this widened the
        # question without changing today's answer.
        for g in _RP.group_present_read():
            circles = _RP.group_tree(g) / "circles"
            for t in sorted(circles.glob("circle_*.md")):
                ot = t.name[len("circle_"):-len(".md")]
                if ot < oldest:
                    continue
                if ot not in seen:
                    fails.append(g + "/" + t.name + ": closed after close "
                                 "reporting began (" + oldest + ") and has no "
                                 "close report")
            before = sum(1 for t in circles.glob("circle_*.md")
                         if t.name[len("circle_"):-len(".md")] < oldest)
            if before:
                notes.append(str(before) + " " + g + " transcript(s) predate "
                             "the oldest close report (" + oldest
                             + ") and are out of scope")

    n_rules = len(contract.get("postcondition", []))
    print("  " + str(checked) + " report(s) read against the transcript each "
          "names, " + str(n_rules) + " postcondition(s) per report")
    for n in notes:
        print("  note  " + n)
    if fails:
        print("\n  " + str(len(fails)) + " FAILURE(S):")
        for f in fails:
            print("    - " + f)
        return 1
    print("  PASS — every close report is a true statement about the circle "
          "it closed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Circle-close teardown verifier.")
    ap.add_argument("--claude-home", default=str(Path.home() / ".claude"),
                    help="path to ~/.claude (override for testing)")
    ap.add_argument("--root", default=str(ROOT),
                    help="project root (for the circles/ transcript check)")
    ap.add_argument("--prune", action="store_true",
                    help="delete leftover team dirs and their matching tasks dirs")
    ap.add_argument("--short-term-only", action="store_true",
                    help="run ONLY the short_term check (check #5) — for the "
                         "/circle_close retry loop, before hard shutdown, while "
                         "agents are still reachable; skips teardown checks, prune, "
                         "and statement_temp deletion")
    ap.add_argument("--group", default=None,
                    # B117 stage 5 — in the comment, not in help=, which ships.
                    help="verify this GROUP's record (groups/<name>/). "
                         "Default: the ifs group.")
    ap.add_argument("--max-members", type=int, default=MAX_MEMBERS)
    ap.add_argument("--open-time", default=None,
                    help="circle open time YYYY-MM-DD_HHMM; if given, check for "
                         "circles/circle_<open-time>.md exactly instead of "
                         "guessing by today's calendar date (avoids a false "
                         "WARN when a circle opens before midnight and closes "
                         "after it)")
    ap.add_argument("--write-report", action="store_true",
                    help="with --short-term-only: emit work/logs/close_<open-time>.json "
                         "recording each speaking part's short_term size+sha256, so the "
                         "audit reconcile can verify the durable store against what "
                         "existed at close (closes the silent 'clean close, empty "
                         "reconcile' gap, #69866).")
    ap.add_argument("--postcondition", action="store_true",
                    help="read every close report against the transcript "
                         "it names (R368); --open-time narrows it to one")
    ap.add_argument("--reconcile", action="store_true",
                    help="audit durability check (runs BEFORE dreaming): re-read the "
                         "on-disk short_terms and compare to work/logs/close_<open-time>."
                         "json; exit 1 with a RECONCILE-DRIFT line naming any part whose "
                         "recorded write is now absent or changed, so it is backfilled "
                         "from the transcript instead of read as no-engagement. "
                         "Requires --open-time.")
    args = ap.parse_args()
    if args.group:
        _RP.group_set(args.group)           # B117 stage 5: this group's record, before any read

    claude_home = Path(args.claude_home)
    root = Path(args.root)
    teams_root = claude_home / "teams"
    tasks_root = claude_home / "tasks"

    blocks: list[str] = []
    warns: list[str] = []
    actions: list[str] = []

    # Reconcile mode: the audit's durability guard, run BEFORE dreaming. Re-reads
    # each short_term the close report said it wrote and compares size+sha256, so a
    # write that vanished between close and reconcile (sandbox mount not flushing to
    # the durable store, #69866) is caught as MISSING/DRIFT against a known
    # expectation — never silently read as no-engagement. Absence is unambiguous
    # even through a stale mount; a spurious DRIFT only triggers a safe re-backfill.
    if args.postcondition:
        # READING circles/ — circle_state fails closed, and a partial
        # transcript is well-formed, so a mid-circle sweep would report
        # a protocol failure that is only an in-flight circle (ruled
        # 2026-08-05).
        import circle_state
        if circle_state.circle_is_in_progress():
            print("Close-report postcondition check (R368)")
            print("  SKIPPED — a circle may be open; its transcript is "
                  "still being written.")
            print("  Run coordinator/circle_state.py to see which.")
            return 0
        return circle_close_postcondition_sweep(root, args.open_time)

    if args.reconcile:
        ot = args.open_time
        print("Circle-close reconcile (audit durability check)")
        if not ot:
            print("  FAIL  --reconcile requires --open-time YYYY-MM-DD_HHMM")
            return 1
        report_path = root / "work" / "logs" / f"close_{ot}.json"
        if not report_path.is_file():
            print(f"  WARN  no close report {report_path.relative_to(root).as_posix()} "
                  f"— circle predates close-report logging; nothing to reconcile")
            return 0
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  FAIL  close report unreadable ({e})")
            return 1
        drift: list[str] = []
        for entry in report.get("parts", []):
            if not entry.get("present"):
                continue  # not recorded present at close; already surfaced there
            part = entry.get("part", "?")
            # THE FILE THE CLOSE HASHED, by its recorded name (B96, R434): a report
            # from before 2026-09-04 carries no `file` key and hashed the .md.
            name = entry.get("file") or f"short_term_{ot}.md"
            nbytes, nsha = record_file_digest(_RP.record_dir(root, "parts") / part / name)
            if nsha is None:
                drift.append(part)
                print(f"  MISSING  {part}: close recorded it present "
                      f"({entry.get('bytes')} bytes) but it is absent on disk now")
            elif nsha != entry.get("sha256") or nbytes != entry.get("bytes"):
                drift.append(part)
                print(f"  DRIFT    {part}: on-disk differs from close "
                      f"(close {entry.get('bytes')}B/{str(entry.get('sha256'))[:12]}…, "
                      f"now {nbytes}B/{str(nsha)[:12]}…)")
            else:
                print(f"  OK       {part}: matches close report")
        if drift:
            print(f"RECONCILE-DRIFT: {','.join(sorted(drift))}")
            print("\nRECONCILE FAIL — durable store diverged from close state; "
                  "backfill the named parts from the transcript before dreaming.")
            return 1
        print("\nRECONCILE PASS — every short_term recorded at close is intact on disk.")
        return 0

    # Short-term-only mode: used by the /circle_close retry loop BEFORE the hard
    # shutdown, to verify each speaking part's record is durably written while agents
    # are still alive and re-reachable. Skips all teardown checks, --prune, and
    # statement_temp deletion (parts may not have fully stood down yet). With
    # --write-report it also emits the close report reconcile reads.
    if args.short_term_only:
        circles = _RP.record_dir(root, "circles")
        transcript, ot, st_warn = circle_transcript_resolve(circles, args.open_time)
        print("Circle-close short_term check")
        if st_warn:
            print(f"  WARN  {st_warn}")
        if transcript is None or not ot:
            # Fail CLOSED. A stale mount can make the transcript unresolvable
            # (#41710/#69866); the old `return 0` here let the check vacuously
            # "pass" with nothing verified — exactly the false clean-close.
            print("  FAIL  no resolvable transcript; cannot verify short_terms "
                  "(pass --open-time YYYY-MM-DD_HHMM)")
            return 1
        records: list[dict] = []
        missing: list[str] = []
        import short_term_manager as STM
        for part, n in sorted(parts_that_spoke(transcript).items()):
            path = STM.short_term_locate(_RP.record_dir(root, "parts") / part, ot)
            ok, why = short_term_status(path)
            nbytes, nsha = record_file_digest(path) if path else (None, None)
            # `file` — THE REAL NAME HASHED, extension included (B96): what
            # --reconcile re-hashes later. Optional in close_contract.toml, so a
            # pre-B96 report (no key, always .md) still reads.
            row = {
                "part": part, "statements": n, "present": ok,
                "bytes": nbytes, "sha256": nsha, "status": "ok" if ok else why,
            }
            if path is not None:
                row["file"] = path.name
            records.append(row)
            if ok:
                print(f"  OK    {part}: short_term present ({n} statement(s))")
            else:
                missing.append(part)
                print(f"  FAIL  {part}: spoke {n}× but "
                      f"{path.name if path else STM.short_term_name(ot)} {why}")
        if args.write_report:
            rp = circle_close_report_write(root, ot, transcript, records, missing)
            print(f"  DONE  wrote close report {rp.relative_to(root).as_posix()}")
        if missing:
            print(f"MISSING-SHORT-TERM: {','.join(sorted(missing))}")
            return 1
        print("  OK    every speaking part wrote a short_term")
        return 0

    # Delete all statement_temp.md files — unconditional, every run (see
    # module docstring). Not part of --prune: this is routine close hygiene,
    # not rare-orphan cleanup.
    parts_root = _RP.record_dir(root, "parts")
    if parts_root.is_dir():
        for tmp in sorted(parts_root.glob("*/statement_temp.md")):
            tmp.unlink()
            actions.append(f"removed {tmp.relative_to(root).as_posix()}")

    own = circle_close_team_dir_read()
    dirs = circle_close_team_dirs_read(teams_root)
    other_dirs = [d for d in dirs if d.name != own]

    # --prune first, so the checks below reflect the final state.
    # Only OTHER (genuinely dead-session) dirs are ever deleted — the
    # current session's own dir is never a deletion candidate while this
    # session is still running. See circle_close_team_dir_read() docstring.
    if args.prune and other_dirs:
        for d in other_dirs:
            sid = d.name  # "session-xxxxxxxx"
            shutil.rmtree(d, ignore_errors=True)
            actions.append(f"removed teams/{sid}")
            tdir = tasks_root / sid
            if tdir.is_dir():
                shutil.rmtree(tdir, ignore_errors=True)
                actions.append(f"removed tasks/{sid}")
        dirs = circle_close_team_dirs_read(teams_root)  # rescan
        other_dirs = [d for d in dirs if d.name != own]

    # Orphaned tasks dirs: any tasks/session-* with NO corresponding team dir
    # at all (own excluded). These are left behind even when team-dir teardown
    # succeeds on its own — the matched-pair prune above only ever fires
    # alongside a leftover TEAM dir, never in isolation. Reported as a WARN
    # (clutter, not interference) rather than a FAIL.
    live_team_names = {d.name for d in circle_close_team_dirs_read(teams_root)}  # post-prune state
    orphan_task_dirs = [
        d for d in circle_close_task_dirs_read(tasks_root)
        if d.name != own and d.name not in live_team_names
    ]
    if args.prune and orphan_task_dirs:
        for d in orphan_task_dirs:
            shutil.rmtree(d, ignore_errors=True)
            actions.append(f"removed orphaned tasks/{d.name} (no matching team dir)")
        orphan_task_dirs = []

    # 1: leftover dirs — only OTHER sessions' dirs count; the current
    # session's own dir persisting is expected (runtime removes it "when
    # the session ends", not at circle close).
    if other_dirs:
        blocks.append(
            f"{len(other_dirs)} leftover team dir(s) after close: "
            f"{[d.name for d in other_dirs]} — runtime did not tear down. "
            f"{'Prune failed.' if args.prune else 'Re-run with --prune, or delete by hand.'}"
        )

    # 2: bloat — checked across ALL dirs still present, including the
    # current session's own (re-spawning within the live session is a
    # real failure even though its dir is never deleted).
    for d in dirs:
        cfg = d / "config.json"
        if not cfg.exists():
            warns.append(f"{d.name}: no config.json (partial/corrupt team dir)")
            continue
        names, err = circle_close_members_read(cfg)
        if err:
            warns.append(f"{d.name}: {err}")
            continue
        if len(names) > args.max_members:
            blocks.append(
                f"{d.name}: {len(names)} members (> {args.max_members}) — "
                f"re-spawning detected ({circle_close_bloat_describe(names)}); a part was spawned "
                f"again instead of messaged"
            )

    # 3: transcript present. Exact check if --open-time was given (avoids a
    # false WARN when a circle opens before midnight and closes after it,
    # since the transcript filename is stamped with OPEN time, not close
    # time); falls back to a same-calendar-day guess otherwise.
    circles = _RP.record_dir(root, "circles")
    if args.open_time:
        expected = circles / f"circle_{args.open_time}.md"
        if not expected.is_file():
            warns.append(
                f"expected transcript {expected.relative_to(root).as_posix()} "
                f"not found — confirm the transcript was written"
            )
    else:
        today = date.today().strftime("%Y-%m-%d")
        todays = list(circles.glob(f"circle_{today}_*.md")) if circles.is_dir() else []
        if not todays:
            warns.append(
                f"no transcript circles/circle_{today}_*.md — confirm the transcript "
                f"was written (pass --open-time YYYY-MM-DD_HHMM for an exact check "
                f"across a midnight boundary)"
            )

    # 4: orphaned tasks dirs remaining after any --prune.
    if orphan_task_dirs:
        warns.append(
            f"{len(orphan_task_dirs)} orphaned tasks dir(s) with no matching team dir: "
            f"{[d.name for d in orphan_task_dirs]} — re-run with --prune to remove."
        )

    # 5: every part that spoke must have a well-formed short_term for this circle.
    # See module docstring check #5. Needs the transcript to know who spoke.
    missing_short_terms: list[str] = []
    transcript, ot, st_warn = circle_transcript_resolve(circles, args.open_time)
    if st_warn:
        warns.append(st_warn)
    if transcript is not None and ot:
        import short_term_manager as STM
        for part, n in sorted(parts_that_spoke(transcript).items()):
            path = STM.short_term_locate(_RP.record_dir(root, "parts") / part, ot)
            ok, why = short_term_status(path)
            if not ok:
                missing_short_terms.append(part)
                blocks.append(
                    f"{part}: spoke {n}× but "
                    f"{path.name if path else STM.short_term_name(ot)} {why} — the lead's "
                    f"close-write did not land (reply dropped #43706, or a mount flush "
                    f"failure #69866); by the --prune stage agents are down, so backfill "
                    f"it from the transcript"
                )

    # Report.
    print(f"Circle-close check  (teams: {teams_root})")
    for a in actions:
        print(f"  DONE  {a}")
    for w in warns:
        print(f"  WARN  {w}")
    for b in blocks:
        print(f"  FAIL  {b}")
    if missing_short_terms:
        # Machine-parseable: the /circle_close retry loop greps this exact prefix
        # to know which parts to re-send the write+stand-down to.
        print(f"MISSING-SHORT-TERM: {','.join(sorted(missing_short_terms))}")
    if blocks:
        print(f"\nCIRCLE-CLOSE FAIL — {len(blocks)} issue(s) need attention "
              f"before the next circle.")
        return 1
    print("  OK    no leftover team dir, no bloat")
    print("\nCIRCLE-CLOSE PASS — team torn down cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
# check #5 (short_term integrity) + --short-term-only added 2026-07-11
# fail-closed check #5 + --write-report (close report) + --reconcile (nightly
# durability guard) added 2026-07-12, after a full-scope close-write loss on
# circle_2026-07-11_1644 (all 6 speaking parts) passed a clean close and read as
# no-engagement at nightly — the Cowork sandbox-mount stale/flush bug class
# (claude-code #45433/#41710/#69866/#51214).
