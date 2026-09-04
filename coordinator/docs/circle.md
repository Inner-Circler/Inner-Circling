# CIRCLE.PY(1)

## NAME
circle — the driver: opens an IFS inner circle, assembles each part's four prompt blocks, runs
the Self> loop, closes, and hands the closed circle to phase 2

## SYNOPSIS
```
python coordinator/circle.py --dry-run
python coordinator/circle.py --live
python coordinator/circle.py (--live | --dry-run) [--parts <dir>,<dir>,... | --group <name>]
                              [--recall-arm off|delivered|withheld]
                              [--no-prewarm] [--no-blind] [--seed <n>] [--yes] [--dev]
                              [--resume OPEN_TIME] [--list-resumable]
python coordinator/circle.py --dev-cmd VERB [args...]
```
Regenerated 2026-08-21 (B65) against the module as it stood after phase 1/2 of the coordinator
partitioning (2026-08-16), B61 (one dispatcher), R277 (the per-request capture) and
R285-R287. The previous page described the pre-partition file — the turn engine, the
annotation grammar, the verb table and the help system inside this module — and is superseded
whole; each of those now has its own module and, where generated, its own page.

## DESCRIPTION
`circle.py` is no longer the program; it is the driver. A circle is one local process: each part
is a stateless Messages API call whose statement is the HTTP return value, the coordinator holds
the single canonical transcript, and every file is written by this process. What this module
still owns is the ORDER of a circle — the integrity gate, the API check, the open-circle
warning, the pre-open vetting checkpoint, the working set and topic questions, the mint of the
open time, the transcript, the prompt capture, the pre-warm, the opening round, the Self> loop,
and the close (short_terms, verifier, commit, phase 2). Everything it calls lives elsewhere:
`seam` (the I/O seams), `write_guard`, `transcript_store`, `prompt_build`, `llm_client`,
`circle_rounds`, `annotations`, `vetting`, `command_surface`, `commands`, `help_system`,
`quote_as_lands`, `prompt_capture`, `token_count`, `inter_circle`, and the issue-graph code under
`memory/`.

Two modes, and ONE IS REQUIRED since R360 — a bare invocation refuses (exit 2) rather than
falling back to a default. `--dry-run` is the test rig: no model calls, every part passes, and
writes land only under `work/sandbox/`. `--live` may write the
live transcript, each speaking part's `short_term_<OT>.toml` (`.md` before 2026-09-04, R434), `work/logs/` (through
`circle_close_verify.py`) and `work/prompts/<OT>/`; `WriteGuard` enforces it. Nothing is written until
the integrity gate and the API check pass, and a run that dies before its first statement
withdraws its transcript, its working-set entry and its capture.

All console output goes through `emit(channel, text)` and all input through
`read_line(prompt, channel, prefill)` — thin wrappers over `seam.emit` / `seam.read_line`, which
`ui/circling.py` rebinds to run this same `main()` in a thread of its own process. Every emit
carries a CHANNEL ("command" or "circle") and every read a LANE; the call site is the single
source of truth for both (R221).

## MAIN
```
    parse the command line (see COMMAND-LINE ARGUMENTS)
if (--dev) then { command_surface.dev_mode = True }                    (R286: the terminal's only door)
if (--list-resumable) then { return circle_resumable_list() }
if (--dev-cmd given) then {
if (no verb) then { emit the usage line; return 2 }
    head = normalise_head(first word); rest = the remaining words; dev_mode = True for this call
if (command_dev_dispatch(head, rest) is False) then { emit "<head> needs a live circle ..."; return 2 }
    return 0
}
    problems = roster.part_verify()
if (problems) then { emit "THE ROSTER DOES NOT VERIFY — no circle opened" + each problem; return 2 }
if (neither --live nor --dry-run) then { emit "Choose a mode..." pointing at the lab; return 2 }   // R360
    parts = --parts split; refuse (return 2) any name not in PART_TAGS or without a directory
if (--seed) then { random.seed(seed) }
if (--live and the roster is reduced) then {
    emit the REDUCED LIVE ROSTER warning
if (not --yes and the answer to "type 'yes' to proceed: " is not "yes") then { emit "cancelled."; return 2 }
}
    circle_path(t) = (ROOT if live else SANDBOX)/circles/circle_<t>.md
if (--resume) then {
if (the open time is malformed) then { emit the shape; return 2 }
if (live and work/logs/close_<OT>.json exists) then { emit "already closed — refusing"; return 2 }
if (live and some short_terms exist) then {
        parse the transcript (refuse on failure)
if (every speaking part has a short_term) then { emit "already closed ... refusing"; return 2 }
        emit "close was interrupted — N written, M missing; resuming"
    }
    guard = WriteGuard(live, OT); path = circle_path(OT)
}
if (not --dry-run) then {
    import anthropic (emit "pip install anthropic" and return 2 if missing)
if (ANTHROPIC_API_KEY unset) then { load .env if python-dotenv is present }
if (still unset) then { emit llm_client.KEY_MISSING_HELP — how to get a key, where to put it, KEY
                        SECURITY (R330, 2026-08-23); return 2 }
    client = Anthropic()
}
    emit the banner: mode, open time or "assigned when the topic is entered", the TREE (and
    "A WORKTREE, not the main checkout" when it is one; a LIVE run in a worktree gets a tag-
    namespace warning), the parts, the transcript path if known, the sandbox note if not live
    emit "integrity check:"; findings, seen = record_verify.record_sweep()
if (findings) then { emit each path/defect/remedy; "The circle was NOT opened"; return 2 }
    emit "ok (N files)"
if (a key-source note applies) then { emit it }
if (client) then { emit "api check:"; why = preflight_api(client, dry); if why then { emit it; return 2 } else {
        emit "ok" } }
if (not --resume) then {
    openc = circle_state.circle_open_read() under this mode's circles/ (a failure to tell counts as one)
    interrupted = _interrupted_closes(base) if live else []
    for each interrupted close: emit "its CLOSE was interrupted", the parts missing, the resume line
if (openc) then {
        emit "N circle(s) may still be OPEN" with each path and reason
if (not --yes and the answer to "type 'yes' to open a NEW circle: " is not "yes") then { emit "cancelled."; return 2
        }
    }
}
if (not --resume) then { coalesce refresh (live only, hash-guarded — R356);
                         proposal_vet("before this circle's prompts are warmed", live) }
    core = group_shared_read()
    chosen = None ; if not --resume and issue_prompt_projection.live_nodes() then chosen = working_set_manager.working_set_ask(issue_prompt_projection, read_line=read_line_no_annotation)
        (no live issue -> no question, chosen stays None — R330, 2026-08-23)
    briefing, unknown = circle_briefing_build(chosen)
if (unknown) then { emit "unknown issue id(s) ignored: ..." }
if (chosen) then { emit on the CIRCLE channel "focus ... · related ..." or "· NO LIVE ISSUE-RELATIONSHIP reaches these" }
    for each part: sysblocks[p], notes[p] = prompt_part_assemble(p, core, briefing)
        (the retired shared_block/system_blocks pair became that one call, 2026-09-02)
    count the cached prefix — blocks 1+2 once, block 3 per part — through token_count.block_tokens
    emit "static prefix, THIS working set|whole graph: N tokens — M shared ... ($ to warm, $ per round)"
    ("ESTIMATED — no model service was asked" when not measured)
if (live and dev_mode) then { n = open topics; if n then emit "N BLOCK 2 topic(s) open (TP-) ... /topic-list ...
        /topic-close" }
    _opened = None; _cap = {"dir": None}
    define discard_unspoken(): idempotent;
        if armed and circle_transcript_discard_empty(path, OT, head bytes, live) then
        emit "circle_<OT> discarded — nothing was ever said" and remove the prompt capture by manifest
if (--resume) then {
    resumed = circle_transcript_resume_read(path, OT, parts)   (emit the error and return 2 on ValueError)
    emit "RESUMING circle_<OT> — transcript verified byte-for-byte", topic, statement count,
    last speaker, since-Self counters, "no opening round"
} else {
    topic = read_line_no_annotation("CIRCLE topic (blank = open): ", "topic", channel="circle")
        (EOF/Ctrl-C: emit "cancelled — no circle was opened."; return 2)
    OT = now as YYYY-MM-DD_HHMM; guard = WriteGuard(live, OT); path = circle_path(OT)
if (path exists) then { emit "already exists — refusing to overwrite it"; return 2 }
    open_transcript(guard, path, OT, topic); working_set_manager.working_set_record(OT, chosen, topic, live)
    emit "transcript: <path>"; _opened = {head: the file's bytes, armed: True}; atexit.register(discard_unspoken)
}
    try: pdir = prompt_capture.prompt_capture_write(cap_OT, sysblocks, notes, live, ...)   (cap_OT = OT, or OT_resume_<k>)
if (pdir and --resume) then {
        changed = _prompt_blocks_changed(prompts/<OT>, pdir, parts)
if (changed) then { emit "the emitted prompt CHANGED since this circle opened: ..." } else { emit "identical" }
    }
if (pdir) then { emit "prompts captured: <dir> (KB, parts, verified byte-for-byte; every request will be recorded)"
        }
    else { emit "prompts NOT captured — sandbox mode" }
    except: fail("prompt capture FAILED: ...")
    try: prompt_capture.prompt_turn_log_open(pdir, OT)  except: fail("per-turn capture could not be opened")
if (not --no-prewarm) then {
    emit "pre-warming caches:"; prewarm(client, parts, sysblocks, dry)
    on any exception: emit "PRE-WARM FAILED — <explanation>"; discard_unspoken(); return 2
}
    transcript = []; if topic then append the topic entry (speaker Self, is_topic, header = topic)
    since_self = {p: 0}; state = {"last": None}; issue_cmds = []; circle_ref = "<circle|sandbox>_<OT>"
    emit "/help for commands"
if (resumed) then { transcript, since_self, state come from it }
elif (--no-blind) then { emit "opening round — SEQUENTIAL"; circle_round_run(...) }
else { emit "opening round — BLIND"; circle_blind_round_run(...) }
    disarm _opened (the circle has had its opening round)
    THE SELF> LOOP — forever:
        cmd = read_line("\n<CONSOLE_NAME>> ", channel="circle").strip()
            Ctrl-C: emit "(Ctrl-C — the circle is still open. /close ... /abort ... /help ...)"; continue
            EOF: emit "(stdin closed — closing)"; break
if (cmd is "/close" or starts "/close ") then {
            props = proposal_unruled_list(transcript)
if (props and not yet shown) then { proposal_unruled_show(props); closing_confirmed = True; continue }
            break
        }
if (cmd == "/abort") then {
if (not yet confirmed) then { emit what /abort will KEEP, DISCARD, NOT collect, NOT undo; "/abort again to confirm";
        abort_confirmed = True; continue }
            aborted = True; break
        }
if (first word == "/help") then {
if (no argument) then { emit circle_pane_help() on the CIRCLE channel }          the ROOM's form (R287)
elif (argument == "all") then { emit help_text("") }                              the standalone terminal's way back
else { emit help_text(argument) }
            continue
        }
if (cmd == "/status") then { emit the tree name and mode, the part count, part_token_table(...), the running cost;
        continue }
if (cmd in ("/round", "/pass")) then { circle_round_run(...); continue }
        (no /dev branch — R286)
if (dev_mode off and cmd starts "/" and its normalised head is not in USER_SUBSET_COMMANDS) then {
            emit junk_help(cmd); continue                                          JUNK -> help (R285)
        }
if (cmd == "/issue-evidence-list") then { show_statements(transcript); continue }
        head = normalise_head(first word) if cmd starts "/" else ""                (no slash supplied here — speech
                is speech)
        define _record_practice_cmd(): append {Self, cmd, cmd: True} to the transcript and the file
if (head and command_dev_dispatch(head, rest, record=_record_practice_cmd, guard=guard)) then {
        continue }
if (head in issue_commands.HEADS) then {                                           the RULING forms
            c, why = issue_commands.issue_command_parse(cmd, circle_ref); if c is None then { emit why; continue }
if (c is issue-evidence-add) then { resolve the statement number against the transcript; emit the reason and
        continue if it fails; fill part/quote/source }
            why2 = issue_commands.issue_precheck(c, vetting.issue_graph_now_read()); if why2 then { emit it; continue }
            c["index"] = len(transcript); issue_cmds.append(c)
            append {Self, cmd, cmd: True} to the transcript and the file (RECORDED, WITHHELD FROM THE ROOM — R079)
            emit "recorded — <description>   (N pending, applied at close)"; continue
        }
if (cmd starts "/") then { emit "UNKNOWN COMMAND <head> — not sent to the room. Known: ..." and the retype hint;
        continue }
if (cmd empty) then { continue }
        raw = cmd; cmd, self_remembered = apply_self_remember(guard, Self, cmd)
if (self_remembered) then { emit "(remember recorded to self/remember.toml — stripped, private)" }
if (cmd) then { cmd = strip_malformed_annotations(cmd, Self) }
if (cmd is now empty) then {
            record = strip_malformed_annotations(raw, quiet)
if (record and the raw line carried a remember) then { append a remember_only entry and the file line }
            continue                                                               STILL A PASS — no round
        }
        record = cmd, or the raw line with malformed annotations stripped when a remember was carried
        quote_as_lands.lands_quote_apply(guard, transcript, cmd)                BEFORE the append (R155/R251)
        append {Self, cmd[, raw]} to the transcript and "[Self]: <record>" to the file
        route_annotations(Self, cmd, live); since_self = all 0; state["last"] = None
        circle_round_run(...)
    AFTER THE LOOP:
if (issue_cmds and not aborted) then {
        write circles|sandbox/circles/commands_<OT>.toml; emit "N graph ruling(s): <file>" and each description on
                the CIRCLE channel
if (live) then { ok, msg = issue_commands.issue_command_apply(issue_cmds); emit msg; if not ok then emit the re-run hint }
else { emit "SANDBOX — not applied. Review, then: python memory/issue_commands.py <file>" }
    }
elif (issue_cmds) then { emit "N graph ruling(s) DISCARDED — circle aborted" }
if (aborted) then { emit "aborted. transcript kept"; if live and a part spoke then emit the no-short_terms NOTE;
        emit METER.report(); return circle_failures_report() }
// (--minimal retired R360 — its close skipped short_terms; a dry-run close collects canned ones)
        "closed."; return circle_failures_report() }
    staged = proposal_stage(OT, transcript, issue_cmds, live); if staged then emit "N proposal(s) staged:
            ..."
    confirmed = proposal_vet("at close", live)                            CHECKPOINT 1
    emit "collecting short_terms:"; written = short_term_collect(...)
        Ctrl-C: fail("close INTERRUPTED"); emit "THE TRANSCRIPT IS INTACT", the resume line, METER.report(); return
                circle_failures_report()
if (live) then {
        run_verifier(OT); transcript_store.circle_commit(OT, written)
        emit "phase 2 — dreaming and synthesis"; if inter_circle.circle_process(OT, live=True, confirmed=confirmed,
                say=...) then fail("phase 2 ... did not complete")
} else { emit the sandbox notes; commit_sandbox(OT) }
    emit METER.report(); emit "closed. transcript: <path>" on the CIRCLE channel; return circle_failures_report()
```

## COMMAND-LINE ARGUMENTS
**ONE OF `--live` / `--dry-run` IS REQUIRED** (R360, 2026-08-27). Neither has a usable default any
more: a bare invocation prints "Choose a mode" and returns 2. The retired default was the practice
mode — real model calls whose writes went to `work/sandbox/` — and practice lives in the lab
checkout now.

- `--live`: write the live transcript, each speaking part's `short_term_<OT>.toml` (`.md` before
  2026-09-04, R434), and run `coordinator/circle_close_verify.py` at close. Default: off — and with
  `--dry-run` also off the run is refused, not sandboxed.
- `--dry-run`: no network, no API key needed; every part passes; writes only under
  `work/sandbox/`. Default: off — see the line above.
- `--parts <dirs>`: comma-separated part directories. Default: every part in `parts/` (the roster).
  A reduced LIVE roster asks for `yes` unless `--yes`.
- `--group <name>`: open on a NAMED roster from `self/groups.toml` (`coordinator/group_add.py`,
  `/group-add`) instead of `--parts` — a deliberately different roster, not a reduced one, so the
  reduced-live-roster question above does not fire for it. Mutually exclusive with `--parts`.
  Default: unset (the `--parts` roster).
- `--recall-arm off|delivered|withheld`: tier A recall (`remember_expand.py`, `docs/MEMORY_DESIGN.md`)
  — expand topic-matched seeds into each part's BLOCK 4. Default: `off`. `withheld` computes and
  logs the packs without delivering them, the trial's control arm.
- (`--minimal` retired with the practice mode, R360 2026-08-27.)

Exit codes: 0 a complete record; 1 the circle RAN and its record is incomplete (the failure
record is non-empty); 2 nothing was opened (refused, cancelled, bad arguments).

## DEPENDENCIES
Standard library: `argparse`, `atexit`, `datetime`, `os`, `pathlib`, `random`, `re`, `sys`.
This project: `identity`, `issue_commands`, `roster`, `record_verify`, `record_paths`, `seam`,
`setting_manager`, `phase_clock`, `write_guard`, `command_surface`, `llm_client`, `prompt_build`,
`annotations`, `quote_as_lands`, `propose_lifecycle`, `help_system`, `vetting`, `circle_rounds`,
`commands`, `transcript_store`, `working_set_manager`, `circle_close`, `token_count` (all
top-level); `issue_prompt_projection`, `circle_state`, `prompt_capture`, `group_add`,
`short_term_manager`, `initialization`, `recall_index`, `topic_manager` (the open-time topics
line; `topics` until 2026-09-03), `inter_circle`, `gitrepo` (imported lazily inside `main()`).
Third party, live runs only: `anthropic`, `python-dotenv` (optional).

## EXTERNAL FILES
Read: `parts/*/part.toml` (the roster), `process_core.md`, `self/best_practices.toml`,
`parts/*/mid_term.md`, `issues/*.toml`, `issues/issue_model.md`
(through `prompt_build`); `.env` (only when `ANTHROPIC_API_KEY` is unset); the transcript on
`--resume`; `work/logs/close_<OT>.json` and `parts/*/short_term_<OT>.toml` (`.md` before
2026-09-04, R434; the resume and interrupted-close checks); `self/proposals.toml`,
`self/best_practices.toml` (vetting);
`self/topics.toml` (the open-time topics line, dev on).
Written (LIVE): `circles/circle_<OT>.md` (statement by statement), `self/working_sets.toml`,
`work/prompts/<OT>/` (the Block files, `manifest.json`, one `Per_turn_*.json` per request),
`parts/<p>/short_term_<OT>.toml` (`.md` before 2026-09-04, R434), `circles/commands_<OT>.toml`
when rulings were made,
`self/remember.toml` (a `[remember: …]` at Self>), and — through the modules it calls —
`work/logs/close_<OT>.json` (`circle_close_verify.py`), the git commits and tags of
`transcript_store.circle_commit()`,
whatever `issue_commands.issue_command_apply()` and phase 2 (`inter_circle`) write. SANDBOX: the same shapes
under `work/sandbox/`; `self/` registers
written by a `cmd>` verb are written for real in either mode.
Withdrawn on a run that dies before its first statement: the transcript, the working-set
entry, the capture.

## NETWORK ACCESS
The Anthropic Messages API, through `llm_client`: one `preflight_api` request, the per-part
pre-warm, every statement and its retry, every short_term and its retry, the token counts of
`token_count.block_tokens`, and phase 2's own calls. None of it under `--dry-run`. Nothing else.

## HUMAN I/O
Prompts (lane in brackets): `type 'yes' to proceed:` [command], `type 'yes' to open a NEW
circle:` [command], `Do you have specific issues you would like to focus on today ('?' to
review) ? ` [circle — only when the live graph is non-empty], `CIRCLE topic (blank
= open):` [circle], `\n<CONSOLE_NAME>> ` [circle — the speaking turn], plus whatever the
dispatched verbs ask (`type 'yes' to apply:`, `/issue-add`'s two prompts — command lane) and
vetting's `[<id>] a)pprove, d)eny, s)kip ?` [command]. Output: the banner, every notice and
refusal on the COMMAND channel; the opening focus line, the room's help, the graph-ruling
summary and "closed." on the CIRCLE channel. Under `ui/circling.py` a command-lane question
owns the `cmd>` input row and a circle-lane opening question owns the circle pane's row.

## OPERATION

### emit(channel, text="", **kw); read_line(prompt="", channel="command", prefill="")
Thin late-binding wrappers over `seam.emit` / `seam.read_line`, so this file's ~170 call sites
see whatever the UI or a probe has rebound. `prefill` is passed by keyword (an affordance only
the dual pane honours).

### read_line_no_annotation(prompt, where, channel="circle", prefill="") -> str
```
    loop:
        raw = read_line(prompt, channel, prefill).strip(); prefill = ""
if (no annotation in raw) then { return raw }
        emit "!! [<first>] (+N more) - an annotation is not valid in the <where>."
        emit "[remember: ...] and [proposed: ...] are valid only at the <CONSOLE_NAME>> prompt ..."
        emit "Nothing was recorded. Type the <where> again."
```
The two opening prompts only (R225). EOFError/KeyboardInterrupt propagate.

### working_set_ask — MOVED to working_set_manager.py, 2026-09-03 (stage 10)
The section below describes it as it was here; the body is unchanged there, the reader is now a parameter.

### (was) working_set_ask(IP, prompt=WORKING_SET_PROMPT) -> list[str] | None
main() calls it only when `IP.live_nodes()` is non-empty (R330, 2026-08-23);
with no live issue the answer is None, silently. The prompt is "Do you have specific issues you
would like to focus on today ('?' to review) ? " (same ruling); the grammar is unchanged.
**A root counts as a live issue since R429 (2026-09-01)**
— `live_nodes()` now includes root-flagged nodes — so in a tree carrying any
root (this one carries two, and a root can never be retired) this question is
asked at every future circle open; the empty-graph skip stays for a fresh
install with no `issues/` entries at all.
```
    loop:
        raw = read_line_no_annotation(prompt, "working set", channel="circle", prefill)
            (EOF/Ctrl-C: emit "(no working set — this circle carries no issues)"; return None)
if (raw is blank or "none") then { emit "none — this circle carries no issues at all."; return None }
if (raw is "all") then { emit "all — the whole live graph."; return [] }
if (raw is "?") then { emit "N live issue(s)" and each "<id>  <label>" on the CIRCLE channel; prefill = ""; continue
        }
        pairs = IP.working_set_parse(raw); ids = their ids; focus, _, unknown = IP.issue_resolve(ids)
            (if the graph will not load: emit why; return [])
if (no unknown) then { return ids }
        emit "not issue ids: <as typed>"                                          never "node" (R279)
        prefill = the valid ones, as typed
        emit "asking again — the valid ones are: ..." or "— an issue id looks like n0010; ? lists them, Enter alone
                (or none) is no issues, all is the whole graph."
```
`[]` means "no focus, project everything"; `None` means "no issues at all".

### _interrupted_closes — MOVED to circle_close.py, 2026-09-03 (stage 12); as it was here:
For each live `circle_*.md` with no close report: parse it (skip unreadable); the parts that
spoke minus those with a `short_term_<OT>.toml` (`.md` before 2026-09-04, R434); report only when
SOME but not all are missing
(all missing is an open circle or an /abort, which circle_state's own warning covers).

### short_term_collect — MOVED to circle_close.py, 2026-09-03 (stage 12); as it was here:
```
    for each part:
if (it did not speak) then { emit "did not speak — no short_term"; continue }
        dest = <sandbox|ROOT>/parts/<p>/short_term_<OT>.toml   (.md before 2026-09-04, R434)
if (dest exists) then { emit "kept — written before the interrupt"; count it written; continue }
        attempt 1, and attempt 2 only if a section is missing or the reply was truncated:
            text, stop = call(client, part, blocks, render_messages(part, transcript, SHORT_TERM_PROMPT), 5000, dry,
                    kind="short_term")
if (a section is still missing) then { emit "FAILED — not written"; count it failed; continue }
if (splitting off the close remember would lose a heading) then { text, recorded = apply_remember(...) (the strict
        path) }
else { text, recorded = apply_close_remember(...) }
if (recorded) then { emit "remember written" }
        guard.check(dest); write "# Short-term — <Tag> — <date> <time>\n\n*(Written by the local coordinator.)*\n\n"
                + text
        emit "wrote <dest>"
if (any failed) then { fail("short_term NOT WRITTEN for: ... the transcript safety net will
        backfill them at close") }
    return written
```

### _prompt_blocks_changed — MOVED to circle_close.py, 2026-09-03 (stage 12); as it was here:
Compares the two captures' per-block sha256 from their manifests; every part on any error.

### circle_resumable_list — MOVED to circle_close.py, 2026-09-03 (stage 12); as it was here:
Circles with a transcript and no close report — including an interrupted close (some short_terms
written, some speaking parts without); a circle whose every speaking part has its short_term is
a pre-close-report close and stays hidden. Emits one block per circle; returns 0.

### circle_failures_report() -> int
```
if (the failure record is empty) then { return 0 }
    emit "N DATA FAILURE(S) THIS CIRCLE — record is incomplete:" + each, and the repair hint; return 1
```

## BUGS
None open. Both entries recorded here were re-examined 2026-08-27; one was already fixed in the
code and one was fixed that day.

WITHDRAWN 2026-08-27 — "`_interrupted_closes()` cannot see a close that died before writing ANY
short_term". True when written (2026-08-21) and false since 2026-08-23, when `circle_close_mark()`
landed with `coordinator/tests/test_close_marker.py`. The all-missing branch now reads
`len(missing) < len(spoke) or _close_began(ot_i)`, so a close that began and wrote nothing IS
reported. The function's own docstring still carried the superseded paragraph — including
"Narrowing this would need a marker written at the START of a close, which nothing writes today",
directly above the line that calls `_close_began()` — and was corrected the same day. **The
residue is real and does not shrink:** a circle that closed before 2026-08-23 has no marker, so
for those the old exemption stands and `circle_audit.py`'s transcript safety net is still the only
catch, by hand.

RESOLVED 2026-08-27 — the module docstring's stale history. It described the agent-teams mechanism
as "UNTOUCHED and fully operational" (retired 2026-07-26) and named `scripts/*.py` among its paths
(the directory was deleted 2026-08-18); its INTEROP paragraph claimed "the nightly --reconcile
guard keeps working unchanged" (no nightly since 2026-07-28). **This entry understated it.** The
same docstring's TWO MODES section still announced `sandbox (default)`, which R360 retired on
2026-08-27 — a bare invocation now refuses with exit 2 — and its RUN block offered
`python coordinator/circle.py --parts <part1>,<part2>,<part3>`, an invocation that refuses as
printed. All four corrected; the docstring now states each superseded claim and its date rather
than dropping it.
