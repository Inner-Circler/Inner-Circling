#!/usr/bin/env python3
"""
part_mid_term_manager.py — the DISTILLATE. The only per-part thing a prompt carries.
(mid_term.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)

    python coordinator/part_mid_term_manager.py            what is fresh, what is stale
    python coordinator/part_mid_term_manager.py --sources <part>
    python coordinator/part_mid_term_manager.py --refresh  derive the stale ones
    python coordinator/part_mid_term_manager.py --refresh <part>   just that one
    python coordinator/part_mid_term_manager.py --refresh --dry-run   no model call
    python coordinator/part_mid_term_manager.py --lock <part> / --unlock <part>

B28, 2026-08-07: `--refresh` MAKES THE CALL. Until this, the derivation was
"by hand" in the literal sense — a Claude conversation reading `--sources`
output and a human pasting the result through `part_mid_term_write()`. That produced the
first fourteen (seven at v1, seven at v3) and is not repeatable: a nightly
cannot hold a conversation. One call per part, no caching (each part's
sources are read once and never reused, so there is no shared prefix worth
paying to cache).

THE CALL GOES THROUGH llm_client SINCE 2026-08-28 (stage 1 of the provider
socket). This paragraph used to say the module built its own client the way
`circle.py` does — env var, else `.env` — and that was exactly the
duplication stage 1 removes: `llm_client.stream_client_build()` is the one builder,
`call_once()` the one call, so a distillation now rides the retry ladder and
reaches the meter like everything else.

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
    short_term_*      the `## Dreamt` sections (.md) / `[[dreamt]]` tables (.toml, R434),
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
struck — dreaming's own semantics are unaffected. See rulings/ for the entry and
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

import concurrent.futures
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

# THE ONE MODULE-LEVEL PROJECT IMPORT, and it is deliberate against this file's
# own lazy-import convention (2026-08-28, R379). MODEL and the RATE_* pair
# (read as LC.MODEL / LC.RATE_IN / LC.RATE_OUT at the use; local aliases
# until 2026-09-03) were LITERAL COPIES of llm_client's, and a price or a model
# id written twice is one edit away from two answers — the defect ifs_model's
# REGISTERS dict already records for circle_history's cap. llm_client is light at
# import (os, threading, time, seam, paths; `anthropic` is lazy inside its own
# functions), so this costs no import-time weight and closes no cycle:
# prompt_build already imports it at module level.
import llm_client as LC                                        # noqa: E402
import LLM_response_disassembler as RD                         # noqa: E402
import setting_manager as SET                                         # noqa: E402

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
                # v8, 2026-08-22 (DESIGN_V2 "DREAMING extension"): part_mid_term_derive()
                # gains two more inputs to the CALL, neither hashed (see
                # part_mid_term_sources_read() — hashing either would make the derivation
                # invalidate itself the moment it wrote its own output):
                # the part's CURRENT mid_term.md, so the model can revise
                # incrementally rather than re-derive from scratch every
                # time; and remember_prompt_projection.remember_rank(part), the
                # salience/chain-depth-bounded record order, so a
                # resolved/charged memory outweighs a merely-newer passing
                # one in what the distillate keeps. PROMPT rides the hash
                # (source_hash appends "|{LC.MODEL}/{PROMPT}"), so — same as
                # every prior bump — every part's mid_term reads stale
                # immediately and the next refresh re-derives all seven
                # under the new SYSTEM prompt, not only the ones whose
                # part_mid_term_sources_read() text actually moved.
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
BUDGET = SET.setting_value_read("mid_term_budget", 5000)   # chars. The two hand-derived
                     # examples ran 3,094 and 4,113.

# RAISED 2026-08-26 from 2,000 (R354, B68's diagnosis): claude-sonnet-5
# THINKS ADAPTIVELY BY DEFAULT and its thinking tokens COUNT AGAINST
# max_tokens — the fact inter_circle's DREAM_MAX_TOKENS note records from
# 2026-08-21, which this call site never received. At 2,000, instrumented
# calls stopped at max_tokens on every part measured: judge's thinking
# consumed the whole budget (0 text chars, SUSPECT-refused), mourner's left
# a document cut mid-sentence that PASSED the half-budget floor, and a live
# /close starved 4 of 7 derivations.
# RAISED AGAIN 2026-08-30 from 8,000, on the lab close of 2026-08-29_2359:
# real derivations write 11,000-15,600 chars (~3-4K tokens of document, not
# the ~1,250 the 8,000 was sized for), and with thinking on top the five
# that succeeded finished near the cap while judge and philosopher hit it
# exactly and were SUSPECT-refused — which then left their stale block-3
# cutoffs to fail block_overlap_verify and refuse the whole phase-2 commit.
# 16,000 fits the measured envelope with room; a genuine runaway is still
# caught, and /settings-update derive_max_tokens overrides either way.
DERIVE_MAX_TOKENS = SET.setting_value_read("derive_max_tokens", 16000)

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


def part_mid_term_locate(part: str) -> pathlib.Path:
    return ROOT / "parts" / part / "mid_term.md"


def part_mid_term_dreamt_read(part: str) -> list[tuple[str, str]]:
    """Every `## Dreamt` section this part has, newest circle first.

    Ruled 2026-08-03 and first written 2026-08-07: a dream belongs to the
    circle it came from, not to `long_term.md`. This is the reader that makes
    those sections reachable — before it, they were written and read by
    nothing."""
    # THROUGH THE ONE READER since B96 (R434, 2026-09-04): a .toml's `[[dreamt]]`
    # tables and a legacy .md's `## Dreamt` sections come back as the same list.
    # EVERY `## Dreamt` IN A FILE, not the first — the loop that finds them
    # moved into short_term_manager verbatim (its first version split once and
    # cut at the next `## `, so a re-dream of the same circle was silently
    # dropped and never reached the hash; a probe's first run caught it), so
    # the bytes this hands the derivation, and the source hash over them, are
    # what they were for every existing part. Verified against all 309 legacy
    # files on 2026-09-04 before the move.
    import short_term_manager as STM
    out = []
    for f in reversed(STM.short_term_paths_read(ROOT / "parts" / part)):
        ot = f.stem.replace("short_term_", "")
        out += [(ot, d["text"]) for d in STM.short_term_read(f, part)["dreamt"]]
    return out


def part_mid_term_dreams_locate(part: str) -> list[tuple[str, str, str]]:
    """[(date, title, content), ...] for every UNSETTLED dream in
    parts/<part>/dreams.toml. Settled entries are excluded — already
    integrated history, not fresh signal for a distillate. (Was also
    the rule coordinator/recency.py's entries() applied; that standalone
    reporting tool, unreachable dead code, was removed 2026-09-01 — D-d.)

    Migrated 2026-08-12: the historic dream corpus moved out of
    long_term.md's `## Dream entries` (see rulings/). This is that
    corpus's replacement source; `part_mid_term_dreamt_read()` below still covers the newer,
    not-yet-condensed material sitting in short_term's `## Dreamt`."""
    import REGISTER_CLASS as SS
    p = ROOT / "parts" / part / "dreams.toml"
    if not p.is_file():
        return []
    doc = SS.register_read(p)
    return [(e["date"], e["title"], SS.register_unwrap(e.get("content", "")))
            for e in doc.get("dreams", []) if e["section"] == "dream"]


def part_mid_term_sources_read(part: str) -> dict:
    """Everything the derivation reads, and nothing else.

    Returned as text so the hash and the model see exactly the same bytes —
    a hash over one view and a call over another is how a cache silently
    serves the wrong thing."""
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    base = ROOT / "parts" / part
    lt = C.part_settled_strip(C.record_ro_read(base / "long_term.md"))
    dt = part_mid_term_dreams_locate(part)
    dr = part_mid_term_dreamt_read(part)
    # FOURTH SOURCE, R178, built with the phase-2 driver 2026-08-15 (was the
    # fifth until part_relationships.toml dropped out, 2026-08-22): the
    # part's whole remember register, file order. Any write — a live
    # [remember: ...] or a DREAMING record — flips this hash, which is the
    # staleness trigger that makes phase 2's refresh step re-derive
    # exactly the parts that moved.
    import remember_manager as RM
    mem = [r.get("text", "") for r in RM.remember_read(part)]
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


def part_mid_term_sources_hash(part: str, src: "dict | None" = None) -> str:
    """`src` reuses an assembly the caller already paid for (2026-08-19,
    review tier 5 #52: part_mid_term_state_read() assembled every source file twice per
    call — once itself, once through here — so the prompt path paid
    double per part per build and --refresh about six-fold). Threading
    the SAME src through part_mid_term_derive() and part_mid_term_write() also closes a race: the
    hash stamped on a distillate now describes the bytes the derivation
    actually read, not a fresh read of disk that may have moved
    mid-refresh."""
    text = (src if src is not None else part_mid_term_sources_read(part))["text"]
    h = hashlib.sha256()
    h.update(text.encode("utf-8"))
    h.update(f"|{LC.MODEL}/{PROMPT}".encode("utf-8"))
    return h.hexdigest()[:16]


def _front(part: str) -> dict:
    p = part_mid_term_locate(part)
    if not p.is_file():
        return {}
    first = p.read_text(encoding="utf-8").splitlines()[:1]
    if not first or not first[0].startswith("<!-- mid_term "):
        return {"legacy": True}
    bits = first[0].strip("<!- >").split(" · ")
    return {"hash": bits[0].replace("mid_term ", "").strip(),
            "model": bits[1].strip() if len(bits) > 1 else "?",
            "when": bits[2].strip() if len(bits) > 2 else None}


def part_mid_term_cutoff_read(part: str) -> str | None:
    """The `when` this part's CURRENT mid_term.md was derived at — the
    cutoff BLOCK 3/4's remember split uses (B44, remember_manager.py's
    project_settled()/project_tail()) to decide 'existed at the last
    refresh' vs 'written since'. `when` is second-precision, no tz suffix
    (part_mid_term_write()'s own `now()[:19]`); a remember record written the SAME
    second as a refresh sorts into the tail, not the settled window — the
    safe direction, since the tail is visible and uncached either way.
    None when there is no real front matter to read one from (absent or
    legacy) — the caller's job is to treat that as nothing settled yet,
    not to guess one."""
    return _front(part).get("when")


def part_mid_term_is_locked(part: str) -> bool:
    # splitlines() of an EMPTY file is [], and [0] then raised IndexError
    # straight up the prompt-assembly path (part_mid_term_state_read() -> part_mid_term_block_render()), crashing
    # every circle open for that part until the file was hand-deleted —
    # and a zero-byte mid_term.md is reachable: part_mid_term_write() is a plain
    # write_text, so a crash or full disk mid-write truncates. _front()
    # right above already guards the same read; this one didn't
    # (2026-08-18 review, tier 2 #22).
    p = part_mid_term_locate(part)
    if not p.is_file():
        return False
    lines = p.read_text(encoding="utf-8").splitlines()
    return bool(lines) and "mid_term_locked" in lines[0]


def part_mid_term_state_read(part: str, src: "dict | None" = None) -> tuple[str, dict]:
    """`fresh` | `stale` | `absent` | `legacy` | `locked`, and the numbers.
    `src` reuses a caller's assembly — see part_mid_term_sources_hash()."""
    src = src if src is not None else part_mid_term_sources_read(part)
    info = {"part": part, "chars": len(src["text"]),
            "dreams": len(src["dreams"]), "dreamt": len(src["dreamt"]),
            "hash": part_mid_term_sources_hash(part, src)}
    if not part_mid_term_locate(part).is_file():
        return "absent", info
    if part_mid_term_is_locked(part):
        return "locked", info
    f = _front(part)
    if f.get("legacy"):
        # A mid_term written before the hash existed. It is real content and
        # must not be discarded, but nothing can say what it was made from.
        return "legacy", info
    return ("fresh" if f.get("hash") == info["hash"] else "stale"), info


def part_mid_term_block_render(part: str) -> tuple[str, str]:
    """WHAT THE PROMPT PATH CALLS. Never derives, never calls a model.

    Returns ("", reason) when there is no distillate — and the caller must
    fall back to the raw sources rather than send a part an empty identity.
    Losing a part's identity to a missing cache file would be the worst
    failure available here, and it is one line of carelessness away."""
    st, info = part_mid_term_state_read(part)
    if st == "absent":
        return "", "no mid_term"
    text = part_mid_term_locate(part).read_text(encoding="utf-8")
    if text.startswith("<!-- mid_term "):
        text = text.split("\n", 1)[1].lstrip("\n")
    return text, st


def part_mid_term_write(part: str, body: str, locked_by_self: bool = False,
          src: "dict | None" = None) -> None:
    when = __import__("REGISTER_CLASS").now()[:19]
    # `src` must be the assembly the DERIVATION read (refresh threads it
    # through) so the stamped hash describes what the body was actually
    # made from — a fresh read here could hash sources that moved
    # mid-refresh, labeling a stale distillate current (tier 5 #52).
    src = src if src is not None else part_mid_term_sources_read(part)
    head = FRONT.format(hash=part_mid_term_sources_hash(part, src), model=f"{LC.MODEL}/{PROMPT}",
                        when=when, n=f"{len(src['text']):,}")
    if locked_by_self:
        head = head[:-3] + " · mid_term_locked -->"
    part_mid_term_locate(part).write_text(head + "\n\n" + body.lstrip("\n"),
                          encoding="utf-8", newline="\n")


# IMPORTED, NOT COPIED (2026-08-28). These were literal 2.00/10.00 here while
# llm_client carried the same two numbers plus the two cache tiers — so a rate
# change had to land in two files or this module would quietly price a
# derivation at yesterday's rates. The rise due 2026-09-01 would have done
# exactly that. llm_client.Meter is the owner; this module prices ONE uncached
# call, so it uses that owner's uncached pair and no cache tier — read as
# LC.RATE_IN / LC.RATE_OUT at the one use (local aliases until 2026-09-03).


# _client() MOVED to llm_client.stream_client_build(), 2026-08-28 (stage 1 of the
# provider socket) — same construction, same refusal message. The "one
# client, reused across parts" property this docstring claimed is kept at
# the call site in part_mid_term_refresh(), which builds one and hands it to every
# part_mid_term_derive(); call_once uses an injected client as given.


def part_mid_term_derive(client, part: str, src: "dict | None" = None):
    """ONE model call: this part's sources in, the distillate body out.

    No caching — sources are read once per part and never reused, so there
    is no shared prefix a cache would pay off. Returns the Reply
    (LLM_response_disassembler) so the caller can report cost and refuse a
    truncated result; part_mid_term_write() is a separate step so a caller can
    inspect the body (length, `## Dream entries` leakage) before it lands.
    `src` is the assembly part_mid_term_refresh() already made — see part_mid_term_sources_hash().

    TWO MORE INPUTS RIDE THE CALL, NEITHER THE HASH (DESIGN_V2's "DREAMING
    extension", step 8, 2026-08-22): the part's CURRENT mid_term.md, read
    fresh here rather than threaded through `src` — putting it in
    part_mid_term_sources_read()["text"] would mean every derivation invalidates its own
    hash the moment it writes, so the part is permanently stale; and
    remember_prompt_projection.remember_rank(part), the salience/chain-depth-bounded record
    order — already read from a register part_mid_term_sources_read() reads too (a live
    write to remember.toml already flips the hash), so ordering it
    differently for the model to SEE needs no hash of its own either.

    THE PRIOR ONLY RIDES THE CALL WHEN IT WAS DERIVED UNDER THIS SAME
    MODEL/PROMPT. Otherwise a PROMPT bump's own purpose — the next
    refresh re-derives from part_mid_term_sources_read() alone, "not a stale cache serving
    old content under a new label" (v7's comment, part_relationships) —
    would be defeated by "revise this incrementally" feeding the
    old-prompt distillate straight back in. The refresh right after a
    bump derives from scratch, exactly as every prior bump did; only the
    refresh after THAT one sees a prior worth revising."""
    src = src if src is not None else part_mid_term_sources_read(part)
    user_parts = [src["text"]]
    prior = part_mid_term_locate(part)
    # ONLY WHEN THE PRIOR WAS DERIVED UNDER THIS SAME MODEL/PROMPT. A PROMPT
    # bump (like v7 -> v8, DESIGN_V2 itself) exists to purge content the old
    # prompt kept that the new one should not (v7's own comment: "not a
    # stale cache serving old content under a new label") — feeding an
    # old-prompt distillate into "revise this incrementally" would let
    # exactly that purged content survive the bump it was supposed to die
    # in. The FIRST refresh after any bump derives from part_mid_term_sources_read() alone,
    # same as before this extension; incremental revision starts from the
    # refresh after that.
    if prior.is_file() and _front(part).get("model") == f"{LC.MODEL}/{PROMPT}":
        prior_body, _st = part_mid_term_block_render(part)
        if prior_body:
            user_parts.append(
                f"# Your current mid_term.md (revise this incrementally)\n"
                f"{prior_body}")
    import remember_prompt_projection as RPP
    ordered = RPP.remember_rank(part)
    if ordered:
        lines = "\n".join(
            f"- ({r.get('salience', 'passing')}) {r['text']}"
            for r in ordered[:20])
        user_parts.append(
            f"# Your remember register, salience-ranked (most weight first)"
            f"\n{lines}")
    # THROUGH THE TRANSPORT SINCE 2026-08-28 (stage 1). This called the SDK
    # directly, so a distillation had no retry ladder and its spend reached
    # no meter — this module priced itself with its own t_in/t_out sum
    # below, which is why RATE_IN/RATE_OUT had to exist here at all.
    # RECORDED FOR THE PART (R412, 2026-08-30) — when a turn log is open,
    # which is a live /close or the hand re-run; `mid_term --refresh` by hand
    # opens none and records nothing.
    return LC.stream_call_once(
        SYSTEM.format(budget=BUDGET), "\n\n".join(user_parts),
        DERIVE_MAX_TOKENS, kind="mid_term", client=client,
        record=True, part=part)


def part_mid_term_suspect_read(reply) -> list[str]:
    """Why a derivation must NOT be written; [] when it may be. Factored
    out of part_mid_term_refresh() so the gate itself is testable without a client;
    takes the Reply (LLM_response_disassembler) since 2026-09-02, not a
    (body, stop_reason) pair.

    `reply.truncated` is TRUNCATION and refuses regardless of length: the
    model's adaptive thinking spends from the same budget (see
    DERIVE_MAX_TOKENS), so a capped reply is a document cut mid-sentence.
    B68's probes watched one pass the half-budget floor below and land in a
    part's prompt — the floor catches starvation; this catches the cut."""
    bad = []
    body = reply.text
    if reply.truncated:
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


def part_mid_term_refresh(only: str | None = None, dry_run: bool = False,
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
        src = part_mid_term_sources_read(p)
        st, info = part_mid_term_state_read(p, src)
        if st in ("stale", "absent", "legacy"):
            todo.append((p, info, src))
        elif st == "locked":
            say(f"  {p}: locked — skipped")
        elif only:
            say(f"  {p}: already fresh — nothing to do")
    if not todo:
        say("  nothing to derive")
        return 0

    t_in = t_out = 0
    fails = 0

    if dry_run:
        for p, info, _src in todo:
            say(f"  {p}: deriving from {info['chars']:,} source chars (dry run)...")
            say("    (skipped — no model call)")
        return 0

    # THE DERIVATIONS RUN IN PARALLEL — B77, built 2026-08-30. This loop took
    # one part at a time while inter_circle's dreaming pass has run seven at
    # once since R170 for comparable per-part work, and the phase clock
    # finally priced the difference at a live close that morning:
    #
    #     inter.dreaming            47.6 s   (7 parts, parallel)
    #     inter.mid_term_refresh   697.4 s   (stale parts, one at a time)
    #
    # 697 s was 62% of an 1,120 s close against a 300 s aim. The wait was
    # never compute — the machine sat far below capacity — it is model-call
    # latency, serialized.
    #
    # ONLY THE CALL IS CONCURRENT. part_mid_term_suspect_read(), part_mid_term_write() and every say()
    # stay on this thread and are taken ONE FINISHED PART AT A TIME, which is
    # what keeps a part's report whole: interleaved output would make the
    # SUSPECT line and the "NOT written" line beneath it read as belonging to
    # whichever part happened to print between them. It also means nothing
    # mutates a file from a worker, so part_mid_term_write()'s per-part path stays a fact
    # about this module rather than a thing to reason about.
    #
    # A CLIENT PER WORKER, not one shared — R170's own rule for the dreaming
    # pool, kept here for the reason it gives: it costs nothing and removes
    # every thread-safety question rather than answering one.
    say(f"  deriving {len(todo)} part(s) in parallel:")
    for p, info, _src in todo:
        say(f"    {p}: started, {info['chars']:,} source chars")

    src_of = {p: src for p, _info, src in todo}

    def _derive_one(part: str, src: dict):
        return part_mid_term_derive(LC.stream_client_build(), part, src)

    with concurrent.futures.ThreadPoolExecutor(len(todo)) as ex:
        futs = {ex.submit(_derive_one, p, src): p for p, _info, src in todo}
        for f in concurrent.futures.as_completed(futs):
            p = futs[f]
            reply = f.result()
            counts = RD.message_usage_counts_read(reply.usage) or {}
            t_in += counts.get("input_tokens", 0) or 0
            t_out += counts.get("output_tokens", 0) or 0
            bad = part_mid_term_suspect_read(reply)
            if bad:
                fails += 1
                say(f"    {p}: SUSPECT — {'; '.join(bad)}")
                say("      NOT written — rerun by hand or inspect before forcing.")
                continue
            part_mid_term_write(p, reply.text, src=src_of[p])
            say(f"    {p}: wrote {len(reply.text):,} chars, "
                f"hash {part_mid_term_sources_hash(p, src_of[p])}")

    if t_in or t_out:
        cost = (t_in * LC.RATE_IN + t_out * LC.RATE_OUT) / 1_000_000
        say(f"\n  {t_in:,} in + {t_out:,} out tok, ~${cost:.3f}")
    return fails


def part_mid_term_list() -> str:
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    out = [f"  {'part':<14}{'state':<9}{'sources':>9}{'dreams':>8}"
          f"{'dreamt':>8}  hash"]
    for p in C.PART_TAGS:
        st, info = part_mid_term_state_read(p)
        out.append(f"  {p:<14}{st:<9}{info['chars']:>9,}{info['dreams']:>8}"
                   f"{info['dreamt']:>8}  {info['hash']}")
    return "\n".join(out)


def main() -> int:
    a = sys.argv[1:]
    import prompt_build as C   # the prompt construction (phase 2 stage 2; was circle)
    if a and a[0] == "--sources":
        part = a[1]
        src = part_mid_term_sources_read(part)
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
        return part_mid_term_refresh(only=only, dry_run=dry_run)
    if a and a[0] in ("--lock", "--unlock"):
        # TOGGLE THE MARKER ON THE EXISTING FRONT MATTER — never re-stamp.
        # Until 2026-08-19 this branch rewrote the old body through part_mid_term_write(),
        # which stamps hash=source_hash(part) computed NOW: locking (or
        # unlocking) a part whose sources had moved re-labeled a stale
        # distillate as fresh, and part_mid_term_refresh() then skipped it indefinitely.
        # The lock is a one-word edit to the head line; the hash, model and
        # when it records must stay the derivation's own.
        part = a[1]
        p = part_mid_term_locate(part)
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
                # so part_mid_term_is_locked() and _front() see one shape from both writers
                head = head[:-3] + " · mid_term_locked -->"
        else:
            head = head.replace(" · mid_term_locked -->", "-->")
        p.write_text(head + "\n" + rest, encoding="utf-8", newline="\n")
        print(f"  {part} {'LOCKED' if a[0] == '--lock' else 'unlocked'}")
        return 0
    print(part_mid_term_list())
    stale = [p for p in C.PART_TAGS if part_mid_term_state_read(p)[0] in ("stale", "absent",
                                                       "legacy")]
    print(f"\n  {len(stale)} of {len(C.PART_TAGS)} need derivation"
          + (f": {', '.join(stale)}" if stale else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
