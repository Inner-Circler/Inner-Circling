# INITIALIZATION.PY(1)

## NAME
initialization — the first-run dialogs: a part's context questions, the first issue, and the
step that runs them at a live circle open

## SYNOPSIS
```
import initialization as INIT
INIT.run_initialization(live=..., resume=..., yes=...)      # circle.py, between CHECKPOINT 2
                                                            # and the working-set question
INIT.part_context_dialog("soul", prefill=True)              # what /part-context-update runs
INIT.issue_add_dialog(seeds={...})                          # what approval of /issue-add runs
INIT.part_add_dialog(seeds={...})                           # what approval of /part-add runs
python coordinator/circle.py --dev-cmd part-context-update soul
```
Generated 2026-08-23, the day the module completed stages 0-6 of `docs/Initialization.md` — the
design, the rulings (R323-R332) and the stage record all live there; this page is the module's own
contract.

## DESCRIPTION
A fresh installation ships the Soul and the Child with universal identities and no particulars.
This module asks for the particulars — in the command pane, briefly, optionally — and records
them where each belongs: a part's answers in its own `parts/<p>/part.toml` `[context.answers]`
(through `roster.write_context()`, the one writer), a first issue through
`commands.cmd_issue_add()` (the one gate-before-write path), a new part through
`part_add.part_add()`. Nothing here renders into a prompt: BLOCK 3 rendering is
`prompt_build.identity_tail()`'s, at assembly, through each question's own `render` string — a
question that declares none is recorded-only (R329; the Soul's two name keys).

Every dialog is the same shape (BNF: `DIALOG`): a purpose, the privacy and optional statements
ONCE PER PROCESS (whichever dialog comes first prints them), numbered questions on the COMMAND
lane, one `OUTCOME` line. Every question carries `data_type`/`data_max` and may carry `unique_in`,
all read from the file at call time — a hand-tuned cap is live at the next dialog (R332). An
invalid answer is described in one line and the same question asked again, until valid or empty;
empty is always valid. A seeded question (a recorded answer prefilled, or a bracket's string at
approval) takes Enter as keep and `-` alone as clear.

## COMMAND-LINE ARGUMENTS
None of its own — reached through `circle.py` (the step and `--dev-cmd`), the Self> loop, and the
dual pane's command pane, all via `commands.dispatch_dev_cmd()`.

## DEPENDENCIES
`roster` (the `[context]` reader/writer and the tag spaces), `seam` (every emit and read),
`llm_client` (PROVIDER/MODEL for the privacy statement), `part_add` and `commands` and
`issue_schema` lazily. `coordinator/initialization.toml` holds the four statements and the issue
and part dialogs' questions; a part's context questions live in its own `part.toml` (R331).

## EXTERNAL FILES
Read: `initialization.toml`, `parts/*/part.toml`, `issues/*` (through issue_schema, for the
trigger and the unique spaces). Written: `parts/<p>/part.toml` (the answers block only),
`issues/nNNNN.toml` + `INDEX.md` (through cmd_issue_add), `parts/<name>/` (through part_add) —
and one git commit of exactly those paths at the end of the step, non-fatal.

## NETWORK ACCESS
None. The privacy statement names where answers will later travel; this module sends nothing.

## HUMAN I/O
All prompts `#/# <question>? ` on the COMMAND lane (the cmd> input row in the dual pane); the
current value said in words wherever a line cannot be seeded. The handover: `state`
"initializing" (focus to the command pane), the dialogs, `Starting your circle...`, `state`
"initialized" (focus back), `state` "" (the engine's token cleared).

## OPERATION

### run_initialization(*, live, resume, yes) -> list[str]
```
if (not live or resume or yes) then { return [] }                        silent, all four skips
if (seam.read_line is the terminal default and stdin is not a TTY) then { return [] }
    due_parts = pending_part_dialogs()          declared [context], nothing recorded;
                                                Soul, Child, then roster order (R324/R331)
    due_issue = issue_dialog_due()              issues/ holds no node of ANY status
if (nothing due) then { return [] }             nothing printed, nothing moved
    emit state "initializing"
    for each due part: part_context_dialog(part)          completed -> its part.toml recorded
if (due_issue) then { issue_add_dialog() }                a new node (+ INDEX.md) recorded
    emit "Starting your circle..."; emit state "initialized"; emit state ""
if (anything written) then { _commit(written) }           own paths only, non-fatal
```

### part_context_dialog(part, *, prefill=False, base=None) -> str
"completed" | "skipped" | "unchanged" | "none". First-run form: empty skips a question, an
all-empty round writes nothing and repeats next open (R327 — no decline). Prefilled form
(/part-context-update, R326): Enter keeps, `-` clears, an unchanged round writes nothing.

### issue_add_dialog(*, guard=None, write=None, seeds=None) -> str
Six questions ([issue] in the TOML). The four descriptive answers compose the description in the
§3.4 shape; label is UNIQUE_IN issue_labels; an empty label derives from the description's first
six words; an empty absence opens a LEAD, said. Writer default:
`cmd_issue_add(values=(label, description, absence))`. Does not loop (R324).

### part_add_dialog(*, seeds=None, write=None) -> str
Two questions ([part] in the TOML); the directory name derives from the Tag and is asked for only
when the derivation collides or empties. Writer default `part_add.part_add()`; a register refusal
is echoed and the questions return, seeded. "skipped" at approval leaves the proposal PENDING.

### validate(question, answer, *, part="") -> str | None
The one validator (R332 + addenda): empty always valid; STRING by length; NUMERIC_STRING
numerals-only by value; `unique_in` refused against the live space; a square bracket in a STRING
refused (the annotation grammar — Claude's, named in the design).

### cmd_part_context_update / _list / _clear, cmd_part_add
The cmd> verbs (§6 of the design): update re-runs the dialog prefilled; list is read-only; clear
empties after 'yes' and re-arms the first-run trigger; /part-add opens the dialog, its two quoted
strings seeded when given. Each refuses a non-interactive surface with where it works.

## BUGS
The statements-once flag is per PROCESS, not per circle open — a second open inside one dual-pane
session would not reprint them. Today a session opens one circle, so the difference has no
observable case; noted so a multi-open future knows where to look.
