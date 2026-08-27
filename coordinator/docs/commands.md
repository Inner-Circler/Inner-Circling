# COMMANDS.PY(1)

## NAME
commands — the command-pane verbs' implementations and their ONE dispatcher, `dispatch_dev_cmd()`

## SYNOPSIS
```
from commands import dispatch_dev_cmd, resolve_statement, show_statements
dispatch_dev_cmd(head, rest_text, *, record=None, guard=None) -> bool
```
No `main()`, no command line of its own: the three doors into the dispatcher are `circle.py
--dev-cmd VERB ...`, `ui/circling.py`'s command pane with no circle running, and — since B61,
2026-08-21 — `circle.py`'s Self> loop itself for every verb that does not need the open circle.
Generated 2026-08-21 (B65) against the module after B61 and B64.

## DESCRIPTION
`dispatch_dev_cmd()` is the one place a no-circle verb is wired: it matches a normalised head
and calls that verb's `cmd_*` function, returning True if it recognised the head and False
otherwise (the caller then refuses with its own reason — a ruling form that needs the open
circle, or an unknown word). Four keyword-only parameters carry what only a running circle can
supply: `record` (the RECORDED-NOT-SENT transcript step the three write verbs fire on success),
`guard` (the circle's WriteGuard, read by
`/remember` for its one-per-circle cap and by `/issue-add` for `opened`). `statements()`,
`resolve_statement()` and `show_statements()` are the 1-based numbering `/issue-evidence-list` prints and
`/issue-evidence-add` addresses into. All console I/O goes through `seam.emit` /
`seam.read_line` by attribute access so the dual pane and the probes can redirect it. Every
surfaced string says "issue"/"relation", never "node"/"edge" (R279).

## MAIN
```
    (none — the module has no entry point)
```

## COMMAND-LINE ARGUMENTS
None here. `circle.py --dev-cmd VERB [args...]` reaches `dispatch_dev_cmd()` with dev mode
forced on for that one call.

## DEPENDENCIES
- `pathlib`, `subprocess`, `sys`, and (lazily) `datetime`, `shutil`, `tempfile`
- `issue_schema` (the one reader/writer of an issue file), `seam`, `transcript_store`
  (`withheld()`), `command_surface` (`ISSUE_NODE_RE`), `help_system` (`cmd_help`, `HELP_WIDTH`),
  `paths` (`ROOT`)
- lazily, per verb: `prompt_show`, `remember`, `topics`, `check_best_practices`, `proposals`,
  `write_guard`

## EXTERNAL FILES
Read: `issues/*.toml` (listings, status reads, `/issue-add`'s id and gate copy),
`self/remember.toml` (`/remember-list`), `self/best_practices.toml` (`/practice-list`,
`/better-option-list`), `self/topics.toml` (`/topic-list`), `self/proposals.toml`
(`/propose-list`).
Written: `self/remember.toml` (`/remember`, via `remember.add`), `self/best_practices.toml`
(`/practice-add`, `/better-option-add`, `/practice-delete`), `self/topics.toml`
(`/topic-close`), `issues/L_nNNNN.toml` and `issues/INDEX.md` (`/issue-add`, after the gate
passes on a temporary copy of `issues/`), and — through subprocesses — whatever
`memory/issue_status.py` and `memory/issue_commands.py` write.
Subprocesses (`_run_captured`, `sys.executable` in `ROOT`): `memory/issue_commands.py`
(`/issue-apply`), `memory/issue_status.py` (`/issue-status … = <value>`, dry-run then apply),
`memory/issue_gate.py <tempdir>` and `memory/issue_index.py` (`/issue-add`).
A temporary directory (`issue_add_*`) holds the gate copy and is removed afterwards.

## NETWORK ACCESS
None.

## HUMAN I/O
Output on the COMMAND channel only. Input via `seam.read_line` (command lane): `/issue-status
nNNNN = <value>` asks `  type 'yes' to apply: ` unless `--yes`/`-y` was given; `/issue-add`
asks for the description and the absence clause. Under the dual pane with no circle running
those reads return "" at once and the verb refuses cleanly.

## OPERATION

### statements(transcript) -> [(index, entry)]
Every transcript entry that is not a scribe note and not withheld (a remember-only turn, an
echoed `/issue` command) — the addressable statements, 1-based by position in this list.

### resolve_statement(transcript, n) -> (entry | None, why)
```
if (n outside 1..len(statements)) then { return (None, "no statement #n — /issue-evidence-list shows 1-N") }
    return (the entry at n, "")
```

### show_statements(transcript) -> None
One emitted row per statement: `  <n>. <display>  <text flattened, cut to the 80-column budget>`.

### cmd_prompt_show(who)
Emits `prompt_show.render(who)`.

### cmd_remember_list(rest) -> None   (alias cmd_recall)
```
if (rest empty) then { emit remember.recall_listing(SELF) }
elif (rest is not digits) then { emit the usage line }
else { emit remember.recall_record(int(rest), SELF) }
```
Self's own register only; no `<part>` form exists.

### cmd_remember(text, guard=None) -> None
```
    body = text with whitespace collapsed
if (body empty) then { emit "usage: /remember <text>"; return }
    g = guard, or _NoCircleGuard() (live, no open time — the cap does not apply)
if (g has an open time and has_remembered(SELF, g)) then { emit "second REMEMBER this circle — not written"; return
        }
    rec = remember.add(SELF, g, body); emit "remembered — <first 56 chars>" and where it went
```

### cmd_topic_list(); cmd_topic_close(rest)
Emit `topics.listing()`; close the named `TP-nnnn` (usage line if none) and emit the result.

### cmd_practice_list(); cmd_better_option_list()
`check_best_practices.listing(better_options=False)` — the rows NOT addressed to Self — and
`listing(better_options=True)` — the Self rows — each numbered on its own.

### cmd_propose_list() -> None
```
    pend = proposals with state "proposed"; settled = the rest; legacy = check_best_practices.pending()
if (all three empty) then { emit "no proposals on file"; return }
    emit PENDING (numbered rows), then PENDING staged as a practice row, then SETTLED
```

### cmd_practice_delete(arg, record=None)
```
if (arg not digits) then { usage line — "the number /practice-list showed (not /better-option-list's)"; return }
    ok, msg = check_best_practices.delete(n); emit msg
if (ok and record given) then { record() }
```

### _add_practice_row(text, addressee, usage, record); cmd_practice_add; cmd_better_option_add
```
if (text empty after collapsing) then { emit the usage line; return }
    ok, msg = check_best_practices.add(text, addressee=addressee); emit msg
if (ok and record given) then { record() }
```
Two verbs, one body: "All parts" vs "Self" is the only difference (R133).

### _run_captured(argv) -> (output, returncode)
Runs `sys.executable argv` in `ROOT`, capturing stdout+stderr.

### cmd_issue_apply(rest)
```
if (no argument) then { emit "usage: /issue-apply <commands.toml>"; return }
    run memory/issue_commands.py <args>; emit its output
```

### cmd_issue_status_show(issue_id)
Emits `  <id>: <status>` or `  no such issue: <id>`.

### cmd_issue_status_set(issue_id, val, trailing) -> bool
```
if (val not a known status) then { emit the known statuses; return False }
    yes = "--yes" or "-y" in trailing; strip --yes/-y/--dry-run from trailing
    run issue_status.py <id> --to <val> --dry-run <trailing>; emit its output
if (dry-run exit != 0) then { return False }
if (not yes) then { read "  type 'yes' to apply: "; if not "yes" then { emit "cancelled — no change made"; return
        False } }
    run issue_status.py <id> --to <val> <trailing>; emit its output
if (exit != 0) then { emit "the apply itself FAILED (exit N)"; return False }
    return True
```

### cmd_issue_status_op(issue_id, op_raw, trailing) -> bool
Parses `= <value>` from `op_raw` or `trailing` (or a leading `show`); a value → `cmd_issue_status_set`,
else `cmd_issue_status_show` and True.

### dispatch_dev_cmd(head, rest_text, *, record=None, guard=None) -> bool
```
if (head == "/help") then { cmd_help(rest_text) }
elif (head == "/practice-add") then { cmd_practice_add(rest_text, record=record) }
elif (head == "/practice-list") then { cmd_practice_list() }
elif (head == "/practice-delete") then { cmd_practice_delete(rest_text, record=record) }
elif (head == "/better-option-add") then { cmd_better_option_add(rest_text, record=record) }
elif (head == "/remember-list") then { cmd_remember_list(rest_text) }      (/recall normalises here)
elif (head == "/remember") then { cmd_remember(rest_text, guard=guard) }
elif (head == "/better-option-list") then { cmd_better_option_list() }
elif (head == "/propose-list") then { cmd_propose_list() }
elif (head == "/issue-relationship-list") then { cmd_issue_relationship_list() }
elif (head == "/issue-add") then { cmd_issue_add(rest_text, guard=guard) }
elif (head == "/topic-list") then { cmd_topic_list() }
elif (head == "/topic-close") then { cmd_topic_close(rest_text) }
elif (head == "/prompt-show") then { cmd_prompt_show(first word or "circle") }
elif (head == "/issue-apply") then { cmd_issue_apply(rest_text.split()) }
elif (head == "/issue-list") then { cmd_issue_list() }
elif (head in ("/issue-status", "/issue-status-update")) then {
if (no tokens) then {
if (head == "/issue-status") then { cmd_issue_status_all() } else { emit the usage line }
        return True
    }
    rest = tokens after the id; for /issue-status-update prepend "=" (the synonym's argument IS the value)
    cmd_issue_property(id, "status", rest)
}
else { return False }
    return True
```

### cmd_issue_list()
Every issue on file, sorted, numbered: header `N issue(s), M live`, then `  <n>  <id>  <label>`.
Emits "no issues on file" when there are none.

### cmd_issue_status_all()
Every issue on file: `  <n>  <id>  <status>  <label>`; "no issues on file" when none.

### cmd_issue_relationship_list()
```
if (no live issue) then { emit "no live issues"; return }
    per live issue, sorted: "  <id>  <label>", then per non-retired edge
    "         <type> <target>  (<status>)  <target label>", or "(no live issue-relationships)"
    a header line "N live issue(s), M live relation(s)" is inserted after the leading blank
```

### _next_issue_id() -> str
One past the largest `nNNNN` on file, every status counted (ids are never reused).

### cmd_issue_add(rest, guard=None) -> None
```
    (label, desc, absence) = _issue_add_args(rest)        "label" ["description" ["absence"]]; a bare text is the label
if (label empty) then { emit usage; return False }
if (interactive and desc empty) then { desc = read_line("  description (what the issue IS; Enter to leave it for later): ") }
if (interactive and absence empty) then { absence = read_line("  absence (...; Enter to leave it for later): ") }
    status = "live" if (desc and absence) else "lead"; nid = _next_issue_id(); today = ISO date
if (guard has an open time) then { opened = "<circle|sandbox>_<OT> (Self, /issue-add)" }
else { opened = today }                                      (the gate admits a bare date there, R290)
    doc = {id, label, status, opened, held_by [], description, absence,
           description_history "- **<today>** — opened by Self via /issue-add in <ref|date>; ..."}
    fails = issue_schema.check(doc, issues/<prefix><nid>.toml)
if (fails) then { emit "refused — the schema: ..."; return False }
    copy issues/*.toml to a temp dir, save the candidate there, run memory/issue_gate.py <tempdir>, remove the dir
if (the gate exited non-zero) then { emit "refused by the gate — nothing written:" + its FAIL lines; return False }
    issue_schema.save(issues/<prefix><nid>.toml, doc); emit "wrote ... — <nid> is LIVE" | "... is a LEAD: its ... still to be written"
if (issue_schema.ISSUES is not the real issues/) then { return True }          (a probe on a copy)
    run memory/issue_index.py; emit its last line; if it failed, say how to revert INDEX.md; return True
```
LIVE when complete, a LEAD when not (2026-08-21, D58; R290 retired R001's "evidence is the only thing that opens an issue"): all three strings -> a live issue nobody holds yet; a missing description or absence -> L_nNNNN until it is written. `interactive=False` (vetting's approval path) asks nothing, so a `[proposed: /issue-add ...]` that carried only a label opens a lead. Returns True only when a file was written — the bool vetting rests on.

### cmd_issue_property(issue_id, prop, rest) -> bool
```
if (id does not match nNNNN) then { emit "'<id>' is not an issue id (nNNNN)"; return False }
if (prop != "status") then { emit "unknown property ... Known: status"; return False }
if (rest empty) then { cmd_issue_status_show(id); return True }
    return cmd_issue_status_op(id, "status", rest)
```

## BUGS
- `cmd_issue_status_all()` and `cmd_issue_list()` read every file under `issues/` on each call;
  fine at the graph's size (tens of files), not designed for thousands.
- `cmd_issue_add()`'s gate copy copies every `issues/*.toml` into a temp dir per call — correct
  and cheap today, but it is a whole-graph copy for one write.
