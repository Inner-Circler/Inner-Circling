# CIRCLING(1)

## NAME

circling.py — how you sit down with your parts. The two-pane window where an inner circle happens.

## SYNOPSIS

    python ui/circling.py --live               a real circle
    python ui/circling.py                      a practice circle, nothing real is written
    python ui/circling.py --help               every option

## WHAT THIS IS FOR

Internal Family Systems starts from a simple observation: you are not one voice. Different parts of you carry different jobs — one keeps watch, one grieves, one wants to be good, one wants to be left alone — and they rarely get to speak in the same place at the same time. Most of the time they take turns running things without ever being heard.

An **inner circle** is that place. Seven parts are given a seat, a topic, and permission to speak in their own voice, and **you** sit among them as Self — not as another part, and not as a manager, but as the one who can listen without being taken over.

The aim is not to fix anything in one sitting. It is **greater health, by way of better options discovered through uncovering and understanding issues** — and uncovering and understanding are the early stages of something that keeps going as long as you keep bringing attention to it. A circle is one sitting's worth of attention.

This program is the room. It gives each part its turn, keeps the record, and makes sure what was said is still there tomorrow.

## THE TWO PANES

The window is split.

    the CIRCLE pane, above     where the conversation happens. The parts speak here.
                               You speak here, as Self, by typing and pressing Enter.
    the COMMAND pane, below    where you attend to the room rather than talk to it —
                               asking what is going on, ruling on something a part
                               proposed, ending the circle.

`Tab` moves between them.

They are separate for a reason that matters in practice: parts answer on their own schedule, and a statement can arrive while you are halfway through typing. If the conversation and your controls shared one line, an arriving statement would land on top of what you were saying. Because they are two panes, it cannot. Nothing you type is ever disturbed by something arriving.

Scrolling up freezes what you are reading — new arrivals leave that pane alone until you press `End` to come back to the live edge. You never have to hurry to finish reading. Scrolling is the number pad's job, with NumLock off; the arrow keys work the line you are typing, and `Up` brings back what you last typed in that pane, up to three entries, `Down` the way back.

## OPENING A CIRCLE

    python ui/circling.py --live

The program checks its own house first — that the files holding your parts' memories are whole, and that it can reach the service the parts think with. **Nothing is written until both pass.** A circle that cannot start properly leaves no trace at all rather than a half-empty record.

**The parts think through Anthropic's service, and that needs a key of your own.** If none is set, the window does not open: it prints what the key is, how to get one, the file it goes in, how to keep it safe, and the link, and stops. Practising (below) needs no key, and says the same in five lines.

Then it asks you two things.

**What is this circle about?** You can name specific issues to put in front of the room, or answer with nothing and let the circle be open. Naming issues is not narrowing the conversation — it is telling the parts what has your attention right now.

**What is the topic?** One line, in your own words. This is what every part is given as the reason you have all sat down.

Then the parts arrive, and the first round begins.

## BEING IN THE CIRCLE

Type in the circle pane and press Enter to speak as Self. That is all there is to it — what you type goes to every part, exactly as you wrote it, and stays in the record.

A few things are worth knowing:

**You do not have to speak every round.** `/round` lets the parts continue without you. Some of the most useful material arrives when parts are responding to each other rather than to you.

**Each part waits its turn, and no part speaks twice in a row.** A part may make at most two statements between your own, so no single voice can take the room over while you are quiet.

**The parts are answering each other, not a snapshot.** Each one sees everything said so far, including what was said moments ago in the same round.

**The first round is blind.** Parts open without seeing one another, so five parts establish their own stance before anyone is influenced. It costs a little repetition at the start; it buys you five genuinely independent openings.

**Statements are short** — a hundred words at most. A part that cannot say it briefly is usually saying more than one thing.

## SPEAKING TO THE ROOM ABOUT THE ROOM

Some things you say are not part of the conversation but instructions about it. Those are typed in the lower pane. `/status` tells you where the circle is. `/help` lists what you can type. When a part has proposed something — a name for an issue, a way the circle should work — you will be asked to approve it, deny it, or leave it for later; that question waits in the lower pane until you answer it, and it will not be lost while you attend to the conversation.

Two things you type in the circle pane are worth naming because they are not commands, they are acts:

**Remembering.** A part can ask to keep something — a phrase, an image, a commitment — and carry it into future circles. You can do the same for yourself.

**Quoting a part back to it.** When you repeat a part's own words to it, that is not just conversation. It is a form of recognition, and the system treats it as one.

## ENDING

`/close` ends the circle properly. Each part that spoke writes a short note about what the circle was for it; the record is saved and committed; and then — this is the part that takes a while — each part **dreams**: it revisits what it has just been through and lets its own sense of itself move. After that, one pass looks at the circle as a whole and writes what it noticed about the room.

**Expect the close to take several minutes**, and to keep working after the conversation itself is over. That work is not bookkeeping. It is how anything said today reaches the part that says something tomorrow.

`/abort` ends a circle without any of that. The conversation is kept, but nothing about any part changes. Use it when a circle went somewhere you do not want carried forward — or when you were only trying things out.

## PRACTISING FIRST

    python ui/circling.py

Without `--live`, nothing real happens: no part actually thinks, every one of them answers with a placeholder, and every file that gets written goes to a scratch area rather than to your record. It is there so you can learn the window — the panes, the turns, the commands — without spending anything or moving anything. It needs no key.

## WHAT IS KEPT

    the transcript          everything said, in order, exactly as said
    each part's short note  written at close by every part that spoke
    what each part carries  updated when the part dreams, after the circle

Your record is yours and stays on this machine. Circles accumulate: the eighth circle is different from the first because the parts in it have been to seven.

## IF SOMETHING GOES WRONG

**A part goes quiet.** A silent part is allowed — not every part has something to say about every topic — and the record distinguishes a part that chose silence from one that failed.

**The circle will not open.** It will tell you which file it is unhappy about and what to do. It refuses rather than opening anyway, because a circle built on a damaged memory produces a part that has quietly lost part of itself, and nothing downstream can tell that apart from the part having changed.

**You are not sure whether a circle is still running.** Ask, rather than guessing — see `coordinator/docs/circle_state.md`.

## GOING FURTHER

This program is the front door. Underneath it, `coordinator/circle.py` is the same circle without the two panes — the single-pane way in, and everything the circle actually does. If you want the full mechanism — how each part's prompt is assembled, what happens at every step of an open and a close, every option available — read **`coordinator/docs/circle.md`**. Everything described above is that program, wearing a window.

Related pages:

    coordinator/docs/circle.md          the circle itself, in full
    coordinator/docs/circle_state.md    is a circle open right now?
    coordinator/docs/record_verify.md the check that runs before a circle opens
    coordinator/docs/circle_close_verify.md    what happens at close, and how it is verified
    coordinator/docs/part_mid_term_manager.md        how a part's sense of itself is distilled

## OPTIONS

A bare run opens a circle. Every option below except `--selftest`, `--no-color` and `--help` is passed through to the circle itself, `coordinator/circle.py`, in any position; `coordinator/docs/circle.md` has each in full.

    --live          make it real: the parts actually think, and the record is
                    your own. Default: off — dry-run, nothing real is
                    written. With no API key set, the window does not open:
                    the key's explanation prints, exit 2 (R546).
    --parts <dir>,<dir>,...
                    which parts to seat. A reduced roster is for testing —
                    the parts left out are absent and stay unaware of the
                    circle. Default: every member of the default group.
    --group <name>  open on a named group instead of --parts — a different
                    roster, not a reduced one. Mutually exclusive with
                    --parts. Default: the default group.
    --recall-arm off|delivered|withheld
                    whether a part may search its own past record, a local
                    index read that costs no model call. `off` answers a
                    part's search privately without running it; `withheld`
                    computes and logs the packs without delivering them.
                    Default: delivered (on).
    --seed <n>      fix the order parts are polled within a round, so a test
                    repeats. No effect on what the parts say. Default: unset —
                    omit for real circles.
    --yes           skip the confirmation prompt for a reduced live roster.
                    Default: off — the prompt is asked.
    --resume <OPEN_TIME>
                    reopen an unclosed circle where it stopped: no topic
                    prompt, no opening round. Refused unless the transcript
                    round-trips byte-for-byte. Default: unset — a new circle.
    --selftest      check the program without needing a terminal. Worth running
                    before trusting a session. A mode, not a toggle. Default: not
                    set — the window opens.
    --no-color      plain text. This program's own flag; never passed through.
                    Default: off — color is used whenever the terminal
                    supports it and the NO_COLOR environment variable is
                    unset.
    --dev[=true|false]
                    open with dev mode ON — forwarded to circle.py's own --dev.
                    Turns on the DEV-table verbs, the help hierarchy, and the
                    coalesce / pre-warm / opening-round progress lines.
                    Default: off. Hidden from --help here as it is in
                    circle.py's; the manual is where it is documented.
    --help, -h      the full list.

## A NOTE ON THE NAME

The shape — a conversation pane above, a command pane below — was called "dual pane" while it was being built, and that name still appears in the design documents. The program was a test rig before it was the front door; it became the way in on 2026-08-23. If you meet the old name `dual_pane.py` in an older note, it is this.
