#!/usr/bin/env python3
"""
issue_gate.py — invariant gate for the issue graph. Read-only.

    python memory/issue_gate.py            the live graph
    python memory/issue_gate.py <dir>      a PREVIEW, without touching it

WHAT CHANGED 2026-08-03. `issues/` is TOML. Roughly half of this file was
checking that Markdown had parsed at all:

    declared-vs-parsed counts for evidence and edges
        a three-space indent made an entry INVISIBLE rather than invalid, so
        the gate had to count `^- circle_` lines and demand the parsed count
        match. TOML has no such state — a malformed file does not parse, and
        `tomllib` says where.
    backslash-escaped Markdown
        a formatting editor "normalising" `[` and `_` on save. It has no reason
        to touch a `.toml`, and if it did the file would fail to parse loudly.
    an edge type containing `_`
        fell outside `EDGE_RE` entirely and went unchecked. Types are now a
        closed set checked in `issue_schema`.
    sections present, in order, non-empty
        structure, which the schema now holds.

WHAT REMAINS is everything that was never about syntax — claims about the world,
which no format can verify for you:

    VERBATIM      every evidence quote appears exactly in the transcript it
                  cites. Caught an em-dash swapped for a colon at 0.9862
                  similarity.
    ATTRIBUTION   and was said by the part it is filed under. `nNNNN` carried
                  Self's own words under `### <part>` for a month. One
                  exception, RULED 2026-08-18 (R223): an entry filed under
                  `self` may carry `adopted_from = "<part>"`, which must name
                  the part the transcript actually shows — Self declaring he
                  adopted those words as his own. Checked, never waived.
                  ZERO ENTRIES USE IT TODAY. The two it was built for came
                  out the same day (R234): the transcript shows Self spoke
                  both, under a bare `Name:` label this gate could only
                  resolve where `.env` was present. The mechanism stands;
                  its founding premise did not. See `identity.self_installed_tags_read`.
    SPAN          a quote containing another speaker's marker has run past the
                  end of the statement it claims.
    CLOSURE       an edge is legal only when both ends are live.
    ATTESTATION   an attested edge carries a real quote from a real circle; a
                  proposed one names who is being asked.
    DIRECTION     a `leads-to` or `narrower-than` whose Basis makes the TARGET
                  the derived thing is pointing the wrong way — the two types
                  the check actually scopes to. `consequence-of`, named at
                  the check itself and in docs/ISSUE_MODEL.md, is the RETIRED
                  spelling: 8df75e8 replaced it with `leads-to` and reversed
                  its sense, and EDGE_TYPES has not carried it since.
    EVIDENCE      a live node cites something. Ruled 2026-07-29: "I prefer not
                  to record possible issues."
    AGREEMENT     `held_by` and the evidence sections name the same parts.
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "coordinator"))  # atomic_write/identity et al.
import identity as ID                                          # noqa: E402
import issue_schema as S                                       # noqa: E402
import part_roster as R                                              # noqa: E402
import record_paths as _RP                                     # noqa: E402

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ISSUES = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else S.ISSUES

# THE DIRECTORY ARGUMENT NOW MOVES THE WHOLE RECORD, NOT JUST THIS ONE PATH —
# audit-register.md #5, 2026-09-08.
#
# The pre-commit hook runs `memory/issue_gate.py "$gdir/issues"` once per non-default group
# (coordinator/gitrepo.py, the groups/ case). Only ISSUES followed that argument. Everything
# else this gate reasons from stayed bound to the DEFAULT group: issue_source_read()'s
# SELF_DIR arm, issue_schema's circle_transcript() roots, and part_roster's speaker tables.
# So a band node citing `circle_<OT>` or a bare session ref resolved against groups/ifs/,
# and its speaker markers were normalised with the IFS roster — a wrong answer, not a crash.
# groups/band/issues/ holds 0 nodes today, so nothing had fired yet; the gate was passing on
# an empty world and reporting the reassuring answer.
#
# GROUP_SET, NOT A --group FLAG, and that is the point: the hook's existing invocation
# becomes correct with no hook change, because every follower (issue_schema, part_roster,
# REGISTER_CLASS, this module's SELF_DIR below) rebinds off the one call. An argument that
# is NOT a group's issues/ still works exactly as before — the man page calls that the
# preview mode, and it stays.
if len(sys.argv) > 1:
    _resolved = ISSUES.resolve()
    for _g in _RP.group_present_read():
        if _resolved == (_RP.group_tree(_g) / "issues").resolve():
            _RP.group_set(_g)
            ISSUES = _RP.ISSUES_DIR
            break
# One copy, in the schema (2026-08-19, review tier 5 #44) — these were
# the first of three lockstep clones the R176 sweep had to edit together.
# Ruled 2026-08-03 (R061): a `--minimal` circle is a real circle with real
# parts; only its memory is stripped, and the distinct sandbox_ prefix
# keeps every claim resting on a stripped-memory room greppable.
# CIRCLES and SANDBOX_CIRCLES were re-exported from issue_schema here until 2026-09-03 (stage 14,
# R8) and nothing read them; record_paths.py is the one home for the tree's paths now.
# Neither `circle_` nor `sandbox_`: a SESSION RECORD, Self's own words from
# a working session rather than a circle (self/session_2026-08-01_2200.md is
# the only one that exists). self/sessions/ retired 2026-08-13 — it held
# exactly that one file and its own directory added a special-cased path
# for a single record; a session ref now resolves straight under self/.
from record_paths import SELF_DIR                              # noqa: E402

MIN_QUOTE = 2   # ruled 2026-08-01, deliberately near zero: "Yeah, ouch."


def issue_source_read(ref: str) -> pathlib.Path:
    # The circle_/sandbox_ mapping is the schema's (one copy, tier 5
    # #44); the SELF-DIR arm — a bare ref is a session record under
    # self/ — is this gate's own, because only the gate admits those.
    p = S.circle_transcript(ref)
    return p if p is not None else SELF_DIR / f"{ref}.md"


# THE SELF ALTERNATION IS CONFIGURED, NOT LITERAL. It used to read
# a hardcoded alternation, which never matched a recipient's evidence —
# their speaker is their own name, so attribution failed silently rather
# than loudly. ID.self_tags() is the same set the transcript parser uses.
SPEAKER_RE = re.compile(r"^(?:\[To:[^\]]*\]\s*)?"
                        r"(?:\[(?P<b>[A-Za-z][A-Za-z_ ]*?)\]|(?P<p>"
                        + "|".join(re.escape(s) for s
                                   in sorted(ID.self_tags()))
                        + r")\b)"
                        r"(?:\s*\[To:[^\]]*\])?(?:\s*\*\([^)]*\)\*)?\s*:", re.M)
# B29: derived from part_roster.py — free-text normalisation, so every dir name
# and every current-or-historical Tag (lowercased) resolves to its dir.
# ONE DICT, REBUILT IN PLACE at every record_paths.group_set() — a follower, registered after
# part_roster's own, so it reads the roster tables already rescanned (R548: circle.py re-binds
# the group at every open whose parts/ moved; another session's 2026-09-11 close-out). The
# SELF keys are read ONCE, at import, exactly as SPEAKER_RE above reads them: the two must
# agree on who Self is, and self_tags() follows the bound group's self/identity.toml while the
# regex does not (R234 — one graph, two verdicts, is the shape this avoids).
_SELF_KEYS: tuple[str, ...] = tuple(s.lower() for s in ID.self_tags())
SPEAKERS: dict[str, str] = {}


def _speakers_rebind() -> None:
    SPEAKERS.clear()
    SPEAKERS.update({d: d for d in R.DIR_NAMES})
    SPEAKERS.update({tag.lower(): d for tag, d in R.DIR_BY_TAG_ALL.items()})
    SPEAKERS.update({s: "self" for s in _SELF_KEYS})
    SPEAKERS["self"] = "self"


_speakers_rebind()
_RP.group_follow(_speakers_rebind)

# Two transcripts are MIXED-ERA. Every genuine circle.py transcript opens its
# first marker within 1389 characters, so 2000 separates the two cases with
# margin; beyond it the leading region is unparsed rather than Self's.
TOPIC_MAX = 2000

REVERSED_RE = re.compile(
    r"{}\b[^.]{{0,80}}?\b(is|as|was)\b[^.]{{0,40}}?"
    r"\b(specific |one |a |an )?(enactment|instance|case|consequence|"
    r"expression|manifestation|form|version|face|behaviour|behavior)\b"
    r"[^.]{{0,30}}?\bof\b[^.]{{0,30}}?\b(this|these|the deeper|the same)\b")

_CACHE: dict[pathlib.Path, str] = {}


def text_of(p: pathlib.Path) -> str:
    if p not in _CACHE:
        _CACHE[p] = p.read_text(encoding="utf-8", errors="replace")
    return _CACHE[p]


def _room_find(txt: str, q: str):
    """(position, part-or-None) for a quote that is ROOM text split by a
    [remember: ...] bracket — the 2026-08-14 room/record ruling: a
    statement goes to the room with its bracket stripped, and to the FILE
    intact, so an /issue-evidence-add quote (stored as the room text,
    circle.py) is NOT byte-present in a transcript whose statement
    carried a mid-text bracket, and until 2026-08-19 the gate refused the
    whole batch over it (review tier 2 #14).

    Byte-exact `txt.find(q)` stays the ONLY rule for bracket-free
    sources; the caller reaches here after it fails. This loosens
    matching exactly one statement-span at a time, and only for spans
    that carry a bracket: the span's room view (annotations.remember_strip,
    the one spelling the live loop and the resume parser share) is
    compared whitespace-flattened, and a hit settles attribution too —
    the span's own speaker. Returns (-1, None) when nothing matches."""
    import annotations as MK             # coordinator/, on sys.path above
    if not MK.REMEMBER_RE.search(txt):
        return -1, None
    fq = " ".join(q.split())
    if not fq:
        return -1, None
    for a, b, w in issue_speaker_spans_read(txt):
        span = txt[a:b]
        if not MK.REMEMBER_RE.search(span):
            continue
        room = " ".join(MK.remember_strip(span).split())
        if fq in room:
            return a, w
    return -1, None


def issue_speaker_spans_read(text: str):
    """[(start, end, part)]. Regions no marker covers are absent, and are
    reported as UNVERIFIABLE rather than passed."""
    ms = list(SPEAKER_RE.finditer(text))
    if not ms:
        return []
    out = [(0, ms[0].start(), "self")] if ms[0].start() < TOPIC_MAX else []
    for i, m in enumerate(ms):
        who = SPEAKERS.get((m.group("b") or m.group("p")).strip().lower())
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        if who:
            out.append((m.start(), end, who))
    return out


def main() -> int:
    fails: list[str] = []
    oks = unattributable = edge_oks = adopted_quotes = 0
    paths = sorted(ISSUES.glob("*n[0-9][0-9][0-9][0-9].toml"))
    docs = {}
    for p in paths:
        raw = p.read_bytes()
        if b"\r\n" in raw:
            fails.append(f"{p.name}: CRLF line endings; the rest of the graph "
                         f"is LF, and .gitattributes sets `* -text` because "
                         f"conversion would break every sha256 in the project")
        try:
            docs[p] = S.issue_read(p)
        except Exception as e:
            # A malformed node no longer parses PARTIALLY. This is the whole
            # point of the format change: the failure is loud and located.
            fails.append(f"{p.name}: will not parse — {e}")
    ids = {d["id"] for d in docs.values()}
    live = {d["id"] for d in docs.values() if d["status"] == "live"}
    # A ROOT IS LIVE (R429, 2026-09-01) — not a status
    # beside `live` and not an exception to this check. From 2026-08-05
    # (B23) to that date, root was its own status and this line read
    # `legal_end = live | roots`: an edge was legal when both ends were live
    # OR the non-live end was a root. A root's `status` is now `"live"`
    # itself, so `live` already contains both roots and this union is gone —
    # the closure rule is exactly "both ends are live" again, with roots
    # inside that set rather than beside it.
    legal_end = live
    roots = {d["id"] for d in docs.values() if d.get("root")}
    print(f"  {len(docs)} issue(s), {len(live)} live ({len(roots)} root): "
          f"{', '.join(sorted(live))}\n")

    for p, doc in docs.items():
        nid = doc["id"]
        fails += S.issue_verify(doc, p)

        for ref, what in ((doc.get("opened", ""), "Opened"),
                          (doc.get("label_ruled", ""), "Label ruled")):
            if not ref:
                continue
            r = ref.split(" ")[0]                      # one node annotates it
            # A BARE DATE IS A HAND-OPENING, 2026-08-21 (R290): an issue
            # opened by Self at cmd> with no circle running names the day,
            # because there is no transcript to name. Only `opened` takes
            # one; a label ruling always happens in a room.
            if what == "Opened" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r):
                continue
            if not issue_source_read(r).is_file():
                fails.append(f"{p.name}: {what} names a transcript that does "
                             f"not exist ({r})")

        if doc.get("description_history", "").strip() == "":
            fails.append(f"{p.name}: description_history is empty — a status "
                         f"or wording change without the quote that caused it")

        # ---- evidence: verbatim, attributed, unique, and within its span ----
        ev = doc.get("evidence", [])
        # R001 ("evidence is the only thing that opens an issue") was
        # SUPERSEDED 2026-08-21 (R290): Self opens an issue by /issue-add, or
        # approves a part's [proposed: /issue-add …], and it is live with no
        # evidence yet. The one shape that still fails is a live issue that
        # SOMEBODY HOLDS with nothing to show for it — the held_by/evidence
        # agreement below — and an issue nobody holds and nobody quoted is a
        # lead's or a hand-opening's legitimate state, not a defect.
        if doc["status"] == "live" and not ev and doc.get("held_by"):
            fails.append(f"{p.name}: held by {doc['held_by']} with no evidence "
                         f"at all — a held issue cites who said what")
        seen: set[str] = set()
        for e in ev:
            # AS STORED, never unwrapped. Four quotes carry a double
            # space; collapsing it here would fail a quote that is
            # byte-identical to its transcript.
            q = e["quote"]
            if len(q) < MIN_QUOTE:
                fails.append(f"{p.name}: quote shorter than {MIN_QUOTE} chars")
                continue
            src = issue_source_read(e["source"])
            if not src.is_file():
                fails.append(f"{p.name}: cites missing {e['source']} "
                             f"(looked in {src.parent.name}/)")
                continue
            if q in seen:
                fails.append(f"{p.name}: the same quote is attached twice: "
                             f"{q[:50]}...")
            seen.add(q)
            txt = text_of(src)
            span_who = None
            i = txt.find(q)
            if i < 0:
                i, span_who = _room_find(txt, q)   # room/record split — see it
            if i < 0:
                fails.append(f"{p.name}: quote not verbatim in {e['source']}: "
                             f"{q[:50]}...")
                continue
            oks += 1
            # Q5 of self/session_2026-08-01_2200.md: a span
            # containing a speaker marker has run past the end of
            # the statement it quotes and swallowed the next speaker's words.
            if SPEAKER_RE.search(q):
                fails.append(f"{p.name}: quote spans a speaker marker — it has "
                             f"run past the statement it cites: {q[:45]}...")
            who = ("self" if e["source"].startswith("session_") else
                   span_who if span_who is not None else
                   next((w for a, b, w in issue_speaker_spans_read(txt) if a <= i < b),
                        None))
            if who is None:
                unattributable += 1
            elif who != e["part"]:
                # ADOPTION, RULED 2026-08-18. Two entries (n0010, n0033)
                # failed here for a year's worth of good reason and one bad
                # one: the transcript shows a PART spoke the words, and the
                # entry files them under `self` — which is exactly right when
                # Self has declared he adopted them as his own. He has:
                # *"The quote attribution to me was the result of my
                # declaring I had adopted the quote as my own."*
                #
                # The node-level [adopted] block could not say this. It names
                # ONE part per node and means "Self adopted this part's
                # framing for the node"; the count printed below already reads
                # it that way, crediting an entry filed under the ADOPTED
                # part. This is the other direction — one QUOTE, spoken by a
                # part, filed as his — so it is a per-entry field, not a
                # second reading of an existing one.
                #
                # STILL CHECKED, not waived: `adopted_from` must name the part
                # the transcript actually shows, so a wrong adoption claim
                # fails exactly as a wrong `part` does. It only lets the entry
                # say WHY the two differ; it cannot make them agree by
                # assertion.
                if e["part"] == "self" and e.get("adopted_from") == who:
                    adopted_quotes += 1
                else:
                    fails.append(f"{p.name}: quote filed under '{e['part']}' "
                                 f"but '{who}' said it in {e['source']}: "
                                 f"{q[:45]}...")
            elif e.get("adopted_from"):
                # THE OTHER HALF OF "CHECKED, NEVER WAIVED". Everything above
                # runs only where the transcript and the filing DISAGREE — so
                # without this branch, `adopted_from` on an entry the
                # transcript already credits to the filed part would be
                # accepted unread: a false claim in the record, in the one
                # field whose whole purpose is to explain a discrepancy that
                # is not there. Nothing was adopted; the words are already
                # whose the entry says they are.
                fails.append(f"{p.name}: `adopted_from = "
                             f"{e['adopted_from']!r}` but "
                             f"'{who}' — the part it is filed under — said it "
                             f"in {e['source']}: nothing was adopted")

        # ---- held_by agrees with the evidence -------------------------------
        held, gave = set(doc.get("held_by", [])), {e["part"] for e in ev}
        if held - gave:
            fails.append(f"{p.name}: in held_by but no evidence: "
                         f"{sorted(held - gave)}")
        if gave - held:
            fails.append(f"{p.name}: has evidence but not in held_by: "
                         f"{sorted(gave - held)}")

        # ---- edges ----------------------------------------------------------
        for e in doc.get("edges", []):
            tgt = e.get("target")
            if tgt not in ids:
                fails.append(f"{p.name}: dangling issue-relationship -> {tgt}")
                continue
            st = e.get("status")
            if st not in ("attested", "proposed", "retired"):
                fails.append(f"{p.name}: issue-relationship -> {tgt} has status {st!r}")
            if not e.get("basis"):
                fails.append(f"{p.name}: issue-relationship -> {tgt} has no basis — "
                             f"an issue-relationship that cites nothing is an "
                             f"assertion with no standing")
            if st == "attested":
                q = e.get("quote", "")
                m = re.search(r"((?:circle|sandbox)_\d{4}-\d{2}-\d{2}_\d{4})",
                              e.get("basis", ""))
                if not q or not m:
                    fails.append(f"{p.name}: attested issue-relationship -> {tgt} needs a "
                                 f"circle and a quote")
                elif len(q) < MIN_QUOTE:
                    # RULED 2026-08-07. MIN_QUOTE was enforced on evidence
                    # quotes and not on these, for no reason anyone chose —
                    # the edge path simply never got the check. An attested
                    # edge is the STRONGEST claim the graph makes: a circle
                    # ratified this relation, and here is the quote proving
                    # it. `quote = "I"` passed, because "I" is verbatim in
                    # every transcript ever written.
                    #
                    # The threshold's own note is about an edge quote —
                    # "'Yeah, ouch.' is eleven characters and it ratified
                    # the graph's only attested edge" — so the rule was
                    # always meant to reach here.
                    #
                    # Found because a probe that damages "the first quote in
                    # the file" caught this on a node that lists evidence
                    # first and missed it on one that lists edges first.
                    fails.append(f"{p.name}: attested issue-relationship -> {tgt}: "
                                 f"quote shorter than {MIN_QUOTE} chars")
                else:
                    f2 = issue_source_read(m.group(1))
                    if not f2.is_file() or (
                            q not in text_of(f2)
                            and _room_find(text_of(f2), q)[0] < 0):
                        fails.append(f"{p.name}: attested issue-relationship -> {tgt}: "
                                     f"quote not verbatim")
                    else:
                        oks += 1
                        edge_oks += 1
            elif st == "proposed":
                ask = e.get("ask")
                if not ask:
                    fails.append(f"{p.name}: proposed issue-relationship -> {tgt} has no "
                                 f"ask (who confirms it)")
                elif (not isinstance(ask, list)
                      or not all(isinstance(a, str) and a.strip() for a in ask)):
                    # R531: an `ask` is a LIST OF NAMES. A sentence passes the
                    # presence check above, and issue_prompt_projection joins it
                    # character by character into every part's BLOCK 2 —
                    # "asked of: D, o, e, s, ..." — silently, in a real prompt.
                    # Whether each name is a roster Tag is NOT this rule.
                    fails.append(f"{p.name}: proposed issue-relationship -> {tgt}: "
                                 f"ask must be a list of names, got {ask!r:.60}")
            # CLOSURE, for every edge that is not retired.
            #
            # THIS CHECK LIVED INSIDE THE `proposed` BRANCH until 2026-08-05,
            # so an ATTESTED edge to a non-live node was never checked at all
            # — the strongest kind of edge was the one kind exempt from the
            # invariant. Found by a probe written for the root exception:
            # pointing an attested edge at a LEAD passed, and should not have.
            # The exception exposed the hole it was supposed to sit beside.
            if st != "retired" and nid in live and tgt not in legal_end:
                fails.append(f"{p.name}: live {st} issue-relationship -> {tgt}, "
                             f"which is not live. An issue-relationship is "
                             f"legal only when both ends are live (a root "
                             f"counts — it is live)")
            # inv 5: direction. The class of error outlives the fix that
            # caused it — 2 of 10 consequence-of edges in the 2026-07-27
            # derivation were written backwards.
            if e.get("type") in ("leads-to", "narrower-than"):
                m = re.search(REVERSED_RE.pattern.format(re.escape(tgt)),
                              e.get("basis", ""), re.I)
                if m:
                    fails.append(f"{p.name}: issue-relationship `{e['type']}` -> {tgt} looks "
                                 f"REVERSED — its basis makes {tgt} the derived "
                                 f"thing: {m.group(0)[:70]!r}")

        # ---- wikilinks resolve ---------------------------------------------
        blob = "\n".join(str(v) for v in doc.values() if isinstance(v, str))
        for t in re.findall(r"\[\[(n\d{4})(?:\|[^\]]*)?\]\]", blob):
            if t not in ids:
                fails.append(f"{p.name}: dangling link -> {t}")

    print(f"  {oks} quote(s) verified verbatim against their source "
          f"— {oks - edge_oks} evidence, {edge_oks} on attested issue-relationships")
    his = sum(1 for d in docs.values() for e in d.get("evidence", [])
              if e["part"] == "self"
              or (d.get("adopted") or {}).get("part") == e["part"])
    print(f"  {his} of {oks - edge_oks} evidence quote(s) are Self's — his "
          f"own, plus any a part gave that he formally adopted")
    for d in docs.values():
        if d.get("adopted"):
            n = sum(1 for e in d["evidence"] if e["part"] == d["adopted"]["part"])
            print(f"    {d['id']}  {n + sum(1 for e in d['evidence'] if e['part'] == 'self')}"
                  f"/{len(d['evidence'])}  adopting: {d['adopted']['part']}")
    print(f"  {unattributable} of those in transcripts with no speaker markers "
          f"— attribution UNVERIFIABLE, not verified")
    if adopted_quotes:
        print(f"  {adopted_quotes} filed as his over a part's own words, by "
              f"declared adoption (`adopted_from`) — verified against the "
              f"transcript, not waived")
    if fails:
        print(f"\n  {len(fails)} INVARIANT FAILURE(S):")
        for f in fails:
            print(f"    - {f}")
        return 1
    print("  GATE PASS — every invariant satisfied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
