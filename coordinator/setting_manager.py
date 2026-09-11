#!/usr/bin/env python3
"""
setting_manager.py — self/settings.toml, the one place a person changes what the
code would otherwise decide. Approved 2026-08-28 (R379).
(settings.py until 2026-09-03 — B99's residue, Q-6 under R435: a register's one
reader/writer is <CLASS>_manager.py, and its gate is its own module —
system_setting_verify.py.)

    python coordinator/setting_manager.py     every setting, its value and its source
    python coordinator/system_setting_verify.py   the gate: SPEC and the call sites agree

THE REGISTER OVERRIDES A CONSTANT; IT DOES NOT REPLACE ONE. Every value here
still has its constant, in its own module, with the paragraph of reasoning
that says why the number is what it is. That paragraph is load-bearing in
this project — remember_manager.py's own comments say four of its numbers are
"Claude's arithmetic, not a ruling, flagged for Self", and record_model's
REGISTERS says "CAP IS IMPORTED, NOT COPIED" directly above the line that
imports it. Moving a number away from its explanation is how this project
has gone wrong before, so nothing moves. The call site reads

    MAX_SINCE_SELF = SET.setting_value_read("statements_per_part", 2)

and the literal it passes IS the documented default. An absent register, an
absent key, or an unreadable file all mean "that default stands" — the same
discipline instrument_manager.py already uses, and the reason a fresh clone, a
worktree and a shipped bundle all work with no file at all.

THE SCHEMA IS CODE; THE VALUES ARE DATA. SPEC below says which settings
exist, what each asks, what it will accept, who may see it and when a change
takes effect. self/settings.toml holds only what a person chose. Which knobs
exist is a property of the program, so it ships and is gated; what they are
set to is one installation's own, so it never ships (packaging/runtime_only.txt).
This is the same split part.toml makes: the questions are mechanism, the
[context.answers] block is the person's.

WHO MAY SEE A SETTING. `audience` is "dev" for all but three. The verb surface
already works this way (R266: USER_SUBSET_COMMANDS / DEV_SUBSET_COMMANDS,
disjoint, "dev adds, never takes away"), and this is that rule one level
down: the verb is available either way, dev mode adds FIELDS. The operator
chose the dev=false starter set on 2026-08-28 and it has grown twice since:
`model`, then `circle_stats` (2026-08-30) and `redact_view` (2026-08-31).
COUNT THEM WITH setting_visible_read(dev=False) RATHER THAN FROM THIS LINE —
3 of 32 today, and the shipped overview names all three because one of them,
redact_view, is a privacy control a recipient would otherwise not know about.

PARTS NEVER SEE ANY OF THIS, and three separate things have to hold:

    1  this register is a source for NO prompt block. BLOCK 2 is
       issue_model.md + the live graph + the relations brief + topics;
       BLOCK 3 is mid_term + identity_tail + instruments. Nothing here.
    2  the verbs are pane = "command" — cmd> only, so no Self> surface and
       therefore no transcript entry at all. Nothing to withhold, by
       construction rather than by a filter.
    3  the verbs are EXCLUDED from the proposable set. THIS IS THE SHARP
       ONE. What a part may name in [proposed: <command>] is
       command_surface.PROPOSE_SUBSET_COMMANDS, minus the deferred, as
       PROPOSABLE_COMMANDS — annotations.py reads those two and has since R267
       (it read DEV_CMD_HEADS before that, and command_surface's own
       comment on DEV_CMD_HEADS still describes it in those terms, which is
       why both are checked below rather than only the live one). A
       settings verb reaching either set would hand a part exactly the
       surface the operator forbade. They are dispatchable and deliberately not
       proposable; coordinator/tests/test_setting_manager.py asserts the
       exclusion against all three sets rather than trusting it.

WHEN A CHANGE TAKES EFFECT. `applies` is "immediate" or "next_circle".

    immediate     written straight to [active]. Refused while a circle is
                  open — circle_state.py answers that and fails closed.
    next_circle   written to [pending], and folded into [active] by
                  setting_pending_fold() at the checkpoint circle.py already runs
                  before a circle's prompts are warmed. That is not a new
                  boundary: the ruling beside that call site says re-vetting
                  any later "would change BLOCK 1 out from under an
                  in-flight transcript", which is the same hazard.

Anything that changes the bytes of a prompt block, the model, or a budget a
block is sized against is next_circle. Nothing needs to change mid-circle;
the operator said so in asking for this.
"""

from __future__ import annotations

import pathlib
import sys

try:
    import tomllib
except ModuleNotFoundError:                                  # 3.10 and older
    import tomli as tomllib                                  # type: ignore

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import record_paths as _RP                                         # noqa: E402

REGISTER = _RP.SELF_DIR / "settings.toml"


@_RP.group_follow
def _register_rebind() -> None:
    """The CURRENT group's settings — B117 stage 4 (2026-09-07); self/ is per group (R467)."""
    global REGISTER
    REGISTER = _RP.SELF_DIR / "settings.toml"

ACTIVE = "active"
PENDING = "pending"

# Accepted types, borrowed from the initialization dialog's own vocabulary
# (R332) so a person meets one set of rules across both editors. BOOL is new
# here, and `record_thinking` is the ONE setting that uses it — "yes"/"no" is
# what a person types. FLOAT is new too — a rate is not a whole number.
#
# THIS SAID "two of these settings are on/off" FROM THE DAY IT WAS WRITTEN
# UNTIL 2026-08-29, while SPEC held none at all. A type declared and unused
# looks exactly like a type in service, and the comment beside it was the only
# thing claiming otherwise. Found while adding the first real one.
TYPES = ("NUMERIC_STRING", "STRING", "BOOL", "FLOAT")

TRUE_WORDS = ("yes", "y", "on", "true", "1")
FALSE_WORDS = ("no", "n", "off", "false", "0")


class Setting:
    """One declared setting. `owner` is file::NAME, the constant that holds
    the default AND the reasoning — the editor prints it so a person can go
    read why the number is what it is, and --check asserts it resolves.

    `why` is that reasoning in ONE SENTENCE, the one `/settings-list <n>` prints
    (R543). Written from the owner's own comment, and
    where the comment records no reason, the sentence says so rather than
    supplying one. IT NEVER STATES THE DEFAULT: the owner's literal is the one
    copy of the number, and system_setting_verify.py refuses a sentence that
    repeats it — "two places asserting the same number, one of them stale"
    is this project's own lesson (remember_manager.GATE_CHAR_CEILING)."""

    __slots__ = ("key", "ask", "data_type", "data_max", "audience",
                 "applies", "owner", "unit", "gate", "why")

    def __init__(self, key, ask, data_type, data_max, audience, applies,
                 owner, unit="", gate="BOUNDED", why=""):
        self.key = key
        self.ask = ask
        self.data_type = data_type
        self.data_max = data_max
        self.audience = audience
        self.applies = applies
        self.owner = owner
        self.unit = unit
        # HOW THIS SETTING IS KEPT VALID — 2026-08-28, "declare the gate
        # kind". EVERY setting is mechanism-facing by definition: the program
        # acts on all of them, none reaches a model as prose. So each declares
        # one, and BOUNDED is the default because most are a number in a
        # range. See settings.check(), which refuses an undeclared or unknown
        # gate rather than assuming.
        self.gate = gate
        self.why = why


def _s(*a, **k) -> Setting:
    return Setting(*a, **k)


# --------------------------------------------------------------- the SPEC
# THE THIRTEEN, plus the model. The operator's phrase was "the dozen or so
# behaviour-setting values"; this is that list, and every entry is one a
# person could reasonably want different. `applies` is next_circle for
# everything that shapes a prompt block or a request, which is most of them.
#
# WHAT IS DELIBERATELY ABSENT. The statement-length guide and the challenge
# rule are sentences in process_core.md, which IS block 1 — making them
# settable means generating that document, which this project retired once
# already (self/circle_briefing.md, 2026-08-11), and the length rule
# currently disagrees with itself in three places (process_core says 100,
# circle_rounds.py's retry string says 150, process.md says a stale 100). Deferred
# on the operator's ruling 2026-08-28: fix the drift first, then decide.
SPEC: tuple[Setting, ...] = (
    # ---- the circle's own shape
    _s("statements_per_part",
       "How many times may one part speak between your turns",
       "NUMERIC_STRING", 5, "dev", "next_circle",
       "coordinator/circle_rounds.py::MAX_SINCE_SELF",
       why="The circle's rule since its first design: a part that reaches it waits for Self, "
           "and Self speaking resets every part's count, so the room keeps returning to Self."),
    _s("statement_max_tokens",
       "The output ceiling for one statement",
       "NUMERIC_STRING", 20000, "dev", "next_circle",
       "coordinator/circle_rounds.py::MAX_TOKENS", unit="tokens",
       why="Headroom for the model's thinking, which counts against this ceiling: a statement "
           "cut off twice is dropped from the circle, and a ceiling left unused costs nothing."),
    _s("short_term_max_tokens",
       "The output ceiling for a part's closing record",
       "NUMERIC_STRING", 20000, "dev", "next_circle",
       "coordinator/circle_close.py::SHORT_TERM_MAX_TOKENS", unit="tokens",   # circle.py's until 2026-09-03
       why="Four sections and a full-length remembered note did not fit in 2,000, and a record "
           "cut short is retried, so a ceiling too small pays for the record twice."),
    _s("quiet_minutes",
       "Minutes of silence before an unclosed circle reads as finished",
       "NUMERIC_STRING", 1440, "dev", "immediate",
       "coordinator/circle_state.py::QUIET_MINUTES", unit="minutes",
       why="A part may think for a long time and a Self prompt waits on a person, so a silence "
           "this long is not a pause, where a shorter one might be."),
    # THE LENGTH RULE'S TWO NUMBERS — ruled 2026-08-28. They reach the parts
    # as prose, in the operator's own sentence, and nothing counts a word:
    # the rule is advisory by design and the ruling says never enforcing it
    # is fine. What was NOT fine was three documents each carrying their own
    # literal; both places that state a number read these now.
    _s("statement_aim_words",
       "The length a part aims for in one statement",
       "NUMERIC_STRING", 1000, "dev", "next_circle",
       "coordinator/prompt_build.py::LENGTH_AIM_WORDS", unit="words",
       why="Ruled 2026-08-28 as the aim of the length rule, which reaches the parts as a sentence "
           "in their rulebook; nothing counts a part's words, and the ruling says that is fine."),
    _s("statement_max_words",
       "The length a part is told never to exceed",
       "NUMERIC_STRING", 2000, "dev", "next_circle",
       "coordinator/prompt_build.py::LENGTH_MAX_WORDS", unit="words",
       why="Ruled 2026-08-28 as the length rule's ceiling; the retry after a cut statement quotes "
           "this same number, so the rule the room is told and the retry cannot disagree."),
    # THE BLIND ROUND AND THE PRE-WARM ARE DELIBERATELY ABSENT, AND NOW HAVE NO
    # CONTROL AT ALL. The reason recorded here was that each already had one a
    # person could reach, --no-blind and --no-prewarm; the operator retired both
    # flags on 2026-09-09 and neither behaviour is switchable any more. That
    # REMOVES a reason to keep them out and supplies no reason to put them in:
    # a setting here would still mean giving argparse a settings-sourced
    # default for a value nothing has ever wanted to change — no invocation of
    # either flag existed anywhere in the tree across its whole life. If one is
    # ever wanted, it is a ruling and a row, not a reinstated flag.
    # ---- what a part is given and allowed to keep
    _s("remember_word_cap",
       "How long a part's own remembered note may be",
       "NUMERIC_STRING", 5000, "dev", "next_circle",
       "coordinator/remember_manager.py::AUTHORED_WORD_CAP", unit="words",
       why="Ruled 2026-08-19 as the length of a part's own remembered note; a longer one is cut, "
           "never refused."),
    _s("remember_budget",
       "How much of a part's remembered notes reach it each circle",
       "NUMERIC_STRING", 200000, "dev", "next_circle",
       "coordinator/remember_manager.py::BUDGET", unit="characters",
       why="Claude's arithmetic, not a ruling: room for about four full-length remembered notes "
           "or about forty short ones, so one long note does not push every older one out of "
           "view."),
    _s("salience_lift",
       "How far a charged memory may jump ahead of a newer one",
       "NUMERIC_STRING", 20, "dev", "next_circle",
       "coordinator/remember_manager.py::SALIENCE_K", unit="places",
       why="Claude's pick, not a ruling: enough for a charged memory to pass a couple of merely "
           "newer ones without a short, deeply chained thread jumping the whole window."),
    _s("remember_gate_ceiling",
       "The largest single remembered note the gate will admit",
       "NUMERIC_STRING", 200000, "dev", "next_circle",
       "coordinator/remember_manager.py::GATE_CHAR_CEILING", unit="characters",
       why="Claude's arithmetic, not a ruling: about twice what a full-length remembered note "
           "measures, so a real one always passes and a runaway still fails."),
    _s("mid_term_budget",
       "How long each part's distilled identity may be",
       "NUMERIC_STRING", 50000, "dev", "next_circle",
       "coordinator/part_mid_term_manager.py::BUDGET", unit="characters",
       why="Sized from the two distillates first made by hand, which ran 3,094 and 4,113 "
           "characters."),
    _s("topics_budget",
       "How much of the open topics is carried into the briefing",
       "NUMERIC_STRING", 50000, "dev", "next_circle",
       "coordinator/topic_manager.py::BUDGET", unit="characters",
       why="About the three newest topics, as the topic design ratified on 2026-08-15 has it: "
           "a topic is a thread carried from a past circle, and the newest come first."),
    # ---- what the processing after a circle is allowed to spend
    # EVERY ONE OF THESE WAS SIZED FOR THINKING, not for length (R354, and
    # the 2026-08-21 raise): this model bills its thinking against the same
    # ceiling, so the visible document is a fraction of the number. Raising
    # one costs nothing until a reply actually gets longer — output is billed
    # on tokens produced — but LOWERING one starves a derivation silently,
    # which is what 2,000 did to four of seven parts at a live close.
    _s("dream_max_tokens",
       "The ceiling for one part's dreaming pass after a circle",
       "NUMERIC_STRING", 64000, "dev", "next_circle",
       "coordinator/part_dreaming.py::DREAM_MAX_TOKENS", unit="tokens",   # inter_circle's until 2026-09-03
       why="Raised from 4,000 on 2026-08-21 after two parts ran out mid-dream: the model's "
           "thinking counts against this ceiling, and the visible dream is only part of it."),
    # B91, 2026-09-04: the grounding heuristic's threshold. A SUSPECT note in
    # the close report, never a refusal — raising it makes the note fire more
    # often, lowering it less. 1 is the floor BOUNDED accepts (a positive
    # whole number), so a memory sharing no content word at all is always
    # noted; the certain case, a silent part's memory, has no knob.
    # next_circle: read at import, like the caps above.
    _s("dream_grounding_min_overlap",
       "How many content words a part's dreamed memory must share with its own lines",
       "NUMERIC_STRING", 50, "dev", "next_circle",
       "coordinator/part_dreaming.py::DREAM_GROUNDING_MIN_OVERLAP", unit="words",
       why="Claude's reading, not a ruling: the smallest count a memory paraphrasing one of the "
           "part's own sentences clears and a memory of another part's moment usually does not; "
           "it only adds a note to the close report."),
    # R451, D86 a, 2026-09-04: the shared room capsule's own cap and ceiling — one
    # model call per circle, never per part.
    _s("dream_capsule_cap",
       "How many characters the shared room capsule may run to",
       "NUMERIC_STRING", 200000, "dev", "next_circle",
       "coordinator/part_dreaming.py::CAPSULE_CAP", unit="characters",
       why="One short paragraph, the same words for every part, as each part's whole view of "
           "the room beyond its own lines; no measurement is recorded beside this number."),
    _s("dream_capsule_max_tokens",
       "The ceiling for the one shared room-capsule call per circle",
       "NUMERIC_STRING", 64000, "dev", "next_circle",
       "coordinator/part_dreaming.py::CAPSULE_MAX_TOKENS", unit="tokens",
       why="No reason is recorded beside this number; the paragraph it pays for is short, but "
           "the model's thinking counts against the same ceiling."),
    _s("synth_max_tokens",
       "The ceiling for the one circle-wide synthesis after a circle",
       "NUMERIC_STRING", 64000, "dev", "next_circle",
       "coordinator/circle_synthesis.py::SYNTH_MAX_TOKENS", unit="tokens",   # inter_circle's until 2026-09-03
       why="Raised from 8,000: one call writes all five sections, the circle's history the "
           "longest of them, and the model's thinking counts against the same ceiling."),
    # B94, 2026-09-04: CIRCLE_JOURNAL's own sizing, not circle_history's — this register
    # reaches Block 1, paid on every part's prompt every circle, and a folded distillate
    # should run smaller than a raw HISTORY entry by construction. Neither number is
    # measured yet; both move without a code change once stage 3's trial informs them.
    _s("circle_journal_cap",
       "How many characters one CIRCLE_JOURNAL entry may run to, refused over",
       "NUMERIC_STRING", 4000, "dev", "next_circle",
       "coordinator/circle_journal_manager.py::CAP", unit="characters",
       why="Tighter than the circle history's own cap, because every character of it is paid on "
           "every part's prompt, every circle; reasoned, not measured, until a trial informs it."),
    _s("circle_journal_target",
       "What the fold is asked for, under the cap so an ordinary overshoot survives",
       "NUMERIC_STRING", 3600, "dev", "next_circle",
       "coordinator/circle_journal_manager.py::TARGET", unit="characters",
       why="Reasoned, not measured: far enough under the cap that a fold which runs a little "
           "long is still kept."),
    _s("derive_max_tokens",
       "The ceiling for distilling one part's identity",
       "NUMERIC_STRING", 64000, "dev", "next_circle",
       "coordinator/part_mid_term_manager.py::DERIVE_MAX_TOKENS", unit="tokens",
       why="Raised twice on measured closes: real distillates run 11,000 to 15,600 characters, "
           "and the model's thinking counts against the same ceiling."),
    # ONE CEILING FOR THE SHORT AUXILIARY CALLS — the coalesce grouping pass
    # and the diagnostic one inter_circle makes when a run fails. Each held
    # its own bare 4000, sized by the same reasoning (thinking bills against
    # the cap, R354) and therefore the same fact in two files.
    _s("auxiliary_max_tokens",
       "The ceiling for the short calls made around a circle",
       "NUMERIC_STRING", 64000, "dev", "next_circle",
       "coordinator/llm_client.py::AUX_MAX_TOKENS", unit="tokens",
       why="Their visible output is a few lines, but the model's thinking counts against the "
           "same ceiling, so even a short call needs headroom."),
    # ---- what the record keeps
    # THE ARCHIVE, NOT THE ROOM. The operator, 2026-08-29: *"keep them if a
    # new boolean setting record_thinking = true"* — ruling on the finding
    # that the model thinks on every statement, that the COUNT of those
    # tokens has been captured all along, and that the reasoning itself was
    # dropped by two filters neither of which was a decision. What a part
    # SAYS is unaffected; thinking never enters the transcript and this does
    # not change that.
    #
    # next_circle, not immediate. The constant is read at import, and a
    # capture directory belongs to one circle: a mid-circle change would
    # leave some turns with the key and some without, in a record whose whole
    # value is being uniform enough to compare across.
    #
    # ONE_OF rather than BOUNDED. A bound is a range and this has none; the
    # valid set is closed, knowable and two words long, which is what ONE_OF
    # is for (see `provider` below, ruled the same way).
    _s("record_thinking",
       "Whether the saved record keeps what the model thought",
       "BOOL", 1, "dev", "next_circle",
       "coordinator/llm_client.py::RECORD_THINKING", gate="ONE_OF",
       why="Ruled 2026-08-29: keep the model's reasoning in the saved record, never in the room; "
           "it costs disk, not money, since those tokens are already bought."),
    # THE DELTA REPORT AT CLOSE — the operator, 2026-08-30: "print auto at
    # close if a new setting, circle_stats = true; include the setting in the
    # UI settings tab. Report also as a file, only when circle_stats = true."
    # `user`, because the UI settings pane serves dev=False unconditionally
    # and the ruling names that pane. `immediate`, because the report shapes
    # no prompt and spends nothing — it reads the record after the circle is
    # already committed — and circle_delta.circle_delta_is_enabled() reads at use, not
    # import, so the value set is the value honoured at the next close.
    _s("circle_stats",
       "Whether a circle's close prints and files its delta report",
       "BOOL", 1, "user", "immediate",
       "coordinator/circle_delta.py::CIRCLE_STATS", gate="ONE_OF",
       why="Asked for on 2026-08-30: the delta report printed at every close and filed beside "
           "it."),
    # THE REDACTED VIEW — the operator, 2026-08-31: "a raw/redacted switch
    # can be on the settings page ... applied: only in the top pane, never
    # in any lower tab." `user`, same reasoning as circle_stats: this is
    # ui/circling.py's own CIRCLE-pane toggle, not a dev tool. `immediate`
    # for the same reason too — it shapes no prompt and spends nothing, it
    # only changes what the pane RENDERS. One nuance worth knowing rather
    # than assuming away: `SET.write()` still defers the SAVED value to
    # `[pending]` while a circle is open, same as every other setting, even
    # though the LIVE pane view flips at once through its own signal
    # (ui/circling.py's Pane.set_redact(), wired from cmd_settings_update) —
    # so toggling mid-circle changes what you see now, and the saved
    # default for the NEXT circle, on two different clocks. Worth saying
    # both halves in the reply text rather than letting it read as if it
    # behaved like every other immediate setting.
    _s("redact_view",
       "Whether the CIRCLE pane shows names/emails/phones as opaque "
       "tokens instead of the real text",
       "BOOL", 1, "user", "immediate",
       "coordinator/stream_redaction.py::REDACT_VIEW_DEFAULT", gate="ONE_OF",
       why="No reason is recorded for leaving it off; turned on, it hides names, emails and phone "
           "numbers in the circle pane only, and never a part's name."),
    # THE CLOSE'S OWN CLOCK — ruled 2026-08-30: "After circle /close, I want
    # to aim for no more than 5 minutes, and progress must be being reported
    # in the command pane at least every 10 seconds, even if its just a
    # spinner." The aim is REPORTED, never enforced — a slow close must not
    # fail a close that otherwise held. The heartbeat is the progress line
    # phase_clock prints while the close pipeline works.
    _s("close_aim_seconds",
       "The wall-clock aim for everything after /close",
       "NUMERIC_STRING", 3600, "dev", "next_circle",
       "coordinator/circle.py::CLOSE_AIM_SECONDS", unit="seconds",
       why="Ruled 2026-08-30 as the aim for everything after /close; reported, never enforced, "
           "so a slow close never fails one that otherwise held."),
    # THE ALARM IS A SECOND NUMBER, NOT THE AIM MOVED — R540. A close
    # past the aim but within this is reported plainly; past this, loudly.
    _s("close_alarm_seconds",
       "How long a close may run before its last line sounds the alarm",
       "NUMERIC_STRING", 3600, "dev", "next_circle",
       "coordinator/circle.py::CLOSE_ALARM_SECONDS", unit="seconds",
       why="A close that runs between the aim and this was ruled not unusual on 2026-09-10, so "
           "only one that runs past it sounds the alarm."),
    _s("close_heartbeat_seconds",
       "How often the close reports progress while it works",
       "NUMERIC_STRING", 120, "dev", "next_circle",
       "coordinator/inter_circle.py::CLOSE_HEARTBEAT_SECONDS", unit="seconds",
       why="The close's own progress beat, from the 2026-08-30 ruling; the beat is armed at "
           "circle open now, so only a hand re-run of the processing after a circle reads it."),
    # DEV, LIKE ITS SIBLING ABOVE, AND THAT IS A QUESTION RATHER THAN A
    # CONCLUSION. The rule it serves is about a person watching a blank screen,
    # which argues for `user` — but the dev=false set is exactly three today
    # (model, circle_stats, redact_view), it is the operator's own 2026-08-28
    # selection, and each of the two widenings since was ruled. Adding a fourth
    # is his call, and test_setting_manager.py pins the set precisely so it
    # cannot be widened by someone passing through. Raised, not taken.
    _s("progress_seconds",
       "How long a silence may last before the app says it is still working",
       "NUMERIC_STRING", 120, "dev", "next_circle",
       "coordinator/circle.py::PROGRESS_SECONDS", unit="seconds",
       why="Ruled 2026-09-09: any silence longer than this while the program works gets a "
           "progress mark, so a person is never left watching a still screen."),
    # ---- what the service charges
    # THESE PRICE A REPORT; THEY DO NOT SPEND ANYTHING. Immediate, because
    # nothing in flight depends on them and a person correcting a price
    # should see the corrected figure at once. They are here because a
    # real future price change (Sonnet 5's own 2026-09-01 rise did NOT
    # happen — Anthropic made the $2/$10 rate permanent, 2026-08-10/11;
    # audit-register.md #27) needs a way to be recorded without editing
    # Python.
    #
    # THE RATES RODE THE MODEL ON 2026-08-30 (B74(2)), and these four became
    # the FALLBACK rather than the price. This comment used to say "v2 should
    # move these onto the model ... left flat here because that is a second
    # document shape, and the price rise is four days away" — the shape is
    # built now (setting_model_rate_rows_read() above, `[[model]]` in the register), the
    # rise is a day away, and llm_client._BUILTIN_RATES carries a row per
    # (model, speed) so a second model is no longer priced at the first
    # one's numbers. What these four still do is price a model NOBODY has a
    # row for, which the usage report flags as RATES UNKNOWN rather than
    # passing off as known.
    _s("rate_in", "Fallback price per million input tokens, for a model with "
       "no rates on file", "FLOAT", 1000, "dev", "immediate",
       "coordinator/llm_client.py::RATE_IN", unit="USD/Mtok",
       why="The published input price of the parts' default model, re-verified 2026-09-01; it "
           "prices only a model with no rates of its own on file."),
    _s("rate_cache_write_1h", "Fallback price per million tokens written to "
       "the cache", "FLOAT", 1000, "dev", "immediate",
       "coordinator/llm_client.py::RATE_CACHE_WRITE_1H", unit="USD/Mtok",
       why="Twice the input price, the ratio every published price list has used; it prices "
           "only a model with no rates of its own on file."),
    _s("rate_cache_read", "Fallback price per million tokens read from the "
       "cache", "FLOAT", 1000, "dev", "immediate",
       "coordinator/llm_client.py::RATE_CACHE_READ", unit="USD/Mtok",
       why="A tenth of the input price, the ratio every published price list has used; it "
           "prices only a model with no rates of its own on file."),
    _s("rate_out", "Fallback price per million output tokens, for a model "
       "with no rates on file", "FLOAT", 1000, "dev", "immediate",
       "coordinator/llm_client.py::RATE_OUT", unit="USD/Mtok",
       why="The published output price of the parts' default model, re-verified 2026-09-01; it "
           "prices only a model with no rates of its own on file."),
    # ---- the service the parts run on
    # THE ONE THE ORDINARY USER SEES, the operator, 2026-08-28: "the model, and
    # nothing else at first". `provider` is declared and single-valued in v1
    # — the register's shape is right on day one, and the adapter behind the
    # thirty-odd Anthropic touch points is its own project.
    # CHECK_AT_USE, AND THIS IS THE CASE THE GATE KIND EXISTS FOR. What models are
    # valid is whatever this account can reach, which changes without this
    # code changing — so a closed list here would refuse a model that works,
    # and there is no local set to check against. The check is the FIRST REAL
    # USE: llm_client.stream_api_preflight() makes one real call before anything is
    # written, and the provider's explain() names the model in its 404 branch
    # ("The model X is not available to this key").
    #
    # DECLARING IT IS THE WHOLE POINT. Until 2026-08-28 this setting declared
    # nothing, which looked identical to a setting nobody had thought about.
    _s("model",
       "Which model the parts speak on",
       "STRING", 60, "user", "next_circle",
       "coordinator/llm_client.py::MODEL", gate="CHECK_AT_USE",
       why="The parts run on the Sonnet tier to keep cost down; any model this account can "
           "reach is accepted, and the first real call checks it."),
    # ONE_OF: unlike the model, the valid set IS knowable here and is closed
    # by ruling (R383) — PROVIDERS_SUPPORTED is it.
    _s("provider",
       "Which service the model runs on",
       "STRING", 40, "dev", "next_circle",
       "coordinator/llm_client.py::PROVIDER", gate="ONE_OF",
       why="The only service this build can talk to; adding a second is a decision about what "
           "leaves this machine, not only about code."),
)

BY_KEY: dict[str, Setting] = {s.key: s for s in SPEC}

# `provider` accepts exactly this, and --check asserts SPEC still says so.
# A provider selector is a policy surface as well as a technical one: this
# project's standing rule is that nothing leaves this machine, so a second
# entry here is a decision about that rule, not only about code.
PROVIDERS_SUPPORTED = ("Anthropic",)


# ------------------------------------------------------------------ reading
# CACHED ON THE FILE'S OWN STAMP, not on first read. A circle is normally one
# process, so an import-time read would do — but ui/circling.py runs
# circle.py's main() in a thread of a LONG-LIVED process, and a person who
# edits a setting there and opens another circle must get the value they set.
# Keying the cache on (mtime, size) costs one stat per lookup and cannot go
# stale in either surface.
_cache: dict = {}
_stamp: tuple | None = None


def _stat() -> tuple | None:
    try:
        st = REGISTER.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def setting_read() -> dict:
    """The register, or {} when there is none. ABSENCE IS NOT A FAILURE — a
    fresh clone, a worktree and a shipped bundle all have no file, and every
    default stands. A CORRUPT file is different and is not silently ignored:
    it returns {} and says so, because a person who wrote a setting is owed
    the news that it did not parse."""
    global _cache, _stamp
    now = _stat()
    if now is None:
        _cache, _stamp = {}, None
        return {}
    if now == _stamp:
        return _cache
    try:
        doc = tomllib.loads(REGISTER.read_text(encoding="utf-8"))
    except Exception as e:                                     # noqa: BLE001
        _say(f"  self/settings.toml did not parse ({type(e).__name__}) — "
             f"every setting is at its default. /settings-list shows what "
             f"is in force")
        _cache, _stamp = {}, now
        return {}
    _cache, _stamp = doc, now
    return doc


def setting_model_rate_rows_read() -> dict:
    """`[[model]]` rows from the register, as llm_client's own rate table
    wants them: `{(id, speed): (in, cache_write_1h, cache_read, out)}`.

    B74(2), built 2026-08-30 — the second document shape this file's own
    comment said the rates belonged in. A price is a fact about a MODEL, and
    until now the four flat settings priced whichever model happened to be
    selected, so picking a second one silently charged it at the first one's
    rates. A row here overrides llm_client's built-in table for that exact
    (id, speed), which is what makes the 2026-09-01 rise a TOML edit.

        [[model]]
        id = "claude-opus-5"
        speed = "standard"        # optional; "standard" when omitted
        rate_in = 5.50
        rate_out = 27.50
        # rate_cache_write_1h and rate_cache_read are optional and default to
        # 2x and 0.1x rate_in, the ratios every published list has used

    MALFORMED ROWS ARE SKIPPED AND SAID SO, one line each, never raised: a
    typo in a price must not stop a circle opening, and a silently dropped
    row would price a model wrongly with nothing on screen — the exact
    failure this entry exists to end."""
    rows = setting_read().get("model")
    if not isinstance(rows, list):
        return {}
    out: dict = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            _say(f"  self/settings.toml: [[model]] #{i + 1} is not a table "
                 f"— skipped")
            continue
        mid = row.get("id")
        speed = row.get("speed", "standard")
        try:
            r_in = float(row["rate_in"])
            r_out = float(row["rate_out"])
        except (KeyError, TypeError, ValueError):
            _say(f"  self/settings.toml: [[model]] {mid!r} needs a numeric "
                 f"rate_in and rate_out — skipped, so it is priced at the "
                 f"built-in or default row")
            continue
        if not isinstance(mid, str) or not mid or not isinstance(speed, str):
            _say(f"  self/settings.toml: [[model]] #{i + 1} needs a string "
                 f"id (and speed, if given) — skipped")
            continue
        try:
            r_cw = float(row.get("rate_cache_write_1h", r_in * 2))
            r_cr = float(row.get("rate_cache_read", r_in / 10))
        except (TypeError, ValueError):
            _say(f"  self/settings.toml: [[model]] {mid!r} has a "
                 f"non-numeric cache rate — skipped")
            continue
        out[(mid, speed)] = (r_in, r_cw, r_cr, r_out)
    return out


def setting_value_read(key: str, default):
    """The active override for `key`, or `default`.

    `default` is the caller's own constant, and it is the documented default
    — --check reads it back out of the source text and reports it, so the
    editor can show a person what they are changing from without this module
    keeping a second copy of every number.

    A value that does not fit its declaration is IGNORED, loudly, not
    coerced: a person who typed something the editor would have refused has
    edited the file by hand, and quietly running on a number nobody chose is
    the worse of the two failures."""
    spec = BY_KEY.get(key)
    if spec is None:                          # not a declared setting at all
        return default
    raw = (setting_read().get(ACTIVE) or {}).get(key)
    if raw is None:
        return default
    ok, parsed, why = setting_coerce(spec, raw)
    if not ok:
        # RULED 2026-08-28: replaced by the default, reported, and the report
        # names the command that tunes it. Buffered — see CORRECTIONS.
        _say(f"  self/settings.toml: {key} = {raw!r} {why} — using the "
             f"default {default!r}. Change it with /settings-update {key}")
        return default
    return parsed


def setting_coerce(spec: Setting, raw):
    """(ok, parsed, why). The one place a stored value is checked, shared by
    setting_value_read() above and by the editor before it writes — so a hand-edited file
    is held to exactly what the dialog would have accepted."""
    if spec.data_type == "BOOL":
        if isinstance(raw, bool):
            return True, raw, ""
        t = str(raw).strip().lower()
        if t in TRUE_WORDS:
            return True, True, ""
        if t in FALSE_WORDS:
            return True, False, ""
        return False, None, "is not yes or no"
    if spec.data_type == "NUMERIC_STRING":
        try:
            n = int(str(raw).strip())
        except ValueError:
            return False, None, "is not a whole number"
        if n < 1:
            return False, None, "is not a positive whole number"
        if n > spec.data_max:
            return False, None, f"is over the {spec.data_max:,} allowed"
        return True, n, ""
    if spec.data_type == "FLOAT":
        try:
            f = float(str(raw).strip())
        except ValueError:
            return False, None, "is not a number"
        if f < 0:
            return False, None, "is negative"
        if f > spec.data_max:
            return False, None, f"is over the {spec.data_max:,} allowed"
        return True, f, ""
    # STRING
    t = str(raw).strip()
    if len(t) > spec.data_max:
        return False, None, f"is over {spec.data_max} characters"
    if spec.key == "provider" and t not in PROVIDERS_SUPPORTED:
        return False, None, (f"is not a service this build can talk to "
                             f"({', '.join(PROVIDERS_SUPPORTED)})")
    return True, t, ""


def setting_accepts_read(spec: Setting) -> str:
    """What setting_coerce() above will take for `spec`, in words — the line `/settings-list <n>`
    prints as `accepts` (R543). Kept BESIDE the check it describes, branch
    for branch, so a rule changed in one is in front of whoever changes the other."""
    if spec.data_type == "BOOL":
        return "yes or no"
    if spec.data_type == "NUMERIC_STRING":
        return f"a whole number from 1 to {spec.data_max:,}"
    if spec.data_type == "FLOAT":
        return f"a number from 0 to {spec.data_max:,}"
    if spec.key == "provider":
        return "one of: " + ", ".join(PROVIDERS_SUPPORTED)
    if spec.gate == "CHECK_AT_USE":
        return (f"up to {spec.data_max} characters; whether this account can reach it is "
                f"checked at the first real call")
    return f"up to {spec.data_max} characters"


def setting_visible_read(dev: bool) -> tuple[Setting, ...]:
    """What the editor lists. Dev mode ADDS fields; it never takes one away —
    R266's rule about the two verb tables, one level down."""
    return SPEC if dev else tuple(s for s in SPEC if s.audience == "user")


# ------------------------------------------------------- per-provider tuning
# STAGE 4 OF THE SOCKET (R382) — the operator's `model_tuning`, declared
# rather than opaque. A provider declares its own knobs (providers.Knob) and
# TRANSLATES them onto the wire; this file stores and validates them, so the
# shared surface never grows a parameter when one vendor adds one.
#
# NAMESPACED BY PROVIDER, so switching providers does not destroy what you
# set: `[tuning.anthropic] effort = "high"` survives a trip to another
# provider and back. A key under a KNOWN provider that the provider does not
# declare is REFUSED; a whole table for a provider this build does not have is
# kept and ignored, for the same reason.
TUNING = "tuning"


def _knobs(provider) -> dict:
    return {k.key: k for k in getattr(provider, "TUNING", ())}


def setting_tuning_read(provider) -> dict:
    """This installation's tuning for `provider`, validated against what that
    provider declares. Anything unrecognised or out of range is dropped with a
    word to the console — never coerced, and never silently obeyed."""
    table = (setting_read().get(TUNING) or {}).get(_slug(provider), {}) or {}
    known, out = _knobs(provider), {}
    for key, raw in table.items():
        knob = known.get(key)
        if knob is None:
            _say(f"  self/settings.toml: {provider.name} declares no tuning "
                 f"called {key!r} — ignored")
            continue
        import part_roster as R
        why = R.part_context_value_verify(knob.as_question(), str(raw))
        if why is not None:
            # RULED 2026-08-28: a stored value that fails validation is
            # REPLACED BY THE DEFAULT and reported, naming the command that
            # tunes it. Not dropped in silence, and not obeyed.
            _say(f"  self/settings.toml: {key} = {raw!r} {why.strip()} "
                 f"— using {knob.default!r}. "
                 f"Change it with /settings-update {key}")
            continue
        out[key] = R.part_canonical_read(knob.as_question(), str(raw))
    return out


def setting_tuning_defaults_read(provider) -> dict:
    return {k.key: k.default for k in getattr(provider, "TUNING", ())}


def setting_tuning_write(provider, key: str, raw) -> tuple:
    """Record one knob. Always PENDING: a tuning change alters what is sent,
    and on this provider it alters the output ceiling too, so it waits for the
    boundary every prompt-shaping change waits for."""
    knob = _knobs(provider).get(key)
    if knob is None:
        return False, f"{provider.name} has no setting called {key}"
    import part_roster as R
    why = R.part_context_value_verify(knob.as_question(), str(raw))
    if why is not None:
        return False, f"{raw!r} {why.strip()}"
    doc = dict(setting_read())
    tune = dict(doc.get(TUNING) or {})
    mine = dict(tune.get(_slug(provider)) or {})
    import part_roster as R
    mine[key] = R.part_canonical_read(knob.as_question(), str(raw))
    tune[_slug(provider)] = mine
    doc[TUNING] = tune
    _dump(doc)
    return True, f"{key} = {raw} — takes effect when the next circle opens"


def _slug(provider) -> str:
    return provider.name.strip().lower()


# CORRECTIONS ARE BUFFERED, NOT PRINTED — 2026-08-28, and this is not a
# nicety. Settings are read at IMPORT, and ui/circling.py rebinds seam.emit
# only in start(); its own comment says so. So a report emitted while
# `import circle` runs goes to the real print, underneath the alt-screen,
# where nobody sees it. In the single-pane CLI it would have worked; in the
# two-pane UI — the way a person opens a circle since R314 — it would have
# been lost, and every test I run would still have passed.
#
# So they queue here and are flushed by whoever has a surface. The ruling was
# "report to the command pane"; a message that cannot reach the pane does not
# satisfy it.
CORRECTIONS: list = []


def _say(msg: str) -> None:
    CORRECTIONS.append(msg)


def setting_corrections_flush(emit=None) -> int:
    """Show and clear whatever was queued. Called once a surface exists —
    circle.py at open, and the command pane on its first use. Returns how
    many were shown, so a caller can stay quiet when there were none."""
    if not CORRECTIONS:
        return 0
    if emit is None:
        import seam
        emit = lambda t: seam.emit("command", t)          # noqa: E731
    emit("")
    emit("  SETTINGS CORRECTED — a stored value did not pass its own check:")
    for line in CORRECTIONS:
        emit(line)
    emit("")
    n = len(CORRECTIONS)
    CORRECTIONS.clear()
    return n


def setting_pending_read() -> dict:
    """Changes written but not yet folded. Shown by the editor so a person
    can see what is waiting, and by circle.py at the checkpoint."""
    return dict(setting_read().get(PENDING) or {})


def setting_active_read() -> dict:
    return dict(setting_read().get(ACTIVE) or {})


# ------------------------------------------------------------------- writing
def setting_write(key: str, raw, *, now: bool) -> tuple[bool, str]:
    """Record one setting. `now` is the caller's answer to "may this take
    effect immediately" — commands.py asks circle_state, this module does
    not, so that the one process that knows whether a circle is open is the
    one that decides. Returns (ok, message-for-the-person).

    ATOMIC, and through REGISTER_CLASS's own dumper — a settings file this
    module wrote must round-trip, for the same reason every other register
    in self/ must."""
    spec = BY_KEY.get(key)
    if spec is None:
        return False, f"{key} is not a setting"
    ok, parsed, why = setting_coerce(spec, raw)
    if not ok:
        return False, f"{raw!r} {why}"
    table = ACTIVE if (spec.applies == "immediate" and now) else PENDING
    doc = dict(setting_read())
    doc.setdefault(ACTIVE, {})
    doc.setdefault(PENDING, {})
    doc[table] = dict(doc.get(table) or {})
    doc[table][key] = parsed
    if table == ACTIVE:
        doc[PENDING].pop(key, None)          # a later immediate write wins
    _dump(doc)
    when = ("now" if table == ACTIVE
            else "when the next circle opens")
    return True, f"{key} = {parsed} — takes effect {when}"


def setting_clear(key: str) -> tuple[bool, str]:
    """Back to the code's own default, from both tables."""
    if key not in BY_KEY:
        return False, f"{key} is not a setting"
    doc = dict(setting_read())
    hit = False
    for table in (ACTIVE, PENDING):
        t = dict(doc.get(table) or {})
        if key in t:
            t.pop(key)
            hit = True
        doc[table] = t
    if not hit:
        return False, f"{key} was already at its default"
    _dump(doc)
    return True, f"{key} is back to its default"


def setting_pending_fold() -> list[str]:
    """Move every pending change into [active]. Called at the checkpoint
    circle.py runs BEFORE a circle's prompts are warmed — the one moment a
    value that shapes a prompt block may move without changing block 1 out
    from under a transcript already in flight. Returns the keys folded, so
    the caller can say what changed."""
    doc = dict(setting_read())
    pend = dict(doc.get(PENDING) or {})
    if not pend:
        return []
    act = dict(doc.get(ACTIVE) or {})
    act.update(pend)
    doc[ACTIVE], doc[PENDING] = act, {}
    _dump(doc)
    return sorted(pend)


def _dump(doc: dict) -> None:
    """Written through atomic_write, like every other register — a half
    written settings file would take every default silently."""
    from atomic_write import record_atomic_write
    lines = ["# self/settings.toml — what THIS installation has changed.",
             "#",
             "# Written by coordinator/setting_manager.py; edit it here or through",
             "# /settings-update at the command prompt. A key that is absent",
             "# means the code's own default stands — see that default, and",
             "# the reasoning for it, at the source named by",
             "# `python coordinator/setting_manager.py`.",
             "#",
             "# [active]  in force now.",
             "# [pending] waiting for the next circle to open.",
             ""]
    for table in (ACTIVE, PENDING):
        lines.append(f"[{table}]")
        for k in sorted(doc.get(table) or {}):
            lines.append(f"{k} = {_lit((doc[table])[k])}")
        lines.append("")
    # [tuning.<provider>] — one table per provider, so what you set for one
    # survives a trip to another and back. Written after the two flat tables
    # because a TOML sub-table would otherwise swallow the keys that follow it.
    for prov in sorted(doc.get(TUNING) or {}):
        rows = (doc[TUNING] or {}).get(prov) or {}
        if not rows:
            continue
        lines.append(f"[{TUNING}.{prov}]")
        for k in sorted(rows):
            lines.append(f"{k} = {_lit(rows[k])}")
        lines.append("")
    REGISTER.parent.mkdir(parents=True, exist_ok=True)
    record_atomic_write(REGISTER, "\n".join(lines).rstrip("\n") + "\n")
    global _stamp
    _stamp = None                            # next read re-stats, never stale


def _lit(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


# ------------------------------------------------- what the owning module declares
# setting_source_default_read() is READ BY BOTH HALVES — the report below prints the
# default a row falls back to, and system_setting_verify.py asserts it against SPEC.
# It was `_source_default` and private here until 2026-09-03, when the gate left.
def setting_source_default_read(owner: str, key: str = "") -> tuple[str | None, str]:
    """The literal the owning module passes to setting_value_read(), GREPPED FROM SOURCE
    and never imported — the same discipline, and the same reason, as
    prompt_capture._source_constant(): a verifier the pre-commit hook runs
    must not pull `anthropic` and an API-key check in behind it.

    THE DEFAULT IS THE CALL SITE'S SECOND ARGUMENT, not the whole right-hand
    side. `MAX_SINCE_SELF = SET.setting_value_read("statements_per_part", 2)` documents 2,
    and reading the RHS whole would report the call itself as the default —
    which is what this did until it was read back on 2026-08-28."""
    import re
    path, _, name = owner.partition("::")
    if not name:
        return None, "owner is not file::NAME"
    try:
        src = (ROOT / path).read_text(encoding="utf-8")
    except OSError:
        return None, f"{path} is unreadable"
    m = re.search(r"^" + re.escape(name) + r"\s*=\s*(.+?)\s*(?:#.*)?$",
                  src, re.M)
    if not m:
        return None, f"{name} is not assigned at the top level of {path}"
    rhs = m.group(1).strip()
    inner = re.match(r'(?:SET\.)?setting_value_read\(\s*["\']' + re.escape(key or name)
                     + r'["\']\s*,\s*(.+?)\s*\)$', rhs)
    lit = inner.group(1) if inner else rhs
    # SHOWN TO A PERSON, so the source's own quotes come off: a default read
    # back as `"claude-sonnet-5"` reads as if the quotes were part of the
    # model's name, and the value they would type has none.
    if len(lit) > 1 and lit[0] == lit[-1] and lit[0] in "\"'":
        lit = lit[1:-1]
    return lit, ""


def setting_show(key: str, v) -> str:
    """One value, in the words the person who sets it would use.

    THE FIRST BOOL MADE THIS NECESSARY — 2026-08-29. Everything before it was
    a number or a string, which reads the same in Python and in a sentence. A
    BOOL does not: the register stores a real TOML `true`, `setting_source_default_read`
    greps `True` out of the source, and the dialog asks a question whose
    answer is `yes`. Three vocabularies for one setting, in front of the one
    person the register exists for. The editor renders through here instead."""
    spec = BY_KEY.get(key)
    if spec is None or spec.data_type != "BOOL":
        return str(v)
    ok, parsed, _why = setting_coerce(spec, v)
    if not ok:
        return str(v)
    return "yes" if parsed else "no"


# ------------------------------------------------------------- one, whole
# `/settings-list <n>` — R543, answering D122 (c). The listing's row, and
# what the listing leaves out: the value the program uses when nothing is changed, what the
# setting accepts, and why the default is what it is. `now`, `default`, `waiting` and `accepts`
# are worked out here; every other key is a slot of the declaration itself, so a slot added
# later is shown without this learning its name — REGISTER_CLASS.register_record_show() walks
# these orders first, then whatever else the record carries.
RECORD_ORDER = ("key", "ask", "now", "default", "unit", "waiting", "accepts", "applies", "why")
TUNING_RECORD_ORDER = ("key", "ask", "now", "default", "values", "applies")
# DEV ADDS FIELDS, IT NEVER TAKES ONE AWAY — R266's rule, one level down, as this module's
# docstring puts it. These are the mechanism slots: a person running without --dev has no use
# for them, and their names would announce the surface dev=false keeps back.
DEV_FIELDS = ("owner", "data_type", "data_max", "audience", "gate")


def _unchanged(chosen: bool) -> str:
    return "" if chosen else "   (unchanged)"


def setting_record_read(spec: Setting, *, dev: bool) -> dict:
    """`spec` whole, as `/settings-list <n>` shows it. The unit is its own line, beside the two
    values it measures, rather than said three times."""
    lit, _msg = setting_source_default_read(spec.owner, spec.key)
    act, pend = setting_active_read(), setting_pending_read()
    rec = {k: getattr(spec, k) for k in Setting.__slots__ if dev or k not in DEV_FIELDS}
    rec["now"] = (setting_show(spec.key, act[spec.key] if spec.key in act else lit)
                  + _unchanged(spec.key in act))
    rec["default"] = setting_show(spec.key, lit)
    if spec.key in pend:
        rec["waiting"] = f"{setting_show(spec.key, pend[spec.key])} — from the next circle"
    rec["accepts"] = setting_accepts_read(spec)
    return rec


def setting_tuning_record_read(provider, knob, *, dev: bool) -> dict:
    """One of `provider`'s own knobs whole. No `why`: a knob is that service's declaration, and
    what it accepts is its business (commands._settings_tuning_row_emit says the same)."""
    chosen = setting_tuning_read(provider)
    rec = {k: getattr(knob, k) for k in type(knob).__slots__ if dev or k not in DEV_FIELDS}
    rec["now"] = str(chosen.get(knob.key, knob.default)) + _unchanged(knob.key in chosen)
    return rec


# The verbs this register owns. Named here, not in command_surface, so the
# exclusion check above has one list to test and cannot be fooled by a verb
# added to the dispatcher and forgotten here: test_setting_manager.py asserts this
# tuple covers every "/settings-" head command_surface knows.
SETTINGS_VERBS = ("/settings-list", "/settings-update", "/settings-clear")


def setting_report() -> int:
    doc = setting_read()
    act, pend = doc.get(ACTIVE) or {}, doc.get(PENDING) or {}
    print(f"settings — {REGISTER}"
          f"{'' if REGISTER.is_file() else '  (no file; every default stands)'}")
    print()
    for s in SPEC:
        lit, why = setting_source_default_read(s.owner, s.key)
        shown = act.get(s.key)
        mark = "" if s.key in act else "  (default)"
        cur = shown if s.key in act else (lit or "?")
        row = f"  {s.key:<24} {str(cur):<16}{mark}"
        print(row)
        print(f"      {s.ask}")
        print(f"      {s.audience:<5} · {s.applies:<12} · {s.owner}"
              + (f" · {why}" if why else ""))
        if s.key in pend:
            print(f"      PENDING -> {pend[s.key]} at the next circle")
    return 0


def main(argv: list[str]) -> int:
    return setting_report()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
