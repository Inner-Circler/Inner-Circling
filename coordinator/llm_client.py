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
self-contained" claim was exactly this line. Everything HERE really is
self-contained: it needs paths.PART_TAGS, seam, and the key in the
environment, nothing else of the coordinator.

METER is a module singleton MUTATED IN PLACE (add()) and never
reassigned — circle.py's `from llm_client import METER` aliases the
same object, the same contract seam.FAILURES documents.
"""

from __future__ import annotations

import os
import threading
import time

import seam
from paths import ROOT, PART_TAGS

MODEL = "claude-sonnet-5"               # parts run on sonnet (cost tiering)
PROVIDER = "Anthropic"                  # who MODEL's requests go to — named in the
                                        # initialization dialogs' privacy statement
CACHE_TTL = "1h"                        # circles have pauses longer than 5m

# Verified 2026-07-26 from platform.claude.com/docs — Claude Sonnet 5,
# USD per MTok. NOTE: these rise on 2026-09-01 to 3.00 / 6.00 / 0.30 / 15.00.
RATE_IN = 2.00
RATE_CACHE_WRITE_1H = 4.00              # 2x base
RATE_CACHE_READ = 0.20                  # 0.1x base
RATE_OUT = 10.00

# The short_term record's four canonical sections — call()'s dry-run
# path returns them as the canned short_term, and circle.py's
# collect_short_terms() checks a real response carries all four.
# coordinator/circle_close.py parses the same headings on its own side.
SHORT_TERM_SECTIONS = (
    "## What I said",
    "## What I observed in others",
    "## Shifts toward other parts",
    "## Current emotional state",
)


# ------------------------------------------------------------------ usage meter
_METER_LOCK = threading.Lock()


class Meter:
    def __init__(self) -> None:
        self.calls = self.t_in = self.t_out = self.t_cw = self.t_cr = 0

    def add(self, u) -> None:
        # The blind round calls every part concurrently; `+=` is a
        # read-modify-write and is not atomic under threads.
        with _METER_LOCK:
            self._add(u)

    def _add(self, u) -> None:
        self.calls += 1
        self.t_in += getattr(u, "input_tokens", 0) or 0
        self.t_out += getattr(u, "output_tokens", 0) or 0
        self.t_cw += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.t_cr += getattr(u, "cache_read_input_tokens", 0) or 0

    def cost(self) -> float:
        return (
            self.t_in * RATE_IN
            + self.t_cw * RATE_CACHE_WRITE_1H
            + self.t_cr * RATE_CACHE_READ
            + self.t_out * RATE_OUT
        ) / 1_000_000

    def no_cache_cost(self) -> float:
        return (
            (self.t_in + self.t_cw + self.t_cr) * RATE_IN + self.t_out * RATE_OUT
        ) / 1_000_000

    def report(self) -> str:
        hit = self.t_cr / max(1, self.t_cr + self.t_cw)
        return (
            f"\n--- usage: {self.calls} calls, model {MODEL}, TTL {CACHE_TTL} ---\n"
            f"  uncached input : {self.t_in:>9,}\n"
            f"  cache writes   : {self.t_cw:>9,}   (billed 2.00x)\n"
            f"  cache reads    : {self.t_cr:>9,}   (billed 0.10x)   hit rate {hit:.0%}\n"
            f"  output         : {self.t_out:>9,}\n"
            f"  est. cost      : ${self.cost():.4f}   (no caching: ${self.no_cache_cost():.4f})\n"
            f"  rates verified 2026-07-26; they rise on 2026-09-01."
        )


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
    req = {"model": MODEL, "max_tokens": max_tokens, "system": blocks,
           "messages": msgs}
    if dry:
        # Exercise the full path offline: a canned statement, so the scheduler,
        # transcript writer, limit enforcement and short_term writer all run.
        # Recorded too, marked dry_run — what WOULD have been sent.
        if kind == "short_term":
            text = "\n".join(f"{h}\n(dry run — no model was called.)"
                             for h in SHORT_TERM_SECTIONS)
        else:
            text = f"(dry run statement from {PART_TAGS[part]}.)"
        _record_turn(part, kind, req, {"text": text, "stop_reason": "end_turn",
                                       "usage": None}, dry_run=True)
        return text, "end_turn"
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
            lambda: _no_sdk_retries(client).messages.create(**req),
        )
    except Exception as e:
        # The request is on record even when it failed — with what raised,
        # and no response. Then the caller sees exactly what it saw before.
        _record_turn(part, kind, req, None, error=f"{type(e).__name__}: {e}")
        raise
    METER.add(resp.usage)
    _record_turn(part, kind, req, _response_record(resp))
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text, resp.stop_reason


# ------------------------------------------------------------------ per-turn record
# R277, 2026-08-21: every request that carries a part's system prompt is
# written to the circle's capture directory as it is sent — the pre-warm,
# each statement and its retry, the short_term and its retry. The transport
# is the one place all of them pass through, so the hook lives here; the
# file format and the directory are prompt_capture's (open_turn_log /
# record_turn), and when no log is open record_turn() writes nothing.
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
    silence — the stop reason, the usage, and the service's own id/model."""
    return {
        "id": getattr(resp, "id", None),
        "model": getattr(resp, "model", None),
        "stop_reason": getattr(resp, "stop_reason", None),
        "text": "".join(b.text for b in getattr(resp, "content", [])
                        if getattr(b, "type", None) == "text"),
        "usage": _usage_dict(getattr(resp, "usage", None)),
    }


def _record_turn(part: str, kind: str, req: dict, response: "dict | None",
                 dry_run: bool = False, error: "str | None" = None) -> None:
    try:
        import prompt_capture as PC
        PC.record_turn(part, kind, req, response, dry_run=dry_run, error=error)
    except Exception as e:                                   # noqa: BLE001
        seam.fail(f"per-turn capture FAILED for {part} {kind}: "
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
    import anthropic
    if isinstance(e, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(e, anthropic.APIStatusError):
        return e.status_code == 429 or e.status_code >= 500
    return False


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
    """The ladder above must be the ONLY retry behaviour, or the ruling does
    not describe what happens. The SDK defaults to max_retries=2 (measured,
    anthropic 0.109.2), which would turn a ruled 3-attempt ladder into as many
    as 9 requests and a ruled 20 seconds of waiting into something nobody
    chose."""
    return client.with_options(max_retries=0)


def _env_file_key() -> str | None:
    """The key literally written in .env — READ, never loaded. This is a
    comparison, not a fallback, so it must not disturb the environment."""
    p = ROOT / ".env"
    if not p.is_file():
        return None
    try:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY"):
                v = line.partition("=")[2].strip().strip('"').strip("'")
                return v or None
    except OSError:
        return None
    return None


def _mask(k: str) -> str:
    """Enough to tell two keys apart, not enough to be one. 12 leading
    characters is `sk-ant-api03` and no secret at all; the last 4 are what
    actually distinguishes a rotated key from the one it replaced."""
    return f"{k[:12]}...{k[-4:]}" if len(k) > 24 else "(too short to mask)"


def key_source_note() -> str | None:
    """os.environ WINS over .env — load_dotenv is only reached when the
    variable is unset. So a rotated key written into .env while a stale one
    sits in the environment changes NOTHING, and that is exactly what produced
    the 401 of 2026-08-09: the .env key was valid the whole time. Proven by
    removing the environment variable.

    Reported at OPEN whenever both exist and differ, not only on failure — a
    stale-but-valid variable pointing at another account is the same trap one
    notch quieter, and nothing else in the run would ever mention it."""
    env = os.environ.get("ANTHROPIC_API_KEY")
    dot = _env_file_key()
    if env and dot and env != dot:
        return ("ANTHROPIC_API_KEY is set in the ENVIRONMENT and differs "
                "from .env.\n"
                f"     environment  {_mask(env)}   <- IN USE\n"
                f"     .env         {_mask(dot)}   <- IGNORED\n"
                "     os.environ wins; .env is read only when the variable is "
                "unset.")
    return None


# THE MISSING-KEY TEXT — R330, 2026-08-23: *"a missing API
# key needs to provide key acquisition and install instructions"*, and the same
# day *"add a clause KEY SECURITY and briefly describe risks and safety
# precautions."* Until then circle.py printed one line — `set ANTHROPIC_API_KEY
# (env var or project .env)` — and exited, which tells a first-run user what to
# set and nothing about how. Policy text, identical for every installation, so
# it lives here beside the check that prints it. docs/Initialization.md §2.1 is
# the design; the console's menu names below are from the 2026-08 console and
# are the part most likely to drift.
KEY_MISSING_HELP = """\
No API key was found, so no part can speak yet.

Inner Circling talks to the parts through Anthropic's API, which needs a key — a
string that starts "sk-ant-". The key is yours. It is used only to send each
part's request to Anthropic and never leaves this folder otherwise.

TO GET ONE
  1  Go to https://console.anthropic.com and sign in, or create an account.
  2  Add a small amount of credit (Settings -> Billing). A circle costs cents,
     not dollars.
  3  Settings -> API Keys -> Create Key. Name it anything ("inner circling").
     Copy it when it is shown — it is shown once.
TO INSTALL IT
  Put one line in a file named  .env  in this folder — create the file if it
  does not exist; it is plain text, never committed, never shared:
      ANTHROPIC_API_KEY=sk-ant-...the key you copied...
  Then open the circle again.
  (Setting the variable in your shell works too, but the file is remembered
  and the shell is not — and if BOTH are set, the shell wins and .env is
  ignored.)
KEY SECURITY
  The key spends your credit, and anyone who has it can spend it too.
    - Keep it in .env and nowhere else: never in a chat, an email, a
      screenshot or a shared document. This program prints it masked and
      never writes it anywhere but here.
    - .env is never committed and never leaves this folder. If you copy or
      back up the folder somewhere others can reach, check that .env did not
      travel with it.
    - If it is ever exposed, delete it in the console (Settings -> API Keys)
      and make a new one; the old one stops working at once. Paste the new
      one into .env.
    - Set a monthly spending limit in the console (Settings -> Limits), so a
      leaked key can cost no more than you chose."""


def explain_api_failure(e: Exception) -> str:
    """The message a human gets instead of a traceback. Names the key source
    on an auth failure, because 'API key is invalid' does not say WHICH key.

    CLASSIFIES, since 2026-08-23 (R330: *"A failed API check
    needs to diagnose the issue"*). The 401/403 branch is the 2026-08-09 one,
    kept whole; the rest name the class and what to do. ORDER MATTERS in the
    SDK's hierarchy: APITimeoutError subclasses APIConnectionError, and every
    status error subclasses APIStatusError, so the specific test comes first.
    A class nothing below recognises falls through to the type and message, as
    before — and says so, so the person has something to search for."""
    import anthropic
    out = [f"{type(e).__name__}: {e}"]
    auth = isinstance(e, (anthropic.AuthenticationError,
                          anthropic.PermissionDeniedError)) or (
        isinstance(e, anthropic.APIStatusError) and e.status_code in (401, 403))
    if auth:
        out.append("Anthropic did not accept the key.")
        env = os.environ.get("ANTHROPIC_API_KEY")
        dot = _env_file_key()
        out.append(f"key in use: {'environment variable' if env else '.env'}"
                   + (f"  {_mask(env or dot or '')}" if (env or dot) else ""))
        if env and dot and env != dot:
            out.append("A DIFFERENT key is in .env and is being IGNORED. "
                       "os.environ wins.")
            out.append("Clear the variable, or update it — editing .env alone "
                       "will not help.")
        elif env:
            out.append("Nothing in .env is being consulted: the variable is "
                       "set, so load_dotenv is never reached.")
        out.append("A revoked or mistyped key: make a new one at "
                   "https://console.anthropic.com (Settings -> API Keys) and "
                   "replace the line in .env.")
        return "\n     ".join(out)
    status = getattr(e, "status_code", None)
    text = str(e).lower()
    if isinstance(e, anthropic.APITimeoutError):
        out.append("Anthropic did not answer in time — the network, not the "
                   "key. Open again.")
    elif isinstance(e, anthropic.APIConnectionError):
        out.append("Could not reach api.anthropic.com — no network, a firewall, "
                   "a proxy, or ANTHROPIC_BASE_URL pointing somewhere else"
                   + (f" (it is set: {os.environ['ANTHROPIC_BASE_URL']})"
                      if os.environ.get("ANTHROPIC_BASE_URL") else "") + ".")
    elif isinstance(e, anthropic.NotFoundError) or status == 404:
        out.append(f"The model {MODEL} is not available to this key — the "
                   "account may not have access yet, or the id has changed. "
                   "Check the console's model list.")
    elif isinstance(e, anthropic.RateLimitError) or status == 429:
        out.append("Anthropic is asking this key to slow down. Already retried "
                   "3 times (+5s, +15s); wait a minute and open again.")
    elif isinstance(e, anthropic.APIStatusError) and status in (503, 529):
        out.append("Anthropic is overloaded right now — not this installation. "
                   "Try again shortly.")
    elif isinstance(e, anthropic.BadRequestError) and (
            "credit" in text or "billing" in text or "balance" in text):
        out.append("The account has no credit. Settings -> Billing at "
                   "https://console.anthropic.com, add credit, open again.")
    else:
        out.append("Not a failure this program recognises. If it repeats, the "
                   "line above is what to search for.")
    return "\n     ".join(out)


def preflight_api(client, dry: bool) -> str | None:
    """One real messages.create against MODEL before anything is written.
    Returns None on success, a printable explanation on failure.

    A REAL CALL, not models.list(). The point is to exercise the endpoint and
    the model id the circle will actually use — a key or a proxy can pass a
    listing and fail a message. max_tokens=1 makes it cost about nothing."""
    if dry:
        return None
    try:
        r = with_backoff("api check", lambda: _no_sdk_retries(client).messages.create(
            model=MODEL, max_tokens=1,
            messages=[{"role": "user", "content": "ping"}]))
    except Exception as e:                                       # noqa: BLE001
        return explain_api_failure(e)
    METER.add(r.usage)
    return None


def prewarm(client, parts: list[str], sysblocks: dict, dry: bool) -> None:
    """max_tokens=0 pre-warm: writes each part's cached prefix before the circle
    opens, so the first real turn is a cache read. Bills zero output tokens.
    Sequential on purpose — a cache entry is not available to a concurrent
    request until the first response has begun.

    Each call goes through with_backoff, and main() catches what it raises.
    This is the site of the 2026-08-09 traceback — seven un-retried, un-caught
    API calls, reached AFTER the transcript was on disk."""
    if dry:
        seam.emit("command", "  (dry run: pre-warm skipped)")
        return
    for p in parts:
        req = {"model": MODEL, "max_tokens": 0, "system": sysblocks[p],
               "messages": [{"role": "user", "content": "warmup"}]}
        try:
            r = with_backoff(f"pre-warm {p}",
                             lambda req=req: _no_sdk_retries(client)
                             .messages.create(**req))
        except Exception as e:
            _record_turn(p, "prewarm", req, None,
                         error=f"{type(e).__name__}: {e}")
            raise
        METER.add(r.usage)
        _record_turn(p, "prewarm", req, _response_record(r))
        seam.emit("command",
                  f"  warmed {p:<12} {r.usage.cache_creation_input_tokens:>7,} tok written")
