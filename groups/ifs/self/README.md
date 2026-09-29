# self/

**Self's own registers.** Some are written by synthesis, some by you.

**Everything here is a DELEGATE — the live shape, none of the content.** Every
`self/` register the code depends on ships as an empty template, never seeded:
one person's registers are not generic enough to ship. What is worth shipping
is the shape.

```
best_practices.toml      how the CIRCLE behaves, and
                         how YOU move
self.md                  who Self is for this
                         installation
topics.toml              synthesis's unvetted BLOCK 2
                         topics
remember.toml            Self's own reflexive record
proposals.toml           the PROPOSE-class register --
                         what parts proposed, what a
                         live close suggested, and how
                         Self ruled on each
coalesce.toml            the proposal coalesce register --
                         groups of pending proposals that
                         are one ask in different words
redaction.toml           your curated redaction targets for
                         the CIRCLE pane's redacted view
(The four one-per-circle registers --
 circle_history.toml, circle_journal.toml,
 circle_observation_log.toml and working_sets.toml
 -- live in `../circles/`, beside the transcripts;
 `../circles/README.md` describes all four. They
 ship empty there.)

(The group's roles, its reserved roles and its
 rulebook layer are in `../group.toml`, beside this
 self/ folder; its presence is what makes the
 folder a group.)
settings.toml            what you change when the code would
                         otherwise decide -- a cap, a budget,
                         a mode. Not shipped: it appears the
                         first time you change one
                         (/settings-update); absent means
                         every setting is at its default
instruments.toml         what a published, scored
                         psychological instrument measured
                         about you, read by
                         instrument_manager.py into ONE
                         part's Block 3 -- the part the
                         register itself names. Optional by
                         design and never shipped: absent
                         means that block is simply empty
dreams.toml              Self's own dream corpus and the
                         standing summary derived over it
                         (dream_history_manager.py, run by
                         hand: --bootstrap, --fold). Never
                         shipped -- one person's dreams --
                         and nothing at /close reads it. Absent
                         reads as an empty corpus. Nothing writes
                         the dream rows but you; a derivation
                         appends only its summary records, and
                         refuses an empty corpus
redaction_map.toml       the redacted view's reverse map:
                         each email, web address, phone
                         number or handle it has hidden,
                         beside the token shown in its place
                         (redaction_manager.py). Never
                         shipped: it appears the first time
                         the view hides one. It holds the
                         REAL text -- keep it as private as
                         your transcripts
```

**Each empty register is the document its reader builds anyway.** `topic_manager.py`,
`proposal_manager.py` and `redaction_manager.py` each construct their own
empty shape when their file is absent — a `next_id = 1` counter (four `next_*` counters for
`redaction_manager.py`) plus an empty table — and each
delegate here loads to that same document, allowing only a longer `[doc]` preamble ("SHIPPED
EMPTY ..." prose appended to the builder's own text). Three exceptions, named so nobody "fixes"
them: `remember_manager.py` builds only `remember = []` when the file is absent — no register
name, no counter — while its delegate carries both, which its reader neither needs nor minds;
and `best_practices.toml` and `coalesce.toml` each carry a preamble their builders
(`practice_manager.py`, `proposal_group_manager.py`) do not construct. The delegates are not
byte-for-byte what the code would write — some carry a header comment — they are equivalent in
what a fresh install *reads*. The delegate exists so the file is *there*, valid and loadable,
rather than conjured on first write.

The same rule covers the four delegates in `../circles/`
(`circle_history_manager.py`, `circle_journal_manager.py`,
`circle_observation_manager.py`, `working_set_manager.py`) — they are not listed
above only because their registers are not Self's.

`self.md` is the one exception: it is prose, so it ships hand-genericized rather
than empty — the two sections synthesis expects, with a note in each saying what
belongs there. Synthesis reads it back as prompt input and replaces it whole,
which makes it a document, not a register.

**This directory arrives nearly empty.** The registers start empty and fill as
you rule things into them.
