# CIRCLE_OBSERVATION_LOG(1)

## NAME

circle_observation_manager.py — the CIRCLE_OBSERVATION register: what synthesis noticed about the CIRCLE as a working body, written to Self.

## SYNOPSIS

    python coordinator/circle_observation_manager.py            the listing
    python coordinator/circle_observation_manager.py --init     write the empty register
    python coordinator/circle_observation_manager.py --show     the newest entry, in full

    /observation-add <text>                room verb: a manual entry, source="self"
    /observation-list [<n>] [--all]        room verb: list (retired hidden by default) or show one
    /observation-continue <id> <text>      room verb: a NEW entry chained onto <id>
    /observation-retire <id>               room verb: soft delete — hides, never removes
    /observation-purge <id> <id>           room verb: true delete of the TEXT only, id typed twice

(As a library: `circle_observation_read()`, `circle_observation_latest_read()`, the pure `circle_observation_new_render(doc, circle, text, note, salience, continues)` used by the phase-2 driver, the pure `circle_observation_manual_render()`/`circle_observation_continue_render()`/`circle_observation_retire()`/`circle_observation_purge()`, `circle_observation_list()`/`circle_observation_show()`, and the impure load-mutate-save wrappers `circle_observation_manual_add()`/`circle_observation_continue_add()`/`circle_observation_retire_now()`/`circle_observation_purge_now()` the five room verbs call.)

## DESCRIPTION

After a circle closes, synthesis writes one note here about **the room** — its pace, what it avoided, where it moved easily. The addressing is precise and worth stating: it is addressed **to Self**, it is **about the circle**, and it is **never about Self**. An entry that turned into commentary on the person would be a different kind of document entirely.

The register was a Markdown file until R256 converted it. The conversion turned on a single question — is this a live append target, or a document something reads back and replaces whole? This one is appended to, one record per circle, so it became a register. `self/self.md` sitting beside it did not convert, because synthesis reads that back as prompt input and rewrites it entirely: that is a document's shape, not a register's.

**There is no cap, deliberately.** Its sibling register `circle_history` carries a TARGET/CAP pair because synthesis is *asked* for a bounded history and the register refuses a breach of that contract. Nothing upstream bounds an OBSERVATION, so a cap here would be a gate failing on legitimate output rather than a contract being enforced. The only thing refused is an empty one.

**The text is stored verbatim, and that matters.** `circle_history` collapses its prose to a single paragraph; this register must not, because an observation carries structure — "Patterns:", "Relationship dynamics:", "Opportunities:" — that flattening destroys. The one transformation applied is an outer strip, which exists so the stored record and its rendered form are the same bytes and the save round-trip guard does not refuse the write.

**Two fields arrived later than the rest.** R358 made synthesis follow the dreaming model: its observation is now shown the most recent record here and may CONTINUE it, with a self-assessed `salience`. Records written before that ruling carry neither field — absent, not empty, the same shape older records in a part's own remember register have.

**Accumulate, never prune — as a promise about the MACHINE.** At most one record per processed circle from SYNTHESIS's own phase-2 write. That promise is enforced by the register gate (`docs/REGISTER_GATE_DESIGN.md`) against phase-2's own delta only; it was never a claim that Self can never touch a record by hand. Writers of the automated kind are the phase-2 processor and the circle audit's synthetic-staging mode, which mints one real record to rehearse the later phases.

**Three fields, and five room verbs, added for the CRUD build (the operator, 2026-09-01).** `source` is `"synthesis"` on every new SYNTHESIS record from here on, `"self"` on one Self added directly; absent means written before the field existed. `retired`/`purged` are present only when true.

```
/observation-add <text>              circle_observation_manual_render() + save — Self's own
                                     entry, no circle required
/observation-list [<n>] [--all]      circle_observation_list()/circle_observation_show() — retired hidden
                                     by default, --all shows everything
/observation-continue <id> <text>    circle_observation_continue_render() + save — a NEW
                                     record chained onto <id>; <id>'s own
                                     record is never touched
/observation-retire <id>             circle_observation_retire() + save — soft delete: sets
                                     retired=true, stays in the file
/observation-purge <id> <id>         circle_observation_purge() + save — replaces TEXT with a
                                     redaction marker and sets purged=true;
                                     the id/date/circle/chain shell survives
                                     so nothing else's chain reference
                                     breaks. The id must be typed twice,
                                     matching, as the one confirmation step.
                                     Irreversible in the live file; the
                                     pre-purge text is still in git history
                                     at the commit before the purge.
```

**Why `/observation-purge` doesn't need a register-gate carve-out.** All
five verbs are command-pane, live-window writes — the same class
`/remember`, `/practice-add` and `/topic-close` already are. The phase-2
gate (`docs/REGISTER_GATE_DESIGN.md`) only ever compares a baseline taken
at `/close` time against SYNTHESIS's own staged delta; a command-pane write
completes and is committed before that baseline is ever read, so by the
time phase-2 runs, a retire or purge is simply part of the baseline — never
a delta the gate has to reason about. No change was made to
`register_gate.py`'s `REGISTERS` spec table or to the gate itself. This is why
a purge is the one place in this register that content can actually
disappear: the operator's own choice over a soft-delete-only design, because this
file is explicitly the one place in the project meant to hold material he
may need genuinely gone.

**Some old records have no circle.** Twenty-nine migrated entries are day-scoped rather than circle-scoped, because the retired nightly ran per night over whatever circles had accumulated. They carry midnight UTC of the day their own header line named — the only precision the Markdown file ever held. Every record written since has a circle, and the listing prints `(day-scoped)` where one is absent.

**Row construction now delegates to `JOURNAL_CLASS.py` (B105, 2026-09-05)**, for `circle_observation_new_render()`, `circle_observation_manual_render()` and `circle_observation_continue_render()` alike — the same shared "mint an id, stamp a date, optionally chain, optionally refuse oversize" core `circle_history_manager.py`, `circle_journal_manager.py` and (for one function) `remember_manager.py` also use. Everything that makes this register its own — no cap, verbatim multi-line text, which optional fields to include and under what condition, the explicit target-id existence check `circle_observation_continue_render()` runs before chaining, and `circle_observation_retire()`/`circle_observation_purge()`'s in-place mutation of an existing row (a different shape from "append new," and the only register with a use for it) — stays exactly where it was. No public name or behavior changed.

## MAIN

    Read the command-line arguments.
    if ("--init" appears) then {
        if (circles/circle_observation_log.toml already exists) then {
            print that it exists and was left untouched; return 0.
        } else {
            write the empty register and print the path; return 0.
        }
    }
    if ("--show" appears) then {
        if (there are no entries) then { print "(no entries)"; return 0. }
        else {
            print the newest entry's id, its circle (or "(day-scoped)"), and its
            date, then its whole text; return 0.
        }
    }
    otherwise {
        print how many entries there are.
        FOR EACH entry, oldest first: print its id, the date to the day, its
            circle or "(day-scoped)", its character count, and "[note]" if it
            carries an annotation.
        return 0.
    }

## COMMAND-LINE ARGUMENTS

    (none)      list every entry, one line each.
    --init      create circles/circle_observation_log.toml as an empty register.
                Refuses to overwrite an existing one, printing and exiting 0.
    --show      print the newest entry in full.

Matched by presence, not position; anything unrecognised falls through to the listing.

## DEPENDENCIES

`REGISTER_CLASS` for load, save and timestamps. `JOURNAL_CLASS` for the shared row-construction core (B105, used by the three render functions; `circle_observation_retire()`/`circle_observation_purge()` still deep-copy directly, since they mutate an existing row rather than append one). `pathlib`, `sys`, `copy`. The parent directory is added to the import path on import.

## EXTERNAL FILES

    circles/circle_observation_log.toml   READ by every verb; WRITTEN here only by
                                     --init. Per-circle records are written by
                                     the phase-2 driver via circle_observation_new_render(). The
                                     five room verbs (2026-09-01) write it too,
                                     directly, as live-window writes outside
                                     the phase-2 gate's scope — see above.

`PATH` is rebindable so probes can point at a temporary file. Because of that, printing goes through `_rel()`, which falls back to the absolute path rather than raising when `PATH` no longer sits under the project root — a module documented as rebindable must not assume otherwise.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout; reads no input. Standard output is reconfigured to UTF-8 with replacement on import.

## OPERATION

### _doc()
The register from disk, or a fresh in-memory one — name, `next_id` of 1, a generic preamble, no entries — when the file does not exist. The generic preamble must stay generic: the packaging scaffold's rule is that its delegate file is byte-equivalent to what this function produces for a fresh install, while the live register's own longer preamble (which carries the account of its own migration) persists because `_doc()` reads the file whenever one exists.

### circle_observation_read() / circle_observation_latest_read()
Every record in file order; and the record with the latest date, chosen by sorting rather than by list position so a hand-edited file cannot make the wrong one current.

### circle_observation_new_render(doc, circle, text, note=None, salience=None, continues=False)
    Strip the text at both ends.
    if (nothing is left) then { raise ValueError — an empty observation is
        nothing to record. }
    Work on a deep COPY; this function writes nothing.
    Mint "SO-" plus next_id, zero-padded to four digits; stamp the UTC time,
        the circle, and the verbatim text.
    if (a salience was given) then { record it. }
    if (continues was asked for and the register is not empty) then {
        chain the new record to the previous one's id. Every record here has
        an id, so unlike a part's remember chain there is no id-less record
        to step over.
    }
    if (a note was given) then { record it. }
    Append, advance next_id, return (the new register, the new record).

## BUGS

None found. `--init` exiting 0 on an existing register is intentional idempotence, not a swallowed error.
