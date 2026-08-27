# CIRCLE.PY(1)

## NAME
circle — the driver: opens an IFS inner circle, assembles each part's four prompt blocks, runs
the Self> loop, closes, and hands the closed circle to phase 2

## SYNOPSIS
```
python coordinator/circle.py --dry-run
python coordinator/circle.py --live
python coordinator/circle.py (--live | --dry-run) [--parts <dir>,<dir>,...]
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
`rounds`, `markers`, `vetting`, `command_surface`, `commands`, `help_system`, `quote_as_mark`,
`prompt_capture`, `token_count`, `inter_circle`, and the issue-graph code under `memory/`.

Two modes. SANDBOX (the default) writes only under `work/sandbox/`; `--live` may write the
live transcript, each speaking part's `short_term_<OT>.md`, `work/logs/` (through
`circle_close.py`) and `work/prompts/<OT>/`; `WriteGuard` enforces it. Nothing is written until
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
if (--list-resumable) then { return list_resumable() }
if (--dev-cmd given) then {
if (no verb) then { emit the usage line; return 2 }
    head = normalise_head(first word); rest = the remaining words; dev_mode = True for this call
if (dispatch_dev_cmd(head, rest) is False) then { emit "<head> needs a live circle ..."; return 2 }
    return 0
}
    problems = roster.verify()
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
    emit "integrity check:"; findings, seen = check_integrity.sweep()
if (findings) then { emit each path/defect/remedy; "The circle was NOT opened"; return 2 }
    emit "ok (N files)"
if (a key-source note applies) then { emit it }
if (client) then { emit "api check:"; why = preflight_api(client, dry); if why then { emit it; return 2 } else {
        emit "ok" } }
if (not --resume) then {
    openc = circle_state.open_circles() under this mode's circles/ (a failure to tell counts as one)
    interrupted = _interrupted_closes(base) if live else []
    for each interrupted close: emit "its CLOSE was interrupted", the parts missing, the resume line
if (openc) then {
        emit "N circle(s) may still be OPEN" with each path and reason
if (not --yes and the answer to "type 'yes' to open a NEW circle: " is not "yes") then { emit "cancelled."; return 2
        }
    }
}
if (not --resume) then { coalesce refresh (live only, hash-guarded — R356); vet_pending_proposals("before this circle's prompts are warmed", live) }
    core = load_shared()
    chosen = None ; if not --resume and issue_projection.live_nodes() then chosen = ask_working_set(issue_projection)
        (no live issue -> no question, chosen stays None — R330, 2026-08-23)
    briefing, unknown = build_briefing(chosen)
if (unknown) then { emit "unknown issue id(s) ignored: ..." }
if (chosen) then { emit on the CIRCLE channel "focus ... · related ..." or "· NO LIVE ISSUE-RELATIONSHIP reaches these" }
    for each part: shared, notes[p] = shared_block(p, briefing); sysblocks[p] = system_blocks(...)
    count the cached prefix — blocks 1+2 once, block 3 per part — through token_count.block_tokens
    emit "static prefix, THIS working set|whole graph: N tokens — M shared ... ($ to warm, $ per round)"
    ("ESTIMATED — no model service was asked" when not measured)
if (live and dev_mode) then { n = open topics; if n then emit "N BLOCK 2 topic(s) open (TP-) ... /topic-list ...
        /topic-close" }
    _opened = None; _cap = {"dir": None}
    define discard_unspoken(): idempotent; if armed and discard_empty_open(path, OT, head bytes, live) then
        emit "circle_<OT> discarded — nothing was ever said" and remove the prompt capture by manifest
if (--resume) then {
    resumed = load_for_resume(path, OT, parts)   (emit the error and return 2 on ValueError)
    emit "RESUMING circle_<OT> — transcript verified byte-for-byte", topic, statement count,
    last speaker, since-Self counters, "no opening round"
} else {
    topic = read_line_no_annotation("CIRCLE topic (blank = open): ", "topic", channel="circle")
        (EOF/Ctrl-C: emit "cancelled — no circle was opened."; return 2)
    OT = now as YYYY-MM-DD_HHMM; guard = WriteGuard(live, OT); path = circle_path(OT)
if (path exists) then { emit "already exists — refusing to overwrite it"; return 2 }
    open_transcript(guard, path, OT, topic); record_working_set(OT, chosen, topic, live)
    emit "transcript: <path>"; _opened = {head: the file's bytes, armed: True}; atexit.register(discard_unspoken)
}
    try: pdir = prompt_capture.write(cap_OT, sysblocks, notes, live, ...)   (cap_OT = OT, or OT_resume_<k>)
if (pdir and --resume) then {
        changed = _prompt_blocks_changed(prompts/<OT>, pdir, parts)
if (changed) then { emit "the emitted prompt CHANGED since this circle opened: ..." } else { emit "identical" }
    }
if (pdir) then { emit "prompts captured: <dir> (KB, parts, verified byte-for-byte; every request will be recorded)"
        }
    else { emit "prompts NOT captured — sandbox mode" }
    except: fail("prompt capture FAILED: ...")
    try: prompt_capture.open_turn_log(pdir, OT)  except: fail("per-turn capture could not be opened")
if (not --no-prewarm) then {
    emit "pre-warming caches:"; prewarm(client, parts, sysblocks, dry)
    on any exception: emit "PRE-WARM FAILED — <explanation>"; discard_unspoken(); return 2
}
    transcript = []; if topic then append the topic entry (speaker Self, is_topic, header = topic)
    since_self = {p: 0}; state = {"last": None}; issue_cmds = []; circle_ref = "<circle|sandbox>_<OT>"
    emit "/help for commands"
if (resumed) then { transcript, since_self, state come from it }
elif (--no-blind) then { emit "opening round — SEQUENTIAL"; run_round(...) }
else { emit "opening round — BLIND"; run_blind_round(...) }
    disarm _opened (the circle has had its opening round)
    THE SELF> LOOP — forever:
        cmd = read_line("\n<CONSOLE_NAME>> ", channel="circle").strip()
            Ctrl-C: emit "(Ctrl-C — the circle is still open. /close ... /abort ... /help ...)"; continue
            EOF: emit "(stdin closed — closing)"; break
if (cmd is "/close" or starts "/close ") then {
            props = unruled_proposals(transcript)
if (props and not yet shown) then { show_unruled_proposals(props); closing_confirmed = True; continue }
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
if (cmd == "/status") then { emit the tree name and mode, the part count, token_table(...), the running cost;
        continue }
if (cmd in ("/round", "/pass")) then { run_round(...); continue }
        (no /dev branch — R286)
if (dev_mode off and cmd starts "/" and its normalised head is not in USER_SUBSET_COMMANDS) then {
            emit junk_help(cmd); continue                                          JUNK -> help (R285)
        }
if (cmd == "/issue-evidence-list") then { show_statements(transcript); continue }
        head = normalise_head(first word) if cmd starts "/" else ""                (no slash supplied here — speech
                is speech)
        define _record_practice_cmd(): append {Self, cmd, cmd: True} to the transcript and the file
if (head and dispatch_dev_cmd(head, rest, record=_record_practice_cmd, guard=guard)) then {
        continue }
if (head in issue_commands.HEADS) then {                                           the RULING forms
            c, why = issue_commands.parse(cmd, circle_ref); if c is None then { emit why; continue }
if (c is issue-evidence-add) then { resolve the statement number against the transcript; emit the reason and
        continue if it fails; fill part/quote/source }
            why2 = issue_commands.precheck(c, vetting.graph_now()); if why2 then { emit it; continue }
            c["index"] = len(transcript); issue_cmds.append(c)
            append {Self, cmd, cmd: True} to the transcript and the file (RECORDED, WITHHELD FROM THE ROOM — R079)
            emit "recorded — <description>   (N pending, applied at close)"; continue
        }
if (cmd starts "/") then { emit "UNKNOWN COMMAND <head> — not sent to the room. Known: ..." and the retype hint;
        continue }
if (cmd empty) then { continue }
        raw = cmd; cmd, self_remembered = apply_self_remember(guard, Self, cmd)
if (self_remembered) then { emit "(remember recorded to self/remember.toml — stripped, private)" }
if (cmd) then { cmd = strip_malformed_markers(cmd, Self) }
if (cmd is now empty) then {
            record = strip_malformed_markers(raw, quiet)
if (record and the raw line carried a remember) then { append a remember_only entry and the file line }
            continue                                                               STILL A PASS — no round
        }
        record = cmd, or the raw line with malformed markers stripped when a remember was carried
        quote_as_mark.apply_quote_as_mark(guard, transcript, cmd)                  BEFORE the append (R155/R251)
        append {Self, cmd[, raw]} to the transcript and "[Self]: <record>" to the file
        route_markers(Self, cmd, live); since_self = all 0; state["last"] = None
        run_round(...)
    AFTER THE LOOP:
if (issue_cmds and not aborted) then {
        write circles|sandbox/circles/commands_<OT>.toml; emit "N graph ruling(s): <file>" and each description on
                the CIRCLE channel
if (live) then { ok, msg = issue_commands.apply(issue_cmds); emit msg; if not ok then emit the re-run hint }
else { emit "SANDBOX — not applied. Review, then: python memory/issue_commands.py <file>" }
    }
elif (issue_cmds) then { emit "N graph ruling(s) DISCARDED — circle aborted" }
if (aborted) then { emit "aborted. transcript kept"; if live and a part spoke then emit the no-short_terms NOTE;
        emit METER.report(); return report_failures() }
// (--minimal retired R360 — its close skipped short_terms; a dry-run close collects canned ones)
        "closed."; return report_failures() }
    staged = stage_propose_proposals(OT, transcript, issue_cmds, live); if staged then emit "N proposal(s) staged:
            ..."
    confirmed = vet_pending_proposals("at close", live)                            CHECKPOINT 1
    emit "collecting short_terms:"; written = collect_short_terms(...)
        Ctrl-C: fail("close INTERRUPTED"); emit "THE TRANSCRIPT IS INTACT", the resume line, METER.report(); return
                report_failures()
if (live) then {
        run_verifier(OT); commit_circle(OT, written)
        emit "phase 2 — dreaming and synthesis"; if inter_circle.process_circle(OT, live=True, confirmed=confirmed,
                say=...) then fail("phase 2 ... did not complete")
} else { emit the sandbox notes; commit_sandbox(OT) }
    emit METER.report(); emit "closed. transcript: <path>" on the CIRCLE channel; return report_failures()
```

## COMMAND-LINE ARGUMENTS
- `--live`: write the live transcript, each speaking part's `short_term_<OT>.md`, and run
  `coordinator/circle_close.py` at close. Default: off (sandbox — writes land under `work/sandbox/` only).
- `--dry-run`: no network, no API key needed; every part passes. Default: off.
- `--parts <dirs>`: comma-separated part directories. Default: every part in `parts/` (the roster).
  A reduced LIVE roster asks for `yes` unless `--yes`.
- (`--minimal` retired with the practice mode, R360 2026-08-27.)

Exit codes: 0 a complete record; 1 the circle RAN and its record is incomplete (the failure
ledger is non-empty); 2 nothing was opened (refused, cancelled, bad arguments).

## DEPENDENCIES
Standard library: `argparse`, `atexit`, `datetime`, `os`, `pathlib`, `random`, `re`, `sys`.
This project: `identity`, `issue_commands`, `roster`, `check_integrity`, `paths`, `seam`,
`write_guard`, `command_surface`, `llm_client`, `prompt_build`, `markers`, `quote_as_mark`,
`help_system`, `vetting`, `rounds`, `commands`, `transcript_store`, `token_count`,
`issue_projection`, `circle_state`, `prompt_capture`, `topics`, `inter_circle`, `gitrepo`
(the last six imported lazily inside `main()`; `transcript_store` and `token_count` are top-level). Third party, live runs only: `anthropic`,
`python-dotenv` (optional).

## EXTERNAL FILES
Read: `parts/*/part.toml` (the roster), `process_core.md`, `self/best_practices.toml`,
`parts/*/mid_term.md`, `issues/*.toml`, `issues/issue_model.md`
(through `prompt_build`); `.env` (only when `ANTHROPIC_API_KEY` is unset); the transcript on
`--resume`; `work/logs/close_<OT>.json` and `parts/*/short_term_<OT>.md` (the resume and
interrupted-close checks); `self/proposals.toml`, `self/best_practices.toml` (vetting);
`self/topics.toml` (the open-time topics line, dev on).
Written (LIVE): `circles/circle_<OT>.md` (statement by statement), `self/working_sets.toml`,
`work/prompts/<OT>/` (the Block files, `manifest.json`, one `Per_turn_*.json` per request),
`parts/<p>/short_term_<OT>.md`, `circles/commands_<OT>.toml` when rulings were made,
`self/remember.toml` (a `[remember: …]` at Self>), and — through the modules it calls —
`work/logs/close_<OT>.json` (`circle_close.py`), the git commits and tags of `commit_circle()`,
whatever `issue_commands.apply()` and phase 2 (`inter_circle`) write. SANDBOX: the same shapes
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

### ask_working_set(IP, prompt=WORKING_SET_PROMPT) -> list[str] | None
main() calls it only when `IP.live_nodes()` is non-empty (R330, 2026-08-23);
with no live issue the answer is None, silently. The prompt is "Do you have specific issues you
would like to focus on today ('?' to review) ? " (same ruling); the grammar is unchanged.
```
    loop:
        raw = read_line_no_annotation(prompt, "working set", channel="circle", prefill)
            (EOF/Ctrl-C: emit "(no working set — this circle carries no issues)"; return None)
if (raw is blank or "none") then { emit "none — this circle carries no issues at all."; return None }
if (raw is "all") then { emit "all — the whole live graph."; return [] }
if (raw is "?") then { emit "N live issue(s)" and each "<id>  <label>" on the CIRCLE channel; prefill = ""; continue
        }
        pairs = IP.parse_working_set_pairs(raw); ids = their ids; focus, _, unknown = IP.resolve(ids)
            (if the graph will not load: emit why; return [])
if (no unknown) then { return ids }
        emit "not issue ids: <as typed>"                                          never "node" (R279)
        prefill = the valid ones, as typed
        emit "asking again — the valid ones are: ..." or "— an issue id looks like n0010; ? lists them, Enter alone
                (or none) is no issues, all is the whole graph."
```
`[]` means "no focus, project everything"; `None` means "no issues at all".

### _interrupted_closes(base) -> [(OT, [missing part tags])]
For each live `circle_*.md` with no close report: parse it (skip unreadable); the parts that
spoke minus those with a `short_term_<OT>.md`; report only when SOME but not all are missing
(all missing is an open circle or an /abort, which circle_state's own warning covers).

### collect_short_terms(client, parts, sysblocks, transcript, ot, guard, dry) -> [written]
```
    for each part:
if (it did not speak) then { emit "did not speak — no short_term"; continue }
        dest = <sandbox|ROOT>/parts/<p>/short_term_<OT>.md
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
if (any failed) then { fail("short_term NOT WRITTEN for: ... the nightly transcript safety net will have to
        backfill") }
    return written
```

### _prompt_blocks_changed(orig, new, parts) -> [parts]
Compares the two captures' per-block sha256 from their manifests; every part on any error.

### list_resumable() -> int
Circles with a transcript and no close report — including an interrupted close (some short_terms
written, some speaking parts without); a circle whose every speaking part has its short_term is
a pre-close-report close and stays hidden. Emits one block per circle; returns 0.

### report_failures() -> int
```
if (the failure ledger is empty) then { return 0 }
    emit "N DATA FAILURE(S) THIS CIRCLE — record is incomplete:" + each, and the repair hint; return 1
```

## BUGS
- `_interrupted_closes()` cannot see a close that died before writing ANY short_term; after the
  45-minute quiet window neither it nor `circle_state` reports one. Stated in its docstring;
  `circle_audit.py`'s safety net is the catch, by hand.
- The module docstring's WHAT THIS IS section still describes the agent-teams mechanism as
  "untouched and fully operational" (retired 2026-07-26), and its INTEROP paragraph says "the
  nightly --reconcile guard keeps working unchanged" (no nightly since 2026-07-28; circle_audit.py
  phase 2 runs --reconcile, by hand). History, not behaviour; the RUN section is four shell lines.
