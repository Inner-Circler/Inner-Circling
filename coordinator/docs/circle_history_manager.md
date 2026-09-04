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

**The writer is the phase-2 driver only.** Nothing else in the system writes this file. Raising the cap was safe for the same reason: no prompt block projects this register, and its one consumer reads the single most recent entry, so the cost of a bigger cap is bounded at one record per run.

## MAIN

    Read the command-line arguments.
    if ("--init" appears) then {
        if (self/circle_history.toml already exists) then {
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
    --init      create self/circle_history.toml as an empty register. Refuses
                to overwrite an existing one — it prints and exits 0.
    --show      print the newest entry in full, text included.

Arguments are matched by presence, not position. Anything unrecognised falls through to the listing.

## DEPENDENCIES

`REGISTER_CLASS` for loading, saving and timestamping the register. `pathlib`, `sys` and `copy` from the standard library. The parent directory and `memory/` are put on the import path at import time, matching every other coordinator module's bootstrap.

## EXTERNAL FILES

    self/circle_history.toml    READ by every verb; WRITTEN only by --init here.
                                The real per-circle writes come from the phase-2
                                driver calling circle_history_new_render() and saving the result.

The module-level `PATH` is deliberately rebindable so a probe can point at a temporary file — test suites never write the live register.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout only; reads no input. Standard output is reconfigured to UTF-8 with replacement on import, so a record containing characters the console cannot render prints a replacement rather than raising.

## OPERATION

### _doc()
Loads the register if the file exists; otherwise returns a fresh in-memory register — name, `next_id` of 1, the preamble, and an empty entry list. So every read path works before the file has ever been created.

### circle_history_read()
The record list, in file order.

### circle_history_latest_read()
The entry with the latest `date`, or nothing if the register is empty. Sorted by date rather than taken from the end of the list, so a hand-edited file cannot make the wrong record current.

### circle_history_new_render(doc, circle, text)
    Collapse all runs of whitespace in the text to single spaces.
    if (the text is longer than CAP) then {
        raise ValueError naming the actual length and the cap, and saying it
        was refused rather than truncated.
    }
    Work on a deep COPY of the register — this function writes nothing.
    Mint the id "CH-" plus the register's next_id, zero-padded to four digits.
    Record the current UTC time, the circle this entry is about, and the text.
    if (the register already has a last entry with an id) then {
        set this entry's chain to that id.
    }
    Append it, advance next_id, and return (the new register, the new entry).

Pure by design: the caller decides whether to save, which is what lets the driver stage a whole circle's registers and commit them together or not at all.

## BUGS

None found. Two behaviours that look like defects and are not: `--init` on an existing register prints and exits 0 rather than failing, because it is meant to be safe to run repeatedly; and an unrecognised argument silently lists rather than erroring, which is the same convention the other register viewers use.
