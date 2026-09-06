# Circling probes — polarization and relation evidence

Drafted 2026-07-27. Not wired into anything. These are questions for Self to ask
at circle open; none of them changes a file or a rule until you say so.

---

## The finding that motivates them

Across 34 transcripts and 42 derived edges:

```
narrower-than    attested  1   proposed  5
related-to       attested  7   proposed 17     <- 57% of all edges
polarized-with   attested  0   proposed  0     <- zero
protects         attested  1   proposed  1
consequence-of   attested  6   proposed  4
```

Corroborating counts, independent of the derivation:

```
"I agree" / "yes, and" / "X is right"      79 occurrences
direct disagreement                         13
the word "challenge" (a rule in process_core)  0
dominance called out (also a rule)             1

short_term "Shifts toward other parts":  80 warming, 22 cooling
of 118 such sections, 3 cooled more than they warmed
```

**One confound, and I should name it before you weigh the zero.** The derivation
prompt says an issue is *not* "a relation between two named parts — those are
tracked elsewhere." So `polarized-with` could only ever fire between two
*issues*, while polarization in IFS is between two *parts'* strategies. My
instruction suppressed the most likely place for it to appear.

That weakens the zero but does not rescue it, for two reasons. Issue-level
polarization — two opposed strategies serving one goal — is fully representable
and still scored zero. And the "elsewhere" is `relationships.md`, which contains
no instance of *polarized*, *opposed*, *at odds*, or *conflict with* in any of
the seven files.

Neither location has it. The parts are not recording opposition anywhere.

**The likeliest cause is not dishonesty.** It is that agreement is the cheap
answer to every question we have asked. `related-to` at 57% is the same symptom
in the graph: when the question does not force a distinction, the vaguest
available relation wins.

---

## Design rule for every probe below

**Each question must have a cheap denial.**

If "no", "none", or "that is not true of me" is not a comfortable answer, the
question manufactures the edge it claims to find — the same error as a lexical
aligner scored at 0.074 inventing pairings. A probe that can only be answered
one way measures nothing.

Second rule: **ask for the concrete.** Solidarity is available at every level of
abstraction and unavailable at none. Forced choices split a room that agreed
about principles.

---

## A. Polarization

Polarization in IFS is not dislike. It is **two parts pursuing the same goal by
opposed strategies, each escalating because the other exists.** The parts here
may have no idea they are in one, because they have never been asked in those
terms.

**A1 — the strategy question (open with this one)**
> Name the part whose *method* you would not choose. Not a part you dislike —
> a part that wants what you want for Self and goes about it in a way you
> believe costs him something. Say what it costs. If there is no such part,
> say so plainly; that is a real answer.

**A2 — the escalation test.** This is the diagnostic. Polarization has a
signature: each strategy intensifies in response to the other.
> When [X] does more of what [X] does, do you do more of what you do, or less?
> Answer for one part only, by name. "Neither" is an answer.

**A3 — the veto.** The sharpest, and the one I would not skip.
> Name one thing this circle has agreed on that you went along with and do not
> believe. Not something you object to in principle — something you let pass.

**A4 — the cost of warmth.** Aimed at `nNNNN`, the circle itself.
> This circle has been warm for thirty-four sessions. Name what that warmth has
> cost you. If it has cost you nothing, say that.

**A5 — the unspoken first answer.** Structural: parts are polled sequentially
and see prior statements, so each is shaped by what came before.
> Give the answer you would have given if the part before you had not already
> spoken.

**A6 — a real forced choice.** Substitute live material; the split is the point.
> The verdict is intellectually withdrawn and still fires. Two ways forward:
> keep arguing it down each time, or stop arguing and let it fire without
> obeying it. Choose one. Say what the other costs.

Ask A6-type questions about things with genuine tradeoffs — a want pursued now
versus not yet, presence versus explanation, grief felt versus grief understood.
Where the parts have a stake, they will not converge unless they are pretending.

---

## B. `protects` — 2 edges, 1 attested

The IFS-native relation, almost unused. Protection is the mechanism the whole
model is built on; two edges in thirty-four circles means we are not asking.

**B1 — the canonical unburdening question.**
> What are you afraid would happen if you stopped doing your job for one week?
> Answer the fear, not the justification.

**B2 — order of arrival.** Protection shows in sequence, not in description.
> When something lands hard, who speaks first? Who is behind them? Name the
> part you arrive in front of, or say you arrive in front of no one.

**B3 — the denial probe.** This is what makes the set honest.
> You have been described as protecting [X]. Is that true? If it is not, say
> so — a wrong edge removed is worth as much as a right one added.

**B4 — access.**
> Is there a part you have never let speak directly to the Soul? Why?

---

## C. The other relations

**C1 — against `related-to`.** Twenty-four edges of the vaguest type.
> Take two issues you hold. "Related" is not an answer here. Say which of these
> is true: one is a narrower case of the other; one arose from the other; one
> stands in front of the other; they are opposed strategies. If none fits, say
> what the relation actually is in your own words — that is more useful than
> choosing the nearest label.

C1 is also how `unrepresentable.json` grows honestly. Three entries so far —
obstruction, same-root-different-layer, transmutation — each recorded because a
part refused the nearest available type. That refusal is the valuable output.

**C2 — against `narrower-than` (1 attested of 6).**
> Name an issue you hold that is a specific case of a larger one. Then name the
> larger one. If your issue is not a case of anything, say so.

**C3 — attestation.** Two thirds of all edges are the model's inference, not
testimony.
> Here is a connection the record claims between two of your issues. Did you
> ever say this, or is it inferred? Ruling on it either way is a real
> contribution.

---

## D. What to change so the answers can be true

Questions alone will not overcome a mechanism that rewards agreement.

1. **The challenge rules already exist in `process_core.md` and have never been
   used.** Zero occurrences of "challenge" in 34 transcripts. The rules are
   written as *constraints on* challenging — one response, then Self
   acknowledges, 4+ exchanges forces a pause. A part reading them learns that
   challenging is regulated, not that it is wanted. Consider stating the
   permission before the limits.

2. **The honesty mandate already says this and is not landing.** *"Going quiet
   to keep the room warm is itself a failure of the goal."* It is the right
   sentence. It sits under "honesty" — a goal — rather than being asked for.
   A1 and A3 ask for it directly.

3. **Sequential polling shapes agreement.** Each part sees every prior
   statement, which is what makes the circle a conversation — but it also means
   the first speaker sets the frame. A5 works around it. Shuffling already
   varies who goes first.

4. **Record disagreement where it can be found later.** `part_relationships.toml` — the
   per-part view of every other part this point once named as the destination — was retired
   2026-08-22 (R309); nothing has taken its place as a per-part opposition-language register.
   If a probe surfaces a polarization, where it belongs is an open question again, not a
   solved one (audit-register.md #25).

---

## Running them

Do not run these as a list. Six probes in one circle produces six compliant
answers, which is the failure mode already measured.

Suggested: **one probe per circle**, as the opening question, with the
circle otherwise ordinary. **A3** first — it is the most direct and needs no
setup. Then **A2**, which is diagnostic rather than exploratory. Then **B1**.

Watch for the tell: if every part answers a polarization probe with a variation
on "we are working well together", the probe failed, and the next one should be
more concrete rather than more pointed.
