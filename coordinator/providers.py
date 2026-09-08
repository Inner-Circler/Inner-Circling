#!/usr/bin/env python3
"""
providers.py — the socket the transport plugs a model service into.
Approved 2026-08-28 (R382); stage 2 of that plan.

WHAT IS ON EACH SIDE OF THE SEAM. `llm_client` keeps POLICY: Self's retry
ladder, the one Meter, the capture hook, and the two entry points every
caller already uses. A provider keeps the VENDOR: how a client is built, what
a request looks like on the wire, how a reply is read, which errors are worth
retrying, what a person is told when the key is refused, and what caching
means here at all. Nothing above the seam names `anthropic`.

WHY THE SPLIT FALLS THERE. The ladder is Self's — three attempts, +5s and
+15s — and it is a decision about how this project behaves, not about
Anthropic; a provider only answers "is this error worth another try?". The
Meter is likewise ours. The four-block prompt architecture stays in
prompt_build, because it is this project's design and no vendor's.

PROVIDERS ARE A CLOSED SET IN CODE — R383, 2026-08-28: *"Never, providers are
a closed set in code."* Configuration SELECTS among the entries in REGISTRY
below and can never introduce one, and NO PROVIDER MAY TAKE A NETWORK
ENDPOINT FROM CONFIGURATION. The reason is not the git-locality rule — that
governs remotes, and model traffic is disclosed and carved out by
initialization.toml's privacy statement — it is that the disclosure and the
destination must never be able to disagree. The statement is regenerated at
every circle open from the live provider, so closing the set is what keeps it
true by construction rather than by anyone checking it.

AND PROVIDERS ARE EXPECTED TO BE ADDED, as development changes with their own
rulings. That is why the contract below is written as questions a second
vendor would answer differently rather than as Anthropic's shape with
indirection over it — and why stage 3 makes the dry-run path a real second
implementation, so the interface is proven before a second vendor exists.
"""

from __future__ import annotations

import os

from record_paths import ROOT

# What a reply's stop reason MEANS, normalised. The vendor's own word is kept
# beside it on the Turn: callers test the normalised value, the record keeps
# what actually came back.
STOP_COMPLETE = "complete"
STOP_TRUNCATED = "truncated"     # ran out of room — the retry-worthy one
STOP_REFUSED = "refused"
STOP_OTHER = "other"


class Turn:
    """One reply, in the shape the transport reads."""

    __slots__ = ("text", "stop", "raw_stop", "usage", "raw_text")

    def __init__(self, text: str, stop: str, raw_stop: str, usage,
                 raw_text: "str | None" = None) -> None:
        self.text = text
        self.stop = stop
        self.raw_stop = raw_stop
        self.usage = usage
        # The text blocks joined and NOT stripped — what the capture has
        # always recorded (LLM_response_disassembler.message_burst). `text` above is
        # the room's form.
        self.raw_text = text if raw_text is None else raw_text


class Knob:
    """One setting a provider declares FOR ITSELF. Stage 4 of the socket
    (R382), and the operator's own idea with one modification.

    He proposed *"a simple opaque 'model_tuning' or such that could be sent
    in"*. The instinct is right — the shared interface must not grow a
    parameter every time one vendor adds a knob — but OPAQUE is the one
    property this tree cannot afford: turn_contract.toml declares the request
    body `closed = true`, and a blob spliced in verbatim would force that
    open to admit arbitrary keys, un-checking the single thing the contract
    checks.

    So a knob is DECLARED here, validated by setting_manager.setting_coerce() like every
    other setting, and TRANSLATED by the provider into its own wire shape.
    The core still never changes when a knob is added, which was the point;
    what it also gets is a gate."""

    __slots__ = ("key", "ask", "values", "default", "applies", "gate",
                 "data_type")

    def __init__(self, key: str, ask: str, values: tuple, default: str,
                 applies: str = "next_circle", gate: str = "ONE_OF",
                 data_type: str = "STRING") -> None:
        self.key = key
        self.ask = ask
        # `values` and `gate`, NOT `choices` — 2026-08-28. This carried its own
        # word and its own inline check, which made it the FOURTH validation
        # vocabulary in the tree a week after the third. It now declares what
        # every other gated field declares and is checked by the same
        # function, part_roster.part_context_value_verify().
        self.values = values
        self.default = default
        self.applies = applies
        self.gate = gate
        self.data_type = data_type

    def as_question(self) -> dict:
        """The declaration in the shape part_roster.part_context_value_verify() reads, so a
        provider's knob and a part's context question are held to one rule."""
        return {"key": self.key, "ask": self.ask, "data_type": self.data_type,
                "gate": self.gate, "values": list(self.values)}


class Provider:
    """The contract. Every method here is something a second vendor answers
    differently; anything both vendors would answer the same way belongs
    above the seam, not in here."""

    # WHAT THIS PROVIDER LETS A PERSON TUNE. Empty for a provider with no
    # knobs, which is the honest default — a vendor is not obliged to have
    # any, and the transport asks rather than assuming.
    TUNING: tuple = ()

    name = ""
    default_model = ""
    supports_cache = False
    supports_token_count = False
    # ANSWERS WITHOUT A NETWORK? False for every real service. True is what
    # makes the dry-run path a PROVIDER rather than an `if dry:` branch
    # threaded through the transport — see DryRunProvider.
    offline = False
    # A pre-warm asks for no output at all; a preflight asks for the least
    # that still exercises the endpoint. Both are vendor facts: a service
    # with no prompt cache has no pre-warm, and one that rejects a zero
    # ceiling needs a different number.
    prewarm_max_tokens = 0
    preflight_max_tokens = 1

    def client(self):
        raise NotImplementedError

    def retry_free(self, client):
        """The same client with the VENDOR's own retries off, so Self's
        ladder is the only retry behaviour. A client that has none returns
        unchanged."""
        return client

    def request(self, model: str, max_tokens: int, system, messages) -> dict:
        raise NotImplementedError

    def send(self, client, req: dict):
        raise NotImplementedError

    def read(self, resp) -> Turn:
        raise NotImplementedError

    def transient(self, e: Exception) -> bool:
        return False

    def explain(self, e: Exception, model: str) -> str:
        return f"{type(e).__name__}: {e}"

    def key_note(self) -> "str | None":
        """A warning about WHICH credential is in use, or None. Printed at
        open whenever it would otherwise be a silent trap."""
        return None

    missing_key_help = ""

    def cache_control(self, ttl: str) -> "dict | None":
        """The wire form of "this block is stable, cache it" — or None when
        the service has no such thing, in which case the caller sends no
        marker and the Meter's cache columns simply read zero."""
        return None

    def count_tokens(self, client, model: str, system, messages) -> "int | None":
        """The service's own count, or None when it cannot answer. A caller
        that gets None must SAY it is estimating; token_count.py already
        does."""
        return None

    def cache_ttl(self, tuning: dict, default: str) -> str:
        """The prompt-cache lifetime this provider should ask for — the
        operator's `cache_ttl` tuning when set, else `default`. A provider
        with no cache ignores it (its cache_control() returns None). Read by
        prompt_build.prompt_cache_control_read() since 2026-09-04
        (audit-register #7: the knob was accepted, stored and never read).
        block_counts_are_exact() sat here until the same day with no
        consumer and a docstring claiming token_count.py relied on it."""
        return tuning.get("cache_ttl") or default

    def thinking_record(self, resp) -> dict:
        """What the model THOUGHT, as keys to merge into the captured
        response record — or {} for a service with no such concept.

        SHAPED LIKE wire_tuning(): the caller merges what it gets and knows
        nothing about the shape. That is the point of putting it here at all.
        "A reply carries reasoning in a content block of type `thinking`,
        whose text is on `.thinking`" is a fact about ONE vendor's wire, and
        llm_client is the module stages 2-5 emptied of exactly those.

        NEVER CALLED UNLESS RECORDING IS ON — llm_client.RECORD_THINKING
        gates it, so a provider that answers here still costs nothing when
        the operator has the setting off."""
        return {}

    def canned(self, kind: str, label: str, sections) -> "str | None":
        """The reply this provider gives WITHOUT calling anything, or None
        when it has none — which is every real service. Only an `offline`
        provider answers here."""
        return None

    def wire_tuning(self, tuning: dict) -> dict:
        """The declared knobs, TRANSLATED into whatever this service puts on
        the wire — never spliced in verbatim. Returns keys to merge into the
        request body; {} when nothing is set or nothing is supported."""
        return {}

    def ceiling_scale(self, tuning: dict) -> float:
        """How far this provider's tuning moves an output ceiling.

        THE OPERATOR'S OWN OBSERVATION, 2026-08-28: *"Turning up thinking must
        also turn up tokens, and vice versa, perhaps a single 'effort' dial
        set externally adjusts both in the adapter?"* Right, and it belongs
        HERE rather than in circle policy, because "thinking is billed against
        max_tokens" is a fact about a model and not about IFS. One external
        dial; the provider moves both."""
        return 1.0


# ------------------------------------------------------------------ Anthropic
class AnthropicProvider(Provider):
    """Everything that was Anthropic-shaped in llm_client, moved whole. The
    comments come with it: each records a failure this project actually had,
    and they are load-bearing where they sit."""

    name = "Anthropic"
    default_model = "claude-sonnet-5"
    supports_cache = True
    supports_token_count = True

    # THE DIAL, AND WHAT IT MOVES. `effort` is generally available on
    # claude-sonnet-5 at all five levels and DEFAULTS TO `high` — so this
    # project has been running at its second-highest setting since the day it
    # was written, without anyone choosing it. Measured on circle
    # 2026-08-21_1139: thinking was 55% of output tokens but only about 6% of
    # the circle's $3.13, because 80% of the bill is writing the cached prefix
    # once per part. Raising it is nearly free in money.
    #
    # WHAT IT IS NOT FREE IN IS CEILING. Thinking bills against max_tokens,
    # and at `high` the statements already press on it: the longest turn in
    # that circle reached 2147 of 2500 (86%) and 7 of 90 requests stopped at
    # max_tokens. So the dial moves the ceiling with it — the operator's
    # point, made structural.
    #
    # THE MULTIPLIERS ARE NOT MEASURED. There is data at exactly one effort
    # level, so every number but 1.0 is an estimate — the same status
    # remember_manager.py marks four of its own numbers with, and the reason the
    # replay comparison is worth running. `high` is 1.0 so that shipping this
    # changes nothing at all until someone turns the dial.
    EFFORT = {
        "low": ("low", 0.6),
        "medium": ("medium", 0.8),
        "high": ("high", 1.0),        # today, bit for bit
        "xhigh": ("xhigh", 1.6),
        "max": ("max", 2.4),
    }

    TUNING = (
        Knob("effort", "How hard the model thinks before it answers",
             tuple(EFFORT), "high"),
        Knob("cache_ttl", "How long a warmed prompt stays warm",
             ("5m", "1h"), "1h"),
    )

    def wire_tuning(self, tuning: dict) -> dict:
        """TRANSLATED, never spliced. `effort` becomes Anthropic's
        `output_config.effort`, which is where that parameter lives — inside
        output_config, not top-level — and the key a person sets is our own
        word rather than the vendor's path."""
        eff = tuning.get("effort")
        if not eff or eff not in self.EFFORT:
            return {}
        wire, _scale = self.EFFORT[eff]
        if wire == "high":
            # The default. Sending it changes nothing and would put a key in
            # every captured request for no reason.
            return {}
        return {"output_config": {"effort": wire}}

    def ceiling_scale(self, tuning: dict) -> float:
        eff = tuning.get("effort")
        return self.EFFORT.get(eff, ("", 1.0))[1] if eff else 1.0

    # cache_ttl(): the base class's, unchanged — `5m` or `1h`, straight into
    # cache_control()'s ttl. (Its only caller arrived 2026-09-04; until then
    # the knob was stored and never read — audit-register #7.)

    def client(self):
        """THE ONE PLACE A CLIENT IS CONSTRUCTED. Five call sites resolved the
        key themselves before stage 1, two of them by hand-parsing `.env` for
        a line starting `ANTHROPIC_API_KEY` — which reads a key the shell has
        already overridden, and misses every other form of the file.

        `os.environ` wins over `.env`, deliberately and as everywhere else in
        this project (the 2026-08-09 rotated-key incident); load_dotenv only
        fills a gap, and its absence is not an error."""
        from anthropic import Anthropic
        if not os.environ.get("ANTHROPIC_API_KEY"):
            try:
                from dotenv import load_dotenv
                load_dotenv(ROOT / ".env")
            except ImportError:
                pass
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "set ANTHROPIC_API_KEY (env var or project .env)")
        return Anthropic()

    def retry_free(self, client):
        """The SDK defaults to max_retries=2 (measured, anthropic 0.109.2),
        which would turn a ruled 3-attempt ladder into as many as 9 requests
        and a ruled 20 seconds of waiting into something nobody chose.

        Tolerant of a client that is not the SDK's: the suites inject fakes
        with no `with_options`, and a fake has no vendor retries to disable."""
        return (client.with_options(max_retries=0)
                if hasattr(client, "with_options") else client)

    def request(self, model: str, max_tokens: int, system, messages) -> dict:
        """THE REQUEST AS ONE DICT, so the thing that is sent and the thing
        that is recorded are the same object (R277, 2026-08-21).

        `system` is passed through untouched — a plain string for most
        callers, a LIST OF BLOCKS for the circle and for circle_audit's
        backfill. Its shape is the caller's business and the transport has
        never inspected it."""
        return {"model": model, "max_tokens": max_tokens,
                "system": system, "messages": messages}

    def send(self, client, req: dict):
        try:
            return client.messages.create(**req)
        except ValueError as e:
            # THE SDK REFUSES a non-streaming create whose effective
            # max_tokens implies more than ten minutes on the wire
            # (_calculate_nonstreaming_timeout; the string matched below is
            # the SDK's own). First hit 2026-08-30: the derive ceiling at
            # 16,000, scaled up by a raised effort, crossed the line and the
            # lab close's refresh step crashed instead of deriving. The
            # refusal is pre-flight — no network call was made — so falling
            # back to the streaming accumulator re-sends nothing, and
            # get_final_message() returns the same Message shape create()
            # does, thinking blocks and usage included.
            if "Streaming is required" not in str(e):
                raise
            with client.messages.stream(**req) as s:
                return s.get_final_message()

    # ANTHROPIC'S OWN VOCABULARY, DECLARED HERE — stage 5 (R382). These two
    # lists also sit in turn_contract.toml, which is the shape a captured turn
    # is held to; they were one vendor's words in two places with no link
    # between them, which is the drift this project records more often than
    # any other defect. test_providers.py asserts the contract's copies equal
    # these, so a second provider cannot quietly be checked against the
    # first's words.
    STOP_REASONS = ("end_turn", "max_tokens", "stop_sequence", "tool_use",
                    "refusal")
    USAGE_FIELDS = ("input_tokens", "output_tokens",
                    "cache_creation_input_tokens", "cache_read_input_tokens")

    STOP_MEANING = {
        "end_turn": STOP_COMPLETE,
        "max_tokens": STOP_TRUNCATED,
        "stop_sequence": STOP_COMPLETE,
        "tool_use": STOP_OTHER,
        "refusal": STOP_REFUSED,
    }

    def read(self, resp) -> Turn:
        raw_text = "".join(b.text for b in resp.content
                           if getattr(b, "type", "") == "text")
        raw = getattr(resp, "stop_reason", None) or ""
        return Turn(raw_text.strip(), self.STOP_MEANING.get(raw, STOP_OTHER),
                    raw, getattr(resp, "usage", None), raw_text=raw_text)

    def thinking_record(self, resp) -> dict:
        """RETURNED ON EVERY REPLY, and discarded here until 2026-08-29.

        claude-sonnet-5 THINKS ADAPTIVELY WITH NOTHING ASKING IT TO — a bare
        messages.create with no `thinking` parameter comes back with content
        blocks ['thinking', 'text'] (probed 2026-08-21). read() above takes
        the text and drops the rest, which is right for the transcript: the
        reasoning never enters the room. It was also what the CAPTURE did,
        and that was not a decision anyone took.

        WHAT IS BEING KEPT IS A SUMMARY, not the raw trace — this model
        family returns summarised thinking, so the record bounds what it can
        ever show and this comment is where that bound is written down.

        REDACTED BLOCKS ARE COUNTED, NOT DROPPED. A `redacted_thinking` block
        carries encrypted bytes this project can do nothing with, but a
        record that silently omitted them would claim to hold the thinking
        while holding only some of it. Counting costs one integer and keeps
        the claim true. The key is absent when the count is zero, so the
        common case adds nothing."""
        blocks = getattr(resp, "content", []) or []
        out = {"thinking": "".join(
            getattr(b, "thinking", "") or "" for b in blocks
            if getattr(b, "type", None) == "thinking")}
        n = sum(1 for b in blocks
                if getattr(b, "type", None) == "redacted_thinking")
        if n:
            out["thinking_redacted_blocks"] = n
        return out

    def transient(self, e: Exception) -> bool:
        """Status codes that waiting cannot fix are fatal; everything else —
        429, any 5xx including 529 overloaded, and a connection or timeout
        error with no status at all — is worth another try. Written as a
        PREDICATE over status codes rather than a tuple of exception classes,
        so a status the SDK has not yet named a class for is still routed."""
        import anthropic
        if isinstance(e, (anthropic.APIConnectionError,
                          anthropic.APITimeoutError)):
            return True
        if isinstance(e, anthropic.APIStatusError):
            return e.status_code == 429 or e.status_code >= 500
        return False

    def cache_control(self, ttl: str) -> dict:
        return {"type": "ephemeral", "ttl": ttl}

    def count_tokens(self, client, model: str, system, messages) -> "int | None":
        kw = {"model": model, "messages": messages}
        if system:
            kw["system"] = system
        return client.messages.count_tokens(**kw).input_tokens

    # ------------------------------------------------------ credentials
    def _env_file_key(self) -> "str | None":
        """The key literally written in .env — READ, never loaded. This is a
        comparison, not a fallback, so it must not disturb the environment."""
        p = ROOT / ".env"
        if not p.is_file():
            return None
        try:
            for line in p.read_text(encoding="utf-8",
                                    errors="replace").splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY"):
                    v = line.partition("=")[2].strip().strip('"').strip("'")
                    return v or None
        except OSError:
            return None
        return None

    @staticmethod
    def _mask(k: str) -> str:
        """Enough to tell two keys apart, not enough to be one. 12 leading
        characters is `sk-ant-api03` and no secret at all; the last 4 are what
        actually distinguishes a rotated key from the one it replaced."""
        return f"{k[:12]}...{k[-4:]}" if len(k) > 24 else "(too short to mask)"

    def key_note(self) -> "str | None":
        """os.environ WINS over .env — load_dotenv is only reached when the
        variable is unset. So a rotated key written into .env while a stale one
        sits in the environment changes NOTHING, and that is exactly what
        produced the 401 of 2026-08-09: the .env key was valid the whole time.
        Proven by removing the environment variable.

        Reported at OPEN whenever both exist and differ, not only on failure —
        a stale-but-valid variable pointing at another account is the same trap
        one notch quieter, and nothing else in the run would ever mention it."""
        env = os.environ.get("ANTHROPIC_API_KEY")
        dot = self._env_file_key()
        if env and dot and env != dot:
            return ("ANTHROPIC_API_KEY is set in the ENVIRONMENT and differs "
                    "from .env.\n"
                    f"     environment  {self._mask(env)}   <- IN USE\n"
                    f"     .env         {self._mask(dot)}   <- IGNORED\n"
                    "     os.environ wins; .env is read only when the variable "
                    "is unset.")
        return None

    def explain(self, e: Exception, model: str) -> str:
        """The message a human gets instead of a traceback. Names the key
        source on an auth failure, because 'API key is invalid' does not say
        WHICH key.

        CLASSIFIES, since 2026-08-23 (R330: *"A failed API check needs to
        diagnose the issue"*). The 401/403 branch is the 2026-08-09 one, kept
        whole; the rest name the class and what to do. ORDER MATTERS in the
        SDK's hierarchy: APITimeoutError subclasses APIConnectionError, and
        every status error subclasses APIStatusError, so the specific test
        comes first. A class nothing below recognises falls through to the
        type and message, as before — and says so, so the person has something
        to search for."""
        import anthropic
        out = [f"{type(e).__name__}: {e}"]
        auth = isinstance(e, (anthropic.AuthenticationError,
                              anthropic.PermissionDeniedError)) or (
            isinstance(e, anthropic.APIStatusError)
            and e.status_code in (401, 403))
        if auth:
            out.append("Anthropic did not accept the key.")
            env = os.environ.get("ANTHROPIC_API_KEY")
            dot = self._env_file_key()
            out.append(
                f"key in use: {'environment variable' if env else '.env'}"
                + (f"  {self._mask(env or dot or '')}" if (env or dot) else ""))
            if env and dot and env != dot:
                out.append("A DIFFERENT key is in .env and is being IGNORED. "
                           "os.environ wins.")
                out.append("Clear the variable, or update it — editing .env "
                           "alone will not help.")
            elif env:
                out.append("Nothing in .env is being consulted: the variable "
                           "is set, so load_dotenv is never reached.")
            out.append("A revoked or mistyped key: make a new one at "
                       "https://console.anthropic.com (Settings -> API Keys) "
                       "and replace the line in .env.")
            return "\n     ".join(out)
        status = getattr(e, "status_code", None)
        text = str(e).lower()
        if isinstance(e, anthropic.APITimeoutError):
            out.append("Anthropic did not answer in time — the network, not "
                       "the key. Open again.")
        elif isinstance(e, anthropic.APIConnectionError):
            out.append(
                "Could not reach api.anthropic.com — no network, a firewall, "
                "a proxy, or ANTHROPIC_BASE_URL pointing somewhere else"
                + (f" (it is set: {os.environ['ANTHROPIC_BASE_URL']})"
                   if os.environ.get("ANTHROPIC_BASE_URL") else "") + ".")
        elif isinstance(e, anthropic.NotFoundError) or status == 404:
            out.append(f"The model {model} is not available to this key — the "
                       "account may not have access yet, or the id has "
                       "changed. Check the console's model list.")
        elif isinstance(e, anthropic.RateLimitError) or status == 429:
            out.append("Anthropic is asking this key to slow down. Already "
                       "retried 3 times (+5s, +15s); wait a minute and open "
                       "again.")
        elif isinstance(e, anthropic.APIStatusError) and status in (503, 529):
            out.append("Anthropic is overloaded right now — not this "
                       "installation. Try again shortly.")
        elif isinstance(e, anthropic.BadRequestError) and (
                "credit" in text or "billing" in text or "balance" in text):
            out.append("The account has no credit. Settings -> Billing at "
                       "https://console.anthropic.com, add credit, open "
                       "again.")
        else:
            out.append("Not a failure this program recognises. If it repeats, "
                       "the line above is what to search for.")
        return "\n     ".join(out)

    # THE MISSING-KEY TEXT — R330, 2026-08-23: *"a missing API key needs to
    # provide key acquisition and install instructions"*, and the same day
    # *"add a clause KEY SECURITY and briefly describe risks and safety
    # precautions."* Until then circle.py printed one line and exited, which
    # tells a first-run user what to set and nothing about how. It lives with
    # the provider because every word of it is one vendor's console.
    missing_key_help = """\
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


# The stop vocabulary moved ONTO AnthropicProvider at stage 5 — it is that
# vendor's own words, and a module-level map would be shared with every
# provider that follows. See AnthropicProvider.STOP_MEANING.


# ------------------------------------------------------------------ dry run
class DryRunProvider(Provider):
    """THE SECOND IMPLEMENTATION, and the reason the interface above can be
    trusted. Stage 3 of the socket (R382).

    An interface with ONE implementation is the first vendor's shape with
    indirection laid over it, and nothing reveals that until a second arrives.
    This project already had a second in disguise: `--dry-run` fabricated
    replies inside an `if dry:` branch in the transport, complete with its own
    canned text, its own skipped pre-warm and its own skipped preflight. Those
    were provider behaviours wearing a flag.

    So it answers the same questions Anthropic does, differently: no client to
    build, no cache to warm, no token count to give, no error that is ever
    worth retrying, and — the one Anthropic cannot answer — a reply with no
    network at all. Every dry-run circle in the suites now exercises the seam,
    which is how the contract stays honest before a second vendor exists.

    IT IS NOT IN THE REGISTRY. A person cannot select it; `--dry-run` does,
    and the registry is what configuration may name (R383)."""

    name = "DryRun"
    default_model = "dry-run"
    supports_cache = False          # nothing to warm, and prewarm() says so
    supports_token_count = False    # token_count falls back and must SAY it
    offline = True

    def client(self):
        return None                 # there is nothing to build

    def retry_free(self, client):
        return client

    def request(self, model: str, max_tokens: int, system, messages) -> dict:
        """The same shape a real request takes, because the CAPTURE records
        what WOULD have been sent — `dry_run` marked, but the same body."""
        return {"model": model, "max_tokens": max_tokens,
                "system": system, "messages": messages}

    def send(self, client, req: dict):
        raise RuntimeError(
            "DryRunProvider never sends — the transport must ask canned() "
            "first, which it does whenever a provider is offline.")

    def transient(self, e: Exception) -> bool:
        return False                # nothing to wait for

    def canned(self, kind: str, label: str, sections) -> str:
        """The fixture, which is THIS PROJECT'S and not a vendor's — it names
        our four short_term headings and our part tags, so it is handed the
        pieces rather than importing a transport that imports us.

        THE KIND IS ASKED FOR, NOT INFERRED. It used to be guessed from
        `max_tokens > 1000`, and the guess went stale when circle_rounds.MAX_TOKENS
        passed that line: EVERY dry-run statement came back as the four
        short_term headings and the statement branch was dead code for weeks.
        Measured 2026-08-20 — no transcript this project has ever written
        matches "dry run statement from"."""
        if kind == "short_term":
            return "\n".join(f"{h}\n(dry run — no model was called.)"
                             for h in sections)
        return f"(dry run statement from {label}.)"


# ------------------------------------------------------------------ registry
# CLOSED, BY RULING (R383). Configuration selects a NAME from this mapping and
# can do nothing else — it cannot add an entry, and no entry reads an endpoint
# from configuration. Adding a provider is a code change with its own ruling,
# and is expected.
REGISTRY: dict = {AnthropicProvider.name: AnthropicProvider}


def stream_provider_active(name: str = ""):
    """The provider this installation talks to. `name` comes from the
    settings register, which validates it against this same registry before
    it is ever stored — so a name arriving here that REGISTRY does not know
    is a defect, and is refused rather than defaulted."""
    key = (name or AnthropicProvider.name).strip()
    if key not in REGISTRY:
        raise RuntimeError(
            f"no provider named {key!r} is built into this program "
            f"(have: {', '.join(sorted(REGISTRY))}). Providers are a closed "
            f"set in code — R383.")
    return REGISTRY[key]()
