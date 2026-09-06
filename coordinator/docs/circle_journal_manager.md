# CIRCLE_JOURNAL(1)

## NAME

circle_journal_manager.py — the CIRCLE_JOURNAL register: the circle's own evolving identity, folded fresh every close and read into every part's Block 1.

## SYNOPSIS

    python coordinator/circle_journal_manager.py            the listing
    python coordinator/circle_journal_manager.py --init     write the empty register
    python coordinator/circle_journal_manager.py --show     the newest entry, in full

(As a library: `circle_journal_read()` for every record, `circle_journal_latest_read()` for the newest, and `circle_journal_new_render(doc, circle, text, provenance=None)` — a pure function the phase-2 driver uses to build one entry without writing anything.)

## DESCRIPTION

`self/circle_history.toml` already writes one durable entry per circle, and each part's own `remember.toml` already collects fresh, salience-tagged material every close — but until B94 (2026-09-04) neither reached a prompt block, and nothing joined them. This register is that join: SYNTHESIS folds the prior CIRCLE_JOURNAL entry (if one exists) with this circle's own fresh HISTORY text and the high-salience remember rows parts surfaced, into one continuing account of what the circle now *is* — not a summary of turns, a part's-eye view of the whole. The same incremental-revision shape `part_mid_term_manager.py` already uses one level down, at the part rather than the circle: fold in what changed, keep what still holds, never replay every past entry from scratch.

Named CIRCLE_JOURNAL by the operator's own ruling (D90/R454, 2026-09-04) — reusing docs/BNF.md's own JOURNAL shape word rather than colliding with `<circle_identity>`, which already names Block 1 as a whole. The operator also ruled the build order (D92/R455): this register shipped bespoke first, ahead of the shared LEDGER/JOURNAL core (`PROMPT_LEDGER`/`PROMPT_JOURNAL`). **B105 (2026-09-05) then built that core and folded this register into it** — `circle_journal_new_render()` now delegates row construction to a module-level `JournalClass` instance (`JOURNAL_CLASS.py`), sharing it with `circle_history_manager.py`, `self_observation_manager.py` and (for one function) `remember_manager.py`. This module keeps only what makes CIRCLE_JOURNAL its own — CAP/TARGET, text normalization, and whether `provenance` is included.

**Two size numbers, doing different jobs — this register's OWN, not `circle_history_manager.py`'s imported.** `TARGET` and `CAP` follow the same asked-for-vs-refused-at pattern as `circle_history_manager.py`'s pair, but sized differently: this register reaches Block 1, paid on every part's prompt every circle, while `circle_history.toml` reaches no prompt block at all — and a folded, deduplicated distillate should run smaller than a raw HISTORY entry by construction, not merely be capped the same. Both defaults (4,000 / 3,600 characters) are setting-overridable and were chosen before more than two circles existed to measure against; the standalone trial that informed them is `work/ablations/2026-09-04/`.

**Provenance, without an id that does not exist yet.** Each entry's `provenance` field names, per retained point, whether it came from this circle's own HISTORY, a specific part's fresh remember material, or was carried forward unchanged from the predecessor. It would be natural to cite `MEM-nnnn` or `CH-nnnn` directly, but SYNTHESIS mints this circle's CIRCLE_JOURNAL entry in the *same reply* that produces its own fresh HISTORY and reads each part's fresh remember material — and the coordinator only mints those ids *after* parsing that reply (R170). So a bare `<part_dir>` (a fresh row this circle, from that part — `per_run_max: 1` on `parts/*/remember.toml` makes the directory name alone unambiguous) or the bare word `history` (this circle's own fresh entry — the row's own `circle` field says which) stand in where an id cannot yet be cited. Only `carried:CJ-nnnn` names an id, because the predecessor's id already exists when SYNTHESIS runs.

**An oversize entry is REFUSED, never truncated** — the same reasoning `circle_history_manager.py` gives for its own pair: an entry cut mid-sentence is a worse record than the prior one standing alone. In practice `circle_synthesis.py` catches an over-cap reply before it ever reaches this function: one insistent re-ask (R192, extended to cover this section alongside HISTORY), then a whitespace-aware truncation if the re-ask still runs long — so `circle_journal_new_render()`'s own refusal is a backstop, not the normal path.

**Accumulate, never prune.** At most one record per processed circle, and nothing here ever deletes one. The register gate enforces exactly that, the same as every other journal-shaped register.

**The writer is the phase-2 driver.** `circle_synthesis.py`'s SYNTHESIS pass mints the entry (B94 stage 4); `inter_circle.py` stages it into `self/circle_journal.toml` right beside `circle_history.toml`'s own staging (B94 stage 4); `group_context.py` — Block 1's sole assembler — reads the newest entry into every part's prompt under a `## Circle identity` heading (B94 stage 5). The newest entry only, never "the last few": its own fold is already incremental revision, so reading more would repeat material the newest entry already carries forward.

## MAIN

    Read the command-line arguments.
    if ("--init" appears) then {
        if (self/circle_journal.toml already exists) then {
            print that it exists and was left untouched.
            return 0.
        } else {
            write the empty register — the preamble, next_id = 1, no entries.
            print the path written.
            return 0.
        }
    }
    if ("--show" appears) then {
        if (there are no entries) then { print "(no entries)"; return 0. }
        else {
            print the newest entry's id, the circle it is about, and its date,
            then its whole text, then its provenance lines if any.
            return 0.
        }
    }
    otherwise {
        print how many entries there are.
        FOR EACH entry, oldest first: print its id, the circle it is about, and
            its chain target if it has one.
        return 0.
    }

## COMMAND-LINE ARGUMENTS

    (none)      list every entry: id, the circle it is about, and its chain link.
    --init      create self/circle_journal.toml as an empty register. Refuses
                to overwrite an existing one — it prints and exits 0.
    --show      print the newest entry in full, text and provenance included.

Arguments are matched by presence, not position. Anything unrecognised falls through to the listing.

## DEPENDENCIES

`REGISTER_CLASS` for loading, saving and timestamping the register. `JOURNAL_CLASS` for the shared row-construction core (B105). `setting_manager` for `CAP`/`TARGET`'s overridable defaults. `pathlib` and `sys` from the standard library.

## EXTERNAL FILES

    self/circle_journal.toml    READ by every verb; WRITTEN only by --init here.
                                The real per-circle writes come from the phase-2
                                driver calling circle_journal_new_render() and saving the result.

The module-level `PATH` is deliberately rebindable so a probe can point at a temporary file — test suites never write the live register.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout only; reads no input. Standard output is reconfigured to UTF-8 with replacement on import, so a record containing characters the console cannot render prints a replacement rather than raising.

## OPERATION

### _JC
A module-level `JournalClass` instance (`JOURNAL_CLASS.py`, B105), configured with this register's own table name, `"CJ-"` id prefix, CAP and its label, register name, preamble, and a `path_fn` lambda that re-reads the module's own `PATH` global on every call. `_doc()`, `circle_journal_read()`, `circle_journal_latest_read()` and `circle_journal_new_render()` below are now thin wrappers over its `doc()`, `read()`, `latest()` and `new_render()` methods.

### _doc()
Delegates to `_JC.doc()`: loads the register if the file exists; otherwise returns a fresh in-memory register — name, `next_id` of 1, the preamble, and an empty entry list. So every read path works before the file has ever been created — the same state a fresh install ships in, deliberately.

### _rel()
`PATH` rendered for printing, tolerant of `PATH` having been rebound outside the tree (the probe suite's own technique) — `PATH.relative_to(ROOT)` would otherwise raise.

### circle_journal_read()
Delegates to `_JC.read()`: the record list, in file order.

### circle_journal_latest_read()
Delegates to `_JC.latest()`: the entry with the latest `date`, or nothing if the register is empty. Sorted by date rather than taken from the end of the list, so a hand-edited file cannot make the wrong record current. This is what `group_context.py` calls at every prompt assembly, and what `circle_synthesis.py` calls to hand SYNTHESIS its own predecessor entry.

### circle_journal_new_render(doc, circle, text, provenance=None)
    Collapse all runs of whitespace in the text to single spaces.
    Build a {circle, text[, provenance]} dict — provenance included only
        when given, as a plain list of strings.
    Hand it to _JC.new_render(), asking it to auto-chain to the most
        recent id-bearing row.
        _JC.new_render, in turn:
        if (the text is longer than CAP) then {
            raise ValueError naming the actual length, the cap, and
            CIRCLE_JOURNAL's own label, saying it was refused rather than
            truncated.
        }
        Work on a deep COPY of the register — nothing here writes.
        Mint the id "CJ-" plus the register's next_id, zero-padded to four
            digits. Record the current UTC time, then this row's own fields.
        if (a chain was requested and the register has a prior row bearing
            an id, scanning backwards from the end of the file) then {
            set this row's chain to that id.
        }
        Append it, advance next_id, and return (the new register, the new row).

Pure by design: the caller decides whether to save, which is what lets the driver stage a whole circle's registers and commit them together or not at all.

## BUGS

None found. Two behaviours that look like defects and are not: `--init` on an existing register prints and exits 0 rather than failing, because it is meant to be safe to run repeatedly; and an unrecognised argument silently lists rather than erroring, which is the same convention the other register viewers use.

`provenance` is a flat list of compact strings, not the nested per-point structure `issues/*.toml`'s own `[[evidence]]` rows carry — `REGISTER_CLASS.register_dumps()` only renders a row's fields as scalars or lists-of-scalars, so a genuine nested table would need infrastructure this register doesn't have. **B105 (2026-09-05) built the shared record-chain core and did NOT add this** — `JOURNAL_CLASS.py` shares row construction (id/date/chain/cap), never a row's own schema richness, so this stays exactly the flat shape it was. Not a bug: the compact form was chosen deliberately over building that infrastructure early, see the module's own docstring.
