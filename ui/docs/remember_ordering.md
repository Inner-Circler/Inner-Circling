# REMEMBER_ORDERING.PY(1)

## NAME

remember_ordering.py — the ordering tool: a page, served to this machine's own browser, where Self
puts an entity's memories in order by hand and sidelines the ones no prompt block should carry.

## SYNOPSIS

    python ui/remember_ordering.py
    python ui/remember_ordering.py --port 8770 --no-browser
    python ui/remember_ordering.py --groups <a copy of groups/>
    /memory-edit                                   from the command pane, or circle.py --dev-cmd

`--port <n>`: the port the page is served on. Default: 8765; when that port is taken, the next
free one after it, and after twenty tries one the system picks. The address is printed either way.

`--no-browser`: print the address and do not open a browser. Default: off — the browser opens.

`--groups <dir>`: serve the groups under `<dir>` in place of this tree's own `groups/`. For
trying the tool on a copy. Default: this tree's `groups/`, the record itself.

`--at <group>[/<part>]`: the group, and the part, the page opens on — `ifs/self`, `ifs/child`.
Default: the default group, on Self.

`--with-parent`: stop when the program that started this one closes. The tool reads its
standard input until the end and shuts down then, so a pipe the starter holds and never writes
is enough. Default: off — Ctrl+C stops it.

Every `python` here is the venv's, as everywhere in this tree. Ctrl+C in the terminal stops the
tool; a saved ordering stays saved. The server reads its code once, at start: after the tree
moves under it, stop it and start it again.

**From the command pane: `/memory-edit`** (R588, 2026-10-03). The verb is on
the always-available surface, so it works in circling.py's command pane, in the Ticker's, and
as `circle.py --dev-cmd memory-edit`. It starts this program as its own process — never inside
the circling program, whose running circle the tool's group switching would pull the record
from under — with `--with-parent` on a pipe it holds, and `--at <group>/self` for the group
the program is on, and reports the address; the tool stops when that program does. A second
`/memory-edit` while it runs reopens the page. The tool's own output goes to the verb, never to
the terminal or the Ticker's window.

## DESCRIPTION

**What the page does.** Pick a GROUP — the default group is selected first — and one of its
parts, or Self, which is selected first and listed the same way. The entity's memories come up
in Self's saved ordering, the memory to keep longest at the top. Memories written since the last
save are unsorted: they sit above a divider, newest first, marked `new`, and the next save sorts
them in. With no ordering saved, the list is the newest-first one the prompt uses today.

    the switch    WRITTEN BY DREAMING — the memories dreaming wrote for the part (an id-bearing
                  record) — THE PART'S OWN WORDS — what it chose to remember in a circle (an
                  id-less one) — or BOTH. Written by dreaming is the default when the page
                  opens, and the setting is kept while the page is open, across parts. Each
                  choice shows its count. Under BOTH, while memories of both kinds are
                  carried, the carried list runs BY DATE, newest first (the operator,
                  2026-10-02): as the list a part opens with, and as an undoable change when
                  "both" is selected or a restore brings the second kind back. So an order
                  made by hand lives under one kind at a time; with one kind carried the saved
                  order stands.
    show          "Show sidelined" is a second switch, independent of the first: the sidelined
    sidelined     memories are listed too, in their place, each with Restore. Off whenever a
                  part loads.
    tick          a checkbox on each memory; Shift+click ticks a range; one box ticks them all.
    sideline      the ticked memories leave the list at once. They are KEPT on file, carried in
                  no prompt block, and still within the part's own `[recall: ...]`.
    drag          press on a memory's handle or its top line and drag: the ticked memories are
                  placed after the memory under the pointer when the button is released. A bar
                  under the page's head places them first. To top, To bottom and
                  Alt+Up/Alt+Down move them without dragging.
    undo, redo    every change to the list, in order (Ctrl+Z, Ctrl+Y). The switches are not
                  changes to the list and are not undone.
    save          writes the ordering (Ctrl+S) — see below.
    fold          a memory longer than two lines shows two, behind a twistie that unfolds the
                  whole of it. Every twistie closes when a list loads, on a sideline, a restore,
                  a re-order, an undo or a redo, and on a change of either switch.

**Save is what you see** (the operator, 2026-10-02). The list as shown, top to bottom, is the
ordering written; every memory on file that the page is not showing as carried — hidden by the
switch, or shown sidelined — is written sidelined. So under the default switch a save carries the
memories written by dreaming, in the order shown, and sidelines every one of the part's own
words; under "both" it carries what is listed. The page says this in its lead, and when the
switch is hiding memories the status line says how many a save would sideline. A memory the part
writes after the save is unsorted and rides its blocks until the next save.

**Nothing is reversed.** The list stays as it is at a save; the prompt reads it from the top until
its budget is spent. The two dividers are drawn in place, live: the line under the memories
written since the last save, and the cutoff where each target BLOCK's budget runs out.

**The estimate is the assembly's own answer.** Each memory carries `lands` or `cut` and the
BLOCK it is bound for — BLOCK 3 for a memory written before the part's last identity refresh,
BLOCK 4 for one written since. The page computes none of it. Every change, and every change of
the switch, sends this server the list exactly as a save would write it, and the server asks
`remember_prompt_projection.remember_window_read()`: the same split, the same arrangement and the
same budget cut the four-block assembly makes. So the estimate is of the save. It is an estimate
of the next circle only because a circle closing before then adds memories ahead of these and
moves the refresh.

**Self is listed and not projected.** No prompt block carries Self's own memories. For Self the
page orders and sidelines, saves, and shows no cutoff. The switch is the id rule, for Self as
for a part: the default group's Self shows, under the default switch, its six rows migrated from
self.md in 2026-08 (they carry ids), and a save there sidelines Self's own notes; a Self with no
id-bearing row — the band's, or a fresh install's — lists nothing, and the page says what the
switch is hiding and what a save would do.

**An ordering in the register's first shape** — saved by a tool started before the change of
2026-10-02: rows the other way, `rejected` for `sidelined` — is read as it was meant, the page
says so, and the next save writes the current shape.

**What a save writes.** One file, `remember_ordering.toml`, beside the `remember.toml` it orders
(`coordinator/remember_ordering_manager.py`). `remember.toml` is never written. The tool runs no
git: the next live close files every ordering with the circle. A save is safe at any time, an
open circle included — that circle's blocks were assembled when it opened, so the ordering applies
from the next one; the page says so when a circle may be open.

**A save made somewhere else is not overwritten.** The page sends the `saved` stamp it loaded. If
the file on disk carries another — a second window saved since — the save is refused and the page
offers to reload.

**An ordering file that does not read** is shown as no ordering, with the reason. A save is
refused rather than laid over it, and the page offers to remove the file.

**Local only.** The server binds 127.0.0.1. Every `/api` call must carry the token the served
page was given, and every request must be addressed to this machine by name (the Host header), so
another site open in the same browser can neither read the record through this server nor write
to it. The page is one file and loads nothing from the network.

### The constants

    PAGE         ui/remember_ordering.html — the page, read at each request for it.
    PORT         8765. The default port.
    PORT_TRIES   20. How many ports from --port upward are tried before the system picks one.
    BODY_MAX     2,000,000. Bytes a request body may carry.
    TOKEN_MARK   the placeholder in the page that the server replaces with this run's token.
    SELF_TAG     "Self" — the name Self is listed under.

**THE RATINGS — B149, R595, 2026-10-03.** Under each of a part's memories the page shows the
part's own ratings — its first, from the memory's row, and its latest blind re-rating with how
many there have been and whether the situation came back — and yours. "Rate" opens five
choices (the four valences on 0 to 1, courage on its five named steps, each "unrated" by
default) and "places it": whose rating would place the memory once anything steers on ratings.
Nothing does yet (D140), so the choice is recorded and read by nothing. "Save rating" adds one row
to the part's `self_rating.toml`, immediately and apart from the list's own Save; the part's
records are never touched, and no part ever reads yours. A value off the steps is refused (400).
Self's own memories are not rated here.

## MAIN

    read the command line: --port, --no-browser, --groups, --at, --with-parent.
    if (the page file is missing) then { say so; return 1 }
    if (--groups was given and is not a directory) then { say so; return 1 }
    if (--at was given and is not GROUP or GROUP/PART) then { say so; return 1 }
    bind the record modules to the groups to serve — remember_ordering_groups_bind():
        if (--groups was given) then { point record_paths.GROUPS_DIR at it }
        if (no group is installed there) then { exit, saying so }
        bind the default group, or the first one when none is marked default.
    build the server — remember_ordering_server_build(): 127.0.0.1 on --port, else the next free
        port, else one the system picks; a fresh random token.
    print the address — the first line, with --at's group and part on it, which /memory-edit
        reads — the record being ordered, and how to stop.
    if (--no-browser was not given) then {
        open the address in the browser;
        if (that fails) then { say the address must be opened by hand }
    }
    if (--with-parent) then { on a thread, read standard input to its end, then shut the server down }
    serve until interrupted or shut down; print "stopped", and why.
    close the server; return 0.

## DEPENDENCIES

`record_paths` (the groups on disk, the default group, `group_set()`); `part_roster` (a group's
seated parts); `remember_manager` (the records); `remember_ordering_manager` (the ordering: read,
write, clear, keys, who wrote a memory); `remember_prompt_projection` (`remember_window_read()` —
what lands); `part_mid_term_manager` (`part_mid_term_cutoff_read()` — the date that splits BLOCK 3
from BLOCK 4); `circle_state` (whether a circle may be open, for the page's note). Standard
library: `argparse`, `json`, `os`, `pathlib`, `secrets`, `sys`, `threading`, `webbrowser`,
`http.server`, `urllib.parse`. No third-party packages are named here; `part_mid_term_manager`
brings the transport it imports.

## EXTERNAL FILES

READ:

    ui/remember_ordering.html                        the page.
    groups/<group>/group.toml                        each group's display name and default mark.
    groups/<group>/parts/<part>/part.toml            the roster, through part_roster.
    groups/<group>/parts/<part>/remember.toml        the memories.
    groups/<group>/self/remember.toml
    groups/<group>/parts/<part>/rerate.toml          the part's re-ratings (B149).
    groups/<group>/parts/<part>/self_rating.toml     your own ratings (B149).
    groups/<group>/parts/<part>/mid_term.md          its first line only: when the part's
                                                     identity was last refreshed.
    groups/<group>/circles/, work/sandbox/circles/, work/logs/    through circle_state, to say
                                                     whether a circle may be open.

WRITTEN:

    groups/<group>/parts/<part>/remember_ordering.toml    on Save; removed by "Remove this part's
    groups/<group>/self/remember_ordering.toml            saved ordering".
    groups/<group>/parts/<part>/self_rating.toml          on "Save rating" — one row added,
                                                          none ever changed (B149).

Nothing else is written, and `remember.toml` and `rerate.toml` never.

## NETWORK ACCESS

Listens on 127.0.0.1 only. Makes no outgoing connection, and the page makes none beyond this
server.

## HUMAN I/O

Prints three lines to the terminal at start — the address, the record, how to stop — and
"stopped" at Ctrl+C. Everything else is the page.

## OPERATION

### The calls the page makes

    GET  /                  the page, with this run's token in it. No token needed to ask for it.
    GET  /api/groups        remember_ordering_groups_read()
    GET  /api/parts         remember_ordering_parts_read(group)
    GET  /api/memories      remember_ordering_view_read(group, part)
    POST /api/estimate      remember_ordering_estimate(group, part, order, sidelined)
    POST /api/save          remember_ordering_save(group, part, order, sidelined, base)
    POST /api/clear         remember_ordering_clear(group, part, base)
    POST /api/rate          remember_ordering_rate(group, part, key, ratings, steers)   (B149)

The server takes an ordering as two lists of keys — the carried, in order, and the sidelined — and
asks nothing about what the page showed. "Save is what you see" is the page's rule, defined once
there (`plan()`) and sent to the estimate and the save alike.

```
for every request {
    if (it is a POST) then { read its body first, up to BODY_MAX — so a refusal below reaches
                             the client as a reply, not as a reset of a connection with the
                             body still unread }
    if (the Host header is not 127.0.0.1:<port> or localhost:<port>) then { refuse, 403 }
    if (it is a call under /api/ and does not carry this run's token) then { refuse, 403 }
    if (it is a POST) then {
        if (its Content-Type is not JSON) then { refuse, 415 }
        if (its body was larger than BODY_MAX) then { refuse, 413 }
        if (its body does not parse as a JSON object) then { refuse, 400 }
    }
    run the call; a refusal it raises carries its own status; any other failure is a 500
    carrying the failure's name and text.
}
```

Every reply is marked no-store; the page is sent with a policy that allows no outside source.

### remember_ordering_groups_read()
Every group on disk, the default one first, each with its name, its display name and whether it
is the default.

### remember_ordering_parts_read(group)
Self, then the group's seated parts — a retired part is not listed. For each: its name and tag,
how many memories it has, how many of them dreaming wrote and how many are its own words, how
many are sidelined, how many are unsorted (none is reported for an entity with no ordering
saved), and when its ordering was saved.

### remember_ordering_view_read(group, part, working=None)
```
{
    bind the group; refuse a part the group does not seat (404).
    if (the entity is Self) then { it is not projected: no cutoff, no blocks }
    else { the cutoff is the part's last identity refresh, or none }
    ask remember_window_read() for every memory in list order, with its block and whether it
        lands — judged against `working` when the page sent its own list, else against the file.
    return the memories (key, id, date, circle, text, class, salience, chain, who wrote it —
        dreaming or own — what each costs its window, sorted, sidelined, block, lands), the two
        blocks' totals, the budget, the cutoff, when the ordering was saved, any reason the file
        did not read, whether it is in the register's first shape, and whether a circle may be
        open.
}
```

### remember_ordering_estimate(group, part, order, sidelined)
The view of the page's working list, with nothing written. `order` and `sidelined` must be lists
of keys; anything else is refused (400).

### remember_ordering_save(group, part, order, sidelined, base)
```
{
    if (the ordering on file does not read) then { refuse (409): nothing is written over it }
    if (the file's `saved` stamp is not `base`) then { refuse (409), returning the stamp on file }
    write the ordering — remember_ordering_manager.remember_ordering_write().
    return the fresh view, with `dropped`: the keys the register did not hold.
}
```

### remember_ordering_clear(group, part, base)
Removes the entity's ordering file and returns the fresh view. Refused like a save when `base` is
not the stamp on file.

### One group at a time
The record modules follow `record_paths.group_set()`, which is process-wide. Every call binds its
group and does its work inside one lock, so two requests for two groups cannot read each other's
record.

## BUGS

None found. Three limits, each deliberate.

The estimate is of the record as it stands. A circle that closes before the next one opens adds
memories ahead of these and moves the refresh date, so a memory shown as landing can be cut by
then.

The headless-browser half of the suite (`ui/tests/test_remember_ordering.py --browser`) is not
run by the commit hook, which has no browser to rely on; it is run by hand.

The tool commits nothing. Between a save and the next live close the ordering file is an
uncommitted change in the working tree.
