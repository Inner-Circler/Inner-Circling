# COMMAND_SUGGEST.PY(1)

## NAME
command_suggest.py — recognise the coordinator actions a circle's prose suggests, and REPORT them.
Nothing is staged, vetted or executed. Ruled R569 (2026-09-15).

## SYNOPSIS
    python coordinator/command_suggest.py --ot <OT> [--group <name>] [--json]
    python coordinator/command_suggest.py --file <transcript.md> [--out <report.json>] [--json]

    import command_suggest as CSG
    CSG.command_suggest_run(ot, transcript_text, say=say)          the close-time step
    CSG.command_suggest_catalogue_read() · command_suggest_classes_read()
    CSG.command_suggest_system_render(cat) · command_suggest_user_render(transcript, topic)
    CSG.command_suggest_derive(transcript, topic, client=) · command_suggest_reply_parse(text, cat)
    CSG.command_suggest_report_render(ot, result) · command_suggest_report_write(path, ot, result)

## DESCRIPTION
The operator, 2026-09-15: *"I'd like for this system to identify possible coordinator actions
across all classes. Identification does not mean execution; it means discriminating across and
among the classes, understanding their roles and methods, and recognising prose that suggests the
use of those methods."* Three landings were put to him — a staged PROPOSE row, a report, an
in-circle nudge — and he chose the report: *"lets go with B, I want to see what it finds."*

ONE MODEL CALL over a closed circle's transcript. Its system prompt is the COMMAND SURFACE read by
class: for each ruled object class (coordinator/object_classes.toml, help_system's reader) the
class's own description — its ROLE — then each of its write verbs with the description /help
shows — its METHODS. The reads (`-list`, `-view`, `-show`), the circle controls (/round /pass
/close /abort /status /help), the installation's tooling classes (settings, redact-alias, group,
prompt) and two synonyms (/issue-status-update, /issue-apply) are left out: prose about a
person's life never asks for them. 22 verbs on 2026-09-15; the catalogue is DERIVED, so a verb
added to COMMANDS is in scope the day it lands. The user message is the numbered statements —
/issue-evidence-list's numbering, so a `statement` in the reply is a number Self can cite.

THE REFERENTS travel with the transcript (2026-09-15, the operator's second question: *"would
they be resolved in a circle context, or does that need more work?"*). command_suggest_referents_read()
reads, and only reads, the bound group's live registers the way their own list verbs do: every
issue with its id, status and label; the open issue-relationships; the open topics; the
observations, practices, better options and parts each numbered as `/observation-list`,
`/practice-list`, `/better-option-list` and `/part-list` number them. Those numbers are
POSITIONAL and shift when a row goes, so the report says when it read them. The model is told
to resolve an id or list number against this section and to keep a placeholder only where
nothing matched, saying so. A register that cannot be read is an empty list and a note, never
a refusal. `--referents <json>` substitutes a file in the same shape for a rehearsal against a
dialog that is not this tree's; the report notes the substitution.

STAGED AT A LIVE CLOSE (R570, 2026-09-15). `command_suggest_run(stage=True)` —
inter_circle.py's call, and nothing else — also stages each line as a pending proposal for the
next checkpoint (`command_suggest_stage`). A `/propose-add X` stages X. A `/part-add` is staged
only from Self's own words (R483). A line said twice is one row. A list number becomes its stable
handle: a practice's BP- id, a part's directory. The kind is "command" when the part classifier
admits the line whole, else "suggestion" when proposal_suggestion.py can run the verb. A line
whose reply names an earlier item in `depends_on` waits on that item's proposal, with the token
its minted id fills; a line holding a placeholder nothing fills is not staged. A line this circle
already ruled is not staged again: a row of this circle already approved, denied or superseded (a
pending one is reused), or a command Self typed in the room. Each suggestion in
the JSON then carries `staged`, `duplicate_of` or `not_staged`. A hand run and the `--file`
rehearsal never stage.

THE REPLY is a JSON array, one object per suggestion: `verb`, `line` (the command as Self would
type it, arguments filled from the prose, an unknowable id left as its placeholder), `speaker`,
`statement`, `quote`, `confidence` (high/medium/low), `why`. The parser FAILS OPEN: an unparseable
reply is no suggestions and one note; an object naming a verb outside the catalogue, or whose
line does not start with its verb, is dropped with a note. The report prints the kept lines
numbered, each with its warrant, then the notes; work/logs/command_suggest_<OT>.json carries the
same, marked `report_only`. Gitignored beside delta_<OT>.json — a report, not the record.

THE OCCASION. A fresh install's circle (2026-09-15_0945) discovered and named a part, Self said
"I wish to add the part", and nothing created it: the verb is Self's alone (R483), parts are not
told it, and six registers carried the intent without one line saying `/part-add`. This is the
line, offered.

## MAIN
`--ot <OT>` reads the bound group's `circles/circle_<OT>.md` and writes the report to work/logs/.
`--file <path>` reads any transcript in the coordinator's shape, prints the report, and writes it
only where `--out` says (otherwise to work/sandbox/logs/, which nothing files). `--json` prints the
JSON too. Exit 0 with a report, 1 without one, 2 on usage.

## COMMAND-LINE ARGUMENTS
    --ot <OT>          a closed circle's open time
    --group <name>     the group whose circle --ot names (record_paths.group_set)
    --file <path>      a transcript file, any location
    --out <path>       where --file's JSON report goes
    --json             print the JSON report after the text

## DEPENDENCIES
    command_surface (CS)      COMMANDS — the verbs and the descriptions /help shows
    help_system               object_classes() — the ruled class table (late import)
    commands                  statement_read() — /issue-evidence-list's numbering (late)
    transcript_store          circle_transcript_parse (late, in command_suggest_run)
    llm_client                stream_call_once, AUX_MAX_TOKENS (late, in derive)
    record_paths (_RP)        ROOT, SANDBOX, record_dir, group_set

## EXTERNAL FILES
Read: the transcript named. Written: `work/logs/command_suggest_<OT>.json` (or `--out`).
At a live close (`stage=True`) it also writes one pending row per staged line to the bound group's
`self/proposals.toml`, through proposal_manager. A hand run and `--file` write nothing under groups/.

## NETWORK ACCESS
One Messages API call per run, through llm_client. NOT CAPTURED: R412/R413 admit the /close
calls that write the record, and this writes none. `client=` injected is used as given, so a
suite reaches no network.

## HUMAN I/O
`say` (print by default; inter_circle's own under a close). Every line of the report goes
through it. Nothing is asked.

## OPERATION

### `command_suggest_run(ot, transcript_text, *, say, client, out)`
    try {
        parse the transcript (circle_transcript_parse — strict; a malformed one raises);
        derive (one call); say the rendered report; write the JSON where `out` says, else
        work/logs/command_suggest_<OT>.json; say where; return the result
    } except anything { say one line "command suggestions: not produced — <why>"; return None }
    NEVER RAISES. inter_circle.py calls it after SYNTHESIS, under `if live`, so a close is
    never held up by a report.

### `command_suggest_catalogue_read()`
    for each COMMANDS row, in order:
        skip a control head, a synonym head, a read method, a tooling class;
        else keep {head, form (one line), cls (help_system's longest-prefix rule), description}

### `command_suggest_reply_parse(text, catalogue)`
    find the outermost [ ... ]; json.loads; if not a list -> ([], [one note])
    for each item: not an object -> note; verb not in catalogue -> note; line not starting
    with verb -> note; else keep, with confidence coerced to high/medium/low and statement to int

## BUGS
None known. From the first run (work/review/command_suggest_2026-09-15/, the every-operation
dialog): at AUX_MAX_TOKENS (4,000) the reply stopped at max_tokens before one visible character —
the thinking took the whole ceiling — and the report said so and nothing else; at
SUGGEST_MAX_TOKENS (12,000) all 22 catalogued verbs were recognised, 22 lines for 26 statements,
ids it could not know left as placeholders and said so in `why`, and one statement that suggested
four operations yielded four lines. With the referents added, 12,000 cut the reply mid-array after
twenty complete objects — the ceiling is 32,000 now, and a cut array is SALVAGED to its last
complete object with a note rather than discarded. The confidence word is the model's own;
nothing here calibrates it.
