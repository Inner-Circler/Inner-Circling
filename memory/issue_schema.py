#!/usr/bin/env python3
"""
issue_schema.py — the one reader and writer for an issue node.

    python memory/issue_schema.py            load every node, report
    python memory/issue_schema.py --render nNNNN   markdown, to stdout

    exit 0 rendered, or every node parsed and checked
         1 validation failures were found
         2 the command itself was wrong (no id after --render, or no node
           of that id) — never mixed with 1, so a caller can tell a broken
           node from a mistyped argument

Ruled 2026-08-03. `issues/` moves from Markdown to TOML.

WHY. Every parsing defect this project has recorded was Markdown ambiguity in a
file a regex had to interpret, and each one FAILED SILENTLY rather than loudly:

    a three-space indent made an evidence entry INVISIBLE, and the verified
    count fell without a word;
    an edge type containing `_` fell outside `EDGE_RE` entirely, so its Status,
    Basis and Ask went unchecked;
    a `## ` line inside a fenced code block ended a section early;
    a markdown-aware editor "normalised" `parts/<part>/long_term.md` and made
    14 of 22 dream entries unparseable while still reading correctly to a human.

Each was met with a narrower regex or a counter-check. That is a ratchet, not a
fix — `issue_gate.py` reached 27 regexes over a format that has no grammar. TOML
has one, and `tomllib` is in the standard library from 3.11 (this project pins
`tomli`, the identical parser, for 3.10).

WHY NOT JSON. No multi-line strings. A node's description is ~800 characters and
would become one line with every em-dash escaped, which is worse to hand-edit
than Markdown — and hand-editability is half the reason for the move.

WHAT DOES NOT CHANGE

    THE PREFIX IS PRESENTATION; THE ID IS IDENTITY. `L_n9999.toml` still carries
    its status in the filename so `ls issues/n0*.toml` shows exactly the live
    set, and the gate still cross-checks prefix against `status`.

    PROSE IS STILL PROSE. `description`, `memo`, `description_history` and the
    evidence `why` are Markdown inside TOML strings. What became structured is
    the SHAPE — fields, edges, evidence — not the writing.

    SOFT WRAP. Prose is stored hard-wrapped for editing, and a single newline is
    soft, exactly as in Markdown. `issue_unwrap()` is the one place that is decided;
    `check_issues` already did `re.sub(r"\\s+", " ", ...)` before this change.
"""

from __future__ import annotations

import pathlib
import re
import sys
import textwrap

try:                                          # 3.11+
    import tomllib
except ModuleNotFoundError:                   # 3.7+, the identical parser
    import tomli as tomllib                   # type: ignore

import tomli_w

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "coordinator"))  # atomic_write/identity et al.
from atomic_write import record_atomic_write

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = pathlib.Path(__file__).resolve().parent.parent
ISSUES = ROOT / "issues"

# The circle-transcript roots and the ref -> path mapping, ONE copy
# (2026-08-19, review tier 5 #44). These lived as three lockstep
# clones — issue_gate.issue_source_read(), issue_prompt_projection._transcript(), and
# quote_verify's own constants — each carrying the identical "moved,
# R176" comment from the sweep that already had to edit all three; the
# next relocation that missed one would resolve provenance against the
# old tree. issue_gate's SELF-DIR arm (a bare ref -> a session record
# under self/) stays ITS OWN: only the gate admits session refs, so this
# shared helper answers circle_/sandbox_ prefixes alone and returns None
# for anything else.
CIRCLES = ROOT / "circles"
SANDBOX_CIRCLES = ROOT / "work" / "sandbox" / "circles"  # moved, R176, 2026-08-15


def circle_transcript(ref: str) -> "pathlib.Path | None":
    """circle_<OT> / sandbox_<OT> -> the transcript path; None otherwise."""
    if ref.startswith("circle_"):
        return CIRCLES / f"{ref}.md"
    if ref.startswith("sandbox_"):
        return SANDBOX_CIRCLES / f"circle_{ref[len('sandbox_'):]}.md"
    return None


WRAP = 74

# Status -> filename prefix. Unchanged from the Markdown era, deliberately.
# ROOT WAS A STATUS from 2026-08-05 (B23) to 2026-09-01 (R429):
# "they are a subset of alive, not a disjoint set... the unquestioned
# alive nodes, nodes that ought never be removed and that ought always to be
# graphed." A root's own `status` is now `"live"` — root is a FLAG (below),
# not a fourth thing beside live/lead/settled/declined/retired. `R_` stays a
# real, permanent filename marker (see `issue_prefix_read()`), kept because a
# reader who sees `R_n0003.toml` in a directory listing should not have to
# open the file to learn it is one. `R_` had meant `retired` before B23;
# retired is `X_` so `R_` can mean the thing a reader would guess it means.
PREFIX = {"live": "", "settled": "S_", "declined": "D_",
          "retired": "X_", "lead": "L_"}
STATUSES = set(PREFIX)
EDGE_TYPES = {"narrower-than", "related-to", "polarized-with",
              "protects", "leads-to"}

# Every key the schema allows, and whether it must be present.
REQUIRED = ("id", "label", "status", "opened", "description", "absence",
            "held_by")
# `root` — OPTIONAL, absent or false on every node but the two that carry it.
# A root is a live node that is also permanent: `issue_status.py` refuses to
# move one to any other status, and `issue_prompt_projection.py` shows it in full
# detail in every circle regardless of the chosen working set. See
# rulings/R429.toml.
OPTIONAL = ("label_ruled", "aliases", "adopted", "root", "description_history",
            "memo", "memo_original", "proposals", "edges", "edges_note",
            "evidence")

# M1, ruled 2026-08-04. A circle produces REQUESTS as well as claims, and the
# system had a kind for every claim and none for a request. A deferred question
# now rides the thing it is about — a node, or an edge — and PROJECTS ONLY WHEN
# THAT THING IS IN THE WORKING SET.
#
# That last property is what keeps it from becoming a queue. R002 ruled leads
# must stop being one; this never accumulates in front of anyone, because it is
# invisible until Self puts the node in a circle and then unavoidable.
#
#   [[proposals]]            on a node
#   [[edges.proposals]]      on an edge
#     question   what is being asked
#     asked_by   which part, or the Self id
#     source     the circle it was asked in
#     status     open | taken-up | declined
#     ruled      optional: where Self settled it
#     type/target  OPTIONAL, and the point of them is that prose cannot say
#                  this unambiguously. a part's first entry read "whether
#                  nMMMM fits this same descent" — Self: *"'this same
#                  descent' is ambiguous"*. A proposal that names a relation
#                  must name it as `<type>` to `<node>`, checked against the
#                  same closed vocabulary an edge uses.
PROPOSAL_KEYS = {"question", "asked_by", "source", "status", "ruled",
                 "type", "target"}
PROPOSAL_STATUS = {"open", "taken-up", "declined"}

# Field order in the emitted file. Not cosmetic: a stable order makes a diff
# between two versions of a node readable, which is the whole reason the
# Description history exists.
ORDER = ("id", "label", "label_ruled", "aliases", "adopted", "status", "root",
         "opened", "held_by", "description", "absence",
         "description_history", "edges_note", "memo", "memo_original")
# `proposals` is deliberately ABSENT from ORDER: it is an array of tables now
# and has its own emitter below. Leaving it here as well wrote every proposal
# TWICE — once by tomli_w from the scalar dict, once by the loop — and the
# duplicate was visible only in the projection.


def issue_prefix_read(doc: dict) -> str:
    """A node's expected filename prefix — `R_` for a root, else its
    status's ordinary prefix. The ONE place that combines the two fields;
    `issue_verify()` and `issue_locate()` both call this rather than re-deriving it."""
    return "R_" if doc.get("root") else PREFIX[doc["status"]]


def issue_locate(nid: str, status: str, root: bool = False) -> pathlib.Path:
    prefix = "R_" if root else PREFIX[status]
    return ISSUES / f"{prefix}{nid}.toml"


def issue_id_read(stem: str) -> str:
    """`L_n9999` -> `nPPPP`. The prefix is presentation."""
    return stem[2:] if stem[1:2] == "_" else stem


def issue_nodes_read() -> list[pathlib.Path]:
    return sorted(ISSUES.glob("*n[0-9][0-9][0-9][0-9].toml"))


def issue_live_read() -> list[pathlib.Path]:
    """Every node whose `status` is `"live"` — a root INCLUDED, since a root
    is a live node (R429), not a disjoint status. Two
    globs, not a parse-and-filter of `issue_nodes_read()`: this stays the fast,
    filename-only check every caller already relies on (`circle.py`'s "is
    there anything to ask a working set about", `quote_verify.py`'s citation
    guard, `/help issue list`) — a root's `R_` prefix is the one exception to
    "unprefixed means live", and it is listed explicitly rather than
    inferred."""
    return sorted(list(ISSUES.glob("n[0-9][0-9][0-9][0-9].toml"))
                  + list(ISSUES.glob("R_n[0-9][0-9][0-9][0-9].toml")))


def issue_read(p: pathlib.Path) -> dict:
    with open(p, "rb") as f:
        return tomllib.load(f)


def issue_unwrap(s: str) -> str:
    """Hard-wrapped prose -> one line per paragraph.

    A single newline is SOFT (it was inserted so the file could be edited); a
    blank line is a paragraph break. Markdown's own rule, and what every
    consumer of a description already assumed."""
    return "\n\n".join(re.sub(r"\s+", " ", b).strip()
                       for b in re.split(r"\n\s*\n", s.strip()))


def issue_wrap(s: str, width: int = WRAP) -> str:
    """One line per paragraph -> hard-wrapped, for storage.

    Lines that are already short, list items, code fences and blockquotes are
    left alone: re-wrapping a `- ` bullet or a ``` block would change what the
    Markdown inside means."""
    out = []
    for block in re.split(r"\n\s*\n", s.strip()):
        flat = re.sub(r"[ \t]+", " ", block.strip())
        if any(flat.lstrip().startswith(m) for m in ("- ", "* ", "> ", "```",
                                                     "|", "#")) \
                or "\n" in flat:
            out.append(block.strip())
        else:
            out.append("\n".join(textwrap.wrap(
                flat, width, break_on_hyphens=False,
                break_long_words=False)) or flat)
    return "\n\n".join(out)


def issue_dumps(doc: dict) -> str:
    """TOML text for one node, fields in ORDER, tables last.

    `tomli_w` emits a multi-line string only when the value contains a newline,
    so prose is wrapped on the way out. It escapes `"` inside `\"\"\"` — 22% of
    evidence quotes carry one, against 42% carrying an apostrophe, which is why
    the basic form is used rather than the literal `'''`."""
    scalar = {k: doc[k] for k in ORDER if k in doc}
    for k in ("description", "absence", "description_history",
              "memo", "memo_original", "edges_note"):
        if k in scalar and isinstance(scalar[k], str):
            scalar[k] = issue_wrap(scalar[k])
    out = tomli_w.dumps(scalar, multiline_strings=True)
    for row in doc.get("proposals", []):
        out += "\n" + tomli_w.dumps({"proposals": [row]},
                                    multiline_strings=True)
    for name in ("edges", "evidence"):
        for row in doc.get(name, []):
            # `quote` is NEVER wrapped. It is a verbatim artifact checked
            # character-for-character against a transcript, and re-flowing it
            # collapses the double spaces four real quotes carry — which broke
            # five nodes on the first migration run and is precisely the silent
            # alteration the verbatim rule exists to catch. Prose beside it may
            # wrap; the evidence may not.
            row = {k: (issue_wrap(v) if k in ("why", "basis")
                       and isinstance(v, str) else v)
                   for k, v in row.items()}
            out += "\n" + tomli_w.dumps({name: [row]}, multiline_strings=True)
    return out


def issue_write(p: pathlib.Path, doc: dict) -> None:
    # Atomic since 2026-08-16 (docs/HELP_DESIGN.md §6): render, then
    # os.replace a same-directory temp over the real path, so a crash
    # mid-write can no longer corrupt the node that was there before.
    record_atomic_write(p, issue_dumps(doc))


# ------------------------------------------------------------------ rendering
# A node still renders to Markdown on demand. Two reasons, and the second is the
# one that matters: a reader who wants the old view can have it, AND the
# converter proves itself by rendering every migrated node back and comparing to
# the original bytes. Anything that does not survive that round trip is a real
# loss, found before the Markdown is deleted rather than after.

def issue_render(doc: dict) -> str:
    L = [f"# {doc['id']}", "",
         f"**Description:** {issue_unwrap(doc['description'])}", "",
         f"**Label:** {doc['label']}", ""]
    if doc.get("label_ruled"):
        L += [f"**Label ruled:** {doc['label_ruled']}", ""]
    if doc.get("aliases"):
        L += ["**Aliases:** " + " · ".join(doc["aliases"]), ""]
    if doc.get("adopted"):
        a = doc["adopted"]
        L += [f"**Adopted:** {a['part']} ({a['date']}, {a['where']})", ""]
    # `root` is a flag, not a status (R429) — said here
    # too, or a root renders identically to any other live node and the
    # one fact that distinguishes it (permanent, always shown in full)
    # disappears from the one human-facing view this function exists for.
    status_line = doc['status'] + (" (root)" if doc.get("root") else "")
    L += [f"**Status:** {status_line}", "",
          f"**Opened:** {doc['opened']}", ""]
    L += ["**Held by:** " + " · ".join(f"{h} (live)" for h in doc["held_by"]),
          ""]
    L += ["## Description history", "", doc.get("description_history", ""), ""]
    L += [f"**What its absence looks like:** {issue_unwrap(doc['absence'])}", ""]
    L += ["## Edges", ""]
    for e in doc.get("edges", []):
        L.append(f"- `{e['type']}` [[{e['target']}]]")
        L.append(f"  Status: {e['status']}"
                 + (f" ({e['dated']})" if e.get("dated") else "")
                 + (f" — {e['status_note']}" if e.get("status_note") else ""))
        L.append(f"  Basis: {issue_unwrap(e['basis'])}")
        if e.get("why"):
            L.append(f"  Why: {issue_unwrap(e['why'])}")
        for extra in e.get("notes", []):
            L.append(f"  {issue_unwrap(extra)}")
        if e.get("ask"):
            L.append("  Ask: " + ", ".join(e["ask"]))
        if e.get("quote"):
            L.append("  > " + issue_unwrap(e["quote"]))
        if e.get("retired"):
            L.append(f"  Retired: {issue_unwrap(e['retired'])}")
    if doc.get("edges_note"):
        L += ["", issue_unwrap(doc["edges_note"])]
    L += ["", "## Evidence", ""]
    # FIRST-APPEARANCE order, not alphabetical. The order parts appear under
    # ## Evidence is the order they arrived, and sorting it silently reordered
    # three nodes on the first migration run.
    seen_parts: list[str] = []
    for e in doc.get("evidence", []):
        if e["part"] not in seen_parts:
            seen_parts.append(e["part"])
    for part in seen_parts:
        L += [f"### {part}", ""]
        for e in doc["evidence"]:
            if e["part"] != part:
                continue
            L += [f"- {e['source']}", f"  > {issue_unwrap(e['quote'])}"]
            # Said aloud in the rendered view, not only in the TOML: a reader
            # of `### self` is otherwise looking at a part's words with no
            # sign of it. RULED 2026-08-18.
            if e.get("adopted_from"):
                L.append(f"  Adopted from: {e['adopted_from']}")
            L += [f"  Why: {issue_unwrap(e['why'])}", ""]
    # PROPOSALS BECAME AN ARRAY OF TABLES (M1, 2026-08-04) AND THIS LINE DID
    # NOT FOLLOW IT — until 2026-08-18 it put the LIST itself into `L`, and
    # `--render <id>` raised TypeError on every node carrying one. Found while
    # checking that the `Adopted from:` line above renders; unrelated to it,
    # pre-existing, and invisible because nothing but a human at a terminal
    # calls this path. issue_dumps() (line ~199) is the emitter that DID follow the
    # change; this is the read-side view catching up.
    L += ["## Proposals", ""]
    for pr in doc.get("proposals", []):
        rel = (f" — proposes `{pr['type']}` [[{pr['target']}]]"
               if pr.get("type") else "")
        L += [f"- **{pr.get('status', '?')}**{rel} · asked by "
              f"{pr.get('asked_by', '?')} ({pr.get('source', '?')})",
              f"  {issue_unwrap(pr.get('question', ''))}"]
        if pr.get("ruled"):
            L.append(f"  Ruled: {issue_unwrap(pr['ruled'])}")
        L.append("")
    L += ["## Memo", "", doc.get("memo", ""), ""]
    # One node carries a `## Memo — original`, kept when its memo was rewritten.
    # A single-instance section is exactly what a closed schema must still hold,
    # or the migration quietly deletes the one thing nobody remembered.
    if doc.get("memo_original"):
        L += ["## Memo — original", "", doc["memo_original"], ""]
    return "\n".join(L)


def issue_verify(doc: dict, p: pathlib.Path) -> list[str]:
    """Schema-level failures. NOT the invariant gate — that is issue_gate.py,
    which checks claims about the world (quotes verbatim, targets exist). This
    checks only that the document is the shape it says it is, which under TOML
    is nearly all that is left to check."""
    f = []
    for k in REQUIRED:
        if k not in doc:
            f.append(f"{p.name}: missing required key `{k}`")
    for k in doc:
        if k not in REQUIRED + OPTIONAL:
            f.append(f"{p.name}: unknown key `{k}` — the schema is closed")
    if doc.get("status") not in STATUSES:
        f.append(f"{p.name}: status {doc.get('status')!r} is not one of "
                 f"{'/'.join(sorted(STATUSES))}")
    elif doc.get("root") and doc["status"] != "live":
        f.append(f"{p.name}: `root = true` but status is `{doc['status']}` — "
                 f"a root is a permanent LIVE node; it cannot carry any other "
                 f"status")
    elif p.name != f"{issue_prefix_read(doc)}{doc['id']}.toml":
        why = "is a root" if doc.get("root") else f"status is `{doc['status']}`"
        f.append(f"{p.name}: {why} so the file must be named "
                 f"{issue_prefix_read(doc)}{doc['id']}.toml — prefix must agree "
                 f"with status and the `root` flag")
    if doc.get("id") != issue_id_read(p.stem):
        f.append(f"{p.name}: id {doc.get('id')!r} does not match its filename")
    for pr in (list(doc.get("proposals", []))
               + [q for e in doc.get("edges", []) for q in e.get("proposals", [])]):
        bad = set(pr) - PROPOSAL_KEYS
        if bad:
            f.append(f"{p.name}: proposal has unknown key(s) {sorted(bad)}")
        if pr.get("status") not in PROPOSAL_STATUS:
            f.append(f"{p.name}: proposal status {pr.get('status')!r} is not "
                     f"one of {'/'.join(sorted(PROPOSAL_STATUS))}")
        for k in ("question", "asked_by", "source"):
            if not pr.get(k):
                f.append(f"{p.name}: proposal has no `{k}`")
        if pr.get("type") and pr["type"] not in EDGE_TYPES:
            f.append(f"{p.name}: proposal names type {pr['type']!r}, which is "
                     f"not an issue-relationship type")
        if bool(pr.get("type")) != bool(pr.get("target")):
            f.append(f"{p.name}: a proposal naming an issue-relationship needs BOTH "
                     f"`type` and `target` — half of one is a claim nobody "
                     f"can act on")
    # `adopted_from` — RULED 2026-08-18, the per-entry counterpart to the
    # node-level [adopted] block. Its whole meaning is "the transcript shows a
    # part said this and Self has declared it his own", so it is meaningless
    # anywhere but on a `self` entry, and naming Self as the part he adopted
    # from is a claim about nothing. The gate checks the harder half — that
    # the named part is the one the transcript actually shows; these two are
    # shape, and belong here.
    for e in doc.get("evidence", []):
        if not e.get("adopted_from"):
            continue
        if e.get("part") != "self":
            f.append(f"{p.name}: `adopted_from` on an entry filed under "
                     f"{e.get('part')!r} — it says whose words Self adopted, "
                     f"so it belongs only on a `self` entry")
        if e["adopted_from"] == "self":
            f.append(f"{p.name}: `adopted_from = \"self\"` claims Self adopted "
                     f"his own words")
    for e in doc.get("edges", []):
        if e.get("type") not in EDGE_TYPES:
            f.append(f"{p.name}: unknown issue-relationship type {e.get('type')!r}")
        if e.get("target") == doc.get("id"):
            f.append(f"{p.name}: issue-relationship points at itself")
    return f


def main() -> int:
    if "--render" in sys.argv:
        # BOTH MISSES ARE ANSWERED, AND NEITHER RETURNS 1 — 2026-08-27.
        # These two lines were unguarded, so `--render n9999` raised
        # StopIteration and `--render` with nothing after it raised
        # IndexError; each printed a Python traceback and exited 1, which
        # is THIS script's documented code for "validation failures found".
        # A caller reading exit codes could not tell a malformed node from
        # a mistyped id, and colliding with a documented code is worse than
        # falling outside the set. 2 is neither.
        #
        # IT IS A SHIPPED SURFACE, which is why it outranked the local
        # defects found beside it: packaging/required.toml ships `memory`
        # as a whole directory, and packaging/additions.toml ships this
        # module's man page for "the --render <id> a person uses to read
        # one as Markdown". The advertised spelling was the one that
        # tracebacked.
        i = sys.argv.index("--render") + 1
        if i >= len(sys.argv):
            print("  --render needs a node id: "
                  "python memory/issue_schema.py --render nNNNN")
            return 2
        nid = sys.argv[i]
        q = next((x for x in issue_nodes_read() if issue_id_read(x.stem) == issue_id_read(nid)), None)
        if q is None:
            print(f"  no issue node matches {nid!r}. The id is the filename "
                  f"without its status prefix — try `ls issues/`.")
            return 2
        print(issue_render(issue_read(q)))
        return 0
    fails, n = [], 0
    for p in issue_nodes_read():
        try:
            doc = issue_read(p)
        except Exception as e:                      # a parse error is now LOUD
            fails.append(f"{p.name}: will not parse — {e}")
            continue
        n += 1
        fails += issue_verify(doc, p)
    print(f"  {n} issue file(s) parsed")
    for x in fails:
        print(f"  FAIL  {x}")
    print("  SCHEMA PASS" if not fails else f"  {len(fails)} FAILURE(S)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
