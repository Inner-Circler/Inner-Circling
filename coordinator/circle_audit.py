#!/usr/bin/env python3
"""
circle_audit.py — the circle-record audit. Renamed from nightly.py 2026-08-19
(Self's ruling; design history under the old name: docs/NIGHTLY_DESIGN.md).
Verifies — and, for lost short_terms, repairs — the per-circle records that
/close and coordinator/inter_circle.py produce.

WHAT EXISTS TODAY
    0  preflight   lock, leftover-journal, git preconditions, check_integrity.py
    1  survey      circles inter_circle.py has not processed (no dream/<OT> tag)
    2  reconcile   circle_close.py --reconcile per circle + transcript safety net
    3  backfill    reconstruct a lost short_term from the transcript
    6  validate    ifs_model invariants: self-check, baseline, or staged candidate
    7  commit      journalled os.replace sweep (transaction.py)
    8  verify      re-read every committed file, compare sha256
    9  record      git commit of this run's own paths, committed.json, log line

    Phases 4 (dream) and 5 (synthesise) are deliberately NOT here: they are
    coordinator/inter_circle.py, run synchronously at /close (R163's
    "between, not cross" — docs/INTER_CIRCLE_DESIGN.md). This module is the
    independent check on that engine's records, and stays independent of it:
    an engine asserting it acted is exactly the assurance this file was
    built to replace.

    Without --commit this script writes only under work/circle_audit/ (its
    lock, snapshots, run log) and work/nightly/ (transaction.py's own
    staging root, shared with inter_circle.py and NOT renamed with this
    file). With --backfill --commit it writes short_terms, and nothing else
    — enforced by the staging set, the invariant gate, and the transaction.

    PRE-INTER_CIRCLE RECORDS ARE OUT OF SCOPE (ruled 2026-08-19,
    with this rename): circles older than the oldest dream/<OT> tag were
    processed — or not — by the retired batch nightly, and this audit
    neither surveys nor reconciles them. work/manifests/ is NOT that
    nightly's record — verified 2026-08-31, it holds this repo's own
    .claude/skills/workflow dev-tooling manifests; no coordinator/*.py
    reads or writes it, so it stays out of scope for an unrelated reason.

EXIT CODES
    0  everything checked passed
    1  a check FAILED (or preflight refused to start)
    2  a leftover commit JOURNAL exists — manual decision required (§3.3)
"""

from __future__ import annotations

import argparse
import atexit
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
# The audit's OWN artifacts (lock, baselines, run log) live here. Staging and
# journals stay under work/nightly/ — that is transaction.py's root, shared
# with inter_circle.py, and renaming it is a separate decision.
WORK = ROOT / "work" / "circle_audit"
LOCK = WORK / ".lock"
LOCK_STALE_SEC = 6 * 3600

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import ifs_model as M                                       # noqa: E402
import backfill as BF                                       # noqa: E402  (B54)
import gitrepo as G                                         # noqa: E402
import transaction as T                                     # noqa: E402
import roster as R                                          # noqa: E402
import self_schema as SS                                    # noqa: E402
import self_observation_log as SO                           # noqa: E402
                                   # noqa: E402

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


CIRCLE_RE = re.compile(r"^circle_(\d{4}-\d{2}-\d{2}_\d{4})\.md$")
# B29: derived from roster.py. Deliberately roster.TAGS (current
# spellings only), NOT the _ALL set — this reader only ever sees circles
# this audit is processing, which postdate the 2026-08-07 Soul tag
# rename, unlike circle_close.py which also walks historical transcripts.
# The GRAMMAR is roster.statement_re, the one builder (2026-08-19, review
# tier 3 #35 — this file's own copy accepted arbitrary spacing and had
# drifted from circle_close's; only the tag set differs now, and that
# difference is the documented intent above).
STATEMENT_RE = R.statement_re(R.TAGS)
TAG_TO_DIR = R.DIR_BY_TAG

# Exactly what an audit run is allowed to have left uncommitted. Anything
# dirty outside this set was not this tool. Rewritten at the 2026-08-19
# rename: the old set was the batch nightly's write surface (long_term.md,
# narratives, self.md, manifests) — writers that are gone. This tool itself
# writes only short_terms (--backfill) and one synthetic observation-log
# append (--stage-synthetic); inter_circle.py git-commits its own writes
# inside /close, so its output never sits uncommitted between runs.
AUDIT_OUTPUT_RE = re.compile(
    r"^(parts/[a-z_]+/short_term_[\d_-]+\.md"
    r"|self/self_observation_log\.toml)$")


def hr(title: str) -> None:
    print(f"\n{'-' * 72}\n{title}\n{'-' * 72}")


class Run:
    """Collects failures so one bad check does not hide the next."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def fail(self, msg: str) -> None:
        self.failures.append(msg)
        print(f"  FAIL  {msg}")

    def ok(self, msg: str) -> None:
        print(f"  OK    {msg}")

    def warn(self, msg: str) -> None:
        print(f"  WARN  {msg}")


# ------------------------------------------------------------------ phase 0
def git(*args: str) -> tuple[int, str]:
    """ALWAYS read-only (--no-optional-locks). Every call through here is
    a QUESTION — version, git-dir, status — and `git status` otherwise
    refreshes and rewrites the index, taking `.git/index.lock` to do it.
    This module has no writing caller of its own (commits go through
    gitrepo.commit_paths), so the flag is unconditional.

    A thin shell over gitrepo.run() since 2026-08-19 (review, tier 5
    #45): this used to be a hand-rolled duplicate of run()'s subprocess
    mechanics — same flag, same encoding, same errors="replace" lesson
    re-pasted by hand — and the copies had already drifted (30s vs 120s
    timeout; a raised GitError vs this module's rc-tuple contract). The
    MECHANICS now have one owner; only the CONTRACT is adapted here:
    phase 0 reports returncodes, so a GitError (git missing, or killed
    at run()'s 120s timeout) degrades to the same (127, message) tuple
    every caller already checks."""
    try:
        return G.run(*args, read_only=True)
    except G.GitError as e:
        return 127, str(e)


def git_setup(run: Run, name: str | None, email: str | None) -> int:
    """Idempotent bootstrap. Everything routine; nothing irreversible. Safe to
    re-run at any time — it only adds what is missing."""
    hr("git setup")
    marks = {"ok": "  OK   ", "did": "  DID  ", "warn": "  WARN ",
             "note": "         ", "fail": "  FAIL "}

    def log(kind, msg):
        print(f"{marks[kind]}{msg}")
        if kind == "fail":
            run.failures.append(msg)

    if not G.available():
        log("fail", "git is not on PATH")
        return 1
    log("ok", G.run("--version")[1].splitlines()[0])
    if not G.ensure_repo(log) or G.refuse_remote(log):
        return 1
    # refuse_remote() reports each remote it PASSES, with the reason, so the
    # blanket line that used to sit here is both redundant and — since
    # 2026-08-09 — false. See gitrepo.classify_remote.
    log("ok", "no remote can take this material off the machine")
    G.ensure_config(log, name, email)
    G.ensure_attributes(log)
    G.ensure_hooks(log)
    G.ensure_ignore(log)
    G.untrack_ignored(log)

    dirty = G.dirty()
    if not dirty:
        log("ok", "working tree clean — nothing to commit")
    else:
        print(f"\n  {len(dirty)} path(s) differ from HEAD:")
        for l in dirty[:20]:
            print(f"      {l}")
        if len(dirty) > 20:
            print(f"      ... and {len(dirty) - 20} more")
        print("\n  This is the ONE step left to you, deliberately: staging the whole")
        print("  tree is a human judgement about what belongs in the baseline.")
        print("  Automated runs only ever commit their own output paths.")
        print("\n    git add -A && git commit -m \"baseline\"")
    return 1 if run.failures else 0


def check_git(run: Run, may_commit: bool) -> None:
    """git preconditions. ENFORCED only when the run could write to the live tree
    — git is the revert target for writes, so a read-only run does not need it."""
    level = run.fail if may_commit else run.warn
    rc, out = git("--version")
    if rc != 0:
        level(f"git unavailable ({out}) — there is no revert target")
        return
    run.ok(out.splitlines()[0])
    if git("rev-parse", "--git-dir")[0] != 0:
        level("not a git repository — run the §6 bootstrap in NIGHTLY_DESIGN.md; "
              "without it a bad night cannot be rolled back")
        return
    # NOTHING LEAVES THIS MACHINE (docs/NIGHTLY_DESIGN.md §6). This block used
    # to fail on any remote at all, which is not the same rule and cost a
    # circle its commit on 2026-08-09 — see gitrepo.classify_remote. It now
    # delegates, so there is ONE classifier and not two that can disagree.
    try:
        import gitrepo as _G
        _G.refuse_remote(lambda k, m: (run.fail if k == "fail" else run.ok)(m))
    except ImportError:
        run.fail("gitrepo.py not importable — cannot classify git remotes")
    rc, status = git("status", "--porcelain")
    if rc != 0:
        level(f"git status failed: {status}")
        return
    lines = [l for l in status.strip().splitlines() if l.strip()]
    if not lines:
        run.ok("working tree clean")
        return
    # Distinguish "the audit wrote its output and you have not committed it yet"
    # — the expected state after an interrupted or --no-git run — from genuinely
    # unexplained dirt. Reporting both the same way trains you to ignore the
    # warning, which defeats its purpose on the day it matters.
    # porcelain v1 is 'XY PATH'; slice past the two status columns and strip,
    # which is correct for ' M f', '?? f', 'M  f' and 'MM f' alike.
    paths = [l[2:].strip().strip('"') for l in lines]
    expected = [p for p in paths if AUDIT_OUTPUT_RE.match(p)]
    other = [p for p in paths if not AUDIT_OUTPUT_RE.match(p)]
    if expected and not other:
        run.ok(f"working tree dirty in {len(expected)} path(s), all of them audit "
               f"output — the expected state after an uncommitted backfill. "
               f"Review, then commit.")
        return
    level(f"working tree is dirty: {len(other)} path(s) outside the audit's "
          f"output set" + (f" (plus {len(expected)} that are audit output)"
                           if expected else "")
          + ". An interrupted run or a hand-edit; commit or stash before a run "
            "that writes.")
    for p in other[:10]:
        print(f"          {p}")


def dream_tags() -> tuple[list[str], str | None]:
    """(every OT inter_circle.py has processed, or None-error). The dream/<OT>
    git tag is the durable marker inter_circle's phase-2 commit writes, and
    already_processed() reads — ONE definition of "processed", theirs.

    On a git failure this returns ([], the error) rather than a bare empty
    list: an empty answer read as "nothing processed" would report every
    circle unprocessed because git hiccuped — the same lesson
    inter_circle.already_processed() carries, pointed the other way."""
    rc, out = git("tag", "-l", "dream/*")
    if rc != 0:
        return [], f"git tag -l dream/* -> {rc}: {out}"
    return sorted(t.split("/", 1)[1] for t in out.split()
                  if t.startswith("dream/")), None


def check_circle_open(run: Run, writing: bool) -> None:
    """Refuse to snapshot while a circle may be open. /close's phase 2
    (inter_circle.py) dreams and commits synchronously inside the close, so a
    snapshot taken mid-circle captures a tree that is neither before nor
    after — and every later comparison against it is meaningless in a way
    that looks like real findings. Replaces check_cowork_nightly, the
    manifest-watching guard for the scheduled task R228 removed."""
    import circle_state as CS
    if not CS.is_circle_in_progress():
        run.ok("no circle is in progress")
        return
    msg = "a circle may be open (circle_state.py, which fails closed)"
    if writing:
        run.fail(msg + " — a snapshot taken mid-circle is neither a before "
                       "nor an after; wait for /close to finish")
    else:
        run.warn(msg)


def check_journal(run: Run) -> bool:
    """A JOURNAL means a previous commit was interrupted mid-swap (§3.3). Refuse
    to do anything until a human decides finish-or-roll-back."""
    found = T.find_journals(ROOT)
    if not found:
        return False
    for j in found:
        run.fail(f"leftover commit JOURNAL: {j.relative_to(ROOT).as_posix()} — a "
                 f"previous commit was interrupted part-way through the file swap")
        try:
            _, states = T.journal_report(j)
        except (OSError, ValueError) as e:
            print(f"          journal unreadable: {e}")
            continue
        tally: dict[str, int] = {}
        for _, s in states:
            tally[s] = tally.get(s, 0) + 1
        print(f"          {len(states)} file(s): "
              + ", ".join(f"{n} {k}" for k, n in sorted(tally.items())))
        for rel, s in states:
            if s not in ("old", "new"):
                print(f"            {s.upper():<7} {rel}")
    print("\n  The live tree is part-swapped. Both repairs are deterministic —")
    print("  every file's state is known from its sha256:")
    print("    python coordinator\\circle_audit.py --journal-status")
    print("    python coordinator\\circle_audit.py --journal-finish     # complete it")
    print("    python coordinator\\circle_audit.py --journal-rollback   # undo it")
    return True


def _logger(run: Run):
    marks = {"ok": "  OK    ", "did": "  DID   ", "warn": "  WARN  ",
             "note": "          ", "fail": "  FAIL  "}

    def log(kind, msg):
        print(f"{marks[kind]}{msg}")
        if kind == "fail":
            run.failures.append(msg)
    return log


def journal_command(run: Run, action: str) -> int:
    hr(f"journal — {action}")
    found = T.find_journals(ROOT)
    if not found:
        run.ok("no JOURNAL present; nothing to resolve")
        return 0
    log = _logger(run)
    for j in found:
        try:
            jdoc, states = T.journal_report(j)
        except ValueError as e:
            # A journal that will not parse: report it (with the repair
            # guidance journal_report carries), keep reporting any OTHER
            # journals, and fail the command — never a raw traceback out
            # of the one tool built to diagnose exactly this state.
            run.fail(str(e))
            continue
        print(f"  {j.relative_to(ROOT).as_posix()}  (created {jdoc['created']})")
        for rel, s in states:
            print(f"    {s.upper():<7} {rel}")
        if action == "status":
            continue
        ok = (T.journal_finish(j, log) if action == "finish"
              else T.journal_rollback(j, log))
        if not ok:
            return 1
    return 1 if run.failures else 0


def take_lock(run: Run) -> bool:
    WORK.mkdir(parents=True, exist_ok=True)
    if LOCK.is_file():
        try:
            info = json.loads(LOCK.read_text(encoding="utf-8"))
            age = datetime.datetime.now().timestamp() - info.get("started", 0)
        except (OSError, ValueError):
            info, age = {}, LOCK_STALE_SEC + 1
        if age < LOCK_STALE_SEC:
            run.fail(f"another run holds the lock (pid {info.get('pid')}, "
                     f"{age / 60:.0f} min old): {LOCK.relative_to(ROOT).as_posix()}")
            return False
        run.warn(f"stale lock ({age / 3600:.1f} h) — taking it over")
    LOCK.write_text(json.dumps(
        {"pid": os.getpid(), "started": datetime.datetime.now().timestamp(),
         "argv": sys.argv[1:]}), encoding="utf-8", newline="")
    return True


def release_lock() -> None:
    """Unlink the lock ONLY if this process wrote it. Until 2026-08-19 this
    was an unconditional unlink, and main()'s phase-0 failure path calls it
    — so a run that LOST the lock race (take_lock refused, phase0 False)
    deleted the winning run's live lock on its way out, and a third run
    could then start phases 7-9 concurrently with the first. A lock that
    does not parse is left in place: take_lock() already treats an
    unreadable lock as stale after LOCK_STALE_SEC, so it self-heals."""
    try:
        info = json.loads(LOCK.read_text(encoding="utf-8"))
        if info.get("pid") != os.getpid():
            return
        LOCK.unlink()
    except (OSError, ValueError):
        pass


def phase0(run: Run, may_commit: bool, writing: bool = False) -> bool:
    hr("phase 0 — preflight")
    if check_journal(run):
        return False
    if not take_lock(run):
        return False
    check_circle_open(run, writing)
    check_git(run, may_commit)
    # WAS scripts/preflight_check.py until 2026-08-18. That script was the
    # agent-teams-era circle-open guard; its agent/team/temp checks died with that
    # runtime, and the one part still worth running — the NUL/UTF-8/JSON sweep —
    # is now coordinator/check_integrity.py, which also covers .toml and issues/
    # and runs at circle open as well as here. Still a subprocess rather than an
    # import: phase 0 reports a returncode, and a gate that can take the whole
    # audit down with it on an unexpected raise is not a gate.
    script = ROOT / "coordinator" / "check_integrity.py"
    if not script.is_file():
        run.fail(f"missing {script.relative_to(ROOT).as_posix()}")
    else:
        p = subprocess.run([sys.executable, str(script)], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8")
        tail = [l for l in p.stdout.splitlines() if l.strip()][-1:] or [""]
        (run.ok if p.returncode == 0 else run.fail)(f"check_integrity.py: {tail[0].strip()}")
        if p.returncode != 0:
            for line in p.stdout.splitlines()[1:]:
                if line.strip():
                    print(f"          {line.rstrip()}")
    return not run.failures


# ------------------------------------------------------------------ phase 1
def phase1(run: Run) -> list[str]:
    """Unprocessed = in scope and carrying no dream/<OT> tag. The scope EPOCH
    is the oldest dream tag: circles older than it are the retired batch
    nightly's era, out of audit scope by ruling (2026-08-19). Deleting the
    oldest tag — inter_circle's own "delete the tag first if you mean it"
    re-run path — therefore shifts the epoch backward and pulls legacy
    circles into scope; a deliberate first-circle re-dream is the only
    honest reason to do that."""
    hr("phase 1 — survey")
    tags, err = dream_tags()
    if err:
        run.fail(f"survey refused: {err} — cannot tell which circles are "
                 f"processed, and guessing would report every circle "
                 f"unprocessed")
        return []
    circles = sorted(m.group(1) for p in (ROOT / "circles").glob("circle_*.md")
                     if (m := CIRCLE_RE.match(p.name)))
    if not tags:
        run.warn(f"no dream/<OT> tags exist — inter_circle.py has processed "
                 f"nothing yet; all {len(circles)} circles on disk predate it "
                 f"and are out of audit scope")
        return []
    epoch = tags[0]
    processed = set(tags)
    legacy = [c for c in circles if c < epoch]
    inscope = [c for c in circles if c >= epoch]
    unprocessed = [c for c in inscope if c not in processed]
    if legacy:
        run.ok(f"{len(legacy)} circle(s) predate the first dream tag ({epoch}) "
               f"— batch-nightly era, out of audit scope")
    if not unprocessed:
        run.ok(f"{len(inscope)} circle(s) in scope, every one carries its "
               f"dream/<OT> tag")
    else:
        run.ok(f"{len(inscope)} circle(s) in scope, {len(unprocessed)} not yet "
               f"processed by inter_circle.py (re-run entry: "
               f"python coordinator/inter_circle.py --ot <OT> --live):")
        for c in unprocessed:
            print(f"          circle_{c}.md")
    return unprocessed


# ------------------------------------------------------------------ phase 2
# spoke_in / the backfill prompt / missing_short_terms MOVED to backfill.py,
# B54 2026-08-19 — the detect and repair halves were entangled with this
# file's phase structure and callable by nothing else, while the path that
# needed them most (inter_circle.process_circle(), every live /close) had no
# way to reach either. One implementation, two drivers.
spoke_in = BF.spoke_in
BACKFILL_PROMPT = BF.BACKFILL_PROMPT
BACKFILL_MAX_TOKENS = BF.BACKFILL_MAX_TOKENS


def phase2(run: Run, unprocessed: list[str]) -> None:
    """Reconcile each unprocessed circle, then apply the transcript safety net:
    any part that SPOKE but has no well-formed short_term must be backfilled
    before dreaming reads it as no-engagement. A silent part is exempt."""
    hr("phase 2 — reconcile + transcript safety net")
    if not unprocessed:
        run.ok("nothing to reconcile")
        return
    cc = ROOT / "coordinator" / "circle_close.py"
    for ot in unprocessed:
        print(f"\n  circle_{ot}")
        p = subprocess.run([sys.executable, str(cc), "--reconcile", "--open-time", ot],
                           cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
        for line in p.stdout.splitlines():
            if line.strip() and not line.startswith("Circle-close"):
                print(f"      {line.strip()}")
        if p.returncode != 0:
            run.fail(f"circle_{ot}: RECONCILE-DRIFT — short_terms recorded at close "
                     f"are absent or changed on disk; phase 3 must backfill them")

        counts = spoke_in(ROOT / "circles" / f"circle_{ot}.md")
        if not counts:
            run.fail(f"circle_{ot}: transcript has no parseable statements")
            continue
        need = []
        for part, n in sorted(counts.items()):
            st = ROOT / "parts" / part / f"short_term_{ot}.md"
            text, findings = M.check_file(st.as_posix(), M.read_bytes(st))
            if text is None:
                need.append((part, n, findings[0].message if findings else "missing"))
                continue
            absent = [h for h in M.SHORT_TERM_SECTIONS if h not in text]
            if absent:
                need.append((part, n, f"malformed (no '{absent[0]}')"))
        if need:
            for part, n, why in need:
                run.fail(f"circle_{ot}: {part} spoke {n}x but short_term is {why} "
                         f"— backfill from the transcript before dreaming")
        else:
            run.ok(f"circle_{ot}: all {len(counts)} speaking parts have a "
                   f"well-formed short_term")
        silent = [p for p in M.PARTS if p not in counts]
        if silent:
            print(f"      (silent, correctly no short_term: {', '.join(silent)})")


# ------------------------------------------------------------------ phase 6
def snapshot(dest: pathlib.Path) -> pathlib.Path:
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in M._tree_files(ROOT):
        if not p.is_file():
            continue
        out = dest / p.relative_to(ROOT)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        n += 1
    for p in (ROOT / "self").glob("narrative_*.md"):
        out = dest / "self" / p.name
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        n += 1
    # Record WHERE in the circle stream this snapshot sits. Without it, a
    # baseline taken after inter_circle already processed a circle looks
    # identical to one taken before, and the resulting "no changes" reads as
    # a clean window rather than as a comparison that never had anything to
    # compare.
    import circle_state as CS
    tags, err = dream_tags()
    (dest / "SNAPSHOT.json").write_text(json.dumps({
        "taken": datetime.datetime.now().isoformat(timespec="seconds"),
        "files": n,
        "latest_dream_tag": (tags[-1] if tags else None) if not err else None,
        "dream_tag_error": err,
        "circle_in_progress": CS.is_circle_in_progress(),
        "circles_on_disk": len(list((ROOT / "circles").glob("circle_*.md"))),
        "sha256": {p.relative_to(dest).as_posix(): M.sha(p.read_bytes())
                   for p in sorted(dest.rglob("*.md"))},
    }, indent=2) + "\n", encoding="utf-8", newline="")
    return dest


def describe_window(run: Run, baseline: pathlib.Path) -> None:
    """Say plainly whether inter_circle.py actually processed a circle between
    the snapshot and now. 'No differences' means two completely different
    things depending on the answer, and only one of them is good news."""
    info_path = baseline / "SNAPSHOT.json"
    if not info_path.is_file():
        run.warn(f"{baseline.name} has no SNAPSHOT.json — cannot tell whether "
                 f"any circle was processed since it was taken")
        return
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        run.warn(f"SNAPSHOT.json unreadable ({e})")
        return
    then = info.get("latest_dream_tag")
    tags, err = dream_tags()
    if err:
        run.warn(f"cannot read dream/<OT> tags now ({err}) — the window below "
                 f"is unknown")
        return
    now = tags[-1] if tags else None
    print(f"  snapshot taken   {info.get('taken')}")
    print(f"  latest dream/<OT> tag at snapshot: {then}")
    print(f"  latest dream/<OT> tag now:         {now}")
    if info.get("dream_tag_error"):
        run.warn(f"the snapshot itself could not read the tags when taken "
                 f"({info['dream_tag_error']}) — its baseline position is "
                 f"unknown")
    if info.get("circle_in_progress"):
        run.warn("a circle may have been open when this snapshot was taken — "
                 "it is neither a before nor an after; take a fresh one")
    if now == then:
        run.warn("inter_circle.py has processed NO circle since this snapshot. "
                 "Any 'unchanged' result below is trivially true and proves "
                 "nothing about the processing.")
    else:
        run.ok(f"circle processing advanced in this window ({then} -> {now}) "
               f"— the comparison below is meaningful")


def phase6(run: Run, baseline: pathlib.Path | None) -> None:
    hr("phase 6 — validate" + (f" (baseline: {baseline})" if baseline else " (self-check)"))
    if baseline:
        describe_window(run, baseline)
        print()
    findings = (M.compare_trees(baseline, ROOT) if baseline
                else M.selfcheck_tree(ROOT))
    for f in findings:
        if f.level != "OK" or baseline:
            print(f)
    nf, nw, no = M.summarise(findings)
    print(f"\n  {nf} FAIL · {nw} WARN · {no} OK")
    for f in findings:
        if f.level == "FAIL":
            run.failures.append(f"{f.path}: {f.code}")
    if not baseline and nw:
        print("\n  Self-check WARNs describe the tree as it stands today, not a run.")
        print("  RECENCY-DERIVED is not a problem: an entry with no *Last mentioned:*")
        print("  anchors to its own dream date (NIGHTLY_DESIGN §10). TOMBSTONE is --")
        print("  the entry's body was lost and only its header survives.")


# ------------------------------------------------------------------ phase 3
# A four-section short_term is a substantially harder generation than a 120-word
# circle statement, and thinking is billed against this ceiling. 2,000 was sized
# for the answer; this is sized for the answer plus the work.



def missing_short_terms(unprocessed: list[str]) -> list[tuple[str, str, int]]:
    """(open_time, part, statements) for every part that SPOKE and has no
    well-formed record, across these circles. The per-circle answer is
    backfill.needs_backfill(); this is the sweep shape phase 3 wants."""
    return [(ot, part, n)
            for ot in unprocessed
            for part, n, _why in BF.needs_backfill(ot)]


def phase3(run: Run, tx, unprocessed: list[str], dry: bool) -> int:
    """Reconstruct lost short_terms from the transcript, into staging.

    The transcript is the authoritative account of what was said, so a part that
    spoke is never read as silent. This is the procedure we ran by hand on
    2026-07-26 for four parts of circle_2026-07-26_1112, now mechanised — with the
    same rule: write ONLY the short_term. Never long_term.md, never any other
    per-part file."""
    hr("phase 3 — backfill")
    todo = missing_short_terms(unprocessed)
    if not todo:
        run.ok("every part that spoke has a well-formed short_term")
        return 0
    for ot, part, n in todo:
        run.warn(f"circle_{ot}: {part} spoke {n}x with no usable record")
    if dry:
        print(f"\n  --dry-run: {len(todo)} backfill(s) would be generated, "
              f"~${BF.estimate_cost(len(todo)):.2f} at today's rates")
        return 0

    import prompt_build as C   # the prompt construction (phase 2 stage 2;
                               # was circle) — same identity assembly as a circle
    import llm_client as LC                  # MODEL's owner (phase 2 stage 1)
    client = LC.build_client()               # one builder, 2026-08-28 (stage 1)
    # PRE-EXISTING BREAK, fixed 2026-08-13 (found while removing the retired
    # OC register): load_shared() stopped returning a 3-tuple and
    # shared_block()'s third positional arg became `minimal`, some time
    # before this file's own last edit; nothing had executed phase3() since,
    # so check_lint.py's compile-only pass never caught it. Mirrors the
    # identical fix already applied in midterms_project.py:146-147.
    core = C.load_shared()
    briefing, _ = C.build_briefing([], False)
    done = 0
    for ot, part, n in todo:
        shared, _ = C.shared_block(part, briefing, False)
        system = C.system_blocks(part, core, shared)

        def _call(system_, user_, max_tokens):
            """circle_audit's own client, in the one shape backfill.py takes.
            inter_circle hands it `_call` instead — same function, two model
            paths, so neither driver has to adopt the other's client.

            THROUGH THE TRANSPORT SINCE 2026-08-28 (stage 1). `system_` is a
            LIST OF BLOCKS here, not a string — this is the one caller that
            assembles a real part prompt — and call_once passes it through
            untouched, as the transport always has."""
            return LC.call_once(system_, user_, max_tokens,
                                kind="backfill", client=client)

        text, err = BF.reconstruct(part, ot, C.PART_TAGS[part], system, _call)
        if err:
            run.fail(f"{part}/{ot}: {err} Nothing staged for this part.")
            continue
        rel = f"parts/{part}/short_term_{ot}.md"
        tx.stage(rel, text.encode("utf-8"))
        run.ok(f"staged {rel} ({len(text.split())} words, RECONSTRUCTED)")
        done += 1
    return done


# ------------------------------------------------------------------ phases 7-9
def stage_synthetic(tx: T.Transaction, run: Run) -> None:
    """A stand-in for phases 3-5, so the transaction can be exercised end
    to end with no model calls and no cost: one legal append to the
    observation log, gated as any real change would be.

    ONE FILE, deliberately (2026-08-19, review tier 2 #17). This used to
    also stage a fake [[dreams]] record into parts/judge/dreams.toml —
    written when the register gate did not yet see TOML, with a docstring
    admitting the change was "committed unchecked". The gate then learned
    the registers (R188) and declared parts/*/dreams.toml FROZEN (R178:
    nothing writes it), so the synthetic run's own staging became a
    guaranteed phase-6 FAIL FROZEN and --stage-synthetic could never
    reach phases 7-9 at all — the docstring and the mechanism had swapped
    truths. The multi-file swap, the crash states between replaces, and
    both journal repairs are covered by coordinator/tests/test_transaction.py
    against throwaway trees; what THIS path uniquely rehearses is the
    real tree, the real gate, and the real phase-6-through-9 plumbing,
    which one observation-log append exercises whole."""
    today = datetime.date.today().isoformat()
    # A REAL RECORD, not a raw append (2026-08-19, R256). The
    # log is a TOML register now, and the register gate refuses anything
    # that is not a dumps() fixed point with the next id in sequence — so
    # the rehearsal has to mint one properly or phase 6 FAILs on the
    # rehearsal itself rather than on what it is rehearsing. CONSEQUENCE,
    # stated because it is real: a synthetic run that reaches phases 7-9
    # CONSUMES an SO- id. The text says so, so the record self-identifies.
    doc, _rec = SO.render_new(
        SO._doc(), f"synthetic-{today}",
        f"Synthetic transaction test: {today}. Not an observation — "
        f"circle_audit.py --stage-synthetic wrote this to rehearse phases "
        f"6-9 against the real tree and the real gate.")
    tx.stage("self/self_observation_log.toml",
             SS.dumps(doc, SO.TABLE, SO.ORDER).encode("utf-8"))
    run.ok(f"staged {len(tx.staged())} synthetic file(s) "
           f"(stand-in for phases 3-5)")


def phase7_9(run: Run, tx: T.Transaction, findings: list, do_git: bool) -> bool:
    """7 commit · 8 verify · 9 record. Nothing here runs if phase 6 failed."""
    if any(f.level == "FAIL" for f in findings):
        run.fail("phase 6 found FAILures — refusing to commit. The live tree is "
                 "untouched; staging is kept for inspection.")
        return False
    changed = tx.changed()
    if not changed:
        run.ok("staged output is identical to the live tree — nothing to commit")
        return True

    hr("phase 7 — commit")
    log = _logger(run)
    print(f"  {len(changed)} file(s) to replace:")
    for rel in changed:
        print(f"      {rel}")
    if not tx.commit(log):
        return False
    # No argument since 2026-08-19: the record carries commit()'s own
    # staging-derived hashes, so phase 8 compares the disk against the
    # INTENT rather than against a re-read of itself.
    tx.record_committed()

    hr("phase 8 — verify")
    if not tx.verify(log):
        run.fail("post-commit verification failed — see the rollback copies")
        return False

    hr("phase 9 — record")
    if do_git:
        G.commit_paths([ROOT / r for r in changed],
                       f"circle_audit {tx.run_id}: {len(changed)} file(s)", log,
                       tag=f"audit/{tx.run_id}")
    else:
        run.warn("--no-git: committed to disk but not to git")
    log_run("commit", "ok", f"{len(changed)} file(s) committed")
    return True


# ------------------------------------------------------------------ baselines/log
RUN_LOG = ROOT / "work" / "logs" / "circle_audit.log"
KEEP_BASELINES = 14


def resolve_baseline(arg: str | None) -> pathlib.Path | None:
    """--baseline last  ->  the newest work/circle_audit/baseline_* directory,
    so a caller need not know the timestamp the snapshot run chose."""
    if not arg:
        return None
    if arg.lower() in ("last", "latest", "auto"):
        cands = sorted((d for d in WORK.glob("baseline_*") if d.is_dir()),
                       key=lambda d: d.name)
        return cands[-1] if cands else None
    return pathlib.Path(arg)


def prune_baselines(keep: int = KEEP_BASELINES) -> int:
    old = sorted((d for d in WORK.glob("baseline_*") if d.is_dir()),
                 key=lambda d: d.name)[:-keep]
    for d in old:
        shutil.rmtree(d, ignore_errors=True)
    return len(old)


class Tee:
    """Mirror stdout to a file, so a run's detailed findings survive somewhere
    durable and not only in a console's scrollback — without it, only the
    one-line summary in circle_audit.log survives an unattended run."""

    def __init__(self, path: pathlib.Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(path, "w", encoding="utf-8", newline="\n")
        self.out = sys.stdout
        # main() has many return paths; register once rather than guard each.
        atexit.register(self.close)

    def write(self, s):
        self.out.write(s)
        self.f.write(s)

    def flush(self):
        self.out.flush()
        self.f.flush()

    def close(self):
        self.f.close()


def log_run(mode: str, result: str, detail: str) -> None:
    """One line per run, so a week of audit runs can be read at a glance."""
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG, "a", encoding="utf-8", newline="\n") as f:
        f.write(f"{datetime.datetime.now():%Y-%m-%d_%H%M}  {mode:<9} "
                f"{result:<7} {detail}\n")


# Task Scheduler install/uninstall (TASK_XML, TASKS, task_defs(), install_tasks(),
# uninstall_tasks()) REMOVED WHOLESALE 2026-08-15 — see RULINGS.md and
# docs/NIGHTLY_DESIGN.md's own §7 retirement note. It existed to snapshot/validate
# around the separate, since-retired ifs-nightly Cowork task; nothing schedules
# dreaming/synthesis any more (docs/INTER_CIRCLE_DESIGN.md's Placement ruling —
# synchronous at /close).


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(
        description="circle-record audit — phases 0-2 and 6 by default (no "
                    "writes to the live tree, no model calls)")
    ap.add_argument("--snapshot", nargs="?", const="auto", metavar="DIR",
                    help="copy the current parts/ + self/ memory files to DIR "
                         "(default work/circle_audit/baseline_<timestamp>) and exit")
    ap.add_argument("--baseline", metavar="DIR",
                    help="validate the live tree against this snapshot instead of "
                         "self-checking it")
    ap.add_argument("--validate", action="store_true",
                    help="run phases 0, 1, 2, 6 (the default) and NOTHING else "
                         "— refuses if combined with a flag that selects "
                         "another path")
    ap.add_argument("--selfcheck", action="store_true",
                    help="phase 6 only, no lock, no git, no reconcile")
    ap.add_argument("--git-setup", action="store_true",
                    help="idempotent git bootstrap: init, config, .gitattributes, "
                         ".gitignore, un-track ignored paths. Never adds a remote, "
                         "never rewrites history, never stages the whole tree.")
    # NO DEFAULTS HERE. Identity is configuration: the flag, else
    # $IFS_GIT_NAME/$IFS_GIT_EMAIL (shell or .env), else git's own
    # user.name/user.email, else unset — gitrepo.resolve_identity().
    # See docs/configuration.md.
    ap.add_argument("--git-name", default=None,
                    help="git user.name for --git-setup. Default: "
                         f"${G.ENV_GIT_NAME}, then git's own config.")
    ap.add_argument("--git-email", default=None,
                    help="git user.email for --git-setup. Default: "
                         f"${G.ENV_GIT_EMAIL}, then git's own config.")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --backfill: report what would be generated (and an "
                         "estimated cost) without calling the model")
    ap.add_argument("--prune-baselines", action="store_true",
                    help=f"delete all but the newest {KEEP_BASELINES} snapshots")
    ap.add_argument("--all-circles", action="store_true",
                    help="with --backfill: scan EVERY circle, not only the "
                         "unprocessed ones. A short_term lost after its circle was "
                         "already dreamed is invisible to the normal scope, since "
                         "nothing revisits a processed circle.")
    ap.add_argument("--backfill", action="store_true",
                    help="phase 3: reconstruct any short_term that is missing or "
                         "malformed for a part that spoke. Stages only; add "
                         "--commit to write.")
    ap.add_argument("--stage-synthetic", action="store_true",
                    help="stage one legal synthetic change, so phases 6-9 can "
                         "be exercised with no model calls")
    ap.add_argument("--commit", action="store_true",
                    help="run phases 7-9 (commit, verify, record). Without this "
                         "the run stops after validation and writes nothing.")
    ap.add_argument("--no-git", action="store_true",
                    help="with --commit: write to disk but do not git-commit")
    ap.add_argument("--journal-status", action="store_true")
    ap.add_argument("--journal-finish", action="store_true",
                    help="complete an interrupted swap from staging")
    ap.add_argument("--journal-rollback", action="store_true",
                    help="undo an interrupted swap from the rollback copies")
    ap.add_argument("--log", action="store_true",
                    help="mirror all output to "
                         "work/logs/circle_audit_<timestamp>.log")
    args = ap.parse_args()

    run = Run()
    started = datetime.datetime.now()
    tee = None
    if args.log:
        tee = Tee(ROOT / "work" / "logs"
                  / f"circle_audit_{started:%Y-%m-%d_%H%M}.log")
        sys.stdout = tee
    print(f"circle audit — phases 0-2, 6 — {started:%Y-%m-%d %H:%M}")
    print(f"project: {ROOT}")

    for flag, action in (("journal_status", "status"), ("journal_finish", "finish"),
                         ("journal_rollback", "rollback")):
        if getattr(args, flag):
            return journal_command(run, action)

    if args.git_setup:
        return git_setup(run, args.git_name, args.git_email)

    if args.selfcheck:
        phase6(run, None)
        return 1 if run.failures else 0

    # --validate IS READ NOW, 2026-08-27. It was a documented argparse flag
    # that `main()` never consulted anywhere in its dispatch chain: bare
    # already fell through to phases 0/1/2/6, so the flag changed nothing
    # whether given or not, while its help text implied it selected a mode.
    # Worse than decoration, because `--validate --backfill` ran the
    # BACKFILL and said nothing — the flag lost silently to whichever other
    # flag was present.
    #
    # HONOURED RATHER THAN DELETED. It ships: circle_audit.py is listed
    # file-by-file in packaging/required.toml, so removing a documented flag
    # from a shipped CLI breaks anyone who typed it. Selecting the default
    # path explicitly, and refusing a combination that would silently
    # override it, makes the help text true without taking anything away.
    _OTHER_PATHS = ("snapshot", "backfill", "stage_synthetic", "commit")
    if args.validate:
        clash = [f"--{x.replace('_', '-')}" for x in _OTHER_PATHS
                 if getattr(args, x)]
        if clash:
            # run.fail() prints it; a second print here said it twice.
            run.fail(f"--validate runs phases 0, 1, 2, 6 and nothing else; "
                     f"{', '.join(clash)} selects a different path. Give one "
                     f"or the other.")
            return 1

    # may_commit follows --commit: check_git's docstring says the git
    # preconditions are "ENFORCED only when the run could write to the live
    # tree", but until 2026-08-19 this call pinned may_commit=False, so
    # exactly the runs that swap files (--backfill --commit,
    # --stage-synthetic --commit) got "git unavailable / not a repository /
    # dirty tree" as warnings and proceeded with no revert target.
    if not phase0(run, may_commit=bool(args.commit),
                  writing=bool(args.snapshot)):
        release_lock()
        return 2 if any("JOURNAL" in f for f in run.failures) else 1
    try:
        if args.snapshot:
            dest = (WORK / f"baseline_{started:%Y-%m-%d_%H%M}") \
                if args.snapshot == "auto" else pathlib.Path(args.snapshot)
            hr("snapshot")
            snapshot(dest)
            info = json.loads((dest / "SNAPSHOT.json").read_text(encoding="utf-8"))
            run.ok(f"{info['files']} files -> {dest}")
            log_run("snapshot", "ok", f"{info['files']} files -> {dest.name}")
            print(f"\n  Validate against it later:")
            print(f"    python coordinator\\circle_audit.py --baseline last")
            return 0

        unprocessed = phase1(run)
        phase2(run, unprocessed)

        if args.backfill:
            tx = T.Transaction(ROOT, f"{started:%Y-%m-%d_%H%M}")
            scope = unprocessed
            if args.all_circles:
                scope = sorted(m.group(1) for f in (ROOT / "circles").glob("circle_*.md")
                               if (m := CIRCLE_RE.match(f.name)))
                run.warn(f"--all-circles: scanning all {len(scope)} circles. A "
                         f"backfill for an ALREADY-PROCESSED circle repairs the "
                         f"record but does not re-run its dreaming — see process.md "
                         f"'short_term backfill'.")
            phase3(run, tx, scope, args.dry_run)
            if tx.staged():
                hr("phase 6 — validate (staged candidate vs live)")
                findings = tx.validate()
                for f in findings:
                    if f.level != "OK":
                        print(f)
                nf, nw, no = M.summarise(findings)
                print(f"\n  {nf} FAIL · {nw} WARN · {no} OK "
                      f"(long_term/relationships/self untouched, as expected)")
                for f in findings:
                    if f.level == "FAIL":
                        run.failures.append(f"{f.path}: {f.code}")
                if args.commit:
                    phase7_9(run, tx, findings, do_git=not args.no_git)
                else:
                    run.ok(f"{len(tx.staged())} backfill(s) staged in "
                           f"{tx.staging.relative_to(ROOT).as_posix()} — "
                           f"add --commit to write them")
        elif args.stage_synthetic or args.commit:
            # Nothing real to stage on this path (backfill has its own branch;
            # dream/synthesise live in inter_circle.py) — --stage-synthetic
            # substitutes a legal change so phases 6-9 can be exercised.
            tx = T.Transaction(ROOT, f"{started:%Y-%m-%d_%H%M}")
            hr("stage (synthetic)")
            if args.stage_synthetic:
                stage_synthetic(tx, run)
            if not tx.staged():
                run.fail("nothing staged — use --stage-synthetic to exercise "
                         "the transaction, or --backfill for a real repair")
            else:
                hr("phase 6 — validate (staged candidate vs live)")
                findings = tx.validate()
                for f in findings:
                    if f.level != "OK":
                        print(f)
                nf, nw, no = M.summarise(findings)
                print(f"\n  {nf} FAIL · {nw} WARN · {no} OK")
                for f in findings:
                    if f.level == "FAIL":
                        run.failures.append(f"{f.path}: {f.code}")
                if args.commit:
                    phase7_9(run, tx, findings, do_git=not args.no_git)
                else:
                    run.ok("validation only — pass --commit to run phases 7-9")
        else:
            base = resolve_baseline(args.baseline)
            if args.baseline and base is None:
                run.fail("--baseline last: no work/circle_audit/baseline_* "
                         "snapshot exists")
            elif base and not base.is_dir():
                run.fail(f"baseline directory not found: {base}")
                base = None
            phase6(run, base)
        if args.prune_baselines:
            n = prune_baselines()
            run.ok(f"pruned {n} old snapshot(s), keeping {KEEP_BASELINES}")
    finally:
        release_lock()

    log_run("validate" if args.baseline else "check",
            "FAIL" if run.failures else "ok",
            f"{len(unprocessed)} unprocessed circle(s); "
            + (f"{len(run.failures)} failure(s)" if run.failures else "all checks passed"))

    hr("result")
    if run.failures:
        print(f"  {len(run.failures)} FAILURE(S):")
        for f in run.failures:
            print(f"    - {f}")
        print("\n  Nothing was written to the live tree — phases 7-9 run only")
        print("  behind --commit, and a phase-6 FAIL refuses them anyway.")
        return 1
    print("  all checks passed")
    print(f"  ({(datetime.datetime.now() - started).total_seconds():.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
