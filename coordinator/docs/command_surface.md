# COMMAND_SURFACE.PY(1)

## NAME
command_surface — the command pane's shared constants, the two command tables, and the one `dev_mode` flag

## SYNOPSIS
```
import command_surface as CS        # always attribute access for dev_mode
from command_surface import COMMANDS, KNOWN_CMDS, PANE_OF, USER_SUBSET_COMMANDS, ...
```
There is no `main()` and no command line. The module is a LEAF: it imports only `re` and
`identity`, so every reader — `circle.py`'s Self> loop, `help_system.py`, `commands.py`'s
dispatcher, `markers.py`'s classifier, `ui/circling.py`'s command pane — can import it without
an import cycle. Regenerated 2026-08-21 (B65) against the module as it stood after R285-R288.

## DESCRIPTION
One table, `COMMANDS`, is the single source every command surface derives from: `/help`'s
listing, the set of known verbs, which pane each verb belongs to, and the help hierarchy's
per-class verb rows. Two further tables split the verbs by audience — `USER_SUBSET_COMMANDS`,
visible and accepted at `cmd>` with dev off, and `DEV_SUBSET_COMMANDS`, which dev mode ADDS
(R266, narrowed by R288) — and a third, `PROPOSE_SUBSET_COMMANDS`, names what a part may put
inside `[proposed: …]` (R267). `_disjoint()` runs at import and refuses a tree in which these
tables contradict one another. `dev_mode` is the one module-global flag, rebound at runtime by
the command pane's unlisted `dev` verb, by `--dev` / `--dev-cmd` in `circle.py`, and by the
test suites; it must be read as `command_surface.dev_mode`, never copied by `from`-import.

The module's comments carry the rulings that shaped each table and are dated; this page
describes what the code does, not why — read the module for the why.

## MAIN
```
    (none — the module has no entry point)
    At import:
    {
        CONSOLE_NAME = identity.user_name()            the console display name (R132)
        COMMANDS, KNOWN_CMDS, PANE_OF are built          (see TABLES)
        DEV_MIN_CMDS, DEV_CMD_HEADS, USER_SUBSET_COMMANDS, DEV_SUBSET_COMMANDS,
        PROPOSE_SUBSET_COMMANDS, DEFERRED_PROPOSE_COMMANDS, PROPOSABLE_COMMANDS are defined
        _disjoint() runs                                 (see OPERATION)
        SYNONYMS, ISSUE_NODE_RE, dev_mode = False are defined
    }
```

## COMMAND-LINE ARGUMENTS
None.

## DEPENDENCIES
- `re` (standard library)
- `identity` (this project) — `user_name()` for `CONSOLE_NAME`

## EXTERNAL FILES
None read, none written. (`identity.user_name()` reads the environment / `.env` on its own
account.)

## NETWORK ACCESS
None.

## HUMAN I/O
None directly. The DESCRIPTION column of `COMMANDS` is human-facing text rendered by
`help_system.help_row()`; it says "issue", never "node" (R279).

## TABLES

### COMMANDS — `tuple[tuple[spec, description, pane], ...]`
One row per verb. `spec` is the verb as typed, with its argument shape (`/issue-status nNNNN
[= <value>]`); `description` is the whole help text, hard-wrapped for editing and re-flowed by
`help_system.help_row()`; `pane` is `"circle"` for `/round`, `/pass`, `/close` and `"command"`
for every other verb. There is NO `<text>` speech row since 2026-08-21 (R285): speech is
CIRCLE_DIALOG, not a COMMAND. `/dev` is deliberately not a row (R199, R286).

The rows, as of this page: `/issue-list`, `/issue-status`, `/issue-status-update`,
`/issue-label-update`, `/issue-relationship-add`, `/issue-evidence-add`,
`/issue-relationship-status`, `/issue-relationship-list`, `/issue-add`, `/issue-apply`,
`/prompt-show`, `/practice-add`, `/better-option-add`, `/practice-list`, `/better-option-list`,
`/practice-delete`, `/remember`, `/remember-list (also /recall)`, `/topic-list`, `/topic-close`,
`/propose-list`, `/round`, `/pass`, `/status`, `/issue-evidence-list`, `/help`, `/close`, `/abort`.

### KNOWN_CMDS, PANE_OF — derived from COMMANDS
`KNOWN_CMDS` is the ordered tuple of slash heads; `PANE_OF` maps head → pane. Neither can drift
from `COMMANDS` because both are computed from it at import.

### DEV_MIN_CMDS — `("/help", "/abort", "/status")`
Historical: the command-pane verbs that ran ahead of the dev gate; kept for the one text that
still names them.

### DEV_CMD_HEADS
Every head `commands.dispatch_dev_cmd()` handles with no circle open — the no-circle door's own
accepted set. Completed 2026-08-21 (18 heads). `test_proposals.py` asserts every entry is
really handled.

### USER_SUBSET_COMMANDS / DEV_SUBSET_COMMANDS — the two audiences (R266, R288)
```
USER  /issue-list /practice-add /practice-list /better-option-list /remember /remember-list
      /propose-list /issue-evidence-list /help /status /abort
DEV   /issue-status /issue-status-update /issue-label-update /issue-evidence-add
      /issue-relationship-add /issue-relationship-status /issue-relationship-list /issue-add
      /issue-apply /practice-delete /topic-list /topic-close /better-option-add /prompt-show
```
Disjoint by assertion. Dev off: the USER table is what `cmd>` accepts and `/help` lists; dev on:
the union. `dev` itself is in neither table.

### PROPOSE_SUBSET_COMMANDS, DEFERRED_PROPOSE_COMMANDS, PROPOSABLE_COMMANDS (R267)
What `[proposed: <command>]` may name. `DEFERRED_PROPOSE_COMMANDS` (`/issue-evidence-add`)
is ruled in and refused today — it resolves a statement number against a live transcript the
approval checkpoint has not got. `PROPOSABLE_COMMANDS` is the table minus the deferred: the set
`markers._propose_command_shape()` accepts and `/help` counts.

### SYNONYMS — `{"/recall": "/remember-list"}`
Accepted spellings that are not the name; applied by `normalise_head()` so every dispatcher
resolves them identically.

### ISSUE_NODE_RE — `^n\d{4}$`
The issue-id shape, shared by the marker grammar and the issue verbs.

### dev_mode — `False` at import
One flag, module-global, rebound at runtime. Read and write as `command_surface.dev_mode`.

## OPERATION

### _disjoint()
```
if (USER_SUBSET_COMMANDS and DEV_SUBSET_COMMANDS share any verb) then {
    raise AssertionError naming the overlap (R266)
}
if (any PROPOSE_SUBSET_COMMANDS verb is in neither USER nor DEV) then {
    raise AssertionError — PROPOSE ⊆ USER ∪ DEV (R267, narrowed from ⊆ USER by R288)
}
if (any DEFERRED_PROPOSE_COMMANDS verb is not in PROPOSE_SUBSET_COMMANDS) then {
    raise AssertionError — the deferred set subtracts from the proposable one
}
```
Runs at import, so a tree whose tables contradict one another fails to import at all.

### normalise_head(word) -> str
```
    strip whitespace
if (empty) then { return it unchanged }
if (no leading "/") then { prepend "/" }      R201 — the command pane does not require one
    lower-case; read "_" as "-"               the verb grammar has no underscore
    map through SYNONYMS                      /recall -> /remember-list
    return the head
```
Used by three dispatchers — `circle.py`'s Self> loop, `commands.dispatch_dev_cmd()`'s callers,
and `ui/circling.py`'s command pane and circle-pane guard — so one typo rule applies everywhere.

## BUGS
None known. One reader-facing subtlety, stated rather than hidden: `DEV_MIN_CMDS` and the
comment block above it describe a gate that no longer exists in that shape (a dev-table verb
typed with dev off is JUNK and answers with help since R285); nothing imports or reads
the tuple — it survives in prose only (`dev_restricted_text()`'s history, a `test_help_system.py`
docstring, `help_system.py`'s module docstring).
