# SELF_OBSERVATION_LOG(1)

## NAME

self_observation_log.py — the SELF_OBSERVATION register: what synthesis noticed about the CIRCLE as a working body, written to Self.

## SYNOPSIS

    python coordinator/self_observation_log.py            the listing
    python coordinator/self_observation_log.py --init     write the empty register
    python coordinator/self_observation_log.py --show     the newest entry, in full

(As a library: `entries()`, `most_recent()`, and the pure `render_new(doc, circle, text, note, salience, continues)` used by the phase-2 driver.)

## DESCRIPTION

After a circle closes, synthesis writes one note here about **the room** — its pace, what it avoided, where it moved easily. The addressing is precise and worth stating: it is addressed **to Self**, it is **about the circle**, and it is **never about Self**. An entry that turned into commentary on the person would be a different kind of document entirely.

The register was a Markdown file until R256 converted it. The conversion turned on a single question — is this a live append target, or a document something reads back and replaces whole? This one is appended to, one record per circle, so it became a register. `self/self.md` sitting beside it did not convert, because synthesis reads that back as prompt input and rewrites it entirely: that is a document's shape, not a register's.

**There is no cap, deliberately.** Its sibling register `circle_history` carries a TARGET/CAP pair because synthesis is *asked* for a bounded history and the register refuses a breach of that contract. Nothing upstream bounds an OBSERVATION, so a cap here would be a gate failing on legitimate output rather than a contract being enforced. The only thing refused is an empty one.

**The text is stored verbatim, and that matters.** `circle_history` collapses its prose to a single paragraph; this register must not, because an observation carries structure — "Patterns:", "Relationship dynamics:", "Opportunities:" — that flattening destroys. The one transformation applied is an outer strip, which exists so the stored record and its rendered form are the same bytes and the save round-trip guard does not refuse the write.

**Two fields arrived later than the rest.** R358 made synthesis follow the dreaming model: its observation is now shown the most recent record here and may CONTINUE it, with a self-assessed `salience`. Records written before that ruling carry neither field — absent, not empty, the same shape older records in a part's own remember register have.

**Accumulate, never prune.** At most one record per processed circle. Writers are the phase-2 processor and the circle audit's synthetic-staging mode, which mints one real record to rehearse the later phases.

**Some old records have no circle.** Twenty-nine migrated entries are day-scoped rather than circle-scoped, because the retired nightly ran per night over whatever circles had accumulated. They carry midnight UTC of the day their own header line named — the only precision the Markdown file ever held. Every record written since has a circle, and the listing prints `(day-scoped)` where one is absent.

## MAIN

    Read the command-line arguments.
    if ("--init" appears) then {
        if (self/self_observation_log.toml already exists) then {
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
    --init      create self/self_observation_log.toml as an empty register.
                Refuses to overwrite an existing one, printing and exiting 0.
    --show      print the newest entry in full.

Matched by presence, not position; anything unrecognised falls through to the listing.

## DEPENDENCIES

`self_schema` for load, save and timestamps. `pathlib`, `sys`, `copy`. The parent directory is added to the import path on import.

## EXTERNAL FILES

    self/self_observation_log.toml   READ by every verb; WRITTEN here only by
                                     --init. Per-circle records are written by
                                     the phase-2 driver via render_new().

`PATH` is rebindable so probes can point at a temporary file. Because of that, printing goes through `_rel()`, which falls back to the absolute path rather than raising when `PATH` no longer sits under the project root — a module documented as rebindable must not assume otherwise.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout; reads no input. Standard output is reconfigured to UTF-8 with replacement on import.

## OPERATION

### _doc()
The register from disk, or a fresh in-memory one — name, `next_id` of 1, a generic preamble, no entries — when the file does not exist. The generic preamble must stay generic: the packaging scaffold's rule is that its delegate file is byte-equivalent to what this function produces for a fresh install, while the live register's own longer preamble (which carries the account of its own migration) persists because `_doc()` reads the file whenever one exists.

### entries() / most_recent()
Every record in file order; and the record with the latest date, chosen by sorting rather than by list position so a hand-edited file cannot make the wrong one current.

### render_new(doc, circle, text, note=None, salience=None, continues=False)
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
