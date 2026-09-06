# Licensing

*Proposed and RULED 2026-08-07; entered in `rulings/` 2026-08-24 as R337,
which is why that entry's own date is the later one. The licence is
**Apache-2.0** and the attribution is **The Inner Circling Project** —
option (b) below, ruled in the same breath as "name is to be removed from
public files." `LICENSE` and `NOTICE` are written. What follows is why,
kept because the reasoning is the durable part.*

*The three files live in `packaging/scaffold/` and are cloned to the
BUNDLE root as-is; this tree has no `LICENSE` at its own root, because it
never leaves the machine. `docs/publishing.md` §6 is the other half.*

---

## Recommendation: Apache License 2.0

It is the only common license that delivers all four requirements
explicitly rather than by side effect.

```
public        no restriction on who
              receives it
sharable      redistribution in source
              and binary form
modifiable    derivative works permitted,
              stated in §3 and §4
attribution   REQUIRED, and required in a
              specific, enforceable way —
              §4(c) and (d)
```

**§4(d) is why Apache-2.0 beats MIT here.** MIT requires only that the
copyright notice be retained somewhere in the source. Apache-2.0
additionally requires that a `NOTICE` file, if the work has one, be
reproduced in every derivative distribution — so attribution survives
into a fork's own documentation, not just its file headers. When
"attribution required" is the stated goal rather than a formality, that
is the difference.

Two further properties that matter for this project specifically:

**An express patent grant (§3), with a termination clause.** Anyone who
sues over patents in this work loses their license to it. This project
is a method for running a multi-agent system; a grant costs nothing and
removes a question a cautious recipient would otherwise have to ask.

**§7 and §8 disclaim warranty and liability in plain terms.** This is
software that implements a *psychotherapeutic practice*. `better_options`
carries the project's only safety content. Someone will eventually run
this on themselves. The disclaimer is not boilerplate here — it is the
sentence that says this is a method someone built for himself and shared,
not a clinical instrument.

## The alternatives, and why not

```
MIT
  simpler, and genuinely fine. Attribution
  is weaker in practice: retain a notice.
  No patent grant. Choose this only if
  Apache's length is itself the objection.

CC BY 4.0
  built for attribution, and the natural
  fit for process_core.md read as a
  document. But Creative Commons
  themselves recommend against CC for
  software, and this bundle is mostly
  code. See "if you want the rulebook
  separate" below.

GPL / AGPL
  requires derivatives to stay open. That
  is a restriction on modification, not
  attribution — it answers a question
  Self did not ask.

CC BY-NC / BY-ND
  NC and ND both contradict "sharable,
  modifiable".
```

## If you want the rulebook licensed separately

Defensible and common: **Apache-2.0 for code, CC BY 4.0 for the prose.**
`coordinator/process_core.md` and `docs/*.md` are documents a reader adapts
rather than compiles, and CC BY is what documents are normally offered
under.

The cost is that a recipient must work out which license covers which
file. Recommendation: **do not split it.** One license over the whole
bundle, stated once in `README`, is clearer than a correct-but-two-part
answer. Revisit only if someone asks.

## What ships

```
LICENSE   the Apache-2.0 text, 202 lines.
          The canonical text, with the
          APPENDIX's `[yyyy] [name of
          copyright owner]` placeholder
          filled in -- which is what the
          appendix itself asks for. So:
          customary, not byte-verbatim.
NOTICE    the attribution
README    one line naming the licence
          -- WRITTEN, README.md line 7:
          "Licensed under Apache-2.0 --
          see `LICENSE` and `NOTICE`."
```

The `NOTICE` file is what does the work:

```
Inner Circling
Copyright 2026 The Inner Circling Project

This product includes software developed
for Inner Circling, an Internal Family
Systems inner circle run as a multi-part
simulation.

Licensed under the Apache License,
Version 2.0. See LICENSE.
```

Apache-2.0 also provides a per-file header. **Do not add it to every module.**
The `LICENSE` + `NOTICE` pair is sufficient, and a header in every module
would push the ruling-quoting docstrings — which are the reason the code
reads as it does — further down the file.

---

## The attribution decision — RULED (b)

**Attribution requires naming someone, and that is the one place PII
deliberately re-enters a public file.** It cannot be avoided: a license
that requires attribution must say who is being attributed.

**THE NAME QUESTION IS NOW RULED, AND IT DECIDES THIS.** On 2026-08-07:
every occurrence of the circle owner's given name in a shared public
file becomes "Self". 311 occurrences across 53 files were replaced, and
`packaging/sanitize.py` plus `packaging/test_package.py` hold the line now
— `check_classification.py --name-scan` retired 2026-08-08.

A `NOTICE` reading `Copyright 2026 <given name> <surname>` would be the
single largest exception to a rule just made, in the one file guaranteed
to be read. So:

```
b  A PROJECT NAME — RECOMMENDED
     "Copyright 2026 The Inner Circling
      Project"
     Consistent with the naming rule.
     Legally workable: an unincorporated
     project can hold a copyright notice.
     Attribution flows to the project
     rather than the person.

a  a personal name
     Conventional, and unambiguous about
     who made it — but it reintroduces
     the name the naming rule just took
     out of 53 files. Choose it only by
     deciding the naming rule has a
     deliberate exception here, and say
     so, so the scan can carry it.

c  a name plus a contact
     NOT RECOMMENDED. Adds back the
     address removed from nightly.py,
     into a file guaranteed to be read.
```

**Note what (b) costs and what it does not.** Copyright arises on
authorship regardless of the notice, so (b) does not give the work away;
it makes enforcement clumsier, because a claimant would have to
establish who "The Inner Circling Project" is. For a shared method that
is a fair trade. For anything you might ever litigate, it is not.

This is one decision, not two: whatever is chosen here should match the
naming rule, or the naming rule should record this as its exception.

## Classification

```
docs/licensing.md   public  doc
LICENSE             public  doc
NOTICE              public  doc
README.md           public  doc
```
