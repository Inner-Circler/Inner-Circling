#!/usr/bin/env python3
"""
quote_as_lands.py — QUOTE-AS-LANDS. Self quotes a part's own words back to
it at the circle prompt; that quoting IS a ratification, and this module
is what records it.

    python coordinator/quote_as_lands.py --demo

RULED 2026-08-13 (R155), VERBATIM: *"Any statement made by self that
includes a quoted <prior statement in this circle by any part> generates
a mark of type 'lands'."* ROUTED 2026-08-19 (R251):
*"Route quote-as-mark at the circle prompt to an unvetted REMEMBER."*

WHY THIS IS NOT A MARK ANY MORE. R155's own mechanism — mint a `lands`
record in marks.py — went MOOT on 2026-08-14 when MARK was retired
wholesale (docs/BNF.md), taking marks.py, the `lands` kind and the
register with it. B38 was struck from the BUILD QUEUE the same week. The
OBSERVATION survived the mechanism (NEXT.md A10 carried it for five
days), and the 2026-08-19 routing is what gives it somewhere to land:
the REMEMBER register, which is already unvetted, already private, and
already the channel Self's own circle-prompt annotation writes to.

RENAMED FROM quote_as_mark.py, 2026-09-01 (D77, ruling): the module's own
name still carried the retired word MARK a fortnight after R155's own
mechanism went moot. Renamed to the word that survived the retirement —
`LANDS_CLASS`, `lands_text()`, `lands_numbers_read()`, and the record's own
`class = "lands"` were already this module's live vocabulary; "MARK" was
the only part of it that was not.

WHOSE RECORD. SELF's — `self/remember.toml`, the B48/R206 channel, NOT
the quoted part's `parts/<p>/remember.toml`. docs/BNF.md's REMEMBER
LIFECYCLE: *"REMEMBER's blast radius is the writing entity's own future
record."* Self is the writing entity here; the part neither typed this
nor chose it, and a Self-authored row under that part's own *"What you
have chosen to remember"* heading (remember_prompt_projection.remember_project()'s BLOCK 4 header)
would be a false attribution in the one place a part reads as its own
voice. So the ratification is recorded where the ratifier can retrieve
it — `/remember-list` — and reaches the part, if at all, the way every other
Self intention reaches one: through a later circle.

NOT VETTED, and that is the ruling's word. Nothing stages, nothing waits
for a checkpoint, nothing appears in the vetting loop; the write happens
at the moment the statement is typed, like a REMEMBER and unlike every
PROPOSE-class annotation.

DETECTION IS SCANNED FROM PROSE, WHICH THIS PROJECT NORMALLY REFUSES.
Every other channel is an explicit bracket, because a scan over prose is
approximately right at best (annotations.py's own note on why annotations beat
inference). The scan is correct HERE for the one reason A10 raised the
channel at all: the signal is something Self does WITHOUT opting in.
An opt-in quote-as-mark would be a different, worse mechanism — the
`[hold]` half of A10 is exactly the story of an opt-in annotation the room
under-used. So it FAILS OPEN, like proposal_unruled_list(): a missed quote
costs nothing (the transcript still holds Self's words verbatim), and a
WRONG mint is what the rules below are shaped to prevent.

    a QUOTED SPAN      "..." or curly quotes, on one line
    MIN_QUOTE_WORDS    3 words, after folding. Two words match half
                       the transcript by accident; three is the
                       smallest span that reliably names one
                       statement. Named here so Self can re-rule it
                       without reading the matcher.
    ATTRIBUTABLE       R155's word is "specific": the folded span must
                       occur in EXACTLY ONE prior part statement. Zero
                       is not a quote of the room; two or more names no
                       one, so neither mints.
    BY A PART          Self quoting Self is not a ratification. Coordinator
                       notes and withheld entries are already outside
                       commands.statement_read(), which is the numbering
                       this cites.
    THIS CIRCLE        `transcript` is the live circle's own, and
                       nothing else is consulted.

CURLY AND STRAIGHT QUOTES FOLD TOGETHER, and that is load-bearing rather
than tidy: a part's statement arrives from the model, which types “ ” and
’ , while Self types " and ' at a terminal. Without the fold the feature
would almost never fire live while every hand-written test passed.

THE STATEMENT NUMBER IS THE ONE `/issue-evidence-list` PRINTS —
commands.statement_read(), 1-based, imported rather than re-derived. That
makes a recorded lands actionable later: the same number
`/issue-evidence-add nNNNN <stmt#>` resolves against.
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "memory"))   # the issue-graph code
                                                  # (R203) — commands.py's
                                                  # own import chain reaches
                                                  # issue_schema, and the
                                                  # late import below is the
                                                  # first thing to need it.

import identity as ID                                          # noqa: E402
import seam                                                    # noqa: E402

MIN_QUOTE_WORDS = 3
LANDS_CLASS = "lands"

# ONE LINE, ONE SPAN. A quoted span that runs across a newline is not
# refused on principle — it is refused because an UNMATCHED quote
# otherwise swallows the rest of the statement and matches nothing, or
# worse, matches something. `[^"\n]+` cannot run away.
QUOTE_RE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')

# The record's own head, built by lands_text() and read back by
# lands_numbers_read(). ONE format, spelled twice on purpose — a builder and
# a parser that must agree, tested against each other, rather than a
# second field the register would have to grow.
LANDS_HEAD_RE = re.compile(r"^lands #(\d+) ")

# Curly punctuation the model emits, folded to what a terminal types.
_FOLD = {
    "“": '"', "”": '"',          # curly double quotes
    "‘": "'", "’": "'",          # curly single quotes / apostrophe
    "–": "-", "—": "-",          # en / em dash
    "…": "...",                       # ellipsis
    " ": " ",                         # non-breaking space
}


def lands_fold(s: str) -> str:
    """The comparison form: curly punctuation folded to straight, case
    folded, whitespace collapsed. Applied to BOTH sides of every match —
    the quoted span and the prior statement — so neither side's typing
    conventions decide whether a quote is recognized."""
    for a, b in _FOLD.items():
        s = s.replace(a, b)
    return " ".join(s.casefold().split())


def lands_spans_read(text: str) -> list[str]:
    """Every quoted span in `text`, in the order typed, verbatim (NOT
    folded — the record quotes what Self actually typed). Spans shorter
    than MIN_QUOTE_WORDS words are dropped here rather than at match
    time, so the threshold is applied in exactly one place."""
    out = []
    for m in QUOTE_RE.finditer(text):
        span = (m.group(1) or m.group(2) or "").strip()
        if len(lands_fold(span).split()) >= MIN_QUOTE_WORDS:
            out.append(span)
    return out


def lands_text(n: int, display: str, span: str) -> str:
    """The record's text. The head is machine-readable (LANDS_HEAD_RE)
    and the tail is for a human reading `/remember-list <n>` — one
    string, so the dedupe key cannot drift away from what is displayed."""
    return f'lands #{n} {display}: "{span}"'


def _part_statements(transcript: list[dict]) -> list[tuple[int, dict]]:
    """(statement number, entry) for every PART statement so far — the
    `/issue-evidence-list` numbering, minus Self's own turns. Late import: this
    module is small and commands.py pulls in the issue schema and the
    help renderer, which nothing here needs until a circle is running."""
    import commands as CM
    return [(n, e) for n, (_i, e) in enumerate(CM.statement_read(transcript), 1)
            if e["speaker"] != ID.SELF_ID]


def lands_detect(transcript: list[dict], text: str) -> list[dict]:
    """Every attributable quote in ONE Self statement, as
    {"n", "display", "span"} — R155's rule, whole. `transcript` must
    hold only PRIOR statements: circle.py calls this before appending
    Self's own, which is also what keeps the numbering stable (the list
    is append-only, so a number, once printed, never moves).

    Silent on both failures. An unattributable span — nothing matched,
    or several statements did — mints nothing and says nothing: Self
    quoting a book, or a phrase two parts both used, is ordinary speech
    and a warning about it would be noise at the one prompt that must
    stay quiet."""
    prior = _part_statements(transcript)
    folded = [(n, e, lands_fold(e["text"])) for n, e in prior]
    out, seen = [], set()
    for span in lands_spans_read(text):
        f = lands_fold(span)
        hits = [(n, e) for n, e, ft in folded if f in ft]
        if len(hits) != 1:
            continue                       # zero, or ambiguous — neither
        n, e = hits[0]
        if n in seen:
            continue                       # two spans, one statement
        seen.add(n)
        out.append({"n": n, "display": e["display"], "span": span})
    return out


def lands_numbers_read(guard) -> set[int]:
    """Which statement numbers already have a lands record THIS circle,
    read back off disk — remember_has_written()'s own discipline, and for the
    same reason: the answer must survive a resume, and the file is the
    only thing that does."""
    import remember_manager as RM
    p = RM.remember_locate(RM.SELF, guard)
    if not p.is_file():
        return set()
    out = set()
    for r in RM._load(p).get(RM.TABLE, []):
        if r.get("class") != LANDS_CLASS or r.get("circle") != guard.ot:
            continue
        m = LANDS_HEAD_RE.match(r.get("text", ""))
        if m:
            out.add(int(m.group(1)))
    return out


def lands_quote_apply(guard, transcript: list[dict],
                         text: str) -> list[dict]:
    """Detect, dedupe, write. Returns the records written (possibly
    none) — never raises on a statement that quotes nothing, which is
    most of them.

    NO CAP OF ITS OWN, and it does not consume Self's. A REMEMBER is one
    per entity per circle because it is the entity's one deliberate note;
    this is a consequence of what Self said, and Self may ratify several
    parts in one turn. What bounds it instead is the dedupe: at most one
    record per QUOTED STATEMENT per circle, so re-quoting the same line
    to press a point does not mint a second row. remember_manager.remember_has_written()
    skips class-bearing records for the other half of the same rule."""
    import remember_manager as RM
    hits = lands_detect(transcript, text)
    if not hits:
        return []
    done = lands_numbers_read(guard)
    written = []
    for h in hits:
        if h["n"] in done:
            continue
        rec = RM.remember_add(RM.SELF, guard,
                     lands_text(h["n"], h["display"], h["span"]),
                     cls=LANDS_CLASS)
        done.add(h["n"])
        written.append(rec)
        seam.emit("command",
                  f"  (lands recorded to self/remember.toml — "
                  f"{h['display']} #{h['n']}, unvetted, private)")
    return written


def main() -> int:
    """--demo renders the matcher against a small transcript. There is
    nothing to verify here that test_quote_as_lands.py does not verify
    properly; this exists so the rules can be READ off a run."""
    # GENERIC SPEAKERS — audit-register.md #1, 2026-09-08. This demo needs two distinct
    # non-Self speakers and nothing more; it used two real part Tags, and this module SHIPS,
    # so every bundle carried them. What the demo shows is the MATCHER, which never looks at
    # a name.
    transcript = [
        {"speaker": "alpha", "display": "Alpha",
         "text": "The dream didn’t stay a dream."},
        {"speaker": "beta", "display": "Beta",
         "text": "The bar was set before the outcome and kept after."},
        {"speaker": ID.SELF_ID, "display": "Self",
         "text": "The dream didn't stay a dream."},
    ]
    said = ('You said "the dream didn\'t stay a dream" and I want to '
            'hold "no" alongside it.')
    print(f"  statement: {said}\n")
    for h in lands_detect(transcript, said):
        print(f'  #{h["n"]} {h["display"]} — "{h["span"]}"')
        print(f"    -> {lands_text(h['n'], h['display'], h['span'])}")
    print(f"\n  (the 1-word span was dropped: MIN_QUOTE_WORDS = "
          f"{MIN_QUOTE_WORDS})")
    print("  (Self's own identical line is not a candidate — parts only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
