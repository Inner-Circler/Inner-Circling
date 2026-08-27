# Inner Circling — Overview

**An IFS Multi-Agent System.** Self's Internal Family Systems inner circle, implemented as asynchronous AI agents.

Canonical source: this markdown file (the `.docx` is a generated export). Updated 2026-07-01.

## What this is

Seven named parts of Self's psyche meet in open, asynchronous circles. Each part is a Claude AI agent with its own memory, perspective, and voice. The system is grounded in Richard Schwartz's Internal Family Systems model and Adam Phillips's critique of self-criticism.

*Parts hold the pain. Self holds the values. The pain did not corrupt the goodness.*

## The parts

| Part | Core quality | Most values |
|------|--------------|-------------|
| Judge | Discernment | Honesty — the clean mirror held with humility |
| Mourner | Sacred grief | Remembrance — being witnessed in what mattered |
| Idealist | Aspiration | Beauty and meaning — evidence a thing was worth it |
| Philosopher | Meaning-making | Belonging — simply being held, not earned |
| Child | Wonder | Safe-to-be-quiet — the room warm enough to come out |
| Learner | Hope/Curiosity | Courage and risk — curiosity that costs something |
| Soul | Foundational substrate — pre-verbal, pre-part. Acknowledged but does not speak in routine circles. | |

## How circles work

Self posts `CIRCLE: [topic]`. Each part reads its context files — `long_term.md`, `part_relationships.toml`, the circle briefing — then speaks asynchronously as ready. Each part may make up to 2 statements per Self turn; no part speaks twice in a row; 100 words max. All statements are public; parts may address each other directly. Domination is named by parts; Self evaluates and enforces.

Behind the scenes, each part runs as one persistent teammate for the circle's duration: the Scribe (the lead session) spawns it once, relays Self's words and other parts' statements to it, and prints its replies. The circle closes with `/circle_close`: transcript written, every part writes its short-term file and stands down, teardown verified.

## The nightly cycle

One scheduled task (`ifs-nightly`, 1:11 AM) runs both steps, serialized — dreaming completes before synthesis begins.

| Step | Task | What it does |
|------|------|--------------|
| 1 | Part Dreaming | Each part reviews the short-term files from circles since the last run, refreshes each dream entry's recency (*Last mentioned*), flags entries unengaged for 5+ circles for review, settles those the circle lets go, appends a new entry to `long_term.md` if warranted, and updates `part_relationships.toml`. |
| 2 | Self Synthesis | Self reads all parts plus the circle transcripts (ground truth), updates `self.md` and the observation log, rewrites the circle briefing (resolved questions), and writes the nightly narrative and phase arc. |

## Goals

stability · learning · satisfaction · appreciation · self-esteem · **honesty** · **mutual-knowing**

Honesty (2026-06-17) anchors the rest — keeping stability from becoming comfort, appreciation from becoming appeasement, hope from becoming anesthesia. Mutual-knowing (2026-06-17) runs both directions: each part comes to know its counterpart in Self; Self comes to know each part faithfully.

## Framework

Richard Schwartz · *Internal Family Systems*
Adam Phillips · *Against Self-Criticism*
Self-energy: the 8 Cs — calm, curiosity, compassion, confidence, creativity, clarity, courage, connectedness.
