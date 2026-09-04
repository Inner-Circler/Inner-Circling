# IDENTITY(1)

## NAME
identity.py — resolves who "Self" is for this installation: the fixed internal id versus the configurable display name, and which tags in a transcript mean Self

## SYNOPSIS
    python coordinator/identity.py

(No arguments; the module's CLI is diagnostic-only. It is otherwise imported as a library — `import identity as ID` — by other coordinator modules.)

## DESCRIPTION
This module resolves ruling 2026-08-07: "during circles, the role of the user 'Self' should be personalized, that is, code should accept and generate 'Self' unless a 'UserName' is present." It exists to prevent conflating two distinct names that a single earlier hardcoded value used to be:

- `SELF_ID` ("self") — the canonical internal id, never displayed or written to a transcript, used for every `speaker ==` comparison in the codebase.
- `user_name_read()` — the CONSOLE-ONLY name: the Soul's recorded preferred_name, else $IFS_USER_NAME from the .env file, else "Self" (R325, 2026-08-23). Shown at the console prompt, in /help and --identity, and nowhere else; the transcript writes the fixed DISPLAY `[Self]:`.

The docstring documents, in some detail, a Windows-specific trap: `os.environ` is case-insensitive on Windows and Windows always sets `USERNAME` for every process, so a naive `os.environ.get("UserName")` silently returns the OS login name (lower-cased) rather than an unset default, and `.env` cannot override it because `load_dotenv()` never overwrites a variable the OS already set. The module works around this by checking a project-specific variable, `IFS_USER_NAME`, first — it is the only variable `.env` can actually control on this platform — and the ruled `UserName` variable second, as the fallback that in practice is rarely reached once `IFS_USER_NAME` is set (which it now is, per the docstring, as of 2026-08-07).

The module also maintains the set of tags a transcript reader should recognize as meaning Self (`self_tags()`), used by parsers elsewhere to distinguish Self's statements from a part's. This set is built explicitly (a fixed historical-names tuple, plus any configured retired tags, plus the current display name) rather than by the earlier, shorter, and wrong heuristic "any tag that is not a part is Self" — a real corpus of transcripts caught that heuristic accepting malformed tags like `[Self, sings]` or `[Child — Self-report]` as ordinary Self statements, which a stricter, explicit-set version correctly refuses. A literal personal name was once in the historical-names tuple and was removed by ruling on 2026-08-07 as PII that a proper export should not carry; `self_tags()` already unions in the *current* configured name, so removing the literal changed nothing functionally for the current installation.

## MAIN
This module has no `main()` function; running it directly executes a flat diagnostic block under `if __name__ == "__main__":` rather than a defined entry point.

    {
        resolve the display name and its source via user_name_source();
        print the resolved display name and source, the canonical internal id (fixed), the transcript tag form, the operator prompt form, and the full set of tags this installation reads as Self (self_tags()).
    }
    if (the resolved name's source is the ruled $UserName environment variable) then {
        print a note that $UserName is the OS login on Windows, not a name deliberately chosen, and that $IFS_USER_NAME should be set in .env to control it.
    }
    {
        print a pointer to `gitrepo.py --identity` for the separate git-author identity question.
    }

## COMMAND-LINE ARGUMENTS
None. The module takes no arguments; running it with `python coordinator/identity.py` always executes the diagnostic block above.

## DEPENDENCIES
Standard library: `os`, `pathlib`, `__future__`. Optional third-party: `python-dotenv` (`from dotenv import load_dotenv`), used best-effort inside `_load_env()`; a missing package is caught and tolerated silently.

## EXTERNAL FILES
Read: `ROOT/.env`, best-effort, via `_load_env()`, called from `user_name_read()`, `user_name_source()`, and `self_retired_tags_read()` — every function that needs environment configuration re-loads `.env` rather than caching it once.

Written: none.

## NETWORK ACCESS
None.

## HUMAN I/O
Stdout only, from the `__main__` diagnostic block described under MAIN. No stdin, and no meaningful exit code beyond Python's default (the block does not call `sys.exit` or return a nonzero status explicitly).

## OPERATION

### `_load_env()`
    {
        Attempt to import python-dotenv and load ROOT/.env; if the package is absent, do nothing. A missing .env file is likewise tolerated (load_dotenv handles that itself).
    }

### `soul_preferred_name()`
    {
        read parts/soul/part.toml directly with tomllib (dependency-light, the way self_installed_tags_read()
        reads self/identity.toml); return [context].answers.preferred_name stripped, or "" when the
        file, the table or the key is absent, empty, or unreadable — never raises. Re-read on every
        call. (R325, 2026-08-23; the Soul is a RESERVED part, which is why a shipped
        module may name its directory.)
    }

### `user_name_read(explicit=None)`
    if (an explicit non-blank name was passed) then {
        return it, stripped.
    } else {
        return user_name_source()[0]
    }

### `user_name_source()`
    {
        (value, source-label), most explicit first: soul_preferred_name() if non-blank
        ("parts/soul/part.toml preferred_name"); else IFS_USER_NAME from the .env FILE
        ("$IFS_USER_NAME"); else the literal "Self" ("default"). Never the OS login (R132). The
        console-only name — DISPLAY and SELF_ID do not move (R329).
    }

### `self_retired_tags_read()`
    {
        Read the comma-separated $IFS_SELF_TAGS environment variable (via .env) and return its non-blank, stripped entries as a frozenset. This exists to let an installation register a display name it used to write but no longer does, so older transcripts under that name keep parsing correctly after the configured name changes. Empty is the normal case — nothing currently needs it.
    }

### `self_tags(current=None)`
    {
        Return the union of: the fixed HISTORICAL_NAMES tuple (currently just "Self"),
        self_retired_tags_read(), and either the given `current` name or the live user_name_read().
    }

### `self_is_tag(tag, current=None)` (`is_self_tag()` before the B99 re-homing, 2026-09-03)
    {
        Return True only if `tag` is literally in self_tags(current) — an explicit membership test, not a "not a known part" fallback. An unrecognized tag is neither a part nor Self, and the docstring is explicit that callers must refuse it rather than silently treating it as Self.
    }

## BUGS
None found.
