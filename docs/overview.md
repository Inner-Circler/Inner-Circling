# Inner Circling — Overview

**An inner circle for one person.** Named members of a circle speak in turn
with Self, run by a local Python coordinator that calls the Messages API
directly.

Canonical source: this markdown file. Updated 2026-09-29.

## What this is

Self and a circle's named members meet in a circle. Each member speaks in
its own voice; what a member is, and the framework the circle draws on,
belong to its group — the group this installation ships describes itself in
its own folder, `groups/<group>/docs/overview.md`.

**There is no agent runtime.** A circle is one local program, one process,
holding the single canonical transcript. Each member's statement is one
stateless call to the Messages API — the program builds that member's whole
context fresh from the transcript and that member's own identity file every
time it is asked to speak. No member is a persistent process, and nothing
runs in the background between its turns.

## The members you receive, and the ones you will add

This installation ships its group's seed members, and every other one is
yours to add, one at a time, as your own circle surfaces it — members are
never manufactured in a batch to fill out a roster. The group's own
overview names its seeds.

No particular roster is expected of you. Look at `groups/<group>/parts/`
for the shape a member takes, and type `/part-add` at the `cmd>` prompt to
add one — it opens a dialog that asks what you need. Only you can add a
member; a member cannot ask for one. A member that has done its work is
retired, never deleted: `/part-retire` takes it out of every circle, prompt
and search and keeps its record whole — the system respects records and
history. Its name stays its own, and its past words stay in the
transcripts, marked retired. Retiring is a developer verb: open the circle
with `--dev` to use `/part-retire`, where `/part-add` needs no such thing.

## Why every path starts `groups/<group>/`

A **group** is one roster and the whole record it keeps — its members, its
issue graph, its registers, its transcripts — under `groups/<name>/`. What
makes a folder a group is the `group.toml` in it, exactly as a `part.toml`
is what makes a folder a member. This installation ships one group, which is
why every record path in this document begins that way; it is the default,
so no command here needs naming it.

Nothing obliges you to add another, and most people never will. If you do,
`/group-list` shows what exists and `/group-add` creates one — its folder
with a stub identity and `part.toml` for every role you name, a stub
`issues/issue_model.md`, a `self/self.md` with its two headings, and the
`group.toml` last, each stub yours to rewrite — and a circle opened on a
named group reads and writes only that group's tree — a different roster
for a different purpose, never a second opinion on the same one.

## How a circle works

Self posts a topic. Each member's prompt is built fresh, in four blocks: the
shared rulebook, the circle's practices, and the note the last circle left
for this one; what the issue graph currently owes; that member's own
long-term identity, distilled; and that member's own newest memories, with
anything it recalled. Statements are public and members may address each
other directly; no member speaks twice in a row. Each statement aims for a
short length, and each member is told never to go past a word count — 150
unless you change the `statement_max_words` setting. The limit reaches the
members as an instruction; nothing counts the words or cuts a statement at it.
That one is a developer setting: open the
circle with `--dev` to see it or change it. `/settings-list` shows what
you can reach — three settings on a normal run, and all thirty-five under
`--dev` — numbered, and `/settings-list <n>` shows one whole: its default,
what it accepts, and why the default is what it is. The three are
`model`, which model the members speak on; `redact_view`, whether the
circle pane shows names, emails and phone numbers as opaque tokens
rather than the real text; and `circle_stats`,
whether a close prints and files its delta report. A fresh install has
none changed, so `groups/<group>/self/settings.toml` does
not exist until you change one. Domination is
named by members; Self evaluates and enforces.

The circle closes with `/close`: each member's closing reflection is
recorded, the transcript is written and verified, and the circle is
committed.

## What happens when a circle closes

Processing is **synchronous**, not scheduled. The moment `/close` finishes
writing the transcript, the same run immediately: each member reviews what
happened in this circle and may keep one memory of it, in parallel
across every member (dreaming); then one pass looks across the
whole circle for practices that should apply to everyone (synthesis);
then each member whose sources have moved has its distilled identity rebuilt
(the refresh); then one pass reads the transcript for the commands its
words suggest and stages each as a proposal for Self's next ruling (the
command suggestions). Earlier in the close, just before you are asked to rule on
proposals, those saying the same thing are grouped (the coalesce pass).
Each of those makes its own model calls, so `/close` takes
noticeably longer than the circle's own turns.
There is no separate scheduled task and nothing runs overnight — if this
step fails, `/close` reports it and says whether running it again is
safe.

## Goals and framework

Each group states its own goals and the framework it draws on, in its own
layer and its own overview: `groups/<group>/docs/overview.md`.
