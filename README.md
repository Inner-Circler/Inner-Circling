# Inner Circling

An Internal Family Systems inner circle, run as a multi-part simulation
across parts you describe. Circles are driven by a local Python 
"coordinator" calling an AI LLM API directly.

Licensed under Apache-2.0 — see `LICENSE` and `NOTICE`.

---

## What this is

Parts hold a conversation with each other and with **Self**, who is you.
A circle is one local process: each part is a stateless API call to an
AI LLM which replies. The coordinator holds the single canonical transcript 
of each circle and evolves each part's view using it.

There is no agent runtime, no inter-agent messaging, and no file written
by anything but the coordinator process itself.

Over time the record accumulates: transcripts, a per-part distillate that
feeds the next circle's prompts, and a graph of **issues** where every
piece of evidence is a verbatim quote checked against the transcript it
came from. `docs/overview.md` is the long account.

## What this is not

**This is a method someone built for himself and shared.** Read the
following as the plain-language half of §7 and §8 of the licence, which
disclaim warranty and liability.

- NOT therapy, and not a substitute for it
- NOT a clinical or diagnostic instrument
- NOT supervised by anyone
- NOT reviewed, validated, or trialed
- NOT a product — no support, no warranty, no promises

The parts are language models given a written identity. They will sound
coherent, warm, and certain. **They model your own parts, produced by
interpretation, and they can be wrong** Nothing a part says is you or even
an observation about you; it is an AI statement generated. You may or
may not find it useful.

Free of charge, offered as-is, by one person who is not a clinician.

## Safety

**Nothing here is a safety net.** No part of this system notices distress,
escalates, or reaches a human being on your behalf. The registers under
`groups/ifs/self/` arrive empty by design, and nothing is watched or
monitored. Earlier versions of this file implied otherwise; they were
wrong.

**The parts do carry crisis lines, and one may offer you them.** The
rulebook every part reads — `coordinator/process_core.md` — names **988**,
texting **HOME** to **741741**, and **findahelpline.com**, and tells each
part that safety content is real and additive, never a substitute for what
the circle is doing. The first two are United States services. If you are
elsewhere, the directory is the one that will reach you, and you may want
to replace those lines with your own country's: that file ships as yours
to edit.

If you are in crisis, or approaching one, stop and use a human service:
your local emergency number, or a directory such as `findahelpline.com`.
An AI circle is not the place for it.

Some further judgement, offered rather than enforced:

- Treat your parts gently. Parts speak about hope and trauma because that 
  is what they mirror. A circle can reach things that deserve care.
- Do not run a circle to settle a decision. The room converges. That 
  tendency is a known risk, and it is why this is not a decision procedure.
- Take what surfaces a trusted and capable person, ideally.

## Privacy — what stays, and what leaves

**Your name never leaves the machine, including to the LLM.** You
are asked your name strictly to personalize the feel in circles.

**You can hide names on screen without touching the record.** The circle
pane has a redacted view: names, places and organisations you list are
shown as stable opaque ids while the transcript on disk, and what the
model receives, stay exactly as written. `/redact-alias-add`,
`/redact-alias-update`, `/redact-alias-delete` and `/redact-alias-list`
keep the list, in `groups/ifs/self/redaction.toml`; part names are never
eligible. The view starts OFF: turn it on with `/settings-update
redact_view yes`, and `/settings-list` shows its current value.
It is presentation only — a screen someone else might see — not privacy
from the model, which is the paragraph below.

**The records are yours and they stay on your disk.** Every transcript,
every part record, every issue node is a plain file in this directory.
Nothing uploads them. **Nothing is published to GitHub or anywhere else**
— and that is enforced, not merely intended: `coordinator/gitrepo.py`
classifies every destination before it will commit, refuses anything that
is not a disk attached to this machine, never adds one on its own, and
fails closed on anything it cannot classify. See "git is not GitHub"
under Configure for what the distinction is.

**One thing does leave: the model calls.** To run a live circle the
coordinator sends, to Anthropic:

- each part's assembled system prompt:
  -- the rulebook
  -- your issue graph as it is projected for that circle,
  -- that part's own distilled identity
  -- **any first-run answers that part renders.** The dialog at your
     first open asks about you; a part sends back only the answers it
     declares a `render` sentence for. The shipped Soul declares
     four -- the year you were born, your sex at birth, your race, and
     where you were raised -- and the shipped Child six: how many
     siblings you had, whether you were home schooled, whether you
     enjoyed school, your favourite things to do, whether you were
     bullied, and whether you made much music or art. They are
     rewritten into that part's own voice ("My human was raised in
     ...", "I grew up with ... sibling(s).") and travel in every prompt
     for as long as they are recorded. Every question is optional and
     blank is a complete answer; `/part-context-list` shows exactly
     what is held, and `/part-context-clear <part>` erases it.
- the circle transcript:
  -- every statement, including everything you have typed as Self
  -- your name is never sent -- `given_name` and `preferred_name`
     deliberately declare no `render`, so they stay on this machine and
     name your console prompt only
- at every live `/close`, the calls that turn a circle into memory:
  -- dreaming: the transcript, and each part's own statements, its
     summary of the circle and its newest memory
  -- synthesis: the transcript, what each part kept, the proposals you
     confirmed, the circle's previous notes, and
     `groups/ifs/self/self.md` in full -- whatever you write about
     yourself there travels at every close
  -- the refresh: each part's own record, to rebuild its distilled
     identity
  -- the grouping of proposals: the ones still pending

That is the whole mechanism — the cloud has no memory of a part, so its
context has to be sent on every call. What you say in a circle goes to
the model provider. Their retention and training policies govern what
happens to it there; read them, and decide before you type.

`--dry-run` sends nothing at all and needs no key.

Two more things worth knowing:

- files are not encrypted. They are plain text on disk. Anyone 
    with your account, your machine, or your backups can read them. 
    Turn on full-disk encryption if that matters.
- .env holds your API key. It is gitignored, never printed, never 
    committed, and never in a distributed bundle. See more below.

## What arrives, and what does not

**The mechanism ships. Nobody's inner life does.**

SHIPS
  - coordinator/                  the running system
  - memory/                       the issue graph's code, and the
                                  record's persistence layer: the
                                  corruption gate, the register gate,
                                  the transaction class
  - ui/                           the two-pane interface (the windowed
                                  Ticker flavor, ui/ticker/, is NOT in
                                  this bundle)
  - docs/overview.md              how it works — the long account
  - docs/what-this-is.md          a description written for readers outside
                                  the project, with what is BUILT and what is
                                  DESIGNED marked separately
  - docs/licensing.md             the licence (Apache-2.0) and the attribution
                                  it asks for
  - docs/circling_probes.md       draft questions Self may ask at a circle's
                                  open. Wired into nothing — reading them
                                  changes no file and no rule
                                  These four are the whole of docs/ that a
                                  bundle carries; the rest of the live
                                  tree's docs/ never ships
  - coordinator/process_core.md   the rulebook every part reads (the universal layer;
                                  coordinator/process_ifs.md is the IFS group's own)
  - groups/ifs/parts/soul/, groups/ifs/parts/child/     two seed parts
  - groups/ifs/group.toml         the group's own descriptor — its presence makes the folder a
                                  group (R468): roles, reserved roles, the first-run order, the
                                  role whose answer names the console, its rulebook layer

ARRIVES EMPTY, WITH A README — under groups/ifs/, the IFS group's own folder; a second
group gets a folder of the same shape beside it (groups/<name>/). Which groups a bundle
carries is a list (packaging/groups.toml on the publishing side) — this one carries IFS;
a bundle may carry any one or more, and the program resolves whatever it finds
  - groups/ifs/circles/           transcripts land here, and the four
                                  one-per-circle registers sit beside them
  - groups/ifs/issues/            the issue graph
  - groups/ifs/self/              Self's registers
  - work/prompts/                 captured prompts
  - work/logs/                    open and close reports
  - work/graph/                   the issue graph's PICTURE, redrawn at every
                                  close whose graph moved; the command pane
                                  prints the path
  - work/manifests/               stays empty here: nothing in this bundle
                                  writes it, as its own README says
  - work/circle_audit/            the record audit's own lock and snapshots
  - work/nightly/                 the staging root a write passes through
                                  before it lands. Nothing is scheduled — the
                                  name is historical and its own README says
                                  so

NEVER SHIPS
  - any transcript, any part, any issue, any remember, any proposal 

Most of these carry a `README.md` saying what gets written there, by
what, and what not to hand-edit. **Empty is correct**: a system
that has not held a circle has no transcripts, and one that has held none
is not broken.

## Requirements

- Python                 3.10 or newer. Developed on 3.10; the `tomli`
                         backport is in requirements.txt for it.
- git                    OPTIONAL. Everything runs without it; what it
                         adds is a version history on your own disk, and
                         with it the ability to undo. NOT GitHub — no
                         account, no upload, no internet. See "git is not
                         GitHub" under Configure.
- an Anthropic API key   for live circles. Dry runs need none.
- a terminal             one that understands ANSI escapes. Windows
                         Terminal, or any modern terminal on macOS or
                         Linux. NOT a shell requirement — see below.

**Windows is the tested platform.** Every example below uses Windows
paths; on macOS and Linux the interpreter is `.venv/bin/python` and the
rest of each line is the same.

**No particular shell is required.** Nothing here invokes PowerShell,
`cmd`, `bash` or any shell for its own work — the commands are plain
`python <script>` and run identically from whichever prompt you use. The
one place a shell appears is git's own hooks, and git supplies that
itself.

What the two-pane interface *does* need is a real terminal, because it
reads keys one at a time and paints the screen directly. It carries a
backend for each platform:

- Windows       msvcrt, plus a call that turns on ANSI escape handling
                for the older conhost console. Windows Terminal already
                has it on.
- macOS/Linux   termios + select, xterm escape sequences for the arrow
                and paging keys.

**The POSIX backend is real but lightly travelled**: 
it exists so the interface can be smoke-tested off Windows, and
it is not a fully exercised target. Expect the arrow/paging keys to be
the place a less common terminal emulator disagrees. Everything beneath
the interface — the coordinator, the registers, the gates — is plain
Python with no platform-specific code at all, and every path it builds is
built with `pathlib`, never spelled with a separator.

**One thing genuinely works only on Windows, and it is better to know
than to discover.** If you keep a git history and want to mirror it to a
second disk, the check that decides whether a destination is a disk on
this machine is implemented with a Windows API. Off Windows it can answer
only "unknown", and it fails closed — so it refuses every destination,
including a perfectly local one:

/Volumes/Backup/Inner-Circling.git returns volume is UNKNOWN as only 
FIXED and REMOVABLE are on this machine.

That refusal is the safe direction and it costs you only the mirror: with
**no** destination configured, which is how a fresh install arrives,
commits work normally on any platform. Copy the directory to your backup
disk instead, or use your system's own backup — the whole record is plain
files in one folder, which is what makes that enough.

## Install

### 1 · The files

**There is no package to install, and that is deliberate.** This is not a
library you import — it is a working directory that becomes your own
record. The code reads and writes `groups/<name>/{parts,self,issues,circles}/`
— `groups/ifs/` for the group you receive — and `work/` *beside itself*: every path is derived from where
the modules sit on disk. Installed into a Python packages directory, your
transcripts and your parts' identities would be written there too, among
the libraries, where nothing expects to find them and an upgrade would
step on them.

So you take a copy of the directory and keep it. Either way works:

- with git         
```
  git clone https://github.com/Inner-Circler/Inner-Circling.git
  cd Inner-Circling
```

- without git      
```
  on the repository page, Code -> Download ZIP,
  then unzip it somewhere you will keep
```

**Downloading from GitHub is not the same as putting anything on
GitHub.** It is how you get the files, once. Nothing in this system ever
sends your record back — see "git is not GitHub" under Configure, and
"Privacy" above.

**Put it where it belongs before you start.** This directory grows into
the record itself, so choose a location you back up and would not clear
out — not `Downloads`, not a temporary folder. Moving it later is fine;
nothing stores an absolute path.

### 2 · Python itself

Get it from **python.org/downloads**, or from your system's own package
manager. Version 3.10 or newer.

**pip comes with it.** Every installer from python.org bundles pip, and
the commands below use it — there is nothing separate to fetch. On Linux
some distributions split it out; if `python3 -m pip` says the module is
missing, install your distribution's `python3-pip` package.

While installing on **Windows**, check this one box:

```
[x] Add python.exe to PATH
```

Tick it. Without it, `python` is not a command your terminal knows, and
every line below fails at the first word. If you have already installed
without it, re-run the installer and choose *Modify*.

On **macOS**, the `python3` that ships with the system is not meant for
this; install a current one from python.org or with `brew install
python`. On **Linux**, your package manager's `python3` is fine.

Check what you have:

On Windows:
```
python --version
```
On macOS / Linux:
```
python3 --version
```

Confirm 3.10 or newer.

### 3 · A virtual environment, in this directory

**Everything this project needs goes into `.venv`, and nothing goes
anywhere else.** A virtual environment is a private copy of Python's
package area belonging to this folder alone — installing here cannot
disturb another project or your system Python, and deleting `.venv`
undoes the install completely.

On Windows:
```
python -m venv .venv      # be patient; silently takes 30 secs
.venv\Scripts\python -m pip install -r requirements.txt
```

On macOS / Linux:
```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Five packages arrive, all named in `requirements.txt`: the Anthropic
client, `python-dotenv`, `tomli` / `tomli-w` to read and write the TOML
the registers are kept in — `tomli` only on Python 3.10, which has no
`tomllib` of its own — and `fastembed`, which serves a part's
`[recall: ...]` search of its own past. **A circle makes no network call
except to the model provider, with one exception you can see coming:** your
first live circle fetches `fastembed`'s embedding model (~65 MB) into a
local cache, once, in the background while the parts warm up; after that
it is offline. Nothing else
is fetched, then or later.

Every command in this file begins `.venv\Scripts\python` for exactly this
reason: it names the interpreter that has those packages. Plain `python`
is a different interpreter and will not find them.

## Configure

### Where to get an API key

Circles run on Claude, and the model calls are made by this program on
your machine, directly to Anthropic. You need your own key.

1. go to console.anthropic.com and create an account. This is the
   DEVELOPER console, a different thing from a claude.ai subscription,
   and a claude.ai plan does not include API access
2. add credit under Billing. Usage is pay-as-you-go, billed per circle.
   See "What a circle costs" below
3. API keys -> Create Key. Copy it when it is shown; it is shown ONCE
   and cannot be read again

**Treat it as a password.** Anyone who has it can spend your credit.
Keep it out of screenshots and out of anything you share.

### Put it in `.env`

Create a file named exactly `.env` at the top of this directory. In
that file, put your key and preferred first name (NEVER shared):

```
ANTHROPIC_API_KEY=sk-ant-...
IFS_USER_NAME=<the name shown at your prompt>
```

No quotes, no spaces around the `=`. `.env` is listed in `.gitignore`,
so it is never committed, never printed, and never included in anything
you pass on.

*On Windows, some editors silently append `.txt`. If a run says the key
is missing, turn on file extensions in Explorer and check the file is
`.env` and not `.env.txt`.*

**The two lines above behave differently, deliberately.** For
`ANTHROPIC_API_KEY`, a shell variable of the same name **wins over the
file** — `.env` is not read for a value the environment already has. That
is worth knowing if you ever rotate a key and nothing seems to change.
`IFS_USER_NAME` is the opposite: it is read from `.env` **only**, never
from the environment, so editing the file always takes effect on the next
run with nothing else to clear. The key taught that lesson; the name was
built not to repeat it.

`IFS_USER_NAME` sets the name the console greets you by. **It does not
change the record** — the transcript writes `[Self]:` for everything you
say, always. It is the *fallback*: once the first-run dialog records a
preferred name against the Soul, that answer wins and editing `.env`
changes nothing. `coordinator/docs/identity.md` gives the full resolution
order and the Windows-specific reason this variable exists at all.

### git is not GitHub, and GitHub is not needed or used here

Worth saying plainly, because the two words travel together and only one
of them is involved.

- git    a program that runs ON YOUR MACHINE and keeps a history of
         a folder. It saves versions locally. It uploads nothing, and
         it needs no account, no sign-up, and no internet connection.
- GitHub a WEBSITE that hosts copies of git histories for other people
         to see. A separate company, a separate decision, and no part
         of this.

**Nothing here uploads your record anywhere, and it cannot be made to by
accident.** `coordinator/gitrepo.py` classifies any destination before it
will commit, and refuses everything that is not a disk attached to this
machine — `https://`, `http://`, `ssh://`, `git://`, `user@host:path`,
`\\server\share`, a mapped network drive, and anything it cannot
classify at all. It fails closed: unrecognised means refused. It also
never adds a destination on its own.

So if you use git here, you get **version history on your own disk** and
nothing else. There is no account to make and no site to visit.

### git is optional, and worth having

**Everything runs without it.** Circles open, close, dream and synthesise
in a directory that was never `git init`ed; the record is written the
same either way, and phase 2 records that a circle was processed in
`work/logs/dream_<OT>.json` instead of a git tag.

What you give up by skipping it is **undo**. Writes here are atomic — a
multi-file write either lands whole or not at all — but only a history
makes a write *reversible after the fact*. A dreaming pass that puts
something wrong into a part's identity is one command away from being
undone if you kept a history, and is not undoable if you did not.

If you want it, set an identity first — if git does not already have one:

```
git config user.name  "Your Name"
git config user.email "you@example.com"
```

Then bootstrap the repository — idempotent, adds only what is missing,
never rewrites history, and never adds a destination to upload to:

```
.venv\Scripts\python coordinator\circle_audit.py --git-setup
```

It installs the pre-commit battery, and says so: the gates that ship —
the corruption sweep, the issue gate, the self-check, the practices check,
the projection — run whenever a commit touches the record (the line-endings
check runs at every commit), and the project's own probe suites, which are
not part of this bundle, are skipped one by one rather than by refusing the
commit. The gates below are the same checks, run by hand.

Check what will be used, changing nothing:

```
.venv\Scripts\python coordinator\identity.py
.venv\Scripts\python coordinator\gitrepo.py --identity
```

## Verify

**Use these commands to confirm your install is healthy.** 

```
  .venv\Scripts\python ui\circling.py --help
  .venv\Scripts\python ui\circling.py --selftest  # expect all PASS 
```

Optional free dry run — no network, no key needed

```
  .venv\Scripts\python ui\circling.py --circle
```

**Dry run is the default HERE** — `--circle` passes `--dry-run` to the
coordinator for you unless you ask for `--live` by name. (`coordinator/circle.py`
run on its own REFUSES a bare invocation since R360: it wants `--live` or
`--dry-run` spelled out.) `--live` may sit anywhere on the command line;
anything else after `--circle` is forwarded to the coordinator unchanged.

## Run

**The two-pane interface is the way in.** 
  
This is how you start a real live circle:

```
  .venv\Scripts\python ui\circling.py --live --circle
```

**The user interface has two panes*

- The upper 'circle' pane is where you speak and listen in circle dialog.
- The lower 'command' pane is where you administer circle records.
- Type TAB to switch the active pane.
- Type `/help` in the circle pane, or `help` in the command pane, to see
  what can be done there — in the circle pane a bare word is said to the
  room, so the verb needs its slash.

**Your first live run asks you some questions.** 

A fresh installation ships the Soul and the Child with universal 
identities and no particulars. A short dialog opens in the command pane. 
It asks a few questions per part, and then one about something thing that 
feels troubling. Answering is optional; empty skips it, and it states what 
it will record and where before it asks. **Skipping is not declining** — a
round you leave entirely empty writes nothing and the dialog returns at
your next live open. Once answered it stops asking; this command re-runs
it whenever you want:

```
/part-context-update <part>   # re-enter that part's personal answers (at cmd>)
```

**Every live run begins with up to two questions** -- the first only
once you have a live issue to choose from.

Do you have specific issues to focus on today? ('?' to review) _

'?' lists the live issues, numbered; answer with those line numbers,
or 'all', or blank for none.

As you circle, you have the option of tracking "issues": things that
trigger you, cause distress, and indicate places where loving care 
might be helpful.  You can return to those issues in the future by
selecting them here.  The easy answer here is nothing, a bare 'enter'.

And the second question:

CIRCLE topic (blank = open): _

Enter a few words about what is on your mind:

"Alcoholism sucks"

**Your circle has started**

Before you are asked to speak, every part speaks once on that topic,
each without seeing the others -- the opening round. A part with
nothing to add answers `[pass]`. Then you are at the circle prompt.
Type to speak as Self:

"I'd like to talk about drinking. I don't handle it well when people 
are drinking, even just moderate casual drinking."

In a few moments you will hear back (an actual reply):

"[Child]: Something in me goes quiet and watchful when you say that. 
Not thinking-quiet — the kind where I'm just... waiting to see what 
happens next. Like when the air in a room changes and you don't know 
why yet, you just know to be still.  I don't have a reason for you. 
I don't have the story that explains it. I just know that "people 
drinking" and "unpredictable" got wired together somewhere very early, 
before I had words for it. It's not about whether this glass, this 
person, this room is actually safe. It's older than that.  I don't 
need you to fix this right now. I just wanted to say it's real, it's 
mine, and it doesn't need to make sense to be true."

So... just talk.  Explore feelings about drinking with your Child!

You should be aware that your Child knows nothing about you beyond
what you have told it.  It knows a lot about people, and as you
say more about yourself it learns about you, memorizing what you
tell it and mirroring your parts.

The "Soul" part is a placeholder for 'who I was born as, and the 
world I was born into'. Unless you ask questions about that, or
address "Soul: ..." directly, it is unlikely to speak.

Each part gets two turns to say something before you speak again;
then they will wait for you. Speaking spends the first of those two,
because your statement is followed by a round straight away. So
`/pass` or `/round` gives them the second one, and a further `/round`
after that is quiet — the circle tells you who is holding, and they
keep holding until you speak again. The exception is a part you have
addressed by name since it last spoke: it may answer even at its
limit.

**About remembering**

A lot of remembering happens automatically.  On occasion there
may be things you want to recall in future circles. You can
enter, in the circle pane, an annotation like this:

```
[remember: <text>]
```

To prevent misfires, such as if you were to say "I remember 
when ..." in the circle, the syntax must be exactly as shown. 

The system will record that, and `/remember-list` at the cmd>
prompt hands it back whenever you ask -- nothing brings it back
on its own. You can manage such memories -- type `help remember`
at the cmd> prompt.

**About proposals**

When circling reveals something important — like another issue, a
practice worth keeping, or a better option for you — this is how a
part registers it for dedicated attention:

```
[proposed: <command>]
```

The command is any of those you can see by typing "help propose"
in the command pane. You can stage the same command yourself
there, with `/propose-add <command>`; a part writes it here in the
circle pane in this way. One cannot be staged that way: a part's
`/issue-evidence-add` offers the statement its bracket rides in, and
the command pane has no statement to offer. To attach one yourself,
type `/issue-evidence-add nNNNN <stmt#> "why"` at cmd> during the
circle — `/issue-evidence-list` numbers the circle's statements. It
is recorded as your words, not sent to the parts, and applied at
close.  Proposals are "staged";
at the end of the circle you are asked if you approve of any
proposals. You can approve (the proposal affects the system,
opening an issue or adding a practice, etc.), deny (the proposal
is forgotten), or skip (you'll be asked again when the next circle
opens).

A part cannot propose a new PART. Adding one is yours alone,
with `/part-add` at the command pane — but parts are told about
any new part or issue, and they will begin to accumulate related
memories.

As with remember, the syntax is strict.

**Closing the circle**
 
`/close` ends it properly. `/abort` stops without closing: the transcript
is kept and its path is printed, but no part writes a closing reflection
and none of the after-close processing runs.

When you close a circle, the system looks at records and learns
more about you. It may take some time to finish... just let it run.

See `coordinator/README.md` for more information.

## What a circle costs

Parts run on Claude Sonnet unless you change the `model` setting
(`/settings-list` shows it and its current value; `/settings-update model
<name>` changes it, and it takes effect at the next circle). The
coordinator prints a token and 
cost meter at the end of every circle, computed from the rates in
`coordinator/llm_client.py` — **read that file rather than trusting a
number written here**, since published rates change and this line 
will go stale.

Measured on the original seven-part installation, and recorded in
`coordinator/README.md`:

```
a three-part test round   about $0.30
a full circle, 15 rounds  roughly $3-4
```

A fresh install starts with two parts, so expect less. The largest lever
is prompt caching: the shared blocks of every part's prompt are cached
for an hour, and the meter reports the hit rate alongside what the same
circle would have cost without it.

## Closing a circle is not free, and not instant

`/close` does more than write the transcript:

```
1  proposals that say the same thing are grouped, and you are asked to rule
   on every proposal still pending
2  if the issue graph moved — by those rulings, or by any typed during the
   circle — its picture is redrawn; the command pane prints the path,
   under work/graph/
3  each part is asked for its summary of the circle, and those are written
4  the close report is verified, and the whole circle is committed to git,
   with the report its open wrote
5  THEN dreaming runs for every part, one circle-wide synthesis after it,
   and each part whose record moved has its distilled identity rebuilt
```

Step 5 makes model calls of its own **after** the transcript is already
committed, so a close takes noticeably longer than the writing alone and
adds to the circle's cost. That is the loop that turns circles into a
part's memory; without it a part's identity never moves.

If it fails it writes a report under `work/logs/`, prints the command to
re-run it, and exits non-zero. Staging is all-or-nothing, so a failed run
wrote nothing and the re-run is clean.

## Parts ... and the ones you will add

**A circle starts at two.** `groups/ifs/parts/soul/` and
`groups/ifs/parts/child/` arrive with
an identity and no history — the substrate and the root of wonder,
structural in the IFS model rather than particular to any one person.

**Nothing is missing.** Every other part is yours to discover and name,
and a system that has not met them yet is not incomplete — it is at the
beginning. Parts arrive as they surface, which is how they arrived in the
circle this came from.

`/part-add` at the cmd> prompt opens the dialog that creates one: a
Tag, a description, and the files a part needs to be spoken to.
`coordinator/process_core.md` §New {members} is the rule it follows — the
heading reads literally like that in the file; `{members}` becomes "parts"
only when a prompt is assembled. **A part
is never created without Self's explicit agreement**, and that rule is in
the rulebook every part reads.

`/part-retire` is the other door, and it is not a delete. **The system
respects records and history:** no command removes a part's record. A
retired part leaves every circle, prompt and search from then on; its
folder stays exactly where it is, its name stays its own, and what it
said in past circles stays in the transcripts, marked retired. The parts
are asked not to speak of it, and any bracket that names it is refused.
To bring one back, rename `parts/<name>/retired.toml` to `part.toml` and
put the name back on `roles` in the group's `group.toml`, both by hand —
there is no command for that, on purpose.

`docs/overview.md` covers the shape a circle takes and what happens when
one closes, in plainer terms than this file.

## Where to read next

```
docs/overview.md              the parts, and what each is for
coordinator/README.md         how to run a circle, step by step
coordinator/process_core.md   the rulebook every part is given — the
                              UNIVERSAL half, shared by every group
coordinator/process_ifs.md    the IFS group's own half, composed into
                              the above at every circle open
coordinator/process.md        the operations rulebook — closing,
                              auditing, recovery
groups/ifs/issues/issue_model.md
                              what an issue is, and what is not one
```

## Status, support, and contributing

```
status         working software, one installation's worth of use behind
               it. Interfaces change without notice.
support        none. There is no issue tracker, no mailing list, and no
               undertaking to answer.
contributing   not set up for it.
bug reports    welcome in principle, unread in practice. Fork it.
```

Apache-2.0 gives you the right to use, modify and redistribute this,
including for your own purposes and under your own name, subject to the
licence's terms. Nothing above narrows that; it describes what is *not*
offered alongside it.

## A note on the code

Module docstrings quote decisions and record what went wrong and why.
That is deliberate and load-bearing: nearly every guard in this system
exists because a specific thing failed quietly, and the docstring is
where that reason lives. If a comment seems to be arguing with itself, it
is usually recording a decision that was made twice.

Man pages for many of the modules are under `coordinator/docs/`. Read
the man page before the module; it is where a module's *why* lives.

## Technical things that can bite

**`.gitattributes` sets `* -text` and must survive.** Line-ending
conversion would break every sha256 and byte-identical check here.

**That setting cuts both ways.** `* -text` stops git normalising on the
way through — which also means nothing removes a carriage return that a
writer put there. On one occasion this project's own repair scripts
converted three files wholesale, and every other check passed:
`pathlib.Path.write_text(..., encoding="utf-8")` translates `\n` to
`\r\n` on Windows unless `newline=""` is passed. If you write to these
files from your own code, pass it.

**A transcript being written is indistinguishable from a finished one.**
Statements are appended as they arrive, which is what makes a crash
survivable and what makes a mid-circle read a silent partial. Ask the
tree, not the file:

```
.venv\Scripts\python coordinator\circle_state.py
    exit 0  safe to read
    exit 1  a circle may be open
```

**Nothing here phones home.** No telemetry, no analytics, no update
check, no crash reporting.

## Editing files by hand

In general, let the app do it. Some files, such as the circle transcript,
record of what happened, and editing those violates history — and invalidates 
the checks that made the history worth anything. **A record you may edit is a
record that proves nothing.**

```
YOURS — the system expects you to update this; the API key is required.
  .env                          your key and your name

YOURS — the system is pretty tolerant if you update these
  groups/ifs/self/self.md       more about you
  groups/ifs/self/best_practices.toml
                                how the CIRCLE behaves, and how you move
  groups/ifs/parts/<name>/long_term.md
                                a part's identity
  groups/ifs/parts/<name>/part.toml
                                a part's tag, and its first-run
                                questions with your answers
  coordinator/process_core.md   the rulebook every part reads — the
                                universal layer
  coordinator/process_ifs.md    the IFS group's own layer, composed onto
                                it: the Soul, the goals, the honesty
                                mandate, mutual knowing

WITH CARE — machine-written, but hand-editable
  groups/ifs/issues/issue_model.md
                                what an issue is
  groups/ifs/issues/*.toml      the issue graph
  groups/ifs/self/*.toml        the registers
  groups/ifs/circles/*.toml     the four one-per-circle registers, which sit
                                beside the transcripts rather than under self/
    Each has one owning module that reads and writes it. Keep the shape,
    edit between circles, and run the gate named below afterwards.

NEVER — the historical record, and what is derived from it
  groups/ifs/circles/*.md       transcripts
  groups/ifs/parts/*/short_term_<OT>.toml
                                each part's record of a circle (.md before 2026-09-04)
  groups/ifs/parts/*/mid_term.md
                                the distillate
  work/logs/*.json              open and close reports
  work/prompts/**               captured prompts
```

Why those three are *never*, specifically:

```
a transcript is what was said
    every evidence quote in the issue graph is verified byte-for-byte
    against it, and the close report holds a sha256 of each part's record
    of the circle. Editing one turns a verified graph into a failing one.
    If the room got something wrong, say so in the next circle — that is
    what the next circle is for.

a short_term is hashed at close
    an edit shows up as DRIFT the next time the audit runs, and it cannot
    tell your edit from a lost write.

a mid_term is a cache, and more
    it is derived from a part's sources, and staleness is a hash over
    THOSE, not over the file itself. So a hand-edit is either silently
    overwritten the next time a source moves, or silently kept while
    nothing supports it. Edit the source instead:
      .venv\Scripts\python coordinator\part_mid_term_manager.py --refresh <part>
    and if you truly want to hold one by hand:
      .venv\Scripts\python coordinator\part_mid_term_manager.py --lock <part>
```

Three rules that apply to every hand-edit, including the sanctioned ones:

```
NEVER while a circle is open
    the coordinator is writing. Ask first:
      .venv\Scripts\python coordinator\circle_state.py

Use a plain-text editor, formatting OFF
    a markdown-aware editor may "normalise" a file on save — escaping [
    and _, merging emphasis across lines. That has silently corrupted a
    part's history in this project before, while still looking correct to
    a reader. Windows Notepad's formatting mode is one of these; turn it
    off under View -> Formatting.

Keep the line endings as you found them
    LF. A carriage return introduced by an editor changes every hash the
    file appears in. Repair one with
    `.venv\Scripts\python coordinator\file_line_endings_verify.py --fix
    <path>`; the pre-commit hook runs that same gate over whatever you
    are committing, first and unconditionally.

Then run the gate below for whatever you touched.
```

```
anything at all
  .venv\Scripts\python memory\record_verify.py
      watch for   INTEGRITY PASS
      a failure prints INTEGRITY FAIL and, per file, the defect and the
      remedy, then exits non-zero. There is no --force.

groups/ifs/parts/, groups/ifs/self/ or groups/ifs/circles/*.toml
  .venv\Scripts\python coordinator\circle_audit.py --selfcheck
      watch for   0 FAIL · 0 WARN · N OK
      a WARN is not a pass. Read it.

groups/ifs/issues/
  .venv\Scripts\python memory\issue_gate.py
      watch for   GATE PASS — every invariant satisfied
      and the "quote(s) verified verbatim" count. It should not fall.

a part's identity sources
  .venv\Scripts\python coordinator\part_mid_term_manager.py
      watch for   that part's row turning stale, then
        .venv\Scripts\python coordinator\part_mid_term_manager.py --refresh <part>
      This one exits 0 either way. Read the word, not the exit code.
```

**A silent pass is the one to distrust.** Every gate here prints what it
checked and how much of it. A count that *drops* after your edit means
something stopped being seen — which looks exactly like less being
wrong.

## Keeping the record honest

The gates above are not decoration; each exists to watch for any fail. 
Three check automatically:

```
record_verify.py runs at every circle open
    a corrupt file stops the circle before any model call is made, and
    before anything is written

the open verifier runs at the end of every open
    it writes work/logs/open_<OT>.json — whether the open left behind its
    transcript, its working-set entry and a whole prompt capture. It only
    reports: it never stops a circle

the close verifier runs at every /close
    it writes work/logs/close_<OT>.json — a size and a sha256 for each
    part that spoke
```

One is worth running after you edit anything by hand, or when a close went
wrong:

```
.venv\Scripts\python coordinator\circle_audit.py
    the audit: the same checks, plus a reconcile of each close report
    against what is on disk for every circle not yet dreamed, and a read of
    every open report, which warns and never fails. It REPORTS a part's
    lost record of a circle; it does not rebuild one.
.venv\Scripts\python coordinator\circle_audit.py --backfill --commit
    the repair: rebuilds a lost record from the transcript and writes it.
    Without --commit it only stages the rebuild for you to read.
```

**A part that spoke but lost its record of the circle would otherwise be
*invisible*, not noisy** — an absent file reads as a part that stayed silent,
which is a legal outcome. So a completing close rebuilds that record from the
transcript itself, as its first step, before dreaming and synthesis run (B54);
and if the close dies after that point, the re-run command it prints does the
same rebuild before it dreams. The audit's copy of the repair is for the two
cases that path never reaches: an `/abort`, which never gets as far as
dreaming, and a record lost *after* its circle was already dreamed
(`--backfill --all-circles`).

## Licence

Copyright 2026 The Inner Circling Project.

Licensed under the Apache License, Version 2.0. You may not use this file
except in compliance with the licence. See `LICENSE` for the full text
and `NOTICE` for attribution.

**Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
ANY KIND**, either express or implied. See §7 and §8 of the licence, and
the disclaimer near the top of this file.
