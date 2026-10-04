# REMEMBER_ORDERING_MANAGER.PY(1)

## NAME

remember_ordering_manager.py — the REMEMBER_ORDERING register: Self's ordering of one entity's
memories, and the memories Self sidelined. Its one reader and its one writer.

## SYNOPSIS

    python coordinator/remember_ordering_manager.py --part <part>     what is saved, most kept first

`--part <name>`: the entity whose ordering is listed — a part's folder name, or `self`. Required;
there is no default, and without it the program prints a usage line and exits 1.

(As a library: `remember_ordering_read(part)`, `remember_ordering_kept_read(part)`,
`remember_ordering_write(part, order, sidelined)`, `remember_ordering_clear(part)`,
`remember_ordering_keys_read(records)`, `remember_ordering_origin(record)`. The writer's one
caller is the ordering tool, `ui/remember_ordering.py`.)

## DESCRIPTION

A part's memories are shown to it in a window with a character budget. Left alone, the window is
newest first and the eldest fall out. This register is the manual alternative: Self puts an
entity's memories in order by hand and sidelines the ones no prompt block should carry.

**One file beside each remember.toml** — `parts/<part>/remember_ordering.toml` and
`self/remember_ordering.toml` — written by the ordering tool and by nothing else. One row per memory
Self has placed:

    key        the memory's own handle in remember.toml: its `id` when it has one, else its
               `date`, a microsecond stamp.
    sidelined  when Self sidelined it, UTC ISO; absent on a memory that is carried.

**The rows run most kept first.** The tool shows the memory to keep longest at the top, and a
save writes that list in that order — the order a prompt reads them in until its budget is
spent. Nothing is reversed anywhere (the operator, 2026-10-02: "the list should not be reversed
upon save"); `remember_ordering_read()` returns `order` in the same direction.

**A memory the file does not name is unsorted.** It was written after the last save. The
projection (`remember_prompt_projection._arrange()`) places unsorted memories ahead of every
ordered one, newest first, by the rule that has always applied. A part with no file at all is
therefore windowed exactly as it was before this register existed.

**A sidelined memory is kept, carried in no block, and still within recall.** It stays in
`remember.toml`, whole. It is left out of both memory windows, of the open-time recall pack and
of the distillate's sources — every path into a prompt BLOCK. It stays in the corpus a part's own
`[recall: mine ...]` searches: recall serves the record a part's blocks do not carry, and a
sidelined memory is exactly that. It still counts in the window header's "on file" and
"omitted", and keeps its number in Self's `/remember-list`. (That a sidelined memory does not
feed the identity distillate was ruled, R587: "(a) per recommendation.")

**Two writers, told apart by the id.** `remember_manager.py`'s own rule: a DREAMING-authored
record carries a Coordinator-minted `MEM-` id, a live `[remember: ...]` stays id-less. The tool's
switch between "written by dreaming" and "the part's own words" is that distinction and no other —
`remember_ordering_origin(record)` returns `DREAMING` ("dreaming") for an id-bearing record and
`OWN` ("own") for an id-less one. Self's six rows migrated from `self.md` in 2026-08 carry ids
too, and so sit with the dreaming-written: a model wrote them between circles. A row carrying a
`class` (`lands`, `better_option`) is id-less and sits with the own words.

**remember.toml is never written here.** The tool runs in its own process, and `remember.toml` is
appended to by an open circle and rewritten under the register gate at every close. Keeping the
ordering in its own file leaves that register with the one writer it has always had; a fault in
this file can cost an ordering and never a memory.

**The reader never raises.** Block assembly, the distillate's sources and the open-time pack ask
this module which memories are sidelined, and none of them may fail over this file. A file that
does not read is reported as no ordering, with the reason in `error` for the tool to show. The
corruption gate (`memory/record_verify.py`) is what refuses a circle open over a file that does
not parse.

### The constants

    FILE       "remember_ordering.toml" — the file's name, beside remember.toml.
    REGISTER   "remember_ordering" — the `register` value the file carries.
    TABLE      "ordering" — the table the rows are under.
    ORDER      ("key", "sidelined") — a row's fields, in the order they are written.
    PREAMBLE   the `[doc] preamble` every save writes: what the file is, in a sentence or two.
    DREAMING   "dreaming" — remember_ordering_origin()'s word for an id-bearing record.
    OWN        "own" — its word for an id-less one.
    FIRST_SHAPE_FIELD   "rejected" — the stamp's name in the register's first shape, read as
               `sidelined` (below).

The field was `rejected`, and the rows ran the other way, for the first evening of the register
(2026-10-02) before the operator named the state; the two files saved under that shape were
rewritten in place, stamps kept. **A file still in that first shape is read as what it meant**
— its preamble says "reversed", or a row carries `rejected` (`FIRST_SHAPE_FIELD`): the rows are
turned back, `rejected` reads as `sidelined`, and the result is flagged `legacy` for the tool to
say so; the next save writes the current shape. Read as the current shape it would have meant
the opposite order and nothing sidelined, with every gate green — and a tool started before the
change writes that shape until it is restarted.

## MAIN

    read the command line.
    if (--part is absent, or has no value) then {
        print "--part <name> required (a part's folder name, or self)"; return 1
    }
    read that entity's ordering — remember_ordering_read().
    if (the file did not read) then {
        print its path and the reason; return 1
    }
    if (nothing is saved) then {
        print "no ordering saved for <part> — its window is newest first"; return 0
    }
    read the entity's remember records and key them.
    print one summary line: how many are ordered, how many sidelined, how many unsorted, and when
        the ordering was saved.
    for each ordered key, most kept first {
        print its position — or the word "sidelined" — who wrote it (dreaming / own), its key,
        and the first 60 characters of its memory; a key the register no longer holds prints
        "(not in the register)".
    }
    return 0

## DEPENDENCIES

`REGISTER_CLASS` (`register_read`, `register_write`, `register_now`) for the file's parse, its
validated atomic write and the save stamp; `remember_manager` for `remember_read()` and
`_real_path()`, which is how the file is found beside its register. `pathlib`, `sys`. No
third-party packages.

## EXTERNAL FILES

    parts/<part>/remember_ordering.toml   READ by every reader; WRITTEN by remember_ordering_write();
    self/remember_ordering.toml           REMOVED by remember_ordering_clear(). In the group this
                                          process is bound to. Always the real tree: a dry-run
                                          circle reads the same file a live one does.
    parts/<part>/remember.toml            READ ONLY — to key the records, to refuse a key the
    self/remember.toml                    register does not hold, and to return the kept records.

## NETWORK ACCESS

None.

## HUMAN I/O

Prints to stdout; reads no input.

## OPERATION

### remember_ordering_key(record) / remember_ordering_keys_read(records)
```
{
    a record's key is its `id` when it has one, else its `date`.
    walk the records in the order given, counting each key;
    if (a key has been seen before) then { that record's key is "<key>#<n>" }
    return the keys in the same order.
}
```
File order is what makes a repeated key stable: the register only grows, so the second record to
carry a key is always the same one. No register on file repeats a key (measured 2026-10-02 over
204 records); the suffix is what keeps that from being an assumption.

### remember_ordering_origin(record)
`DREAMING` when the record carries an `id`, else `OWN`.

### remember_ordering_locate(part)
The file's path: beside that entity's `remember.toml`, under `parts/<part>/` or `self/`.

### remember_ordering_read(part) / remember_ordering_file_read(path)
```
if (the file is absent) then { return nothing saved, nothing ordered, nothing sidelined, no error }
try {
    parse the file; keep the rows that are tables carrying a `key`.
    if (the preamble says "reversed", or a row carries `rejected`) then {
        it is the first shape: turn the rows back, and read `rejected` as `sidelined`; legacy = true
    }
    order     = the rows' keys in that order (most kept first), a key named twice kept once;
    sidelined = { key: stamp } for every row carrying the stamp;
    return { saved, order, sidelined, error: none, legacy }
} on any failure {
    return nothing saved, nothing ordered, nothing sidelined, and the failure as `error`
}
```
`remember_ordering_file_read()` is the same by path, for a reader that holds a record directory
rather than an entity's name.

### remember_ordering_kept_read(part)
```
{
    read the entity's remember records, in file order.
    if (nothing is sidelined) then { return them all }
    else { return the ones whose key is not sidelined, still in file order }
}
```
What every path that carries a memory into a prompt BLOCK reads in place of
`remember_manager.remember_read()`. The recall corpus does not read this: it reads the register
whole.

### remember_ordering_write(part, order, sidelined, now=None)
```
{
    `order` is the tool's list top to bottom, most kept first; `sidelined` names the sidelined keys.
    for each key in `order` {
        if (the register does not hold it) then { drop it, and report it }
        else if (it has not been placed yet) then { place it }
    }
    for each key in `sidelined` {
        if (the register does not hold it) then { drop it, and report it }
        else {
            its stamp is the one already on file, or this save's time when it is newly sidelined;
            if (`order` did not place it) then { place it last — the least-kept end }
        }
    }
    build the rows from the placed keys in that order, each carrying `sidelined` when it is.
    write { register, saved, [doc] preamble, the rows } through REGISTER_CLASS.register_write(),
        which round-trips the text before an atomic replace.
    return { saved, order, sidelined, dropped, path }
}
```

### remember_ordering_clear(part)
Removes the file. Every memory is unsorted again, none is sidelined, and the window is the
newest-first one. Returns whether there was a file to remove.

## BUGS

None found. Two things that read as omissions and are not. A save writes the whole list, so a
memory Self never touched is placed too, where it stood — that is what makes "unsorted" mean
"written since the last save" and nothing else. And nothing here asks whether a circle is open:
the file is read when a circle's blocks are assembled, at its open, so a save made during a
circle applies from the next one and disturbs nothing in the one that is running.
