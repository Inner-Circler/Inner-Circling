# CIRCLE_HISTORY(1)

## NAME

circle_history_manager.py — the CIRCLE_HISTORY register: SYNTHESIS's one durable record per circle, saying what the circle was and what moved.

## SYNOPSIS

    python coordinator/circle_history_manager.py            the listing
    python coordinator/circle_history_manager.py --init     write the empty register
    python coordinator/circle_history_manager.py --show     the newest entry, in full

(As a library: `circle_history_read()` for every record, `circle_history_latest_read()` for the newest, and `circle_history_new_render(doc, circle, text)` — a pure function the phase-2 driver uses to build one entry without writing anything.)

## DESCRIPTION

Every other register in this project holds something small and repeated — a part's note to itself, a topic, a proposal. This one holds the account of a whole circle, written once, after the circle is over. It is what a later circle's synthesis reads to know what the last one was, so the record is not a summary kept for a human's convenience: it is an input.

The register began as a single append-only bullet in `self/narrative_arc.md` and was promoted to a structured record by R165. R186 then added the PRIOR entry to SYNTHESIS's own inputs, which is what lets each entry genuinely continue the last rather than restate it — the `chain` field records the predecessor's id, so the entries form a linked list by construction, but the *continuity* comes from synthesis having actually read the previous entry, not from the field.

**Two size numbers, doing different jobs.** `TARGET` (7,200 characters) is what the prompt asks synthesis for. `CAP` (8,000) is what this register refuses at. Collapsing them is what made the first breach expensive: a model asked for exactly the hard limit has no room to run slightly long without being refused, so the 800-character gap absorbs ordinary overshoot. A TARGET breach is survivable and earns one insistent re-ask; a CAP breach is not. The cap itself was raised from 600 to 8,000 by R191 after the first real rehearsal refused a 43-statement circle's history at 795 characters — 600 had been set by analogy to the cap on a part's private note to itself, which is a much smaller kind of thing. The analogy was to the wrong neighbour.

**An oversize entry is REFUSED, never truncated.** A history entry cut off mid-sentence is a worse record than the previous entry standing alone, so `circle_history_new_render()` raises rather than trims, the caller reports it, and the prior entry stays current.

**Accumulate, never prune.** At most one record per processed circle, and nothing here ever deletes one. The register gate enforces exactly that.

**The writer is the phase-2 driver only.** Nothing else in the system writes this file. Raising the cap was safe for the same reason: no prompt block projects this register, and both its consumers are SYNTHESIS's own — the next run's input, which reads the single most recent entry, and this run's CIRCLE JOURNAL fold, which reads the fresh HISTORY text produced beside it in the same reply — so the cost of a bigger cap is bounded at one record per run.

**Row construction now delegates to `JOURNAL_CLASS.py` (B105, 2026-09-05).** `circle_history_manager.py`, `circle_observation_manager.py`, `circle_journal_manager.py` and (for one function) `remember_manager.py` shared this same "mint an id, stamp a date, optionally chain to the prior row, optionally refuse oversize text" shape by duplication; a module-level `JournalClass` instance now owns it, and this module keeps only what makes CIRCLE_HISTORY its own — the CAP/TARGET numbers, and whitespace-collapsing the text to one paragraph before handing it over. No public name or behavior changed.

## MAIN

    Read the command-line arguments.
    if ("--init" appears) then {
        if (circles/circle_history.toml already exists) then {
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
            then its whole text.
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
    --init      create circles/circle_history.toml as an empty register. Refuses
                to overwrite an existing one — it prints and exits 0. Default: off.
    --show      print the newest entry in full, text included. Default: off.

Arguments are matched by presence, not position. Anything unrecognised falls through to the listing.

## DEPENDENCIES

`REGISTER_CLASS` for loading, saving and timestamping the register. `JOURNAL_CLASS` for the shared row-construction core (B105). `pathlib` and `sys` from the standard library. The parent directory and `memory/` are put on the import path at import time, matching every other coordinator module's bootstrap.

## EXTERNAL FILES

    circles/circle_history.toml    READ by every verb; WRITTEN only by --init here.
                                The real per-circle writes come from the phase-2
                                driver calling circle_history_new_render() and saving the result.

The module-level `PATH` is deliberately rebindable so a probe can point at a temporary file — test suites never write the live register.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout only; reads no input. Standard output is reconfigured to UTF-8 with replacement on import, so a record containing characters the console cannot render prints a replacement rather than raising.

## OPERATION

### _JC
A module-level `JournalClass` instance (`JOURNAL_CLASS.py`, B105), configured with this register's own table name, `"CH-"` id prefix, CAP and its label, register name, preamble, and a `path_fn` lambda that re-reads the module's own `PATH` global on every call — so a probe suite's rebind of `PATH` still reaches the register `_JC` reads and writes. `_doc()`, `circle_history_read()`, `circle_history_latest_read()` and `circle_history_new_render()` below are now thin wrappers over its `doc()`, `read()`, `latest()` and `new_render()` methods.

### _doc()
Delegates to `_JC.doc()`: loads the register if the file exists; otherwise returns a fresh in-memory register — name, `next_id` of 1, the preamble, and an empty entry list. So every read path works before the file has ever been created.

### _rel()
`PATH` rendered for printing, tolerant of `PATH` having been rebound outside the tree (the probe suite's own technique) — `PATH.relative_to(ROOT)` would otherwise raise. Added with B105: this module was the one register-with-a-CLI still missing the fix `circle_observation_manager.py` and `circle_journal_manager.py` already carried, found when B105's own new direct test rebound `PATH` the same way and hit exactly that raise.

### circle_history_read()
Delegates to `_JC.read()`: the record list, in file order.

### circle_history_latest_read()
Delegates to `_JC.latest()`: the entry with the latest `date`, or nothing if the register is empty. Sorted by date rather than taken from the end of the list, so a hand-edited file cannot make the wrong record current.

### circle_history_new_render(doc, circle, text)
    Collapse all runs of whitespace in the text to single spaces.
    Hand the register and a {circle, text} dict to _JC.new_render(),
    asking it to auto-chain to the most recent id-bearing row.
        _JC.new_render, in turn:
        if (the text is longer than CAP) then {
            raise ValueError naming the actual length, the cap, and CIRCLE_HISTORY's
            own label, saying it was refused rather than truncated.
        }
        Work on a deep COPY of the register — nothing here writes.
        Mint the id "CH-" plus the register's next_id, zero-padded to four digits.
        Record the current UTC time, then this row's own fields (circle, text).
        if (a chain was requested and the register has a prior row bearing an id,
            scanning backwards from the end of the file) then {
            set this row's chain to that id.
        }
        Append it, advance next_id, and return (the new register, the new row).

Pure by design: the caller decides whether to save, which is what lets the driver stage a whole circle's registers and commit them together or not at all.

## BUGS

None found. Two behaviours that look like defects and are not: `--init` on an existing register prints and exits 0 rather than failing, because it is meant to be safe to run repeatedly; and an unrecognised argument silently lists rather than erroring, which is the same convention the other register viewers use.
