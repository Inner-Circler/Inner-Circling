#!/usr/bin/env python3
"""
command_surface.py — the command-pane's shared constants, and the one
dev_mode flag. Phase 2 stage 0 of the coordinator partitioning
(2026-08-16, Self's build authorization; dev_mode's move here ruled
explicitly the same day); until then every name here lived in
circle.py.

WHY A MODULE OF ITS OWN. These constants are read from three directions
at once — circle.py's Self> loop, the help system, the dev-command
dispatcher, and ui/circling.py's command pane — and stages 3-7 of the
split put those readers in separate modules. Wherever the table lived
among them would have manufactured an import cycle (dispatch's /help
calls help_text, which renders COMMANDS); a leaf module below all of
them is what makes the later extractions acyclic. DEV_CMD_HEADS and
ISSUE_NODE_RE ride along for the same reason: each is shared by the
annotation grammar AND the dispatcher, and before this module they lived in
one consumer's region while the other reached across the file.

dev_mode IS REBOUND AT RUNTIME — the same late-binding contract as
seam.emit/seam.read_line (see seam.py's header): read and write it as
`command_surface.dev_mode` attribute access, NEVER `from command_surface
import dev_mode`, which copies the value at import time and goes stale
the moment anything toggles it. Everything else here is a constant,
never reassigned, and safe to from-import.
"""

from __future__ import annotations

import re

import identity as ID

# The console display name, for the one COMMANDS row that names it.
# Same derivation circle.py and transcript_store.py use; console-only
# (R132), never written to a transcript, never sent to a model.
CONSOLE_NAME = ID.user_name_read()

# ONE TABLE, so /help and KNOWN_CMDS cannot disagree. Ruled 2026-08-05:
# "Add a /help to the coordinator to report /commands. Report only the
# presence of /help (and the stats) at circle start."
#
# Both used to be hand-written lists. `/issue` and the four `/concern-*`
# commands were added on 2026-08-04 and 08-05 and each needed editing in two
# places — which is the same shape as every defect found this week: a
# projection with no verifier. `test_help.py` now fails if a command exists
# in one and not the other.
# THIRD COLUMN, RULED 2026-08-10: which pane a verb belongs to —
# "circle" or "command" — per circling_and_evolving.md §5's settled
# vocabulary split (the circle pane recognizes speech and /pass/round,
# nothing else; every ruling verb is command-pane-only). This is a
# CLASSIFICATION, not yet an ENFORCED restriction: until
# docs/dual_pane_integration.md §5's steps 7-8 build the merged
# command-pane verb surface, every one of these still only runs through
# circle.py's single Self> loop, same as always. `/concern-circle` is
# gone entirely (§5 step 9) — direct circle-pane speech replaced it.
COMMANDS: tuple[tuple[str, str, str], ...] = (
    # NO `<text>` ROW SINCE 2026-08-21 (R285, the
    # operator: "<text> ::= <circle_dialog> | <command_text> ... The list you
    # have are commands, remove <text> from the list"). Speech is
    # CIRCLE_DIALOG, not a COMMAND; what is typed at cmd> is a COMMAND or
    # JUNK, and JUNK is answered with help. The row that sat here glossed
    # speech as if it were a cmd> verb; the room's own help
    # (help_system.circle_pane_help) says "IN THE ROOM you speak".
    # THE VERB IS THE SLASH HEAD — R261, 2026-08-20. Every row below read
    # `/issue <verb> ...` until then: a two-token form whose FIRST ARGUMENT
    # named the verb, while docs/BNF.md had ruled the name as one
    # hyphenated `<object>-<property>-<method>` token since 2026-08-15
    # (B16). The line now matches the name it was already given.
    ("/issue-list",
     "the live graph, numbered — id and label, one row\n"
     "each. New with the regrammar: there was no way to\n"
     "ask this from a command at all", "command"),
    ("/issue-status nNNNN [= <value>]",
     "that issue's lifecycle status. THE PROPERTY CONSTRUCT\n"
     "(R261): a bare property READS it, `= <value>` WRITES\n"
     "it. A write previews via issue_status.py --dry-run,\n"
     "asks 'yes' to confirm, then applies. NO transcript\n"
     "quote needed, unlike the three ruling forms below",
     "command"),
    ("/issue-status-update nNNNN <value>",
     "the same write, spelled as a verb — an accepted\n"
     "synonym for `/issue-status nNNNN = <value>` (R261),\n"
     "for a caller that would rather not quote an `=`",
     "command"),
    ('/issue-label-update nNNNN "name" ["why"]',
     "rule on an issue's name", "command"),
    # <type> IS ONE OF FIVE, AND THE HELP NAMES THEM — the operator, 2026-08-21:
    # *"the help for '/issue-relationship-add nNNNN leads-to nMMMM' must describe
    # other valid relationship-type tags."* The spec said `leads-to` where it
    # meant a placeholder. The five are memory/issue_schema.EDGE_TYPES; this
    # leaf module must not import memory/, so the list is WRITTEN here and
    # test_help_system.py asserts it equals EDGE_TYPES — a drift guard, so the
    # gloss cannot go stale silently when the vocabulary moves.
    ('/issue-relationship-add nNNNN <type> nMMMM ["why"]',
     "rule on an issue-relationship. <type> is one of: leads-to,\n"
     "narrower-than, related-to, polarized-with, protects.\n"
     "The ruling forms are RECORDED TO THE TRANSCRIPT AS\n"
     "YOUR WORDS AND NOT SENT TO THE PARTS (R079);\n"
     "validated as a batch and applied at close —\n"
     "automatically in a LIVE circle, never in a sandbox\n"
     "one", "command"),
    ('/issue-evidence-add nNNNN <stmt#> "why"',
     "attach a PRIOR statement (its number from\n"
     "/issue-evidence-list) as evidence — quote and speaker\n"
     "come from the transcript, not typed fresh. Same\n"
     "RECORDED/NOT SENT/batch-at-close rule. R160/B40",
     "command"),
    ('/issue-relationship-status nNNNN <type> nMMMM = retired "reason"',
     "retire an issue-relationship — the property construct\n"
     "again; <type> as for /issue-relationship-add.\n"
     "Batch-at-close like the ruling forms\n"
     "above, unlike an ISSUE's status, which applies at\n"
     "once. Only retired is built; attested/proposed need\n"
     "a quote/an ask, not yet. R161", "command"),
    ("/issue-relationship-list",
     "every live issue with its live issue-relationships —\n"
     "type, target, status and the target's label, one\n"
     "row each. Retired ones are not listed: they do not\n"
     "project either. 2026-08-21", "command"),
    ('/issue-add "label" ["description" ["absence"]]',
     "open a NEW issue: its name, what it is, and what its\n"
     "absence looks like. All three -> a LIVE issue (nobody\n"
     "holds it yet); fewer -> a LEAD (L_nNNNN) until the rest\n"
     "is written. At cmd> a missing one is asked for. A part\n"
     "may propose it: [proposed: /issue-add \"label\" ...]. R290", "command"),
    ("/issue-apply <commands.toml>",
     "apply a circle's own already-recorded rulings to\n"
     "the live graph. Ported from ic.py 2026-08-13", "command"),
    ("/prompt-show circle | <part>",
     "the assembled system prompt, with placeholders\n"
     "where a circle supplies or may supply a piece.\n"
     "`circle` shows the blocks every part shares,\n"
     "a part name shows the two that are its own", "command"),
    ("/practice-add <your practice statement>",
     "a best practice, in YOUR words, punctuation and\n"
     "all. Always addressed to the whole circle.\n"
     "Written immediately — /abort does not undo it", "command"),
    ("/better-option-add <how Self moves>",
     "the same register, addressed to Self rather than\n"
     "the circle — how Self moves, not how the room\n"
     "behaves. R133 merged the two files into one.\n"
     "Written immediately — /abort does not undo it", "command"),
    ("/practice-list",
     "the circle's practices, numbered — every row NOT\n"
     "addressed to Self (the rows addressed to Self are\n"
     "/better-option-list's, since 2026-08-21)", "command"),
    ("/better-option-list",
     "how Self moves — the rows of the same register\n"
     "addressed to Self, numbered on their own. Always\n"
     "visible (the operator, 2026-08-21)", "command"),
    ("/practice-delete <n>",
     "remove one, by the number /practice-list showed —\n"
     "that list's numbering, not /better-option-list's",
     "command"),
    ("/remember <text>",
     "YOUR OWN private note, written at once to\n"
     "self/remember.toml — the same record [remember: ...]\n"
     "typed at the circle prompt writes. No circle needed;\n"
     "inside a circle the one-per-circle rule applies, as it\n"
     "does to the annotation. 2026-08-21", "command"),
    ("/remember-list [<n>]   (also /recall)",
     "YOUR OWN [remember: ...] records — bare lists them\n"
     "numbered, one line each; `<n>` shows one whole.\n"
     "Reads self/remember.toml directly, no circle needed.\n"
     "A part's own register is private to it and is NEVER\n"
     "reachable from here (R224, docs/BNF.md's\n"
     "REMEMBER_PROJECTION). Named /recall until 2026-08-21;\n"
     "/recall is still accepted", "command"),
    # SELF_OBSERVATION CRUD — 2026-09-01, the operator: "first class object with
    # CRUD operations and a help entry." self/self_observation_log.toml is
    # SYNTHESIS's own note to Self about the CIRCLE (never about Self, never
    # projected into any part's prompt) and is explicitly allowed to hold
    # personal material — /observation-purge exists because of that, not
    # despite the register's own "accumulate, never prune" rule: these are
    # live-window writes, outside the phase-2 gate's scope by the same
    # carve-out /remember and /practice-add already use (see
    # self_observation_manager.py's ORDER comment).
    ("/observation-add <text>",
     "a note Self adds directly, source=\"self\" — same\n"
     "register SYNTHESIS writes to at /close, no circle\n"
     "needed. 2026-09-01", "command"),
    ("/observation-list [<n>] [--all]",
     "bare lists every SELF_OBSERVATION entry, numbered\n"
     "(retired ones hidden unless --all); `<n>` shows one\n"
     "whole. 2026-09-01", "command"),
    ("/observation-continue <id> <text>",
     "a NEW entry chained onto <id> — <id>'s own record is\n"
     "never touched, matching accumulate-never-prune.\n"
     "2026-09-01", "command"),
    ("/observation-retire <id>",
     "soft delete — hides one entry from the default list;\n"
     "it stays in the file and in git history.\n"
     "/observation-list --all still shows it. 2026-09-01",
     "command"),
    ("/observation-purge <id> <id>",
     "true delete of the TEXT only (the id/date/chain shell\n"
     "survives, so nothing else's chain breaks) — type the\n"
     "SAME id twice to confirm. Irreversible in the live\n"
     "file; the pre-purge commit still has it in git\n"
     "history. 2026-09-01", "command"),
    # THE EDIT PATH FOR WHAT THE FIRST-RUN DIALOG RECORDS — docs/Initialization.md
    # §6; the operator, 2026-08-23: *"Add the ability to launch
    # PART_CONTEXT_DIALOG via cmd> "part-context-update <partname>" regardless
    # of (dev) and regardless of existing member values. Pre-populate question
    # responses with existing member values and allow their entry as-is OR
    # their edit on the line."* USER table: the answers are the person's own.
    ("/part-context-update <part>",
     "ask that part's context questions again — what it\n"
     "knows about you (the Soul: where you come from; the\n"
     "Child: your childhood). Each answer comes prefilled:\n"
     "Enter keeps it, type to change it, `-` clears it.\n"
     "Written to parts/<part>/part.toml at once; reaches the\n"
     "NEXT circle's prompts. 2026-08-23", "command"),
    ("/part-context-list [<part>]",
     "every part that declares context questions, each\n"
     "question with the recorded answer beside it (blank\n"
     "shown as —); one part if named. Read-only. 2026-08-23", "command"),
    ("/part-context-clear <part>",
     "erase that part's recorded answers, after 'yes' —\n"
     "the first-run dialog then asks again at the next\n"
     "open. 2026-08-23", "command"),
    # THE PART-LIFECYCLE VERBS — A14's creation path, stage 5, 2026-08-23
    # (docs/Initialization.md §8 reconciling docs/part_commands_design.md).
    ('/part-add ["<describe>" "<name>"]',
     "invite a NEW part: describe that aspect of yourself\n"
     "(up to 40 words), then its name — the same two strings\n"
     "a part's [proposed: /part-add ...] carries. Bare opens\n"
     "the dialog. It joins from the NEXT circle. IMMEDIATE —\n"
     "/abort does not undo it", "command"),
    ("/part-list",
     "the roster, numbered — Tag and directory, one row\n"
     "each. The number is positional (it shifts when a part\n"
     "is removed), the same contract /practice-list keeps", "command"),
    ("/part-view <n>",
     "that part's long_term.md, verbatim, by /part-list's\n"
     "number", "command"),
    ("/part-delete <n>",
     "remove a part — REFUSED for Soul and Child (reserved)\n"
     "and while a circle may be open; confirmation is typing\n"
     "the DIRECTORY name. The record survives in git\n"
     "(git log --all -- parts/<name>/)", "command"),
    # THE GROUP VERBS — a named, reusable roster (docs/CIRCLE_TYPES_DESIGN.md),
    # 2026-09-02. Same numbered/confirmation shape as the part verbs above.
    ('/group-add "<name>" <m1>,<m2>,...',
     "define a named roster from existing part directory\n"
     "names — circle.py --group <name> opens on it instead\n"
     "of --parts. IMMEDIATE — /abort does not undo it", "command"),
    ("/group-list",
     "every defined group, numbered — name and its members.\n"
     "The number is positional, same contract as\n"
     "/part-list", "command"),
    ("/group-view <n>",
     "one group's full member list, by /group-list's number,\n"
     "flagging any member that is no longer a real part", "command"),
    ("/group-delete <n>",
     "remove a group — confirmation is typing the group's\n"
     "NAME. Removes only the named roster, never the member\n"
     "parts themselves", "command"),
    ("/topic-list",
     "the TOPIC register (TP-): open BLOCK 2 topics —\n"
     "synthesis material carried for circle review,\n"
     "unvetted by design (R184)", "command"),
    ("/topic-close TP-nnnn",
     "close one topic — kept as a tombstone, id never\n"
     "reused. Written immediately — /abort does not\n"
     "undo it", "command"),
    ("/propose-list",
     "the staged proposals — pending first (what awaits\n"
     "your ruling at the next checkpoint), then settled —\n"
     "and any practice row still staged the old way.\n"
     "Numbered. No circle needed. 2026-08-21", "command"),
    # THE USER'S OWN STAGING DOOR — R350, the operator
    # 2026-08-25: "fill out the list, for now just propose-add (alias
    # bare 'propose' to this) and its arguments." Same register, same
    # checkpoint ruling a part's [proposed: <command>] reaches; the body
    # meets the identical test (annotations' _propose_command_shape) — one
    # grammar, not two.
    ("/propose-add <command>   (also bare propose)",
     "stage a proposal yourself — <command> is a\n"
     "proposable command with its arguments ('help propose'\n"
     "lists them), the same set a part's [proposed: ...]\n"
     "may name. Ruled at the next checkpoint; a sandbox\n"
     "circle refuses it (a draft, not the record)", "command"),
    ("/round",
     "let the parts take another round without a Self\n"
     "statement. /pass (below) is an equally valid alias", "circle"),
    ("/pass",
     "a new alias for /round, above — same operation,\n"
     "either spelling. The only other thing the circle\n"
     "pane recognizes besides speech itself", "circle"),
    # /tokens was folded in here 2026-08-20 — one report, one unit; the
    # fold note left the gloss and "since-Self" became "dialog turn"
    # R347 (the operator's wording, 2026-08-25).
    ("/status",
     "parts, every prompt block's size IN TOKENS as the\n"
     "model service counts them, the dialog turn counters,\n"
     "and the running cost.", "command"),
    # NAMED /statements UNTIL 2026-08-21 (D59), the operator: *""statement" is
    # unqualified, abstract, forbidden standing alone. If you mean
    # "issue-evidence", that sounds valid."* <object>-<property>-<method>:
    # the circle's statements ARE the candidate evidence, numbered as
    # /issue-evidence-add cites them. A USER verb by his word. No alias.
    ("/issue-evidence-list",
     "this circle's statements, numbered — what\n"
     "/issue-evidence-add cites by number. Named /statements\n"
     "until 2026-08-21 (D59)", "command"),
    # THE SETTINGS EDITOR — 2026-08-28 (R379). COMMAND
    # pane, deliberately: cmd> only means no Self> surface, so a settings
    # change writes no transcript line and there is nothing for a part to
    # see. That is guarantee 2 of three in coordinator/setting_manager.py's
    # docstring, and it holds by construction rather than by a filter.
    #
    # THESE ARE NOT IN PROPOSE_SUBSET_COMMANDS AND MUST NEVER BE. Ruled by
    # the operator, 2026-08-28: *"I do NOT want such operations surfaced for
    # parts."* coordinator/tests/test_setting_manager.py asserts the exclusion
    # against all three sets a proposal could travel through.
    # NEITHER ROW ALLUDES TO ANY FURTHER VIEW — 2026-08-29, the operator:
    # the earlier "dev adds the rest" tail was a leak of a surface he keeps
    # deliberately unannounced.
    ("/settings-list",
     "what this installation has changed, and what it would\n"
     "run on otherwise", "command"),
    ("/settings-update <name> [<value>]",
     "change one setting — give the new value on the line,\n"
     "or answer the question with the current value offered.\n"
     "A change that would disturb a circle already running\n"
     "waits for the next one to open", "command"),
    ("/settings-clear <name>",
     "put one setting back to what the code decides", "command"),
    # THE REDACTION REGISTRY — 2026-08-31, the operator: "a raw/redacted
    # switch can be on the settings page, support CRUD of target strings,
    # offer stable reversable opaque ids." USER table beside /settings-*
    # for the same reason: curating what YOUR OWN redacted view hides is
    # a tool for yourself, not a dev surface. NOT IN PROPOSE_SUBSET_COMMANDS
    # and NEVER should be — the same ruling setting_manager.py's own rows cite: a
    # part has no legitimate path to naming what its own operator wants
    # hidden. test_setting_manager.py asserts the exclusion against all three
    # sets a proposal could travel through, same as /settings-*.
    ('/redact-alias-add "<canonical>" [<kind>] ["<form>" ...]',
     "curate a name/place/org to hide in the redacted CIRCLE-pane\n"
     "view — kind is one of: person, place, org, other (default).\n"
     "Extra quoted forms are matched alongside the canonical one,\n"
     "longest-first. Part names are refused outright — they are\n"
     "never redacted, in circles or consults", "command"),
    ("/redact-alias-list",
     "the alias registry, numbered — id, kind, canonical label\n"
     "and every form, one row each", "command"),
    ('/redact-alias-update <n> "<canonical>" ["<form>" ...]',
     "edit one alias's canonical/forms in place — same id, same\n"
     "kind. Kind is not editable here: delete and re-add to\n"
     "change it, rather than leave an id's prefix meaning\n"
     "something its own row no longer says", "command"),
    ("/redact-alias-delete <n>",
     "remove one, by the number /redact-alias-list showed", "command"),
    ("/help",
     "this list", "command"),
    ("/close",
     "collect short_terms, verify, apply rulings, report", "circle"),
    # RULED 2026-08-14: "/close is allowed only in the circle dialog
    # pane" — reclassified from "command". PANE_OF (derived from this
    # table) is what circling.py's submit_command() consults to refuse
    # a circle-pane-only verb typed at the command pane; that refusal
    # now covers /close automatically, no separate change needed there.
    # DEV_MIN_CMDS below drops it for the same reason: it is no longer
    # reachable from the command pane at all, dev-gated or not.
    # Trimmed to two clauses R347 (the operator's wording,
    # 2026-08-25). The dropped detail — R173/B41, no short_terms, the
    # transcript kept, /issue rulings discarded, mid-circle writes not
    # undone — is what /abort's own confirmation prints before the second
    # /abort is asked for.
    #
    # CIRCLE-PANE SINCE 2026-08-31 (R414): the operator
    # separated the APP's lifecycle from the CIRCLE's — quit ends the
    # window and belongs to cmd>; /close ends the circle and belongs to
    # the room — and /abort ends the circle, so it moved beside /close.
    # The gloss's first word was "quit" (R347's verbatim); that word now
    # names the other lifecycle, so it is the one word of his that
    # changed here, on his ruling.
    ("/abort",
     "end the circle without a close — shows what stays and\n"
     "what's discarded first; a second /abort confirms.", "circle"),
)

# DERIVED from COMMANDS — the two can no longer drift apart.
KNOWN_CMDS = tuple(dict.fromkeys(c.split(" ")[0] for c, _, _ in COMMANDS
                                 if c.startswith("/")))

# head -> pane ("circle"/"command"), DERIVED from COMMANDS — same
# single-source discipline as KNOWN_CMDS, added 2026-08-13 so a second
# surface (circling's command pane) can ask "is this verb command-pane-
# shaped" without a second table that could drift from COMMANDS itself.
# Duplicate heads (the three "/issue ..." rows) all agree on "command",
# so last-value-wins in the dict comprehension is harmless here.
PANE_OF: dict[str, str] = {c.split(" ", 1)[0]: p for c, _, p in COMMANDS
                          if c.startswith("/")}

# /dev IS DELIBERATELY NOT A ROW IN COMMANDS. Everything above this line
# drives /help and the "Known:" hint on a typo — adding /dev there would
# document it. It is the command pane's own unlisted toggle
# (ui/circling.py, `dev`), and the standalone terminal opens with --dev
# (R286, 2026-08-21) — so /help, KNOWN_CMDS and the
# unknown-command hint never mention it.
#
# The four COMMAND-PANE verbs still usable with dev mode off. Not a
# design about which verbs are "safe" — /help, /abort, /status and
# /tokens all run ahead of the dev-mode check in circle.py's loop
# because they `break`/`continue` before reaching it; this tuple only
# drives what dev_restricted_text() prints back, so that text names the
# same four the loop actually still honours.
#
# /close dropped 2026-08-14 (reclassified "circle" above, not
# "command") — it still runs ahead of the same check in circle.py's own
# loop, unchanged, but it is no longer a command-pane verb for this list
# to track: dev-gating is a command-pane concept, and /close no longer
# reaches the command pane at all.
#
# /tokens ADDED 2026-08-14 — RULED available under both dev==true and
# dev==false. REMOVED 2026-08-20: folded into /status, which was already
# in this tuple and already ran ahead of the same gate. The two verbs
# reported the same text in different units over different spans and
# disagreed with each other in public; one report cannot.
#
# /abort dropped 2026-08-31 for /close's reason: reclassified "circle"
# (R414), so it no longer reaches the command pane at all.
DEV_MIN_CMDS = ("/help", "/status")

# The always-available, no-circle-needed verb surface a COMMAND-class
# propose may name — deliberately NARROWER than every real command-pane
# verb (KNOWN_CMDS): propose-approval runs at checkpoints where no
# circle may be open (before the NEXT circle's prompts are warmed —
# vet_pending_proposals()'s own "checkpoint 2"), so /round, /pass,
# /close, /abort, /status, /tokens, /issue-evidence-list — anything circle-pane-
# only or transcript-dependent — would be nonsense to "approve" here.
# This is dispatch_dev_cmd()'s own accepted-heads set, named once so
# PROPOSE's classifier and dispatch_dev_cmd() itself cannot drift apart
# — test_proposal_manager.py asserts the two stay in sync. Lived beside the
# annotation grammar until stage 0; both that grammar and the dispatcher
# read it, which is exactly why it lives in this shared leaf now.
# COMPLETED 2026-08-21: it was short by /recall, /issue-list, /issue-status
# and /issue-status-update — heads dispatch_dev_cmd() had handled for days
# while test_proposal_manager' sync probe asserted only ⊆ — and it gains the verbs
# minted the same day. Every entry is a no-circle head; /remember-list is
# listed under its own name (/recall normalises to it, see normalise_head).
DEV_CMD_HEADS = ("/help", "/practice-add", "/better-option-add",
                 "/practice-list", "/better-option-list", "/practice-delete",
                 "/topic-list", "/topic-close", "/prompt-show", "/issue-apply",
                 "/issue-list", "/issue-status", "/issue-status-update",
                 "/issue-relationship-list", "/issue-add",
                 "/remember", "/remember-list", "/propose-list",
                 "/observation-add", "/observation-list",
                 "/observation-continue", "/observation-retire",
                 "/observation-purge",
                 "/part-context-update", "/part-context-list",
                 "/part-context-clear", "/part-add", "/part-list",
                 "/part-view", "/part-delete",
                 "/group-add", "/group-list", "/group-view", "/group-delete")

# ---------------------------------------------------------- the two tables
# R266, 2026-08-20, the operator's own words: *"There is, or needs to be, a table of
# commands exposed to the non-dev user, USER_SUBSET_COMMANDs, entirely
# disjoint from DEV_SUBSET_COMMANDs."*
#
# DEV MODE ADDS; IT NEVER TAKES AWAY. Dev off, the user table alone is
# accepted at cmd> and listed by /help; dev on, the UNION. The tables are
# DISJOINT — no verb is in both — which is what makes the union a statement
# about availability rather than a second, competing list. `_disjoint()`
# below is not decoration: two tables that quietly overlapped would make
# "dev adds" false in a way nothing else would notice.
#
# THE ISSUE VERBS WERE THE USER'S, and for one day that was the point of the
# split (R266: "Nothing about naming an issue or drawing a relation is
# hidden from the person whose issues they are"). NARROWED 2026-08-21,
# R288, the operator's own words: *"These are items I do
# not want visible while dev is off, I think of them as tools for myself and
# do *not* want typical users exposed to them for now: /issue-* (EXCEPT for
# /issue-list), /practice-delete, /topic*, /better-option-add. Also: add a
# path for /better-option-list and make it always visible."* So the user
# table keeps /issue-list alone of the issue verbs; every other /issue-*
# — present and future — is DEV, and so are /practice-delete, the topic
# verbs (R281, the same day) and /better-option-add.
# "For now" is his phrase both times. What dev gates is still, as well,
# docs/HELP_DESIGN.md §2's hierarchical BROWSING surface (/help <class>,
# list, read # — R280).
#
# `statements` RIDES THE USER TABLE BY NECESSITY: issue-evidence-add
# addresses a statement BY ITS NUMBER and nothing else discovers that
# number. A user table holding evidence-add without statements holds a verb
# nobody can use — and evidence-add is DEV now, but the number is also what
# a person reads the room BY, so statements stays where the reader is.
#
# /remember, /remember-list (/recall accepted), /better-option-list and
# /propose-list were minted 2026-08-21 from the same dictation (NEXT.md
# B64): the everyday surface is what the user owns —
# the issue list, practices and better options, their own notes, and what
# the parts have proposed.
USER_SUBSET_COMMANDS: tuple[str, ...] = (
    "/issue-list", "/practice-add", "/practice-list", "/better-option-list",
    "/remember", "/remember-list", "/propose-list", "/propose-add",
    "/observation-add", "/observation-list", "/observation-continue",
    "/observation-retire", "/observation-purge",          # 2026-09-01
    "/issue-evidence-list",
    "/part-context-update",                  # "regardless of (dev)", 2026-08-23
    "/part-context-list", "/part-context-clear",     # the same data, same owner
    "/part-add", "/part-list",               # the user's own growth path (stage 5;
                                             # Claude's reading of R288's line)
    "/group-add", "/group-list",             # choosing which roster to run is the
                                             # same class of thing, 2026-09-02
    # THE SETTINGS VERBS RIDE THE USER TABLE, and the FIELDS are what dev
    # gates — 2026-08-28. Putting them in DEV_SUBSET_COMMANDS instead would
    # have hidden the verb outright with dev off, and the operator asked for
    # the opposite: a chosen few settings visible to an ordinary person, "such
    # as the LLM provider/model". So the verb is always there and
    # setting_manager.setting_visible_read(dev) decides what it shows — R266's "dev adds, never
    # takes away", one level down from the verb to the field.
    "/settings-list", "/settings-update", "/settings-clear",
    # THE REDACTION-REGISTRY VERBS RIDE THE USER TABLE for the same reason
    # /settings-* does — curating what your own redacted view hides is a
    # tool for yourself. 2026-08-31.
    "/redact-alias-add", "/redact-alias-list", "/redact-alias-update",
    "/redact-alias-delete",
    # /abort LEFT this table 2026-08-31 with its reclassification to the
    # circle pane (R414) — like /close, /round and /pass it
    # is no command-pane verb, and these tables are the command pane's.
    "/help", "/status",
)

DEV_SUBSET_COMMANDS: tuple[str, ...] = (
    "/issue-status", "/issue-status-update", "/issue-label-update",
    "/issue-evidence-add", "/issue-relationship-add",
    "/issue-relationship-status", "/issue-relationship-list", "/issue-add",
    "/issue-apply", "/practice-delete", "/topic-list", "/topic-close",
    "/better-option-add", "/prompt-show",
    "/part-view", "/part-delete",            # inspection and removal are tooling
                                             # (Claude's reading; say the word to move them)
    "/group-view", "/group-delete",          # same split as the part verbs, 2026-09-02
)

# /dev IS IN NEITHER TABLE, and that is R199 (2026-08-16), verbatim: *"yes,
# dev is meant to require being told, permanently."* Re-confirmed 2026-08-20
# when it was put to the operator a second time — see rulings/, where the second
# asking is recorded as an error rather than a second decision.

# R267, 2026-08-20, the operator's own words: *"/practice-add is a circle construct,
# valid for users or parts to propose, stage, and vett. *list operations are
# not valid in any ANNOTATION."*
#
# A SUBSET OF THE TWO TABLES, never a third list. A propose asks for a
# CHANGE; a listing is a question, and a question staged for ratification is
# a category error — approving one would "run" a read.
#
# IT WAS "A SUBSET OF THE USER TABLE" UNTIL 2026-08-21, and the change is the
# flagged consequence of R288: three of these five —
# /issue-label-update, /issue-relationship-add, /better-option-add — are
# DEV-table verbs now, hidden at cmd> with dev off. Nothing about PROPOSING
# changed: a part proposes them in a bracket and Self rules at the vetting
# prompt without typing the verb. What changed is the assertion in
# _disjoint(): PROPOSE ⊆ USER ∪ DEV.
#
# /issue-status-update LEFT THIS TABLE LATER THE SAME DAY, 2026-08-21 — the
# operator, verbatim: *"remove /issue-status-update from annotation
# visibility."* R267 is narrowed by that one verb: a part may no longer ask
# for an issue's status to change; Self sets one at cmd> (a DEV verb since
# R288). annotations' classifier reads this table, so the bracket is MALFORMED
# ("not proposable") without a second edit, and the `issue_status` shape the
# classifier and vetting once carried for it is gone with it.
#
# /issue-relationship-status IS NOT HERE, AND THAT IS NOW RULED rather than
# merely followed: R269, 2026-08-20,
# verbatim *"no, a part may not propose retiring an edge. Possible future."*
# It is an issue mutation and would sit here naturally, which is why the
# omission was worth asking about instead of tidying away.
#
# RETIRING IS THE ONLY HALF THAT WAS EVER BUILDABLE. Of the three values
# issue_gate.py accepts, `attested` needs a verbatim quote from a named
# transcript and `proposed` needs an `ask` — arguments a bare status write
# cannot solicit, which is why R161 scoped the verb to `retired`. And a
# retired edge STOPS PROJECTING: live_edges() drops it, it leaves BLOCK 2,
# and no part sees that relation again, including the one that asked.
#
# "Possible future" is his word. This tuple is where it would land, and
# _disjoint() below already asserts this table is a subset of the user's.
# /issue-add JOINED 2026-08-21 (R290 — R001 retired): the operator, verbatim,
# *"[propose: issue-add <text>] is valid and important."* A part may ask that an
# issue be opened; approval writes it (complete -> live, incomplete -> lead).
PROPOSE_SUBSET_COMMANDS: tuple[str, ...] = (
    "/issue-label-update", "/issue-relationship-add",
    "/issue-evidence-add", "/practice-add", "/better-option-add",
    "/issue-add",
    # R323, 2026-08-23: a part proposing a part is the room noticing someone
    # not yet at the table; approval fires PART_ADD_DIALOG with the
    # bracket's strings prefilled. [proposed: /part-add "<describe>" "<Tag>"]
    "/part-add",
)

# THE FIVE /observation-* VERBS ARE NOT IN PROPOSE_SUBSET_COMMANDS AND MUST
# NEVER BE, same reasoning as /settings-*/-redact-alias-* above: a part has
# no legitimate path to proposing a write into Self's own private register,
# one explicitly allowed to hold personal material never projected into any
# prompt. test_setting_manager.py's exclusion pattern is the one to extend if this
# needs asserting the same way (2026-09-01).

# RULED INTO THE TABLE, NOT YET BUILDABLE FROM A BRACKET. R267 put
# /issue-evidence-add in PROPOSE_SUBSET_COMMANDS and annotations.py's classifier
# refuses it anyway, with a reason — it addresses a statement BY ITS NUMBER
# and resolves part, quote and source against the LIVE TRANSCRIPT, which the
# checkpoint a propose is approved at has not got.
#
# IT LIVES BESIDE THE TABLE IT SUBTRACTS FROM, 2026-08-20 (code review). It
# sat in annotations.py for one afternoon, and help_system — which reads THIS
# module, never annotations — counted PROPOSE_SUBSET_COMMANDS whole and told
# Self "one of the 6 proposable commands" while the classifier's refusal
# listed 5 and process_core.md taught 5. Before that it was a bare
# `if head ==` and _proposable_list() advertised the verb as valid, so a
# part following its own prompt got MALFORMED and spent its one propose.
# Four surfaces have to agree about this set — the refusal, the "valid:"
# list that refusal sends a writer to, what process_core.md teaches, and
# what /help counts — and they agree only if every one reads ONE
# subtraction, made here.
DEFERRED_PROPOSE_COMMANDS: tuple[str, ...] = ("/issue-evidence-add",)

# What a `[proposed: ...]` may actually name TODAY — the ruled table minus
# the deferred. /help counts this and a refusal lists it. The table above
# is what R267 ruled and keeps the deferred verb because the ruling did.
PROPOSABLE_COMMANDS: tuple[str, ...] = tuple(
    c for c in PROPOSE_SUBSET_COMMANDS if c not in DEFERRED_PROPOSE_COMMANDS)


def _disjoint() -> None:
    both = set(USER_SUBSET_COMMANDS) & set(DEV_SUBSET_COMMANDS)
    if both:
        raise AssertionError(
            f"USER_SUBSET_COMMANDS and DEV_SUBSET_COMMANDS must be disjoint "
            f"(R266) — both hold {sorted(both)}")
    stray = (set(PROPOSE_SUBSET_COMMANDS)
             - set(USER_SUBSET_COMMANDS) - set(DEV_SUBSET_COMMANDS))
    if stray:
        raise AssertionError(
            f"PROPOSE_SUBSET_COMMANDS is a SUBSET of USER ∪ DEV (R267, narrowed "
            f"from ⊆ USER by R288, 2026-08-21) — "
            f"{sorted(stray)} is in neither table")
    loose = set(DEFERRED_PROPOSE_COMMANDS) - set(PROPOSE_SUBSET_COMMANDS)
    if loose:
        raise AssertionError(
            f"DEFERRED_PROPOSE_COMMANDS subtracts from PROPOSE_SUBSET_COMMANDS "
            f"— {sorted(loose)} is not in it")


_disjoint()

def command_pane_verb_read(text: str) -> str | None:
    """The command-pane verb this circle-dialog line stands alone as, or
    None. D55(2), 2026-08-20, verbatim: *"no command pane verb standing
    alone in any circle dialog text may EVER be recognised - standalones
    MUST be ignored no-ops."*

    HOISTED HERE 2026-08-30 from ui/circling.py's AppState._pane_verb — the
    Ticker flavor's bridge feeds the engine's circle channel directly, below
    the TUI's pane layer, so the ruling was enforced for one flavor and
    bypassed by the other: with dev on, `/practice-add ...` typed into the
    window's room wrote a practice, the exact regression D55(2) closed.
    One classifier, both flavors; circling.py delegates here.

    STANDING ALONE is the whole test: a verb INSIDE an annotation is a
    different thing entirely (it stages for vetting, which is the one way a
    command may be named from the room), and ordinary speech that merely
    mentions one is speech. So this looks at the FIRST WORD of the line and
    nothing else. No leading slash, no verb: in the room everything typed
    is SPEECH unless marked, and a bare word like "close" is a word.

    BARE /help IS THE ROOM'S OWN (R287): PANE_OF classes /help as a
    command-pane verb, but bare `/help` passes to the loop, which answers
    with the room set alone; `/help <anything>` is the command pane's.
    /dev IS cmd>-ONLY (R286) and no PANE_OF key (R199): refused by name.
    /quit IS THE WINDOW'S OWN, cmd>-ONLY SINCE 2026-08-31
    (R414) and no PANE_OF key either — a pane-local verb of
    both flavors' UI layer, so it too is refused by name. A caller should
    word its notice for it separately: "stage it as an annotation" is
    advice for a command, and quit is not one."""
    cls = verb_class(text)
    if cls in ("command", "window"):
        return command_head_normalise(text.strip().split(" ", 1)[0])
    return None


def verb_class(text: str) -> str | None:
    """What lifecycle the FIRST WORD of a typed line belongs to, if it is a
    verb standing alone — or None, which means the line is text: speech in
    a running room, a journal entry in an idle one.

        "circle"     /close, /abort, /round, /pass — PANE_OF's circle class:
                     the CIRCLE's lifecycle, the room's own while one runs
        "command"    a PANE_OF command-class verb, or /dev, or `/help <arg>`
        "window"     /quit — the APP's lifecycle, cmd> only
        None         not a verb (no slash, an unknown word, or bare /help,
                     which is the room's own)

    R414, 2026-08-31 — the operator: *"there are two
    lifecycles to be managed: the app and the circle."* ONE classifier for
    every input surface in both flavors: command_pane_verb_read() above is this filtered
    to what a running room refuses, and the Ticker bridge asks it directly
    for the idle band and the closing band, where a verb typed in the wrong
    box becomes a NOTICE rather than a journal entry — his journal carried
    `/close`, `/circle`, `quit` and `/quit` as fossils before this."""
    first = text.strip().split(" ", 1)[0]
    if not first.startswith("/"):
        return None
    head = command_head_normalise(first)
    if head == "/help":
        return None if text.strip() == "/help" else "command"
    if head == "/dev":
        return "command"
    if head == "/quit":
        return "window"
    return PANE_OF.get(head)


def command_head_normalise(word: str) -> str:
    """A typed verb, normalised to the one spelling the tables hold.

    FINDING 14, 2026-08-20. the operator typed `/topic_close TP-0029` and got
    "not understood, see 'help'" — twice, because the second attempt was
    the same typo. `/topic_close` is not a second grammar; it is a
    keyboard away from `/topic-close`, and every dispatch site in this
    project compares by exact string.

    THREE THINGS, and they are all the same thing: give it a leading
    slash if it has none (R201 — the command pane does not require one),
    lower-case it, and read `_` as `-`. THE VERB GRAMMAR HAS NO
    UNDERSCORE IN IT — docs/BNF.md's `<object>-<property>-<method>` is
    hyphens throughout — so nothing legal is being shadowed.

    ONE FUNCTION, THREE DISPATCHERS. circle.py's Self> loop, this file's
    dev-command door and ui/circling.py's command pane each computed
    their own `head`; a normaliser in one of them would have fixed the
    typo in one place and left it unfixed in the others, which is how
    this project ends up with a surface nobody can state."""
    h = word.strip()
    if not h:
        return h
    if not h.startswith("/"):
        h = "/" + h
    h = h.lower().replace("_", "-")
    return SYNONYMS.get(h, h)


# ACCEPTED SPELLINGS THAT ARE NOT THE NAME. One table, read by command_head_normalise()
# so every dispatcher — the Self> loop, the dev-command door, the command
# pane, the circle pane's guard — resolves them identically. /recall was the
# verb's name from R224 (2026-08-18) until 2026-08-21, when the operator named
# the register's verbs /remember and /remember-list ("\"recall\" is a
# synonym"); the old spelling keeps working and is shown once, on the
# /remember-list row, never as a row of its own.
SYNONYMS: dict[str, str] = {"/recall": "/remember-list",
                            # bare "propose" (the pane adds the slash) —
                            # the operator, 2026-08-25, with the verb.
                            "/propose": "/propose-add"}


# The node-id shape (`n0001`), shared by the annotation grammar's
# issue_status classification and the /issue command forms — one regex,
# not one per consumer.
ISSUE_NODE_RE = re.compile(r"^n\d{4}$")

# ONE FLAG, MODULE-GLOBAL, RULED 2026-08-13 (moved here from circle.py
# 2026-08-16, phase 2 stage 0, by explicit ruling). Defaults
# OFF, reversed the same day from the ON-BY-DEFAULT ship, once ruled
# that dev must be reachable and toggleable "whether a circle is
# running" at all: circling's command pane and any no-circle dispatch
# (docs/dual_pane_integration.md) need to read and write this with no
# `main()` invocation alive to hold a local. circle.py's own /dev
# toggle flips this same attribute — there is exactly one dev_mode, not
# one per caller. Read and write as `command_surface.dev_mode`; never
# `from command_surface import dev_mode`, which copies the value at
# import time and goes stale the moment anything toggles it.
dev_mode = False
