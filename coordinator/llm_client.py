#!/usr/bin/env python3
"""
llm_client.py — the Messages-API transport: the model id and its
rates, the usage meter, the one stream_call() wrapper, Self's retry ladder,
the key diagnostics, the preflight, and the cache pre-warm. Phase 2
stage 1 of the coordinator partitioning (2026-08-16); until then all
of it lived in circle.py. Verbatim move — bodies and comments
unchanged, except console output goes through `seam.emit` by attribute
access (the seam contract in seam.py).

TRANSPORT ONLY, deliberately: part_statement_ask() stays in circle.py (for
rounds, stage 7) — it is round-logic wearing an API call, and the
phase-2 review's correction of the original plan's "llm_client is
self-contained" claim was exactly this line. What it needs of the
coordinator is small and named: record_paths.PART_TAGS, seam, settings, providers
(the vendor seam, R382), and record_model for the four short_term headings it
must not keep a second copy of.

METER is a module singleton MUTATED IN PLACE (add()) and never
reassigned — circle.py's `from llm_client import METER` aliases the
same object, the same contract seam.FAILURES documents.
"""

from __future__ import annotations

import threading
import time

import command_surface as CS
import seam
import setting_manager as SET
import providers as _providers
import LLM_response_disassembler as RD
from record_paths import PART_TAGS
# `os` and `ROOT` left with the provider at stage 2 — the only readers here
# were the credential diagnostics, and a credential's name and its file are
# the vendor's, not the transport's.

# EVERY LITERAL BELOW IS STILL THE DOCUMENTED DEFAULT. setting_manager.setting_value_read()
# returns it unless self/settings.toml overrides that key, and an absent
# register — a fresh clone, a worktree, a shipped bundle — means every one of
# these stands exactly as written. See coordinator/setting_manager.py.
MODEL = SET.setting_value_read("model", "claude-sonnet-5")   # parts run on sonnet (cost tiering)
PROVIDER = SET.setting_value_read("provider", "Anthropic")   # who MODEL's requests go to — named
                                        # in the initialization dialogs' privacy
                                        # statement
CACHE_TTL = "1h"                        # circles have pauses longer than 5m

# Verified 2026-07-26 from platform.claude.com/docs — Claude Sonnet 5,
# USD per MTok. STILL CORRECT — re-verified 2026-09-01 (audit-register.md
# #27) directly against platform.claude.com/docs/en/about-claude/pricing:
# Anthropic made the $2/$10 introductory rate permanent on 2026-08-10/11
# and CANCELLED the 3.00/6.00/0.30/15.00 rise this comment used to warn
# about here — a warning this project's own tree kept past the date the
# warning itself expired, which is precisely the audit's own finding: a
# tripwire firing on stale ground rather than a real drift. What made
# these settable (2026-08-28) still stands: a real future price change is
# a self/settings.toml [[model]] row or a flat-setting override, not a
# Python edit.
RATE_IN = SET.setting_value_read("rate_in", 2.00)
RATE_CACHE_WRITE_1H = SET.setting_value_read("rate_cache_write_1h", 4.00)   # 2x base
RATE_CACHE_READ = SET.setting_value_read("rate_cache_read", 0.20)           # 0.1x base
RATE_OUT = SET.setting_value_read("rate_out", 10.00)

# THE SHORT AUXILIARY CALL'S CEILING — one home, 2026-08-28. coalesce and
# inter_circle each held a bare 4000, and I called that a coincidence when
# system_unique_home_verify flagged it. It is not: coalesce's own comment cites
# DERIVE_MAX_TOKENS's lesson (R354), so the two were sized by the SAME
# reasoning and landed on the same number for the same reason — thinking bills
# against the cap, so even a call whose visible output is a few lines needs
# generous headroom.
#
# THE OUTPUTS GENUINELY DIFFER — "a few lines" for a grouping pass, "a few
# paragraphs" for a diagnostic — and neither is what sets this number. The
# thinking is. If one of them ever needs its own ceiling it declares one, and
# that is then a visible decision rather than a silent divergence.
AUX_MAX_TOKENS = SET.setting_value_read("auxiliary_max_tokens", 4000)

# WHETHER THE CAPTURE KEEPS WHAT THE MODEL THOUGHT — R386,
# *"keep them if a new boolean setting record_thinking = true"*, ruling on the
# finding that thinking arrives on every statement and was being dropped twice:
# by providers.read() for the transcript and by _response_record() (now
# LLM_response_disassembler.message_burst(), which takes this setting as an argument)
# for the archive. THE TRANSCRIPT DROP STAYS. Thinking never enters the room, and that
# was not what was ruled on. This is the archive alone.
#
# DEFAULT ON, because the ruling was to keep them and a default of off would
# make it inert. The setting is how it gets turned back OFF.
#
# WHAT IT COSTS IS DISK, NOT MONEY. The tokens are already bought and already
# counted — usage.output_tokens_details.thinking_tokens has ridden into every
# turn file since the captures began, which is where "thinking is 55% of output
# tokens" was measured. The count was on file and the reasoning was not.
# Estimated at 79 KB per circle against 820 KB today, from circle
# 2026-08-21_1139's 20,341 thinking tokens at four characters each.
RECORD_THINKING = SET.setting_value_read("record_thinking", True)

# THE PROVIDER — stage 2 of the socket (R382). Everything vendor-shaped moved
# to providers.py; this module keeps the POLICY: Self's retry ladder, the one
# Meter, the capture hook, and the two entry points every caller already uses.
#
# RESOLVED ONCE, AT IMPORT, FROM THE SETTING. providers.stream_provider_active() REFUSES a
# name the registry does not know rather than defaulting to one — a provider
# is a closed set in code (R383) and the settings register validates against
# that same registry before storing, so a name arriving here that is unknown
# is a defect and must say so.
#
# The names below stay bound in THIS module on purpose: circle.py and the
# suites import KEY_MISSING_HELP, explain_api_failure and key_source_note from
# here, and stage 2 is a refactor — moving an implementation, not a caller.
PROVIDER_IMPL = _providers.stream_provider_active(PROVIDER)
KEY_MISSING_HELP = PROVIDER_IMPL.missing_key_help
KEY_MISSING_BRIEF = PROVIDER_IMPL.missing_key_brief     # the same four things, for a run that
                                                        # goes on without a key (R546)

# `--dry-run` SELECTS A PROVIDER — stage 3 (R382). It is not in REGISTRY and
# a person cannot name it: the mode chooses it, and R383's closed set is about
# what CONFIGURATION may select. Every dry-run circle in the suites exercises
# the seam this way, which is what keeps the contract honest before a second
# real vendor exists.
DRY_IMPL = _providers.DryRunProvider()


def _impl(dry: bool):
    """Which provider answers this call. The `dry` flag every caller already
    passes now RESOLVES a provider instead of branching the transport."""
    return DRY_IMPL if dry else PROVIDER_IMPL


# THIS PROVIDER'S OWN KNOBS — stage 4 (R382). Read ONCE at import, like every
# other setting, so a change takes effect at the next circle: that is what
# `applies = next_circle` means, and a tuning change alters both the wire and
# the ceilings, so it must not move under a transcript in flight.
TUNING = SET.setting_tuning_read(PROVIDER_IMPL)


def stream_ceiling_read(base: int, dry: bool = False) -> int:
    """An output ceiling, scaled by whatever the provider's tuning does to it.

    ONE DIAL MOVES BOTH — the operator, 2026-08-28: *"Turning up thinking must
    also turn up tokens, and vice versa."* Thinking bills against max_tokens
    on this model, so raising effort without raising the ceiling reproduces
    the truncation this project has already fixed three times. The provider
    owns the mapping because the coupling is a fact about a model, not about
    circling; at the default effort the scale is exactly 1.0, so nothing moves
    until someone turns the dial."""
    scale = _impl(dry).ceiling_scale(TUNING)
    return base if scale == 1.0 else max(1, int(round(base * scale)))

# The short_term record's four canonical sections — the dry provider returns
# them as its canned short_term, and circle_close.py's short_term_collect() checks
# a real response carries all four.
#
# IMPORTED, NOT COPIED (2026-08-28). This module and record_model each wrote the
# same four strings out, and the two were read by different consumers —
# circle.py took this copy, circle_close_verify.py took that one. record_model owns a
# short_term's SHAPE (its own comment beside RECONSTRUCTED_MARK says so, in
# the words "the literal lives here, in the module that owns a short_term's
# shape, so the writer and the reader cannot drift apart"), so it owns these.
#
# THE SELF-CONTAINMENT LINE IN THIS MODULE'S HEADER IS NOW WRONG, and is
# corrected there: this file needs one more thing of the coordinator than it
# used to. That is the price of one home, and it is the right way round.
from record_model import SHORT_TERM_SECTIONS                     # noqa: E402,F401


# ------------------------------------------------------------------ usage meter
_METER_LOCK = threading.Lock()


# RATES RIDE THE MODEL — ruled 2026-08-28 ("RATES SHOULD RIDE THE MODEL,
# yes"). KEYED ON (model, speed), not on the model alone: fast mode prices the
# SAME model differently ($5/$25 standard against $10/$50 on Opus 5), so a
# model id is not a sufficient key and never was. Speed is not a setting and
# is not exposed — the operator ruled it stays inside the provider — but the
# accounting has to be able to tell the two apart the day one is used.
#
# A model with no row here is priced at the default row and SAYS SO in the
# report. Guessing silently at a price is worse than an obviously-flagged
# estimate, and this project has already had four documents call the operator
# pessimistic off one misread number.
_STANDARD = "standard"
_FAST = "fast"


def _row(rate_in: float, rate_out: float) -> tuple:
    """One model's four numbers from its two published ones.

    THE CACHE TIERS RIDE THE INPUT RATE and always have: a 1-hour cache write
    is 2x base, a cache read 0.1x. Deriving them is not a shortcut — it
    removes the way three of the four numbers could drift out of agreement
    with the first, which is precisely the defect the flat table had at
    seven-fold scale. The two published numbers are the only ones a price
    list actually quotes, so they are the only ones written here."""
    return (rate_in, rate_in * 2, rate_in / 10, rate_out)


# THE TABLE IS THE POINT OF B74(2) — built 2026-08-30. Until then there was
# ONE row, filled from four FLAT settings, so every model that was not
# claude-sonnet-5 was silently priced at claude-sonnet-5's numbers. The report
# would have been wrong by 2.5x on Opus 5 and 5x on Fable, with nothing on
# screen to say so.
#
# KEYED ON (model, speed), which is why the flat table could never have been
# stretched: fast mode prices the SAME model differently — Opus 5 is $5/$25
# standard and $10/$50 fast — so a model id is not a sufficient key and never
# was. Speed is not a setting and is not exposed; the operator ruled it stays
# inside the provider. The accounting still has to tell the two apart the day
# one is used.
#
# Rates verified against Anthropic's published list 2026-08-30, and
# RE-VERIFIED 2026-09-01 (audit-register.md #27) — every row here still
# matches platform.claude.com/docs/en/about-claude/pricing exactly.
# Sonnet 5's row does NOT rise to 3.00/6.00/0.30/15.00 on 2026-09-01 as
# this comment used to warn: Anthropic made the $2/$10 introductory rate
# permanent on 2026-08-10/11 and cancelled that rise. `[[model]]` below
# still exists for whenever a REAL price change does land — a price
# change is a TOML edit, not a Python edit.
_BUILTIN_RATES: dict[tuple, tuple] = {
    ("claude-fable-5", _STANDARD): _row(10.00, 50.00),
    ("claude-opus-5", _STANDARD): _row(5.00, 25.00),
    ("claude-opus-5", _FAST): _row(10.00, 50.00),
    ("claude-opus-4-8", _STANDARD): _row(5.00, 25.00),
    ("claude-opus-4-8", _FAST): _row(10.00, 50.00),
    ("claude-sonnet-5", _STANDARD): _row(2.00, 10.00),
    ("claude-sonnet-4-6", _STANDARD): _row(3.00, 15.00),
    ("claude-haiku-4-5", _STANDARD): _row(1.00, 5.00),
}

# A MODEL WITH NO ROW ANYWHERE is priced here and SAYS SO in the report. This
# is what the four flat settings became: not one model's price pretending to
# be every model's, but the acknowledged fallback for a model nobody has
# priced yet. Guessing silently at a price is worse than an obviously-flagged
# estimate — this project has already had four documents call the operator
# pessimistic off one misread number.
DEFAULT_RATES = (RATE_IN, RATE_CACHE_WRITE_1H, RATE_CACHE_READ, RATE_OUT)


def stream_model_rates_read() -> dict:
    """The built-in table with `self/settings.toml`'s `[[model]]` rows laid
    over it. Read fresh so a corrected price takes effect at once, the same
    immediacy the four rate settings were declared with — these price a
    report, they do not spend anything."""
    table = dict(_BUILTIN_RATES)
    table.update(SET.setting_model_rate_rows_read())
    return table


def stream_rates_read(model: str, speed: str = _STANDARD) -> tuple:
    return stream_model_rates_read().get((model, speed), DEFAULT_RATES)


class _Bucket:
    """One (provider, model, speed)'s own tally. Nothing is summed across
    models until it has been priced at its OWN rates."""

    __slots__ = ("calls", "t_in", "t_out", "t_cw", "t_cr")

    def __init__(self) -> None:
        self.calls = self.t_in = self.t_out = self.t_cw = self.t_cr = 0


class Meter:
    """USAGE PER (provider, model, speed), 2026-08-28 — the operator:
    "provider/model costs should be independently tracked and inspectable".

    It was ONE accumulator against ONE rate set, which is correct only while
    there is one model. The moment the circle and the inter-circle work run on
    different models — which is the axis ruled the same day — a single tally
    prices one model's tokens at the other's rates and reports a number that
    is simply wrong, with nothing to reveal it.

    The aggregate attributes are kept as properties so every existing reader
    goes on working; what changes is that `cost()` prices each bucket at its
    own row rather than the whole tally at one."""

    def __init__(self) -> None:
        self.by: dict[tuple, _Bucket] = {}

    def add(self, u, *, provider: str = "", model: str = "",
            speed: str = _STANDARD) -> None:
        # The blind round calls every part concurrently; `+=` is a
        # read-modify-write and is not atomic under threads.
        with _METER_LOCK:
            self._add(u, provider or PROVIDER, model or MODEL, speed)

    def reset(self) -> None:
        """Empty the tally. ONE PROCESS IS NO LONGER ONE CIRCLE — ruled by
        the operator 2026-08-30, *"support multiple circles in one app
        context ... assume the ticker will be running permanently"* — and
        the usage report
        circle.py prints at every close is a PER-CIRCLE report. Left
        un-reset, a window's second circle would be priced with its first
        one's tokens still in the buckets — a wrong number with nothing on
        screen to reveal it, because a cumulative total looks exactly like a
        large one. `CircleEngine.start()` is the caller: it is the thing that
        runs `main()` more than once in a process, so it is the thing that
        owes the reset."""
        with _METER_LOCK:
            self.by.clear()

    def _add(self, u, provider: str, model: str, speed: str) -> None:
        b = self.by.setdefault((provider, model, speed), _Bucket())
        b.calls += 1
        b.t_in += getattr(u, "input_tokens", 0) or 0
        b.t_out += getattr(u, "output_tokens", 0) or 0
        b.t_cw += getattr(u, "cache_creation_input_tokens", 0) or 0
        b.t_cr += getattr(u, "cache_read_input_tokens", 0) or 0

    def _total(self, field: str) -> int:
        return sum(getattr(b, field) for b in self.by.values())

    calls = property(lambda self: self._total("calls"))
    t_in = property(lambda self: self._total("t_in"))
    t_out = property(lambda self: self._total("t_out"))
    t_cw = property(lambda self: self._total("t_cw"))
    t_cr = property(lambda self: self._total("t_cr"))

    def rows(self) -> list[dict]:
        """One record per bucket, priced at its own rates, with the rates it
        was priced AT. The rates travel with the row so a later price change
        cannot silently reprice history — the 2026-09-01 rise is exactly the
        event that would otherwise do it."""
        out = []
        # ONE read of the table for the whole report — stream_model_rates_read() merges
        # the register's rows over the built-ins on every call, and a report
        # must price every row against the same table it flags them against
        table = stream_model_rates_read()
        for (prov, model, speed), b in sorted(self.by.items()):
            r_in, r_cw, r_cr, r_out = table.get((model, speed), DEFAULT_RATES)
            out.append({
                "provider": prov, "model": model, "speed": speed,
                "known_rates": (model, speed) in table,
                "calls": b.calls, "input_tokens": b.t_in,
                "cache_creation_input_tokens": b.t_cw,
                "cache_read_input_tokens": b.t_cr, "output_tokens": b.t_out,
                "rates": {"in": r_in, "cache_write": r_cw,
                          "cache_read": r_cr, "out": r_out},
                "cost": (b.t_in * r_in + b.t_cw * r_cw
                         + b.t_cr * r_cr + b.t_out * r_out) / 1_000_000,
            })
        return out

    def cost(self) -> float:
        return sum(r["cost"] for r in self.rows())

    def no_cache_cost(self) -> float:
        """What the same tokens would have cost with no caching at all —
        every cached token billed as uncached input, per bucket's own rate."""
        total = 0.0
        for (_p, model, speed), b in self.by.items():
            r_in, _cw, _cr, r_out = stream_rates_read(model, speed)
            total += ((b.t_in + b.t_cw + b.t_cr) * r_in
                      + b.t_out * r_out) / 1_000_000
        return total

    def report(self) -> str:
        rows = self.rows()
        hit = self.t_cr / max(1, self.t_cr + self.t_cw)
        ttl = PROVIDER_IMPL.cache_ttl(TUNING, CACHE_TTL)   # the operator's, when set
        head = (f"\n--- usage: {self.calls} calls across {len(rows)} "
                f"model(s), TTL {ttl} ---\n")
        body = ""
        # THE BREAKDOWN IS THE POINT, not a total: a total cannot be checked
        # against anything, and with two models it cannot even be right.
        for r in rows:
            flag = "" if r["known_rates"] else "   RATES UNKNOWN — priced at the default row"
            body += (
                f"  {r['provider']} / {r['model']}"
                f"{'' if r['speed'] == _STANDARD else ' / ' + r['speed']}"
                f"   {r['calls']} call(s){flag}\n"
                f"    uncached input : {r['input_tokens']:>9,}\n"
                f"    cache writes   : {r['cache_creation_input_tokens']:>9,}\n"
                f"    cache reads    : {r['cache_read_input_tokens']:>9,}\n"
                f"    output         : {r['output_tokens']:>9,}\n"
                f"    cost           : ${r['cost']:.4f}\n")
        return (
            head + body +
            f"  cache hit rate : {hit:.0%}\n"
            f"  est. cost      : ${self.cost():.4f}   "
            f"(no caching: ${self.no_cache_cost():.4f})\n"
            f"  rates verified 2026-07-26; they rise on 2026-09-01."
        )

    def snapshot(self) -> dict:
        """The durable record's payload — see circle.circle_spend_report_write()."""
        return {"calls": self.calls, "cost": self.cost(),
                "no_cache_cost": self.no_cache_cost(), "by_model": self.rows()}


METER = Meter()


# ------------------------------------------------------------------ API
def stream_call(client, part: str, blocks: list[dict], msgs: list[dict],
         max_tokens: int, dry: bool, kind: str = "statement"):
    """`kind` is "statement" or "short_term" — WHICH REQUEST THIS IS, said
    outright by the caller.

    IT USED TO BE INFERRED FROM max_tokens, AND THE INFERENCE HAD GONE
    STALE. The dry-run branch below read `max_tokens > 1000` as "this is
    the short_term request"; circle_rounds.MAX_TOKENS was under that when it was
    written and is 2500 today, so EVERY dry-run STATEMENT came back as the
    four short_term section headings and the statement branch was dead
    code. Measured 2026-08-20: `grep "dry run statement from"` matches no
    transcript this project has ever written. Every sandbox and lab circle
    had its parts speaking `## What I said / (dry run ...)` into the room,
    and nothing failed, because no suite asserts what a dry statement says.

    A number that means one thing until another number moves is not a
    test. The caller knows which request it is making; it says so.
    """
    # THE REQUEST AS ONE DICT, so the thing that is sent and the thing that
    # is recorded are the same object (R277, 2026-08-21): `**req` below is
    # exactly the keyword form it replaced.
    impl = _impl(dry)
    req = impl.request(MODEL, stream_ceiling_read(max_tokens, dry), blocks, msgs)
    # TRANSLATED, NEVER SPLICED — the provider turns our word (`effort`) into
    # its own wire path (`output_config.effort`). At the default the mapping
    # returns {} and the request is byte-identical to what it was before
    # stage 4, which is what makes shipping this a no-op until the dial moves.
    req.update(impl.wire_tuning(TUNING))
    # Exercise the full path offline: a canned statement, so the scheduler,
    # transcript writer, limit enforcement and short_term writer all run.
    # Recorded too, marked dry_run — what WOULD have been sent.
    #
    # ASKED OF THE PROVIDER since stage 3: the fixture is ours (our four
    # headings, our part tags) but "can you answer without a network" is the
    # provider's, and making it one is what gives the interface a second
    # implementation to be honest against.
    offline_text = impl.canned(kind, PART_TAGS[part], SHORT_TERM_SECTIONS)
    if offline_text is not None:
        reply = RD.Reply.canned(offline_text)
        _record_turn(part, kind, req, reply.record, dry_run=True)
        return reply
    # SELF'S LADDER COVERS THIS CALL TOO, since 2026-08-20
    # (R264). It did not, and that is
    # the whole of the crash that ruling was written for: a LIVE /close
    # died on one APIConnectionError with four of seven short_terms
    # written. with_backoff was wired into preflight_api and prewarm
    # only -- the two calls made BEFORE a circle exists, when a failure
    # costs a retry -- while every statement and every short_term, the
    # calls made once there IS a record to lose, went bare.
    #
    # _retry_free(client) COMES WITH IT, and is not optional. The SDK's own
    # max_retries=2 was the only retry behaviour here; leaving it on
    # underneath the ladder would turn a ruled 3 attempts into 9 and a
    # ruled 20 seconds of waiting into something nobody chose -- exactly
    # what that helper's docstring already says about the other two
    # sites.
    #
    # Both names are defined BELOW in this module. Python resolves them
    # at call time, not at import, so the reading order stands: the
    # transport first, the ladder it uses after.
    #
    # The label is what with_backoff prints while waiting, so it names
    # the part AND which of its two requests is being retried.
    try:
        resp = stream_backoff_wrap(
            f"{PART_TAGS[part]} {kind}",
            lambda: PROVIDER_IMPL.send(_retry_free(client), req),
        )
    except Exception as e:
        # The request is on record even when it failed — with what raised,
        # and no response. Then the caller sees exactly what it saw before.
        _record_turn(part, kind, req, None, error=f"{type(e).__name__}: {e}")
        raise
    # ONE BURST, RETURNED WHOLE (2026-09-02): the Reply the disassembler
    # makes is what the Meter reads, what the capture records, and what the
    # caller gets — circle_rounds.py and circle.py test `reply.truncated` rather
    # than the vendor's own word, which this used to return as a bare tuple.
    reply = RD.message_burst(PROVIDER_IMPL, resp, record_thinking=RECORD_THINKING)
    METER.add(reply.usage, model=MODEL)
    _record_turn(part, kind, req, reply.record)
    return reply


# ------------------------------------------------- the other model call
# EVERY MODEL CALL THAT IS NOT A PART'S TURN, 2026-08-28 (stage 1 of the
# provider socket). stream_call() above is the CIRCLE's call: it takes a part, its
# four cached blocks and the rendered transcript. Everything else this
# project asks a model — dreaming, synthesis, the mid_term distillate, the
# coalesce grouping, a dream fold, a transcript backfill — has one shape,
# and until today each of the five had its OWN copy of it.
#
# WHAT THOSE FIVE COPIES COST. Measured 2026-08-28: not one of
# inter_circle, mid_term, coalesce, dream_history or circle_audit called
# with_backoff, METER.add or _record_turn. So:
#
#   NO LADDER   a transient 529 during dreaming failed the whole run.
#               inter_circle stages all-or-nothing, so a blip the ladder
#               would have absorbed in 15 seconds cost a re-run of seven
#               parallel dreaming calls. The ladder is Self's, and it was
#               covering one of six paths.
#   NO METER    a circle's own report priced the circle and nothing after
#               it. mid_term re-implemented its own t_in/t_out arithmetic
#               instead — three cost accountings, one of them per-module.
#   NO RECORD   nothing could be captured even in principle, because there
#               was no single place the request passed through.
#
# The fix is one function, not five better copies of one. It is also where
# the provider seam lands in stage 2: this signature and stream_call()'s are the
# whole surface a provider has to satisfy.
def stream_client_build():
    """THE ONE PLACE A CLIENT IS CONSTRUCTED — the provider's business since
    stage 2. Kept as a name here because five call sites reach it, and stage
    2 moves an implementation, not a caller."""
    return PROVIDER_IMPL.client()


def _retry_free(client):
    """The client with the VENDOR's own retries off, so Self's ladder is the
    only retry behaviour. Tolerant of a fake with no such control — the
    suites inject them, and a fake has nothing to disable."""
    return PROVIDER_IMPL.retry_free(client)


def stream_call_once(system, user: str, max_tokens: int, *, kind: str,
              client=None, record: bool = False, part: str | None = None):
    """One non-circle model call. Returns the Reply, burst
    (LLM_response_disassembler.Reply) — it returned (text, usage,
    stop_reason) until 2026-09-02, and every caller re-shaped that tuple.

    `system` is a plain string for four of the five callers and a LIST OF
    BLOCKS for circle_audit's backfill, which assembles a real part prompt.
    Both are passed through untouched — the shape is the caller's business
    and the transport has never inspected it.

    `client` INJECTED means a test's fake: it is used as given, its own
    `model` attribute wins, and nothing here builds or configures one. That
    is the contract coalesce._call and dream_history._call already had, kept
    verbatim so their suites go on reaching no network.

    `record` IS THE CAPTURE HOOK, and it is OFF unless a caller asks. R277
    enumerated the pre-warm, the statements and the short_terms; R412
    (2026-08-30) and R413 (2026-08-31) admitted the /close calls that WRITE
    THE RECORD — dreaming, synthesis, the mid_term refresh, the coalesce pass
    — and the failure diagnostic stays off, because it writes nothing. `part`
    is who the call is made for: a part's directory name for dreaming and
    the refresh, None for the two circle-wide calls, whose file the log then
    names by kind. Recorded only while a turn log is open — a live circle's,
    or the one circle_process() opens for a hand re-run — so a rehearsal, a
    dry run and `mid_term --refresh` by hand record nothing, as before."""
    # A TEST'S FAKE NAMES ITSELF; A REAL CLIENT DOES NOT. Both suites that
    # inject one set `self.model = "fake"` explicitly, and the SDK's client
    # carries no `model` attribute at all — so `or MODEL` resolves a real
    # injected client (mid_term passes one, reused across parts) to the
    # project's own model instead of the string "fake", which is what the
    # two hand-rolled copies of this would have done.
    if client is None:
        client = stream_client_build()
    model = getattr(client, "model", None) or MODEL
    req = PROVIDER_IMPL.request(model, stream_ceiling_read(max_tokens), system,
                                [{"role": "user", "content": user}])
    req.update(PROVIDER_IMPL.wire_tuning(TUNING))
    try:
        resp = stream_backoff_wrap(
            kind, lambda: PROVIDER_IMPL.send(_retry_free(client), req))
    except Exception as e:                                     # noqa: BLE001
        if record:
            _record_turn(part, kind, req, None,
                         error=f"{type(e).__name__}: {e}")
        raise
    reply = RD.message_burst(PROVIDER_IMPL, resp, record_thinking=RECORD_THINKING)
    if reply.usage is not None:
        # ONE meter, so a close can price itself — and the MODEL is PASSED,
        # not assumed, because this is the path the inter-circle work takes
        # and that is exactly where a second model would first appear.
        METER.add(reply.usage, model=model)
    if record:
        _record_turn(part, kind, req, reply.record)
    return reply


# ------------------------------------------------------------------ per-turn record
# R277, 2026-08-21: every request that carries a part's system prompt is
# written to the circle's capture directory as it is sent — the pre-warm,
# each statement and its retry, the short_term and its retry. R412/R413
# (2026-08-30/31) added the /close calls that write the record — dreaming,
# synthesis, mid_term, coalesce — through call_once(record=True). The
# transport is the one place all of them pass through, so the hook lives
# here; the file format and the directory are prompt_capture's
# (open_turn_log / record_turn), and when no log is open record_turn()
# writes nothing.
#
# NEVER COSTS A REQUEST. A recorder failure is reported through seam.fail
# — loud, and it makes the run non-zero — and the statement goes on: the
# emitted program is the thing no other record holds, but a circle is the
# thing the record is FOR.
# THE RESPONSE DICT ITSELF — id, model, stop_reason, the RAW text, the usage,
# and the thinking when RECORD_THINKING is on — is built by
# LLM_response_disassembler.message_burst() as `Reply.record`, 2026-09-02; it was
# _response_record()/_usage_dict() here, a second reader of the wire beside
# the provider's own.
def _record_turn(part: "str | None", kind: str, req: dict,
                 response: "dict | None", dry_run: bool = False,
                 error: "str | None" = None) -> None:
    try:
        import prompt_capture as PC
        PC.record_turn(part, kind, req, response, dry_run=dry_run, error=error)
    except Exception as e:                                   # noqa: BLE001
        seam.fail(f"per-turn capture FAILED for {part or kind} {kind}: "
                  f"{type(e).__name__}: {e}")


# ------------------------------------------------------------------ API preflight
# RULED 2026-08-09, after a rotated key raised 401 inside stream_prewarm() and left
# circles/circle_2026-08-09_1507.md behind — a header, a topic, a working-set
# entry, and nothing else:
#
#   "Test the API as early as practical and error out gracefully on fail; do
#    not write circle records of any sort until after the check passes."
#
# EARLY means BEFORE the working-set and topic prompts, not merely before the
# first write. The stub was the cheap half of that failure; the expensive half
# was re-pasting a 500-character topic into a second process. The check runs
# the moment the client exists, so a bad key costs a retry and nothing else.
#
# THE LADDER IS SELF'S: three attempts, 5 seconds after the first failure and
# 15 after the second, TRANSIENT ONLY. A fatal error does not wait — a 401 is
# not going to become a 200, and making someone watch 20 seconds of it is the
# opposite of erroring out gracefully.
BACKOFF = (5, 15)


# Status codes that no amount of waiting will fix. Everything else that
# reaches _transient() — 429, any 5xx including 529 overloaded, and a
# connection or timeout error with no status at all — is worth another try.
# Written as a PREDICATE over status codes rather than a tuple of exception
# classes so a status the SDK has not yet named a class for is still routed.
def _transient(e: Exception) -> bool:
    return PROVIDER_IMPL.transient(e)


def stream_backoff_wrap(what: str, fn):
    """Run fn(), retrying transient failures on Self's ladder. Re-raises the
    fatal ones at once and the last transient one after the third attempt."""
    for i, wait in enumerate((*BACKOFF, None)):
        try:
            return fn()
        except Exception as e:                                   # noqa: BLE001
            if wait is None or not _transient(e):
                raise
            seam.emit("command",
                      f"  {what}: {type(e).__name__} — retrying in {wait}s "
                      f"(attempt {i + 2} of {len(BACKOFF) + 1})")
            time.sleep(wait)


def stream_key_source_note() -> "str | None":
    """A warning about WHICH credential is in use, or None — the provider's,
    since only it knows what its credential is called and where else it may
    be written. Printed at OPEN whenever it would otherwise be a silent trap:
    the 401 of 2026-08-09 was a stale environment variable shadowing a
    perfectly valid .env, and nothing in the run would have mentioned it."""
    return PROVIDER_IMPL.key_note()


def stream_key_present_read() -> bool:
    """Would the configured provider find its credential? Asked WITHOUT building a client, so
    a dry run and the window's demo — which never build one — can still say what a live circle
    will need (R546). The configured provider's, never the dry run's: that
    one has no key to be missing."""
    return PROVIDER_IMPL.key_present()


# KEY_MISSING_HELP is bound near the top of this module, from
# PROVIDER_IMPL.missing_key_help. The text is one vendor's console, start to
# finish — the account page, the menu names, the spending-limit screen — so it
# lives with the provider and every word of it changes when the provider does.


def stream_failure_explain(e: Exception) -> str:
    """The message a human gets instead of a traceback — the provider's, since
    it classifies that vendor's own exception hierarchy and status codes.
    MODEL is passed in because the 404 branch names it and the provider does
    not own the model choice."""
    return PROVIDER_IMPL.explain(e, MODEL)


def stream_api_preflight(client, dry: bool) -> str | None:
    """One real messages.create against MODEL before anything is written.
    Returns None on success, a printable explanation on failure.

    A REAL CALL, not models.list(). The point is to exercise the endpoint and
    the model id the circle will actually use — a key or a proxy can pass a
    listing and fail a message. The ceiling is the provider's own
    `preflight_max_tokens` — 1 on Anthropic, which costs about nothing, and a
    vendor fact rather than a policy of ours."""
    impl = _impl(dry)
    if impl.offline:
        return None                  # nothing to check; nothing to reach
    req = impl.request(MODEL, impl.preflight_max_tokens,
                       None, [{"role": "user", "content": "ping"}])
    req.pop("system", None)              # no system prompt on a bare ping
    try:
        r = stream_backoff_wrap("api check",
                         lambda: PROVIDER_IMPL.send(_retry_free(client), req))
    except Exception as e:                                       # noqa: BLE001
        return stream_failure_explain(e)
    METER.add(RD.message_burst(PROVIDER_IMPL, r, record_thinking=False).usage,
              model=MODEL)
    return None


def stream_prewarm(client, parts: list[str], sysblocks: dict, dry: bool) -> None:
    """max_tokens=0 pre-warm: writes each part's cached prefix before the circle
    opens, so the first real turn is a cache read. Bills zero output tokens.
    Sequential on purpose — a cache entry is not available to a concurrent
    request until the first response has begun.

    Each call goes through with_backoff, and main() catches what it raises.
    This is the site of the 2026-08-09 traceback — seven un-retried, un-caught
    API calls, reached AFTER the transcript was on disk."""
    impl = _impl(dry)
    if impl.offline:
        if CS.dev_mode:
            seam.emit("command", "  (dry run: pre-warm skipped)")
        return
    # A SERVICE WITH NO PROMPT CACHE HAS NOTHING TO WARM, and says so rather
    # than paying for seven calls that buy nothing. The Meter's cache columns
    # then read zero, which is correct rather than broken. The dry provider
    # takes the branch above instead, so its message stays the one people are
    # used to seeing.
    if not impl.supports_cache:
        if CS.dev_mode:
            seam.emit("command",
                      f"  (pre-warm skipped: {impl.name} has no prompt "
                      f"cache to warm)")
        return
    for p in parts:
        req = impl.request(MODEL, impl.prewarm_max_tokens,
                           sysblocks[p],
                           [{"role": "user", "content": "warmup"}])
        try:
            r = stream_backoff_wrap(f"pre-warm {p}",
                             lambda req=req: impl.send(
                                 _retry_free(client), req))
        except Exception as e:
            _record_turn(p, "prewarm", req, None,
                         error=f"{type(e).__name__}: {e}")
            raise
        reply = RD.message_burst(impl, r, record_thinking=RECORD_THINKING)
        METER.add(reply.usage, model=MODEL)
        _record_turn(p, "prewarm", req, reply.record)
        if CS.dev_mode:
            seam.emit("command",
                      f"  warmed {p:<12} "
                      f"{getattr(reply.usage, 'cache_creation_input_tokens', 0) or 0:>7,} "
                      f"tok written")
