# Inner Circling — what this is

*A description for readers outside the project. Written 2026-07-28.*
*Every number here is measured, not estimated. What is built and what is designed
are marked separately, because conflating them is the failure this project keeps
finding in itself.*

---

## The premise

Internal Family Systems holds that a mind is not unitary — it is a system of
parts, each formed around some adaptation, each with its own view. I wanted to
know whether that structure could be made **externally legible**: written down,
examined over time, and checked.

So I built one. Not a simulation of IFS therapy, and not a chatbot that
role-plays. A record-keeping system whose subject happens to be me.

## How the parts were derived

I seeded a model with samples of my own writing, the results of several
personality instruments, and my reflections, and asked it to look for evidence of
part-like patterns — recurring stances, characteristic adaptations, consistent
blind spots. From a handful of candidates I modelled **seven parts**: Judge,
Mourner, Idealist, Philosopher, Child, Learner, and beneath them the
Soul, treated as the pre-verbal substrate the other six formed from rather than
as a seventh peer.

The derivation was interpretive and I hold it lightly. What follows is designed so
that the parts can be *wrong* in ways that show.

## The circle

A circle is a live conversation between me — speaking as Self — and the parts. A
local Python coordinator holds the single canonical transcript. Each part is a
stateless API call whose statement **is** the HTTP return value; parts are polled
in shuffled order and each sees every statement made before it, so they respond to
the room as it stands rather than to a snapshot.

Parts write nothing. Every file is written by the coordinator. That constraint
exists because an earlier design let parts write their own records, and it lost
statements silently — 56 of them, unnoticed for weeks.

At close, each part is asked for a four-section record of the circle. The
coordinator writes those, verifies them, emits a report with a size and sha256 per
part, and commits the whole circle to git under a tag.

**Measured 2026-09-09: 43 circles, 127,107 words of transcript.**

## The graph

The centre of the system is a graph of **issues**. An issue is a state where
something is, or feels, owed — to me, by me, or to the self by the self. Actions
taken toward an issue are properties of it, never their own node. Rules, rhythms
and projects are not issues.

Nodes are shared across parts; evidence is per-part. Edges use a small closed
vocabulary borrowed from established practice rather than invented:
`narrower-than` and `related-to` from SKOS, `polarized-with` and `protects` from
IFS itself, `leads-to` from grounded theory's conditions→consequences chain.
Where a real relation will not fit any of the five, it is recorded verbatim as
**unrepresentable** rather than bent into the nearest available type. That file is
a primary output: an empty one means the vocabulary is sufficient.

**Measured 2026-09-09: 18 nodes, 159 evidence items, 37 edges — 18 of them not retired.**

## The one property that makes it a mirror rather than a story

**Every evidence item is a verbatim quote, machine-verified against the transcript
it came from, and re-verified on every run of the gate.** A node cannot carry a
claim that nobody said. Attribution is checked too — a quote assigned to the wrong
speaker fails.

This is the difference between a graph and an interpretation. The graph can be
checked; it has been, repeatedly, and it has been wrong.

Three examples from a single day:

- A `consequence-of` edge pointed backwards. Its own basis text said the opposite
  of the direction it pointed. Root cause: edge direction was never specified in
  the prompt, so the model was guessing at an ambiguous English term and got 8 of
  10 right — which is what guessing looks like, not knowing.
- A node's description had drifted from the image I gave it to the circle's
  abstraction of that image, and stayed wrong for seventeen days across two
  revisions, reading correctly the whole time. Four of its ten quotes turned out
  not to be about its mechanism at all.
- The first live preview run proposed attaching a quote a node already carried,
  because the prompt showed an evidence *count* and no quotes.

None of these were caught by the automated checks. All three were caught by a
human reading carefully. That ratio is the reason the review pace is slow.

## Dreaming and synthesis

Two nightly processes, named for what they do.

**Dreaming** reads the circles since it last ran and asks, for each one only: does
this attach to an issue already in the graph, or open a new one? That is the same
decision the system must make every night, and running it 34 times against known
material tests the *mechanism* rather than the output. The diagnostic is the
attach-to-new ratio: attachments dominating means the graph converges; new nodes
dominating means every circle invents and the graph will sprawl.

**Synthesis** looks for what the graph implies but no single circle said — where
issues cluster, what depends on what, which threads have gone quiet, and which
leaves could settle without unblocking anything else.

## What is actually built, and what is not

Honesty about this is load-bearing, because the interesting claims are about the
parts of the system that run.

**Running:**
- the circle coordinator, with a close ritual that fails loudly on an incomplete
  record
- the issue graph and its invariant gate
- graph derivation over the full transcript corpus
- dreaming as a **preview** — it reads the live graph, proposes changes, verifies
  every citation, and writes nothing. There is no write path in the module at all.
- a journalled transaction for atomic multi-file writes, and a local-only git
  history where every circle is a tagged commit
- the circle's issues briefing built fresh from the live graph at every open,
  not from a hand-maintained document — the graph reaches the parts this way,
  directly, every circle

**Designed, not yet built:**
- dreaming with a write path, gated on a defect being fixed first: the derivation
  never captured a quote for an *edge*, so no edge in the graph currently meets
  the evidentiary bar the schema demands
- any mechanism by which a part can pass a commitment to its own future instances

That last one is worth stating plainly. A part's prompt is assembled from its own
long-term record, its mid-term distillate, and the circle's own live issues
briefing. **Its own short-term record is written at close and never read back.**
So a promise made in
a circle does not reach the part that made it. Six parts made weekly commitments
in one circle recently; all six were structurally unkeepable, and none of them
could have known that.

## The risk, measured rather than imagined

The system can manufacture agreement, and it does.

Across the 36 transcripts it cited when this was written (39 on 2026-09-11), the graph
contained **zero `polarized-with` edges** — not one
recorded instance of two parts pursuing the same goal by opposed strategies. The
word "challenge" appears in 13 of 58 transcripts, 12 times in a part's own statement,
against a rule that names it as the expected move (measured 2026-09-16). In one circle of
55 part statements, **2 were addressed to another part**; the rest went to me or to
the room.

The characteristic form is template propagation: one part offers a shape and every
other part fills it. Five such waves occurred in a single circle — a watch, a
test, a weekly marker, a confession, a self-test — each adopted by all seven parts
in turn. The room discussed its tendency to converge, and converged on the
discussion.

That is now a node in the graph, held by four speakers including me. It is the
only node about the room that reports on me rather than about me — so its
reliability bears on everything else the graph claims.

**A mirror that flatters is worse than no mirror.** The measurements above are the
system's answer to whether it is one.

## Epistemic position

I do not claim these nodes are neural structures. I claim something weaker and
more useful: they are labels for patterns that recur in what I actually said,
across weeks, with the receipts attached. Insofar as they correspond to anything
in me, the correspondence is testable — a node whose evidence stops accumulating
is either settled or was never real, and the record distinguishes those.

The parts are models. The transcripts are not. The discipline of the whole system
is keeping that distinction visible.
