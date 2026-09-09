#!/usr/bin/env python3
"""
inter_circle.py — the INTER_CIRCLE_PROCESSOR (R163: "between, not
cross"). DREAMING then SYNTHESIS for one closed circle, run synchronously
as `/close`'s SECOND phase (R167: the circle itself is already committed
before this starts) or by hand:

    python coordinator/inter_circle.py --ot 2026-08-15_1900 --live
    python coordinator/inter_circle.py --ot 2026-08-15_1900          (rehearse)

The bare form is the REHEARSAL: real model calls, real staging, the real
register gate — and then a report instead of a commit, staging kept for
inspection. `--live` commits. The `--ot` form IS R168's manual re-run
entry point: the same code `/close` calls, pointed at a closed circle.

THE SHAPE (docs/REGISTER_GATE_DESIGN.md, approved R188 — phase 2 writes
NOTHING directly):

    1  DREAMING     one model call per part, ALL PARTS IN PARALLEL (R170);
                    each RETURNS a payload — at most one memory — and
                    writes nothing. part_relationships.toml is NOT part
                    of this payload — see "part_relationships is INERT,"
                    below.
    2  SYNTHESIS    one circle-wide call, five inputs (R183 + R179 + R186):
                    transcript, each part's fresh dreaming record,
                    confirmed proposals, current self.md, the prior
                    CIRCLE_HISTORY entry
    3  VALIDATE     every payload against the writer-scope matrix and each
                    register's own rules (caps refuse, headings must hold)
    4  RENDER+STAGE each register module renders baseline + its own tail
                    (render_dreamt/render_new/render_stage — the same code
                    the direct writers use); Transaction stages the bytes
    5  GATE         register_gate.record_tree_compare — the register gate judges
                    baseline vs candidate; any FAIL leaves the tree
                    untouched, staging kept
    6  COMMIT       Transaction.commit, then mid_term --refresh for the
                    parts whose hashes the writes flipped (R186/H3 — the
                    one direct-write step, guarded by mid_term's own
                    SUSPECT checks and hash stamp), then ONE git commit

FAILURE (R168): no automated catch-up. A failure writes
work/logs/dream_error_<OT>.json, makes ONE diagnostic model call (its own
failure is survived), prints the diagnosis and the re-run line, and exits
non-zero. All-or-nothing staging means a failed run wrote NOTHING, so the
re-run is clean by construction — no run markers, no author fields.

PRIVACY, mechanical: SYNTHESIS's input carries each part's ONE fresh
dreaming record, handed over in-process from the DREAMING payloads —
SYNTHESIS never reads any remember.toml, and the writer-scope matrix
(steps 3-4 stage only what a row grants) is enforced by construction
here and verified by the gate after.

LIVE-ONLY: non-live circles are skipped by the caller —
SYNTHESIS writes self/, which no sandbox may touch.

part_relationships IS INERT, 2026-08-22 (the operator: "inactivate all
code writing part_relationships.toml. Leave it in place and patch it out;
no LLM call(s)."). Follows R302, which had already removed the BLOCK 3
READ — this removes the WRITE too, so no part of DREAMING's prompt or
output spends any attention on it any more. part_relationships.py, the
seven parts/*/part_relationships.toml files, and register_gate.REGISTERS'
own entry for the register are UNTOUCHED — a part's LAST converged
record from before this change simply stops updating. See NEXT.md,
"part-relationships-unconsumed," for what becomes of the register
itself.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import REGISTER_CLASS as SS                                       # noqa: E402
import record_paths as _RP                                         # noqa: E402
import remember_manager as RM                                          # noqa: E402
import topic_manager as TOP                                           # noqa: E402
import circle_history_manager as CH                                    # noqa: E402
import circle_observation_manager as CO                              # noqa: E402
import circle_journal_manager as CJ                                 # noqa: E402  B94 stage 4
import practice_manager as PM                             # noqa: E402
import part_mid_term_manager as MT                                          # noqa: E402
import TRANSACTION_CLASS as T                                        # noqa: E402
import part_roster as R                                             # noqa: E402
import backfill as BF                                          # noqa: E402  (B54)
import llm_client as LC                                        # noqa: E402  MODEL's owner
import LLM_response_disassembler as RD                         # noqa: E402  every read
                                                               # of a reply (2026-09-02)
import setting_manager as SET                                         # noqa: E402
import part_dreaming as PD                                     # noqa: E402  DREAMING, and the
                                                               # shared _call (stage 11)
import circle_synthesis as SYN                                 # noqa: E402  SYNTHESIS (stage 11)
import phase_clock as PC                                       # noqa: E402  wall-clock
                                                               # per phase (2026-08-30)
import prompt_capture as PCAP                                  # noqa: E402  the circle's
                                                               # capture (R412/R413)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# IMPORTED, NOT COPIED (2026-08-28, R379). This said
# `"claude-sonnet-5"  # circle.MODEL — the parts' own model`: a comment naming
# the owner, beside a literal that did not read from it. Dreaming and synthesis
# must run on the same model the parts spoke on, and that is now true by
# construction rather than by two files agreeing: read as LC.MODEL at the
# use (a local MODEL alias stood here until 2026-09-03).
# THE TWO CAPS AND THE TWO PROMPTS MOVED OUT, 2026-09-03 (cohesion re-homing stage
# 11): DREAM_MAX_TOKENS and DREAMING_PROMPT_V1 to part_dreaming.py, SYNTH_MAX_TOKENS,
# SYNTHESIS_PROMPT_V2, SYN_HEADERS and _INSIST to circle_synthesis.py, with the
# passes that use them. This file is the DRIVER: the diagnostic, the marker, the
# capture, the transaction and the commit.
# IMPORTED, NOT COPIED (2026-08-28) — the diagnostic call is a few
# paragraphs, and coalesce's grouping pass a few lines, but the number is set
# by thinking headroom in both. Read as LC.AUX_MAX_TOKENS at the diagnostic
# call (a local DIAG_MAX_TOKENS alias stood here until 2026-09-03).

DIAGNOSIS_PROMPT = """\
A between-circles processing run (DREAMING/SYNTHESIS) failed. Below is its error
report. Give a plain-English DIAGNOSIS (what most likely went wrong) and a REPAIR
RECOMMENDATION (what to check or try). Diagnostic only — you repair nothing.
"""


# Module-level, rebindable — test_inter_circle.py points this at a temp dir
# so exercising the R168 failure path cannot overwrite or delete a REAL
# dream_error_<OT>.json. It writes under a real circle's OT by necessity (the
# driver reads the transcript by that OT), so redirecting the WRITE is the
# only separation available. Same convention as topic_manager.PATH.
LOGS = ROOT / "work" / "logs"


def _shown(p: pathlib.Path) -> str:
    """Tree-relative when it is, absolute when it is not. LOGS is rebindable
    (probes point it at a temp dir), and a bare relative_to() raises there —
    which turned a clean probe run into a traceback inside the very error
    path it was exercising."""
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


class _Unparseable(RuntimeError):
    """A parse failure that CARRIES THE MODEL'S ACTUAL OUTPUT.

    The first rehearsal (2026-08-09_1520) failed on SYNTHESIS and the sample
    was discarded at the error return, so R168's diagnostic call was asked to
    explain an output it could not see. Its own first repair recommendation
    was "pull the raw synthesis output and inspect it" — which nothing had
    kept, and re-seeing it would have cost another 8 model calls.

    The raw text is written BESIDE the report as .txt rather than embedded in
    the JSON: it runs to tens of KB, and a report you must un-escape to read
    is a report nobody reads."""

    def __init__(self, msg: str, raw: str | None = None,
                 stop_reason: str | None = None,
                 output_tokens: int | None = None):
        super().__init__(msg)
        self.raw = raw
        self.stop_reason = stop_reason
        self.output_tokens = output_tokens


class _PostCommitFailed(RuntimeError):
    """The git commit failed AFTER Transaction.commit() already succeeded.

    DISTINCT from every other R168 failure in this module, which all happen
    BEFORE any live-tree write — their report's "the live tree is untouched"
    line is true for them and would be a LIE here. 2026-08-16: a live run
    against 2026-08-09_1520 hit exactly this (project_stats.py --check
    refused the commit) and `circle_process()` never checked
    `gitrepo.system_git_paths_commit()`'s return value at all — it printed "phase 2
    complete" and exited 0 on a run whose git commit never landed, while 25
    files sat modified and uncommitted in the live tree."""


# part_dream() -> part_dreaming.py, circle_synthesise() -> circle_synthesis.py, 2026-09-03
# (stage 11); this driver reads them as PD and SYN.

# ------------------------------------------------------------------ driver
def _stage_toml(tx: T.Transaction, rel: str, doc: dict, table: str,
                order: tuple[str, ...]) -> None:
    tx.stage(rel, SS.register_dumps(doc, table, order).encode("utf-8"))


def _load_or(p: pathlib.Path, empty: dict) -> dict:
    return SS.register_read(p) if p.is_file() else empty


def circle_is_processed(ot: str) -> bool:
    """Has phase 2 ALREADY run to completion for this circle? The second
    commit's own `dream/<OT>` tag is the durable marker — all-or-nothing
    staging makes a FAILED run leave nothing, so the tag exists exactly
    when a run succeeded. This is the run-marker H6 deliberately did not
    build into the records themselves; the tag carries it instead.

    Through gitrepo.system_git_run() since 2026-08-19 (review tier 2): the raw
    subprocess call had no timeout (git hung by AV = phase 2 blocked
    forever, before touching anything) and let a missing git binary raise
    a bare FileNotFoundError. And this guard must NEVER answer "not
    processed" because git itself failed — that answer double-dreams —
    so a nonzero rc raises rather than reading as False.

    TWO MARKERS SINCE 2026-08-24, EITHER OF WHICH REFUSES A RE-RUN. The
    operator ruled git OPTIONAL that day, so the tag can no longer be the
    only place this answer lives — a tree with no git history has nowhere
    to keep one. `work/logs/dream_<OT>.json` is the file form, written
    last by a successful run.

        marker file present         -> processed. No git consulted.
        no .git in the tree at all  -> the file is the WHOLE record, and it
                                       said no. A tree that never had a
                                       history cannot be hiding a tag.
        .git present, git answers   -> the tag, exactly as before.
        .git present, git does NOT
          answer                    -> RAISE, exactly as before.

    THE RAISE IS NOT WEAKENED, IT IS SCOPED. It was unconditional, and
    that is what broke: `git tag -l` exits 128 outside a repository, so a
    freshly installed bundle met this guard as an uncaught GitError and
    CRASHED every live /close after the transcript was already safely
    written (measured 2026-08-24 in a built bundle). The invariant the
    raise protects — never answer "not processed" because git FAILED —
    only has meaning where a tag could exist. Where `.git` is absent no
    tag can exist, so there is nothing to be wrong about; where `.git` is
    present and git still cannot answer, something is wrong and this
    refuses to guess, as it always did."""
    import gitrepo as G
    if circle_dream_marker_read(ot).is_file():
        return True
    if not circle_git_history_read():
        return False
    # THE READER USES THE SAME NAMER AS THE WRITER (B56(5), R245): in a
    # lab tree this asks about `dream/lab/<OT>`, which is what a lab run
    # writes. Asking about the plain name there would never find the
    # marker and would re-dream every run — the guard dead in exactly the
    # venue meant to rehearse it.
    tag = G.system_git_tag_name_read("dream", ot)
    rc, out = G.system_git_run("tag", "-l", tag, read_only=True)
    if rc != 0:
        raise G.GitError(f"git tag -l {tag} -> {rc}: {out} — cannot "
                         f"tell whether this circle was already dreamt")
    return bool(out.strip())


def short_term_backfill_step(ot: str, say) -> int:
    """STEP 0 of every live close: a part that SPOKE never reaches dreaming as
    if it had been silent. B54, 2026-08-19.

    THE GAP THIS CLOSES. Detection and repair both existed, in circle_audit's
    phases 2 and 3, and NOTHING CALLED EITHER on this path — the one that runs
    synchronously at every live /close since B3/R189, with dreaming as the
    first thing it does. PD.part_dream() guards the short_term on a bare
    `is_file()`, and a silent part is a designed, legal, non-SUSPECT outcome
    (with an empty MEMORY — B91 flags a silent part that writes one),
    so a part that spoke and lost its record simply did not move that circle.
    No error anywhere.

    HERE, NOT IN circle.py's /close, and B54 named the trade: a step 0 inside
    circle_process keeps the manual `--ot` re-run covered by the same guard,
    where a call from /close would leave that path bare. It costs
    inter_circle a second responsibility, which is the price.

    WARN-REPAIR-RECORD, not refuse. Refusing to process would lose the circle
    over a record that can be rebuilt. Every reconstruction is MARKED (R248,
    "Do mark reconstructions") and dreaming is told which kind of record it
    has — see PD.part_dream.

    THE ORDERING IS THE WHOLE POINT and was already written down in
    circle_audit's own failure text: *backfill from the transcript before
    dreaming*. A repair that runs after dreaming fixes the file and not the
    dream, which is the part that mattered.

    Returns 0 to continue. Non-zero only if a repair was needed and could not
    be made — dreaming on a record known to be missing would bake the loss in."""
    todo = BF.short_term_needs_backfill(ot)
    if not todo:
        return 0
    say(f"\n  transcript safety net — {len(todo)} part(s) spoke with no usable "
        f"record. Reconstructing before dreaming; this adds {len(todo)} model "
        f"call(s) to this close.")
    # SAME STALE-`False`-ARGUMENT BREAK AS circle_audit.py/part_mid_term_project.py
    # (audit-register.md Tier 1 #2, fixed there 2026-09-01) — R360
    # (2026-08-27) dropped circle_briefing_build()'s and shared_block()'s trailing
    # `minimal` parameter entirely; this call site's own trailing `False`
    # was never updated to match, so both calls would have raised TypeError
    # the moment needs_backfill() ever found real work — which nothing had,
    # since the live wiring's first exercise is still pending (see
    # CLAUDE.md, "There is no nightly"). shared_block() ITSELF RETIRED
    # 2026-09-02 alongside the fix, replaced by one call, prompt_part_assemble().
    import prompt_build as C
    core = C.group_shared_read()
    briefing, _ = C.circle_briefing_build([])
    failed: list[str] = []
    for part, n, why in todo:
        say(f"    {part}: spoke {n}x — {why}")
        system, _ = C.prompt_part_assemble(part, core, briefing)
        # a real part prompt, so it records under the PART shape — kind
        # backfill, R277's own rule ("every request that carries a part's
        # system prompt"), which the wiring never honoured until R412
        text, err = BF.short_term_backfill(
            part, ot, R.TAG_BY_DIR[part], system,
            lambda s, u, m, _p=part: PD._call(s, u, m, kind="backfill",
                                           record=True, part=_p))
        if err:
            failed.append(f"{part}: {err}")
            say(f"    {part}: RECONSTRUCTION FAILED — {err}")
            continue
        # In the circle's OWN format (B96, R434): .toml for a circle whose other
        # parts are .toml, .md into a legacy circle — backfill decides, once,
        # for both the text and the path.
        BF.short_term_backfill_path(part, ot).write_text(
            text, encoding="utf-8", newline="\n")
        say(f"    {part}: reconstructed and MARKED ({len(text.split())} words)")
    if failed:
        say(f"\n  {len(failed)} record(s) could not be reconstructed. Dreaming "
            f"on a record known to be missing would bake the loss into the "
            f"part's identity, so this close's processing stops here.")
        return 1
    return 0


def circle_synthesis_is_first() -> bool:
    """Has phase 2 EVER completed in this tree? The shrink waiver's own
    test — R348, the operator's "(a)"
    (2026-08-25): the FIRST synthesis replaces the shipped seed self.md,
    not a record, so record_tree_compare waives its shrink tolerance for that
    one run. Evidence mirrors circle_is_processed()'s two markers: any
    `dream_<OT>.json` run marker (the [0-9] glob keeps the
    `dream_error_*` reports beside them from counting as runs), else any
    `dream/*` tag where there is a git history.

    WRONG-ANSWER ASYMMETRY, deliberate: git UNABLE to answer reads as NOT
    first — a waiver granted on a mature tree strips the very protection
    the gate exists for, while one withheld on a fresh tree merely
    reproduces today's refusal, loudly."""
    if any(LOGS.glob("dream_[0-9]*.json")):
        return False
    if not circle_git_history_read():
        return True
    try:
        import gitrepo as G
        rc, out = G.system_git_run("tag", "-l", "dream/*", read_only=True)
    except Exception:                                       # noqa: BLE001
        return False
    if rc != 0:
        return False
    return not out.strip()


def circle_dream_marker_read(ot: str) -> pathlib.Path:
    """`work/logs/dream_<OT>.json` — the run marker's FILE form, and the
    twin of the `dream_error_<OT>.json` that has always sat beside it.
    Written as the last act of a successful run; see circle_dream_marker_write()."""
    return LOGS / f"dream_{ot}.json"


def circle_git_history_read() -> bool:
    """Does this tree keep a git history at all? A FILESYSTEM test, no
    subprocess — so it answers the same on a machine with no git binary
    installed as on one that has it.

    `.git` is a directory in a main checkout and a FILE (the `gitdir:`
    pointer) in a worktree, so `.exists()` and not `.is_dir()` — the same
    distinction gitrepo.system_git_is_main_checkout() turns the other way."""
    return (ROOT / ".git").exists()


def circle_dream_marker_write(ot: str, *, committed: bool, tag: str | None) -> None:
    """Record that phase 2 ran to completion for this circle. Called ONCE,
    last, after the commit step — so a run that died earlier leaves no
    marker and its re-run is clean, the same property the tag has.

    THE TAG REMAINS AUTHORITATIVE WHEREVER THERE IS ONE. This file does
    not replace it; circle_is_processed() reads either, and in a tree with a
    git history the tag is what a failed commit still guarantees. The file
    exists for the tree that has no history to hold a tag."""
    LOGS.mkdir(parents=True, exist_ok=True)
    rec = {"ot": ot, "processed_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "committed": committed, "tag": tag,
           "note": "phase 2 (dreaming + synthesis) completed for this circle. "
                   "circle_is_processed() reads this file OR the git tag; either "
                   "one refuses a re-run. Delete it only if you mean to dream "
                   "this circle again."}
    circle_dream_marker_read(ot).write_text(json.dumps(rec, indent=2) + "\n",
                                encoding="utf-8", newline="\n")


def _capture_paths(ot: str, dirty: "list[str] | None" = None
                   ) -> tuple[list[pathlib.Path], bool]:
    """Every file in the circle's capture directory, and whether any of them
    is new or changed since the last commit. R412/R413, 2026-08-31.

    WHY THE DREAM COMMIT CARRIES THEM: circle_commit() runs BEFORE this
    module and takes the capture as it stood; every processing turn recorded
    since — dreaming, synthesis, the refresh, the coalesce pass at close —
    and the manifest they rewrote land after it, and nothing else commits
    them. Called AFTER the refresh, so its turns are in. A path already
    committed costs nothing; a capture that was never opened (a re-run of a
    circle with none) contributes nothing.

    `dirty` is git's own porcelain (gitrepo.system_git_is_dirty()) so "changed" means what
    the commit will see; injectable so a probe can hand it a line. A tree
    with no git, or a capture root outside the repository (a suite's temp
    redirect), answers (files, False) and the tier-1 branch reports as it
    always has."""
    d = PCAP.PROMPTS / ot
    if not d.is_dir():
        return [], False
    files = sorted(p for p in d.iterdir() if p.is_file())
    try:
        rel = d.resolve().relative_to(ROOT.resolve()).as_posix() + "/"
    except ValueError:
        return files, False
    if dirty is None:
        try:
            import gitrepo as G
            dirty = G.system_git_is_dirty()
        except Exception:                                      # noqa: BLE001
            dirty = []
    moved = any(line[3:].strip().strip('"').startswith(rel) for line in dirty)
    return files, moved


def _open_capture_log(ot: str, live: bool, say) -> bool:
    """For the HAND RE-RUN (R168's `--ot <OT> --live`): open the circle's own
    capture directory so this run's processing calls record there, exactly
    as they do under circle.py's /close, whose turn log is already open when
    it calls circle_process(). Returns True only when THIS call opened it —
    the caller closes what it opened and nothing else. R412/R413, 2026-08-31.

    LIVE ONLY: a rehearsal and a dry run record nothing (R360). A circle with
    no capture (closed before R277) has nowhere to record and is skipped; a
    capture that cannot be read is skipped too and said so — a capture
    failure must not cost a run, the rule the transport already keeps."""
    if not live or PCAP.prompt_turn_log_locate() is not None:
        return False
    d = PCAP.PROMPTS / ot
    if not (d / PCAP.MANIFEST).is_file():
        return False
    try:
        PCAP.prompt_turn_log_open(d, ot)
    except Exception as e:                                     # noqa: BLE001
        say(f"  capture: {_shown(d)}/ could not be opened "
            f"({type(e).__name__}: {e}) — this run's requests are NOT "
            f"recorded")
        return False
    say(f"  capture: this run's requests record into {_shown(d)}/")
    return True


def circle_process(ot: str, live: bool, confirmed: list[dict] | None = None,
                   say=print) -> int:
    """Phase 2, whole. Returns 0 on success; non-zero means the circle's
    own record is UNTOUCHED and work/logs/dream_error_<OT>.json says why.

    Opens the circle's capture for a hand re-run and closes it after — see
    _open_capture_log(); under a live /close the log is circle.py's, already
    open, and is left exactly as found."""
    opened = _open_capture_log(ot, live, say)
    try:
        return _process_circle(ot, live, confirmed, say)
    finally:
        if opened:
            PCAP.prompt_turn_log_open(None)


def _process_circle(ot: str, live: bool, confirmed: list[dict] | None,
                    say) -> int:
    """circle_process()'s body — everything but the capture log's lifetime."""
    confirmed = confirmed or []
    if circle_is_processed(ot):
        # NAME THE MARKER THAT REFUSED — audit-register.md #6, 2026-09-08. There are TWO since
        # 2026-08-24 and either refuses; this said "git tag dream/<OT> ... Delete the tag first",
        # which is the WRONG INSTRUCTION whenever the marker FILE was the refuser — deleting the
        # tag changes nothing, and a tree with no git history has no tag to delete at all.
        # Reachable today: :751-757 sets `tag = None` on a capture-only refused commit while :772
        # still writes the marker file.
        marker = circle_dream_marker_read(ot)
        which = (f"work/logs/{marker.name}" if marker.is_file()
                 else f"git tag dream/{ot}")
        say(f"  circle {ot} is already processed ({which}) — "
            f"re-running would double-dream it. Remove that marker first if "
            f"you mean it.")
        return 1
    tpath = _RP.record_dir(ROOT, "circles") / f"circle_{ot}.md"
    try:
        transcript = tpath.read_text(encoding="utf-8")
    except FileNotFoundError:
        say(f"  no transcript at {tpath.relative_to(ROOT)} — is {ot!r} a "
            f"closed LIVE circle?")
        return 1
    # THE HEARTBEAT, for the hand re-run path: under a live /close circle.py
    # is already beating and this returns False; run from the CLI it starts
    # one, so the every-10-seconds rule (2026-08-30) holds either way in.
    PC.PHASES.start_heartbeat(SET.setting_value_read("close_heartbeat_seconds", 10),
                              notify=say)
    if live:
        with PC.PHASES.span("inter.backfill"):
            rc0 = short_term_backfill_step(ot, say)
        if rc0:
            return rc0
    parts = R.DIR_NAMES
    with PC.PHASES.span("inter.capsule"):
        capsule = PD.circle_capsule_build(ot, transcript, say)     # R451, D86 a: ONE call,
                                                                  # shared by every part below
    say(f"\ndreaming — {len(parts)} parts, in parallel ({LC.MODEL}):")
    payloads: list[dict] = []
    errors: list[str] = []
    try:
        for p in parts:
            say(f"  {p}: started")
        with PC.PHASES.span("inter.dreaming"), \
                concurrent.futures.ThreadPoolExecutor(len(parts)) as ex:
            futs = {ex.submit(PD.part_dream, p, ot, transcript, capsule): p for p in parts}
            for f in concurrent.futures.as_completed(futs):
                pay = f.result()
                payloads.append(pay)
                if pay.get("chars"):
                    PD._report_chars(say, pay["part"], pay["chars"])
                what = []
                if pay.get("memory"):
                    what.append("memory"
                                + (f" ({pay['salience']})" if pay.get("salience")
                                   else "")
                                + (" (continues)" if pay.get("continues")
                                   else ""))
                for s in pay.get("truncated", []):
                    say(f"  {pay['part']}: TRUNCATED — {s}")
                for s in pay.get("suspect", []):
                    say(f"  {pay['part']}: SUSPECT — {s}")
                # THE TWO NUMBERS THAT EXPLAIN A TRUNCATION, on every line
                # since 2026-08-21: how many output tokens the call spent
                # (thinking included — see PD.DREAM_MAX_TOKENS) and why it
                # stopped.
                tok = pay.get("output_tokens")
                sr = pay.get("stop_reason")
                spent = (f" [{tok:,} output tokens" if tok is not None else "")
                spent += (f"{', ' if spent else ' ['}{sr}" if sr else "")
                spent += "]" if spent else ""
                if pay.get("error"):
                    errors.append(f"{pay['part']}: {pay['error']}"
                                  + (f" (stop_reason={sr})" if sr else "")
                                  + (f" (output_tokens={tok})"
                                     if tok is not None else ""))
                    say(f"  {pay['part']}: FAILED — {pay['error']}{spent}")
                else:
                    say(f"  {pay['part']}: done"
                        + (f" — {', '.join(what)}" if what
                           else " — nothing to carry") + spent)
        if errors:
            raise _Unparseable(
                "DREAMING: " + "; ".join(errors),
                "\n\n".join(f"--- {p.get('part', '?')} ---\n{p['raw']}"
                            for p in payloads if p.get("raw")))

        say("\nsynthesis — one circle-wide call:")
        with PC.PHASES.span("inter.synthesis"):
            syn = SYN.circle_synthesise(ot, transcript, payloads, confirmed, say)
        if syn.get("error"):
            raise _Unparseable(f"SYNTHESIS: {syn['error']}", syn.get("raw"),
                               syn.get("stop_reason"), syn.get("output_tokens"))
        for s in syn.get("truncated", []):
            say(f"  TRUNCATED — {s}")
        for s in syn.get("suspect", []):
            say(f"  SUSPECT — {s}")

        say("\nstaging + gate:")
        tx = T.Transaction(ROOT, f"dream_{ot}")
        # DESIGN_V2 LONG_TERM_CANDIDATE (2026-08-22): a qualifying chain
        # (3+ records, this run's own terminal record "resolved", a prior
        # link notable/charged) surfaces ONE topics.toml row per part —
        # never an auto-write to long_term.md itself. Collected here, over
        # THIS run's own new record only, so a chain that already
        # qualified in a PRIOR run is never re-surfaced on every run after.
        lt_candidates: list[tuple[str, dict]] = []
        for pay in sorted(payloads, key=lambda x: x["part"]):
            part = pay["part"]
            if pay.get("memory"):
                doc, rec = RM.remember_dreamt_render(
                    _load_or(RM._real_path(part), {RM.TABLE: []}),
                    pay["memory"], ot, pay.get("continues", False),
                    salience=pay.get("salience"))
                _stage_toml(tx, _RP.record_rel(f"parts/{part}/remember.toml"), doc,
                            RM.TABLE, RM.ORDER)
                if RM.remember_chain_qualifies(doc, rec):
                    lt_candidates.append((part, rec))
            # part_relationships.toml: NOT staged, 2026-08-22 — see
            # inter_circle's own module docstring, "part_relationships IS
            # INERT." DREAMING no longer produces a rel_doc at all.
        for part, rec in lt_candidates:
            say(f"  {part}: LONG_TERM CANDIDATE — a resolved chain of 3+ "
                f"reached self/topics.toml for review, never auto-written "
                f"to long_term.md")
        secs = syn["sections"]
        if secs["HISTORY"].strip():
            doc, _rec = CH.circle_history_new_render(CH._doc(), ot, secs["HISTORY"])
            _stage_toml(tx, _RP.record_rel("circles/circle_history.toml"), doc, CH.TABLE,
                        CH.ORDER)
        # CIRCLE JOURNAL — B94 stage 4, 2026-09-04 (D90/R454, D92/R455; the operator:
        # "add it now" (R456), confirming the /review-item's recommended answer after
        # Claude's report of the standalone trial's findings, work/ablations/2026-09-04/).
        # Same pattern as HISTORY just above; circle_journal_new_render() REFUSES over
        # CJ.CAP rather than truncating, but circle_synthesise() already truncated a
        # still-over-cap reply before returning, so this call is never expected to
        # raise — see that module's own CAP-crunch handling.
        if syn.get("circle_journal"):
            doc, _rec = CJ.circle_journal_new_render(
                CJ._doc(), ot, syn["circle_journal"],
                provenance=syn.get("circle_journal_provenance"))
            _stage_toml(tx, _RP.record_rel("circles/circle_journal.toml"), doc, CJ.TABLE, CJ.ORDER)
        if syn.get("observation"):
            # A REGISTER since 2026-08-19 (R256) — was a raw
            # append to self/self_observation_log.md, whose "## Circle <OT>
            # — synthesis" heading carried the only structure it had.
            # R358: the parsed body (CONTINUES prefix stripped), with the
            # dreaming-model fields; a bare CONTINUES staged nothing above.
            doc, _rec = CO.circle_observation_new_render(CO._doc(), ot, syn["observation"],
                                      salience=syn.get("obs_salience"),
                                      continues=bool(syn.get("obs_continues")))
            _stage_toml(tx, _RP.record_rel("circles/circle_observation_log.toml"), doc,
                        CO.TABLE, CO.ORDER)
        if syn.get("self_md"):
            tx.stage(_RP.record_rel("self/self.md"), (syn["self_md"] + "\n").encode("utf-8"))
        tdoc = TOP._doc()
        for item in RD.message_items_read(secs["BLOCK 2 CANDIDATE"]):
            tdoc, _rec = TOP.topic_new_render(tdoc, ot, item)
        # LONG_TERM_CANDIDATE rows ride the SAME register SYNTHESIS's own
        # BLOCK 2 CANDIDATE already uses (DESIGN_V2's own words) — no new
        # field, a human-legible prefix distinguishes them in the listing.
        for part, rec in lt_candidates:
            tag = R.TAG_BY_DIR[part]
            tdoc, _rec2 = TOP.topic_new_render(
                tdoc, ot, f"LONG_TERM CANDIDATE [{tag}]: {rec['text']}")
        bdoc = PM._doc()
        for item in RD.message_items_read(secs["BLOCK 1 CANDIDATE"]):
            bdoc, _pid = PM.practice_stage_render(bdoc, "add", addressee="All parts",
                                          title=item, sources=["synthesis"],
                                          circle=f"circle_{ot}")
        if RD.message_items_read(secs["BLOCK 2 CANDIDATE"]) or lt_candidates:
            _stage_toml(tx, _RP.record_rel("self/topics.toml"), tdoc, TOP.TABLE, TOP.ORDER)
        if RD.message_items_read(secs["BLOCK 1 CANDIDATE"]):
            _stage_toml(tx, _RP.record_rel("self/best_practices.toml"), bdoc,
                        "practice", PM.ORDER)
        staged = tx.changed()
        say(f"  {len(staged)} file(s) staged: "
            + (", ".join(staged) if staged else "nothing to write"))
        first = circle_synthesis_is_first()
        if first:
            say("  first synthesis of this tree — self.md's shrink "
                "tolerance is waived this once: the seed is not yet a "
                "record (R348)")
        with PC.PHASES.span("inter.gate"):
            findings = tx.validate(first_synthesis=first)
        fails = [f for f in findings if f.level == "FAIL"]
        for f in fails:
            say(f"  GATE FAIL  {f.path}: {f.message}")
        if fails:
            raise RuntimeError(
                f"register gate refused {len(fails)} finding(s) — the live "
                f"tree is untouched; staging kept at {tx.staging}")
        if not live:
            say("\nREHEARSAL — gate green, nothing committed. Staging kept "
                "for inspection; rerun with --live to commit.")
            return 0
        if staged:
            with PC.PHASES.span("inter.tx_commit"):
                tx_ok = tx.commit(lambda lvl, msg: say(f"  {lvl}  {msg}"))
            if not tx_ok:
                raise RuntimeError("Transaction.commit refused — see above")

        # PAST tx.commit(), THE LIVE TREE IS ALREADY UPDATED (whenever
        # anything was staged). Anything that RAISES from here on —
        # MT.part_mid_term_refresh()'s raw messages.create (no retry ladder; one
        # transient 529 does it), the gitrepo import, commit_paths raising
        # GitError or TimeoutExpired instead of returning False — used to
        # fall through to the generic R168 handler, whose report claims
        # "the live tree is untouched; the re-run below starts clean" and
        # prints the re-run command. Both halves were lies in this window:
        # no dream/<OT> tag exists yet, so circle_is_processed() reads False
        # and the advised re-run would DREAM AGAIN on top of the committed
        # content. Since 2026-08-19 every raise in this window is wrapped
        # into _PostCommitFailed, whose report shape tells the truth. When
        # nothing was staged the tree really is untouched (mid_term.md is
        # a re-derivable cache, not part of the record), so the generic
        # handler stays correct there and the raise passes through.
        try:
            say("\nmid_term refresh — stale parts only (R186/H3):")
            with PC.PHASES.span("inter.mid_term_refresh"):
                mt_fails = MT.part_mid_term_refresh(say=say)
            if mt_fails:
                say(f"  {mt_fails} SUSPECT derivation(s) NOT written — rerun "
                    f"mid_term --refresh by hand; everything else committed")

            import gitrepo as G
            paths = [ROOT / rel for rel in staged]
            paths += [MT.part_mid_term_locate(p) for p in parts if MT.part_mid_term_locate(p).is_file()]
            # THE CIRCLE'S CAPTURE RIDES THIS COMMIT (R412/R413): the turns
            # recorded since circle_commit() took the directory, and the
            # manifest they rewrote. AND IT COMMITS EVEN WHEN NOTHING WAS
            # STAGED — an empty staging is right for mid_term.md, a
            # re-derivable cache, and wrong for the capture, which is the
            # record: the calls happened whether or not their output moved a
            # register.
            cap_paths, cap_moved = _capture_paths(ot)
            paths += cap_paths
            to_commit = bool(staged) or cap_moved
            committed, tag = False, None
            # NO GIT HISTORY IS A SUPPORTED TREE SINCE 2026-08-24, ruled by
            # the operator ("Tier 1"): a distributed bundle that was never
            # `git init`ed dreams and synthesises like any other, and
            # records the run in work/logs/dream_<OT>.json instead of a
            # tag. The commit is SKIPPED there rather than attempted and
            # failed — commit_paths() would warn "not a git repository" and
            # return False, which the branch below reads as a REFUSED
            # commit and escalates to _PostCommitFailed. Absent is not
            # refused, and telling a recipient their record is "REAL and
            # UNCOMMITTED" in a tree that commits nothing would be a
            # warning about the design working.
            if to_commit and not circle_git_history_read():
                say("  no git history in this tree — the run's output is "
                    "written but not committed. "
                    f"work/logs/dream_{ot}.json records that this circle "
                    f"was processed; that file is what refuses a re-run "
                    f"here, in place of the dream/{ot} tag.")
            elif to_commit and not G.system_git_identity_is_known():
                # git is HERE but unconfigured — the fresh-install case,
                # R349 (2026-08-25): the same
                # skip as the tier above, never a refusal escalated to
                # _PostCommitFailed. The marker below still refuses a
                # re-run; this circle's record stays uncommitted until a
                # hand `git add` after git learns an identity.
                G.system_git_unconfigured_report(lambda lvl, msg: say(f"  {lvl}  {msg}"))
                say("  git is not configured — the run's output is written "
                    "but not committed. "
                    f"work/logs/dream_{ot}.json records that this circle "
                    f"was processed; that file is what refuses a re-run "
                    f"here, in place of the dream/{ot} tag.")
            elif to_commit:
                tag = G.system_git_tag_name_read("dream", ot)
                with PC.PHASES.span("inter.git_commit"):
                    committed = G.system_git_paths_commit(
                        paths, f"dream/synthesis for circle {ot}",
                        lambda lvl, msg: say(f"  {lvl}  {msg}"),
                        tag=tag)
                if not committed and not staged:
                    # only the capture moved and its commit was refused: no
                    # register is at stake, so this is a warning, not the
                    # escalation below — the files sit where a hand commit
                    # finds them, and the marker below still refuses a re-run
                    tag = None
                    say(f"  the capture's new turn files under "
                        f"work/prompts/{ot}/ are written but NOT committed — "
                        f"see the 'fail' line above; commit them by hand.")
                elif not committed:
                    raise _PostCommitFailed(
                        f"the live tree was already updated ({len(staged)} "
                        f"file(s), via Transaction.commit) before the git "
                        f"commit failed — see the 'fail' line above for why. "
                        f"These changes are REAL and UNCOMMITTED, not "
                        f"discarded. Do NOT re-run inter_circle.py for {ot} — "
                        f"circle_is_processed() still reads False (no "
                        f"dream/{ot} tag), so a re-run would DREAM AGAIN on "
                        f"top of this uncommitted content. Fix whatever the "
                        f"commit gate refused, then `git add` and `git commit` "
                        f"the pending paths by hand.")
            else:
                say("  nothing changed — no second commit for this circle")
            # THE LAST ACT, DELIBERATELY. A run that died anywhere above
            # leaves no marker, so its re-run is clean — the same property
            # all-or-nothing staging gives the tag, kept by writing this
            # only once everything else has succeeded.
            circle_dream_marker_write(ot, committed=committed, tag=tag)
            # One line of wall-clock per phase, here as well as in the spend
            # report — the hand re-run path has no spend report to read.
            rows = [r for r in PC.PHASES.snapshot()["phases"]
                    if r["phase"].startswith("inter.")]
            if rows:
                say("\n  phase seconds — " + ", ".join(
                    f"{r['phase'][6:]} {r['seconds']:.0f}" for r in rows))
            say(f"\nphase 2 complete for {ot}.")
            return 0
        except _PostCommitFailed:
            raise
        except Exception as e:
            if not staged:
                raise                  # tree untouched — R168's report is true
            raise _PostCommitFailed(
                f"the live tree was already updated ({len(staged)} file(s), "
                f"via Transaction.commit) when this failed: "
                f"{type(e).__name__}: {e}. The committed changes are REAL. "
                f"Do NOT re-run inter_circle.py for {ot} — "
                f"circle_is_processed() still reads False (no dream/{ot} tag), "
                f"so a re-run would DREAM AGAIN on top of them. Fix the "
                f"cause, then `git add` and `git commit` the pending paths "
                f"by hand (a mid_term refresh that died mid-way can be "
                f"re-run safely: part_mid_term_manager.py --refresh).") from e

    except _PostCommitFailed as e:
        # See the class docstring: the live tree IS modified here, so this
        # gets its own report shape rather than R168's generic one, which
        # would falsely claim "the live tree is untouched" and suggest a
        # re-run that would double-dream on top of the uncommitted content.
        report = {"ot": ot, "error": str(e),
                 # the field circle.py's failure banner branches on — its
                 # absence in a report means the old prose is the only signal
                 "rerun_safe": False,
                 "note": "PARTIAL SUCCESS, NOT a clean failure: dreaming and "
                         "synthesis both completed and Transaction.commit "
                         "already wrote their output into the live tree — "
                         "only the git commit itself failed. Do not re-run "
                         "this OT; fix the commit gate and commit by hand."}
        rp = LOGS / f"dream_error_{ot}.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, indent=2), encoding="utf-8",
                      newline="\n")
        say(f"\n!! phase 2 committed the live tree but NOT git — "
            f"report: {_shown(rp)}")
        say(f"\n{e}")
        return 1

    except Exception as e:                                     # R168
        report = {
            "ot": ot, "error": f"{type(e).__name__}: {e}",
            "payload_errors": errors,
            "parts_done": sorted(p.get("part", "?") for p in payloads),
            # PER PART, 2026-08-21: what each call spent and why it stopped —
            # the two facts the 2026-08-21_1139 report lacked, and the ones
            # that tell "the model thought the budget away" from "the model
            # renamed a header".
            "parts": [{"part": p.get("part", "?"),
                       "output_tokens": p.get("output_tokens"),
                       "stop_reason": p.get("stop_reason"),
                       **({"error": p["error"]} if p.get("error") else {})}
                      for p in sorted(payloads, key=lambda x: x.get("part", ""))],
            "dream_max_tokens": PD.DREAM_MAX_TOKENS,
            "synth_max_tokens": SYN.SYNTH_MAX_TOKENS,
            "rerun_safe": True,
            "note": "all-or-nothing staging: the live tree is untouched; "
                    "the re-run below starts clean",
        }
        sr = getattr(e, "stop_reason", None)
        if sr:
            report["stop_reason"] = sr
        ot_used = getattr(e, "output_tokens", None)
        if ot_used is not None:
            report["output_tokens"] = ot_used
        rp = LOGS / f"dream_error_{ot}.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        raw = getattr(e, "raw", None)
        # `is not None`, NOT truthiness. PD._call() returns "" when the response
        # carries no text block at all, and an empty answer is precisely the
        # case worth seeing — the first two capture attempts wrote nothing
        # here for exactly that reason, and the report said raw_output: null
        # while looking like the capture had simply not run.
        if raw is not None:
            xp = rp.with_name(f"dream_error_{ot}_raw.txt")
            xp.write_text(raw, encoding="utf-8", newline="\n")
            report["raw_output"] = _shown(xp)
            # The diagnostic call gets a SAMPLE inline, head AND tail: the two
            # failure modes it must tell apart are a decorated/renamed header
            # (visible at the top) and truncation (visible only at the end).
            report["raw_len"] = len(raw)
            report["raw_head"] = raw[:1500]
            report["raw_tail"] = raw[-800:] if len(raw) > 2300 else ""
            if not raw:
                report["raw_note"] = (
                    "THE MODEL RETURNED NO TEXT AT ALL — not a header "
                    "mismatch. Check stop_reason below: 'max_tokens' means "
                    "the answer was truncated to nothing useful; anything "
                    "else means the response carried no text block.")
        rp.write_text(json.dumps(report, indent=2), encoding="utf-8",
                      newline="\n")
        say(f"\n!! phase 2 FAILED — report: {_shown(rp)}")
        try:
            diag_user = json.dumps(report, indent=2)
            # NOT RECORDED, by ruling (R412): it writes nothing
            diag = PD._call(DIAGNOSIS_PROMPT, diag_user, LC.AUX_MAX_TOKENS,
                         kind="diagnosis").text
            PD._report_chars(say, "diagnosis", {"system": DIAGNOSIS_PROMPT,
                                             "user": diag_user, "reply": diag})
            say(f"\ndiagnosis (one model call, diagnostic only):\n{diag}")
        except Exception as e2:
            say(f"  (diagnosis call itself failed: {e2} — the report above "
                f"stands on its own)")
        # The "circle already committed" line is only true on the /close path.
        # A --ot run is a re-run or a rehearsal against a circle committed long
        # ago, and telling the operator his circle "closed and committed
        # BEFORE this phase" reads as news about THIS run when it is not.
        # Caught on the first rehearsal, 2026-08-09_1520.
        if raw:
            say(f"\nThe model's actual output is kept at "
                f"{report['raw_output']} — read it before changing anything.")
        say(f"\nDreaming/synthesis did not run to completion, and NOTHING was "
            f"written: the live tree is byte-identical to before this run.\n"
            f"Re-run by hand — note this re-runs every DREAMING call too, "
            f"not only the step that failed:\n"
            f"    python coordinator/inter_circle.py --ot {ot} --live")
        return 1


def main() -> int:
    a = sys.argv[1:]
    if "--ot" not in a:
        print("usage: inter_circle.py --ot <OT> [--live] [--group <name>]")
        return 1
    ot = a[a.index("--ot") + 1]
    # `--group <name>`: process a circle of that GROUP's record (groups/<name>/) — B117 stage 5
    # (2026-09-07). Default: the ifs group. A live /close never needs it: circle.py has already
    # set the group in this process before the close runs.
    if "--group" in a:
        _RP.group_set(a[a.index("--group") + 1])
    return circle_process(ot, live="--live" in a)


if __name__ == "__main__":
    raise SystemExit(main())
