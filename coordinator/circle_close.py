#!/usr/bin/env python3
"""
circle_close.py — the CLOSE step: what `/close` does between the last statement and the
commit.

THIS FILE WAS THE VERIFIER until 2026-09-03; that is circle_close_verify.py now (R435), and
the bare name belongs to the step itself (B5/C, cohesion re-homing stage 12). Everything
here lived in circle.py, verbatim; only the file moved, and the driver reads it as CC.

RENAMED AT THE MOVE (R436, R442 — 2026-09-03), the class word first, the bodies untouched:

    collect_short_terms  -> short_term_collect      SHORT_TERM is R442's own class word
    mark_close_started   -> circle_close_mark
    list_resumable       -> circle_resumable_list   (the flag stays --list-resumable)
    _short_term_call, _interrupted_closes, _failed_phase2, _close_began, _dest_for,
    _prompt_blocks_changed, CLOSING_MARK, SHORT_TERM_*   private, or constants — unchanged

    SHORT_TERM_PROMPT, SHORT_TERM_MAX_TOKENS   the one request the close makes of each part
                                               that spoke (R255: the four sections, then the
                                               part's one remember, last)
    _short_term_call, short_term_collect      that request on a worker thread per part
                                               (B89/R420), every write back on this thread
    CLOSING_MARK, circle_close_mark,          the start-of-close marker (2026-08-23) and the
    _close_began                               question it answers
    _interrupted_closes, _failed_phase2        the two open-time reports (R312) the next open
                                               prints from the marker, the close reports and
                                               the dream/<OT> tags
    _dest_for, _prompt_blocks_changed,         where a short_term lands; the resume gate's
    circle_resumable_list                             prompt-drift check; --list-resumable

Design: docs/BNF.md (CLOSE, CP_PROTOCOL for the request's shape), circle_close_verify.py for
what is asserted afterwards, transcript_store for the durable records the step ends with.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import seam                                                    # noqa: E402
import part_roster as R                                             # noqa: E402
import setting_manager as SET                                         # noqa: E402
import annotations as MK                                       # noqa: E402  the remember split
import LLM_response_disassembler as RD                         # noqa: E402  every read of a reply
import llm_client as LC                                        # noqa: E402  call, build_client
import prompt_build as PB                                      # noqa: E402  render_messages
import transcript_store as TS                                  # noqa: E402  write_lf, parse, resume
import short_term_manager as STM                               # noqa: E402  THE record's one reader/writer (B96)
from record_paths import ROOT, SANDBOX, PART_TAGS, record_dir        # noqa: E402


# THE CLOSE ASKS FOR TWO THINGS NOW, ruled 2026-08-19 (R255): the four
# short_term sections, and — after them, last — the part's one
# `[remember: "..."]` for the circle. The two are collected in ONE reply
# rather than a second call per part because the part is already holding
# the whole circle in mind at exactly this moment, and a second call would
# pay for that context twice.
#
# THE ORDERING IS LOAD-BEARING, not stylistic. annotations.remember_close_split()
# is deliberately lenient about "]" so a 1000-word memory containing one
# cannot be silently truncated mid-sentence; the price of that lenience is
# that everything after the opener is the memory. Saying "last" here, in
# process_core.md, annotation and standing guidance alike, is what makes that safe — and
# short_term_collect() still re-checks the four headings after the split
# and falls back to the strict parse if any went missing.
SHORT_TERM_PROMPT = (
    "The circle is closing. Write your short_term record of THIS circle, in "
    "exactly these four sections, in this order, with these exact headings:\n\n"
    "## What I said\n## What I observed in others\n"
    "## Shifts toward other parts\n## Current emotional state\n\n"
    "Write substantively under each heading — this is your own memory of the "
    "circle, and dreaming reads it when the circle closes. No preamble, "
    "no closing remarks, "
    "no other headings. Begin with '## What I said'.\n\n"
    "THEN, if you have one, write your one remember for this circle — "
    "LAST, after '## Current emotional state', on its own line:\n\n"
    '[remember: "<what you are choosing to carry forward>"]\n\n'
    "It is a private note to your own future self: never shown to Self, to "
    "another part, or to the room, and it is the only thing you write "
    "tonight that you will read again. Up to 1000 words. Write it in your "
    "own voice, about what you are keeping rather than what happened. "
    "One per circle — if you already used yours in a round, this one is "
    "dropped. Writing none is a real answer and costs you nothing."
)

# THE CLOSE BUDGET, named 2026-08-28 (R379). It was the bare
# literal `5000` in short_term_collect()'s retry loop, and a value with no name
# is a value nothing can configure — a settings override is resolved BY NAME.
#
# 5000, not 2000 (R255): four substantive sections plus a remember of up to 1000
# words does not fit in 2000, and the failure mode is not a short answer — it is
# stop == "max_tokens", which that loop RETRIES, so an under-budget close would
# have paid for two truncated calls per part and then written the second one
# anyway.
#
# NOT circle_rounds.MAX_TOKENS, which is the ceiling for one STATEMENT. These are two
# different requests with two different shapes; they were never one number.
SHORT_TERM_MAX_TOKENS = SET.setting_value_read("short_term_max_tokens", 5000)



CLOSING_MARK = "closing_{ot}.json"


def _close_mark(ot: str) -> pathlib.Path:
    return ROOT / "work" / "logs" / CLOSING_MARK.format(ot=ot)


def circle_close_mark(ot: str) -> None:
    """Write the START-OF-CLOSE marker. LIVE closes only; callers gate it.

    THE ONE CASE _interrupted_closes() COULD NOT SEE, and its own docstring
    named the fix: "a marker written at the START of a close, which nothing
    writes today". A close that died before writing ANY short_term is
    indistinguishable from an /abort and from a circle still in progress, so
    the all-missing case had to be exempted — and after 45 minutes
    circle_state stops speaking to it too, leaving it reported by nothing.

    IT IS NEVER DELETED. A close report supersedes it: transcript_store writes
    close_<OT>.json as the last act of a completed close, and every reader here
    checks that first. A deletion step is one more thing that can fail on the
    path whose failures this exists to catch."""
    import json
    from atomic_write import record_atomic_write
    m = _close_mark(ot)
    m.parent.mkdir(parents=True, exist_ok=True)
    record_atomic_write(m, json.dumps(
        {"open_time": ot,
         "started": datetime.datetime.now().isoformat(timespec="seconds")},
        indent=2) + "\n")


def _close_began(ot: str) -> bool:
    """Did a close START for this circle? See circle_close_mark()."""
    return _close_mark(ot).is_file()


def _failed_phase2(base: pathlib.Path) -> list[str]:
    """[open_time] for every circle whose dreaming/synthesis failed and has
    not been re-run since. Reported at open, 2026-08-23, ruled (R312).

    THE GAP. inter_circle writes work/logs/dream_error_<OT>.json, prints the
    re-run line and exits non-zero — at that close, once. Nothing mentioned it
    ever again: the transcript is committed and complete, every short_term is
    written, so _interrupted_closes() is right to stay quiet and circle_state
    has nothing to say either. The circle simply never moved anyone's identity,
    silently, from then on.

    THE TAG IS THE RESOLUTION, not the file. already_processed() reads
    `dream/<OT>` as the durable evidence a run succeeded — all-or-nothing
    staging means a failed run leaves nothing else behind — so a re-run that
    works clears this report without anyone tidying up a log. Asked through
    gitrepo.system_git_tag_name_read() so a lab tree asks about its own `dream/lab/<OT>`.

    QUIET ON ANYTHING IT CANNOT READ, the same rule as _interrupted_closes():
    this runs in the open path, and git being unavailable is not a reason to
    refuse to start a circle."""
    logs = ROOT / "work" / "logs"
    if not logs.is_dir():
        return []
    out = []
    for f in sorted(logs.glob("dream_error_*.json")):
        ot_i = f.stem[len("dream_error_"):]
        if ot_i.endswith("_raw"):
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}", ot_i):
            continue
        if not (base / f"circle_{ot_i}.md").is_file():
            continue
        # EITHER MARKER RESOLVES IT, 2026-08-24. Since the operator ruled
        # git optional, a completed phase 2 records itself in
        # work/logs/dream_<OT>.json as well as (or, in a tree with no git
        # history, instead of) the tag — so this asks the file first and
        # never reaches git in a bundle.
        if (logs / f"dream_{ot_i}.json").is_file():
            continue                                     # processed
        try:
            import gitrepo as _G
            rc, tags = _G.system_git_run("tag", "-l", _G.system_git_tag_name_read("dream", ot_i),
                              read_only=True)
            if rc != 0 or tags.strip():
                continue                 # processed, or git could not tell
        except Exception:                                        # noqa: BLE001
            continue
        out.append(ot_i)
    return out


def _interrupted_closes(base: pathlib.Path) -> list[tuple[str, list[str]]]:
    """[(open_time, parts that spoke with no short_term)] for every LIVE
    circle whose close was interrupted. Reported at open, 2026-08-20.

    THE TEST IS THE RESUME GATE'S, NOT circle_state'S, and that is the
    whole point of the function. circle_state asks "has this transcript
    been quiet for 45 minutes" — a heuristic for "is someone still in
    there", which an interrupted close passes cleanly the moment it is
    older than the window. On 2026-08-20 a live close died with four of
    seven short_terms written; by the time anyone looked, circle_state
    called it finished and the next open would have said nothing.

    A CLOSE REPORT MEANS FINISHED. transcript_store writes it as the last
    act of a completed close, so its presence ends the question no matter
    what the parts directory looks like.

    QUIET ON ANYTHING IT CANNOT READ. This runs in the open path, before
    a circle exists; an unparseable old transcript is not a reason to
    refuse to start a new one, and the audit is where that belongs.

    THE CASE NOTHING SAW IS SEEN SINCE 2026-08-23, and this paragraph
    said otherwise until 2026-08-27. A close that died before writing ANY
    short_term used to be indistinguishable here from an /abort, and
    indistinguishable to circle_state once the transcript had been quiet
    45 minutes — reported by neither, after that window. It asked for a
    marker written at the START of a close; circle_close_mark() is that
    marker, and the all-missing branch below consults it.

    THE RESIDUE IS HISTORY, and it does not shrink: a circle that closed
    BEFORE the marker existed has none, so for those the old exemption
    stands exactly as it did, and circle_audit.py's transcript safety net
    is still the only thing that catches them — by hand. The exemption
    itself is deliberate and stays: without a marker, all-missing is what
    a circle actually in progress looks like, which is what
    circle_state's own warning is for."""
    out: list[tuple[str, list[str]]] = []
    for f in sorted(base.glob("circle_*.md")):
        ot_i = f.stem[len("circle_"):]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_\d{4}", ot_i):
            continue
        if (ROOT / "work" / "logs" / f"close_{ot_i}.json").is_file():
            continue
        try:
            _, _, tr = TS.circle_transcript_parse(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        spoke = {e["speaker"] for e in tr if e["speaker"] in PART_TAGS}
        if not spoke:
            continue
        missing = sorted(p for p in spoke
                         if STM.short_term_locate(record_dir(ROOT, "parts") / p, ot_i) is None)
        # ALL of them missing usually means an OPEN circle or an /abort, not
        # an interrupted close — nobody has started closing yet, so nothing
        # has been written. circle_state's own warning above is what speaks
        # to that ordinary case.
        #
        # THE REAL SIGNAL IS circle_close_mark(), NOT COMPLETION ORDER.
        # This comment used to read "short_term_collect writes in roster
        # order, so a genuine interrupt leaves SOME written" — true once,
        # false since B89 (2026-08-31, R420) parallelized short_terms
        # collection, where an interrupt can just as easily leave ALL of
        # them missing. It was already unnecessary the day it stopped being
        # true: circle_close_mark(), written 2026-08-23 the instant a close
        # BEGINS — before any short_term is collected, serial or not — settles
        # the ambiguity on its own. With the marker on disk the circle is
        # neither open nor aborted, so all-missing is a real interrupted
        # close and is reported; without one — every circle closed before
        # the marker existed — the exemption stands exactly as it always did.
        # `missing` itself was always a plain per-part file-existence check,
        # never order-dependent to begin with.
        if missing and (len(missing) < len(spoke) or _close_began(ot_i)):
            out.append((ot_i, [PART_TAGS[p] for p in missing]))
    return out


def _dest_for(part: str, ot: str, guard) -> pathlib.Path:
    """Where this part's record of this circle goes: the file an interrupted close
    already wrote, whatever its suffix, else `short_term_<OT>.toml` — R434
    (2026-09-02, B96): a NEW circle writes TOML, live and dry-run alike."""
    base = SANDBOX if not guard.live else ROOT
    return STM.short_term_path_new(record_dir(base, "parts"), part, ot)


def _short_term_call(part: str, sysblocks, transcript, dry: bool):
    """Runs on a WORKER THREAD (B77's own discipline, R420): the Messages
    API call only, own client per worker (R170's rule — costs nothing,
    answers no thread-safety question). Returns (reply, notes) — `notes`
    are lines the caller emits once this part's future completes, so no two
    parts' console lines can interleave; what the reply is missing is the
    disassembler's read of it, taken again by the caller rather than carried.

    One loop, two attempts (2026-08-19, review tier 5 #47): the retry used
    to be a verbatim copy-paste of the first call four lines apart, so any
    change to the request — budget, prompt, a stop-reason check — had to
    land twice or the retry silently issued the old one. Semantics
    unchanged: attempt 1 retries on a missing section OR truncation; the
    retry's own result is judged on sections alone, exactly as before."""
    notes: list[str] = []
    worker_client = None if dry else LC.stream_client_build()
    reply = RD.Reply.canned("")
    for attempt in (1, 2):
        # SHORT_TERM_MAX_TOKENS, not a literal here — see its own comment
        # beside SHORT_TERM_PROMPT for why the number is 5000 (R255).
        reply = LC.stream_call(
            worker_client, part, sysblocks[part],
            PB.prompt_messages_render(part, transcript, SHORT_TERM_PROMPT),
            SHORT_TERM_MAX_TOKENS, dry,
            kind="short_term",
        )
        missing = RD.short_term_missing(reply.text)
        if not (missing or reply.truncated) or attempt == 2:
            break
        notes.append(f"  {part:<12} FAILED "
                    f"({'truncated' if reply.truncated else 'missing ' + missing[0]}) "
                    f"— retrying")
    return reply, notes


def short_term_collect(client, parts, sysblocks, transcript, ot, guard, dry) -> list[str]:
    spoke = {e["speaker"] for e in transcript}
    written, failed, todo = [], [], []
    for part in parts:
        if part not in spoke:
            seam.emit("command", f"  {part:<12} did not speak — no short_term")
            continue
        dest = _dest_for(part, ot, guard)
        if dest.is_file():
            # An interrupted close already wrote this one — the resume
            # gate let the circle back in for exactly this case. The
            # first write is the record; re-deriving would overwrite it
            # with a second telling (and pay for the call again). Listed
            # in `written` so commit_circle stages it — the interrupt
            # died before any commit.
            seam.emit("command", f"  {part:<12} kept — written before the interrupt")
            written.append(part)
            continue
        todo.append(part)
    if not todo:
        return written

    # THE CALLS RUN IN PARALLEL — B89/R420, 2026-08-31, on mid_term.refresh()'s
    # own proven pattern (B77): ONLY _short_term_call() (the API request, its
    # own client) runs on a worker thread. Every write — apply_remember /
    # apply_close_remember (both touch `guard`), the file write, and every
    # seam.emit() — happens back HERE, on this thread, one finished part at a
    # time via as_completed(), so nothing mutates a file or prints a line
    # from a worker and no two parts' output can interleave.
    #
    # CTRL-C: deliberately NOT special-cased. `with ... as ex:` shuts down
    # with its default wait=True, so an interrupt here lets in-flight calls
    # (each already the sole cost — nothing is written until this thread
    # sees the result) finish before propagating to the KeyboardInterrupt
    # handler at the call site, same as dreaming's and part_mid_term_manager.part_mid_term_refresh()'s
    # own pools. Slower to actually stop than the old serial code; no
    # half-written file or discarded-but-unaccounted spend either way.
    #
    # THE ORDER GUARANTEE THIS REPLACES IS GONE ON PURPOSE. Until this
    # change, _interrupted_closes() could infer a genuine interrupt from
    # "some but not all" written, because short_term_collect() wrote in
    # roster order. It no longer does — see that function's own comment,
    # corrected alongside this one — and does not need to: circle_close_mark()
    # (2026-08-23) already marks a close as begun independently of order,
    # and the missing-set test there was always a plain per-part file check,
    # never order-dependent to begin with.
    seam.emit("command", f"  {len(todo)} part(s) to write, in parallel:")
    with concurrent.futures.ThreadPoolExecutor(len(todo)) as ex:
        futs = {ex.submit(_short_term_call, p, sysblocks, transcript, dry): p
               for p in todo}
        for f in concurrent.futures.as_completed(futs):
            part = futs[f]
            reply, notes = f.result()
            text = reply.text
            missing = RD.short_term_missing(text)
            for n in notes:
                seam.emit("command", n)
            if missing:
                failed.append(part)
                seam.emit("command", f"  {part:<12} FAILED — not written")
                continue

            # THE REMEMBER COMES OUT BEFORE THE FILE IS WRITTEN (R255). A
            # short_term is read by dreaming and by circle_audit; a remember
            # reaches only this part's own BLOCK 4. Leaving the bracket in the
            # .md would put a private note into the one document another
            # process reads on the part's behalf.
            #
            # FALLBACK ON A LOST SECTION. split_close_remember() takes
            # everything after the opener, which is what makes a "]" inside a
            # long memory safe; if a part wrote the bracket mid-reply instead
            # of last, that would swallow a heading. So the split is checked,
            # not trusted: if any of the four went missing, the strict ASK_RE
            # path (apply_remember) runs instead — it keeps the sections and
            # gives up only the lenience.
            #
            # THE CHECK RUNS BEFORE ANY WRITE, and that ordering is the whole
            # correctness of the fallback. split_close_remember() is PURE, so
            # it can be consulted first — RD.message_close_split() is that
            # consultation. Deciding afterwards — writing the lenient record,
            # then noticing a heading had gone — would leave the
            # swallowed-heading version on file AND have the strict retry
            # refuse itself as a second use this circle, since has_remembered()
            # would already be True. One cap, read once, spent once.
            if not RD.message_close_split(text):
                text, recorded = MK.remember_apply(
                    guard, part, PART_TAGS[part], text)
            else:
                text, recorded = MK.remember_close_apply(
                    guard, part, PART_TAGS[part], text)
            if recorded:
                seam.emit("command", f"  {part:<12} remember written")
            # THE RECORD IS TOML SINCE R434 (B96, 2026-09-04) — four named keys,
            # the reply's prose verbatim, through the one writer. THE FORMAT
            # CHECK IS ON THE FILE, NOT THE REPLY: after the write the record is
            # read back through the one reader, and a section missing or empty
            # there is a FAILURE, reported the way an unwritten short_term is.
            # B54's incident is exactly a record on disk that read downstream
            # as no engagement; a heading check on the reply text (above)
            # cannot see an empty body, and a write nothing re-reads cannot
            # see anything at all.
            rec = STM.short_term_record_build(part, PART_TAGS[part], ot, text)
            dest = _dest_for(part, ot, guard)
            guard.check(dest)
            try:
                STM.short_term_write(dest, rec)
                back = STM.short_term_read(dest, part)
                empty = STM.short_term_sections_missing(back)
            except (OSError, ValueError) as e:
                empty, back = [f"({e})"], None
            if empty:
                failed.append(part)
                seam.emit("command", f"  {part:<12} FAILED — the written record does not "
                                     f"read back whole: {', '.join(empty)}")
                continue
            written.append(part)
            seam.emit("command", f"  {part:<12} wrote {dest}")
    if failed:
        seam.fail(f"short_term NOT WRITTEN for: {', '.join(failed)} — these parts spoke "
             f"but have no record; the transcript safety net will backfill them "
             f"from circles/circle_{ot}.md at close")
    return written


def _prompt_blocks_changed(orig: pathlib.Path, new: pathlib.Path,
                           parts: list[str]) -> list[str]:
    """Parts whose EMITTED PROGRAM differs between two captures.

    Compares the manifests' per-block sha256, never the capture files, whose
    headers legitimately differ. Returns every part on any error — an unreadable
    manifest must read as "cannot show it is the same", not as "it is"."""
    try:
        import prompt_capture as PC
        a = PC.block_shas(PC.prompt_manifest_read(orig))
        b = PC.block_shas(PC.prompt_manifest_read(new))
    except Exception:
        return list(parts)
    out = []
    for p in parts:
        ha, hb = a.get(p, []), b.get(p, [])
        if not ha or ha != hb:
            out.append(p)
    return out


def circle_resumable_list() -> int:
    """Circles with a transcript and no close report — including a close
    Ctrl-C interrupted mid-collection (some short_terms written, some
    speaking parts still without; until 2026-08-19 any short_term at all
    hid the circle here, the same over-wide test the --resume gate used).
    A circle whose every speaking part has its short_term is a finished
    close from before close reports existed, and stays hidden. Read-only."""
    rows = []
    for f in sorted(record_dir(ROOT, "circles").glob("circle_*.md")):
        ot = f.stem[len("circle_"):]
        if (ROOT / "work" / "logs" / f"close_{ot}.json").is_file():
            continue
        done = {p.parent.name for p in STM.short_term_glob(record_dir(ROOT, "parts"), ot)}
        try:
            topic, tr, _, _ = TS.circle_transcript_resume_read(f, ot, R.DIR_NAMES)
            spoke = {e["speaker"] for e in tr if e["speaker"] in PART_TAGS}
            if done and not (spoke - done):
                continue                     # closed, pre-close-report era
            n = sum(1 for e in tr if e["speaker"] in PART_TAGS)
            note = f"{n} statement(s)"
            if done:
                note += (f" — close interrupted, "
                         f"{len(spoke - done)} short_term(s) missing")
            rows.append((ot, note, (topic or "(no topic)")[:40]))
        except ValueError as e:
            rows.append((ot, "NOT RESUMABLE", str(e).split("\n")[0][:40]))
    if not rows:
        seam.emit("command", "\n  no unclosed circles.")
        return 0
    seam.emit("command", f"\n  {len(rows)} circle(s) with no close report:\n")
    for ot, n, why in rows:
        seam.emit("command", f"    {ot}")
        seam.emit("command", f"        {n}")
        seam.emit("command", f"        {why}")
    return 0
