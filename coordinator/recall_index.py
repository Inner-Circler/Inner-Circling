#!/usr/bin/env python3
"""
recall_index.py — the parts' recall engine: the [recall: ...] annotation,
its local search, and the private reply.

RULED ACROSS R400-R402 (2026-08-29). R400 made semantic search local;
R401 narrowed the grammar ("no journal ... the parts should remain unaware
of a journal", no date window, part_name implicit and enforced); R402
settled it ("6-40 is better, build it"). A part that meets resonance
mid-circle writes, inside an ordinary statement:

    [recall: <scope>* ( <semantic_prompt> | "<exact_string>" ) <breadcrumb>*]

    scope       mine | room | issues     (default mine; claimed only while
                LEADING the annotation — after the first non-keyword
                token, these are ordinary prompt words)
    prompt      bare words = SEMANTIC; "double-quoted" = EXACT, 6-40
                printable ASCII, no '"' and no ']' inside
    breadcrumb  n0012 · BP-0047 (bare ids, any length, by shape) ·
                'single-quoted phrase' (6-40, same character rules)

THE ALREADY-SENT RULE (the operator, 2026-08-30): *"if a part is already
being given a prompt segment, don't return it in search."* What recall
serves is the INVISIBLE record. So `mine` excludes mid_term (Block 3 IS
it); `issues` excludes the live and lead nodes Block 2 already projects
(only R_/S_/D_/X_ history is searchable); and there is NO practices scope
at all — broadcast rows (All parts AND Self) are in every Block 1, a
part's own narrowcast is in its Block 3, and the only rows left are other
parts' narrowcast, which E09's routing exists to keep from it. A leading
`practices` token gets a private note saying exactly that. long_term.md
STAYS searchable: only its DISTILLATE reaches Block 3 (R113/R114 — 230k
raw chars became 46k), and the lost four-fifths is much of recall's point.

ONE RECALL PER PART PER ROUND (the operator's own cap, 2026-08-29/30). The
first bracket in a round is executed; a later one in the same round gets a
private "not run" note. Within one statement, the last bracket wins.
Queries execute SERIALLY by construction — rounds poll parts one at a
time, and even the blind round's parallel asking reveals statements
sequentially, so the coordinator never runs two searches at once.

THE QUERY IS STRIPPED FROM THE ROOM AND KEPT IN THE RECORD — the remember
bracket's own discipline (docs/BNF.md, REMEMBER): the transcript FILE
keeps the bracket, no part ever sees another part's query, and a
statement that was ENTIRELY a recall is a pass the room hears as one
(transcript_store.circle_transcript_is_withheld(), third member). THE REPLY IS PRIVATE: it
rides at the tail of the asking part's next request — never a prompt
block (blocks are static per circle, capture-verified), never the room —
latest result wins, and it expires at /close. What a part wants to keep
it speaks aloud or [remember:]s; that is the persistence door, already
built.

PART_NAME IS NOT A SLOT. The coordinator knows who asked, and `mine` can
only ever mean the asker's own files. THERE IS NO JOURNAL LOADER in this
module, and never will be — unawareness is structural, not a filter
(R401); the probe greps this file for the word and fails if it appears.

THE SEARCH IS LOCAL AND ADDS NO MODEL CALL TO THE ROOM. Exact search is a
normalized in-memory scan over the same chunk records the semantic side
embeds — the two kinds see byte-identical corpora by construction.
Semantic ranking is embed_store's (bge-small over fastembed, cosine).
REFRESH IS LAZY: the first query of a circle embeds whatever moved since
the corpus was last indexed — sub-second once warm, a few seconds on the
first-ever build — and nothing is indexed at open or close.

THE CACHES ARE DERIVED, NEVER THE RECORD: work/recall_index/*.ndjson,
gitignored, one re-embed to rebuild.

A FAILURE HERE CANNOT COST A STATEMENT: recall_apply() catches
everything, answers the part with the error privately, and the turn
proceeds.
"""
from __future__ import annotations

import pathlib
import re
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent          # coordinator/
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "memory"))         # the issue-graph code

import annotations as MK                                # noqa: E402
import embed_store as ES                                # noqa: E402
import record_paths as P                                       # noqa: E402
import seam                                             # noqa: E402

try:
    import tomllib                                      # 3.11+
except ModuleNotFoundError:                             # pragma: no cover
    import tomli as tomllib                             # type: ignore

# ------------------------------------------------------------- the grammar
_RECALL_OPEN = r"\[recall:"
RECALL_RE = re.compile(_RECALL_OPEN + r"[^\]]*\]", re.I)

SCOPES = ("mine", "room", "issues")
# A scope word that was RULED and then closed by the already-sent rule —
# recognized so the part gets taught privately instead of the token
# leaking into its semantic prompt.
CLOSED_SCOPES = {"practices": (
    "the practices register is already in your opening blocks — broadcast "
    "rows in Block 1, your own in Block 3; BP- ids still work as "
    "breadcrumbs over mine/room/issues")}
ISSUE_ID_RE = re.compile(r"^n\d{4}$")
PRACTICE_ID_RE = re.compile(r"^BP-\d{4}$", re.I)
_EXACT_RE = re.compile(r'"([^"\]]*)"')
_PHRASE_RE = re.compile(r"'([^'\]]*)'")
QUOTE_MIN, QUOTE_MAX = 6, 40            # R402: "6-40 is better, build it"

FLOOR = 0.62        # semantic relevance floor for bge cosine. MEASURED
                    # 2026-08-29 against the Child's real 284-chunk mine
                    # corpus: on-topic queries top 0.65-0.68 while a
                    # deliberately off-topic control ("quarterly accounting
                    # spreadsheets") tops 0.59 — the first floor, 0.45, sat
                    # below even the noise and could never fire. Below this,
                    # silence beats noise. A constant, not a register: parts
                    # do not tune it, and Self's lens has its own slider.
MAX_EXCERPTS = 3
# THE BUDGET IS TIER A's, SHARED ON PURPOSE: remember_expand's EXPAND_CAP
# (1200 chars) was sized as what one recall delivery may put in front of a
# part, and this reply is the same delivery through a different door — one
# fact, one owner (system_unique_home_verify's rule; the 4000-pair lesson). The
# per-excerpt window derives from it rather than declaring its own number.
from remember_expand import EXPAND_CAP as TOTAL_CHARS  # noqa: E402
EXCERPT_CHARS = TOTAL_CHARS // MAX_EXCERPTS
CACHE_DIR = P.ROOT / "work" / "recall_index"

_TRANSLATE = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": ".",
})
# EVERY MAPPING IS 1:1 ON PURPOSE: _kwic() slices the ORIGINAL text with
# offsets found in the normalized form, so a mapping that changed length
# ("…" -> "...") would shift the window and mismark the span for any
# record with an ellipsis before the match.


def _norm(text: str) -> str:
    """The comparison form: curly quotes and long dashes straightened,
    case folded — so a part's ASCII-only quote still matches a record
    that was typed with typographic characters."""
    return text.translate(_TRANSLATE).casefold()


# _is_quoted WAS DEFINED HERE, PRIVATELY, UNTIL 2026-09-01 (B82's own
# module). It moved to annotations.annotation_is_quoted() (audit-register.md Tier 1
# #3) once the identical gap turned up for `remember:`/`proposed:` — a
# second private copy would have been the exact two-recognizer drift
# annotations.py's own module docstring warns about ("ONE TAUGHT SPELLING,
# TWO RECOGNIZERS... the cost of drift is a bracket one recognizes and the
# other fails to strip reaches the room"). Read as MK.annotation_is_quoted() at each
# call; the local `_is_quoted` alias went 2026-09-03.


def _executable_matches(text: str) -> list[re.Match]:
    """Every RECALL_RE match in `text` that is NOT backtick-quoted — the
    ones recall_apply() may actually run."""
    return [m for m in RECALL_RE.finditer(text)
           if not MK.annotation_is_quoted(text, m.start(), m.end())]


def recall_strip(text: str) -> str:
    """Remove every EXECUTABLE recall bracket, valid or malformed alike,
    and tidy the whitespace the removal left behind — the same three tidy
    operations as annotations.remember_strip(), for the same reason: the live
    path and the resume path must produce byte-identical room text. A
    backtick-quoted bracket is prose ABOUT the syntax, not a use of it, and
    is left exactly as written (B82) — nothing here is stripped from a
    part's own description of the feature."""
    def _sub(m: re.Match) -> str:
        return m.group(0) if MK.annotation_is_quoted(text, m.start(), m.end()) else ""
    cleaned = RECALL_RE.sub(_sub, text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _valid_quote(s: str) -> str | None:
    """None when s is a legal quoted form, else the private correction."""
    if not (QUOTE_MIN <= len(s) <= QUOTE_MAX):
        return (f"a quoted form must be {QUOTE_MIN}-{QUOTE_MAX} characters "
                f"({len(s)} given: {s[:50]!r}); ids like n0012 or BP-0047 "
                f"go bare, without quotes")
    if any(not (0x20 <= ord(c) <= 0x7E) for c in s):
        return (f"a quoted form is plain printable characters only "
                f"({s[:50]!r})")
    return None


def recall_parse(body: str) -> dict:
    """The bracket's content -> {scopes, exact, semantic, ids, practices,
    phrases, errors}. Scope keywords are claimed only while they LEAD —
    'mine', 'room', 'issues' are common words, and [recall: what is mine
    to carry] must be a prompt, not a scope."""
    q = {"scopes": [], "exact": None, "semantic": "", "ids": [],
         "practices": [], "phrases": [], "errors": []}
    exacts = _EXACT_RE.findall(body)
    body = _EXACT_RE.sub(" ", body)
    phrases = _PHRASE_RE.findall(body)
    body = _PHRASE_RE.sub(" ", body)
    if len(exacts) > 1:
        q["errors"].append('one "exact search" at most')
    for s in exacts[:1]:
        err = _valid_quote(s)
        q["errors"].append(err) if err else q.__setitem__("exact", s)
    for s in phrases:
        err = _valid_quote(s)
        q["errors"].append(err) if err else q["phrases"].append(s)
    rest, leading = [], True
    for tok in body.split():
        word = tok.strip(",;")
        if leading and word.lower() in SCOPES:
            if word.lower() not in q["scopes"]:
                q["scopes"].append(word.lower())
            continue
        if leading and word.lower() in CLOSED_SCOPES:
            q["errors"].append(CLOSED_SCOPES[word.lower()])
            continue
        leading = False
        if ISSUE_ID_RE.match(word):
            q["ids"].append(word.lower())
        elif PRACTICE_ID_RE.match(word):
            q["practices"].append(word.upper())
        else:
            rest.append(tok)
    q["semantic"] = " ".join(rest).strip()
    if not q["scopes"]:
        q["scopes"] = ["mine"]
    if not (q["exact"] or q["semantic"] or q["ids"] or q["practices"]
            or q["phrases"]):
        q["errors"].append("nothing to search for — give words, a "
                           '"quoted exact string", an id, or a '
                           "'quoted phrase'")
    return q


# ------------------------------------------------------------- the corpora
def _sections(text: str, id_prefix: str, meta: dict) -> list:
    """Split a markdown document on its ## headings; each section is one
    chunk. The preamble before the first heading is chunk 0."""
    out, buf, title, n = [], [], "", 0
    def flush():
        nonlocal n
        body = "\n".join(buf).strip()
        if body:
            out.append({"id": f"{id_prefix}#{n}", "text": body,
                        **meta, "kind": meta.get("kind", "") or title})
            n += 1
    for ln in text.splitlines():
        if ln.startswith("## "):
            flush()
            buf, title = [], ln[3:].strip()
        else:
            buf.append(ln)
    flush()
    return out


def _closed(ot: str, root: pathlib.Path) -> bool:
    return (root / "work" / "logs" / f"close_{ot}.json").is_file()


def recall_records_read(scope: str, part: str, root: pathlib.Path) -> list:
    """The chunk records one scope holds for one part. Every record:
    {id, text, scope, kind, ot?, speaker?}. Defensive throughout — a
    missing file is an empty corpus, never a crash."""
    recs: list = []
    if scope == "mine":
        pdir = root / "parts" / part
        # Both suffixes since B96 (R434): a .toml is chunked in the .md shape
        # it renders to, so a section's `kind` is its heading either way.
        import short_term_manager as STM
        for f in STM.short_term_paths_read(pdir):
            ot = f.stem.removeprefix("short_term_")
            rec = STM.short_term_read(f, part)
            text = (STM.short_term_prose_render(rec) if rec["format"] == STM.FORMAT_NEW
                    else f.read_text(encoding="utf-8"))
            recs += _sections(text, f"st:{ot}", {"scope": "mine", "ot": ot})
        lt = pdir / "long_term.md"
        if lt.is_file():
            recs += _sections(lt.read_text(encoding="utf-8"),
                              "lt", {"scope": "mine", "kind": "long_term"})
        for name, table, field in (("remember.toml", "remember", "text"),
                                   ("dreams.toml", "dreams", "content")):
            f = pdir / name
            if not f.is_file():
                continue
            try:
                doc = tomllib.loads(f.read_text(encoding="utf-8"))
            except Exception:                             # noqa: BLE001
                continue
            for i, row in enumerate(doc.get(table, [])):
                body = str(row.get(field, "")).strip()
                if body:
                    recs.append({"id": f"{table}:{i}", "text": body,
                                 "scope": "mine", "kind": table,
                                 "ot": str(row.get("circle",
                                                   row.get("date", "")))})
    elif scope == "room":
        import transcript_store as TS
        for f in sorted((root / "circles").glob("circle_*.md")):
            ot = f.stem.removeprefix("circle_")
            if not _closed(ot, root):
                continue
            try:
                _ot, _topic, entries = TS.circle_transcript_parse(
                    f.read_text(encoding="utf-8"))
            except Exception:                             # noqa: BLE001
                continue
            # Statements as the ROOM heard them: parse_transcript's
            # _split_remember/_split_recall already stripped every private
            # bracket from e["text"], so another part's note cannot enter
            # this corpus; a bracket-only turn has empty text and is
            # skipped with the Coordinator notes.
            for i, e in enumerate(entries):
                body = (e.get("text") or "").strip()
                if body and e.get("speaker") != "__coordinator__":
                    recs.append({"id": f"rm:{ot}#{i}", "text": body,
                                 "scope": "room", "kind": "statement",
                                 "ot": ot,
                                 "speaker": e.get("display", "")})
    elif scope == "issues":
        # ONLY THE HISTORY Block 2 does not project: R_/S_/D_/X_ prefixed
        # nodes. A bare nNNNN.toml is LIVE and an L_ is a LEAD — both are
        # already in every part's Block 2, so returning them would violate
        # the already-sent rule.
        try:
            import issue_schema as ISC
            # the STATUS IS THE FILENAME PREFIX (CLAUDE.md's register
            # table): this glob IS the already-sent filter — only history.
            for f in sorted((root / "issues")
                            .glob("[RSDX]_n[0-9][0-9][0-9][0-9].toml")):
                try:
                    doc = ISC.issue_read(f)
                    body = ISC.issue_render(doc).strip()
                except Exception:                         # noqa: BLE001
                    body = f.read_text(encoding="utf-8").strip()
                nid = re.search(r"n\d{4}", f.stem)
                recs.append({"id": f"is:{f.stem}", "text": body,
                             "scope": "issues",
                             "kind": nid.group(0) if nid else f.stem})
        except ImportError:
            pass
    return recs


# ------------------------------------------------------------- the search
def _kwic(text: str, needle_norm: str) -> str:
    """A window centered on the first normalized match, the match marked."""
    pos = _norm(text).find(needle_norm)
    if pos < 0:
        return text[:EXCERPT_CHARS]
    half = (EXCERPT_CHARS - len(needle_norm)) // 2
    lo, hi = max(0, pos - half), min(len(text), pos + len(needle_norm) + half)
    window = text[lo:hi]
    pre = "..." if lo > 0 else ""
    post = "..." if hi < len(text) else ""
    return (pre + window[:pos - lo] + "<<" + text[pos:pos + len(needle_norm)]
            + ">>" + window[pos - lo + len(needle_norm):] + post)


def _provenance(r: dict) -> str:
    bits = [r.get("scope", "")]
    if r.get("ot"):
        bits.append(str(r["ot"]))
    if r.get("speaker"):
        bits.append(str(r["speaker"]))
    if r.get("kind"):
        bits.append(str(r["kind"]))
    return " · ".join(b for b in bits if b)


def recall_execute(part: str, q: dict, root: pathlib.Path | None = None,
            embedder=None) -> str:
    """One query, one private reply text. Raises nothing on a sound stack;
    embed_store's IndexUnavailable propagates to apply_recall's catch."""
    root = root or P.ROOT
    recs: list = []
    for s in q["scopes"]:
        recs += recall_records_read(s, part, root)
    hits: list = []                     # (rank_key, excerpt_kind, record)
    seen: set = set()

    def take(r: dict, key: tuple, needle: str | None) -> None:
        if r["id"] in seen:
            return
        seen.add(r["id"])
        hits.append((key, needle, r))

    # exact prompt first, then breadcrumbs — direct anchors outrank
    # resemblance — newest first within each band.
    def _recency(r: dict) -> str:
        return str(r.get("ot", ""))
    if q["exact"]:
        n = _norm(q["exact"])
        for r in sorted(recs, key=_recency, reverse=True):
            if n in _norm(r["text"]):
                take(r, (0, 0), q["exact"])
    for i, crumb in enumerate(q["ids"] + q["practices"] + q["phrases"]):
        n = _norm(crumb)
        for r in sorted(recs, key=_recency, reverse=True):
            if n in _norm(r["text"]):
                take(r, (1, i), crumb)
    sem_query = q["semantic"] or " ".join(q["phrases"])
    if sem_query and embedder is not False:
        embedder = embedder or ES.memory_embedder_read()
        cache = CACHE_DIR / f"{part}.ndjson"
        for r in ES.memory_rank(sem_query, recs, embedder, cache, MAX_EXCERPTS * 3):
            if r["score"] >= FLOOR:
                take(r, (2, -r["score"]), None)

    hits.sort(key=lambda h: h[0])
    lines, total = [], 0
    for _key, needle, r in hits[:MAX_EXCERPTS]:
        ex = (_kwic(r["text"], _norm(needle)) if needle
              else r["text"][:EXCERPT_CHARS])
        if total + len(ex) > TOTAL_CHARS:
            ex = ex[:max(0, TOTAL_CHARS - total)]
        if not ex:
            break
        total += len(ex)
        score = f"  ({r['score']:.2f})" if "score" in r else ""
        lines.append(f"{len(lines) + 1}. [{_provenance(r)}]{score}\n{ex}")

    head = "query understood: scope=" + ",".join(q["scopes"])
    if q["exact"]:
        head += f' exact="{q["exact"]}"'
    if q["semantic"]:
        head += f" semantic={q['semantic']!r}"
    crumbs = q["ids"] + q["practices"] + [f"'{p}'" for p in q["phrases"]]
    if crumbs:
        head += " breadcrumbs=" + ", ".join(crumbs)
    body = "\n\n".join(lines) if lines else "nothing above floor."
    return (f"<recall_result>\n{head}\n\n{body}\n\n"
            f"This result is yours alone and expires at /close. To keep "
            f"something, speak it in the room or [remember:] it.\n"
            f"</recall_result>")


# --------------------------------------------- the per-circle module state
_PENDING: dict = {}                     # part -> latest private reply
_ROUND_ASKED: set = set()               # parts whose recall ran this round
_ARM = "off"                            # set by circle.py from --recall-arm


def recall_clear() -> None:
    """At circle open. CircleEngine runs circle.py inside a long-lived UI
    process, so module state can outlive a circle — this cannot."""
    _PENDING.clear()
    _ROUND_ASKED.clear()


def recall_round_reset() -> None:
    """At each round's start — the one-recall-per-round cap's boundary."""
    _ROUND_ASKED.clear()


def recall_arm_set(arm: str) -> None:
    global _ARM
    _ARM = arm or "off"


def recall_pending_read(part: str) -> str | None:
    """A PEEK — does not consume. Tests and diagnostics read this; the room
    prompt uses recall_pending_pop() instead, so a reply is never delivered twice
    (B82)."""
    return _PENDING.get(part)


def recall_pending_pop(part: str) -> str | None:
    """Read AND CLEAR this part's private reply in one step — the one call
    render_messages() actually reaches for. Its own docstring already said
    the delivery is singular ("the latest <recall_result>... appended to
    the tail"); until B82 (2026-08-31) nothing enforced that, and a reply
    rode along unexpired on every one of a part's later turns for the rest
    of the circle. A retry within the SAME turn (circle_rounds.part_statement_ask's
    truncation path) captures the popped value once and reuses it for both
    attempts — it is one delivery, not two, even though the API is called
    twice."""
    return _PENDING.pop(part, None)


def recall_apply(part: str, display: str, text: str, *,
                 live: bool) -> tuple[str, bool]:
    """Recognize, execute, and silently remove every EXECUTABLE RECALL
    annotation in ONE statement before it can reach the ROOM — a
    backtick-quoted one (`` `[recall: ...]` ``) is left untouched, prose
    about the syntax rather than a use of it (B82). Returns (stripped_text,
    asked). The returned text is the ROOM's; the caller keeps its own raw
    text for the transcript FILE, bracket intact — apply_remember()'s own
    contract, kept exactly (docs/BNF.md, RECALL).

    NEVER RAISES: a recall failure is a private error reply and a loud
    command-pane line, and the statement proceeds unharmed."""
    matches = _executable_matches(text)
    if not matches:
        return text, False
    room = recall_strip(text)
    try:
        if not live:
            reply = ("<recall_result>\nrecall is unavailable in a dry-run "
                     "circle.\n</recall_result>")
        elif _ARM != "delivered":
            reply = ("<recall_result>\nrecall is not armed this circle.\n"
                     "</recall_result>")
        elif part in _ROUND_ASKED:
            reply = ("<recall_result>\none recall per round — this one was "
                     "not run; ask again next round.\n</recall_result>")
        else:
            body = matches[-1].group(0)  # latest EXECUTABLE bracket wins
            body = body[body.index(":") + 1:-1]
            q = recall_parse(body)
            if q["errors"]:
                reply = ("<recall_result>\nyour recall could not run:\n- "
                         + "\n- ".join(q["errors"])
                         + "\n</recall_result>")
            else:
                t0 = time.monotonic()
                reply = recall_execute(part, q)
                _ROUND_ASKED.add(part)
                seam.emit("command",
                          f"  [{display} recalled — answered in "
                          f"{time.monotonic() - t0:.1f}s, attached to "
                          f"their next turn]")
    except ES.IndexUnavailable as e:
        reply = f"<recall_result>\n{e}\n</recall_result>"
        seam.emit("command", f"  [{display}'s recall failed: {e}]")
    except Exception as e:                                # noqa: BLE001
        reply = ("<recall_result>\nrecall failed on the coordinator's "
                 "side; the circle continues.\n</recall_result>")
        seam.emit("command", f"  [{display}'s recall CRASHED ({e!r}) — "
                             f"answered with an apology, statement kept]")
    _PENDING[part] = reply
    return room, True
