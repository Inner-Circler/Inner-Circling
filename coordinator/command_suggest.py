#!/usr/bin/env python3
"""
command_suggest.py — RECOGNISE the coordinator actions a circle's prose suggests. REPORT ONLY.

    python coordinator/command_suggest.py --ot <OT> [--group <name>] [--json]
    python coordinator/command_suggest.py --file <transcript.md> [--out <report.json>] [--json]

The operator, 2026-09-15: *"I'd like for this system to identify possible coordinator actions
across all classes. Identification does not mean execution; it means discriminating across and
among the classes, understanding their roles and methods, and recognising prose that suggests
the use of those methods."* Put three ways to land a recognised action, he chose the report:
*"lets go with B, I want to see what it finds."* (the ruling is R569).

WHAT IT IS. One model call over a closed circle's transcript with the COMMAND SURFACE as its
catalogue — every verb that WRITES, with the description /help shows for it; the reads, the
circle controls and the installation's own tooling (settings, redaction aliases, groups) are
left out (command_suggest_catalogue_read). The reply is a JSON list: for each place the prose
suggests an operation, the verb, the line exactly as Self would type it, who said it and in
which statement, the words that suggested it, and a confidence. The report prints those lines
numbered and writes work/logs/command_suggest_<OT>.json beside the circle's other reports.
THE REFERENTS travel with the transcript (2026-09-15, the operator's second question): the
live issues with their labels, the open relationships and topics, the observations, practices
and parts numbered as their own list verbs number them — read only, so an id or a list number
in a line is the real one, and a placeholder survives only where nothing matched.

WHAT IT IS NOT. Nothing here is executed: no dialog fires and no act is taken. At a LIVE close
alone (R570, 2026-09-15) each line is also STAGED as a pending proposal with its
dependency — command_suggest_stage() — and it happens only if Self approves it at a checkpoint.
A hand run and the --file rehearsal stage nothing; their lines are what Self MAY type at cmd>.
The call is not captured (R412/R413 admit the /close calls that WRITE the record; this one
writes none), and it never blocks a close: inter_circle.py runs it after SYNTHESIS inside its
own try, and a failure is one warning line.

THE OCCASION. In a fresh install's circle (2026-09-15_0945) the room discovered and named a
part, Self said "I wish to add the part", and nothing created it: the verb is Self's alone
(R483), parts are not told it, and the record carried the intent into six registers without
one line saying `/part-add`. This is the line.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "memory"))

import command_surface as CS                                        # noqa: E402
import record_paths as _RP                                          # noqa: E402
import setting_manager as SET                                       # noqa: E402

ROOT = _RP.ROOT

# THE CEILING. The first run at AUX_MAX_TOKENS (4,000) stopped at max_tokens before one
# visible character — the model's thinking bills against the same number (the lesson
# part_dreaming.py records from 2026-08-21). At 12,000 the referents rehearsal was cut mid-array
# after twenty objects: the reasoning over 22 verbs, a full transcript and the referents is
# long, and the visible JSON is ~150 tokens an item. 32,000 costs nothing until produced;
# the `suggest_max_tokens` setting overrides it.
SUGGEST_MAX_TOKENS = SET.setting_value_read("suggest_max_tokens", 32000)

# ------------------------------------------------------------------ the catalogue
# A verb is in the catalogue when a person could be moved to type it by what was SAID.
# Reads show a register; controls move the circle; the tooling classes configure the
# installation. None of those is suggested by prose about the person's life.
READ_METHODS = frozenset({"list", "view", "show"})
CONTROL_HEADS = frozenset({"/round", "/pass", "/close", "/abort", "/status", "/help"})
TOOLING_CLASSES = frozenset({"settings", "redact-alias", "group", "prompt"})
# `/issue-status-update` is `/issue-status ... = <value>` spelled as a verb — one catalogue
# row, the property form. `/issue-apply` replays a file of rulings; prose never asks for it.
DUPLICATE_HEADS = frozenset({"/issue-status-update", "/issue-apply"})
CONFIDENCES = ("high", "medium", "low")


def _head(form: str) -> str:
    return form.split()[0]


def _class_of(head: str, classes: dict) -> str:
    """The ruled object class a head belongs to — help_system's own rule, the LONGEST
    class name that prefixes the head (`/issue-relationship-add` is issue-relationship,
    `/issue-add` is issue). A head no ruled class prefixes is its own first word."""
    best = None
    for cname in classes:
        if head == f"/{cname}" or head.startswith(f"/{cname}-"):
            if best is None or len(cname) > len(best):
                best = cname
    return best or head.lstrip("/").split("-", 1)[0]


def _method_of(head: str) -> str:
    word = head.lstrip("/")
    return word.rsplit("-", 1)[1] if "-" in word else ""


def command_suggest_classes_read() -> dict:
    """The ruled object classes (coordinator/object_classes.toml, help_system's reader):
    name -> its row, whose `description` is the class's role in the person's own words."""
    import help_system as HS
    return HS.object_classes()


def command_suggest_catalogue_read() -> list[dict]:
    """The write-class verbs of the COMMAND surface, in COMMANDS' own order: `head`, `form`
    (the usage line /help shows), `cls` (the ruled class), `description`. Derived from the
    command surface and the class table, never a second list."""
    classes = command_suggest_classes_read()
    out: list[dict] = []
    for form, desc, _pane in CS.COMMANDS:
        head = _head(form)
        if head in CONTROL_HEADS or head in DUPLICATE_HEADS:
            continue
        cls, method = _class_of(head, classes), _method_of(head)
        if method in READ_METHODS or cls in TOOLING_CLASSES:
            continue
        out.append({"head": head, "form": form.replace("\n", " "), "cls": cls,
                    "description": " ".join(desc.split())})
    return out


# ------------------------------------------------------------------ the referents
# WHAT A PLACEHOLDER CAN RESOLVE TO — the operator, 2026-09-15, of nNNNN, <id> and <n> in the
# first report: "would they be resolved in a circle context, or does that need more work?"
# READ ONLY, and read the way each register's own list verb reads it, so a number here is
# the number that verb prints: /practice-list's, /observation-list's, /part-list's. Those
# numbers are POSITIONAL and shift when a row goes; the report says when it read them.
REFERENT_HEAD = 120      # characters of a text shown beside its id — enough to match on


def _head_text(s: str, n: int = REFERENT_HEAD) -> str:
    flat = " ".join(str(s or "").split())
    return flat if len(flat) <= n else flat[:n - 1] + "…"


def command_suggest_referents_read() -> dict:
    """Every referent a line's argument could name, from the LIVE registers of the bound
    group — writes nothing. Each register is read in its own try: a fresh install's
    missing register is an empty list and a note, never a refusal."""
    out: dict = {"issues": [], "relationships": [], "topics": [], "observations": [],
                 "practices": [], "better_options": [], "parts": [], "notes": []}
    try:
        import issue_index as II
        g = II.issue_index_read()
        for nid in sorted(g):
            d = g[nid]
            out["issues"].append({"id": nid, "label": d.get("label", nid),
                                  "status": d.get("status", "")})
            for typ, tgt, st in d.get("edges", []):
                if st == "open":
                    out["relationships"].append({"source": nid, "type": typ, "target": tgt})
    except Exception as e:                                       # noqa: BLE001
        out["notes"].append(f"issues not read ({type(e).__name__}: {e})")
    try:
        import topic_manager as TOP
        for t in TOP.topic_open_read():
            out["topics"].append({"id": t.get("id", ""), "text": _head_text(t.get("text"))})
    except Exception as e:                                       # noqa: BLE001
        out["notes"].append(f"topics not read ({type(e).__name__}: {e})")
    try:
        import circle_observation_manager as CO
        shown = [r for r in CO.circle_observation_read() if not r.get("retired")]
        for n, r in enumerate(shown, 1):
            out["observations"].append({"n": n, "id": r.get("id", ""),
                                        "text": _head_text(r.get("text"))})
    except Exception as e:                                       # noqa: BLE001
        out["notes"].append(f"observations not read ({type(e).__name__}: {e})")
    try:
        import practice_manager as PM
        rows = PM.practice_read()
        pr = [p for p in rows if p.get("addressee") != PM.BETTER_OPTION_ADDRESSEE]
        bo = [p for p in rows if p.get("addressee") == PM.BETTER_OPTION_ADDRESSEE]
        for n, p in enumerate(pr, 1):
            out["practices"].append({"n": n, "id": p.get("id", ""),
                                     "text": _head_text(p.get("title"))})
        for n, p in enumerate(bo, 1):
            out["better_options"].append({"n": n, "id": p.get("id", ""),
                                          "text": _head_text(p.get("title"))})
    except Exception as e:                                       # noqa: BLE001
        out["notes"].append(f"practices not read ({type(e).__name__}: {e})")
    try:
        import part_add as PA
        for n, (d, tag) in enumerate(PA.part_rows_read(), 1):
            out["parts"].append({"n": n, "tag": tag, "dir": d})
    except Exception as e:                                       # noqa: BLE001
        out["notes"].append(f"parts not read ({type(e).__name__}: {e})")
    return out


def command_suggest_referents_render(ref: dict) -> str:
    """The REFERENTS section of the user message — one line per referent, the id or list
    number first, then what a person would recognise it by."""
    out = ["REFERENTS — what an id or list number in a line must resolve to. Read from the "
           "live registers at the time of this call; a list number is positional."]
    out.append("issues (id, status, label):")
    out += [f"  {i['id']}  {i['status']}  {i['label']}" for i in ref.get("issues", [])] or ["  (none)"]
    out.append("issue-relationships (source type target), open:")
    out += [f"  {r['source']} {r['type']} {r['target']}"
            for r in ref.get("relationships", [])] or ["  (none)"]
    out.append("topics (TP- id, text), open:")
    out += [f"  {t['id']}  {t['text']}" for t in ref.get("topics", [])] or ["  (none)"]
    out.append("observations (/observation-list number, id, text):")
    out += [f"  {o['n']}. {o['id']}  {o['text']}"
            for o in ref.get("observations", [])] or ["  (none)"]
    out.append("practices (/practice-list number, id, text):")
    out += [f"  {p['n']}. {p['id']}  {p['text']}"
            for p in ref.get("practices", [])] or ["  (none)"]
    out.append("better options (/better-option-list number, id, text):")
    out += [f"  {p['n']}. {p['id']}  {p['text']}"
            for p in ref.get("better_options", [])] or ["  (none)"]
    out.append("parts (/part-list number, Tag):")
    out += [f"  {p['n']}. {p['tag']}" for p in ref.get("parts", [])] or ["  (none)"]
    for n in ref.get("notes", []):
        out.append(f"  note: {n}")
    return "\n".join(out)


def command_suggest_referents_counts(ref: dict) -> dict:
    return {k: len(v) for k, v in ref.items() if isinstance(v, list) and k != "notes"}


# ------------------------------------------------------------------ the prompt
SYSTEM_HEAD = """\
You read the transcript of one Inner Circling session — an IFS inner circle: Self (the person)
and named parts of that person speaking in turn. Your one job is RECOGNITION: find every place
where what was SAID suggests an operation the coordinator can perform, and name the operation.

You do not perform anything. Nothing you name is executed or staged. The report you produce is
read by Self, who may or may not type a line from it.

THE CATALOGUE below is the whole set of operations, one per line: the form Self would type,
then what it does. Discriminate among them — the class (issue, part, practice, remember,
observation, topic, propose ...) and the method (add, update, retire, close ...). A statement
can suggest more than one; most suggest none. Prefer precision: a suggestion should quote the
words that carry it.

CATALOGUE
"""

SYSTEM_TAIL = """
OUTPUT. A JSON array and nothing else. One object per suggestion:
  {"verb": "<head exactly as in the catalogue, e.g. /part-add>",
   "line": "<the full command line as Self would type it, arguments filled from the prose>",
   "speaker": "<who said the words>",
   "statement": <the statement number from the transcript>,
   "quote": "<the words, verbatim, that suggest it — short>",
   "confidence": "high" | "medium" | "low",
   "why": "<one sentence: which words map to which argument>",
   "depends_on": <the 1-based position IN THIS ARRAY of an earlier item that must happen first
                  — a relationship to an issue this same array adds, say — or null>,
   "token": "<the placeholder in `line` that item's result fills, e.g. nMMMM, or empty>"}
Order the array so an item comes after anything it depends on.
Rules for `line`: use the catalogue's own form; quote string arguments with straight double
quotes. Where the form takes an id or a list number (nNNNN, TP-nnnn, <id>, <n>), RESOLVE it
against the REFERENTS section that follows the transcript: the issue whose label the prose
names, the topic or observation whose text it echoes, the practice or part by its list
number. Say in `why` which referent you matched and by what words. Keep the placeholder as
written ONLY when no referent matches, and say so. A verb not in the catalogue is never named.
An empty array is a correct answer when nothing was suggested.
"""


def command_suggest_system_render(catalogue: list[dict] | None = None,
                                  classes: dict | None = None) -> str:
    """The catalogue BY CLASS: the class's ruled description (its role), then each of its
    verbs with the description /help shows (its methods)."""
    cat = catalogue if catalogue is not None else command_suggest_catalogue_read()
    cls_rows = classes if classes is not None else command_suggest_classes_read()
    out: list[str] = []
    seen: list[str] = []
    for c in cat:
        if c["cls"] not in seen:
            seen.append(c["cls"])
    for cls in seen:
        role = " ".join(str(cls_rows.get(cls, {}).get("description", "")).split())
        out.append(f"CLASS {cls}" + (f" — {role}" if role else ""))
        for c in cat:
            if c["cls"] == cls:
                out.append(f"  {c['form']}\n      {c['description']}")
        out.append("")
    return SYSTEM_HEAD + "\n".join(out) + SYSTEM_TAIL


def command_suggest_user_render(transcript: list[dict], topic: str = "",
                                referents: dict | None = None) -> str:
    """The numbered statements — the numbering /issue-evidence-list shows, so a `statement`
    in the reply is the number Self can cite — then the REFERENTS section when given."""
    import commands as CMD
    lines = [f"TOPIC: {topic}", ""] if topic else []
    for n, (_i, e) in enumerate(CMD.statement_read(transcript), 1):
        flat = " ".join(e["text"].split())
        lines.append(f"{n}. [{e['display']}]: {flat}")
    if referents is not None:
        lines += ["", command_suggest_referents_render(referents)]
    return "\n".join(lines)


# ------------------------------------------------------------------ the reply
def _array_salvage(s: str, tries: int = 200) -> list | None:
    """`s` starts at the array's `[` and was cut short. Close it after the last complete
    object that makes the whole parse: walk the `}` positions from the end, at most
    `tries` of them. None when not even one object is whole."""
    pos = len(s)
    for _ in range(tries):
        pos = s.rfind("}", 0, pos)
        if pos < 0:
            return None
        try:
            got = json.loads(s[:pos + 1] + "]")
        except ValueError:
            continue
        return got if isinstance(got, list) else None
    return None


def command_suggest_reply_parse(text: str, catalogue: list[dict]
                                ) -> tuple[list[dict], list[str]]:
    """(suggestions, notes). FAILS OPEN: an unparseable reply is no suggestions and one
    note; an object naming a verb outside the catalogue, or missing its verb or line, is
    dropped with a note. Everything kept is shaped to the seven keys."""
    heads = {c["head"] for c in catalogue}
    notes: list[str] = []
    s = text.strip()
    a, b = s.find("["), s.rfind("]")
    if a < 0:
        return [], ["reply carried no JSON array — nothing recognised"]
    raw = None
    if b > a:
        try:
            raw = json.loads(s[a:b + 1])
        except ValueError:
            raw = None
    if raw is None:
        # A TRUNCATED ARRAY IS SALVAGED, not discarded: the second rehearsal (2026-09-15)
        # stopped at max_tokens mid-object with twenty complete objects before the cut.
        # Everything up to the last complete object is kept, and the note says so.
        raw = _array_salvage(s[a:])
        if raw is None:
            return [], ["reply's JSON did not parse and no complete item could be salvaged "
                        "— nothing recognised"]
        notes.append(f"reply's array was cut short — {len(raw)} complete item(s) kept, "
                     f"the rest lost; raise suggest_max_tokens")
    if not isinstance(raw, list):
        return [], ["reply's JSON was not an array — nothing recognised"]
    out: list[dict] = []
    for i, o in enumerate(raw, 1):
        if not isinstance(o, dict):
            notes.append(f"item {i}: not an object — dropped")
            continue
        verb = str(o.get("verb", "")).strip()
        line = str(o.get("line", "")).strip()
        if verb not in heads:
            notes.append(f"item {i}: verb {verb!r} is not in the catalogue — dropped")
            continue
        if not line.startswith(verb):
            notes.append(f"item {i}: line does not start with its verb {verb} — dropped")
            continue
        conf = str(o.get("confidence", "low")).strip().lower()
        if conf not in CONFIDENCES:
            conf = "low"
        stmt = o.get("statement")
        try:
            stmt = int(stmt) if stmt is not None else None
        except (TypeError, ValueError):
            stmt = None
        dep = o.get("depends_on")
        try:
            dep = int(dep) if dep not in (None, "", "null") else None
        except (TypeError, ValueError):
            dep = None
        if dep is not None and not 1 <= dep < i:
            notes.append(f"item {i}: depends_on {dep} is not an earlier item — ignored")
            dep = None
        out.append({"item": i, "verb": verb, "line": line,
                    "speaker": str(o.get("speaker", "")).strip(),
                    "statement": stmt,
                    "quote": " ".join(str(o.get("quote", "")).split()),
                    "confidence": conf,
                    "why": " ".join(str(o.get("why", "")).split()),
                    "depends_on": dep,
                    "token": str(o.get("token", "") or "").strip()})
    return out, notes


# ------------------------------------------------------------------ derive
def command_suggest_derive(transcript: list[dict], topic: str = "", *,
                           client=None, referents: dict | None = None) -> dict:
    """ONE model call. {"suggestions", "notes", "truncated", "catalogue", "referents"} — the
    catalogue the call was given and the referent counts, so a report can say what was in
    scope. `referents` None means the live registers (command_suggest_referents_read); a
    rehearsal against a dialog that is not this tree's passes its own."""
    import llm_client as LC
    cat = command_suggest_catalogue_read()
    if referents is None:
        referents = command_suggest_referents_read()
    system = command_suggest_system_render(cat)
    user = command_suggest_user_render(transcript, topic, referents)
    # NOT RECORDED: R412/R413 admit the /close calls that write the record; this writes
    # none. `kind` labels the retry ladder only.
    reply = LC.stream_call_once(system, user, SUGGEST_MAX_TOKENS, kind="suggest",
                                client=client, record=False)
    text = reply.text
    notes: list[str] = []
    truncated = bool(getattr(reply, "truncated", False))
    if truncated:
        notes.append("reply stopped at max_tokens — the list may be incomplete")
    found, parse_notes = command_suggest_reply_parse(text, cat)
    return {"suggestions": found, "notes": notes + parse_notes + referents.get("notes", []),
            "truncated": truncated, "catalogue": [c["head"] for c in cat],
            "referents": command_suggest_referents_counts(referents),
            "raw": text}


# ------------------------------------------------------------------ report
def command_suggest_report_render(ot: str, result: dict) -> str:
    """The report Self reads: numbered lines, each what would be typed, then its warrant."""
    found = result.get("suggestions", [])
    counts = result.get("referents", {})
    head = ("staged for your ruling — see below" if "staged" in result
            else "REPORT ONLY, nothing staged")
    lines = [f"  command suggestions for {ot} — {head} "
             f"({len(found)} found; {len(result.get('catalogue', []))} verbs in scope"
             + (f"; referents read: {', '.join(f'{k} {v}' for k, v in counts.items())}"
                if counts else "") + ")"]
    for n, s in enumerate(found, 1):
        who = s.get("speaker") or "?"
        st = s.get("statement")
        where = f"{who}, statement {st}" if st else who
        lines.append(f"  {n:3}. {s['line']}")
        lines.append(f"       {s['confidence']} — {where}: \"{s.get('quote', '')}\"")
        if s.get("why"):
            lines.append(f"       {s['why']}")
    for note in result.get("notes", []):
        lines.append(f"  note: {note}")
    if not found:
        lines.append("  (nothing recognised)")
    return "\n".join(lines)


def command_suggest_report_write(path: pathlib.Path, ot: str, result: dict) -> None:
    doc = {"ot": ot, "written_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "report_only": "staged" not in result,         # False once a close staged its lines
           "catalogue": result.get("catalogue", []),
           "referents": result.get("referents", {}),
           "suggestions": result.get("suggestions", []),
           "notes": result.get("notes", []),
           "truncated": result.get("truncated", False)}
    if not doc["suggestions"] and doc["notes"]:
        # nothing kept: the head of what came back, so a misfire can be read
        doc["raw_head"] = str(result.get("raw", ""))[:2000]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")


def command_suggest_report_locate(ot: str) -> pathlib.Path:
    return ROOT / "work" / "logs" / f"command_suggest_{ot}.json"


# ------------------------------------------------------------------ staging
# R570, 2026-09-15: *"build the whole thing"* — each recognised line also becomes
# a pending proposal, carrying its dependency, for the next checkpoint. The report stays.
_POSITIONAL_HANDLES = {"/practice-delete": ("practices", "id"),
                       "/practice-update": ("practices", "id"),
                       "/part-retire": ("parts", "dir")}


def _stable_handles(verb: str, line: str, referents: dict) -> str:
    """A list number is positional and shifts when a row goes; staging writes the stable handle
    the referents give for it — a practice's BP- id, a part's directory — and the executor
    resolves that back to the list's number at approval."""
    spec = _POSITIONAL_HANDLES.get(verb)
    toks = line.split(None, 2)
    if spec is None or len(toks) < 2 or not toks[1].isdecimal():
        return line
    table, key = spec
    hit = next((str(r.get(key, "")) for r in referents.get(table, [])
                if r.get("n") == int(toks[1]) and r.get(key)), "")
    return " ".join([toks[0], hit] + toks[2:]) if hit else line


def command_suggest_stage(result: dict, ot: str, referents: dict,
                          typed: list[str] | None = None) -> list[str]:
    """Stage the report's lines as pending proposals. Marks each suggestion with `staged` (its
    P- id, new or already pending), `duplicate_of` (the item it repeats) or `not_staged` (why).
    Returns the distinct ids staged.

      /propose-add X   is a request to stage X, so X is the line staged
      /part-add        staged only from Self's own words — a part proposing a part is R483's
      duplicates       one row for a line said twice (a part asks, Self confirms)
      list numbers     staged as the stable handle (_stable_handles)
      kind             "command" when the part classifier admits the line whole, else
                       "suggestion" when proposal_suggestion.py can run the verb, else not staged
      depends_on       the staged id of the item it depends on, with the token its id fills;
                       a line whose token waits on an item that was not staged is not staged
      placeholders     a line holding one that no dependency fills is not staged
      already ruled    a line this circle already ruled — a row of this circle no longer
                       pending, or a command Self typed in the room (`typed`) — is not staged
    A ring or a missing prior is refused by the register; the suggestion says why."""
    import annotations as MK
    import proposal_manager as PR
    import proposal_suggestion as PS
    found = result.get("suggestions", [])
    by_item = {s.get("item"): s for s in found}
    canon: dict[str, dict] = {}
    # ALREADY RULED THIS CIRCLE. The close's checkpoint vets the parts' brackets before this
    # runs, and a typed command is recorded in the transcript, so the model names both again.
    # A pending row is left to proposal_row_stage_once(), which reuses it; a row of this circle
    # that is resolved (its `circle` is dropped then, its author credit "<who> in circle_<OT>"
    # stays) or a line Self typed is not staged again.
    ref = PR.circle_ref(ot)
    ruled_here: dict[str, str] = {}
    for r in PR.proposal_read():
        if r.get("state") != "proposed" and str(r.get("author", "")).endswith(f" in {ref}"):
            ruled_here.setdefault(" ".join(str(r.get("text", "")).split()),
                                  f"already ruled this circle as {r['id']}")
    for t in typed or []:
        t = t.strip()
        head = CS.command_head_normalise("/" + t.split()[0].lstrip("/")) if t else ""
        for form in {t, _stable_handles(head, t, referents)}:
            ruled_here.setdefault(" ".join(form.split()), "already typed by Self in the room")
    for s in found:
        line, verb = s["line"].strip(), s["verb"]
        if verb == "/propose-add":
            line = line[len("/propose-add"):].strip()
            if not line:
                s["not_staged"] = "a propose-add with nothing in it"
                continue
            verb = CS.command_head_normalise("/" + line.split()[0].lstrip("/"))
        if verb == "/part-add" and s.get("speaker") != "Self":
            s["not_staged"] = ("adding a part is Self's alone (R483) — a part's words stay in "
                               "the report")
            continue
        line = _stable_handles(verb, line, referents)
        key = " ".join(line.split())
        if key in canon:
            first = canon[key]
            s["duplicate_of"] = first.get("item")
            if first.get("staged"):
                s["staged"] = first["staged"]
            else:
                s["not_staged"] = first.get("not_staged", "its first mention was not staged")
            continue
        canon[key] = s
        if key in ruled_here:
            s["not_staged"] = ruled_here[key]
            continue
        depends: list[str] = []
        covered = ""
        dep = s.get("depends_on")
        tok = s.get("token", "")
        if dep is not None:
            prior = by_item.get(dep) or {}
            if prior.get("staged"):
                if tok and tok in line:
                    depends, covered = [f"{prior['staged']}{PR.DEPENDS_SEP}{tok}"], tok
                else:
                    depends = [prior["staged"]]
            elif tok and tok in line:
                s["not_staged"] = f"it waits on line {dep}, which was not staged"
                continue
        unfilled = [p for p in PS.proposal_suggestion_placeholders_read(line) if p != covered]
        if unfilled:
            s["not_staged"] = f"it holds {', '.join(unfilled)}, which nothing staged here fills"
            continue
        shape = MK._propose_command_shape(line)
        if shape and shape.get("ok"):
            kind = "command"
        elif PS.proposal_suggestion_is_runnable(verb):
            kind = "suggestion"
        else:
            s["not_staged"] = f"{verb} is not a verb a staged line can run"
            continue
        try:
            pid, new = PR.proposal_row_stage_once(kind, line, [s.get("speaker") or "Self"], ot,
                                                  quote=s.get("quote") or "",
                                                  depends_on=depends or None)
        except ValueError as e:
            s["not_staged"] = str(e)
            continue
        s["staged"] = pid
        if not new:
            s["already_pending"] = True
    out: list[str] = []
    for s in found:
        if s.get("staged") and s["staged"] not in out:
            out.append(s["staged"])
    return out


def command_suggest_staged_render(result: dict) -> str:
    """What staging did, one line per report line, numbered as the report numbers them."""
    found = result.get("suggestions", [])
    pos = {s.get("item"): n for n, s in enumerate(found, 1)}
    ids = result.get("staged", [])
    lines = [f"  staged for your ruling at the next checkpoint: {len(ids)} proposal(s)"
             + (f" — {', '.join(ids)}" if ids else "")]
    for n, s in enumerate(found, 1):
        if s.get("duplicate_of") is not None:
            lines.append(f"  {n:3}. the same as line {pos.get(s['duplicate_of'], '?')}")
        elif s.get("staged"):
            lines.append(f"  {n:3}. {s['staged']}"
                         + (" (already pending)" if s.get("already_pending") else ""))
        elif s.get("not_staged"):
            lines.append(f"  {n:3}. not staged — {s['not_staged']}")
    return "\n".join(lines)


def command_suggest_run(ot: str, transcript_text: str, *, say=print, client=None,
                        out: pathlib.Path | None = None,
                        referents: dict | None = None, stage: bool = False) -> dict | None:
    """The close-time step and the CLI's body: parse, derive, say the report, write the
    file. NEVER RAISES — a close is not held up by a report; the failure is one line.
    `referents` None reads the live registers; a rehearsal passes its own. `stage` True — the
    live close alone (inter_circle.py) — also stages each line for vetting."""
    import transcript_store as TS
    try:
        _ot, topic, transcript = TS.circle_transcript_parse(transcript_text)
        ref = referents if referents is not None else command_suggest_referents_read()
        result = command_suggest_derive(transcript, topic, client=client, referents=ref)
        if stage:
            import identity as ID
            typed = [e["text"] for e in transcript
                     if e.get("speaker") == ID.SELF_ID and not e.get("is_topic")
                     and e.get("text", "").lstrip().startswith("/")]
            try:
                result["staged"] = command_suggest_stage(result, ot, ref, typed)
            except Exception as e:                               # noqa: BLE001
                result.setdefault("notes", []).append(
                    f"staging stopped ({type(e).__name__}: {e}) — what was staged stands")
        say(command_suggest_report_render(ot, result))
        if stage and "staged" in result:
            say(command_suggest_staged_render(result))
        path = out if out is not None else command_suggest_report_locate(ot)
        command_suggest_report_write(path, ot, result)
        say(f"  written: {_shown(path)}")
        return result
    except Exception as e:                                       # noqa: BLE001
        say(f"  command suggestions: not produced — {type(e).__name__}: {e}")
        return None


def _shown(p: pathlib.Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--ot", help="a closed circle's open time; its transcript is read from "
                                 "the bound group's circles/ and the report lands in work/logs/")
    ap.add_argument("--group", default=None, help="the group whose circle --ot names")
    ap.add_argument("--file", help="any transcript file in the coordinator's shape; the "
                                   "report is printed, and written only with --out")
    ap.add_argument("--out", help="where to write the JSON report (with --file)")
    ap.add_argument("--referents", help="a JSON file in command_suggest_referents_read()'s "
                                        "shape, used INSTEAD of the live registers — a "
                                        "rehearsal against a dialog that is not this tree's. "
                                        "Default: the live registers of the bound group")
    ap.add_argument("--json", action="store_true", help="print the JSON report too")
    args = ap.parse_args()
    if bool(args.ot) == bool(args.file):
        ap.print_help()
        return 2
    referents = None
    if args.referents:
        with open(args.referents, encoding="utf-8") as f:
            referents = json.load(f)
        referents.setdefault("notes", []).append(
            f"referents from {args.referents}, not the live registers (a rehearsal)")
    if args.file:
        p = pathlib.Path(args.file)
        ot = re.sub(r"^circle_|\.md$", "", p.name)
        text = p.read_text(encoding="utf-8")
        out = pathlib.Path(args.out) if args.out else None
        if out is None:
            # printed only: write to a scratch path nothing files, so the run leaves no report
            # in work/logs/ for a circle that never closed here
            out = _RP.SANDBOX / "logs" / f"command_suggest_{ot}.json"
    else:
        if args.group:
            _RP.group_set(args.group)
        ot = args.ot
        p = _RP.record_dir(ROOT, "circles") / f"circle_{ot}.md"
        if not p.is_file():
            print(f"  no transcript at {_shown(p)}")
            return 1
        text = p.read_text(encoding="utf-8")
        out = None
    result = command_suggest_run(ot, text, client=None, out=out, referents=referents)
    if result is None:
        return 1
    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != "raw"},
                         indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
