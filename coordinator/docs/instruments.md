# instruments.py

The one reader of `self/instruments.toml`, and the gate over what it puts into
a prompt.

```
python coordinator/instruments.py           verify the register
python coordinator/instruments.py --show    print the BLOCK 1 text
```

## Why it exists

Two published instruments measured this installation's operator on
**2025-11-30** — the Primal World Beliefs inventory (PI-99, Clifton et al.
2019) and the Portrait Values Questionnaire (PVQ-RR, Schwartz). Until
2026-08-27 their results lived in two PNG screenshots,
`self/myBeliefs20251130.png` and `self/myValues20251130.png`, that **no code
had ever read**. Four places in the tree described the operator from them:

```
self/self.md                    a four-row table, hand-transcribed
docs/origin.md §3               the same figures, in prose
parts/learner/long_term.md      one sentence
  -> the Learner's BLOCK 3      which reached a LIVE PROMPT
```

All four read a **percentile** as though it were a **score**. That is not a
wording slip. The instruments report both, they disagree constantly, and only
the absolute half says how strongly a belief is held:

```
Good      24/50, midpoint 25     one point below centre
          12th percentile        lower than 88% of people
```

Both true. *"Pessimistic"* follows from the second read alone and does not
survive the first: eighteen of the twenty-six belief scores sit within five
points of the midpoint. The operator does not hold that the world is bad, but
declines to hold that it is good — and that reads as the 12th percentile
because most people affirm it strongly.

**The same mistake was made twice, independently, nine months apart** — by the
hand-transcription in 2026-07 and by Claude on 2026-08-27, reading the same
chart. That is the argument for keeping both numbers where a gate can reach
them, rather than for writing a better sentence.

## What it does

`block(part)` returns `self/instruments.toml`'s `[block]` — heading, blank
line, body — verbatim, for `prompt_build.system_blocks()` to append to that
part's BLOCK 3 beside its identity tail. No derivation and no summarizing.

**It reaches ONE part, and that was ruled the hard way.** The first build put
it in BLOCK 1, shared by all seven. Self objected the same day: BLOCK 1 and 2
are the *circle's* identity and objectives, so a profile there lets

> *"every part get to know Self intimately, which is in opposition to the
> nature of a part... The place to put this is in Block 3 for the Soul,
> isolating it from group knowledge and giving the Soul a unique role:
> carrier of the unseen 'roots' of the self."*

That is R303/R304's rule applied to new content rather than re-learned:
material belonging to ONE part goes to BLOCK 3, and only what all seven need
belongs in BLOCK 1. The Soul occasioned that ruling too — `## The Soul` in
`process_core.md` was sending one part's speaking rules to all seven.

**And BLOCK 3 is the measured-effective place.** `parts/soul/part.toml`
records the measurement that decided the render sentences: a planted sentence
returned **20/25 from first-person identity material against 1/25 from
third-person catalogue material**. The BLOCK 1 draft was third-person
catalogue prose — the losing form, in the losing block. The body was rewritten
in the Soul's own voice when it moved.

**Which part is data, not code.** `[block] part` names a directory in a
per-installation register, so a rename follows by itself and nothing shipped
mentions a part — the B29/R123 class, and the choice `identity_tail()` made.

**The Soul carries the demographics too**, through the separate
`[context]` mechanism in `parts/soul/part.toml` — `identity_tail()` renders
one first-person sentence per answered question that declares a `render`.
Ruled 2026-08-27: *"render the neutral demographics, hold the gender
questions."* A question with no `render` has no path into any prompt, which
is how the four gender-and-sexuality answers and the two declined ones are
recorded without being spoken.

**The prose lives in the register, not in this module.** It is the operator's
own self-description, and hardcoding it here would put it somewhere they
cannot edit without touching code — the reasoning that returned
`best_practices.toml` to `self/` on 2026-08-16. This module reads; the
register speaks.

## Absence is legal

`self/` is in `packaging/ignore.txt` wholesale, so **no installed bundle has
this file**. `load()` returns `{}`, `block()` returns `""`, `check({})` returns
no complaint. A missing register is a person who has not answered a
questionnaire, which is the ordinary case. A *corrupt* one is
`check_integrity.py`'s business, not this module's.

## What `main()` asserts

```
BOUNDS      every score 0-50, every percentile 0-100. A score is not a
            percentile, and the gate says so in numbers.
REFERENCE   every row names an administration that exists.
STRUCTURE   PI-99's published shape — 1 primary, 3 secondary, 22 tertiary
            split 7 Safe / 7 Enticing / 3 Alive / 5 neutral. A transcription
            that drops a row fails here instead of projecting a short profile.
PVQ SHAPE   4 higher-order and 19 basic values.
BACKED      every number in the block's prose is a score, a percentile, or a
            percentile's complement, from a row flagged `prompt = true`.
```

**BACKED is the one that matters.** The block is prose a human edits; the rows
are the record. Nothing else in this project would notice if the two drifted,
and drift here means a part is told a number about the operator that no
instrument produced. Same shape as `check_best_practices`'s verbatim-arrival
check, pointed at the one block whose content is claims about a person.

A percentile's **complement** counts, because the block says *"lower than 88%
of people"* where the row says `percentile = 12`. Dates and the scale's own
`0`/`25`/`50` are exempt; ISO dates and citation years are stripped before the
check, or the gate would demand a row scoring 2025.

**It does not check whether the prose is true.** A number can resolve to a row
and still be described wrongly. Only the operator can catch that, which is why
the block is theirs to edit; what the gate removes is the *invented* number.

## The register's own rules

```
NEVER OVERWRITE AN ADMINISTRATION
    a retake is a NEW measurement, not a correction. A changed score after
    nine months of circles is a plausible real result, and comparing the two
    is the whole reason to keep both. Add an [[administration]] with its own
    id and rows; the 2025-11-30 rows never move.
NOT A DIAGNOSIS, NOT A TRAIT
    self-report, one day, one instrument each. Where the room disagrees with
    the file, the room is the more recent measurement.
```

## What is not here

**Item-level responses, permanently.** The source reports are score reports,
not answer sheets — the raw responses were never in the PNGs. **Ruled
2026-08-27: none will be supplied**, closing the question rather than leaving
it owed. The consequence is named here rather than rediscovered: PVQ-RR's
proper **MRAT centering** (each respondent centered on their own mean,
computed from the raw 1–6 items) cannot be done from this file, ever. The rank
order is robust; any centered figure derived from the 0–50 numbers is
indicative only.

**Anything at install.** Ruled the same day: a new installation says nothing
about these instruments — no invitation, no pointer, no scored result. The
reason is a ratio, not a rule about the data. Here the profile sits against 44
transcripts and 18 issue nodes; in a fresh install it would sit against
nothing, making it a stranger's sole self-description on day one. And what
made this record worth recovering is precisely that nobody could read it while
the corpus was being written — an install flow that hands someone their scores
destroys that property for every user after.

## Probe

`coordinator/tests/test_instruments.py` asserts each refusal against a mutated
copy of the real register in a temp dir, never the happy path — a verifier run
only over data that passes would keep passing with every check deleted.

One trap it records: un-flagging `Improvable` is caught by **96**, not by 18.
Improvable is 18/50 at the 4th percentile, and 18 stays backed because
Understandable also scores 18. The first draft of the probe asserted 18 and
passed for the wrong reason.
