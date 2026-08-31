#!/usr/bin/env python3
"""
llm_client.py — the Messages-API transport: the model id and its
rates, the usage meter, the one call() wrapper, Self's retry ladder,
the key diagnostics, the preflight, and the cache pre-warm. Phase 2
stage 1 of the coordinator partitioning (2026-08-16); until then all
of it lived in circle.py. Verbatim move — bodies and comments
unchanged, except console output goes through `seam.emit` by attribute
access (the seam contract in seam.py).

TRANSPORT ONLY, deliberately: ask_statement() stays in circle.py (for
rounds, stage 7) — it is round-logic wearing an API call, and the
phase-2 review's correction of the original plan's "llm_client is
self-contained" claim was exactly this line. What it needs of the
coordinator is small and named: paths.PART_TAGS, seam, settings, providers
(the vendor seam, R382), and ifs_model for the four short_term headings it
must not keep a second copy of.

METER is a module singleton MUTATED IN PLACE (add()) and never
reassigned — circle.py's `from llm_client import METER` aliases the
same object, the same contract seam.FAILURES documents.
"""

from __future__ import annotations

import threading
import time

import seam
import settings as SET
import providers as _providers
from paths import PART_TAGS
# `os` and `ROOT` left with the provider at stage 2 — the only readers here
# were the credential diagnostics, and a credential's name and its file are
# the vendor's, not the transport's.

# EVERY LITERAL BELOW IS STILL THE DOCUMENTED DEFAULT. settings.value()
# returns it unless self/settings.toml overrides that key, and an absent
# register — a fresh clone, a worktree, a shipped bundle — means every one of
# these stands exactly as written. See coordinator/settings.py.
MODEL = SET.value("model", "claude-sonnet-5")   # parts run on sonnet (cost tiering)
PROVIDER = SET.value("provider", "Anthropic")   # who MODEL's requests go to — named
                                        # in the initialization dialogs' privacy
                                        # statement
CACHE_TTL = "1h"                        # circles have pauses longer than 5m

# Verified 2026-07-26 from platform.claude.com/docs — Claude Sonnet 5,
# USD per MTok. NOTE: these rise on 2026-09-01 to 3.00 / 6.00 / 0.30 / 15.00 —
# which is what made them settable: until 2026-08-28 the only way to record
# that rise was to edit this file.
RATE_IN = SET.value("rate_in", 2.00)
RATE_CACHE_WRITE_1H = SET.value("rate_cache_write_1h", 4.00)   # 2x base
RATE_CACHE_READ = SET.value("rate_cache_read", 0.20)           # 0.1x base
RATE_OUT = SET.value("rate_out", 10.00)

# THE SHORT AUXILIARY CALL'S CEILING — one home, 2026-08-28. coalesce and
# inter_circle each held a bare 4000, and I called that a coincidence when
# check_one_home flagged it. It is not: coalesce's own comment cites
# DERIVE_MAX_TOKENS's lesson (R354), so the two were sized by the SAME
# reasoning and landed on the same number for the same reason — thinking bills
# against the cap, so even a call whose visible output is a few lines needs
# generous headroom.
#
# THE OUTPUTS GENUINELY DIFFER — "a few lines" for a grouping pass, "a few
# paragraphs" for a diagnostic — and neither is what sets this number. The
# thinking is. If one of them ever needs its own ceiling it declares one, and
# that is then a visible decision rather than a silent divergence.
AUX_MAX_TOKENS = SET.value("auxiliary_max_tokens", 4000)

# WHETHER THE CAPTURE KEEPS WHAT THE MODEL THOUGHT — R386,
# *"keep them if a new boolean setting record_thinking = true"*, ruling on the
# finding that thinking arrives on every statement and was being dropped twice:
# by providers.read() for the transcript and by _response_record() below for the
# archive. THE TRANSCRIPT DROP STAYS. Thinking never enters the room, and that
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
RECORD_THINKING = SET.value("record_thinking", True)

# THE PROVIDER — stage 2 of the socket (R382). Everything vendor-shaped moved
# to providers.py; this module keeps the POLICY: Self's retry ladder, the one
# Meter, the capture hook, and the two entry points every caller already uses.
#
# RESOLVED ONCE, AT IMPORT, FROM THE SETTING. providers.active() REFUSES a
# name the registry does not know rather than defaulting to one — a provider
# is a closed set in code (R383) and the settings register validates against
# that same registry before storing, so a name arriving here that is unknown
# is a defect and must say so.
#
# The names below stay bound in THIS module on purpose: circle.py and the
# suites import KEY_MISSING_HELP, explain_api_failure and key_source_note from
# here, and stage 2 is a refactor — moving an implementation, not a caller.
PROVIDER_IMPL = _providers.active(PROVIDER)
KEY_MISSING_HELP = PROVIDER_IMPL.missing_key_help

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
TUNING = SET.tuning(PROVIDER_IMPL)


def ceiling(base: int, dry: bool = False) -> int:
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
# them as its canned short_term, and circle.py's collect_short_terms() checks
# a real response carries all four.
#
# IMPORTED, NOT COPIED (2026-08-28). This module and ifs_model each wrote the
# same four strings out, and the two were read by different consumers —
# circle.py took this copy, circle_close.py took that one. ifs_model owns a
# short_term's SHAPE (its own comment beside RECONSTRUCTED_MARK says so, in
# the words "the literal lives here, in the module that owns a short_term's
# shape, so the writer and the reader cannot drift apart"), so it owns these.
#
# THE SELF-CONTAINMENT LINE IN THIS MODULE'S HEADER IS NOW WRONG, and is
# corrected there: this file needs one more thing of the coordinator than it
# used to. That is the price of one home, and it is the right way round.
from ifs_model import SHORT_TERM_SECTIONS                     # noqa: E402,F401


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
# Rates verified against Anthropic's published list 2026-08-30. They rise on
# 2026-09-01 — which is what `[[model]]` below exists for: a price change is a
# TOML edit, not a Python edit.
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


def model_rates() -> dict:
    """The built-in table with `self/settings.toml`'s `[[model]]` rows laid
    over it. Read fresh so a corrected price takes effect at once, the same
    immediacy the four rate settings were declared with — these price a
    report, they do not spend anything."""
    table = dict(_BUILTIN_RATES)
    table.update(SET.model_rate_rows())
    return table


def rates_for(model: str, speed: str = _STANDARD) -> tuple:
    return model_rates().get((model, speed), DEFAULT_RATES)


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
        # ONE read of the table for the whole report — model_rates() merges
        # the register's rows over the built-ins on every call, and a report
        # must price every row against the same table it flags them against
        table = model_rates()
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
            r_in, _cw, _cr, r_out = rates_for(model, speed)
            total += ((b.t_in + b.t_cw + b.t_cr) * r_in
                      + b.t_out * r_out) / 1_000_000
        return total

    def report(self) -> str:
        rows = self.rows()
        hit = self.t_cr / max(1, self.t_cr + self.t_cw)
        head = (f"\n--- usage: {self.calls} calls across {len(rows)} "
                f"model(s), TTL {CACHE_TTL} ---\n")
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
        """The durable record's payload — see circle.write_spend_report()."""
        return {"calls": self.calls, "cost": self.cost(),
                "no_cache_cost": self.no_cache_cost(), "by_model": self.rows()}


METER = Meter()


# ------------------------------------------------------------------ API
def call(client, part: str, blocks: list[dict], msgs: list[dict],
         max_tokens: int, dry: bool, kind: str = "statement"):
    """`kind` is "statement" or "short_term" — WHICH REQUEST THIS IS, said
    outright by the caller.

    IT USED TO BE INFERRED FROM max_tokens, AND THE INFERENCE HAD GONE
    STALE. The dry-run branch below read `max_tokens > 1000` as "this is
    the short_term request"; rounds.MAX_TOKENS was under that when it was
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
    req = impl.request(MODEL, ceiling(max_tokens, dry), blocks, msgs)
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
        _record_turn(part, kind, req,
                     {"text": offline_text, "stop_reason": "end_turn",
                      "usage": None}, dry_run=True)
        return offline_text, "end_turn"
    # SELF'S LADDER COVERS THIS CALL TOO, since 2026-08-20
    # (R264). It did not, and that is
    # the whole of the crash that ruling was written for: a LIVE /close
    # died on one APIConnectionError with four of seven short_terms
    # written. with_backoff was wired into preflight_api and prewarm
    # only -- the two calls made BEFORE a circle exists, when a failure
    # costs a retry -- while every statement and every short_term, the
    # calls made once there IS a record to lose, went bare.
    #
    # _no_sdk_retries COMES WITH IT, and is not optional. The SDK's own
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
        resp = with_backoff(
            f"{PART_TAGS[part]} {kind}",
            lambda: PROVIDER_IMPL.send(_retry_free(client), req),
        )
    except Exception as e:
        # The request is on record even when it failed — with what raised,
        # and no response. Then the caller sees exactly what it saw before.
        _record_turn(part, kind, req, None, error=f"{type(e).__name__}: {e}")
        raise
    turn = PROVIDER_IMPL.read(resp)
    METER.add(turn.usage, model=MODEL)
    _record_turn(part, kind, req, _response_record(resp))
    # THE VENDOR'S OWN WORD IS RETURNED, not the normalised one: rounds.py and
    # circle.py both test `stop == "max_tokens"`, and stage 2 moves an
    # implementation rather than a caller. `turn.stop` carries the normalised
    # value for whatever reads it next.
    return turn.text, turn.raw_stop


# ------------------------------------------------- the other model call
# EVERY MODEL CALL THAT IS NOT A PART'S TURN, 2026-08-28 (stage 1 of the
# provider socket). call() above is the CIRCLE's call: it takes a part, its
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
# the provider seam lands in stage 2: this signature and call()'s are the
# whole surface a provider has to satisfy.
def build_client():
    """THE ONE PLACE A CLIENT IS CONSTRUCTED — the provider's business since
    stage 2. Kept as a name here because five call sites reach it, and stage
    2 moves an implementation, not a caller."""
    return PROVIDER_IMPL.client()


def _retry_free(client):
    """The client with the VENDOR's own retries off, so Self's ladder is the
    only retry behaviour. Tolerant of a fake with no such control — the
    suites inject them, and a fake has nothing to disable."""
    return PROVIDER_IMPL.retry_free(client)


def call_once(system, user: str, max_tokens: int, *, kind: str,
              client=None, record: bool = False, part: str | None = None):
    """One non-circle model call. Returns (text, usage, stop_reason).

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
    or the one process_circle() opens for a hand re-run — so a rehearsal, a
    dry run and `mid_term --refresh` by hand record nothing, as before."""
    # A TEST'S FAKE NAMES ITSELF; A REAL CLIENT DOES NOT. Both suites that
    # inject one set `self.model = "fake"` explicitly, and the SDK's client
    # carries no `model` attribute at all — so `or MODEL` resolves a real
    # injected client (mid_term passes one, reused across parts) to the
    # project's own model instead of the string "fake", which is what the
    # two hand-rolled copies of this would have done.
    if client is None:
        client = build_client()
    model = getattr(client, "model", None) or MODEL
    req = PROVIDER_IMPL.request(model, ceiling(max_tokens), system,
                                [{"role": "user", "content": user}])
    req.update(PROVIDER_IMPL.wire_tuning(TUNING))
    try:
        resp = with_backoff(
            kind, lambda: PROVIDER_IMPL.send(_retry_free(client), req))
    except Exception as e:                                     # noqa: BLE001
        if record:
            _record_turn(part, kind, req, None,
                         error=f"{type(e).__name__}: {e}")
        raise
    turn = PROVIDER_IMPL.read(resp)
    text, usage = turn.text, turn.usage
    if usage is not None:
        # ONE meter, so a close can price itself — and the MODEL is PASSED,
        # not assumed, because this is the path the inter-circle work takes
        # and that is exactly where a second model would first appear.
        METER.add(usage, model=model)
    stop = turn.raw_stop
    if record:
        _record_turn(part, kind, req, _response_record(resp))
    return text, usage, stop


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
def _usage_dict(u) -> "dict | None":
    if u is None:
        return None
    try:
        return u.model_dump()                           # the SDK's pydantic object
    except AttributeError:
        return {k: getattr(u, k) for k in
                ("input_tokens", "output_tokens",
                 "cache_creation_input_tokens", "cache_read_input_tokens")
                if hasattr(u, k)}


def _response_record(resp) -> dict:
    """The reply as a plain dict: the RAW text — before rounds.ask_statement
    strips a sign-off, a [To: ...] or a bracket, and before "[pass]" becomes
    silence — the stop reason, the usage, and the service's own id/model.

    AND THE THINKING, when RECORD_THINKING is on. The provider supplies it,
    because where reasoning sits in a reply is its business and not this
    module's; `{}` back means either the setting is off or the service has no
    thinking to give. THE KEY'S PRESENCE IS THE RECORD OF THE SETTING: when
    recording is on the key is written even if the model thought nothing, so
    an empty string means "asked, none came" and an absent key means "not
    asked". A reader a year from now cannot otherwise tell those apart, and
    the first captures will straddle the change."""
    out = {
        "id": getattr(resp, "id", None),
        "model": getattr(resp, "model", None),
        "stop_reason": getattr(resp, "stop_reason", None),
        "text": "".join(b.text for b in getattr(resp, "content", [])
                        if getattr(b, "type", None) == "text"),
        "usage": _usage_dict(getattr(resp, "usage", None)),
    }
    if RECORD_THINKING:
        out.update(PROVIDER_IMPL.thinking_record(resp))
    return out


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
# RULED 2026-08-09, after a rotated key raised 401 inside prewarm() and left
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


def with_backoff(what: str, fn):
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


def _no_sdk_retries(client):
    """The vendor's own retries off — the provider's job since stage 2.
    Kept as a name because the suite asserts this seam by patching it."""
    return PROVIDER_IMPL.retry_free(client)


def _env_file_key() -> "str | None":
    """The key literally written in .env — the provider's, since only it
    knows what its credential is called."""
    return PROVIDER_IMPL._env_file_key()


def _mask(k: str) -> str:
    """Enough to tell two keys apart, not enough to be one."""
    return PROVIDER_IMPL._mask(k)


def key_source_note() -> "str | None":
    """A warning about WHICH credential is in use, or None — the provider's,
    since only it knows what its credential is called and where else it may
    be written. Printed at OPEN whenever it would otherwise be a silent trap:
    the 401 of 2026-08-09 was a stale environment variable shadowing a
    perfectly valid .env, and nothing in the run would have mentioned it."""
    return PROVIDER_IMPL.key_note()


# KEY_MISSING_HELP is bound near the top of this module, from
# PROVIDER_IMPL.missing_key_help. The text is one vendor's console, start to
# finish — the account page, the menu names, the spending-limit screen — so it
# lives with the provider and every word of it changes when the provider does.


def explain_api_failure(e: Exception) -> str:
    """The message a human gets instead of a traceback — the provider's, since
    it classifies that vendor's own exception hierarchy and status codes.
    MODEL is passed in because the 404 branch names it and the provider does
    not own the model choice."""
    return PROVIDER_IMPL.explain(e, MODEL)


def preflight_api(client, dry: bool) -> str | None:
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
        r = with_backoff("api check",
                         lambda: PROVIDER_IMPL.send(_retry_free(client), req))
    except Exception as e:                                       # noqa: BLE001
        return explain_api_failure(e)
    METER.add(PROVIDER_IMPL.read(r).usage, model=MODEL)
    return None


def prewarm(client, parts: list[str], sysblocks: dict, dry: bool) -> None:
    """max_tokens=0 pre-warm: writes each part's cached prefix before the circle
    opens, so the first real turn is a cache read. Bills zero output tokens.
    Sequential on purpose — a cache entry is not available to a concurrent
    request until the first response has begun.

    Each call goes through with_backoff, and main() catches what it raises.
    This is the site of the 2026-08-09 traceback — seven un-retried, un-caught
    API calls, reached AFTER the transcript was on disk."""
    impl = _impl(dry)
    if impl.offline:
        seam.emit("command", "  (dry run: pre-warm skipped)")
        return
    # A SERVICE WITH NO PROMPT CACHE HAS NOTHING TO WARM, and says so rather
    # than paying for seven calls that buy nothing. The Meter's cache columns
    # then read zero, which is correct rather than broken. The dry provider
    # takes the branch above instead, so its message stays the one people are
    # used to seeing.
    if not impl.supports_cache:
        seam.emit("command",
                  f"  (pre-warm skipped: {impl.name} has no prompt "
                  f"cache to warm)")
        return
    for p in parts:
        req = impl.request(MODEL, impl.prewarm_max_tokens,
                           sysblocks[p],
                           [{"role": "user", "content": "warmup"}])
        try:
            r = with_backoff(f"pre-warm {p}",
                             lambda req=req: impl.send(
                                 _retry_free(client), req))
        except Exception as e:
            _record_turn(p, "prewarm", req, None,
                         error=f"{type(e).__name__}: {e}")
            raise
        usage = impl.read(r).usage
        METER.add(usage, model=MODEL)
        _record_turn(p, "prewarm", req, _response_record(r))
        seam.emit("command",
                  f"  warmed {p:<12} "
                  f"{getattr(usage, 'cache_creation_input_tokens', 0) or 0:>7,} "
                  f"tok written")
