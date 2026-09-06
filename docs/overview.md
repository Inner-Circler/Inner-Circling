# Inner Circling — Overview

**An IFS system for one person's inner circle.** Self's Internal Family
Systems inner circle, run by a local Python coordinator that calls the
Messages API directly.

Canonical source: this markdown file. Updated 2026-09-01.

## What this is

Named parts of Self's psyche meet in a circle. Each part speaks in its own
voice, grounded in Richard Schwartz's Internal Family Systems model and
Adam Phillips's critique of self-criticism.

*Parts hold the pain. Self holds the values. The pain did not corrupt the goodness.*

**There is no agent runtime.** A circle is one local program, one process,
holding the single canonical transcript. Each part's statement is one
stateless call to the Messages API — the program builds that part's whole
context fresh from the transcript and that part's own identity file every
time it is asked to speak. No part is a persistent process, and nothing
runs in the background between its turns.

## The parts you receive, and the ones you will add

This installation ships two parts: **Soul** (the foundational substrate —
acknowledged, present in every circle, speaks rarely and on its own
terrain) and **Child** (wonder — the youngest part, closest to original
vulnerability). Every other part is yours to add, one at a time, as your
own circle surfaces it — parts are never manufactured in a batch to fill
out a roster.

An earlier draft of this document described a specific seven-part roster
as if it shipped with the product. That was one person's own roster, not
a set you are expected to reproduce. Look at `parts/child/` and
`parts/soul/` for the shape a part takes, and see `/part-add` in the
rulebook (`coordinator/process_core.md`) for how a new one joins.

## How a circle works

Self posts a topic. Each part's prompt is built fresh, in four blocks: the
shared rulebook and circle practices; what the issue graph currently owes;
that part's own long-term identity, distilled; and anything addressed to
that part alone. Statements are public and parts may address each other
directly; no part speaks twice in a row. Each statement aims for a short
length and is hard-capped at a configurable word count — 150 unless you
change the `statement_max_words` setting (`/settings-list` shows every
setting and its current value; a fresh install has none changed, so
`self/settings.toml` does not exist until you change one). Domination is
named by parts; Self evaluates and enforces.

The circle closes with `/close`: each part's closing reflection is
recorded, the transcript is written and verified, and the circle is
committed.

## What happens when a circle closes

Processing is **synchronous**, not scheduled. The moment `/close` finishes
writing the transcript, the same run immediately: each part reviews what
happened in this circle and may update its own long-term identity, in
parallel across every part (dreaming); then one pass looks across the
whole circle for practices that should apply to everyone (synthesis).
There is no separate scheduled task and nothing runs overnight — if this
step fails, `/close` reports it and nothing about it is left
half-written.

## Goals

stability · learning · satisfaction · appreciation · self-esteem · **honesty** · **mutual-knowing**

Honesty (2026-06-17) anchors the rest — keeping stability from becoming comfort, appreciation from becoming appeasement, hope from becoming anesthesia. Mutual-knowing (2026-06-17) runs both directions: each part comes to know its counterpart in Self; Self comes to know each part faithfully.

## Framework

Richard Schwartz · *Internal Family Systems*
Adam Phillips · *Against Self-Criticism*
Self-energy: the 8 Cs — calm, curiosity, compassion, confidence, creativity, clarity, courage, connectedness.
