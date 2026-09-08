# CIRCLE_DELTA(1)

## NAME

circle_delta.py — what one circle changed, across the registers, in both segments: the circle itself, then its inter-circle processing.

## SYNOPSIS

    python coordinator/circle_delta.py                 the newest closed circle
    python coordinator/circle_delta.py --ot <OT>       one circle, by open time
    python coordinator/circle_delta.py --series        part memory over every closed circle
    python coordinator/circle_delta.py --json          the payload instead of the report

## DESCRIPTION

A read-only reporter over the record. For one closed circle it gathers the two segments — the circle (statements, annotations, proposals, /issue commands, spend) and its processing (dreaming's remember rows, synthesis's register writes, the mid_term refresh) — and renders them as one report whose centerpiece is a per-part memory table: spoke, short_term bytes, dreamt (with salience and chain length), and mid_term size before and after the refresh. It reads registers through their own modules' path and table constants, anchors the two segments on the machine commits tagged `circle/<OT>` and `dream/<OT>`, and classifies every path in those commits against their writers' own declared sets, naming anything off-matrix under UNEXPECTED.

Behind the `circle_stats` setting (default on; `CIRCLE_STATS` in this file is the constant), a live `/close` calls `circle_delta_at_close()` to print this report and file its payload as `work/logs/delta_<OT>.json` — a gitignored memo, re-derivable in full. When the setting is off, `/close` stays silent and a by-hand run prints without filing.

Three doctrines it inherits rather than invents: the close report is the read gate (no `close_<OT>.json`, no report — a partial transcript is well-formed, so this is the one test that cannot read a circle in flight); dream evidence is one-directional (a tag or marker means processed; absence means only "no evidence here"); and the SILENT flag is B54 made visible per circle — a part that spoke but has no well-formed short_term took dreaming's silent path, and the report says so with the backfill-first repair order.

## MAIN

    read the command-line arguments after the script's own path;
    if (--series was given) then {
        for every work/logs/close_*.json, oldest first, collect that circle's delta
            (a circle that cannot be collected becomes an error row, not a crash);
        if (--json) then { print the list as JSON } else { print the compact series table };
        exit 0;
    }
    take the OT from --ot, else the newest close report's;
    if (there is no close report at all) then { say so; exit 1 }
    try to collect the delta;
    if (the OT has no close report) then { print the refusal, which names circle_state.py; exit 1 }
    if (--json) then { print the payload as JSON } else { print the rendered report };
    if (the circle_stats setting is on) then { file work/logs/delta_<OT>.json and name it };
    exit 0;

## COLLECT

    refuse unless work/logs/close_<OT>.json exists (DeltaUnavailable);
    find the circle anchor {
        ask git for the tree's own stamped tag first (gitrepo.system_git_tag_name_read knows the lab stamp, R245),
        then plain circle/<OT> as a READ fallback — a worktree shares the main record but
        tag_name stamps it lab/, so without the fallback a worktree run would call every
        processed circle unprocessed;
        if (no tag answers) then { fall back to the commit that ADDED the transcript —
            R130's signature, a close whose commit silently failed }
    }
    find the dream anchor the same way; processed is "tag", else "marker"
        (work/logs/dream_<OT>.json), else "no evidence";
    parse the transcript for the topic, Self's statement count (cmd-echoed graph rulings and
        Coordinator notes excluded) and per-part counts {
        if (the transcript is missing or unparseable) then { fall back to the close report's
            per-part counts, with zero Self statements and no annotation counts }
    }
    count [remember: …], ask and [recall: …] brackets over the raw transcript bytes;
    read proposals, the circle's commands_<OT>.toml, and spend_<OT>.json;
    for every part in the roster {
        take statements, bytes and status from the close report;
        flag SILENT when it spoke and the short_term is absent or unwell (B54's shape);
        read parts/<p>/remember.toml: an id-bearing row citing this circle is the DREAMT
            record (salience, chain length via remember.chain_of); an id-less one is a live
            [remember: …];
        if (the dream commit carries parts/<p>/mid_term.md) then { sizes before and after are
            that commit's parent blob and its own blob } else { the live file's size, marked
            unchanged }
    }
    count the rows each register gained for this circle — circles/circle_history.toml and
        circles/circle_observation_log.toml, self/topics.toml (with its LONG_TERM CANDIDATE
        prefix) and self/best_practices.toml — noting `missing` for any the reporter cannot
        find, because absence and a quiet circle both otherwise read as 0/0;
        and whether the dream commit touched self/self.md;
    classify each machine commit's paths against its writer's declared set;
    if (a tagged commit is a merge) then { report that instead of classifying — a machine
        commit is single-parent by construction, so a merge there is itself the finding }

## FILES

READ: `work/logs/close_<OT>.json` (the gate and the per-part sizes), `circles/circle_<OT>.md`, `circles/commands_<OT>.toml`, `work/logs/spend_<OT>.json`, `work/logs/dream_<OT>.json`, `parts/*/remember.toml`, `parts/*/mid_term.md`, `self/proposals.toml` (via proposal_manager.py), the four synthesis registers under `self/`, and git objects via read-only subprocess calls (`rev-list`, `log`, `show`, `cat-file`, `rev-parse`), each of which degrades to "no evidence" on any failure.

WRITTEN: `work/logs/delta_<OT>.json` only — through atomic_write, only when the `circle_stats` setting is on. Gitignored beside `dream_<OT>.json`; the registers, the machine commits and the close report are the record, and a re-run regenerates it.

NETWORK: none. No model calls, ever.

## DEPENDENCIES

settings (the `circle_stats` read), part_roster, identity, transcript_store (whose annotations import needs `memory/` on sys.path — this module adds it, the same hop circle.py makes), remember, proposals, annotations, recall_index, gitrepo (tag_name only), atomic_write. Every project import is function-local and guarded; tomllib (tomli on 3.10) reads the registers raw.

## HUMAN I/O

Prints the report (or JSON) to stdout; every rendered line stays within 116 characters. `circle_delta_at_close(ot, emit)` is the `/close` hook: it emits through the caller's own channel, honours `circle_delta_is_enabled()`, and FAILS OPEN — a reporting fault must never fail a close.

## BUGS

Annotation counts are regex matches over the raw transcript bytes, so an ask- or remember-shaped bracket inside quoted text counts as one. The UNEXPECTED classifier judges against today's write matrix: a historical machine commit that legitimately carried a since-retired file (part_relationships.toml, retired 2026-08-22) is flagged, which is honest about the matrix but not about the moment. `--series` reads every register once per circle rather than once, which is quadratic-ish and fine at this corpus's size.
