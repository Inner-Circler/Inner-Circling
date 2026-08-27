#!/usr/bin/env python3
"""
mid_term.py — the DISTILLATE. The only per-part thing a prompt carries.

    python coordinator/mid_term.py            what is fresh, what is stale
    python coordinator/mid_term.py --sources <part>
    python coordinator/mid_term.py --refresh  derive the stale ones
    python coordinator/mid_term.py --refresh <part>   just that one
    python coordinator/mid_term.py --refresh --dry-run   no model call
    python coordinator/mid_term.py --lock <part> / --unlock <part>

B28, 2026-08-07: `--refresh` MAKES THE CALL. Until this, the derivation was
"by hand" in the literal sense — a Claude conversation reading `--sources`
output and a human pasting the result through `write()`. That produced the
first fourteen (seven at v1, seven at v3) and is not repeatable: a nightly
cannot hold a conversation. This is the same shape as `circle.py`'s own API
path — `Anthropic()`, `ANTHROPIC_API_KEY` from the environment or `.env`,
one call per part, no caching (each part's sources are read once and never
reused, so there is no shared prefix worth paying to cache).

RULED 2026-08-07, over three exchanges. First, on reading the live-vs-minimal
diff for two parts:

    "Both an order of magnitude. Save these in
     their parts as 'mid_term.md'. I far prefer
     these appending part-identity to including
     relationship or dreaming content
     unprocessed."

Then, catching what the ruled dream destination had broken:

    "prompt-show extracts dreams from long_term.
     It will also need to append new short_term
     ##dreamt entries, yes?"

    "Yes: The right wiring is that `## Dreamt`
     becomes a mid_term source. I do not want to
     lose the semantics of prior relationships or
     dreaming: your derive is correct."

**HE FOUND A HOLE I HAD MADE.** R112 sent dreams to `short_term_<OT>.md` per
his 2026-08-03 ruling. Nothing reads a short_term. So the thirteen `## Dreamt`
sections written that night reached no prompt at all — correct by the ruling,
inert in fact.

The fix is not to append them to `part_identity`. That would put raw dream
prose back in a prompt, which is the thing he asked to stop and the thing
measurement condemned: **of 26,290 characters of live-only Child material,
about 1,400 were actionable.** So the dream becomes a SOURCE, and the
distillate is what travels.

```
SOURCES, per part
    long_term.md      settled identity and the
                      historical dream corpus
    dreams.toml       the migrated dream corpus,
                      unsettled entries
    short_term_*.md   the `## Dreamt` sections,
                      newest circles first
    remember.toml     the part's own reflexive
                      chain (R178, 2026-08-15)
        |
        v  derive (one model call)
    mid_term.md       what reaches part_identity
```

**`part_relationships.toml` DROPPED as a source, 2026-08-22** — the operator: *"I do not want it
in the prompt context in any block. Studies showed it was not helpful."* It was a source from
v5 (2026-08-15) until here; the 2026-08-07 ruling below that first named it ("I do not want to
lose the semantics of prior relationships or dreaming") is superseded on this one point, not
struck — dreaming's own semantics are unaffected. See RULINGS.md for the entry and
`docs/BNF.md`'s `<relationships_distillate>` for the prompt-side half (the direct BLOCK 3
projection, removed earlier the same day by R302).

**THE NAMES NOW MEAN WHAT THEY SAY.** `long_term` is the historical record and
stops growing — dreams go to short_terms. `short_term_<OT>` is one circle and
its dream, append-only. `mid_term` is the standing distillate, rewritten
whenever a source moves.

STALENESS IS A CONTENT HASH, NOT A DATE. `long_term.md` carries no per-record
timestamps, so there is nothing to compare a date against.
The hash covers every source, which means **a new circle's dream invalidates
that part's mid_term automatically** — the trigger fires on its own rather
than on someone remembering.

`prompt_version` is in the hash because the prompt is an input to the
derivation exactly as the sources are — the same reasoning `asks_extract.py`
applied to its own fragments before it was retired 2026-08-12.

**THERE IS NO VERIFIER HERE, AND THAT IS RULED, NOT MISSING.** I proposed one:
the derivation would return a distinctive phrase per heading, and a check would
locate each in the sources. Self denied it, 2026-08-07:

    "The checkable claim would verify the presence
     of origins that large themselves carry the
     authority of an LLM derivation at circle time.
     The entire system is placing substantial trust
     in LLM derivations."

**He is right, and the distinction is where a guard can be anchored at all.**
An ask fragment's backing quote is located in a part's STATEMENT — an event
that happened in a room at a time, recorded as it was said. That anchors to
something outside the derivation. A `mid_term` source is `long_term.md` and a
`## Dreamt` section, which are themselves derivations. Locating a phrase in one
would prove that two derivations agree, not that either is true — a guard
checking derivation against derivation is theatre with a passing exit code.

Where the trust actually sits is stated plainly instead: the distillate is
Claude's, the sources it came from are named in the front matter by hash, and
the record it was made from is untouched and readable.

**NOTHING HERE DELETES A SOURCE.** The distillate is a projection; the record
keeps everything. If a derivation is wrong, the fix is another derivation, and
the material it was made from has not moved.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)

PROMPT = "v9"   # v9, 2026-08-25: SYSTEM now says RETURN THE WHOLE DOCUMENT
                # EVERY TIME. v8 told the model to "revise it incrementally"
                # and never said the reply REPLACES the file, so a model with
                # little to change answered with little — and the caller's
                # `len(body) < BUDGET // 2` check read that as dropped content
                # and refused to write. Measured at the operator's live close
                # of circle_2026-08-25_1719: SIX of seven parts SUSPECT at 0,
                # 0, 203 and 2,240 chars against a 5,000 budget, the seventh
                # (whose sources had moved most) whole at 3,483. Nothing was
                # lost — a SUSPECT derivation is not written — but six parts'
                # identities did not move for that circle. The bump re-derives
                # all seven, as every bump does.
                # v8, 2026-08-22 (DESIGN_V2 "DREAMING extension"): derive()
                # gains two more inputs to the CALL, neither hashed (see
                # sources() — hashing either would make the derivation
                # invalidate itself the moment it wrote its own output):
                # the part's CURRENT mid_term.md, so the model can revise
                # incrementally rather than re-derive from scratch every
                # time; and remember.scored_order(part), the
                # salience/chain-depth-bounded record order, so a
                # resolved/charged memory outweighs a merely-newer passing
                # one in what the distillate keeps. PROMPT rides the hash
                # (source_hash appends "|{MODEL}/{PROMPT}"), so — same as
                # every prior bump — every part's mid_term reads stale
                # immediately and the next refresh re-derives all seven
                # under the new SYSTEM prompt, not only the ones whose
                # sources() text actually moved.
                # v7, 2026-08-22: part_relationships.toml DROPPED as a
                # source (the operator: "I do not want it in the prompt
                # context in any block. Studies showed it was not
                # helpful."). SYSTEM no longer asks the model to weigh
                # relationship material at all; every part's hash moves,
                # so the next refresh re-derives all seven from a genuinely
                # smaller source set — not a stale cache serving old
                # content under a new label.
                # v6, 2026-08-15: remember.toml added as the FIFTH source
                # (R178 — a DREAMING write now flips this hash, which is
                # what makes phase 2's refresh step fire for exactly the
                # parts that dreamed). v5, same day: relationships source
                # is the NEWEST relationships.toml record (relationships.md
                # converted and retired — coordinator/relationships.py).
                # v4, 2026-08-12: dreams.toml added as a source (dream
                # corpus moved out of long_term.md); SYSTEM gained the
                # identity-core anti-duplication line
MODEL = "claude-sonnet-5"
BUDGET = 5000        # chars. The two hand-derived examples ran 3,094 and 4,113.

# RAISED 2026-08-26 from 2,000 (R354, B68's diagnosis): claude-sonnet-5
# THINKS ADAPTIVELY BY DEFAULT and its thinking tokens COUNT AGAINST
# max_tokens — the fact inter_circle's DREAM_MAX_TOKENS note records from
# 2026-08-21, which this call site never received. At 2,000, instrumented
# calls stopped at max_tokens on every part measured: judge's thinking
# consumed the whole budget (0 text chars, SUSPECT-refused), mourner's left
# a document cut mid-sentence that PASSED the half-budget floor, and a live
# /close starved 4 of 7 derivations. Sized like DREAM_MAX_TOKENS: the
# visible document targets BUDGET (5,000 chars, ~1,250 tokens); the rest is
# the thinking's room.
DERIVE_MAX_TOKENS = 8000

FRONT = "<!-- mid_term {hash} · {model} · {when} · from {n} chars -->"

# THE DERIVATION, recorded here because it is an input to the result exactly
# as the sources are — and because the first seven were produced by running
# this by hand, so the method must be legible rather than remembered.
#
# Ruled 2026-08-07 across two exchanges. Self, on the exclusions:
#
#     "Ignore episodic narrative, affective state
#      formulas, provenance metadata, rationales,
#      derivations, self-assessments, relationship
#      histories, and all non-actionable elements.
#      Report only actionable semantic content."
#
# and on what must survive:
#
#     "I do not want to lose the semantics of prior
#      relationships or dreaming."
#
# Those two together were the whole specification: keep the STANCE a part
# holds toward each other part, drop the dated turning points that produced
# it; keep what a dream concluded, drop the evening it happened in.
#
# THE RELATIONSHIPS HALF IS SUPERSEDED, 2026-08-22 — the operator: "I do
# not want it in the prompt context in any block. Studies showed it was
# not helpful." Not struck: dreaming's own semantics are unaffected, and
# this quote stands as the record of what was first asked for. What
# changed is which of the two the derivation now keeps.
SYSTEM = """\
You are distilling one part's accumulated record into the only per-part text
that will reach its prompt. The sources are its long_term.md and every
`## Dreamt` section it has written.

Report ONLY actionable semantic content — a test it can run, a distinction that
changes what it concludes, a claim it holds as settled, a stance toward another
part, a watch aimed at itself.

IGNORE: episodic narrative, affective state formulas, provenance metadata,
rationales, derivations, and self-assessments.

**DO NOT REPEAT WHAT THE SHARED BLOCK ALREADY SAYS.** `process_core.md` reaches
every part in `circle_identity`, and it already carries the honesty mandate,
the Self-energy test, and each part's named watch. A per-part restatement of a
commitment every part already reads is duplication wearing identity's clothes —
it costs seven copies of one sentence and makes the distillate look larger than
it is. Include a watch here ONLY where this part's record has sharpened it past
what the shared block says, and then only the sharpening.

**DO NOT REPEAT WHAT `long_term.md` ITSELF ALREADY SAYS, EITHER.** As of
2026-08-12 `long_term.md` reaches every part's prompt unconditionally,
alongside you, not only as a fallback — restating its identity-core
sections here is the same duplication as restating `process_core.md`, one
level down. You may sharpen or extend a claim `long_term.md` makes; do not
restate it.

KEEP THE SEMANTICS OF DREAMING. What a dream CONCLUDED is actionable; the
evening it happened in is not.

PREFER THE PART'S OWN WORDS. Many of these lines are already its own
formulations and should survive verbatim. Do not coin a new phrase for
something the part has already named.

DO NOT GIVE IT ANYTHING IT DOES NOT HAVE. No test it never articulated, no
stance it never took. If a source holds nothing actionable, say so rather than
filling the space.

Include a live-edge section only if the record actually has one open.

OPEN FROM THE IDENTITY CORE. What the part fundamentally is comes from the
sections of `long_term.md` above `## Dream entries` — the material no nightly
authored. Do not let the most recent circle recolour it: a dream sharpens or
extends what a part is, it does not redefine it.

Address the part as "you". Group under short headings, its own purpose and
watches first. Target {budget} characters and treat a result under half that
as evidence something was dropped rather than as economy.

Write so it would still make sense to the part a year from now, with no memory
of the circles it came from.

WHEN YOUR CURRENT mid_term.md IS INCLUDED BELOW, revise it incrementally
rather than re-deriving from nothing: keep what still holds, drop only what a
newer source has actually superseded, and add what changed. Do not reorganize
or reword a line that no source below has touched — an unforced rewrite of
something still true is a loss, not an update.

RETURN THE WHOLE DOCUMENT EVERY TIME, revision or not. Your reply REPLACES the
file: it is not a patch, not a list of changes, and not a note about what you
left alone. Carry every line you are keeping through into your answer. If
nothing has changed at all, return the current text unchanged. A reply shorter
than the document you were given is read as dropped content and is refused —
the part then keeps its old distillate and learns nothing from this circle.

WHEN A SALIENCE-RANKED REMEMBER LIST IS INCLUDED, it orders this part's own
memories by self-reported charge (resolved and charged ahead of passing),
never by a coordinator score of what matters. Treat "resolved" and "charged"
entries as more likely to deserve a place in the distillate than "passing"
ones — a steer toward attention, not a ranking that overrides your own
judgment of what is actionable."""


def path(part: str) -> pathlib.Path:
    return ROOT / "parts" / part / "mid_term.md"


def dreamt(part: str) -> list[tuple[str, str]]:
    """Every `## Dreamt` section this part has, newest circle first.

    Ruled 2026-08-03 and first written 2026-08-07: a dream belongs to the
    circle it came from, not to `long_term.md`. This is the reader that makes
    those sections reachable — before it, they were written and read by
    nothing."""
    out = []
    for f in sorted((ROOT / "parts" / part).glob("short_term_*.md"),
                    reverse=True):
        text = f.read_text(encoding="utf-8")
        ot = f.stem.replace("short_term_", "")
        # EVERY `## Dreamt` IN THE FILE, not the first. The first version
        # split once and cut at the next `## `, so a second dream section —
        # a re-dream of the same circle — was silently dropped and never
        # reached the hash. The probe that appended one caught it on its
        # first run, which is the only reason this reads as it does.
        rest = text
        while "\n## Dreamt" in rest:
            body = rest.split("\n## Dreamt", 1)[1]
            nxt = body.find("\n## ")
            out.append((ot, (body[:nxt] if nxt >= 0 else body).strip()))
            rest = body[nxt:] if nxt >= 0 else ""
    return out


def dreams_toml(part: str) -> list[tuple[str, str, str]]:
    """[(date, title, content), ...] for every UNSETTLED dream in
    parts/<part>/dreams.toml. Settled entries are excluded — already
    integrated history, not fresh signal for a distillate, same rule
    recency.py's entries() applies.

    Migrated 2026-08-12: the historic dream corpus moved out of
    long_term.md's `## Dream entries` (see RULINGS.md). This is that
    corpus's replacement source; `dreamt()` below still covers the newer,
    not-yet-condensed material sitting in short_term's `## Dreamt`."""
    import self_schema as SS
    p = ROOT / "parts" / part / "dreams.toml"
    if not p.is_file():
        return []
    doc = SS.load(p)
    return [(e["date"], e["title"], SS.unwrap(e.get("content", "")))
            for e in doc.get("dreams", []) if e["section"] == "dream"]


def sources(part: str) -> dict:
    """Everything the derivation reads, and nothing else.

    Returned as text so the hash and the model see exactly the same bytes —
    a hash over one view and a call over another is how a cache silently
    serves the wrong thing."""
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    base = ROOT / "parts" / part
    lt = C.strip_settled(C.read_ro(base / "long_term.md"))
    dt = dreams_toml(part)
    dr = dreamt(part)
    # FOURTH SOURCE, R178, built with the phase-2 driver 2026-08-15 (was the
    # fifth until part_relationships.toml dropped out, 2026-08-22): the
    # part's whole remember register, file order. Any write — a live
    # [remember: ...] or a DREAMING record — flips this hash, which is the
    # staleness trigger that makes phase 2's refresh step re-derive
    # exactly the parts that moved.
    import remember as RM
    mem = [r.get("text", "") for r in RM.entries(part)]
    return {
        "long_term": lt,
        "dreams": dt,
        "dreamt": dr,
        "remember": mem,
        "text": "\n\n".join(
            [f"# long_term.md\n{lt}"]
            + [f"# Dream {date} — {title}\n{content}"
               for date, title, content in dt]
            + [f"# Dreamt · circle {ot}\n{body}" for ot, body in dr]
            + ([f"# Remembered\n" + "\n".join(f"- {t}" for t in mem)]
               if mem else [])),
    }


def source_hash(part: str, src: "dict | None" = None) -> str:
    """`src` reuses an assembly the caller already paid for (2026-08-19,
    review tier 5 #52: state() assembled every source file twice per
    call — once itself, once through here — so the prompt path paid
    double per part per build and --refresh about six-fold). Threading
    the SAME src through derive() and write() also closes a race: the
    hash stamped on a distillate now describes the bytes the derivation
    actually read, not a fresh read of disk that may have moved
    mid-refresh."""
    text = (src if src is not None else sources(part))["text"]
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    h.update(f"|{MODEL}/{PROMPT}".encode("utf-8"))
    return h.hexdigest()[:16]


def _front(part: str) -> dict:
    p = path(part)
    if not p.is_file():
        return {}
    first = p.read_text(encoding="utf-8").splitlines()[:1]
    if not first or not first[0].startswith("<!-- mid_term "):
        return {"legacy": True}
    bits = first[0].strip("<!- >").split(" · ")
    return {"hash": bits[0].replace("mid_term ", "").strip(),
            "model": bits[1].strip() if len(bits) > 1 else "?",
            "when": bits[2].strip() if len(bits) > 2 else None}


def refresh_cutoff(part: str) -> str | None:
    """The `when` this part's CURRENT mid_term.md was derived at — the
    cutoff BLOCK 3/4's remember split uses (B44, remember.py's
    project_settled()/project_tail()) to decide 'existed at the last
    refresh' vs 'written since'. `when` is second-precision, no tz suffix
    (write()'s own `now()[:19]`); a remember record written the SAME
    second as a refresh sorts into the tail, not the settled window — the
    safe direction, since the tail is visible and uncached either way.
    None when there is no real front matter to read one from (absent or
    legacy) — the caller's job is to treat that as nothing settled yet,
    not to guess one."""
    return _front(part).get("when")


def locked(part: str) -> bool:
    # splitlines() of an EMPTY file is [], and [0] then raised IndexError
    # straight up the prompt-assembly path (state() -> block()), crashing
    # every circle open for that part until the file was hand-deleted —
    # and a zero-byte mid_term.md is reachable: write() is a plain
    # write_text, so a crash or full disk mid-write truncates. _front()
    # right above already guards the same read; this one didn't
    # (2026-08-18 review, tier 2 #22).
    p = path(part)
    if not p.is_file():
        return False
    lines = p.read_text(encoding="utf-8").splitlines()
    return bool(lines) and "mid_term_locked" in lines[0]


def state(part: str, src: "dict | None" = None) -> tuple[str, dict]:
    """`fresh` | `stale` | `absent` | `legacy` | `locked`, and the numbers.
    `src` reuses a caller's assembly — see source_hash()."""
    src = src if src is not None else sources(part)
    info = {"part": part, "chars": len(src["text"]),
            "dreams": len(src["dreams"]), "dreamt": len(src["dreamt"]),
            "hash": source_hash(part, src)}
    if not path(part).is_file():
        return "absent", info
    if locked(part):
        return "locked", info
    f = _front(part)
    if f.get("legacy"):
        # A mid_term written before the hash existed. It is real content and
        # must not be discarded, but nothing can say what it was made from.
        return "legacy", info
    return ("fresh" if f.get("hash") == info["hash"] else "stale"), info


def block(part: str) -> tuple[str, str]:
    """WHAT THE PROMPT PATH CALLS. Never derives, never calls a model.

    Returns ("", reason) when there is no distillate — and the caller must
    fall back to the raw sources rather than send a part an empty identity.
    Losing a part's identity to a missing cache file would be the worst
    failure available here, and it is one line of carelessness away."""
    st, info = state(part)
    if st == "absent":
        return "", "no mid_term"
    text = path(part).read_text(encoding="utf-8")
    if text.startswith("<!-- mid_term "):
        text = text.split("\n", 1)[1].lstrip("\n")
    return text, st


def write(part: str, body: str, locked_by_self: bool = False,
          src: "dict | None" = None) -> None:
    when = __import__("self_schema").now()[:19]
    # `src` must be the assembly the DERIVATION read (refresh threads it
    # through) so the stamped hash describes what the body was actually
    # made from — a fresh read here could hash sources that moved
    # mid-refresh, labeling a stale distillate current (tier 5 #52).
    src = src if src is not None else sources(part)
    head = FRONT.format(hash=source_hash(part, src), model=f"{MODEL}/{PROMPT}",
                        when=when, n=f"{len(src['text']):,}")
    if locked_by_self:
        head = head[:-3] + " · mid_term_locked -->"
    path(part).write_text(head + "\n\n" + body.lstrip("\n"),
                          encoding="utf-8", newline="\n")


RATE_IN = 2.00          # $/M input tokens, no cache — verified against circle.py
RATE_OUT = 10.00        # $/M output tokens, 2026-07-26; rise 2026-09-01


def _client():
    """Same construction as circle.py's --live path: env var, else .env,
    else fail with the same message. One client, reused across parts."""
    import os
    from anthropic import Anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except ImportError:
            pass
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("set ANTHROPIC_API_KEY (env var or project .env)")
    return Anthropic()


def derive(client, part: str, src: "dict | None" = None) -> tuple[str, object]:
    """ONE model call: this part's sources in, the distillate body out.

    No caching — sources are read once per part and never reused, so there
    is no shared prefix a cache would pay off. Returns (body, usage,
    stop_reason) so the caller can report cost and refuse a truncated
    result; write() is a separate step so a caller can
    inspect the body (length, `## Dream entries` leakage) before it lands.
    `src` is the assembly refresh() already made — see source_hash().

    TWO MORE INPUTS RIDE THE CALL, NEITHER THE HASH (DESIGN_V2's "DREAMING
    extension", step 8, 2026-08-22): the part's CURRENT mid_term.md, read
    fresh here rather than threaded through `src` — putting it in
    sources()["text"] would mean every derivation invalidates its own
    hash the moment it writes, so the part is permanently stale; and
    remember.scored_order(part), the salience/chain-depth-bounded record
    order — already read from a register sources() reads too (a live
    write to remember.toml already flips the hash), so ordering it
    differently for the model to SEE needs no hash of its own either.

    THE PRIOR ONLY RIDES THE CALL WHEN IT WAS DERIVED UNDER THIS SAME
    MODEL/PROMPT. Otherwise a PROMPT bump's own purpose — the next
    refresh re-derives from sources() alone, "not a stale cache serving
    old content under a new label" (v7's comment, part_relationships) —
    would be defeated by "revise this incrementally" feeding the
    old-prompt distillate straight back in. The refresh right after a
    bump derives from scratch, exactly as every prior bump did; only the
    refresh after THAT one sees a prior worth revising."""
    src = src if src is not None else sources(part)
    user_parts = [src["text"]]
    prior = path(part)
    # ONLY WHEN THE PRIOR WAS DERIVED UNDER THIS SAME MODEL/PROMPT. A PROMPT
    # bump (like v7 -> v8, DESIGN_V2 itself) exists to purge content the old
    # prompt kept that the new one should not (v7's own comment: "not a
    # stale cache serving old content under a new label") — feeding an
    # old-prompt distillate into "revise this incrementally" would let
    # exactly that purged content survive the bump it was supposed to die
    # in. The FIRST refresh after any bump derives from sources() alone,
    # same as before this extension; incremental revision starts from the
    # refresh after that.
    if prior.is_file() and _front(part).get("model") == f"{MODEL}/{PROMPT}":
        prior_body, _st = block(part)
        if prior_body:
            user_parts.append(
                f"# Your current mid_term.md (revise this incrementally)\n"
                f"{prior_body}")
    import remember as RM
    ordered = RM.scored_order(part)
    if ordered:
        lines = "\n".join(
            f"- ({r.get('salience', 'passing')}) {r['text']}"
            for r in ordered[:20])
        user_parts.append(
            f"# Your remember register, salience-ranked (most weight first)"
            f"\n{lines}")
    resp = client.messages.create(
        model=MODEL,
        max_tokens=DERIVE_MAX_TOKENS,
        system=SYSTEM.format(budget=BUDGET),
        messages=[{"role": "user", "content": "\n\n".join(user_parts)}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, resp.usage, getattr(resp, "stop_reason", None)


def suspect_reasons(body: str, stop_reason: "str | None") -> list[str]:
    """Why a derivation must NOT be written; [] when it may be. Factored
    out of refresh() so the gate itself is testable without a client.

    `stop_reason == "max_tokens"` is TRUNCATION and refuses regardless of
    length: the model's adaptive thinking spends from the same budget (see
    DERIVE_MAX_TOKENS), so a capped reply is a document cut mid-sentence.
    B68's probes watched one pass the half-budget floor below and land in a
    part's prompt — the floor catches starvation; this catches the cut."""
    bad = []
    if stop_reason == "max_tokens":
        bad.append(f"stopped at max_tokens ({DERIVE_MAX_TOKENS:,}) — the "
                   f"document is truncated, whatever its length")
    if len(body) < BUDGET // 2:
        bad.append(f"{len(body):,} chars, under half the {BUDGET:,} "
                   f"budget — check for dropped content")
    import ifs_model as IFS          # IDENTITY_END — the long_term.md boundary
    if IFS.IDENTITY_END in body:
        bad.append(f"'{IFS.IDENTITY_END}' leaked into the body — the "
                   f"derivation reached past the identity boundary")
    return bad


def refresh(only: str | None = None, dry_run: bool = False,
           say=print) -> int:
    """Derive every stale/absent/legacy part, or just `only`. Skips `locked`
    and `fresh` — locked is Self's, fresh has nothing to do.

    Returns the number of FAILURES (a result under half BUDGET, or the raw
    `## Dream entries` heading leaking into the body) — not the number
    derived, so a caller can use the return value as an exit code.

    `say` defaults to `print`, so a direct/CLI call is unchanged. A caller
    that routes output elsewhere (inter_circle.py's own `say`, which under
    circle.py's live /close is `emit("command", ...)`) passes its own —
    every line here used to go straight to stdout regardless of the
    caller's own routing, invisible under circling's alternate screen
    buffer even though the driver's own summary line already routed
    correctly. Every live close refreshes mid_term for whichever parts
    moved, so this was not a rare case."""
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    targets = [only] if only else list(C.PART_TAGS)
    todo = []
    for p in targets:
        # ONE assembly per part, threaded through state -> derive ->
        # write (tier 5 #52) — the scan alone used to assemble twice,
        # and the whole path six-fold. Carrying `src` in the todo tuple
        # holds each part's source text in memory for the run (~100KB a
        # part at today's sizes) — fine at this scale, and it is exactly
        # what makes the stamped hash describe the derived bytes.
        src = sources(p)
        st, info = state(p, src)
        if st in ("stale", "absent", "legacy"):
            todo.append((p, info, src))
        elif st == "locked":
            say(f"  {p}: locked — skipped")
        elif only:
            say(f"  {p}: already fresh — nothing to do")
    if not todo:
        say("  nothing to derive")
        return 0

    client = None if dry_run else _client()
    t_in = t_out = 0
    fails = 0
    for p, info, src in todo:
        say(f"  {p}: deriving from {info['chars']:,} source chars"
            f"{' (dry run)' if dry_run else ''}...")
        if dry_run:
            say(f"    (skipped — no model call)")
            continue
        body, usage, stop = derive(client, p, src)
        t_in += getattr(usage, "input_tokens", 0) or 0
        t_out += getattr(usage, "output_tokens", 0) or 0
        bad = suspect_reasons(body, stop)
        if bad:
            fails += 1
            say(f"    SUSPECT — {'; '.join(bad)}")
            say("    NOT written — rerun by hand or inspect before forcing.")
            continue
        write(p, body, src=src)
        say(f"    wrote {len(body):,} chars, hash {source_hash(p, src)}")

    if not dry_run and (t_in or t_out):
        cost = (t_in * RATE_IN + t_out * RATE_OUT) / 1_000_000
        say(f"\n  {t_in:,} in + {t_out:,} out tok, ~${cost:.3f}")
    return fails


def listing() -> str:
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    out = [f"  {'part':<14}{'state':<9}{'sources':>9}{'dreams':>8}"
          f"{'dreamt':>8}  hash"]
    for p in C.PART_TAGS:
        st, info = state(p)
        out.append(f"  {p:<14}{st:<9}{info['chars']:>9,}{info['dreams']:>8}"
                   f"{info['dreamt']:>8}  {info['hash']}")
    return "\n".join(out)


def main() -> int:
    a = sys.argv[1:]
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    if a and a[0] == "--sources":
        part = a[1]
        src = sources(part)
        print(f"  {part}: {len(src['text']):,} chars")
        print(f"    long_term      {len(src['long_term']):>8,}")
        for date, title, content in src["dreams"]:
            print(f"    Dream {date} {title[:30]:<30}{len(content):>8,}")
        for ot, body in src["dreamt"]:
            print(f"    Dreamt {ot:<12}{len(body):>8,}")
        return 0
    if a and a[0] == "--refresh":
        rest = a[1:]
        dry_run = "--dry-run" in rest
        rest = [x for x in rest if x != "--dry-run"]
        only = rest[0] if rest else None
        return refresh(only=only, dry_run=dry_run)
    if a and a[0] in ("--lock", "--unlock"):
        # TOGGLE THE MARKER ON THE EXISTING FRONT MATTER — never re-stamp.
        # Until 2026-08-19 this branch rewrote the old body through write(),
        # which stamps hash=source_hash(part) computed NOW: locking (or
        # unlocking) a part whose sources had moved re-labeled a stale
        # distillate as fresh, and refresh() then skipped it indefinitely.
        # The lock is a one-word edit to the head line; the hash, model and
        # when it records must stay the derivation's own.
        part = a[1]
        p = path(part)
        if not p.is_file():
            print(f"  {part} has no mid_term")
            return 1
        text = p.read_text(encoding="utf-8")
        head, _, rest = text.partition("\n")
        if not head.startswith("<!-- mid_term "):
            print(f"  {part}'s mid_term has no front matter (legacy) — "
                  f"derive it first (--refresh {part}), then lock")
            return 1
        if a[0] == "--lock":
            if "mid_term_locked" not in head:
                # the same construction write(locked_by_self=True) uses,
                # so locked() and _front() see one shape from both writers
                head = head[:-3] + " · mid_term_locked -->"
        else:
            head = head.replace(" · mid_term_locked -->", "-->")
        p.write_text(head + "\n" + rest, encoding="utf-8", newline="\n")
        print(f"  {part} {'LOCKED' if a[0] == '--lock' else 'unlocked'}")
        return 0
    print(listing())
    stale = [p for p in C.PART_TAGS if state(p)[0] in ("stale", "absent",
                                                       "legacy")]
    print(f"\n  {len(stale)} of {len(C.PART_TAGS)} need derivation"
          + (f": {', '.join(stale)}" if stale else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
