# ISSUE_GATE.PY(1)

## NAME
issue_gate.py — the invariant gate for the issue graph: verifies claims about the world (verbatim quotes, attribution, edge legality) that no file format can check for you. Read-only.

## SYNOPSIS
    python memory/issue_gate.py
    python memory/issue_gate.py <dir>

## DESCRIPTION
Where `issue_schema.py` checks that a node document is shaped the way the schema says it should be, `issue_gate.py` checks that the *claims* the graph makes are actually true, by cross-referencing every node against the transcripts it cites. The module's docstring frames this as "everything that was never about syntax," and lists eight invariants it enforces: VERBATIM (every evidence quote appears exactly, byte-for-byte, in the transcript it cites — the docstring cites catching an em-dash silently swapped for a colon), ATTRIBUTION (a quote was actually said by the part it is filed under, catching a case where Self's own words sat filed under a part's name for a month), SPAN (a quote must not run past a speaker-marker boundary into someone else's statement), CLOSURE (a live edge is legal only when both ends are live, or the far end is a root), ATTESTATION (an attested edge must carry a real quote from a real circle; a proposed one must name who is being asked to confirm it), DIRECTION (a `leads-to`/`narrower-than` edge whose own basis text describes the target as the *derived* thing is pointing backwards), EVIDENCE (a live node must cite something — Self is quoted directly ruling out "possible issues" recorded without evidence), and AGREEMENT (`held_by` and the set of parts actually giving evidence must name the same parties).

Since the TOML migration (2026-08-03), roughly half of what this file used to check — declared-vs-parsed counts, backslash-escaped Markdown artifacts, malformed edge-type regexes, section ordering — is now enforced structurally by the TOML format itself and by `issue_schema.check()`, so this file's remaining job is entirely the semantic, cross-file verification a schema cannot express. The script never writes anything; running it against an arbitrary directory (rather than the live `issues/`) is explicitly supported as a preview mode that does not touch that directory.

The root exception (ruled 2026-08-05, B23) treats a `root`-status node as a legal edge target even though roots are not themselves "live" — a root is explicitly the source the live graph descends from and carries no claim of its own, so forbidding edges to it would make the graph unable to say where it came from.

## MAIN
    for each *nNNNN.toml file under ISSUES, sorted {
        read its raw bytes;
        if (it contains CRLF line endings) then {
            record a failure — the rest of the graph is LF and
            .gitattributes disables line-ending conversion because it
            would break every recorded sha256
        }
        try to load it as TOML via issue_schema;
        if (loading raises) then { record "will not parse" with the error
            and skip further checks on this file }
    }
    compute the set of all ids, the set of live ids, and the set of root
    ids; a legal edge target is (live ids UNION root ids);
    print a one-line summary of node/live counts;

    for each successfully-loaded document {
        run issue_schema.check() and fold in its shape failures;

        for its "opened" and "label_ruled" references, if present {
            if (the transcript file they name does not exist) then {
                record a failure
            }
        }
        if (description_history is empty) then {
            record a failure — a status/wording change with no quote
            explaining it
        }

        # --- evidence ---
        if (status is live and there is no evidence at all) then {
            record a failure — evidence is the only thing that opens an issue
        }
        for each evidence entry {
            if (its quote is shorter than MIN_QUOTE=2 characters) then {
                record a failure and skip further checks on this entry
            }
            if (its cited source file does not exist) then {
                record a failure and skip further checks on this entry
            }
            if (the exact same quote string was already seen on this node)
                then { record a duplicate-quote failure }
            if (the quote is not found verbatim in the source text) then {
                if (the source carries [remember: ...] brackets) then {
                    retry per statement-span against the span's ROOM view
                    (markers.strip_remember, whitespace-flattened) — the
                    2026-08-14 room/record split stores issue-evidence-add
                    quotes as room text while the FILE keeps the bracket,
                    so a mid-statement bracket made a true quote fail
                    byte matching and refuse the whole batch (2026-08-19,
                    review tier 2 #14). A hit also settles attribution:
                    the span's own speaker. Byte-exact matching remains
                    the only rule for bracket-free sources, and the
                    bracket's own private text never matches the room
                    view, so it cannot be laundered in as evidence.
                }
                if (still not found) then {
                    record a failure and skip further checks on this entry
                }
            }
            if (found) then {
                count it as verified;
                if (the quote's text itself contains a speaker marker) then {
                    record a span failure — it ran past the statement it cites
                }
                determine who actually said it (source text, spoken-region
                lookup unless the source is a session file, which is always
                attributed to self);
                if (nobody can be determined) then { count as unattributable }
                else if (that speaker is not the part the evidence names) then {
                    record an attribution-mismatch failure
                }
            }
        }

        # --- held_by agreement ---
        if (a part is in held_by but gave no evidence) then { record it }
        if (a part gave evidence but is not in held_by) then { record it }

        # --- edges ---
        for each edge on the node {
            if (its target is not a known node id) then {
                record a dangling-edge failure and skip further checks on
                this edge
            }
            if (its status is not attested/proposed/retired) then { record it }
            if (it has no basis text) then {
                record it — "an assertion with no standing"
            }
            if (status is attested) then {
                if (it has no quote, or its basis names no circle/sandbox id)
                    then { record it }
                else if (the quote is shorter than MIN_QUOTE) then { record it }
                else {
                    look up the named circle's transcript;
                    if (missing, or the quote is not verbatim in it AND
                    not found by the same bracket-carrying room-view
                    retry the evidence check uses) then {
                        record it
                    } else { count it as verified, and as an edge-verification }
                }
            } else if (status is proposed) then {
                if (it has no "ask" naming who would confirm it) then {
                    record it
                }
            }
            if (status is not retired, and this node is live, and the
                target is not a legal end) then {
                record a closure failure — neither live nor a root
            }
            if (edge type is leads-to or narrower-than, and a reversed-
                direction phrasing pattern matches the edge's basis text
                around the target's id) then {
                record a "looks REVERSED" failure
            }
        }

        # --- wikilinks ---
        for every [[nNNNN]] link found anywhere in the node's string fields {
            if (it does not name a known node id) then {
                record a dangling-link failure
            }
        }
    }

    print counts of verified quotes (split evidence vs. attested-edge),
    how many of those are Self's own or a formally-adopted part's, a
    per-node adoption tally, and the unattributable count;
    if (there were any failures) then {
        print each one prefixed "-"; return 1
    } else {
        print "GATE PASS — every invariant satisfied"; return 0
    }

## COMMAND-LINE ARGUMENTS
- (no arguments): checks the live `issues/` directory (`issue_schema.ISSUES`).
- `<dir>` (optional, positional): checks the given directory instead, as a preview — nothing is written regardless.

## DEPENDENCIES
Standard library: `pathlib`, `re`, `sys`, `__future__.annotations`. Sibling modules: `identity` (as `ID`, for `ID.self_tags()`, the configurable set of tags meaning Self, used to build the speaker regex and the speaker-lookup table so attribution is not hardcoded to a literal name); `issue_schema` (as `S`, for `S.ROOT`, `S.ISSUES`, `S.load()`, `S.check()`); `roster` (as `R`, for `R.DIR_NAMES` and `R.DIR_BY_TAG_ALL`, the canonical part-directory list and tag-to-directory map including historical spellings, used to normalise a speaker marker to a part directory name).

## EXTERNAL FILES
Read: every `*nNNNN.toml` file under the target issues directory. For each node's evidence and edge citations, the transcript files they name — `circles/circle_<ref>.md` for a `circle_`-prefixed reference, `work/sandbox/circles/circle_<ref>.md` for a `sandbox_`-prefixed one, or `self/<ref>.md` otherwise (via `source_of()`), cached in-memory per path once read (`_CACHE`) to avoid re-reading a transcript for every evidence entry that cites it.

Written: nothing. The module's own docstring states it is "Read-only," and no file-write call appears anywhere in it.

## NETWORK ACCESS
None.

## HUMAN I/O
Stdout only, no stdin. Prints a node/live-count summary, verification counts, adoption tallies, an unattributable count, and (if any) a numbered list of invariant failures. Exit codes: 1 if any failure was recorded, 0 if the gate passes cleanly.

## OPERATION

### `source_of(ref)`
    {
        map a citation reference string to its transcript file path. The
        circle_/sandbox_ mapping is issue_schema.circle_transcript() —
        ONE copy since 2026-08-19 (review, tier 5 #44: this gate,
        issue_projection._transcript() and check_budget's constants were
        three lockstep clones the R176 sweep had to edit together). The
        SELF-DIR arm — a bare ref resolves to a session record under
        self/ — stays this gate's own, because only the gate admits
        session refs.
    }

### `text_of(p)`
    {
        read and cache (by path) a transcript file's full text, replacing
        undecodable bytes rather than raising.
    }

### `speaker_spans(text)`
    {
        find every regex match of a speaker marker in the text; if none,
        return no spans (the whole transcript is unattributable). Assign
        the region before the first marker to "self" only if it starts
        within TOPIC_MAX=2000 characters (a mixed-era transcript's
        unparsed leading region beyond that point is left unattributed
        rather than guessed at). For each marker, resolve its speaker
        name to a canonical part directory (or "self") via the SPEAKERS
        table built from roster.py and identity.py; unresolvable markers
        are silently dropped from the span list rather than raising.
    }

## BUGS
None found — the module's own docstring and inline comments already document and date several bugs this version fixes (the closure check that only lived inside the `proposed` branch until 2026-08-05, letting an attested edge to a non-live node go unchecked; a MIN_QUOTE threshold that was enforced on evidence quotes but not attested-edge quotes until 2026-08-07). Nothing further was found while reading it.
