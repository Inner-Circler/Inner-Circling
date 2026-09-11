# SETTING_MANAGER.PY(1)

## NAME
setting_manager.py — the SETTING register: `self/settings.toml`, the one place a person changes what
the code would otherwise decide. Approved 2026-08-28 (R379). (`settings.py` until 2026-09-03 — B99's
residue under R435; its gate is its own module, `system_setting_verify.py`.)

## SYNOPSIS
```
python coordinator/setting_manager.py           every setting, its value and its source
python coordinator/system_setting_verify.py     the gate: SPEC and the call sites agree
```
    import setting_manager as SET
    SET.setting_value_read(key, default) · SET.setting_write(key, raw, now=...) · SET.setting_clear(key)
    SET.setting_pending_fold() · SET.setting_corrections_flush(emit) · SET.setting_visible_read(dev)
    SET.setting_tuning_read(provider) · SET.setting_tuning_write(provider, key, raw)
    SET.setting_model_rate_rows_read() · SET.setting_show(key, v) · SET.setting_source_default_read(owner, key)
    SET.setting_accepts_read(spec) · SET.setting_record_read(spec, dev=...)
    SET.setting_tuning_record_read(provider, knob, dev=...)

The verbs — `/settings-list [<n>]`, `/settings-update`, `/settings-clear` (`SETTINGS_VERBS`) — are
`commands.py`'s; they are command-pane only and deliberately not proposable. `/settings-list <n>`
shows one setting whole: its default, what it accepts, and why the default is what it is
(R543, answering D122 (c)).

## DESCRIPTION
THE REGISTER OVERRIDES A CONSTANT; IT DOES NOT REPLACE ONE. Every value still has its constant, in
its own module, beside the paragraph that says why the number is what it is; the call site reads
`SET.setting_value_read("statements_per_part", 2)` and the literal it passes IS the documented
default. An absent file, an absent key or an unreadable file all mean the default stands — which is
why a fresh clone, a worktree and a shipped bundle all work with no file at all.

THE SCHEMA IS CODE; THE VALUES ARE DATA. `SPEC` declares which settings exist — the key, the question
it asks, its type (`NUMERIC_STRING`, `STRING`, `BOOL`, `FLOAT`), its ceiling, who may see it
(`audience`: "user" or "dev"), when a change takes effect (`applies`: "immediate" or "next_circle"),
the constant that owns its default (`owner`, `file::NAME`), a unit, how it is kept valid (`gate`:
BOUNDED, ONE_OF or CHECK_AT_USE), and `why` — one sentence saying why the default is what it is,
written from the owner's own reasoning paragraph, or saying that paragraph records none. A `why`
never states the default: the owner's literal is the one copy of the number, and
`system_setting_verify.py` refuses a sentence that repeats it. `self/settings.toml` holds only what a
person chose, in two tables:
`[active]` (in force now) and `[pending]` (waiting for the next circle to open, folded in by
`setting_pending_fold()` at the checkpoint `circle.py` runs before a circle's prompts are warmed).
Anything that shapes a prompt block, the model or a budget is `next_circle`. Per-provider tuning
lives in `[tuning.<provider>]` (R382), validated against what the provider declares. PARTS NEVER SEE
ANY OF THIS: the register feeds no prompt block, the verbs are command-pane only, and they are
excluded from the proposable set (`test_setting_manager.py` asserts all three).

CORRECTIONS ARE BUFFERED, NOT PRINTED: settings are read at import, before the two-pane UI has a
surface, so a stored value that fails its check is queued in `CORRECTIONS` and shown by whoever has
a surface (`circle.py` at open, the command pane on first use).

## MAIN
    { setting_report(): print the register path (or "no file; every default stands"), then for
      every setting in SPEC: its key, the active value or the source default marked "(default)",
      its question, its audience · applies · owner, and any PENDING value }
    exit 0

## COMMAND-LINE ARGUMENTS
None — a bare run prints the report.

## DEPENDENCIES
Standard library: `pathlib`, `sys`, `tomllib` (`tomli` on 3.10), `re` (inside
`setting_source_default_read()`). Sibling modules: `part_roster` (inside the tuning functions:
`part_context_value_verify()`, `part_canonical_read()`), `atomic_write` (inside `_dump()`), `seam`
(inside `setting_corrections_flush()` when no emitter is given). Nothing imports `anthropic`: the
gate that reads this module must stay runnable inside the pre-commit hook.

## EXTERNAL FILES
    self/settings.toml     READ by setting_read(), cached on the file's own (mtime, size) so a
                           long-lived UI process sees an edit at once; WRITTEN by setting_write(),
                           setting_clear(), setting_pending_fold() and setting_tuning_write()
                           through _dump() (atomic_write). Never ships.
    <owner module>         READ AS TEXT by setting_source_default_read() — the default is grepped
                           from the call site's second argument, never imported.

## NETWORK ACCESS
None.

## HUMAN I/O
`main()` prints the report. Corrections queue in `CORRECTIONS` and reach the command pane through
`setting_corrections_flush()`; every write returns `(ok, message-for-the-person)`.

## OPERATION

### `setting_read()`
    if (the file is absent) then { {} — every default stands }
    else if (its (mtime, size) match the cache) then { the cached document }
    else if (it does not parse) then { queue a correction saying so; cache {} }
    else { parse, cache, return }

### `setting_value_read(key, default)`
    if (key is not declared in SPEC) then { default }
    else if (no active value) then { default }
    else if (the stored value fails setting_coerce()) then { queue a correction naming the
        default and the command that tunes it; default }
    else { the parsed value }

### `setting_coerce(spec, raw)`
    if (BOOL) then { a real bool, or yes/y/on/true/1 -> True, no/n/off/false/0 -> False;
        else refuse "is not yes or no" }
    else if (NUMERIC_STRING) then { a positive whole number not over data_max; else refuse }
    else if (FLOAT) then { a non-negative number not over data_max; else refuse }
    else { STRING: at most data_max characters; `provider` must be in PROVIDERS_SUPPORTED }

### `setting_accepts_read(spec)`
    { setting_coerce()'s rule for spec, in words, branch for branch beside it: "yes or no";
      "a whole number from 1 to <data_max>"; "a number from 0 to <data_max>"; `provider`'s
      "one of: ..."; a CHECK_AT_USE string's length and its check at the first real call;
      else "up to <data_max> characters" }

### `setting_record_read(spec, *, dev)` / `setting_tuning_record_read(provider, knob, *, dev)`
    { what `/settings-list <n>` shows: every slot of the declaration, plus `now` (the value in
      use, "(unchanged)" when nothing was chosen), `default`, `waiting` when a change is
      pending, and `accepts`; walked by RECORD_ORDER (a knob by TUNING_RECORD_ORDER) and then
      the rest. With dev off the DEV_FIELDS — owner, data_type, data_max, audience, gate — are
      left out: dev adds fields, it never takes one away. A knob carries no `why`; its
      provider declares none }

### `setting_model_rate_rows_read()`
    { `[[model]]` rows as llm_client's rate table wants them: {(id, speed): (in, cache_write_1h,
      cache_read, out)}; a malformed row is skipped and said so, one line each, never raised }

### `setting_visible_read(dev)`
    { SPEC whole in dev mode; only audience = "user" otherwise — dev adds, never takes away }

### `setting_tuning_read(provider)` / `setting_tuning_write(provider, key, raw)`
    { the `[tuning.<provider>]` table, each key validated against the provider's declared
      knobs through roster's own value check; an unknown key is ignored with a word; an
      invalid value is replaced by the knob's default and reported. A write is ALWAYS
      pending — it alters what is sent }

### `setting_write(key, raw, *, now)`
    if (key is not a setting) then { refuse }
    else if (setting_coerce refuses) then { refuse with why }
    else { write to [active] if (applies is "immediate" and now) else [pending]; an active
        write drops the same key from [pending]; dump; (True, "key = value — takes effect
        now | when the next circle opens") }

`now` is the caller's answer to "may this take effect immediately" — `commands.py` asks
`circle_state`, this module does not.

### `setting_clear(key)`
    { remove the key from both tables; (False, "already at its default") if it was in neither }

### `setting_pending_fold()`
    { move every [pending] key into [active]; return the keys folded (empty list when none) }

### `_dump(doc)`
    { the file, written whole through atomic_write: a comment header, [active], [pending], then
      one [tuning.<provider>] table per provider with rows; the read cache is invalidated }

### `setting_source_default_read(owner, key)`
    { grep the owner module's source for `NAME = ...` at top level; if the right-hand side is a
      setting_value_read(...) call, the default is its SECOND argument, else the whole rhs;
      quotes stripped for display; (None, why) when the owner is not file::NAME, unreadable, or
      the name is not assigned at top level }

### `setting_show(key, v)`
    { a BOOL as "yes"/"no"; anything else as str(v) }

## BUGS
None found. Two behaviours worth naming: `redact_view` is `immediate` yet its SAVED value still
defers to `[pending]` while a circle is open, while the live pane flips at once through its own
signal — two clocks, said in the reply text on purpose; and a `[tuning.<provider>]` table for a
provider this build does not have is kept and ignored, never refused.
