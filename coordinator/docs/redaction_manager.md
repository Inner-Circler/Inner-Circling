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
    RM.alias_delete(n) · RM.alias_list() · RM.alias_protected_read()

The command-pane verb is `/redact-alias` (`commands.py`); `ui/circling.py`'s CIRCLE pane is the one
surface that renders the redacted view.

## DESCRIPTION
Ruled 2026-08-31 on the CIRCLE pane's redacted view: a raw/redacted switch on the settings page, CRUD
of target strings, stable reversible opaque ids — a model adapted from a design used in a separate
personal project. TWO REGISTERS, DELIBERATELY SEPARATE, at two sensitivity levels:

    self/redaction.toml       the CURATED alias registry — canonical name, kind (person/place/org/
                             other), extra surface forms, a stable opaque id (P1, L1, O1, G1). Ships
                             empty: it holds only the labels the operator chose to hide.
    self/redaction_map.toml   the REVERSE MAP for auto-detected structured identifiers (email/url/
                             phone/handle) — literal -> stable id (E1, W1, T1, H1), minted the first
                             time each is seen so the same email always redacts to the same token.
                             `literal` IS raw PII; this file never ships.

Token spelling is unhyphenated (`P1`, not `P-1`) because these are PROSE-FACING — they replace a
name inline in the rendered pane. THE HARD EXEMPTION, the operator's own words: *"part names are never
redacted."* Every part tag, every historical alt-spelling and every name Self has gone by is refused
at add/update time and filtered out of the compiled pattern besides. NON-DESTRUCTIVE: nothing here
touches the transcript or the record; the one display-time write is a new structured-identifier token
minted into the map, so it stays stable across restarts.

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
                              stream_redaction.py through _map_doc()/_map_save() here; --init writes
                              it empty. NEVER SHIPS (packaging/runtime_only.txt).
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

### `alias_list()`
    { "  no redaction aliases", or one numbered line per alias: [id] kind canonical (forms) }

## BUGS
None found. Note for the reader: the alias listing's number is positional, so `alias_update(n)` and
`alias_delete(n)` typed against a stale listing act on a different row — the same contract every
numbered listing in this project carries.
