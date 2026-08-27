# HELP_SYSTEM.PY(1)

## NAME
help_system — `/help`'s whole surface: the one row shape, the dev-tiered level 0, the
object-class hierarchy (hot-reloaded), the room's own help, and JUNK's answer

## SYNOPSIS
```
import help_system as HS
HS.help_text(arg)          the text /help <arg> prints (level 0 for arg == "")
HS.cmd_help(arg)           the same, emitted on the command channel
HS.junk_help(line)         "not a command: <line>" + level 0       (R285)
HS.circle_pane_help()      what the ROOM accepts — the Self> form of /help
HS.help_row(spec, desc)    one rendered row, shared with ui/circling.py
```
No `main()`, no command line. Generated 2026-08-21 (B65) against the module after the S5/S6
renderer rewrite and R280/R285/R287.

## DESCRIPTION
Every verb `/help` prints goes through ONE renderer, `help_row()`: `  <spec>  —  <whole
description>`, wrapped at `HELP_WIDTH` (80) with an `ROW_HANG` (8-space) hanging indent, the spec
never broken, the rows sorted by verb. Level 0 tiers by `command_surface.dev_mode` and never
refuses: dev off prints the room's three verbs plus the USER table; dev on prints every
COMMANDS row, then an OBJECT CLASSES summary, then the level-1 row `/help object_classes`. The
hierarchy — `/help object_classes` (level 1), `/help <class>` (2), `/help <class> list` (3),
`/help <class> read #` (4) — is dev-gated (R280) and refuses with `dev_restricted_text()`
while dev is off; its class table is read from `coordinator/object_classes.toml` and reparsed
only when that file's (mtime, size) changes; a class's VERBS are derived from COMMANDS by head
prefix, not read from the TOML. `circle_pane_help()` answers `/help` typed in the room with
only what the room accepts. `junk_help()` is what a `cmd>` line that is not a command gets
(R285).

## MAIN
```
    (none — the module has no entry point)
    At import:
    {
        OBJECT_CLASSES_PATH = <this directory>/object_classes.toml
        HELP_WIDTH = 80; ROW_HANG = 8
        LEVEL_ROWS, OBJECT_CLASS_PROVIDERS, _HELP_ONE_LINERS, _LEVEL1_ROW are defined
    }
```

## COMMAND-LINE ARGUMENTS
None.

## DEPENDENCIES
- `pathlib`, `re`, `textwrap`, `tomllib` (or `tomli` on Python < 3.11)
- `command_surface` (attribute access for `dev_mode`; `COMMANDS`, the two tables,
  `PROPOSABLE_COMMANDS`)
- `issue_commands` (`all_edges()` for the issue-relationship provider)
- `issue_schema` (`live_nodes()`, `load()`, `render()`, `unwrap()`, `nid_of()`)
- `seam` (`emit`, attribute access)

## EXTERNAL FILES
Read: `coordinator/object_classes.toml` (hot-reloaded — re-stat on every help call, reparsed
on change); `issues/*.toml` through `issue_schema` for the level-3/4 providers. Written: none.

## NETWORK ACCESS
None.

## HUMAN I/O
`cmd_help()` emits on the COMMAND channel; every other function returns text for a caller to
emit. The text says "issue"/"relation", never "node"/"edge" (R279), never names "dev mode"
(R199), and is at most `HELP_WIDTH` columns wide after `_wrap80()`.

## OPERATION

### _hot_load(path, cache, parse) -> object; object_classes() -> dict
```
    stat the file; key = (mtime_ns, size)
if (the cache's key differs) then { parse the TOML, store (key, parse(doc)) }
    return the cached parse
```
`object_classes()` applies this to OBJECT_CLASSES_PATH with `_parse_object_classes`
(name → class table). No polling; the check runs only when a help command does.

### help_row(spec, desc="") -> str
```
    join the description to ONE line (" ".join(desc.split()))
    protect the spec's spaces as NBSP so textwrap never breaks inside it
    wrap "<spec>  —  <desc>" at HELP_WIDTH: first line indented 2, continuations ROW_HANG
    restore the spaces; if wrapping produced nothing, return "  <spec>"
```
Nothing is truncated; a spec wider than the room overflows its own line (break_long_words off).
Public on purpose: `ui/circling.py` renders its own verbs through it.

### _head(spec), _command_specs() -> {head: (spec, desc)}
The first COMMANDS row per slash head, re-read on every call so a test that swaps COMMANDS is
seen.

### _gloss(head, specs) -> (spec, desc)
```
if (head in _HELP_ONE_LINERS) then { return (spec, the hand-written one-liner) }
else { return (spec, the COMMANDS description, or "(no description)") }
```
The four hand-written glosses are the room's three verbs and `/help`, whose COMMANDS text reads
relative to table order and would read wrong once sorted.

### _verb_rows(heads, specs) -> list[str]
One `help_row()` per distinct head, sorted.

### _class_of_head(head, classes) -> str | None
The LONGEST class name that prefixes the head (`/issue-relationship-add` → issue-relationship,
every other `/issue-*` → issue); None for a head no class prefixes.

### _class_verb_rows(name) -> list[str]
```
    for each COMMANDS head, sorted:
if (its class is not `name`) then { skip }
if (it is a DEV-table verb and dev is off) then { skip }
        append help_row(spec, desc)
```

### object_class_help_text(name="") -> str
```
if (no name) then {
if (the TOML holds no class) then { return the "not populated" sentence }
    return "  OBJECT CLASSES" + one "/help <class>  —  <description>" row per class   (level 1)
}
if (the class is unknown) then { return "unknown object class ... — known: ..." }
    return the class name, its description (one line), the two LEVEL_ROWS ("/help <class> list",
    "/help <class> read #"), then _class_verb_rows(name)                                (level 2)
```

### Providers: _issue_entries/_issue_read, _issue_relationship_entries/_issue_relationship_read
`issue`: (id, label) per live issue; read = the issue rendered by `issue_schema.render()`.
`issue-relationship`: ("<src> <type> <tgt>", type) per edge from `issue_commands.all_edges()`;
read = a Markdown record of that edge (status, dated, note, basis, why, notes, ask, quote,
retired). `OBJECT_CLASS_PROVIDERS` maps class → (entries, read).

### object_class_list_text(name) -> str
```
if (no provider) then { return "<name>: list not built yet" }
if (no entries) then { return "<name>: no live entries" }
    "<name> — N live", then one numbered row per entry, the key cut to the row's remaining budget
```

### object_class_read_text(name, pos_raw) -> str
```
if (no provider) then { "read not built yet" }
if (pos_raw is not an int) then { "read # must be a number — try /help <name> list first" }
if (no entries) then { "no live entries" }
if (pos out of 1..N) then { "<name> has N live entries — # must be 1-N" }
    return read(entry at pos) + blank line + object_class_help_text(name)
```
`#` is the position in the list AS IT WOULD PRINT NOW — never a stored id.

### _one_liner(cmd) -> str
The hand-written gloss if there is one, else the FIRST line of the COMMANDS description, else
"(no description)". Used by `circle_pane_help()` only.

### circle_pane_help() -> str
The room's own help: "IN THE ROOM you speak", the rows for `/round`, `/pass`, `/close`, `/help`,
the two annotations (`[remember: <text>]`, `[proposed: <command>]` naming the count of
`PROPOSABLE_COMMANDS`), the bracket rules, and one line pointing everything else at the command
pane. Never lists a command-pane verb.

### _help_level0() -> str
```
    "  COMMANDS"
if (dev is off) then {
    rows for ("/round", "/pass", "/close") + USER_SUBSET_COMMANDS, sorted; return
}
    rows for every COMMANDS head, sorted
if (the TOML holds classes) then {
    "  OBJECT CLASSES", then per class: help_row("/help <class>", "(N live) <first sentence> —
    its verbs, list and read #")
}
    blank line, then help_row(_LEVEL1_ROW)            "/help object_classes — the object classes; ..."
```
Neither tier names "dev mode".

### _wrap80(text, width=HELP_WIDTH) -> str
Line at a time: a line that fits is untouched; a longer one is re-wrapped with its continuation
hanging past its indent and any leading `-`/`*`/`#`/`N.` marker.

### help_text(arg="") -> str; _help_text_raw(arg)
```
    help_text = _wrap80(_help_text_raw(arg))
_help_text_raw:
if (arg == "") then { return _help_level0() }
if (arg == "object_classes") then {
if (dev off) then { return dev_restricted_text() } else { return object_class_help_text("") }
}
    cls = first word
if (cls names a class) then {
if (dev off) then { return dev_restricted_text() }
if (second word == "list") then { return object_class_list_text(cls) }
if (second word == "read" and a third word exists) then { return object_class_read_text(cls, it) }
if (only the class was given) then { return object_class_help_text(cls) }
    return "unrecognized: help '<arg>' — try /help <cls>, /help <cls> list, or /help <cls> read #"
}
    return "unrecognized: help '<arg>' — try /help or /help object_classes"
```

### cmd_help(arg) -> None
`seam.emit("command", help_text(arg.strip()))` — the `--dev-cmd help` and dispatcher door.

### junk_help(line) -> str
`"  not a command: <line>"` + `help_text("")` — what a `cmd>` line that is not a COMMAND in the
current dev state receives (R285); never names dev mode.

### dev_restricted_text() -> str
`"  not understood, see 'help'\n"` — the refusal for the dev-gated HIERARCHY only (R280). A
dev-table VERB typed with dev off is JUNK and gets `junk_help()` instead.

## BUGS
None known. `DEV_MIN_CMDS` is still imported nowhere here but named in the module docstring's
history; harmless.
