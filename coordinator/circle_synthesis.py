#!/usr/bin/env python3
"""
circle_synthesis.py — SYNTHESIS: the CIRCLE's one pass over the circle that just closed.

MOVED OUT OF inter_circle.py, 2026-09-03 (cohesion re-homing stage 11, NEXT.md B99; the
names are Q-D's). inter_circle.py keeps the DRIVER; part_dreaming.py is the per-part pass and
owns the one _call and the footprint line, which this module reads as PD. Every function below
is the verbatim body it had there; only the file moved.

    SYNTHESIS_PROMPT_V2   the pass's prompt — versioned code, never a payload
    SYNTH_MAX_TOKENS      its cap (settings-overridable)
    SYN_HEADERS, _INSIST  what comes back, and the ONE insistent re-ask a HISTORY over
                          CH.CAP earns (R192)
    circle_synthesise            the pass: SECTIONS, writes nothing — the driver stages them

RENAMED AT THE MOVE (R436, R442 — 2026-09-03), the class word first, the body
untouched: synthesise -> circle_synthesise. The _private names are unchanged.

Design: docs/INTER_CIRCLE_DESIGN_V2.md (SYNTHESIS); the OBSERVATION follows the dreaming
grammar (R358); SELF is refused when its heading set moves.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import remember_manager as RM                                          # noqa: E402
import circle_history_manager as CH                                    # noqa: E402
import self_observation_manager as SO                              # noqa: E402
import roster as R                                             # noqa: E402
import LLM_response_disassembler as RD                         # noqa: E402
import setting_manager as SET                                         # noqa: E402
import part_dreaming as PD                                     # noqa: E402  _call, _report_chars
from record_paths import ROOT                                         # noqa: E402

SYNTH_MAX_TOKENS = SET.setting_value_read("synth_max_tokens", 12000)   # was 8000: one
                                # circle-wide call across five
                                # sections — HISTORY alone is capped at CH.CAP
                                # (8000 chars) — needs more headroom than a
                                # single part's dreaming pass, and now also
                                # the room for the thinking above.


SYNTHESIS_PROMPT_V2 = """\
You are the circle's synthesis pass for the circle that just closed ({ot}).
{n} parts attended: {roster}.

Below, in order: the closed circle's full transcript; the most recent dreaming record
for each part that produced one, written moments ago by that part's own dreaming pass;
every proposal Self confirmed during this circle; the CURRENT self.md, the standing
account of Self this circle may or may not have moved; the PREVIOUS circle's HISTORY
entry, so what you write continues an account rather than restarting one; and — if one
exists — the most recent observation in your own chain, a note your synthesis pass left
for Self last time, including how charged it was, if you said so.

Your job is to find what is TRUE OF THE CIRCLE — not of any one part. A thing only one
part said, that no other part took up and Self did not confirm, is that part's own
material and belongs to that part alone. Leave it there.

Condense syntactically. Coalesce semantically. Where several parts said one thing in
different words, say it once, in words none of them used. Where they genuinely disagreed,
that disagreement IS the finding — record it as a live tension, not as a split you resolve
on their behalf.

Emit only what is ACTIONABLE: something that changes what a future circle does, attends
to, or holds as settled. Observation with no consequence is not actionable. Say nothing
rather than pad.

OUTPUT FORMAT, exactly. Seven section headers, each alone on its own line, at column 0,
spelled exactly as shown, in this order. EVERY header must be printed even when that
section is empty — print the header and nothing under it.

HISTORY
    One durable entry for the circle record: what this circle was, and what moved. Prose,
    a part's-eye view of the whole rather than a summary of turns. Under {history_cap}
    characters.

OBSERVATION
    Appended to Self's own observation log. What you noticed about the CIRCLE as a
    working body — its pace, what it avoided, where it went easily. Addressed to Self,
    about the room, never about Self. If a prior observation exists below, either
    continue it — a first line reading exactly "CONTINUES" followed by the observation —
    or let it stand and leave this section EMPTY; an observation you choose not to
    change is not a failure. A new thread simply starts as plain prose.

SALIENCE
    Required whenever OBSERVATION is not empty — your own sense of how charged the
    observation is, exactly one word: passing, notable, charged, or resolved. "passing"
    is ordinary; "notable" is worth a second look later; "charged" is live and
    unsettled; "resolved" is a charge that has actually settled. Print the header with
    nothing under it when OBSERVATION is empty.

RESOLUTION
    Only filled if this observation resolves a prior observation you tagged "charged" —
    a line naming what settled. Print the header with nothing under it otherwise.

SELF
    A REPLACEMENT for self.md, in full, only if this circle genuinely moved the standing
    account of Self given below. Reproduce its section headings exactly; carry forward
    every section this circle did not touch, unchanged and verbatim. If nothing moved,
    leave this section EMPTY — that is the ordinary case, and an unnecessary rewrite of a
    standing document is a loss, not an update.

BLOCK 2 CANDIDATE
    Cross-part, part-agnostic material for the NEXT circle's working surface: an open
    question the room did not close, a tension worth naming aloud, an unconfirmed proposal
    worth discussing. This is what the next room will WORK ON. Each item one short
    paragraph, opening with "- ". It is a topic, never an instruction.

BLOCK 1 CANDIDATE
    Only for something that has genuinely SETTLED and should become how the circle
    behaves from now on — a practice, in the same register as the practices already in
    the prompt. Self must ratify each one before it lands, so propose sparingly: an item
    here asserts "this is now identity", and most circles will have none. Each item one
    short paragraph, opening with "- ".

BLOCK 2 CANDIDATE items reach the next circle's room UNVETTED, as topics for it to
examine (R184). BLOCK 1 CANDIDATE items reach no part until Self has ratified each one.
"""


SYN_HEADERS = ("HISTORY", "OBSERVATION", "SALIENCE", "RESOLUTION", "SELF",
               "BLOCK 2 CANDIDATE", "BLOCK 1 CANDIDATE")

# Appended to the SYNTHESIS system prompt for the ONE re-ask a cap breach
# earns (R192). Names the ACTUAL overshoot rather than repeating the original
# instruction louder: the first ask already said "under {history_cap}", so
# saying it again unchanged is the same request, and the model has no way to
# know by how much it missed.
_INSIST = """

--- THIS IS A SECOND ASK. YOUR PREVIOUS ANSWER WAS REFUSED. ---

Your HISTORY section was {got:,} characters. The register refuses anything
over {cap:,} and it does not truncate — an over-length answer is DISCARDED
whole and the previous circle's entry stands instead, so the account of this
circle is simply lost.

Write HISTORY again, under {target:,} characters. Every other section stays as
you judged it. Do not pad the shortfall elsewhere; cut HISTORY itself — decide
what this circle was ABOUT and say that, rather than covering everything that
happened in it."""


# --------------------------------------------------------------- synthesis
def circle_synthesise(ot: str, transcript: str, payloads: list[dict],
               confirmed: list[dict], say=lambda _s: None) -> dict:
    dreams = []
    for p in payloads:
        if p.get("memory"):
            dreams.append(f"[{R.TAG_BY_DIR[p['part']]}] {p['memory']}")
    conf = [f"- {c['kind']} {c['id']}: {c['line']}" for c in confirmed]
    self_md = (ROOT / "self" / "self.md")
    self_now = self_md.read_text(encoding="utf-8") if self_md.is_file() else ""
    prior = CH.circle_history_latest_read()
    prior_obs = SO.self_observation_latest_read()          # R358: the chain the OBSERVATION
    user = [f"# Transcript of circle {ot}\n{transcript}",
            "# Each part's fresh dreaming record\n"
            + ("\n".join(dreams) if dreams else "(none produced one)"),
            "# Proposals Self confirmed this circle\n"
            + ("\n".join(conf) if conf else "(none)"),
            f"# The CURRENT self.md\n{self_now or '(absent)'}",
            "# The previous circle's HISTORY entry\n"
            + (f"{prior['id']} ({prior['circle']}): {prior['text']}"
               if prior else "(none — this is the first)"),
            "# The previous observation in your own chain\n"
            + ((f"{prior_obs['id']} ({prior_obs['circle']}"
                + (f", {prior_obs['salience']}"
                   if prior_obs.get("salience") else "")
                + f"): {prior_obs['text']}")
               if prior_obs else "(none — this is the first)")]
    # ASK FOR TARGET, REFUSE AT CAP (R192). The prompt names CH.TARGET
    # (7200); render_new() refuses at CH.CAP (8000). A model asked for
    # exactly its hard limit has no room to run slightly long without being
    # refused — and the whole run, seven DREAMING calls included, is lost to
    # a few dozen characters.
    system = SYNTHESIS_PROMPT_V2.format(
        ot=ot, n=len(R.DIR_NAMES), roster=", ".join(R.TAGS),
        history_cap=CH.TARGET)
    body = "\n\n".join(user)
    # RECORDED WITH NO PART (R412): the synthesis speaks for the circle, and
    # its turn file is named by kind — Per_turn_synthesis_<time>_<seq>.json.
    reply = PD._call(system, body, SYNTH_MAX_TOKENS, kind="synthesis",
                  record=True)
    text, usage, stop_reason = reply.text, reply.usage, reply.raw_stop
    PD._report_chars(say, "synthesis", {"system": system, "user": body,
                                     "reply": text, "blocks": user})
    sections, err = RD.message_sections_read(text, SYN_HEADERS)

    # ONE INSISTENT RE-ASK ON A CAP BREACH (R192: "ask the LLM again and
    # insist"). Only when the overshoot would actually be REFUSED — an answer
    # between TARGET and CAP is within the headroom the target exists to
    # provide, and re-billing it would waste a call to buy nothing.
    #
    # Bounded at ONE retry: a model that ignores an explicit character count
    # twice will not comply on a third, and R168's hand-back is the honest
    # outcome there rather than a loop that spends money to reach it slowly.
    if sections is not None:
        n_hist = RD.message_length_norm(sections["HISTORY"])
        if n_hist > CH.CAP:
            say(f"  HISTORY {n_hist:,} chars — over the {CH.CAP:,} cap; "
                f"re-asking once, insisting")
            insisted_system = system + _INSIST.format(
                got=n_hist, cap=CH.CAP, target=CH.TARGET)
            reply2 = PD._call(insisted_system, body, SYNTH_MAX_TOKENS,
                           kind="synthesis", record=True)
            PD._report_chars(say, "synthesis re-ask",
                         {"system": insisted_system, "user": body,
                          "reply": reply2.text, "blocks": user})
            usage = RD.message_usage_merge(usage, reply2.usage)
            s2, e2 = RD.message_sections_read(reply2.text, SYN_HEADERS)
            if s2 is None:
                say(f"  the re-ask did not parse ({e2}) — keeping the first "
                    f"answer, which the cap will refuse")
            else:
                n2 = RD.message_length_norm(s2["HISTORY"])
                say(f"  re-ask returned {n2:,} chars"
                    + ("" if n2 <= CH.CAP
                       else " — still over; truncating at the cap"))
                sections, err, text, stop_reason = (s2, e2, reply2.text,
                                                    reply2.raw_stop)

    if sections is None:
        return {"error": f"unparseable output: {err}", "raw": text,
                "usage": usage, "stop_reason": stop_reason,
                "output_tokens": RD.message_out_tokens_read(usage)}
    out = {"usage": usage, "suspect": [], "truncated": [], "sections": sections,
           "stop_reason": stop_reason, "output_tokens": RD.message_out_tokens_read(usage)}
    # A CAP CRUNCH IS TRUNCATED AND ALLOWED, 2026-08-21 (the operator's rule,
    # see part_dream). CH.circle_history_new_render() still REFUSES over CH.CAP — that is the
    # register's own guard and does not move — so the HISTORY it is handed
    # is already cut to the cap, whitespace-aware, on the same normalized
    # text render_new measures. Reported, never silent.
    n_hist = RD.message_length_norm(sections["HISTORY"])
    if n_hist > CH.CAP:
        norm = " ".join(sections["HISTORY"].split())
        cut = RD.message_truncate(norm, CH.CAP)
        sections = dict(sections, HISTORY=cut)
        out["sections"] = sections
        out["truncated"].append(
            f"HISTORY TRUNCATED at {len(cut):,} chars (was {n_hist:,}; cap "
            f"{CH.CAP:,}) — the insistent re-ask did not bring it under")
    # THE OBSERVATION FOLLOWS THE DREAMING MODEL (R358): CONTINUES chains
    # onto the prior observation, SALIENCE coerces rather than refuses, a
    # RESOLUTION also chains, and a bare CONTINUES lets the prior stand —
    # part_dream's own rules, applied to the circle's reflexive record.
    obs = sections["OBSERVATION"].strip()
    if obs:
        o_cont, o_body = RD.message_continues(obs)
        if o_body:
            out["observation"] = o_body
            sal_raw = sections.get("SALIENCE")
            out["obs_salience"] = RM.remember_salience_coerce(sal_raw)
            if (sal_raw is None
                    or sal_raw.strip().lower() not in RM.SALIENCE_VALUES):
                out["suspect"].append(
                    f"OBSERVATION SALIENCE absent or unparseable "
                    f"({sal_raw!r}) — coerced to 'passing'")
            resolution = sections.get("RESOLUTION")
            resolved = bool(resolution and resolution.strip())
            if resolved and prior_obs and prior_obs.get("salience") != "charged":
                out["suspect"].append(
                    "OBSERVATION RESOLUTION claimed but the prior "
                    f"observation was not tagged 'charged' (was "
                    f"{prior_obs.get('salience')!r})")
            out["obs_continues"] = o_cont or resolved
        # a bare CONTINUES lets the prior observation stand — nothing staged

    self_new = sections["SELF"].strip()
    if self_new:
        if set(RD.message_headings_read(self_new)) != set(RD.message_headings_read(self_now)):
            out["suspect"].append(
                "SELF replacement changes self.md's heading set — a dropped "
                "section is silent loss; refused, self.md stands")
        else:
            out["self_md"] = self_new
    return out
