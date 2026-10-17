#!/usr/bin/env python3
"""
remember_ordering.py — THE ORDERING TOOL: a page, served to this machine's own browser, where
Self puts an entity's memories in order by hand and sidelines the ones no prompt block should
carry.

    python ui/remember_ordering.py                  serve the page and open it
    /memory-edit                                    the same, from the command pane of circling.py
                                                    or the Ticker, or `circle.py --dev-cmd`: the
                                                    tool starts as its own process beside that
                                                    one, on the active group's Self record, and
                                                    stops when that program does (R588)
    /issue-graph                                    the same program, from the same doors, opened
                                                    on its other page: the active group's issue
                                                    graph, at /issue-graph?group=<name>. Each
                                                    page links to the other.

    --port <n>       the port to serve on. Default: 8765; when that is taken, the next free one.
    --no-browser     print the address and do not open a browser. Default: the browser opens.
    --groups <dir>   serve the groups under <dir> in place of this tree's own groups/ — a COPY
                     to try the tool on. Default: this tree's groups/, the record itself.
    --at <group>[/<part>]   the group, and the part, the page opens on. Default: the default
                     group, on Self.
    --with-parent    stop when the program that started this one closes — standard input is read
                     until its end, so a pipe from the starter is enough. Default: off; Ctrl+C
                     stops it.

WHAT THE PAGE DOES (ui/remember_ordering.html). Pick a GROUP and one of its parts — or Self, whose
memories it lists the same way. The memories come up in Self's saved ordering, most kept first,
the ones written since the last save on top under a divider, newest first; the cutoff each target
BLOCK's budget sets is drawn where it falls, live, as the list changes. A SWITCH shows the
memories "written by dreaming" (the default), "the part's own words", or both; "Show sidelined"
is a second, independent switch. Tick memories; SIDELINE them (kept on file, carried in no
block, still within recall); DRAG the ticked ones to follow the memory under the pointer at
release; undo and redo; SAVE.

SAVE IS WHAT YOU SEE (the operator, 2026-10-02). The list as shown, top to bottom, is the
ordering written; every memory on file that the page is NOT showing as carried — hidden by the
switch, or shown sidelined — is written sidelined. So under the default switch a save carries the
memories written by dreaming and sidelines every one of the part's own words. Nothing is
reversed, at a save or anywhere: the prompt reads the list from its top until the budget is
spent.

WHAT THIS FILE IS. The page's server and nothing more. It holds no rule of its own:

    the ordering on file            remember_ordering_manager.py   (its one reader and writer)
    who wrote a memory              remember_ordering_manager.remember_ordering_origin()
    which memories land, and where  remember_prompt_projection.remember_window_read() — the same
                                    split, order and budget cut the four-block assembly makes
    the cutoff between BLOCK 3/4    part_mid_term_manager.part_mid_term_cutoff_read()

so what the page calls an estimate is the assembly's own arithmetic, run now — and the page
sends it the list exactly as a save would write it, so the estimate is of the save. The server
takes an ordering as two lists of keys and asks nothing about what the page showed: WYSIWYG is
the page's rule, defined once there (plan()). SELF IS LISTED AND NOT PROJECTED: no prompt block
carries Self's own memories, so for Self the page orders and sidelines and shows no cutoff.

IT WRITES TWO KINDS OF FILE — remember_ordering.toml, beside the remember.toml it orders, and
self_rating.toml, Self's own rating of a part's memory (B149) — and never remember.toml itself.
EVERY SAVE FILES ITSELF IN GIT (the operator, 2026-10-08: a close never leaves state unfiled, and
neither does this tool): one pathspec commit of the one file written, through the close's own
helper, which declines without failing the save where there is no git, no repository or no
identity. The page says when a save was written but not filed; the next live close files
whatever a save could not (transcript_store.circle_commit_paths). A save is safe at any time, an
open circle included; that circle's blocks were assembled when it opened, so the ordering
applies from the next one.

LOCAL ONLY. Bound to 127.0.0.1. Every /api call must carry the token the served page was given,
and every request must be addressed to this machine by name (the Host header), so another site
open in the same browser can neither read the record through this server nor write to it. The
page loads nothing from the network.

ONE GROUP AT A TIME, UNDER A LOCK. The record modules follow record_paths.group_set(), which is
process-wide; every request binds its group and does its work inside one lock.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "coordinator"))
sys.path.insert(0, str(ROOT / "memory"))

import record_paths as RP                                # noqa: E402
RP.system_dependencies_ensure()       # B141: name the interpreter, not a traceback
import circle_state as CS                                # noqa: E402
import part_roster as R                                  # noqa: E402
import remember_manager as RM                            # noqa: E402
import remember_ordering_manager as ROM                  # noqa: E402
import remember_prompt_projection as RPP                 # noqa: E402
import part_mid_term_manager as MT                       # noqa: E402
import initialization_form as IF                         # noqa: E402  the forms page

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PAGE = HERE / "remember_ordering.html"
PORT = 8765
PORT_TRIES = 20          # how many ports past --port are tried before the system picks one
BODY_MAX = 2_000_000     # bytes a request body may carry — an ordering is a list of keys
TOKEN_MARK = "%%ORDERING_TOKEN%%"
SELF_TAG = "Self"

_LOCK = threading.RLock()


class OrderingRefusal(Exception):
    """A request this server will not carry out, with the HTTP status that says why."""

    def __init__(self, status: int, message: str, **extra):
        super().__init__(message)
        self.status = status
        self.extra = extra


# ------------------------------------------------------------------ the record
def _bind(group: str) -> None:
    """Point the record modules at `group`. Callers hold _LOCK."""
    if group not in RP.group_present_read():
        raise OrderingRefusal(404, f"no group named {group!r}")
    if RP.group_read() != group:
        RP.group_set(group)


def _entities() -> list[tuple[str, str]]:
    """(name, tag) for Self and every part seated in the bound group. A retired part is not
    listed: it reaches no prompt."""
    return [(RM.SELF, SELF_TAG)] + [(d, t) for d, t in R.ROSTER]


def remember_ordering_groups_read() -> list[dict]:
    """Every group on disk, the default one first: {name, display, default}."""
    default = RP.group_default_read()
    names = RP.group_present_read()
    if default in names:
        names = [default] + [n for n in names if n != default]
    return [{"name": n, "display": str(RP.group_descriptor_read(n).get("display") or n),
             "default": n == default} for n in names]


def remember_ordering_parts_read(group: str) -> list[dict]:
    """Self, then the group's parts: {name, tag, memories, dreaming, own, sidelined, unsorted,
    saved}. `unsorted` is None for an entity with no ordering saved — nothing there is sorted
    yet."""
    with _LOCK:
        _bind(group)
        out = []
        for name, tag in _entities():
            records = RM.remember_read(name)
            keys = ROM.remember_ordering_keys_read(records)
            st = ROM.remember_ordering_read(name)
            placed = set(st["order"])
            dreaming = sum(1 for r in records if ROM.remember_ordering_origin(r) == ROM.DREAMING)
            out.append({"name": name, "tag": tag, "memories": len(keys),
                        "dreaming": dreaming, "own": len(keys) - dreaming,
                        "sidelined": sum(1 for k in keys if k in st["sidelined"]),
                        "unsorted": (sum(1 for k in keys if k not in placed)
                                     if st["saved"] else None),
                        "saved": st["saved"]})
        return out


def remember_ordering_view_read(group: str, part: str, working: "dict | None" = None) -> dict:
    """Everything the page shows for one entity: its memories in list order, each with its
    target block and whether it lands, the two blocks' totals, the budget and the cutoff.

    `working` is the page's own list before it is saved, in remember_ordering_read()'s shape;
    the estimate is then made of IT and nothing is written. Self is not projected: `blocks` is
    empty and every memory's `block` and `lands` are None."""
    with _LOCK:
        _bind(group)
        tags = dict(_entities())
        if part not in tags:
            raise OrderingRefusal(404, f"no part named {part!r} in group {group!r}")
        projected = part != RM.SELF
        cutoff = MT.part_mid_term_cutoff_read(part) if projected else None
        saved = ROM.remember_ordering_read(part)
        w = RPP.remember_window_read(part, cutoff, ordering=working)
        # B149 (R595): the part's own ratings and Self's, for Self's eyes — a part never reads
        # this view, so showing them here costs the blind asking nothing.
        rated = RM.remember_ratings_by_memory_read(part) if projected else {}
        memories = []
        for row in w["rows"]:
            r = row["record"]
            memories.append({
                "ratings": rated.get(r.get("id") or row["key"]),
                "key": row["key"], "id": r.get("id"), "date": r.get("date"),
                "circle": r.get("circle"), "text": str(r.get("text", "")),
                "class": r.get("class"), "salience": r.get("salience"), "chain": r.get("chain"),
                "origin": ROM.remember_ordering_origin(r),
                "chars": row["chars"], "sorted": row["sorted"], "sidelined": row["sidelined"],
                "block": row["block"] if projected else None,
                "lands": row["lands"] if projected else None})
        try:
            circle_open = bool(CS.circle_is_in_progress())
        except Exception:                                        # noqa: BLE001
            circle_open = True
        return {"group": group, "part": part, "tag": tags[part], "projected": projected,
                "saved": saved["saved"], "error": saved["error"], "legacy": saved["legacy"],
                "budget": w["budget"],
                "cutoff": cutoff, "circle_open": circle_open,
                "blocks": ({str(n): b for n, b in w["blocks"].items()} if projected else {}),
                "memories": memories}


def _keys(value, what: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(k, str) for k in value):
        raise OrderingRefusal(400, f"`{what}` must be a list of memory keys")
    return value


def remember_ordering_estimate(group: str, part: str, order, sidelined) -> dict:
    """The view of a WORKING list — `order` top to bottom, most kept first, and the keys
    sidelined in it — with nothing written."""
    working = {"order": _keys(order, "order"),
               "sidelined": {k: "unsaved" for k in _keys(sidelined, "sidelined")}}
    return remember_ordering_view_read(group, part, working=working)


def remember_ordering_file(path: "pathlib.Path | list[pathlib.Path]", message: str) -> dict:
    """File what a save wrote in git — one path, or one save's paths as one commit — and say
    what happened; never fail the save over it.

    A close never leaves the record unfiled, and neither does a save here (the operator, 2026-10-08:
    "Either mark files for .gitignore or commit them"). The commit is the close's own helper,
    gitrepo.system_git_paths_commit: only this path, never `add -A`; it warns and declines where
    there is no git binary, no repository, or no identity yet, and this function turns ANY other
    failure (a held index.lock while a close is committing, a hook that refuses) into the same
    answer. The file is written either way; what the next live close files is whatever a save
    could not (transcript_store.circle_commit_paths).

    Returns {"filed": True | False | None, "note": str}. None: the path is not under this tree
    (the suite's temporary groups), so there was nothing to file and git was not asked."""
    inside = []
    for p in (path if isinstance(path, list) else [path]):
        try:
            pathlib.Path(p).resolve().relative_to(ROOT)
            inside.append(pathlib.Path(p))
        except ValueError:
            pass
    if not inside:
        return {"filed": None, "note": ""}
    lines: list[str] = []

    def log(kind: str, msg: str) -> None:
        if kind in ("warn", "fail", "note"):
            lines.append(msg)
    try:
        import gitrepo as G
        done = bool(G.system_git_paths_commit(inside, message, log))
    except Exception as e:                                       # noqa: BLE001
        done = False
        lines.append(f"git could not file it ({type(e).__name__}: {e})")
    return {"filed": done, "note": " ".join(lines)[:600]}


def remember_ordering_save(group: str, part: str, order, sidelined, base) -> dict:
    """Write one entity's ordering and return its fresh view, with `dropped`: the keys the
    register did not hold.

    `base` is the `saved` stamp the page loaded. When the file on disk carries another, someone
    else saved since — a second window — and the save is REFUSED (409) rather than laid over it."""
    order, sidelined = _keys(order, "order"), _keys(sidelined, "sidelined")
    with _LOCK:
        _bind(group)
        if part not in dict(_entities()):
            raise OrderingRefusal(404, f"no part named {part!r} in group {group!r}")
        now = ROM.remember_ordering_read(part)
        if now["error"]:
            raise OrderingRefusal(409, f"the ordering on file does not read ({now['error']}); "
                                       f"nothing was written over it")
        if now["saved"] != base:
            raise OrderingRefusal(409, "this ordering was saved somewhere else since it was "
                                       "loaded here — reload to see it", saved=now["saved"])
        done = ROM.remember_ordering_write(part, order, sidelined)
        view = remember_ordering_view_read(group, part)
        view["dropped"] = done["dropped"]
        view.update(remember_ordering_file(done["path"], f"memory tool: {part}'s ordering saved"))
        return view


def remember_ordering_rate(group: str, part: str, key, ratings, steers) -> dict:
    """Self's own rating of one memory (B149, R595): appended to the part's self_rating.toml,
    never over the part's own. `ratings` is {member: detent or ""}; "" leaves that member unrated.
    Returns the memory's fresh ratings, as the view carries them."""
    if not isinstance(key, str) or not key:
        raise OrderingRefusal(400, "`key` names the memory being rated")
    if not isinstance(ratings, dict):
        raise OrderingRefusal(400, "`ratings` is an object of member: value")
    clean: dict = {}
    for k, v in ratings.items():
        if k not in RM.RATING_FIELDS:
            raise OrderingRefusal(400, f"{k!r} is not a rated member")
        if v in ("", None):
            continue
        allowed = RM.COURAGE_DETENTS if k == "courage" else RM.AROUSAL_DETENTS
        if str(v) not in allowed:
            raise OrderingRefusal(400, f"{k} takes one of {', '.join(allowed)}, not {v!r}")
        clean[k] = str(v)
    steers = steers or "part"
    if steers not in RM.SELF_RATING_STEERS:
        raise OrderingRefusal(400, f"`steers` is one of {', '.join(RM.SELF_RATING_STEERS)}")
    with _LOCK:
        _bind(group)
        if part not in dict(_entities()) or part == RM.SELF:
            raise OrderingRefusal(404, f"no part named {part!r} in group {group!r} to rate")
        records = RM.remember_read(part)
        keys = dict(zip(ROM.remember_ordering_keys_read(records), records))
        if key not in keys:
            raise OrderingRefusal(404, f"no memory {key!r} on file for {part}")
        memory = keys[key].get("id") or key
        RM.remember_self_rating_write(part, memory, clean, steers)
        out = {"key": key, "ratings": RM.remember_ratings_by_memory_read(part).get(memory)}
        out.update(remember_ordering_file(RM.remember_self_rating_path_read(part),
                                          f"memory tool: Self rated a memory of {part}"))
        return out


def remember_ordering_clear(group: str, part: str, base) -> dict:
    """Remove one entity's ordering — every memory unsorted again, none sidelined — and return
    its fresh view. Refused like a save when `base` is not what is on file."""
    with _LOCK:
        _bind(group)
        if part not in dict(_entities()):
            raise OrderingRefusal(404, f"no part named {part!r} in group {group!r}")
        now = ROM.remember_ordering_read(part)
        if now["saved"] != base and not now["error"]:
            raise OrderingRefusal(409, "this ordering was saved somewhere else since it was "
                                       "loaded here — reload to see it", saved=now["saved"])
        ROM.remember_ordering_clear(part)
        view = remember_ordering_view_read(group, part)
        view.update(remember_ordering_file(ROM.remember_ordering_locate(part),
                                           f"memory tool: {part}'s ordering cleared"))
        return view


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------------ the issue graph
# THE ISSUE GRAPH IS SERVED HERE TOO, so the two pages reach each other: a browser will not
# follow a link from this server's page to a file on disk, so the picture ui/issue_draw.py
# writes into work/graph/ is read and handed out by this process, with a link back to the
# memory page set into its header. /issue-graph starts this program for that page alone.
#
# The picture is redrawn first when the group's issues/ moved since it was drawn — the same
# `--if-stale` run a live close makes, as its own process, so a slow layout never holds _LOCK.
ISSUE_DRAW = HERE / "issue_draw.py"
ISSUE_GRAPH_MARK = "<header><h1>Issue graph</h1>"
_TREE_GROUPS = RP.GROUPS_DIR          # before --groups can rebind it


def remember_ordering_issue_graph_read(group: str) -> str:
    """The issue graph page for `group`, redrawn if its issues moved, with a link back to the
    memory page on that group's Self. Refused for a --groups copy: issue_draw.py runs as its own
    process on this tree's own groups, and would draw a copy's issues over the real picture."""
    import subprocess
    if pathlib.Path(RP.GROUPS_DIR).resolve() != pathlib.Path(_TREE_GROUPS).resolve():
        raise OrderingRefusal(409, "the issue graph is drawn for this tree's own groups only — "
                                   "this run of the tool serves a copy (--groups)")
    with _LOCK:
        _bind(group)
        issues = RP.group_tree(group) / "issues"
        import issue_draw as ID
        ID.issue_draw_out_bind(issues)
        page = pathlib.Path(ID.OUT_HTML)
    back = (f'<p style="margin:.3rem 0"><a href="/#{group}/self">Memory tool</a> — this '
            f'group&#39;s memories, and your own</p>')
    if not issues.is_dir() or not any(p.suffix == ".toml" for p in issues.iterdir()):
        return (f"<!doctype html><meta charset=utf-8><title>Issue graph</title>{ISSUE_GRAPH_MARK}"
                f"</header>{back}<p>No issue is on file for this group yet, so there is nothing "
                f"to draw.</p>")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}
    # stdin=DEVNULL IS LOAD-BEARING: under --with-parent this process's standard input is a pipe
    # a thread is blocked reading, and on Windows a child that inherits that handle hangs at
    # its start, holding the page open for ever (measured 2026-10-03).
    run = subprocess.run([sys.executable, str(ISSUE_DRAW), f"{issues}/", "--if-stale"],
                         cwd=str(ROOT), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                         encoding="utf-8",
                         errors="replace", **flags)
    if run.returncode != 0 or not page.is_file():
        tail = (run.stderr or run.stdout or "").strip().splitlines()[-1:] or ["no output"]
        raise OrderingRefusal(500, f"the issue graph could not be drawn ({tail[0]})")
    html = page.read_text(encoding="utf-8")
    if ISSUE_GRAPH_MARK in html:
        html = html.replace(ISSUE_GRAPH_MARK, ISSUE_GRAPH_MARK + back, 1)
    return html


# ------------------------------------------------------------------ the initialization forms
# THE FORMS PAGE IS SERVED HERE TOO (ui/initialization_form.py, its page initialization_form.html):
# a group's descriptor and a part's record, each one form. The functions there hold no lock and
# bind no group; these do, as every other call here does, and file what a save wrote in git.
def _initialization_group_read(group: str) -> dict:
    with _LOCK:
        if group:
            _bind(group)
        return IF.group_initialization_read(group)


def _initialization_group_save(group: str, new, record) -> dict:
    with _LOCK:
        if not new:
            _bind(group)
        out = IF.group_initialization_save(group, record or {}, new=bool(new))
        if bool(new):
            RP.group_set(out["group"])                    # the record modules follow the new group
        wrote = out.pop("wrote")
    filed = (remember_ordering_file(wrote, f"group-initialization: {out['group']}")
             if wrote else {"filed": None, "note": ""})
    return {**out, **filed}


def _initialization_part_read(group: str, part: str) -> dict:
    with _LOCK:
        _bind(group)
        R.part_roster_rebind()
        return IF.part_initialization_read(group, part)


def _initialization_part_save(group: str, part: str, body: dict) -> dict:
    with _LOCK:
        _bind(group)
        R.part_roster_rebind()
        out = IF.part_initialization_save(group, part, body)
        if not part:
            R.part_roster_rebind()                        # the new part joins the roster now
        wrote = out.pop("wrote")
    filed = (remember_ordering_file(wrote, f"part-initialization: {group}/{out['part']}")
             if wrote else {"filed": None, "note": ""})
    return {**out, **filed}


def _initialization_part_retire(group: str, part: str, body: dict) -> dict:
    with _LOCK:
        _bind(group)
        R.part_roster_rebind()
        out = IF.part_initialization_retire(group, part, body.get("confirm", ""), body.get("why", ""))
        R.part_roster_rebind()                            # the retired part leaves the roster now
        wrote = out.pop("wrote")
    return {**out, **remember_ordering_file(wrote, f"part-retire: {part}")}


# ------------------------------------------------------------------ the server
class OrderingHandler(BaseHTTPRequestHandler):
    # HTTP/1.0, the base class's own default: one request per connection, so nothing of one
    # request can sit in front of the next. A POST's body is read before any refusal, bounded by
    # BODY_MAX — see _body_read().
    server_version = "remember-ordering"

    def log_message(self, fmt, *args):       # the page's own status line is the log
        pass

    # ---- the two checks every request passes
    def _host_ok(self) -> bool:
        host = (self.headers.get("Host") or "").strip().lower()
        port = self.server.server_address[1]
        return host in (f"127.0.0.1:{port}", f"localhost:{port}")

    def _token_ok(self) -> bool:
        return secrets.compare_digest(self.headers.get("X-Ordering-Token") or "",
                                      self.server.token)

    # ---- replies
    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if ctype.startswith("text/html"):
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "script-src 'unsafe-inline'; connect-src 'self'; img-src data:; "
                             "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, obj) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _run(self, fn) -> None:
        """Call `fn` and send what it returns; a refusal carries its own status."""
        try:
            self._json(200, fn())
        except (OrderingRefusal, IF.InitializationRefusal) as e:
            self._json(e.status, {"error": str(e), **e.extra})
        except Exception as e:                                   # noqa: BLE001
            self._json(500, {"error": f"{type(e).__name__}: {e}"})

    # ---- GET
    def do_GET(self):                                            # noqa: N802
        if not self._host_ok():
            return self._json(403, {"error": "this server answers only to this machine"})
        url = urlsplit(self.path)
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        if url.path in ("/", "/index.html"):
            try:
                page = PAGE.read_text(encoding="utf-8").replace(TOKEN_MARK, self.server.token)
            except OSError as e:
                return self._send(500, f"the page is missing: {e}".encode("utf-8"),
                                  "text/plain; charset=utf-8")
            return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
        if url.path == "/initialization":
            try:
                page = IF.PAGE.read_text(encoding="utf-8").replace(TOKEN_MARK, self.server.token)
            except OSError as e:
                return self._send(500, f"the page is missing: {e}".encode("utf-8"),
                                  "text/plain; charset=utf-8")
            return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
        if url.path == "/issue-graph":
            group = q.get("group") or RP.group_default_read()
            try:
                page = remember_ordering_issue_graph_read(group)
            except OrderingRefusal as e:
                return self._send(e.status, f"<!doctype html><meta charset=utf-8><p>{_esc(str(e))}"
                                            f"</p><p><a href=\"/\">Memory tool</a></p>".encode("utf-8"),
                                  "text/html; charset=utf-8")
            except Exception as e:                               # noqa: BLE001
                return self._send(500, f"the issue graph failed: {type(e).__name__}: {e}"
                                  .encode("utf-8"), "text/plain; charset=utf-8")
            return self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
        if not url.path.startswith("/api/"):
            return self._json(404, {"error": "no such page"})
        if not self._token_ok():
            return self._json(403, {"error": "this page was opened by another run of the tool "
                                             "— reload it"})
        if url.path == "/api/groups":
            return self._run(remember_ordering_groups_read)
        if url.path == "/api/parts":
            return self._run(lambda: remember_ordering_parts_read(q.get("group", "")))
        if url.path == "/api/group-initialization":
            return self._run(lambda: _initialization_group_read(q.get("group", "")))
        if url.path == "/api/part-initialization":
            return self._run(lambda: _initialization_part_read(q.get("group", ""),
                                                               q.get("part", "")))
        if url.path == "/api/memories":
            return self._run(lambda: remember_ordering_view_read(q.get("group", ""),
                                                                 q.get("part", "")))
        return self._json(404, {"error": "no such call"})

    # ---- POST
    def _body_read(self) -> "bytes | None":
        """The request body, or None when it is too large to take (or its length unreadable).
        A refusal READS THE BODY FIRST: a reply sent and the connection closed with the body
        still unread arrives at the client as a reset — on Windows, a ConnectionAbortedError in
        place of the 403 — and the suite's own refusal checks met that race."""
        try:
            size = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if size < 0 or size > BODY_MAX:
            return None
        return self.rfile.read(size)

    def do_POST(self):                                           # noqa: N802
        raw = self._body_read()
        if not self._host_ok():
            return self._json(403, {"error": "this server answers only to this machine"})
        if not self._token_ok():
            return self._json(403, {"error": "this page was opened by another run of the tool "
                                             "— reload it"})
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._json(415, {"error": "a call's body is JSON"})
        if raw is None:
            return self._json(413, {"error": "the request body is too large"})
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(body, dict):
                raise ValueError("not an object")
        except ValueError as e:
            return self._json(400, {"error": f"the request body is not JSON: {e}"})
        group, part = str(body.get("group", "")), str(body.get("part", ""))
        path = urlsplit(self.path).path
        if path == "/api/estimate":
            return self._run(lambda: remember_ordering_estimate(
                group, part, body.get("order"), body.get("sidelined")))
        if path == "/api/save":
            return self._run(lambda: remember_ordering_save(
                group, part, body.get("order"), body.get("sidelined"), body.get("base")))
        if path == "/api/clear":
            return self._run(lambda: remember_ordering_clear(group, part, body.get("base")))
        if path == "/api/group-initialization":
            return self._run(lambda: _initialization_group_save(group, body.get("new"),
                                                                body.get("record")))
        if path == "/api/part-initialization":
            return self._run(lambda: _initialization_part_save(group, part, body))
        if path == "/api/part-retire":
            return self._run(lambda: _initialization_part_retire(group, part, body))
        if path == "/api/rate":
            return self._run(lambda: remember_ordering_rate(
                group, part, body.get("key"), body.get("ratings"), body.get("steers")))
        return self._json(404, {"error": "no such call"})


class OrderingServer(ThreadingHTTPServer):
    daemon_threads = True
    # http.server asks for address reuse, and on Windows that lets a SECOND run bind the port a
    # first run is still serving — two tools on one address, each answering some requests. Off
    # there, so a taken port is refused and the next one is tried.
    allow_reuse_address = os.name != "nt"
    token = ""


def remember_ordering_server_build(port: int = PORT, tries: int = PORT_TRIES) -> OrderingServer:
    """A server bound to 127.0.0.1 — on `port`, or the next free one within `tries`, or one the
    system picks — carrying a fresh token. The caller serves it and closes it."""
    last: "OSError | None" = None
    for candidate in ([port + i for i in range(max(1, tries))] if port else []) + [0]:
        try:
            server = OrderingServer(("127.0.0.1", candidate), OrderingHandler)
        except OSError as e:
            last = e
            continue
        server.token = secrets.token_urlsafe(24)
        return server
    raise last if last else OSError("no port could be bound")


def remember_ordering_groups_bind(groups_dir: "pathlib.Path | None") -> None:
    """Serve the groups under `groups_dir` in place of this tree's own (--groups): rebind
    record_paths.GROUPS_DIR, then bind its default group so every record module follows."""
    if groups_dir is not None:
        RP.GROUPS_DIR = pathlib.Path(groups_dir).resolve()
    names = RP.group_present_read()
    if not names:
        raise SystemExit(f"  no group is installed under {RP.GROUPS_DIR} — a group is a folder "
                         f"carrying group.toml")
    default = RP.group_default_read()
    RP.group_set(default if default in names else names[0])


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="remember_ordering.py",
        description="Order an entity's memories by hand, and sideline the ones no prompt block "
                    "should carry, in this machine's own browser.")
    ap.add_argument("--port", type=int, default=PORT,
                    help=f"the port to serve on. Default: {PORT}; when that is taken, the next "
                         f"free one.")
    ap.add_argument("--no-browser", action="store_true",
                    help="print the address and do not open a browser. Default: the browser "
                         "opens.")
    ap.add_argument("--groups", type=pathlib.Path, default=None, metavar="DIR",
                    help="serve the groups under DIR in place of this tree's own — a copy to "
                         "try the tool on. Default: this tree's groups/, the record itself.")
    ap.add_argument("--at", default=None, metavar="GROUP[/PART]",
                    help="the group, and the part, the page opens on — `ifs/self`, `ifs/child`. "
                         "Default: the default group, on Self.")
    ap.add_argument("--with-parent", action="store_true",
                    help="stop when the program that started this one closes: this one reads its "
                         "standard input until the end and stops then, so a pipe from the "
                         "starter is enough (the /memory-edit verb starts it this way). "
                         "Default: off — Ctrl+C stops it.")
    a = ap.parse_args()
    if not PAGE.is_file():
        print(f"  the page is missing: {PAGE}")
        return 1
    if a.groups is not None and not a.groups.is_dir():
        print(f"  --groups: {a.groups} is not a directory")
        return 1
    at = (a.at or "").strip().strip("/")
    if at and not re.fullmatch(r"[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)?", at):
        print(f"  --at: {a.at!r} is not GROUP or GROUP/PART")
        return 1
    remember_ordering_groups_bind(a.groups)
    server = remember_ordering_server_build(a.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/" + (f"#{at}" if at else "")
    print(f"  the ordering tool is at {url}", flush=True)       # the first line: /memory-edit reads it
    print(f"  the record it orders: {RP.GROUPS_DIR}")
    print(f"  the initialization forms: http://127.0.0.1:{server.server_address[1]}/initialization")
    print("  Ctrl+C here stops it. A saved ordering stays saved." if not a.with_parent
          else "  It stops with the program that started it. A saved ordering stays saved.", flush=True)
    if not a.no_browser:
        try:
            webbrowser.open(url)
        except Exception:                                        # noqa: BLE001
            print("  (no browser could be opened — open the address above by hand)")
    if a.with_parent:
        # The starter holds the other end of standard input and never writes; when it closes —
        # quits, or is killed — the read returns empty and the server is shut down from here.
        def _watch() -> None:
            try:
                while sys.stdin.readline():
                    pass
            except Exception:                                    # noqa: BLE001
                pass
            server.shutdown()
        threading.Thread(target=_watch, name="with-parent", daemon=True).start()
    try:
        server.serve_forever()
        print("\n  stopped — the program that started it closed")
    except KeyboardInterrupt:
        print("\n  stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
