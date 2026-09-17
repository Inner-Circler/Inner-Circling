#!/usr/bin/env python3
"""
git_hook_script.py — THE THREE SHELL SCRIPTS, and the code that installs them. 2026-09-09.

AND MOST OF IT IS NOT PYTHON. PRE_COMMIT is 834 lines of /bin/sh inside a Python string,
so compile() and pyflakes walk straight past it — which is exactly why _hook_syntax_check()
exists, shelling each rendered body through `sh -n`. Naming the file for what it holds means
a reader looking for the gate's behaviour opens the file that has it.

A BUMP IS NOT A CHANGELOG (R525). Every comment here states what is true of the code beside
it; what CHANGED and why goes in the commit message, where git keeps it and no reader pays
for it — and every comment in the PRE_COMMIT string is paid for on every commit, by every
worktree, since `sh` parses the whole rendered hook. `git log -p -- coordinator/
git_hook_script.py` is where a version's account is read.

WHETHER AN EDIT CHANGED THE PROGRAM OR ONLY ITS COMMENTS is work/tools/hook_strip_diff.py's
answer — HEAD against the working tree by default, or any two refs. A changed body needs its
mark bumped either way; the tool says whether the change is behaviour-safe.

THIS IS A TEMPLATE, NOT A FILE YOU EDIT. `.git/hooks/pre-commit` is a RENDERING of
PRE_COMMIT below. Editing the installed hook installs nothing and editing this installs
nothing either: system_git_hooks_ensure() reinstalls only when HOOK_MARK DIFFERS, so a
change here needs its mark bumped and then

    python coordinator/circle_audit.py --git-setup

run FROM THE MAIN CHECKOUT — .git/hooks/ is shared with every worktree, so installing from
one would publish a template that exists only on that branch.

A CHANGE ALSO NEEDS ITS TRIGGER CHECKED. A `case "$FILES" in ...` arm that matches no path
never runs, and a file inside a trigger whose arm never INVOKES it reports nothing — v45
(2026-08-18) is that exact defect, found a day late.

THE DEPENDENCY IS ONE-WAY, and with NOTHING coming back. This module imports gitrepo;
gitrepo imports nothing from here. That was checked rather than assumed: the plan for this
move expected a back-edge from gitrepo.main() and there is none — main() is `--identity`
only, a read-only window onto system_git_identity_resolve(), and the one caller of
system_git_hooks_ensure() is circle_audit.circle_audit_git_setup(). So no lazy import and no
cycle-breaker is needed here, and the module-level import graph system_layer_verify.py reads
stays acyclic without one.
"""
from __future__ import annotations

import os
import pathlib
import subprocess

import gitrepo as _G
from gitrepo import GitError, system_git_run

# ROOT IS READ THROUGH THE MODULE (_G.ROOT), NEVER FROM-IMPORTED. It is REBOUND —
# test_hook_template.py sets gitrepo.ROOT to a temp tree to prove the battery installs
# in a dev tree and refuses to install in a bundle that has no coordinator/tests/ — and
# a from-import would bind a copy that never sees the rebinding. Same rule, same reason,
# as record_paths.py:28 for its constants and seam.py for emit/read_line.

# tempfile is NOT imported here: _sh_n() and _hook_syntax_check() each import it inside
# themselves, which is how they arrived and is left as it was — a module-level import
# beside them is a second, unused one and pyflakes says so.

# THE HOOK VERSION IS NOT AN ALLOCATED ID and takes no placeholder, so
# assign_ids.py cannot help here. The rule that does: after any merge
# that touches this file, compare the template's mark against
# .git/hooks/pre-commit's, and bump if the BODIES differ even when the
# marks agree.
HOOK_MARK = "# inner-circling pre-commit v196"
HOOK_FAMILY = "# inner-circling pre-commit v"
PRE_COMMIT = f'''#!/bin/sh
{HOOK_MARK}
# Verifies whatever the commit actually touches. Nothing here depends on a human
# remembering to run a verifier.
#
# Local-only repository, so this hook never leaves the machine.
# Bypass deliberately with: git commit --no-verify
set -e
FILES=$(git diff --cached --name-only)

# THE INTERPRETER, RESOLVED ONCE, HERE. `.venv/Scripts/python.exe` is this
# machine's layout: a POSIX venv puts it at .venv/bin/python, and a clone that
# has not made one yet has neither.
PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY=".venv/bin/python"
# A WORKTREE HAS NO .venv OF ITS OWN. Resolve the MAIN TREE's .venv via
# git-common-dir before falling back to bare python;
# same lookup coordinator/system_lint_verify.py's venv_python() and
# .claude/skills/my_commit/my_commit.py's own venv-finder already use.
if [ ! -x "$PY" ]; then
    GCD=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
    if [ -n "$GCD" ]; then
        MAIN_ROOT=$(dirname "$GCD")
        MPY="$MAIN_ROOT/.venv/Scripts/python.exe"
        [ -x "$MPY" ] || MPY="$MAIN_ROOT/.venv/bin/python"
        [ -x "$MPY" ] && PY="$MPY"
    fi
fi
[ -x "$PY" ] || PY="python"

# AND A SCRIPT THIS TREE DOES NOT HAVE IS NOT A FAILURE. The published package
# ships 6 of the 72 scripts named below -- the probes and the dev gates are not
# part of the product -- so naming one by path must not refuse a recipient's
# commit. The gates they DO have still run, and still fail the commit when they
# fail.
# WHERE A REFUSAL GOES. A check that refuses is the moment its reader is most
# stuck, and the checkers speak to a developer. So the output is CAPTURED as
# well as shown, and on a non-zero exit coordinator/gate_report.py writes
# work/diagnostics/gate_<time>.md -- ordinary language on the screen, the
# technical account and a prompt the person may choose to send in the file. It
# opens no socket; the sending is theirs.
#
# STREAMED AND CAPTURED BOTH. `cmd | tee` would report tee's exit status, so
# the status is carried out of the pipeline through a file — POSIX, and it
# keeps a long check printing as it goes rather than in one lump at the end.
GATE_OUT="${{TMPDIR:-/tmp}}/ic-gate-out.$$"
GATE_RC="${{TMPDIR:-/tmp}}/ic-gate-rc.$$"
trap 'rm -f "$GATE_OUT" "$GATE_RC"' EXIT

refused() {{   # $1 = exit code, rest = the check and its arguments
    code="$1"; shift
    if [ -f coordinator/gate_report.py ]; then
        "$PY" coordinator/gate_report.py --code "$code" --out "$GATE_OUT" -- "$@"
    fi
    exit 1
}}

run() {{
    [ -f "$1" ] || return 0
    if [ -n "$NOTE" ]; then printf '%s\n' "$NOTE"; NOTE=""; fi
    # THE STATUS HAS TO SURVIVE `set -e`. A pipeline stage is a SUBSHELL and
    # inherits errexit, so a FAILING probe kills the brace group before
    # `echo $?` can run, and rc then reads whatever the PREVIOUS probe left in
    # the file -- and the first check of every invocation
    # (file_line_endings_verify) passes and leaves "0" behind. That is a red
    # gate printing its failure IN FULL while the commit goes through.
    # Two guards, because either alone suffices and neither is obvious:
    #   `set +e` inside the group  the TRUE exit code is recorded
    #   `rm -f` before it          a group that dies anyway leaves NO file,
    #                              and a missing file reads as 1 rather than
    #                              as the last probe's success. FAILS CLOSED.
    rm -f "$GATE_RC"
    {{ set +e; "$PY" "$@" 2>&1; echo $? > "$GATE_RC"; }} | tee "$GATE_OUT"
    rc=$(cat "$GATE_RC" 2>/dev/null || echo 1)
    [ "$rc" = "0" ] || refused "$rc" "$@"
}}

# AND THE SAME, FOR A SCRIPT WHOSE OWN OUTPUT IS NOISE. `run X >/dev/null`
# at the call site redirected system_git_run() ITSELF, so the note it was about to print
# went with it — one announcement silently absent from the dev tree's own
# hook run, which is how this was caught.
quiet() {{
    [ -f "$1" ] || return 0
    if [ -n "$NOTE" ]; then printf '%s\n' "$NOTE"; NOTE=""; fi
    # `|| rc=$?` TESTS the status, so errexit does not fire. A bare command
    # would trip `set -e` and exit the hook non-zero, which refuses -- but
    # SILENTLY, before `cat "$GATE_OUT"` and before gate_report, leaving the
    # reader a failed commit and not one word about which check failed or why.
    rc=0
    "$PY" "$@" > "$GATE_OUT" 2>&1 || rc=$?
    [ "$rc" = "0" ] || {{ cat "$GATE_OUT"; refused "$rc" "$@"; }}
}}

# ADVISORY ONLY -- the one case here that never refuses, unlike run()/quiet()
# above. packaging/scaffold_staleness.py's answer ("might be stale") is a
# REMINDER, not a verdict: resolving it means running conform_packaging.py,
# which costs a real paid model call, and a commit hook may not spend that for
# you. The hard gate is publish.py's own preflight, the one moment staleness
# actually reaches a user.
advise() {{
    [ -f "$1" ] || return 0
    if [ -n "$NOTE" ]; then printf '%s\n' "$NOTE"; NOTE=""; fi
    "$PY" "$@" || true
}}

# FIRST, and unconditional. `.gitattributes` sets `* -text`, so a CR that
# reaches a commit is a CR that reaches every sha256 downstream of it —
# nothing normalises it away. Three files were converted wholesale on
# 2026-08-07 and every other check passed.
run coordinator/file_line_endings_verify.py --staged
case "$FILES" in *groups/*)
    NOTE="  pre-commit: a group's record touched — every group's tree is checked"
    run memory/record_verify.py
    for gdir in groups/*/; do
        gname="${{gdir#groups/}}"; gname="${{gname%/}}"
        [ "$gname" = "ifs" ] && continue
        [ -d "$gdir/parts" ] || continue
        run coordinator/circle_audit.py --selftest --group "$gname"
        [ -d "$gdir/issues" ] && run memory/issue_gate.py "$gdir/issues"
    done
esac

case "$FILES" in *issues/*|*coordinator/tests/test_issue_gate.py*\
|*memory/issue_gate.py*|*memory/issue_schema.py*)
    NOTE="  pre-commit: issues/ or its gate/schema touched"
    run memory/issue_gate.py
    run coordinator/tests/test_issue_gate.py
esac

# THE RECORD'S OWN CHECKS, SPLIT OUT FROM THE CODE SUITES BELOW, AND THE SPLIT
# IS BY WHAT A CHECK READS, NOT BY WHERE ITS FILE LIVES. This case runs
# whatever reads the RECORD and keeps the full union trigger; the case below
# keeps the module patterns alone. A commit touching code AND records fires
# both, and nothing runs twice -- the invocations here are not repeated there.
#
# test_inter_circle.py IS HERE, AND IT IS THE EXPENSIVE ONE (~24s). It stays on
# the record trigger because it REHEARSES against the newest CLOSED circle
# (`ots[-1]` after filtering for a close report) and snapshots every live
# register to prove the rehearsal wrote nothing. A records-only commit is
# precisely when a new closed circle has appeared. The other eight suites that
# read outside their own temp tree stay below: four read packaging/scaffold/
# and four read coordinator/process_core.md, and a close commit touches neither.
#
# TWO FLAGS, ONE MODULE LIST. The record checks must ALSO fire for a code
# change, so the naive split -- two cases, two pattern lists -- would need the
# 88 module patterns written twice and kept in step by hand, which is the
# duplicate-fact defect system_unique_home_verify.py refuses in a file it
# cannot see into. The record trigger is the data patterns OR the module list,
# and the module list is written once.
#
# `if`, NOT a `&&` with a brace group -- the hook runs under `set -e`, where a
# && whose test fails is a non-zero command at the top level and kills the
# hook. The two blocks below are the whole reason this is spelled out.
IC_RECORD=""
IC_CODE=""
case "$FILES" in *parts/*|*self/*|*circles/*.toml*)
    IC_RECORD=1
esac

# THE CODE SUITES. Module paths only -- the three record patterns (*parts/*,
# *self/*, *circles/*.toml*) live in the case above. `*packaging/scaffold/groups/*`
# covers a scaffold edit under parts/, circles/ or issues/, which those three
# patterns used to be what reached test_scaffold_delegates.py for.
case "$FILES" in *groups/*/group.toml*\
|*coordinator/practice_manager.py*|*coordinator/practice_verify.py*|*coordinator/circle.py*\
|*coordinator/command_surface.py*|*coordinator/llm_client.py*\
|*coordinator/prompt_build.py*|*coordinator/annotations.py*|*coordinator/propose_lifecycle.py*\
|*coordinator/remember_expand.py*|*coordinator/tests/test_remember_expand.py*\
|*coordinator/recall_index.py*|*coordinator/tests/test_recall_index.py*\
|*coordinator/embed_store.py*|*coordinator/process_core.md*\
|*coordinator/help_system.py*|*coordinator/commands.py*\
|*coordinator/proposal_vetting.py*|*coordinator/circle_rounds.py*\
|*coordinator/REGISTER_CLASS.py*|*coordinator/tests/test_practice_verify.py*\
|*coordinator/tests/test_practice_annotations.py*|*coordinator/proposal_manager.py*\
|*coordinator/tests/test_proposal_manager.py*|*coordinator/topic_manager.py*\
|*coordinator/tests/test_topic_manager.py*|*coordinator/inter_circle.py*\
|*coordinator/part_dreaming.py*|*coordinator/circle_synthesis.py*\
|*coordinator/tests/test_inter_circle.py*|*coordinator/circle_history_manager.py*\
|*packaging/scaffold/groups/*|*coordinator/tests/test_scaffold_delegates.py*\
|*coordinator/JOURNAL_CLASS.py*|*coordinator/tests/test_journal_class.py*\
|*coordinator/tests/test_circle_history_manager.py*\
|*coordinator/tests/test_part_dreaming_grounding.py*\
|*coordinator/circle_observation_manager.py*\
|*coordinator/tests/test_circle_observation_manager.py*\
|*coordinator/circle_journal_manager.py*\
|*coordinator/tests/test_circle_journal_manager.py*\
|*coordinator/setting_manager.py*|*coordinator/tests/test_setting_manager.py*\
|*coordinator/system_setting_verify.py*\
|*coordinator/process_core.md*\
|*coordinator/providers.py*|*coordinator/tests/test_providers.py*\
|*coordinator/backfill.py*|*coordinator/tests/test_register_gate.py*\
|*coordinator/record_model.py*|*memory/register_gate.py*|*coordinator/tests/test_annotations.py*\
|*coordinator/remember_manager.py*|*coordinator/tests/test_remember_manager.py*\
|*coordinator/remember_prompt_projection.py*|*coordinator/remember_list_projection.py*\
|*coordinator/quote_as_lands.py*|*coordinator/tests/test_quote_as_lands.py*\
|*coordinator/process_core.md*|*coordinator/process_ifs.md*|*coordinator/part_roster.py*\
|*coordinator/tests/test_annotation_exemplars.py*\
|*coordinator/transcript_store.py*|*coordinator/tests/test_transcript_store.py*\
|*coordinator/part_mid_term_manager.py*|*coordinator/tests/test_part_mid_term_manager.py*\
|*coordinator/tests/test_proposal_vetting.py*|*coordinator/tests/test_issue_commands.py*\
|*coordinator/tests/test_circle_rounds_display.py*|*coordinator/llm_client.py*\
|*coordinator/token_count.py*|*coordinator/tests/test_token_count.py*\
|*coordinator/tests/test_llm_client.py*\
|*coordinator/tests/test_issue_status_cmd.py*|*coordinator/tests/test_help_system.py*\
|*coordinator/tests/test_dispatch_partition.py*|*coordinator/tests/test_issue_add.py*\
|*coordinator/tests/test_backfill.py*\
|*coordinator/tests/test_issue_prompt_projection.py*|*coordinator/tests/test_spend_report.py*\
|*coordinator/tests/test_strip_malformed_annotations.py*\
|*coordinator/LLM_response_disassembler.py*\
|*coordinator/tests/test_llm_response_disassembler.py*\
|*memory/issue_status.py*|*memory/issue_commands.py*|*coordinator/PROPOSE_CLASS.py*\
|*coordinator/process_core_prompt_projection.py*|*coordinator/quote_verify.py*\
|*memory/issue_prompt_projection.py*)
    IC_RECORD=1
    IC_CODE=1
esac

# THE RECORD'S OWN CHECKS. Fires for a record change OR a code change, so this is
# exactly as often as the single case fired before the split.
if [ -n "$IC_RECORD" ]; then
    NOTE="  pre-commit: the record, or code that reads it, was touched"
    # THE TRIGGER NAMES coordinator/process_ifs.md AS WELL AS process_core.md,
    # because test_annotation_exemplars.py reads the COMPOSED rulebook -- the
    # [proposed:] exemplars live in the IFS layer, so the file that holds the
    # counted exemplars must fire the suite that counts them. process_band.md is
    # deliberately NOT added: circle_identity_text_render() composes the DEFAULT
    # layer, so this suite reads the IFS one and never the band's.
    run coordinator/circle_audit.py --selftest
    run coordinator/practice_verify.py
    run coordinator/logbook_ruling_verify.py
    run memory/issue_prompt_projection.py
    run coordinator/quote_verify.py
    run coordinator/system_setting_verify.py
    run coordinator/tests/test_inter_circle.py
fi

if [ -n "$IC_CODE" ]; then
    NOTE="  pre-commit: parts/, self/ (incl. self/best_practices.toml), or its
  implementation (practice_manager.py, practice_verify.py/circle.py/REGISTER_CLASS.py/
  proposal_manager.py)
  touched"
    run coordinator/tests/test_practice_verify.py
    run coordinator/tests/test_practice_annotations.py
    run coordinator/tests/test_issue_prompt_projection.py
    run coordinator/tests/test_topic_manager.py
    run coordinator/tests/test_register_gate.py
    # Its own suite, because test_register_gate.py runs on bytes it builds
    # itself and so cannot notice that the 30 migrated records are still whole.
    run coordinator/tests/test_circle_observation_manager.py
    run coordinator/tests/test_circle_journal_manager.py
    run coordinator/tests/test_part_dreaming_grounding.py
    run coordinator/tests/test_backfill.py
    run coordinator/tests/test_llm_response_disassembler.py
    run coordinator/tests/test_scaffold_delegates.py
    run coordinator/tests/test_journal_class.py
    run coordinator/tests/test_circle_history_manager.py
    run coordinator/tests/test_remember_manager.py
    # It rides this case because its subjects are already here: circle.py's
    # Self> loop calls it, and it writes through remember_manager.py, whose cap
    # it changed.
    run coordinator/tests/test_quote_as_lands.py
    # THE ANNOTATION SURFACE. process_core.md and part_roster.py are in THIS
    # case because they are what the parts are actually taught, and nothing
    # else that triggers on them reads the GRAMMAR. The suite parses
    # process_core.md's OWN exemplars through the real grammar, so the taught
    # form and the parsed form cannot drift apart -- that divergence is E09's
    # shape.
    run coordinator/tests/test_annotation_exemplars.py
    # AND THE COMMAND PANE'S DISPATCH SUITE, which reads annotations.py as SOURCE
    # (ASK_KEYWORDS, by ast) and asserts the keyword list -- property 7's shape
    # (audit-register 2026-09-11 #12). --fast: the delay tests nothing a gate needs.
    run ui/tests/test_circling.py --fast
    run coordinator/tests/test_strip_malformed_annotations.py
    run coordinator/tests/test_proposal_manager.py
    run coordinator/tests/test_annotations.py
    run coordinator/tests/test_remember_expand.py
    run coordinator/tests/test_recall_index.py
    run coordinator/tests/test_circle_rounds_display.py
    run coordinator/tests/test_llm_client.py
    # ITS SUBJECT RUNS ONLY AT A LIVE CLOSE -- a dry-run circle takes the
    # `not live` branch on the function's first line, so test_circle_engine.py
    # exercises the guard and never the write.
    run coordinator/tests/test_spend_report.py
    run coordinator/tests/test_setting_manager.py
    run coordinator/tests/test_providers.py
    run coordinator/tests/test_token_count.py
    run coordinator/tests/test_transcript_store.py
    run coordinator/tests/test_part_mid_term_manager.py
    run coordinator/tests/test_proposal_vetting.py
    run coordinator/tests/test_issue_commands.py
    run coordinator/tests/test_issue_status_cmd.py
    run coordinator/tests/test_issue_status_write.py
    run coordinator/tests/test_help_system.py
    run coordinator/tests/test_dispatch_partition.py
    run coordinator/tests/test_command_policy.py
    run coordinator/tests/test_issue_add.py
fi

case "$FILES" in *coordinator/group_manager.py*|*coordinator/group_context.py*\
|*coordinator/group_attention.py*|*coordinator/parts_prompt_projection.py*\
|*coordinator/role_attention.py*|*coordinator/role_context.py*\
|*coordinator/topic_prompt_projection.py*|*coordinator/prompt_build.py*\
|*coordinator/tests/test_group_manager.py*|*coordinator/tests/test_parts_prompt_projection.py*\
|*coordinator/tests/test_prompt_build.py*|*coordinator/tests/test_role_attention.py*\
|*coordinator/tests/test_role_context.py*|*coordinator/tests/test_topic_prompt_projection.py*)
    NOTE="  pre-commit: the Block 1-4 assembly split (group_context/group_attention/
  parts_prompt_projection/role_attention/role_context/topic_prompt_projection/group_manager) touched"
    run coordinator/tests/test_group_manager.py
    run coordinator/tests/test_parts_prompt_projection.py
    run coordinator/tests/test_prompt_build.py
    run coordinator/tests/test_role_attention.py
    run coordinator/tests/test_role_context.py
    run coordinator/tests/test_topic_prompt_projection.py
esac

# THE TOKEN COUNTER differences CUMULATIVE PREFIXES to get per-block numbers.
# That subtraction is exact only because `system` is a list of separately-
# tokenized blocks -- an edit that concatenated them first would still "work"
# and be quietly wrong, which is what its probe is for.
#
# THE ROOM AND THE RECORD PART COMPANY in circle_rounds.py, and two rulings
# pull in opposite directions there: the trailing `[pass]` sign-off is dropped
# from BOTH, the whitespace-only lines from the ROOM ONLY. Getting them the
# wrong way round is silent -- nothing re-reads a transcript during a circle,
# so a record quietly losing blank lines would surface as a close report that
# will not reproduce, months later.
#
# THE TRANSPORT rides the same case: llm_client.py is the one module every
# statement and every short_term passes through, and its suite pins Self's
# retry ladder over the calls made once there is a record to lose.

# `work/pending/`, `rulings/` AND `work/instrument/LOG.md` ARE IN THIS TRIGGER
# because a branch writes its ruling, its progress note and its E entry there,
# not at a logbook's tail -- so a commit adding one must reach the checker that
# holds it to shape and to the branch rule. Otherwise the first reading of a
# malformed entry is the merge, which is the one moment no hook fires and the
# reader is not its author. progress.md is here for the branch-write refusal,
# the other half of the same rule.
case "$FILES" in *rulings/*|*progress.md*|*work/pending/*|*work/instrument/LOG.md*\
|*coordinator/logbook_ruling_verify.py*|*coordinator/tests/test_logbook_ruling_verify.py*)
    NOTE="  pre-commit: rulings/, progress.md, LOG.md, or a pending entry touched"
    run coordinator/logbook_ruling_verify.py
    run coordinator/tests/test_logbook_ruling_verify.py
esac

case "$FILES" in *coordinator/assign_ids.py*|*coordinator/tests/test_assign_ids.py*\
|*coordinator/ruling_sweep.py*)
    NOTE="  pre-commit: the id assign step touched"
    run coordinator/tests/test_assign_ids.py
esac

case "$FILES" in *NEXT.md*|*coordinator/logbook_next_verify.py*\
|*coordinator/tests/test_logbook_next_verify.py*)
    NOTE="  pre-commit: NEXT.md or its checker touched"
    run coordinator/logbook_next_verify.py
    run coordinator/tests/test_logbook_next_verify.py
esac

case "$FILES" in *coordinator/block_overlap_verify.py*|*coordinator/tests/test_block_overlap_verify.py*|*coordinator/process_core.md*|*coordinator/prompt_build.py*|*self/best_practices.toml*|*parts/*)
    NOTE="  pre-commit: a prompt block source or its overlap checker touched"
    # Through the venv, not bare `python`: this checker imports circle.py,
    # which imports anthropic, and the hook's `python` is the system 3.10
    # (measured in system_lint_verify.py's docstring). Same reason ui/ is called
    # this way below.
    run coordinator/block_overlap_verify.py
    run coordinator/tests/test_block_overlap_verify.py
esac

case "$FILES" in *docs/BNF.md*|*docs/PRODUCT_BNF.md*|*GROUP_BNF.md*|*work/tools/bnf_compose.py*|*work/tools/test_bnf_compose.py*)
    NOTE="  pre-commit: the grammar's SOURCES or its composition touched"
    # THE GUARD RUNS BEFORE THE CONFORMANCE HARNESS BELOW, and the order is the
    # point: docs/BNF.md is GENERATED (D101), so a conformance verdict on a
    # docs/BNF.md that is not its sources' composition is a verdict on a file
    # nobody wrote. Its own probe runs first, for the same reason the harness's
    # does — a guard that cannot fail is not evidence either.
    run work/tools/test_bnf_compose.py
    run work/tools/bnf_compose.py --check
esac

case "$FILES" in *docs/BNF.md*|*work/tools/bnf_conformance.py*|*work/tools/bnf_known_gaps.toml*|*work/tools/test_bnf_conformance.py*|*work/graph/prompt_grammar_draw.py*\
|*coordinator/LLM_response_disassembler.py*|*coordinator/REGISTER_CLASS.py*|*coordinator/annotations.py*\
|*coordinator/circle.py*|*coordinator/circle_open.py*|*coordinator/circle_rounds.py*|*coordinator/circle_synthesis.py*\
|*coordinator/command_suggest.py*|*coordinator/dependency_manager.py*\
|*coordinator/circle_history_manager.py*|*coordinator/circle_journal_manager.py*\
|*coordinator/circle_observation_manager.py*|*coordinator/circling_verify.py*|*coordinator/command_surface.py*\
|*coordinator/commands.py*|*coordinator/dream_history_manager.py*|*coordinator/group_manager.py*\
|*coordinator/help_system.py*|*coordinator/initialization.py*|*coordinator/instrument_manager.py*\
|*coordinator/logbook_ruling_verify.py*|*coordinator/part_add.py*|*coordinator/part_dreaming.py*\
|*coordinator/part_roster.py*|*coordinator/practice_manager.py*|*coordinator/prompt_build.py*\
|*coordinator/prompt_capture.py*|*coordinator/proposal_group_manager.py*|*coordinator/proposal_manager.py*\
|*coordinator/proposal_vetting.py*|*coordinator/recall_index.py*|*coordinator/record_paths.py*\
|*coordinator/redaction_manager.py*|*coordinator/remember_list_projection.py*|*coordinator/remember_manager.py*\
|*coordinator/ruling_manager.py*|*coordinator/setting_manager.py*|*coordinator/short_term_manager.py*\
|*coordinator/stream_redaction.py*|*coordinator/topic_manager.py*|*coordinator/working_set_manager.py*\
|*memory/TRANSACTION_CLASS.py*|*memory/issue_gate.py*|*memory/issue_schema.py*|*memory/issue_status.py*\
|*ui/circling.py*|*ui/ticker/bridge.py*)
    NOTE="  pre-commit: docs/BNF.md, its conformance harness, or code the harness checks touched"
    # The harness checks the CODE against the grammar, so this arm names every production file
    # it reads as well as the grammar and the harness itself. test_hook_template.py parses the
    # harness's path literals and fails when one is missing here. The data files the harness
    # only checks exist (groups/, self/) stay out: they change at every circle's close.
    # The harness's own probe runs FIRST: a broken harness's verdict
    # on docs/BNF.md is not evidence, so checking it before trusting it is
    # the only order that means anything.
    run work/tools/test_bnf_conformance.py
    run work/tools/bnf_conformance.py
esac

case "$FILES" in *coordinator/dream_history_manager.py*|*coordinator/tests/test_dream_history_manager.py*)
    NOTE="  pre-commit: DREAM_HISTORY touched"
    # R359/B45 — the one writer of Self's history records; its suite proves
    # the bootstrap-once/fold-per-dream contract and that refusals write
    # nothing.
    run coordinator/tests/test_dream_history_manager.py
esac

case "$FILES" in *coordinator/proposal_group_manager.py*|*coordinator/tests/test_proposal_group_manager.py*)
    NOTE="  pre-commit: the proposal coalesce touched"
    # test_proposal_group_manager runs the module selftest itself, then the write path,
    # hash guard and ruled-group survival; test_vetting covers the loop the
    # coalesce presents into. R356/B69, and E22 for why the model call
    # lives at circle.py's checkpoints rather than in the loop these
    # suites drive.
    run coordinator/tests/test_proposal_group_manager.py
    run coordinator/tests/test_proposal_vetting.py
esac

case "$FILES" in *work/tools/htmlify.py*|*work/tools/test_htmlify.py*|*work/tools/test_htmlify_spy.js*)
    NOTE="  pre-commit: htmlify (the JOURNAL of rendered LEDGERs, B113) touched"
    # The probe holds the palette rule (no hex literal in the
    # tool; every colour a var(--ROLE) palette.py defines), opens-from-disk (no URL, no
    # CR), and the journal's rules (a ledger is never edited in place; --remove; the
    # index's previous/next). The lint runs through system_lint_verify's leg above.
    run work/tools/test_htmlify.py
esac

case "$FILES" in *work/tools/memory_probe.py*|*work/tools/test_memory_probe.py*)
    NOTE="  pre-commit: the B68 probe harness touched"
    # The suite is the tool's LAB GUARD (every mutating verb refuses off the
    # lab branch); a probe tool whose guard quietly stopped guarding could
    # seed a record or open a live circle in the main tree. R351/R354.
    run work/tools/test_memory_probe.py
esac

case "$FILES" in *work/tools/storage_audit.py*|*work/tools/test_storage_audit.py*)
    NOTE="  pre-commit: the storage audit touched"
    run work/tools/test_storage_audit.py
esac

case "$FILES" in *work/tools/hook_strip_diff.py*|*work/tools/test_hook_strip_diff.py*)
    NOTE="  pre-commit: the hook strip-diff touched"
    # The probe holds the one answer the tool must never give wrongly: IDENTICAL for an
    # edit inside a string, where a line opening with # is content, not comment.
    run work/tools/test_hook_strip_diff.py
esac

case "$FILES" in *.gitignore*)
    echo "  pre-commit: .gitignore touched — its re-negations are load-bearing"
    if git check-ignore -q work/sandbox/circles; then
        echo "  FAIL: work/sandbox/circles/ is ignored — the ruled negations"
        echo "        (!work/sandbox/circles/, !work/sandbox/prompts/) are broken."
        echo "        A directory-form ignore defeats them; see gitrepo.py."
        exit 1
    fi
    echo "    ok: work/sandbox/circles/ still tracked"
    # circle_commit_paths() stages both reports, and `git add --` refuses the whole list when
    # one path is ignored: an ignored report fails every live close.
    if git check-ignore -q --no-index work/logs/close_2000-01-01_0000.json work/logs/open_2000-01-01_0000.json; then
        echo "  FAIL: a circle's close or open report is ignored — the negations"
        echo "        (!work/logs/close_*.json, !work/logs/open_*.json) are broken, and"
        echo "        every live close would be refused its commit."
        exit 1
    fi
    echo "    ok: a circle's close and open reports are committable"
esac

case "$FILES" in *prompts/*)
    NOTE="  pre-commit: prompts/ touched"
    run coordinator/prompt_capture.py --verify
esac

# THE CLOSE STEP GETS A CLOSE RUN. ui/tests/test_circle_engine.py is the ONLY
# suite in the tree that drives a full /close: short_terms collected and
# written, the .toml located and parsed back with all four sections, the close
# path reaching commit_sandbox.
#
# ITS OWN CASE, NOT AN ADDITION TO THE ui/ ONE, and the cost is why. That case
# runs FIVE suites including two more real dry-run circles; hanging it off
# every circle.py commit would make the commonest commit in this tree
# noticeably slower for four suites nobody asked for.
#
# THE ARM NAMES coordinator/circle_open.py AS WELL AS circle.py. The driver is
# two files -- main() parses the flags and runs the Self> loop, circle_open()
# does everything between -- so an arm naming only circle.py goes on matching
# while silently ceasing to cover its subject. A trigger that names a path is
# not the same as a trigger that names a SUBJECT, and a carve is exactly when
# the two come apart.
#
# AND circle_rounds.py, THE TURN ENGINE: this suite runs a real round of it
# (178 lines, measured by tracer, audit-register 2026-09-11 #4), while the
# IC_CODE block circle_rounds.py sits in runs only the DISPLAY suite.
case "$FILES" in *coordinator/circle_close.py*|*coordinator/circle.py*|*coordinator/circle_open.py*|*coordinator/circle_rounds.py*)
    NOTE="  pre-commit: the close step or its driver touched — running a real dry-run close"
    run ui/tests/test_circle_engine.py
    # The exemplars suite reads circle_close.py as SOURCE (the pure-split consultation
    # before any write) -- property 7 (audit-register 2026-09-11 #12).
    run coordinator/tests/test_annotation_exemplars.py
esac

case "$FILES" in *coordinator/circle.py*|*coordinator/circle_open.py*|*coordinator/tests/test_circle_argv.py*\
|*memory/record_verify.py*|*coordinator/llm_client.py*)
    NOTE="  pre-commit: circle.py's refusals or a gate they consult touched"
    run coordinator/tests/test_circle_argv.py
esac

case "$FILES" in *coordinator/*|*memory/*|*ui/*|*packaging/*|*.claude/skills/*|*work/graph/*|*work/tools/*)
    NOTE="  pre-commit: code touched — compiling and linting every module"
    # THE PATTERN IS system_lint_verify.CODE_DIRS PLUS ITS EXTRA_LEGS. A whole-
    # directory leg is `*<dir>/*`, and every leg is one today: work/tools was the
    # last narrowed to a glob, widened 2026-09-11 once the directory linted clean
    # (audit-register 2026-09-11 #10). Nothing else compiles those files: work/
    # is deliberately outside CODE_DIRS.
    #
    # .claude/skills/ IS A SCOPE LEG, NOT A CODE_DIR: CODE_DIRS also drives
    # file_line_endings_verify.SCOPE_DIRS, and .claude/ is CRLF by convention.
    #
    # test_system_lint_verify holds this pattern to CODE_DIRS + the legs, glob
    # included -- comparing directory names alone let a trigger claim coverage
    # the scope did not deliver.
    run coordinator/system_lint_verify.py
    run coordinator/system_unique_home_verify.py
    run coordinator/tests/test_system_unique_home_verify.py
    run coordinator/system_layer_verify.py
    run coordinator/tests/test_system_layer_verify.py
    run coordinator/system_name_verify.py
    run coordinator/tests/test_system_name_verify.py
    run coordinator/tests/test_system_lint_verify.py
esac

case "$FILES" in *coordinator/file_line_endings_verify.py*\
|*coordinator/tests/test_file_line_endings_verify.py*)
    # The CR/NUL gate runs on every commit (the unconditional line at the top),
    # so what needs invoking here is the probe that proves it still REFUSES. A
    # checker whose own probe is never invoked reports nothing.
    NOTE="  pre-commit: the CR/NUL gate touched — asserting it still refuses"
    run coordinator/tests/test_file_line_endings_verify.py
esac

case "$FILES" in *coordinator/gate_report.py*\
|*coordinator/tests/test_gate_report.py*)
    NOTE="  pre-commit: the diagnostic note touched — asserting what it does
  and does not carry"
    run coordinator/tests/test_gate_report.py
esac

case "$FILES" in *coordinator/gitrepo.py*|*coordinator/git_hook_script.py*|*coordinator/tests/test_backup_hooks.py*)
    NOTE="  pre-commit: the hook templates touched — asserting the backup hooks
  still install on the path that actually runs"
    run coordinator/tests/test_backup_hooks.py
esac

# (a) THE TWO OPEN-TIME REPORTS. circle.py's two detectors -- a close that died
#     before ANY short_term (settled by the start-of-close marker) and a circle
#     whose dreaming failed (settled by the dream/<OT> tag) -- are read-only
#     path logic with fixtures, so they cost a fraction of a second and they
#     ride circle.py itself, the file whose edit can break them.
#
# (b) work/graph/*.py IS IN THE LINT TRIGGER ABOVE as an EXTRA_LEG, not a
#     CODE_DIR (see system_lint_verify's own note on why), and its probe runs
#     here. Nothing else checks the script that REFUSES to draw a wrong picture.
case "$FILES" in *coordinator/circle.py*|*coordinator/circle_open.py*|*coordinator/circle_close.py*|*coordinator/tests/test_close_marker.py*)
    NOTE="  pre-commit: circle.py's open-time failure reports touched"
    run coordinator/tests/test_close_marker.py
esac

case "$FILES" in *coordinator/circle.py*|*coordinator/circle_open.py*|*coordinator/transcript_store.py*\
|*coordinator/tests/test_discard_unspoken.py*)
    NOTE="  pre-commit: the no-trace discard touched"
    run coordinator/tests/test_discard_unspoken.py
esac

case "$FILES" in *coordinator/short_term_manager.py*|*coordinator/tests/test_short_term_manager.py*|*coordinator/circle_close.py*|*coordinator/backfill.py*|*coordinator/part_dreaming.py*|*coordinator/record_model.py*)
    NOTE="  pre-commit: the SHORT_TERM record's reader/writer, or a module that writes through it, touched"
    run coordinator/tests/test_short_term_manager.py
esac

# THE COLLECTOR, HANDED AN IMPERFECT REPLY. short_term_collect() decides whether a
# circle's record is whole, and every other suite that reaches it runs dry, where
# the canned reply is well-formed by construction. This one scripts the reply:
# the resume guard, both `failed` arms, seam.fail(), and the two close-time
# remember writers (audit-register 2026-09-11 #1).
case "$FILES" in *coordinator/circle_close.py*|*coordinator/tests/test_short_term_collect.py*)
    NOTE="  pre-commit: the close step's collector touched — handing it an imperfect reply"
    run coordinator/tests/test_short_term_collect.py
esac

case "$FILES" in *coordinator/ruling_manager.py*|*coordinator/ruling_migrate.py*|*coordinator/tests/test_ruling_manager.py*|*rulings/*)
    NOTE="  pre-commit: the RULING record, its reader/writer, or its suite touched"
    run coordinator/ruling_manager.py
    run coordinator/tests/test_ruling_manager.py
esac

# coordinator/seam.py's two stated invariants -- the closed UI-signal-channel
# set, and only three named sites opening the "circle" read_line channel -- are
# held by this suite and by nothing else. The three sites are three MODULES,
# each in the trigger: circle.py (the speaking prompt), circle_open.py (the
# topic) and working_set_manager.py (the working set). ui/circling.py is here
# because the suite reads its queue drain -- the inline second copy of the
# UI-signal set -- and asserts it handles every channel emit() does.
# test_hook_template.py parses the suite's own path literals and holds this
# arm to them.
case "$FILES" in *coordinator/seam.py*|*coordinator/tests/test_seam.py*|*coordinator/circle.py*\
|*coordinator/circle_open.py*|*coordinator/working_set_manager.py*|*ui/circling.py*)
    NOTE="  pre-commit: seam.py's channel contract touched, or a new
  circle-channel read_line site"
    run coordinator/tests/test_seam.py
esac

# The module diagram DISCOVERS its modules by scanning coordinator/, memory/ and ui/, and
# validate() refuses a module its hand-typed REGION_OF does not place or a record file its
# FILES table does not claim — so a new module in any of the three, or a module naming a new
# record file, moves the drawing without touching the drawer. Those directories fire the
# suite; it runs in seconds. Its drawings are untracked, so nothing is redrawn here.
case "$FILES" in *work/graph/coordinator_draw.py*|*work/graph/test_coordinator_draw.py*\
|*coordinator/*.py*|*memory/*.py*|*ui/*.py*)
    NOTE="  pre-commit: the module diagram's derivations, or a module it must place, touched"
    run work/graph/test_coordinator_draw.py
esac

# The subsystem picture derives its centre from coordinator_draw AND the two
# sibling drawers' function columns, so a change to any of the three can move
# it — trigger and invocation land together (v19's rule). And it refuses with
# coordinator_draw, so the same three directories fire it.
case "$FILES" in *work/graph/llm_orchestration_draw.py*|*work/graph/test_llm_orchestration_draw.py*\
|*work/graph/coordinator_draw.py*|*work/graph/prompt_grammar_draw.py*\
|*work/graph/llm_response_data_flow_draw.py*|*coordinator/*.py*|*memory/*.py*|*ui/*.py*)
    NOTE="  pre-commit: the subsystem picture's derivations, or a module it must place, touched"
    run work/graph/test_llm_orchestration_draw.py
esac

# THE MODULE-GRAPH REDRAW IS GONE and the drawings are UNTRACKED, the way
# work/graph/issue_graph.* already was (R365) and for the same stated reason:
# nothing reads a picture back, it is for a person to open, and it is rebuilt
# from tracked source whenever it falls behind. Nothing stored is nothing to
# conflict over -- redrawing and staging ten tracked artifacts on every commit
# put merge conflicts with no human answer in front of the operator, and the
# ruling was to remove the premise: *"stop saving them and do the merges
# yourself"*. Rebuild by hand:
#
#     python work/graph/coordinator_draw.py --dump
#     python work/graph/coordinator_draw.py --live --dump
#     python work/graph/coordinator_draw.py --simple
#     python work/graph/coordinator_draw.py --live --simple

case "$FILES" in *memory/record_verify.py*|*coordinator/tests/test_record_verify.py*)
    NOTE="  pre-commit: the corruption gate touched — asserting it still refuses"
    run coordinator/tests/test_record_verify.py
esac

case "$FILES" in *coordinator/*|*memory/*|*packaging/*|*process_core.md*\
|*ui/*|*groups/*|*docs/*|*work/*|*README.md*|*LICENSE*|*NOTICE*|*requirements.txt*\
|*.gitattributes*|*.gitignore*)
    NOTE="  pre-commit: shipped surface touched — the owner's name may not enter it"
    quiet packaging/sanitize.py --dry-run
    quiet packaging/shipped_references.py
esac

case "$FILES" in *packaging/package.py*|*packaging/test_package.py*|*packaging/sanitize.py*|*packaging/scan.py*|*packaging/ignore.txt*|*packaging/exceptions.toml*|*packaging/runtime_only.txt*\
|*packaging/required.toml*|*packaging/additions.toml*)
    NOTE="  pre-commit: the build, or a register it builds from, touched"
    # The two registers are here because the build refuses when both name one path: a
    # regenerated required.toml that newly reaches a file additions.toml also names fails
    # every build, and nothing else runs one.
    run packaging/test_package.py
esac

case "$FILES" in *coordinator/seam.py*|*coordinator/phase_clock.py*|*coordinator/tests/test_progress_indication.py*\
|*ui/circling.py*|*coordinator/circle.py*|*coordinator/circle_open.py*)
    NOTE="  pre-commit: the >3s progress indication — its cadence, and its silence"
    # Its own arm because the mechanism spans three modules that each already
    # trigger a DIFFERENT suite: seam.py runs test_seam, phase_clock.py runs
    # test_phase_clock, and neither would have run this. The clause it protects
    # is the one that can hurt somebody -- the beat must stay silent while a
    # person is typing -- and that guard is only true because every console read
    # in the tree is inside the WAITING span. A read added outside it re-opens
    # the hazard silently.
    #
    # ui/circling.py IS IN THE TRIGGER because the suite reads it by path and
    # asserts CircleEngine._emit calls system_output_mark() -- the call whose
    # absence killed the guard. circle.py arms the beat and chooses what it
    # looks like; circle_open.py holds the open step's console reads. Neither
    # fired this suite before (audit-register 2026-09-11 #4).
    run coordinator/tests/test_progress_indication.py
esac

case "$FILES" in *packaging/shipped_references.py*|*packaging/test_shipped_references.py*)
    NOTE="  pre-commit: the scan for references a recipient cannot resolve"
    run packaging/test_shipped_references.py
esac

case "$FILES" in *packaging/conform_packaging.py*|*packaging/test_conform_packaging.py*)
    NOTE="  pre-commit: the argument gate over a script that SPENDS and RECORDS"
    # conform_packaging.py's DEFAULT action makes up to 2 paid model calls and
    # then writes scaffold_check_state.toml, the record the publish gate reads.
    # parse_args is pure, so this suite costs nothing and can never reach the
    # model -- which is what makes it a probe that will still be run in a year.
    run packaging/test_conform_packaging.py
esac

case "$FILES" in *packaging/scaffold_staleness.py*|*packaging/test_scaffold_staleness.py*)
    NOTE="  pre-commit: the staleness hash touched — asserting it answers the same in every tree"
    # The sensor below is ADVISORY on purpose, so nothing refuses when its
    # answer depends on which directory asked -- and a gitignored live
    # counterpart can put its bytes in the hash in one tree and an absence
    # marker in another over byte-identical committed content. The HASH is the
    # thing to gate, not its reading; this suite holds the tree-independence.
    run packaging/test_scaffold_staleness.py
esac

# ADVISORY. This reminds, at commit time, on the same trigger as the sanitize
# case above plus .claude/CLAUDE.md itself (the thing conform_packaging.py
# judges every scaffold file against). It never refuses -- resolving a real
# STALE reading costs a paid model call, which a commit hook does not get to
# spend, and the hard gate is publish.py's own preflight.
case "$FILES" in *coordinator/*|*memory/*|*packaging/*|*process_core.md*\
|*.claude/CLAUDE.md*)
    NOTE="  pre-commit: scaffold-relevant files touched — checking staleness (advisory)"
    advise packaging/scaffold_staleness.py --check
esac

case "$FILES" in *memory/TRANSACTION_CLASS.py*|*coordinator/circle_audit.py*\
|*coordinator/tests/test_TRANSACTION_CLASS.py*|*coordinator/tests/test_circle_audit_lock.py*\
|*coordinator/atomic_write.py*)
    # atomic_write.py is THE UNIVERSAL WRITE PATH (38 call sites) and has no
    # trigger of its own, so it rides this case.
    NOTE="  pre-commit: the audit's transaction/lock machinery, or atomic_write, touched"
    # Both probes build their own temp trees (transaction's crash states via a
    # scripted os.replace failure, the lock cases against a rebound
    # circle_audit.LOCK) -- nothing here reads or writes work/nightly or the
    # live registers, so this can never race a real run.
    run coordinator/tests/test_TRANSACTION_CLASS.py
    run coordinator/tests/test_circle_audit_lock.py
esac

case "$FILES" in *ui/issue_draw.py*|*ui/tests/test_issue_draw.py*|*coordinator/circle.py*|*coordinator/circle_open.py*)
    NOTE="  pre-commit: the issue picture and the close that draws it"
    # issue_draw.py is shipped code that circle.py runs at every live /close,
    # and the two halves of that wiring fail in opposite directions: the SCRIPT
    # can break at import time, and the CALL SITE can stop naming
    # "ui/issue_draw.py" as a literal, which is the only reason packaging/scan.py
    # ships the script and its man page at all.
    #
    # A CASE OF ITS OWN RATHER THAN A LINE IN THE ui/ CASE BELOW: this must also
    # fire for a commit that touches only coordinator/circle.py, which *ui/*
    # does not match. The redraw runs under `if args.live:`, so
    # test_circle_engine.py -- which forces --dry-run -- cannot reach it.
    run ui/tests/test_issue_draw.py
esac

case "$FILES" in *coordinator/working_set_manager.py*|*coordinator/tests/test_working_set_manager.py*\
|*coordinator/transcript_store.py*|*memory/issue_index.py*|*ui/issue_draw.py*\
|*memory/issue_prompt_projection.py*|*coordinator/circle.py*)
    NOTE="  pre-commit: the working set — the question, its register, the parsers, the pulls"
    run coordinator/tests/test_working_set_manager.py
esac

case "$FILES" in *ui/*|*coordinator/seam.py*|*coordinator/circle.py*|*coordinator/circle_open.py*\
|*coordinator/command_surface.py*|*coordinator/stream_redaction.py*|*coordinator/commands.py*\
|*coordinator/circle_rounds.py*)
    NOTE="  pre-commit: ui/, its rebinding surface, or a coordinator module covered only from ui/tests/"
    # SIX coordinator MODULES BESIDES seam.py ARE IN THIS TRIGGER because their
    # deepest executing cover lives in ui/tests/:
    #
    #   coordinator/circle.py            the Self> loop's verbs, driven by
    #                                    circle_test.py; the /issue ruling's
    #                                    STAGING (issue_cmds, the transcript echo)
    #                                    by circle_test.py, and its sandbox RECORD
    #                                    (commands_<OT>.toml at close) by
    #                                    test_circle_engine.py. Its live
    #                                    APPLICATION runs under no suite.
    #   coordinator/circle_open.py       the --resume transcript read and the
    #                                    same-minute overwrite refusal, since the
    #                                    2026-09-09 carve (the three --resume
    #                                    REFUSALS are circle.py's, executed by
    #                                    test_circle_argv.py since 2026-09-11).
    #   coordinator/command_surface.py   COMMANDS/PANE_OF, the pane-refusal
    #                                    contract, proved only by test_circling.py.
    #   coordinator/stream_redaction.py  what the circle pane redacts with.
    #   coordinator/commands.py          565 lines executed by circle_test.py,
    #                                    the register-isolation check among them
    #                                    (a dry-run write must never reach a live
    #                                    register); the IC_CODE block runs its
    #                                    dispatch and policy suites only.
    #   coordinator/circle_rounds.py     a real round, in circle_test.py and both
    #                                    engine suites; its own block runs the
    #                                    display suite.
    #
    # test_hook_template.py property 5 cannot see this class: it asks whether a
    # SUITE's own subject triggers it, never whether a MODULE's trigger reaches
    # the suites that cover it. Its seventh property covers the half that is
    # static -- a suite that NAMES a production path must be fired by it; the
    # half above, a suite that merely EXECUTES a module, needs the tracer
    # (audit-register 2026-09-11 #4).
    #
    # test_circling.py takes --fast (0-0.02s per line instead of 10-20s): the
    # delay exists to make a human watch real interleaving and tests nothing a
    # commit gate needs. It REWRITES ui/tests/outputs.txt every run, which is
    # safe because the record is deterministic -- same inputs.txt and same
    # dispatch behaviour, byte-identical file. If a commit DOES change dispatch
    # behaviour this leaves the regenerated outputs.txt unstaged afterwards;
    # that is the harness reporting what moved, not a failure.
    run ui/tests/test_circling_selftest.py
    run ui/tests/test_ui_main_loop.py
    run ui/tests/test_circle_engine.py
    run ui/tests/test_circle_engine_band.py
    run ui/tests/test_circling.py --fast
    run ui/tests/circle_test.py --fast
    run ui/tests/test_ticker_bridge.py
    run ui/tests/test_ticking_index.py
    run ui/palette.py --check
    run ui/tests/test_palette.py
esac

case "$FILES" in *parts/*|*coordinator/part_roster.py*|*coordinator/tests/test_part_roster.py*)
    NOTE="  pre-commit: the roster is read from the tree, so the tree can lie"
    # A missing or malformed part.toml shrinks the roster, and a part outside
    # the roster is ABSENT from the circle rather than faulty -- downstream,
    # indistinguishable from a part present and silent.
    #
    # circle_audit.py --selftest rides the parts/ case above and LOOKS like
    # this gate. It is register_gate.record_tree_verify: register schemas, line
    # endings, long_term.md dream entries. It never calls
    # part_roster.part_verify().
    run coordinator/tests/test_part_roster.py
esac

case "$FILES" in *coordinator/identity.py*|*coordinator/tests/test_identity.py*|*coordinator/prompt_build.py*|*parts/*)
    NOTE="  pre-commit: who Self is, or what a part's recorded context renders to"
    run coordinator/tests/test_identity.py
esac

case "$FILES" in *coordinator/part_add.py*|*coordinator/tests/test_part_add.py*)
    NOTE="  pre-commit: the part-lifecycle register touched"
    run coordinator/tests/test_part_add.py
esac

case "$FILES" in *coordinator/initialization.py*|*coordinator/initialization.toml*|*coordinator/tests/test_initialization.py*|*parts/*)
    NOTE="  pre-commit: the first-run dialogs, their validator, their verb"
    # PART_CONTEXT_DIALOG and /part-context-update: the ruled validator
    # (data_type/data_max/unique_in, empty always valid, echo-and-loop on
    # invalid), the statements-once flag, prefill semantics (Enter keeps,
    # `-` clears), and the dispatcher wiring. A parts/ edit can change what
    # the dialog asks.
    run coordinator/tests/test_initialization.py
esac

case "$FILES" in *coordinator/phase_clock.py*|*coordinator/tests/test_phase_clock.py*|*coordinator/docs/phase_clock.md*)
    NOTE="  pre-commit: the phase clock touched"
    run coordinator/tests/test_phase_clock.py
esac

case "$FILES" in *coordinator/circle_delta.py*|*coordinator/circling_verify.py*\
|*coordinator/command_suggest.py*|*coordinator/dependency_manager.py*\
|*coordinator/instrument_manager.py*|*coordinator/part_mid_term_project.py*\
|*coordinator/parts_prompt_projection.py*|*coordinator/project_stats.py*\
|*coordinator/prompt_show.py*|*coordinator/quote_as_lands.py*\
|*coordinator/remember_expand.py*|*coordinator/remember_prompt_projection.py*\
|*coordinator/ruling_migrate.py*|*coordinator/token_count.py*\
|*coordinator/topic_prompt_projection.py*|*memory/issue_index.py*\
|*coordinator/circle_history_manager.py*|*coordinator/circle_journal_manager.py*\
|*coordinator/circle_observation_manager.py*|*coordinator/circle_state.py*\
|*coordinator/dream_history_manager.py*|*coordinator/identity.py*\
|*coordinator/part_mid_term_manager.py*|*coordinator/part_roster.py*\
|*coordinator/proposal_group_manager.py*|*coordinator/proposal_manager.py*\
|*coordinator/redaction_manager.py*|*coordinator/remember_manager.py*\
|*coordinator/setting_manager.py*|*coordinator/topic_manager.py*\
|*memory/issue_schema.py*|*memory/issue_commands.py*|*packaging/scan.py*\
|*coordinator/ruling_sweep.py*|*coordinator/gitrepo.py*\
|*ui/ticker/lens_index.py*|*ui/ticker/ticking_index.py*\
|*memory/record_verify.py*|*memory/issue_gate.py*|*coordinator/circle_open_verify.py*\
|*work/tools/generate_block*.py*\
|*coordinator/tests/test_entry_points.py*)
    NOTE="  pre-commit: an untested-until-now __main__ entry point touched"
    run coordinator/tests/test_entry_points.py
esac

case "$FILES" in *coordinator/circle_delta.py*|*coordinator/tests/test_circle_delta.py*|*coordinator/docs/circle_delta.md*)
    NOTE="  pre-commit: the per-circle delta report touched"
    run coordinator/tests/test_circle_delta.py
esac

case "$FILES" in *coordinator/command_suggest.py*|*coordinator/tests/test_command_suggest.py*|*coordinator/docs/command_suggest.md*\
|*work/review/command_suggest_*)
    NOTE="  pre-commit: the report-only command recogniser touched"
    run coordinator/tests/test_command_suggest.py
esac

case "$FILES" in *coordinator/dependency_manager.py*|*coordinator/tests/test_dependency_manager.py*\
|*coordinator/docs/dependency_manager.md*|*coordinator/proposal_group_manager.py*\
|*coordinator/proposal_manager.py*|*coordinator/proposal_vetting.py*|*coordinator/proposal_suggestion.py*\
|*coordinator/docs/proposal_suggestion.md*|*coordinator/tests/test_proposal_suggestion.py*\
|*coordinator/command_suggest.py*|*coordinator/commands.py*|*coordinator/part_add.py*\
|*memory/issue_status.py*)
    NOTE="  pre-commit: the dependency map, or the chain that stages and vets it, touched"
    run coordinator/tests/test_dependency_manager.py
    run coordinator/tests/test_proposal_suggestion.py
esac

case "$FILES" in *coordinator/redaction_manager.py*|*coordinator/stream_redaction.py*|*coordinator/tests/test_redaction.py*)
    NOTE="  pre-commit: the redaction registry touched"
    run coordinator/tests/test_redaction.py
esac

case "$FILES" in *test_*.py*)
    # A COMMIT THAT ADDS A SUITE IS THE ONE COMMIT THAT CAN STRAND IT, so the
    # stray-suite detector triggers on every suite path, not just on the hook
    # module's own.
    #
    # ONLY test_hook_template.py runs here, deliberately. It is the detector;
    # the three heavier suites in the arm below stay keyed to the hook module
    # itself, so touching an ordinary suite does not drag in the whole set. A
    # commit touching BOTH gitrepo.py and a suite runs this one twice -- the arm
    # below names it too. That is accepted rather than factored out: the suite
    # is read-only and quick, and collapsing the two triggers would re-couple
    # the detector to the hook module, which is the coupling that strands suites.
    NOTE="  pre-commit: a suite touched — the stray-suite detector"
    run coordinator/tests/test_hook_template.py
esac

case "$FILES" in *coordinator/gitrepo.py*|*coordinator/git_hook_script.py*|*coordinator/tests/test_gitrepo_unstage.py*|*coordinator/tests/test_remote_classify.py*|*coordinator/tests/test_hook_template.py*|*coordinator/tests/test_hook_gate.py*)
    NOTE="  pre-commit: the hook's own module touched"
    run coordinator/tests/test_hook_template.py
    run coordinator/tests/test_gitrepo_unstage.py
    run coordinator/tests/test_remote_classify.py
    run coordinator/tests/test_hook_gate.py
esac

case "$FILES" in *packaging/sanitize.py*|*packaging/package.py*|*packaging/ignore.txt*)
    NOTE="  pre-commit: the ship set's own definition touched — re-checking the PII trigger reaches it"
    run coordinator/tests/test_hook_template.py
esac

case "$FILES" in *coordinator/instrument_manager.py*|*self/instruments.toml*|*coordinator/tests/test_instrument_manager.py*)
    NOTE="  pre-commit: the instruments register or its reader touched"
    # self/instruments.toml is in the trigger for the reason close_contract.toml
    # and turn_contract.toml are in theirs -- it is DATA a human edits, and
    # BLOCK 3's <profile> can be loosened without touching a .py. self/ never
    # ships, so an installed bundle has neither file and run() skips the suite.
    run coordinator/tests/test_instrument_manager.py
esac

case "$FILES" in *coordinator/circling_verify.py*|*coordinator/circling_contract.toml*|*coordinator/tests/test_circling_verify.py*|*docs/BNF.md*)
    NOTE="  pre-commit: the CIRCLING grammar or its guards touched"
    # docs/BNF.md is IN THE TRIGGER because the grammar lives there and the
    # guards live in the TOML beside the checker: circling_verify asserts the
    # two still name the same set, so an edit to EITHER can break the agreement
    # while touching nothing the other case matches.
    run coordinator/tests/test_circling_verify.py
esac

case "$FILES" in *coordinator/write_guard.py*|*coordinator/tests/test_write_guard.py*|*coordinator/circle_state.py*|*coordinator/tests/test_circle_state.py*|*coordinator/circle_close_verify.py*|*coordinator/tests/test_circle_close_verify.py*|*coordinator/close_contract.toml*|*coordinator/tests/test_close_postcondition.py*|*coordinator/transcript_store.py*\
|*coordinator/record_paths.py*|*coordinator/tests/test_record_paths.py*|*coordinator/part_roster.py*\
|*coordinator/circle_close.py*|*coordinator/circle_open.py*|*coordinator/circle.py*\
|*coordinator/group_manager.py*|*ui/tests/test_circle_engine_band.py*|*groups/*)
    NOTE="  pre-commit: a record-safety module touched"
    # THE CLOSE STEP, THE OPEN STEP AND THE DRIVER ARE HERE for the band's
    # isolation suite: "a band close touches nothing under groups/ifs/" is
    # decided in circle_close._dest_for() and the open step's group binding,
    # and that suite executes 99 lines of the one and 189 of the other
    # (audit-register 2026-09-11 #4). group_manager.py is here because that
    # suite opens a dry-run circle on a group /group-add scaffolded (2026-09-11)
    # and proves groups/ifs/ byte-identical after it.
    run coordinator/tests/test_record_paths.py
    run ui/tests/test_circle_engine_band.py
    run coordinator/tests/test_write_guard.py
    run coordinator/tests/test_circle_state.py
    run coordinator/tests/test_circle_close_verify.py
    run coordinator/tests/test_close_postcondition.py
esac

case "$FILES" in *coordinator/circle_open_verify.py*|*coordinator/open_contract.toml*|*coordinator/tests/test_circle_open_verify.py*\
|*coordinator/circle_open.py*|*coordinator/prompt_capture.py*|*coordinator/working_set_manager.py*|*coordinator/transcript_store.py*\
|*coordinator/circle_audit.py*|*coordinator/tests/test_circle_audit_open_report.py*)
    NOTE="  pre-commit: the open report, its writer, or a reader of it touched"
    # open_contract.toml is data a human edits, so it triggers on its own, as close_contract.toml
    # does. circle_open.py calls the verifier; prompt_capture, working_set_manager and
    # transcript_store are the readers it uses; circle_audit.py reads the report it writes.
    run coordinator/tests/test_circle_open_verify.py
    run coordinator/tests/test_circle_audit_open_report.py
esac

case "$FILES" in *coordinator/REGISTER_CLASS.py*|*coordinator/tests/test_REGISTER_CLASS.py*)
    NOTE=""
    run coordinator/tests/test_REGISTER_CLASS.py
esac

case "$FILES" in *coordinator/command_surface.py*|*coordinator/tests/test_dev_mode.py*)
    NOTE=""
    run coordinator/tests/test_dev_mode.py
esac

# A PERSON'S FIRST CIRCLE (R571): the open step decides it, the
# CIRCLE_HISTORY register's reader is the fact, initialization.toml holds the words.
case "$FILES" in *coordinator/circle_open.py*|*coordinator/circle_history_manager.py*\
|*coordinator/initialization.toml*|*coordinator/tests/test_first_circle_welcome.py*)
    NOTE="  pre-commit: the first circle's welcome touched — running real dry-run opens"
    run coordinator/tests/test_first_circle_welcome.py
esac

# What a part may put in a [proposed: ...] bracket lives on FIVE surfaces, and
# this is the one that holds them together. The trigger is deliberately wide --
# every input the suite reads -- because the drift it catches is between files
# that no single edit touches together. A group's layer is hand-written
# markdown, so the code and the rulebook would otherwise agree by memory alone.
case "$FILES" in *coordinator/command_surface.py*|*coordinator/annotations.py*\
|*coordinator/process_ifs.md*|*coordinator/process_band.md*|*coordinator/process_core.md*\
|*groups/*/group.toml*|*packaging/scaffold/coordinator/process_ifs.md*\
|*coordinator/tests/test_proposable_surfaces.py*)
    NOTE=""
    run coordinator/tests/test_proposable_surfaces.py
esac

case "$FILES" in *coordinator/prompt_capture.py*|*coordinator/tests/test_prompt_capture.py*|*coordinator/turn_contract.toml*|*coordinator/tests/test_turn_contract.py*)
    NOTE=""
    run coordinator/tests/test_prompt_capture.py
    # THE WIRE CONTRACT and the probe that proves it still refuses.
    # turn_contract.toml is DATA read by prompt_capture, so a commit that
    # touches only the TOML changes what every capture is checked against while
    # touching no .py at all -- it needs its own trigger or the contract could
    # be loosened silently.
    run coordinator/tests/test_turn_contract.py
    # AND the OTHER suite that calls verify(). test_llm_client.py builds a
    # capture and asserts `verify() == 0`, so a new assertion inside verify()
    # can break it. Cheap to run, and the exposure is the v45 lesson: a change
    # also needs its TRIGGER checked.
    run coordinator/tests/test_llm_client.py
esac

# THREE .claude/skills/ SUITES ARE WIRED DIRECTLY, fast and self-contained.
# test_pull_main.py stays an ALLOW entry in test_hook_template.py instead: it
# fires real commits inside temp git repos as part of its own assertions, which
# would mean every pull-main commit running the whole pre-commit battery nested
# inside itself.
case "$FILES" in *.claude/skills/install-package/install.py*\
|*.claude/skills/install-package/test_install.py*)
    NOTE="  pre-commit: the install skill touched"
    run .claude/skills/install-package/test_install.py
esac

case "$FILES" in *.claude/skills/my_commit/my_commit.py*\
|*.claude/skills/my_commit/test_my_commit.py*)
    NOTE="  pre-commit: the my_commit skill touched"
    run .claude/skills/my_commit/test_my_commit.py
esac

case "$FILES" in *.claude/skills/publish-package/publish.py*\
|*.claude/skills/publish-package/test_publish.py*)
    NOTE="  pre-commit: the publish skill touched"
    run .claude/skills/publish-package/test_publish.py
esac

case "$FILES" in *.claude/skills/scaffold-check/scaffold_check.py*\
|*.claude/skills/scaffold-check/test_scaffold_check.py*)
    NOTE="  pre-commit: the scaffold-check skill touched"
    run .claude/skills/scaffold-check/test_scaffold_check.py
esac

case "$FILES" in *coordinator/process_core.md*|*coordinator/process_ifs.md*\
|*coordinator/process_band.md*\
|*coordinator/process_core_prompt_projection.py*\
|*coordinator/tests/test_process_core_layers.py*)
    NOTE="  pre-commit: BLOCK 1's layers touched — the byte-identity probe runs"
    run coordinator/tests/test_process_core_layers.py
esac

case "$FILES" in *.claude/skills/run-inner-circling/driver.py*\
|*.claude/skills/run-inner-circling/test_driver.py*)
    NOTE="  pre-commit: the run-inner-circling driver touched"
    run .claude/skills/run-inner-circling/test_driver.py
esac
'''


# THE TWO BACKUP-PUSH HOOKS -- post-commit and post-merge.
#
# ONE GENERATOR, TWO HOOKS, ON PURPOSE. They do the identical thing and differ
# only in when git calls them and what they call themselves in a warning. Two
# hand-maintained copies would be worse here than anywhere: the two hooks are
# the disk-failure safeguard, so a divergence between them is silent by
# construction -- nothing reads a backup until something has already been lost.
#
# WHY post-merge EXISTS AT ALL. git never runs `post-commit` for a merge. It
# runs `post-merge`, for both merge shapes -- fast-forward and merge-commit
# alike. (Its one argument is 1 for a squash merge, 0 otherwise; we push either
# way, so it is not read.) A tree with only post-commit learns nothing from any
# merge, and the backup falls behind by exactly that much.
#
# THE TWO PUSHES, and why they are two. `--all` pushes BRANCHES ONLY, so the
# tags -- circle/<OT>, dream/<OT>, the per-circle provenance markers this backup
# exists to protect -- need a push of their own, and git refuses `--all --tags`
# in one command. NOT `--mirror`: a mirror propagates a local deletion to the
# backup disk, which is the one thing a disk-failure safeguard must never do.
# These two are additive -- a ref deleted here survives there.
def _backup_push_hook(kind: str, mark: str, when: str, prelude: str = "") -> str:
    """The body both backup-push hooks share. `kind` is the git hook name,
    used for the warning prefix; `when` completes "…after every <when>".

    `prelude` is shell that runs BEFORE the backup push, and exists so
    post-merge can carry the logbook fold without this becoming two
    generators. THAT PROPERTY IS LOAD-BEARING: these two hooks ARE the
    disk-failure safeguard, and a divergence between them is silent by
    construction, because nothing reads a backup until something has already
    been lost. Composing keeps one body; forking would not.

    ORDER MATTERS, and only one way round works. The fold makes a COMMIT, and
    a commit fires post-commit, which pushes to backup. Running the fold first
    therefore gets the fold onto the backup disk by way of its own hook; the
    push below then carries the merge itself. Reversed, the fold's commit
    would sit unpushed until the next commit happened to come along."""
    return f'''#!/bin/sh
{mark}
{prelude}
# Pushes every branch and tag to the local `backup` remote after every {when}.
# `backup` points at a bare repo on a different physical drive, so a disk
# failure on the working copy does not also take the history with it.
#
# THIS HOOK AND ITS TWIN ARE GENERATED FROM ONE FUNCTION in
# coordinator/git_hook_script.py -- _backup_push_hook(). Editing this file
# changes nothing that survives the next `--git-setup`; edit the generator.
#
# GIT RUNS post-commit FOR A COMMIT AND post-merge FOR A MERGE, and never one
# for the other -- not even for a merge commit, which looks like a commit and
# is not one to a hook. Both are needed; neither covers the other.
#
# NEVER FAILS THE {kind.split('-')[1].upper()}. A backup push that could block would turn
# "the backup drive is unplugged" into "I cannot work right now" -- the wrong
# failure mode for a safety net. Warns and exits 0 regardless.
#
# Silent on success, loud on failure -- a hook that prints every time trains a
# reader to stop reading its output.
#
# THE TWO PUSHES ARE SEQUENCED, NEVER CHAINED. Joined by `&&`, a single
# unpushable BRANCH withholds every TAG -- and the tags are the RECORD.
#
# `git push --all` IS NOT ATOMIC -- every ref it can advance, it advances, and
# it still exits non-zero for the one it cannot. So a rejection means "one ref
# is stuck", never "the backup got nothing". Both pushes run unconditionally
# and the warning fires if EITHER failed.
if git remote get-url backup >/dev/null 2>&1; then
    {{
        git push backup --all --quiet
        _all_rc=$?
        git push backup --tags --quiet
        _tag_rc=$?
    }} 2>/tmp/inner-circling-backup-push.log
    if [ "$_all_rc" -ne 0 ] || [ "$_tag_rc" -ne 0 ]; then
        echo "  {kind}: WARNING — backup push to 'backup' remote failed" \\
             "(branches rc=$_all_rc, tags rc=$_tag_rc)." >&2
        echo "  {kind}: see /tmp/inner-circling-backup-push.log" >&2
    fi
fi
exit 0
'''


# BOTH MARKS MOVE TOGETHER, because both hooks are one generator. A bump on one
# alone would install a fixed body beside an unfixed one, and that divergence
# is silent -- which is the property _backup_push_hook()'s docstring exists to
# protect.
POST_COMMIT_MARK = "# inner-circling post-commit v5"
POST_COMMIT_FAMILY = "# inner-circling post-commit v"
POST_COMMIT = _backup_push_hook("post-commit", POST_COMMIT_MARK, "commit")

POST_MERGE_MARK = "# inner-circling post-merge v6"
POST_MERGE_FAMILY = "# inner-circling post-merge v"

# THE LOGBOOK FOLD RUNS HERE.
#
# `coordinator/assign_ids.py --write` is the one step in the branch-and-merge
# mechanism that a human would otherwise have to remember, and forgetting it
# leaves logbook_ruling_verify.py refusing master. No PRE-commit hook can catch
# it -- a clean `git merge` creates a commit without firing pre-commit -- but
# git runs post-merge for exactly the event that leaves a fold owing.
#
# EVERY GUARD IS IN THE PYTHON, NOT HERE. `--commit` refuses off master and
# refuses inside a worktree (`.git/hooks/` is SHARED with every worktree, so
# `git merge master` run inside one fires this same hook, in a tree where
# `.venv` does not exist and master is not checked out). A guard written in
# this file would be a guard no probe could reach; in assign_ids.py,
# test_assign_ids.py holds it -- and that suite is the only thing that can,
# since nothing else runs at the moment ids move.
#
# IT CANNOT FAIL THE MERGE. git ignores post-merge's exit status, and the merge
# has already happened by the time this runs. A failure here is loud and leaves
# the folded logbooks in the working tree, uncommitted.
_FOLD_STEP = '''
# --- the logbook fold, before the backup push (see _backup_push_hook) ---
if [ -x .venv/Scripts/python.exe ]; then
    if ! .venv/Scripts/python.exe coordinator/assign_ids.py --commit; then
        echo "  post-merge: assign_ids --commit FAILED." >&2
        echo "  post-merge: the fold may be WRITTEN and UNCOMMITTED — check" >&2
        echo "  post-merge: 'git status', fix what the gate named, commit." >&2
    fi
fi
'''

POST_MERGE = _backup_push_hook("post-merge", POST_MERGE_MARK, "merge",
                               prelude=_FOLD_STEP)


def _sh_n(body: str, label: str, log) -> bool:
    """`sh -n` over one hook template. True if it parsed, False if `sh` is
    absent (the validator's absence is not evidence of a broken template).
    Raises GitError on a real parse failure.

    Split out 2026-08-19 when POST_MERGE joined PRE_COMMIT: two templates
    now need the same gate, and a second copy of it is the shape that lets
    one of them quietly stop being checked."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False,
                                     encoding="utf-8", newline="\n") as f:
        f.write(body)
        tmp = f.name
    try:
        try:
            r = subprocess.run(["sh", "-n", tmp], capture_output=True,
                               text=True, timeout=30)
        except OSError:
            log("warn", f"sh not on PATH — {label} template syntax check skipped")
            return False
        if r.returncode != 0:
            raise GitError(f"{label} template fails sh -n — refusing to "
                           f"install a hook the shell cannot parse:\n"
                           f"{(r.stderr or r.stdout).strip()}")
        return True
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _hook_syntax_check(log, pre_commit: bool = True) -> None:
    """`sh -n` over the PRE_COMMIT template, before any install. Raises
    GitError on a parse failure — installing a hook the shell refuses
    turns every future commit into a hard failure (v38's own origin
    story). If no `sh` is on PATH (a non-Git-Bash console), the check
    is SKIPPED WITH A WARNING rather than failed: the validator's
    absence is not evidence the template is broken, and git-for-Windows
    ships the sh that will actually run the hook.

    `pre_commit=False` CHECKS POST_MERGE ALONE, for the caller that is
    not going to install a pre-commit hook. Added 2026-08-24, and found
    by running --git-setup in a real bundle rather than reasoning about
    it: the execution layer below RUNS the template against this repo,
    and in a tree without coordinator/tests/ that run fails on the
    template's own first line, so system_git_hooks_ensure() raised here — before
    reaching the guard that exists to skip the install. Validating a
    program nobody is about to install, by running it, is the check
    getting in front of its own decision."""
    # POST_MERGE gets `sh -n` and NOTHING MORE, deliberately. The execution
    # layer below runs a template for real against this repo; running
    # POST_MERGE for real would push to the backup remote as a side effect of
    # a syntax check. A validator with a side effect is not one.
    _sh_n(POST_MERGE, "POST_MERGE", log)
    if not pre_commit:
        return
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False,
                                     encoding="utf-8", newline="\n") as f:
        f.write(PRE_COMMIT)
        tmp = f.name
    try:
        try:
            r = subprocess.run(["sh", "-n", tmp], capture_output=True,
                               text=True, timeout=30)
        except OSError:
            log("warn", "sh not on PATH — hook template syntax check skipped")
            return
        if r.returncode != 0:
            raise GitError(f"PRE_COMMIT template fails sh -n — refusing to "
                           f"install a hook the shell cannot parse:\n"
                           f"{(r.stderr or r.stdout).strip()}")
        # EXECUTION LAYER. `sh -n` is not enough on its own: a rendering defect
        # can be syntactically VALID overall and still execute prose as a
        # command, announcing itself only at run time and only on stderr (the
        # checks' own output goes to stdout). So when NOTHING is staged, run the
        # template for real against this repo and require exit 0 with an EMPTY
        # stderr. With something staged the run would exercise real gates on a
        # mid-edit tree, so the layer is skipped with a warning rather than made
        # to lie.
        rc_staged, staged = system_git_run("diff", "--cached", "--name-only",
                                read_only=True)
        if rc_staged == 0 and not staged.strip():
            try:
                x = subprocess.run(["sh", tmp], cwd=str(_G.ROOT),
                                   capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   timeout=300)
            except OSError:
                log("warn", "sh vanished mid-check — execution layer skipped")
                return
            if x.returncode != 0 or x.stderr.strip():
                raise GitError(
                    "PRE_COMMIT template misbehaves when RUN (exit "
                    f"{x.returncode}; stderr below) — refusing to install:\n"
                    f"{x.stderr.strip() or x.stdout.strip()}")
        else:
            log("warn", "files are staged — hook template execution check "
                        "skipped (sh -n still passed)")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def system_git_index_lock_read(root: "pathlib.Path | None" = None) -> "list[pathlib.Path]":
    """Every index lock git holds right now: this repository's, and each worktree's. Read off
    the filesystem with no git call, so it answers the same on a machine with no git binary.

    A PATHSPEC COMMIT HOLDS ONE THROUGH ITS PRE-COMMIT HOOK, and it is the only kind that does.
    Measured 2026-09-10 by listing .git from inside each hook of a scratch repository:
    `git commit -- <paths>` — every commit R377 allows, and every close commit, since
    system_git_paths_commit() passes --only — holds index.lock (in a worktree,
    .git/worktrees/<name>/index.lock) beside a next-index-<pid>.lock; a plain `git commit`
    holds none, and neither does post-merge. So an empty answer does not mean no hook is
    running, and _hook_write() is the route that covers the rest."""
    git = pathlib.Path(root if root is not None else _G.ROOT) / ".git"
    if not git.is_dir():
        return []
    held = [git / "index.lock", *sorted(git.glob("worktrees/*/index.lock"))]
    return [p for p in held if p.is_file()]


def _commit_in_flight_refuse(log) -> bool:
    """True, having said why, when a commit holds an index lock. See system_git_hooks_ensure()."""
    held = system_git_index_lock_read()
    if not held:
        return False
    names = []
    for p in held:
        try:
            names.append(p.relative_to(_G.ROOT).as_posix())
        except ValueError:
            names.append(str(p))
    log("fail", f"a commit is in progress ({', '.join(names)} is held), so no hook was "
                f"rewritten — a hook changed while it runs checks something other than what "
                f"it began. Re-run --git-setup when the commit finishes. If no git is running, "
                f"the lock was left by a crash: report it rather than deleting it.")
    return True


def _hook_write(p: pathlib.Path, body: str, log) -> bool:
    """Write one hook WHOLE — a temp file beside it, made executable, then os.replace() — and
    never in place. False, having said why, when the hook is running and cannot be replaced.

    `sh` reads a script by byte offset as it executes, so a rewrite in place hands a running
    hook the new file's bytes from the old file's position. Measured 2026-09-10 on both of this
    machine's volumes, C: (NTFS) and D: (exFAT): rewritten in place, a running script executed
    the new file's next line; replaced, it finished its own — and Windows refused the replace
    outright with PermissionError, because sh holds the file open. That refusal is the signal:
    a hook in use is left exactly as it was. On POSIX the replace succeeds and the running shell
    keeps reading the file it opened.

    Not atomic_write.record_atomic_write(): a hook needs its execute bit set on the temp BEFORE
    the rename, or a commit starting in between finds a hook git declines to run."""
    tmp = p.with_name(f".{p.name}.tmp{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        try:
            tmp.chmod(0o755)          # a no-op on Windows; git for Windows runs it anyway
        except OSError:
            pass
        try:
            os.replace(tmp, p)
        except PermissionError:
            log("fail", f"the {p.name} hook is running right now, so it was not replaced — "
                        f"Windows will not replace a file a program has open. Re-run "
                        f"--git-setup when the commit finishes.")
            return False
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return True


def system_git_hooks_ensure(log) -> bool:
    """Install the pre-commit and post-merge hooks if absent, and UPDATE AN
    OUT-OF-DATE ONE. Never overwrites a hook this project did not write — a
    human may have put one there deliberately.

    IT REFUSES WHILE A COMMIT IS RUNNING (R537). `sh` reads a hook by byte
    offset as it runs, so a hook rewritten under a running commit executes the new file's
    bytes from the old file's position. Two routes, because git leaves a trace for one kind of
    commit only — see system_git_index_lock_read():

        an index lock is held    refused before anything is checked or written, and again
                                 after the syntax check, which can run the template for minutes
        the hook file is open    every hook is written whole, by _hook_write(), and Windows
                                 refuses to replace a file a running sh has open

    Returns False on a refusal, so --git-setup stops there; True otherwise, including the two
    cases that install nothing on purpose — no hooks directory, and a hook that is not ours.

    A VERSION MARK THAT IS NEVER COMPARED IS A COMMENT, and reporting alone
    lets the hook on disk and the template here drift into two programs
    agreeing about their name. So an existing hook of this family at a
    different version is REPLACED, and the replacement is announced rather
    than done quietly.

    SYNTAX-GATED: the template is `sh -n`-checked before any install. A
    rendering defect — a scripted edit's literal two-character "\\n" inside
    a case pattern is the shape it takes — produces a hook that FAILS every
    commit rather than running its checks, so a template sh cannot parse is
    refused here, loudly, instead of written into .git/hooks.

    THE BACKUP HOOKS ARE DONE FIRST, ON PURPOSE. The pre-commit block below
    is a chain of early returns — the FIRST of which is the ordinary case, a
    pre-commit already at this mark. Calling _ensure_backup_hooks at the tail
    would have installed them only on a tree that happened to be missing its
    pre-commit hook, i.e. almost never, while reading like it ran always."""
    # THE DISCRIMINATOR IS READ FIRST because the syntax check below RUNS the
    # pre-commit template -- see _hook_syntax_check's `pre_commit` parameter.
    # The backup hooks are installed and validated either way; they are
    # recipient-safe (no `backup` remote, no push) and cost a tree without
    # suites nothing.
    if _commit_in_flight_refuse(log):
        return False
    dev_tree = (_G.ROOT / "coordinator" / "tests").is_dir()
    _hook_syntax_check(log)
    d = _G.ROOT / ".git" / "hooks"
    if not d.is_dir():
        log("warn", "no .git/hooks directory; skipping pre-commit hook")
        return True
    # Asked again: the syntax check can run the whole template, and a commit may have begun.
    if _commit_in_flight_refuse(log):
        return False
    if not _ensure_backup_hooks(d, log):
        return False
    # THE BATTERY INSTALLS EVERYWHERE, AND `run`/`quiet` ARE WHY. The template
    # names 72 scripts by path and a distributed bundle ships 6 of them -- the
    # probes and the operator-only checkers are not part of the product. A
    # script this tree does not have is SKIPPED; one it HAS still fails the
    # commit when it fails.
    #
    # RULED BY THE OPERATOR, 2026-08-26: a recipient's circle closes are gated
    # by the gates that ship, because a corrupted register is worth catching as
    # the circle commits rather than at the next open. transcript_store's
    # circle_commit() runs through this same hook at every /close, so anything
    # unconditional here reaches a stranger's circles, not just their commits.
    if not dev_tree:
        log("note", "coordinator/tests/ is absent — this is a distributed "
                    "bundle. The pre-commit battery IS installed and runs "
                    "the gates that ship (the corruption sweep, the issue "
                    "gate, the self-check, the practices check, the "
                    "projection); the probe suites and dev-only checkers "
                    "are skipped one by one, not by refusing the commit.")
    p = d / "pre-commit"
    if p.is_file():
        text = p.read_text(encoding="utf-8", errors="replace")
        if HOOK_MARK in text:
            log("ok", "pre-commit hook installed (gate runs on any issues/ commit)")
            return True
        if HOOK_FAMILY in text:
            old = next((l.strip() for l in text.splitlines()
                        if HOOK_FAMILY in l), "an earlier version")
            if not _hook_write(p, PRE_COMMIT, log):
                return False
            log("did", f"replaced {old!r} with {HOOK_MARK!r} — an out-of-date "
                       f"hook of ours runs different checks than this file "
                       f"describes")
            return True
        log("warn", f"a pre-commit hook exists and is not ours; leaving it alone "
                    f"— add the gate call by hand, see {HOOK_MARK}")
        return True
    if not _hook_write(p, PRE_COMMIT, log):
        return False
    log("did", "installed .git/hooks/pre-commit — the gate now runs on any "
               "commit touching issues/")
    return True


# The two backup-push hooks, in the order they are installed. A list rather
# than two calls: adding a third git hook to this safeguard should be one
# entry, not another copy of the installer.
BACKUP_HOOKS = (
    ("post-commit", lambda: POST_COMMIT, lambda: POST_COMMIT_MARK,
     lambda: POST_COMMIT_FAMILY),
    ("post-merge", lambda: POST_MERGE, lambda: POST_MERGE_MARK,
     lambda: POST_MERGE_FAMILY),
)


def _ensure_backup_hooks(d: pathlib.Path, log) -> None:
    """Install or update .git/hooks/post-commit and .git/hooks/post-merge —
    the backup pushes, one per git event that can move a ref.

    SAME THREE-WAY DECISION AS pre-commit, and for the same reason: ours at
    this mark is left alone, ours at a DIFFERENT mark is replaced (a version
    mark that is never compared is a comment — v8's lesson), and a hook this
    project did not write is never touched.

    NOT MERGED WITH pre-commit's block: these answer a different question
    (has the backup got this? / does this commit pass?) and fail differently
    (never blocks anything / blocks the commit). pre-commit also has a
    syntax-and-execution gate these do not need — running one of these for
    real would push to the backup remote as a side effect of a check.

    False when a hook in use could not be replaced — _hook_write() has said which."""
    for name, body, mark, family in BACKUP_HOOKS:
        if not _ensure_one_backup_hook(d, name, body(), mark(), family(), log):
            return False
    return True


def _ensure_one_backup_hook(d: pathlib.Path, name: str, body: str, mark: str,
                            family: str, log) -> bool:
    p = d / name
    if p.is_file():
        text = p.read_text(encoding="utf-8", errors="replace")
        if mark in text:
            log("ok", f"{name} hook installed (backup push)")
            return True
        if family in text:
            old = next((l.strip() for l in text.splitlines()
                        if family in l), "an earlier version")
            if not _hook_write(p, body, log):
                return False
            log("did", f"replaced {old!r} with {mark!r}")
            return True
        log("warn", f"a {name} hook exists and is not ours; leaving it alone "
                    f"— add the backup push by hand, see _backup_push_hook() "
                    f"in gitrepo.py")
        return True
    if not _hook_write(p, body, log):
        return False
    # SAY WHAT IS TRUE FOR WHOEVER IS READING IT. This module ships, and a
    # recipient has no `backup` remote -- these hooks no-op without one -- so a
    # line naming what the backup disk now knows would name a thing they do not
    # have. packaging/shipped_references.py is the gate for exactly that.
    log("did", f"installed .git/hooks/{name} — a `backup` remote, if this clone "
               f"has one, now learns about this event")
    return True
