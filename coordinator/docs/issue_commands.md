# ISSUE_COMMANDS(1)

## NAME
issue_commands.py — parses, records, and applies Self's in-circle `/issue` graph rulings (`issue-label-update`, `issue-relationship-add`) against the issue graph

## SYNOPSIS
    python memory/issue_commands.py <record.toml> [--dry-run]

In-circle, the commands this module parses are typed as:

    /issue-label-update  nNNNN "new name" ["comment"]
    /issue-relationship-add  nNNNN <type> nMMMM ["comment"]

As a library it is imported by `circle.py` (for `issue_command_parse()`/`issue_precheck()`/`issue_describe()` during a live circle) and by `ic.py`'s `issue-apply` verb (which shells out to this file's own CLI).

## DESCRIPTION
This module implements three load-bearing rulings from 2026-08-04. First, and most structurally important: a `/issue` command is echoed into the transcript as a statement from Self, and is explicitly *not* sent to the parts. This single decision resolves a design deadlock — a graph edge cannot be `attested` without a verbatim quote from a real circle, and until this ruling, Self typing a command was not itself "saying" anything on the record. Once the command line is itself Self's transcript words, the graph gate can verify the resulting edge by the exact same rule it applies to everything else, with no special exemption required. The second half of the same ruling — that the command is *not* sent to the parts — closes a related failure: on 2026-08-01, a command that did not yet exist fell through to the room and became content a part reacted to (the Idealist, per the module's own reference, called a mark "the ember-tending act"). A ruling about the graph is not addressed to the room, and letting the room react to it would contaminate the very record the ruling is meant to be drawn from.

Second, the verb is named `issue-label-update`, not `update` — naming exactly what changes.

Third, a *live* circle applies its recorded commands automatically at close; a *sandbox* circle records them but applies nothing, which is what lets a sandbox circle propose changes to the live tree without ever touching it.

Commands are deliberately applied at circle close rather than immediately, because each part's briefing is compiled into its system prompt at circle open; a mid-circle graph write would either never reach the room in that circle, or would require rebuilding and re-caching all seven parts' prompts mid-circle for no benefit.

Validation is strictly all-or-nothing: `issue_command_apply()` copies the entire `issues/` directory to a temp location, applies every pending command there, and runs the real gate (`issue_gate.py`) over that copy. The live tree is written only if the whole batch passes; `issue_gate.py` already accepted a directory argument for exactly this purpose.

## MAIN
This module has no `main()` function. Its `if __name__ == "__main__":` block is a small flat CLI script, not a defined entry point function; it is documented here in the same if/then/else style since it is the module's only top-level execution path.

    {
        parse arguments via argparse: a required `record` path (a circle's commands.toml) and an optional `--dry-run` flag.
    }
    {
        load the TOML record, attach the record's own `circle` value onto every parsed command dict, and print a one-line summary (circle name, command count) followed by issue_describe() for each command.
    }
    {
        call issue_command_apply(cmds, dry_run=args.dry_run); print the resulting message.
    }
    if (issue_command_apply() succeeded) then { exit 0. } else { exit 1. }

## COMMAND-LINE ARGUMENTS
- `record` — required positional path to a circle's `commands.toml` file (the file issue_dump()'s output produces).
- `--dry-run` — optional flag. When set, issue_command_apply() validates the batch against the temp copy and the real gate but does not write to the live `issues/` tree, reporting only whether it *would* apply cleanly.

## DEPENDENCIES
Standard library: `datetime`, `pathlib`, `re`, `shutil`, `subprocess`, `sys`, `tempfile`, `__future__`, and (inside `__main__` only) `tomllib`/`tomli` fallback for Python 3.10 and older. Sibling module: `issue_schema` (as `S`), for `S.ROOT`, `S.EDGE_TYPES` (the known relation-type vocabulary), `S.issue_read()`, and `S.issue_write()` — the shared TOML reader/writer for issue node files. External program: `python memory/issue_gate.py <dir>`, invoked as a subprocess by `issue_command_apply()` to validate a batch of proposed changes against the full graph-consistency gate before anything is promoted to the live tree.

## EXTERNAL FILES
Read:
- The record TOML file named on the command line (`__main__` block only), parsed with `tomllib`/`tomli`.
- `ROOT/issues/*.toml` node files, both the live tree and a temporary copy, via `S.issue_read()` inside `issue_command_apply_one()`.

Written:
- A temporary copy of the entire `issues/` directory (created by `shutil.copytree` into a `tempfile.TemporaryDirectory`, auto-cleaned on exit), mutated by `issue_command_apply_one()` for every command in the batch before the gate runs against it.
- The live `ROOT/issues/*.toml` node files — but only after the temp-copy validation passes and `dry_run` is False — via `issue_command_apply_one()` calling `S.issue_write()` on the real path for each command in the batch.

## NETWORK ACCESS
None.

## HUMAN I/O
Stdout, from the `__main__` block only: the circle/command-count summary, one `issue_describe()` line per command, and the final issue_command_apply() result message. No stdin. Exit code: 0 if `issue_command_apply()` succeeded (including "no commands" and dry-run success), 1 otherwise.

## OPERATION

### `_args(rest)`
    {
        Tokenize a command-line's remainder using ARG_RE, which matches either a `"quoted, with \" escapes"` group or a bare non-space word, unescaping `\"` to `"` inside quoted tokens. This is the shared tokenizer both parse branches use.
    }

### `issue_command_parse(line, circle)`
    if (the tokenized line is empty, or its first token is not "/issue") then {
        return (None, "not an /issue command").
    } else if (fewer than 2 tokens) then {
        return (None, usage string).
    } else {
        {
            take the second token as verb.
        }
        if (verb == "issue-label-update") then {
            if (fewer than 4 tokens) then { return (None, usage). }
            else if (the node token doesn't match `nNNNN`) then { return (None, "<token> is not an issue id (nNNNN)"). }
            else if (the new label is blank) then { return (None, "the new label is empty"). }
            else if (more than one extra token beyond the optional comment) then { return (None, "too many arguments"). }
            else { return a fully-populated command dict (verb, node, label, comment, circle, the original line), "". }
        } else if (verb == "issue-relationship-add") then {
            if (fewer than 5 tokens) then { return (None, usage). }
            else if (either the source or target node token doesn't match `nNNNN`) then { return (None, naming the bad one). }
            else if (the type is not in S.EDGE_TYPES) then { return (None, "<type> is not an issue-relationship type", listing the known types). }
            else if (source and target are the same node) then { return (None, "an issue-relationship cannot point at itself"). }
            else if (more than one extra token beyond the optional comment) then { return (None, "too many arguments"). }
            else { return a fully-populated command dict, "". }
        } else {
            return (None, "unknown /issue verb", listing the two known verbs).
        }
    }
This function is pure — it touches no file — and is deliberately strict: it refuses on anything it does not fully understand, called out in the docstring as avoiding the failure mode a prior `/mark` command had, where a malformed invocation silently misparsed an argument as a note instead of being rejected.

### `issue_precheck(cmd, graph)`
    {
        A partial, pre-close sanity check against the in-memory graph, meant to give Self immediate feedback (e.g. "no such issue <n>") rather than waiting for the authoritative gate run at close.
    }
    for each of "node"/"target" present in cmd: if (it names a node absent from the graph) then { return "no such issue <n>". }
    if (cmd is issue-relationship-add) then {
        for each of source/target node: if (its graph status is not "live") then { return that an edge is only legal when both ends are live. }
        for each existing edge on the source node: if (it already has this exact target+type and is not retired) then { return "<issue> already has this issue-relationship (<status>)". }
    }
    if (cmd is issue-label-update and the requested label already matches the current one) then {
        return "that is already the label".
    }
    return "" (no problem found at this stage).

### `issue_describe(cmd)`
    if (cmd is issue-label-update) then { return `<issue> label -> "<label>"`. }
    else if (cmd is issue-evidence-add) then { return `<issue> evidence <- <part>: "<quote, cut at 40>"`. }
    else if (cmd is issue-relationship-update) then { return `<issue> --<type>--> <target> status -> <value>`. }
    else { return `<issue> --<type>--> <target>`. }

### `issue_dump(cmds, circle)`
    {
        Render a list of parsed command dicts into a TOML text: a header (`circle`, `written` timestamp), then one `[[command]]` table per command carrying whichever of verb/node/label/type/target/comment/line are populated, each string-escaped by hand (backslashes doubled if present).
    }

### `_history(cmd, today)`
    {
        Build the one-line Markdown history entry appended to a node's description_history: for issue-label-update, "Label ruled by Self in `<circle>`: **<label>**"; for issue-relationship-add, "Relation `<type>` -> <target> added by Self in `<circle>`" — each optionally suffixed with the comment as an italic quote.
    }

### `issue_command_apply_one(cmd, issues, today)`
    {
        Locate the single node TOML file under `issues` whose filename ends with `<node>.toml`, and load it via S.issue_read().
    }
    if (cmd is issue-label-update) then {
        {
            record the old label as an alias if not already present (per ruling R007: old names are kept, not discarded), set the new label, and record which circle ruled it (label_ruled).
        }
    } else {
        {
            append a new edge dict: type, target, status "attested", today's date, a basis string that names the circle by regex-findable substring (required because the gate finds the circle in the basis text itself — this is not decoration), and a quote — the comment if given, else the entire command line, either of which is guaranteed verbatim because the coordinator itself wrote both.
        }
    }
    {
        append the rendered `_history()` line to the node's description_history and save the node file via S.issue_write().
    }

### `issue_command_apply(cmds, issues=None, dry_run=False)`
    if (cmds is empty) then {
        return (True, "no commands").
    } else {
        {
            copy the real `issues` directory (default S.ISSUES) into a fresh temp directory.
        }
        try {
            issue_command_apply_one() every command against the temp copy.
        } except any Exception {
            return (False, an error naming the command that actually
            raised and the exception — until 2026-08-19 it always named
            the FIRST command, sending the operator to debug the wrong
            ruling whenever a later one failed (review tier 2 #16).
        }
        {
            run `issue_gate.py <temp_copy_path>` as a subprocess.
        }
        if (the gate returned nonzero) then {
            return (False, a message stating nothing was written, with the gate's last ~12 output lines).
        } else if (dry_run) then {
            return (True, "N command(s) would apply cleanly") — the temp copy is discarded (TemporaryDirectory cleanup) and the live tree is never touched.
        } else {
            {
                re-run issue_command_apply_one() for every command against the real `issues` directory — the temp-copy run having already proven the batch is valid.
            }
            return (True, "N command(s) applied").
        }
    }

## BUGS
None found.

## Since 2026-09-03 — /issue-add's body lives here

`issue_add(label, desc, absence, *, guard, interactive)`, `_next_issue_id()`, `ISSUE_ADD_USAGE` and
`_run_captured(argv)` moved in from `coordinator/commands.py` (cohesion re-homing, stage 6). The verb
`commands.command_issue_add` parses the three quoted strings and delegates; the write is still
`issue_schema.issue_write`, so `issues/` keeps one writer. `_run_captured` runs this directory's scripts
(`issue_gate.py`, `issue_index.py`, `issue_status.py`, and this file) as subprocesses.
