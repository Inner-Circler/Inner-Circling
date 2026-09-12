# Inner Circling — Overview

**An IFS system for one person's inner circle.** Self's Internal Family
Systems inner circle, run by a local Python coordinator that calls the
Messages API directly.

Canonical source: this markdown file. Updated 2026-09-12.

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
a set you are expected to reproduce. Look at `groups/ifs/parts/child/` and
`groups/ifs/parts/soul/` for the shape a part takes, and type `/part-add`
at the `cmd>` prompt to add one — it opens a dialog that asks what you
need. Only you can add a part; a part cannot ask for one. A part that has
done its work is retired, never deleted: `/part-retire` takes it out of
every circle, prompt and search and keeps its record whole — the system
respects records and history. Its name stays its own, and its past words
stay in the transcripts, marked retired.

## Why every path starts `groups/ifs/`

A **group** is one roster and the whole record it keeps — its parts, its
issue graph, its registers, its transcripts — under `groups/<name>/`. What
makes a folder a group is the `group.toml` in it, exactly as a `part.toml`
is what makes a folder a part. This installation ships one, `ifs`, which is
why every path in this document begins that way; it is the default, so no
command here needs naming it.

Nothing obliges you to add another, and most people never will. If you do,
`/group-list` shows what exists and `/group-add` creates one — its folder
with a stub identity and `part.toml` for every role you name, a stub
`issues/issue_model.md`, a `self/self.md` with its two headings, and the
`group.toml` last, each stub yours to rewrite — and a circle opened on a
named group reads and writes only that group's tree — a different roster
for a different purpose, never a second opinion on the same one.

## How a circle works

Self posts a topic. Each part's prompt is built fresh, in four blocks: the
shared rulebook, the circle's practices, and the note the last circle left
for this one; what the issue graph currently owes; that part's own
long-term identity, distilled; and anything addressed to that part alone. Statements are public and parts may address each other
directly; no part speaks twice in a row. Each statement aims for a short
length, and each part is told never to go past a word count — 150 unless
you change the `statement_max_words` setting. The limit reaches the parts
as an instruction; nothing counts the words or cuts a statement at it.
That one is a developer setting: open the
circle with `--dev` to see it or change it. `/settings-list` shows what
you can reach — three settings on a normal run, and all thirty-four under
`--dev` — numbered, and `/settings-list <n>` shows one whole: its default,
what it accepts, and why the default is what it is. The three are
`model`, which model the parts speak on; `redact_view`, whether the
circle pane shows names, emails and phone numbers as opaque tokens
rather than the real text; and `circle_stats`,
whether a close prints and files its delta report. A fresh install has
none changed, so `groups/ifs/self/settings.toml` does
not exist until you change one. Domination is
named by parts; Self evaluates and enforces.

The circle closes with `/close`: each part's closing reflection is
recorded, the transcript is written and verified, and the circle is
committed.

## What happens when a circle closes

Processing is **synchronous**, not scheduled. The moment `/close` finishes
writing the transcript, the same run immediately: each part reviews what
happened in this circle and may keep one memory of it, in parallel
across every part (dreaming); then one pass looks across the
whole circle for practices that should apply to everyone (synthesis);
then each part whose sources have moved has its distilled identity rebuilt
(the refresh). Earlier in the close, just before you are asked to rule on
proposals, those saying the same thing are grouped (the coalesce pass).
Each of those makes its own model calls, so `/close` takes
noticeably longer than the circle's own turns.
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
