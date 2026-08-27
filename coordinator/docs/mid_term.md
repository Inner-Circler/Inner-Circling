# MID_TERM.PY(1)

## NAME
mid_term.py — derives and caches each part's `mid_term.md`, the single distilled per-part text that reaches its prompt, from its `long_term.md`, `dreams.toml`, its `## Dreamt` short_term sections, and its `remember.toml` chain.

## SYNOPSIS
```
python coordinator/mid_term.py                          # state of every part: fresh/stale/absent/legacy/locked
python coordinator/mid_term.py --sources judge           # source char counts for one part
python coordinator/mid_term.py --refresh                 # derive every stale/absent/legacy part (real API calls)
python coordinator/mid_term.py --refresh judge            # derive just one part
python coordinator/mid_term.py --refresh --dry-run        # show what would be derived, call nothing
python coordinator/mid_term.py --lock judge                # freeze judge's current mid_term (Self's action)
python coordinator/mid_term.py --unlock judge
```

## DESCRIPTION
`mid_term.md` is described in the module docstring as "the only per-part
thing a prompt carries" — the distillate of a part's settled identity and
what its recent dreams concluded, boiled down to what's actually actionable
in a future prompt. Before this file (B28, 2026-08-07), that distillation
was done by hand: a human read `--sources` output in a Claude conversation
and pasted the result through `write()`. That produced the first fourteen
distillates and cannot be repeated automatically — a nightly cannot hold a
conversation. This file makes `--refresh` actually call the model,
mirroring `circle.py`'s own live API path (same `Anthropic()` client
construction, same `ANTHROPIC_API_KEY` resolution via env or `.env`).

The sources are named precisely and their names are meant to describe what
they now are, following a 2026-08-07 ruling: `long_term.md` is the settled
historical record and has stopped growing (it used to also receive dream
write-backs); `short_term_<OT>.md` is one circle's own file, append-only,
and carries that circle's `## Dreamt` section; `mid_term.md` is the
standing distillate, rewritten whenever any source changes. This fixed a
real defect: R112's 2026-08-03 ruling sent dreams to `short_term_<OT>.md`,
but nothing read a short_term file, so thirteen `## Dreamt` sections were
written and reached no prompt at all — correct per the letter of the
ruling, inert in fact. `dreamt()` is what makes those sections reachable
again, by treating them as a mid_term source rather than routing them into
`part_identity` raw (which measurement showed was mostly waste: of 26,290
characters of live-only Child material, only ~1,400 were actionable).

`part_relationships.toml` WAS a fifth source, from PROMPT v5 (2026-08-15)
through v6 (2026-08-15, when `remember.toml` joined it), and is DROPPED as
of v7 (2026-08-22): "I do not want it in the prompt context in any block.
Studies showed it was not helpful." — the same instruction that, earlier
the same day (R302), had already removed the register's own DIRECT
projection into BLOCK 3. Today's `sources()` returns four keys of
substance — `long_term`, `dreams` (the `dreams.toml` corpus), `dreamt` (the
`## Dreamt` short_term sections), and `remember` (the reflexive chain,
R178, 2026-08-15) — plus the assembled `text` all four are concatenated
into.

Staleness is computed from a content hash over the sources' assembled
`text` plus the model/prompt version, not from a date — `long_term.md`
carries no per-record timestamps, so there is nothing to compare a date
against, and hashing means a new circle's dream, or a new `remember`
write, automatically invalidates that part's cached distillate without
anyone having to remember to trigger it. Bumping `PROMPT` (as v7 did) also
invalidates every part at once, deliberately: a prompt-shape change is an
input to the derivation exactly as the sources are, so a version bump must
force a fresh derivation rather than let an old distillate — one made
under the old prompt, from a source set that no longer matches — go on
being served as `fresh` under a new label.

There is deliberately no verifier that checks the distillate's claims
against its sources. A prior proposal — having the derivation emit a
distinctive phrase per heading and locating it in the sources, as
`asks_extract` did for ask fragments before it was retired 2026-08-12 —
was explicitly denied by Self on 2026-08-07: an ask fragment's quote
anchors to a part's STATEMENT, an event that happened in a room and was
recorded as said; a mid_term source (`long_term.md`, a `## Dreamt`
section) is *itself* an LLM derivation, so locating a phrase in one
derivation inside another would only prove two derivations agree with
each other, not that either is true — "a guard checking derivation
against derivation is theatre with a passing exit code." Trust is instead
placed plainly: the distillate is attributed to the model, its sources
are named by hash in the front matter, and the untouched source record
remains readable. Nothing here ever deletes a source.

## MAIN
```
read argv (no argparse; manual dispatch on argv[0]).
if (argv[0] == "--sources") then {
    print per-source character counts (long_term, each Dream and Dreamt
    section) for the named part; return 0.
} else if (argv[0] == "--refresh") then {
    strip a possible --dry-run flag; take the remaining first token, if
    any, as "only this part"; call refresh(only, dry_run) and return its
    result (a failure count used as the exit code).
} else if (argv[0] in ("--lock", "--unlock")) then {
    read the named part's mid_term.md directly.
    if (it has no mid_term at all) then {
        print "<part> has no mid_term" and return 1.
    } else if (its first line is not mid_term front matter — legacy) then {
        print that a legacy file must be derived (--refresh) before it
        can be locked, and return 1.
    } else {
        toggle the " · mid_term_locked" marker on the EXISTING front-
        matter line (same construction write() uses) and write the file
        back otherwise byte-identical; print LOCKED/unlocked; return 0.
        Never re-stamp via write(): until 2026-08-19 this path did, and
        write() computes hash from the CURRENT sources — locking or
        unlocking a part whose sources had moved re-labeled a stale
        distillate as fresh, and refresh() then skipped it indefinitely.
    }
} else {
    print the state listing() for every roster part (fresh / stale /
    absent / legacy / locked, plus source char count, dream count, and
    hash) and how many need derivation; return 0.
}
```

## COMMAND-LINE ARGUMENTS
- `--sources <part>` — print each source's character count for one part; makes no derivation, no API call.
- `--refresh [part] [--dry-run]` — derive every part in `stale`/`absent`/`legacy` state (or just `part`, if given), skipping `locked` and `fresh` parts. `--dry-run` prints what would be derived without calling the API.
- `--lock <part>` / `--unlock <part>` — mark the part's current `mid_term.md` as Self-authored and frozen (or release that freeze); does not re-derive.
- (no arguments) — print the state table for all parts.

## DEPENDENCIES
Standard library: `hashlib`, `pathlib`, `sys`, `os` (imported locally inside `_client`). Sibling modules, imported locally where used: `prompt_build` (as `C`, for `C.strip_settled()`, `C.read_ro()`, `C.PART_TAGS`), `self_schema` (as `SS` inside `dreams_toml()`, for `SS.load()`/`SS.unwrap()`; via `__import__("self_schema")` inside `write()`, for `self_schema.now()`), `remember` (as `RM` inside `sources()`, for `RM.entries()`), `ifs_model` (as `IFS` inside `refresh()`, for `IFS.IDENTITY_END`). Third-party (only for `--refresh` without `--dry-run`): `anthropic` (`Anthropic`), optionally `python-dotenv` for `.env` loading.

## EXTERNAL FILES
Read: `parts/<part>/long_term.md` (via `prompt_build.read_ro`, with settled sections stripped by `prompt_build.strip_settled`); `parts/<part>/dreams.toml` (unsettled entries only); every `parts/<part>/short_term_*.md`, scanned for `## Dreamt` sections; `parts/<part>/remember.toml` (every record's text, via `remember.entries()`); `parts/<part>/mid_term.md` (to read its front-matter hash/lock state and, in `block()`, its body). `part_relationships.toml` is NOT read here as of 2026-08-22 (PROMPT v7) — see DESCRIPTION.

Written: `parts/<part>/mid_term.md` — by `write()`, called from `refresh()` on a successful derivation; and by the `--lock`/`--unlock` path directly, which since 2026-08-19 toggles the `mid_term_locked` marker on the existing front-matter line and leaves every other byte (hash included) as the derivation wrote it.

## NETWORK ACCESS
Yes, conditionally: one `Anthropic().messages.create()` call per part being refreshed (model `claude-sonnet-5`, `max_tokens=8000` (`DERIVE_MAX_TOKENS` — thinking tokens count against the cap, R354)), made only when `--refresh` is run without `--dry-run`. No network call in any other mode.

## HUMAN I/O
No stdin. `refresh()` reports per-part state listings, per-part derivation progress ("deriving from N source chars..."), a SUSPECT warning (with reasons) for any derivation that comes back short, stopped at `max_tokens` (a truncated document, refused whatever its length — `suspect_reasons()`, R354), or leaks a raw dream-corpus heading — such results are explicitly NOT written — and a final token/cost summary, all through a `say` parameter (default `print`, so a direct/CLI call is unchanged) — fixed 2026-08-16 from a bare `print()` that bypassed whatever routing the caller used, invisible under circling's alternate screen buffer even when `inter_circle.py`'s own summary line was already routing correctly. `refresh()` returns the number of failed derivations, used directly as `main()`'s exit code for `--refresh`; all other subcommands return 0 (or 1 for lock/unlock on a part with no mid_term).

## OPERATION

### path(part)
`parts/<part>/mid_term.md`.

### dreamt(part)
```
{
    For every parts/<part>/short_term_*.md file, newest circle first,
    scan the WHOLE file for every "\n## Dreamt" occurrence (not just the
    first), slicing each section up to the next "## " heading or end of
    file. Return a list of (open_time, section_text) tuples.
}
```
The comment flags a fixed prior defect: the original version split once and cut at the next heading, silently dropping a second dream section in the same file (a re-dream of the same circle) — caught by a probe's first run, which is the stated reason it now loops.

### dreams_toml(part)
```
{
    If parts/<part>/dreams.toml does not exist, return [].
    Otherwise load it and return (date, title, unwrapped content) for
    every record whose section is "dream" (unsettled) — a "settled"
    record is excluded, already-integrated history rather than fresh
    signal for a distillate.
}
```

### sources(part)
```
{
    Read long_term.md (with settled sections stripped); call
    dreams_toml(part); call dreamt(part); read every remember.toml
    record's text via remember.entries(). Concatenate long_term, every
    dream, every Dreamt section, and (if any exist) the remembered lines
    into one "text" string used identically for both hashing and the
    model call — ensuring the hash and the API call see exactly the
    same bytes.
    Return a dict with long_term, dreams, dreamt, remember, and text.
}
```

### source_hash(part, src=None)
sha256 of the sources' text plus `"|<MODEL>/<PROMPT>"`, truncated to 16 hex chars. `src` (2026-08-19, review tier 5 #52) reuses an assembly the caller already made — state()/derive()/write() all take the same optional parameter, and refresh() threads ONE assembly per part through the whole chain: this halves the prompt path's per-part read cost (state() used to assemble every source file twice per call) and closes a race — the hash stamped on a distillate now describes the bytes the derivation actually read, not a fresh read of disk that may have moved mid-refresh. Omitted, each function assembles its own, so direct calls are unchanged.

### _front(part) / locked(part)
```
{
    _front reads the first line of an existing mid_term.md. If the file
    doesn't exist, returns {}. If the first line isn't a "<!-- mid_term
    ...-->" comment, returns {"legacy": True}. Otherwise parses out the
    hash and model from the comment.
    locked reads whether the first line contains "mid_term_locked".
}
```

### refresh_cutoff(part)
```
{
    Return _front(part)'s "when" field — the timestamp this part's
    CURRENT mid_term.md was derived at, second-precision. None if there
    is no real front matter to read one from (absent or legacy), which
    the caller must treat as "nothing settled yet", not guess a cutoff.
    Used by remember.py's BLOCK 3/4 split to decide whether a remember
    record existed at the last refresh or was written since.
}
```

### state(part, src=None)
```
compute the sources (once — `src` reuses a caller's, see source_hash)
and their hash into an info dict.
if (path(part) doesn't exist) then {
    return "absent".
} else if (locked(part)) then {
    return "locked".
} else {
    read the front matter.
    if (it's a legacy file with no hash) then {
        return "legacy" — real content that predates the hash and cannot
        be judged stale/fresh, so it must not be silently discarded.
    } else if (its stored hash matches the current source hash) then {
        return "fresh".
    } else {
        return "stale".
    }
}
```

### block(part)
```
{
    The only function the live prompt-assembly path calls — never
    derives, never calls a model.
}
if (state is "absent") then {
    return ("", "no mid_term") — the caller MUST fall back to raw
    sources rather than send a part an empty identity.
} else {
    read the file, strip the front-matter comment line if present, and
    return (text, state).
}
```

### write(part, body, locked_by_self=False, src=None)
```
{
    Build the front-matter comment line (hash, model/prompt version,
    timestamp, source char count), append "· mid_term_locked" to it if
    locked_by_self, and write it plus the body to the part's mid_term.md.
    `src` must be the assembly the DERIVATION read (refresh threads it
    through — see source_hash) so the stamped hash describes what the
    body was actually made from.
}
```

### _client()
```
if (ANTHROPIC_API_KEY is not set) then {
    try loading it from .env via python-dotenv (ignored if unavailable).
}
if (still not set) then {
    raise RuntimeError with the required-env-var message.
} else {
    return an Anthropic() client.
}
```

### derive(client, part, src=None)
```
{
    One non-cached model call: SYSTEM (formatted with BUDGET) as the
    system prompt, the part's full source text as the sole user message.
    Returns (response text, usage object) — write() is a separate step
    so a caller can inspect the body before committing it. `src` as in
    source_hash.
}
```

### refresh(only=None, dry_run=False, say=print)
```
determine target parts (only [only] if given, else every roster part).
for each target, assemble its sources ONCE and compute state(part, src)
— the same assembly is then threaded through derive() and write()
(tier 5 #52), so the scan costs one read per part and the stamped hash
matches the derived bytes:
if (state in stale/absent/legacy) then {
    queue it for derivation.
} else if (state == "locked") then {
    print "<part>: locked — skipped".
} else if (only was given, i.e. the single requested part is already
fresh) then {
    print "<part>: already fresh — nothing to do".
}
if (nothing queued) then {
    print "nothing to derive" and return 0.
} else {
    obtain a client unless dry_run.
    for each queued part:
    if (dry_run) then {
        print "(skipped — no model call)" and continue.
    } else {
        call derive(); accumulate input/output token totals.
        if (result is under half of BUDGET characters) then {
            flag it as suspiciously short.
        }
        if (IDENTITY_END appears in the result) then {
            flag it as a raw-corpus leak past the identity boundary.
        }
        if (any flag was raised) then {
            count it as a failure, print SUSPECT with reasons, and do
            NOT write it.
        } else {
            write() it and print the char count and new hash.
        }
    }
    if (any real API calls were made) then {
        print total tokens and estimated cost.
    }
    return the failure count.
}
```
Every line goes through the `say` parameter (default `print`), not a bare `print()` — see HUMAN I/O.

### listing()
Prints a state table (state, source chars, dream count, dreamt count, hash) for every roster part.

## BUGS
None found. `refresh()`'s "under half budget" and "leaked heading" checks are heuristic by design and documented as such (a caller is told to inspect manually rather than force a bad write), which is a deliberate tradeoff rather than a defect.
