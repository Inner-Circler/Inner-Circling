# PART_ADD.PY(1)

## NAME
part_add — the part-lifecycle register: create, list, view, delete a `parts/<name>/` directory
(A14's creation path)

## SYNOPSIS
```
import part_add as PA
PA.part_add(name, tag, identity) -> (ok, msg)
PA.precheck(name, tag, identity) -> "" | reason
PA.derive_name(tag) -> str
PA.listing() -> str;  PA.view(n) -> (ok, text);  PA.delete(n) -> None
```
Generated 2026-08-23 with stage 5 of `docs/Initialization.md`, built to
`docs/part_commands_design.md` as its §8 reconciled it. `initialization.part_add_dialog()` is the
asking layer; the cmd> verbs (`/part-add`, `/part-list`, `/part-view`, `/part-delete`) dispatch
through `commands.dispatch_dev_cmd()` into here.

## DESCRIPTION
A part IS a directory under `parts/` whose `part.toml` names its Tag (roster.py — the marker's
presence is membership) and whose `long_term.md` is its identity. `part_add()` writes
long_term.md FIRST and part.toml LAST, so a crash between the two leaves a reported non-part,
never a member with no identity — `prompt_build.read_ro()` reads long_term.md bare and an empty
identity crashes prompt assembly, which is also why an empty description is refused outright.
The identity seed is the person's words VERBATIM under `## How my human describes me`; dreaming
evolves it from there. A part added now JOINS THE NEXT CIRCLE: six modules copy the roster at
import, so the current process cannot see a new directory.

`precheck()` is the whole validation, against a FRESH scan: the description (required, <= 40
words), the Tag (non-empty, none of roster.BAD_IN_TAG, no live-Tag collision case-insensitively,
not Self's reserved names), the directory name (derives from the Tag; `^[a-z][a-z0-9_]*$`, not
taken), and the ceiling (`circle_close.MAX_MEMBERS` = 9 = 8 parts + lead — raising it is its own
deliberate act).

`delete()` refuses the RESERVED Soul and Child before any question, refuses while a circle may be
open (`circle_state.open_circles()`, failing closed — a live round reading a vanished
long_term.md is a crash, not an absence), lists every file it would remove, and confirms by
TYPING THE DIRECTORY NAME — a destructive act gets a harder yes than 'yes'. The removal is then
COMMITTED: git is the record (`git log --all -- parts/<name>/` finds it,
`git checkout <rev> -- parts/<name>/` restores it whole); nothing is archived (the 2026-08-19
ruling).

Positional numbers, never ids: `view`/`delete` take the number `listing()` printed, which shifts
when a part is removed — /practice-list's stated contract.

## DEPENDENCIES
`roster` (scan, the marker, the tag rules), `seam`, `circle_close.MAX_MEMBERS`, and lazily
`identity` (Self's reserved names), `circle_state`, `atomic_write`, `gitrepo`.

## EXTERNAL FILES
Read: `parts/` (fresh scans). Written: `parts/<name>/long_term.md` + `part.toml` on add; a
directory removed and its deletion committed on delete.

## NETWORK ACCESS
None.

## BUGS
`delete()`'s confirmation reads `seam.read_line` directly; on the dual pane's no-circle door that
read answers "" at once, so the delete always cancels there — safe, but the message is
"cancelled" rather than "this surface cannot confirm". The interactive-refusal shape the dialogs
use would say it better.
