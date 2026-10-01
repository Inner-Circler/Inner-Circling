# REDACTION_MANAGER.PY(1)

## NAME
redaction_manager.py — the two REDACTION registers, `self/redaction.toml` (the curated aliases) and
`self/redaction_map.toml` (the structured-identifier tokens): their one reader/writer. (`redaction.py`
until 2026-09-03 — B99 stage 18d under R435; the redact pipeline and the view's default are
`stream_redaction.py`'s now.)

## SYNOPSIS
```
python coordinator/redaction_manager.py           the alias listing
python coordinator/redaction_manager.py --init    write both empty registers
```
    import redaction_manager as RM
    RM.alias_read() · RM.alias_add(canonical, kind, forms) · RM.alias_update(n, canonical, forms)
    RM.alias_delete(n) · RM.alias_list() · RM.alias_protected_read() · RM.alias_forms_expand(row)

The command-pane verb is `/redact-alias` (`commands.py`). Two surfaces read the registry through
`stream_redaction.py`: `ui/circling.py`'s CIRCLE pane (`stream_redact`) and the Ticker's lens
(`bridge.py`'s `do_redact`, via `stream_session_redact`).

## DESCRIPTION
Ruled 2026-08-31 on the CIRCLE pane's redacted view: a raw/redacted switch on the settings page, CRUD
of target strings, stable reversible opaque ids — a model adapted from a design used in a separate
personal project. TWO REGISTERS, DELIBERATELY SEPARATE, at two sensitivity levels:

    self/redaction.toml       the CURATED alias registry — canonical name, kind (person/place/org/
                             other), extra surface forms, a stable opaque id (P1, L1, O1, G1). Ships
                             empty: it holds only the labels the operator chose to hide.
    self/redaction_map.toml   the REVERSE MAP for auto-detected structured identifiers (email/url/
                             phone/handle) — literal -> stable id (E1, W1, T1, H1), minted the first
                             time each is seen so the same email always redacts to the same token;
                             and each chat-log SPEAKER detected by its line's shape (U1, U2).
                             `literal` IS raw PII; this file never ships.

Token spelling is unhyphenated (`P1`, not `P-1`) because these are PROSE-FACING — they replace a
name inline in the rendered pane. THE HARD EXEMPTION, the operator's own words: *"part names are never
redacted."* Every part tag, every historical alt-spelling and every name Self has gone by is refused
at add/update time and filtered out of the compiled pattern besides. NON-DESTRUCTIVE: nothing here
touches the transcript or the record; the one display-time write is a new structured-identifier token
or speaker id minted into the map, so it stays stable across restarts.

## MAIN
    if ("--init" is among the arguments) then {
        for each of the two registers: if (absent) then { write its empty document }
        print which were written, or that both already exist; exit 0
    } else { print alias_list(); exit 0 }

## COMMAND-LINE ARGUMENTS
`--init`: write both empty registers where absent. Default: off (the listing).

## DEPENDENCIES
Standard library: `pathlib`, `sys`. Sibling modules: `REGISTER_CLASS` (as `SS`: `register_read`,
`register_write`, `register_now`), `part_roster` (as `R`: `TAGS`, `ALT_TAGS`), `identity` (as `ID`:
`self_tags()`), `record_paths` (as `P`: `REDACTION`, `REDACTION_MAP`).

## EXTERNAL FILES
    self/redaction.toml       READ by alias_read()/alias_list(); WRITTEN by alias_add(),
                              alias_update(), alias_delete() and --init, through REGISTER_CLASS.
                              Absent reads as the empty document with four `next_<kind>` counters.
    self/redaction_map.toml   READ and WRITTEN by the structured-identifier pass in
                              stream_redaction.py through _map_doc()/_map_save() here, and by
                              redaction_speaker_read()/redaction_speaker_add(); --init writes it
                              empty. NEVER SHIPS (packaging/runtime_only.txt).
    parts/*/part.toml         READ indirectly, through roster, for the protected tags.
    self/identity.toml        READ indirectly, through identity.self_tags().

## NETWORK ACCESS
None.

## HUMAN I/O
`main()` prints to stdout; every other function returns `(ok, message)` or a listing string for the
caller to show.

## OPERATION

### `_alias_doc()` / `_map_doc()`
    if (the file exists) then { load it } else { the empty document: register name, [doc] preamble,
        one `next_<kind>` = 1 per kind, no rows }

### `alias_protected_read()` / `_protected_hit(s)`
    { every word that may NEVER be redacted, casefolded: the live part tags, the alt tags,
      every name Self has gone by — rebuilt on every call; _protected_hit() returns the
      collision or None }

### `alias_add(canonical, kind="other", forms=None)`
    if (canonical is empty) then { refuse }
    else if (kind is not person/place/org/other) then { refuse, naming the four }
    else if (canonical or ANY form collides with a protected name) then { refuse, naming it }
    else { mint the id from that kind's counter (P/L/O/G + n), append {id, kind, canonical,
        forms = [canonical] + forms, created}, bump the counter, save; (True, "added [id] ...") }

### `alias_update(n, canonical, forms=None)`
    if (n is outside 1..count) then { refuse, pointing at /redact-alias-list }
    else if (canonical is empty, or any candidate collides with a protected name) then { refuse }
    else { replace the nth row's canonical and forms IN PLACE — same id, same kind, same
        position; save; (True, "updated [id] ...") }

KIND IS NOT EDITABLE HERE, on purpose: an id's prefix names its kind at creation and never changes —
the "an id is never reused or renumbered" rule. Delete and re-add if the kind was wrong.

### `alias_delete(n)`
    if (n is outside 1..count) then { refuse } else { pop the nth row; the counter is
        untouched (the id is never reused); save; (True, "removed [id] ...") }

### `alias_forms_expand(row)`
    { every surface form the alias redacts, longest first: its curated forms and its canonical;
      if (the canonical is `display (user.name)`) then { add display, user.name, and each word of
          both — the user name split on its dots too }
      else if (kind is person) then { add each whitespace-separated word of the canonical }
      drop any derived word shorter than two characters; write nothing }

`anon::expand_forms` from the original design's own anonymization engine: the short and long
names of one alias collapse to its one id. Other kinds keep the whole label, since splitting an org
into its common words invites false positives. The protected-name filter is applied to every
expanded form in `stream_redaction._alias_lookup()`, not here.

### `redaction_speaker_split(segment)` / `redaction_speaker_expand(segment)`
    { `Name (user.name)` -> (display, handle); no parentheses -> (the slot, "") }
    if (the slot is empty) then { None }
    else { forms = the whole slot, the display name, its GIVEN name (two characters or more), the
        handle — never the surname or the handle's dotted pieces; key = the handle lowercased, else
        the display name lowercased; (key, forms longest first) }

The original design's `anon::expand_speaker`. The key makes a slot with a handle and a later bare
handle one speaker.

### `redaction_speaker_read()` / `redaction_speaker_add(segment)`
    { every map row of kind `speaker` }
    if (a speaker row with the same key is on file) then { return it; write nothing }
    else { mint `U` + next_speaker, append {id, kind speaker, literal = the slot, created}, bump
        the counter, save; return the row }

### `redaction_speaker_list()` / `redaction_speaker_record_show(n)`
    { "  no detected speakers", or one numbered line per speaker: [id] the slot (its forms), then
      the footer naming the count and `/redact-speaker-list <n>` }
    { the nth speaker WHOLE, by REGISTER_CLASS.register_record_show() }

### `redaction_speaker_delete(n)` / `redaction_speaker_suppressed_read()`
    if (n is outside 1..count) then { refuse, pointing at /redact-speaker-list }
    else { replace the nth speaker row, in place, with {same id, kind suppressed, literal = its
        identity key, created}; save; (True, "removed [id] ...") }
    { the identity key of every suppressed row }

A removed speaker's names show again at once and its slot is never detected again; the id is never
reused. To hide the name after all, curate it with `/redact-alias-add` — a curated alias matches
whatever is suppressed. The command-pane verbs are `/redact-speaker-list [<n>]` and
`/redact-speaker-delete <n>` (`commands.py`).

Detection is stream_redaction.py's (`_speakers_discover`): a line starting `[time]` or
`[date time]`, the slot up to the first colon. A speaker lives in the map, not the alias registry:
its name is a third party's the operator never typed, so it takes the map's sensitivity.

### `alias_list()` / `alias_record_show(n)`
    { "  no redaction aliases", or one numbered line per alias: [id] kind canonical (forms), then
      the footer naming the count and `/redact-alias-list <n>` (B133) }
    { the nth alias WHOLE — every field, by REGISTER_CLASS.register_record_show() }

## BUGS
None found. Note for the reader: the alias listing's number is positional, so `alias_update(n)` and
`alias_delete(n)` typed against a stale listing act on a different row — the same contract every
numbered listing in this project carries.
