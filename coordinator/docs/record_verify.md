# RECORD_VERIFY(1)

## NAME

record_verify.py — the corruption gate: one sweep over every file this system keeps state in, run before a circle is allowed to open.

## SYNOPSIS

    python memory/record_verify.py

(As a library: `record_sweep(root)` returns findings and a file count; `record_report_lines_render(findings)` formats them. `coordinator/circle.py` calls `record_sweep()` directly at open, and `coordinator/circle_audit.py` runs it as phase 0.)

## DESCRIPTION

This looks for the damage classes that are invisible to a reader and fatal to a run:

    NUL bytes       the file is binary or truncated; it will not load cleanly
    invalid UTF-8   the same defect, one layer up
    invalid JSON    a manifest that no longer parses
    invalid TOML    a register, a part.toml or an issue node that no longer parses

plus a truncation guard on the two rulebooks: each must still carry its own section anchors, because a rulebook cut short still looks like a rulebook.

**It is a gate, not a report.** NUL-byte damage once silenced a part. The file still had a name, a plausible size and a plausible first line; the part simply went dark, and nothing downstream could tell corruption from content. That is the whole problem — every reader below this point takes the bytes as the truth, so the only place it can be caught is before a circle is built on them.

What a corrupted file costs depends on where it sits:

EVERY PATH BELOW IS RECORD-RELATIVE, AND THE RECORD IS PER GROUP. `record_verify.py:357` builds
its bases as `group_tree(g) / subdir` for every `g` in `group_present_read()`, so `parts/` here
means `groups/<name>/parts/` for each group installed — `groups/ifs/parts/` and
`groups/band/parts/` today. None of these four directories exists at the tree root; they moved
under `groups/<name>/` at R467/B117 and this table kept the old spelling until 2026-09-08
(audit-register.md #16).

    parts/<name>/long_term.md    BLOCK 3 of that part's prompt. mid_term.md is
    parts/<name>/mid_term.md     DERIVED from the record, so damage propagates into
                                 the distillate and into the prompt: the part runs
                                 with a mangled identity, or the API call fails.
    parts/<name>/part.toml       THE ROSTER. Its presence is what makes a directory
                                 a part, so corrupting it means the part does not
                                 exist for this circle — a part silently missing,
                                 not an error.
    issues/issue_model.md        the briefing's ONE hard file dependency.
    issues/*.toml                the graph behind it. Both feed BLOCK 2, which is
    self/best_practices.toml     byte-identical for all parts and CACHED — so one
                                 corrupt file poisons every prompt at once, and the
                                 cached prefix holds it for the whole circle.
    work/manifests/*.json        dead records from the retired batch nightly. Still
                                 swept: corruption under work/ should never hide.
    circles/*.md                 the single canonical record. A part that spoke can
                                 be read as silent, which dreaming then reads as
                                 no engagement.

**Corruption here does not decay — it sets.** Git normalises nothing on the way through, and every sha256 in a close report is computed over whatever bytes were present. Once a corrupt file has been hashed into a close report, the reconcile check confirms it matches its record and reports no drift: the damage has become the record.

**There is deliberately no override flag.** "Open anyway" on a corruption finding is the act this gate exists to prevent, and the remedy is a `git checkout` away.

**Two exit codes, from two callers.** Run bare, this script exits 1 on any finding and 0 when clean. When `circle.py` calls `record_sweep()` at open and finds something, *it* exits 2 and the circle is never opened — no transcript, no working-set entry, no API call.

## MAIN

    Run record_sweep() over the project root.
    print how many state files were scanned, plus the two rulebooks.
    if (there are findings) then {
        FOR EACH finding: print FAIL, the path, the defect, and the remedy.
        print "INTEGRITY FAIL — <n> corrupted file(s). Do NOT open a circle
            until resolved."
        return 1.
    } else {
        print that there are no NUL bytes, the UTF-8 is valid, and every JSON
            and TOML parses.
        print "INTEGRITY PASS."
        return 0.
    }

## COMMAND-LINE ARGUMENTS

None, by design. There is no `--force` and no `--fix`.

## DEPENDENCIES

`json` and `tomllib` (falling back to `tomli` on Python 3.10 and older) from the standard library, plus `pathlib`, `sys` and `typing`. `gitrepo` is imported lazily inside the lab-tag check only.

## EXTERNAL FILES

Read-only throughout; this module writes nothing, ever.

    parts/*/*.md, parts/*/*.toml     every part's record and its roster entry
    self/*.md, self/*.toml           every Self-owned document and register
    issues/*.md, issues/*.toml       the issue graph and its prologue
    work/manifests/*.json            the retired nightly's manifests
    circles/*.md                     every transcript
    coordinator/process.md           read deeper — anchors as well as bytes
    coordinator/process_core.md      the same

A directory that is absent is skipped rather than reported, so the sweep still runs against a partial or archived tree.

## NETWORK ACCESS

None. It shells out to `git` for the lab-tag tripwire and nothing else.

## HUMAN I/O

Prints to stdout; reads no input. Standard output is reconfigured to UTF-8 with replacement on import, because Windows consoles default to cp1252 and would raise on the characters this project prints — a probe that dies formatting its own PASS message reports a failure that is not there.

## OPERATION

### _check_bytes(rel, raw)
    if (the bytes contain any NUL) then {
        return a finding naming how many, saying the file is corrupted or
        binary and will not load cleanly.
    }
    try to decode as UTF-8.
    if (that fails) then {
        return a finding naming the decode error, with a remedy that also says
        to check the editor that last wrote it.
    }
    otherwise return the decoded text.

### _check_one(p, root)
    try to read the file's bytes.
    if (that raises) then { return a finding about permissions or a held handle. }
    Run the NUL and UTF-8 checks; if either fails, return that finding.
    if (the suffix is .json) then { parse it; a failure is a finding naming the
        position. }
    else if (the suffix is .toml) then { the same, for TOML. }
    return nothing — the file is clean.

### record_process_verify(root) (`check_process()` before the B99 re-homing, 2026-09-03)
    FOR EACH of the two rulebooks, with its own anchor list:
        if (the file is missing) then { record a finding and move on. }
        Run the byte and parse checks; if one fails, record it and move on.
        FOR EACH anchor: if (it is not in the text) then {
            record "has lost its '<anchor>' section — the file was cut short".
        }

The anchors are a truncation guard, not a style rule. They carry a correction from 2026-08-07: a rulebook renamed one of its sections, the stale anchor made the guard fail on a correct file, and it told the reader not to open a circle. A truncation guard that fires on a rename is worse than none, because the one thing it must mean is "this file was cut short".

### record_lab_tags_read(tags, is_ancestor) (`lab_tags_reaching_master()` before the B99 re-homing, 2026-09-03)
Pure, so the decision can be probed with fabricated inputs: returns the tags for which `is_ancestor` answers yes.

### record_lab_merge_verify(root) (`check_lab_never_merged_back()` before the B99 re-homing, 2026-09-03)
    Ask git for every tag matching */lab/*.
    if (git errors, or there are none) then { return no findings. }
    FOR EACH tag: ask whether it is an ancestor of master.
    Return a finding for each one that is.

The ruling this protects is that nothing in a lab is ever merged back — travel is main to lab only. The obvious check, asking whether the `lab` branch is merged into master, is wrong here and would fire on a clean tree: the lab branch sits at a commit that came from an already-merged worktree branch, so it is an ancestor of master while having contributed nothing, and a checker that cries wolf gets switched off. The violation is also invisible in the graph after the fact — once lab work lands on master those commits are simply master's. So the check needs a marker for "made in the lab", and the only one there is is the tag stamp a lab tree puts on its own refs.

Its limit is stated rather than papered over: this catches lab work that carried a tag — a closed circle, which is the record, and the record is what the ruling protects. An untagged lab code commit merged to master is invisible to it.

It **fails open** on any git error, matching the rest of this file: this is the gate that runs before a circle opens, and a missing git must not be the thing that stops one.

### record_sweep(root)
    FOR EACH (subdirectory, pattern) in the state globs:
        if (the directory does not exist) then { skip it. }
        FOR EACH matching file, in sorted order: count it and check it.
    Add the rulebook checks and the lab-tag tripwire.
    Return (findings, files scanned).

### record_report_lines_render(findings)
One stanza per corrupted file — path, defect, remedy — for a caller that wants to print the block itself.

## BUGS

None found. One thing that reads as an inconsistency and is not: the module docstring says a failure "returns 2 and the circle is never opened", which describes `circle.py`'s exit code at open, not this script's. Run bare, this script exits 1.

## HISTORY

Extracted 2026-08-18 from a preflight script of the retired agent-teams era, which had exactly one caller — itself unscheduled — and so never actually ran before a circle. Its agent-definition and team-directory checks died with that runtime and were not carried over. Coverage widened in the same move: the old sweep covered no `.toml` at all and nothing under `issues/`, which left the roster, the whole issue graph and every Self register outside the only sweep of its kind.
