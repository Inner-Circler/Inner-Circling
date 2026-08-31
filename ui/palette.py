#!/usr/bin/env python3
"""
palette.py — every colour this project shows a person, named once.

Ruled 2026-08-30: *"generate it, keep 4-bit ansi, build it."* B75 gave the
four diagram tools in work/graph/ one home for their colours; this is the
same fix one level up, across the three surfaces a PERSON actually looks at —
the terminal UI, the Ticker window, and the issue-graph picture.

A ROLE HAS TWO VALUES, NOT ONE. That is the whole shape of this file. The
drawings are on white and the Ticker is on near-black, so the same meaning
needs a different value on each ground: "settled" is #2c6e49 on paper and
#9ad6a5 on the dark band, and neither is legible where the other belongs.
The Ticker's own tokens turned out to BE the dark column of the roles the
drawings already used — --status-ok is green, --status-warn is gold,
--status-err is red, --accent is navy — which is not a coincidence, they were
chosen for the same meanings by the same eye. This file only says so.

WHAT IS SHARED IS THE MEANING, AND THE TERMINAL PROVES IT. `circling.py`
takes 4-bit ANSI here, not hex: a terminal's palette belongs to the person
running it, and emitting 24-bit colour would override the theme they chose.
So the TUI shares the ROLE and keeps its own values, which is the honest
limit of a shared palette across surfaces that do not share a colour system.

THE CSS IS GENERATED, BECAUSE NOTHING ELSE COULD KEEP IT HONEST.
`ui/ticker/src/app.css` is CSS and cannot import Python, and
`check_one_home.py` reads only Python, so a hand-copied hex there could drift
forever with no gate able to see it. `--css` prints the token block and
`--check` verifies the file still matches it.

    python ui/palette.py            print the palette
    python ui/palette.py --css      print the CSS token block
    python ui/palette.py --check    verify app.css matches (the gate)

MOST OF THESE VALUES WERE ALREADY IN THE TREE and are only being named. Five
are new, because nothing needed them before and a half-filled column is how a
later reader gets a different purple: PURPLE dark, AFFORD light, FAINT light,
GOLD_DIM light, GROUND_ALT light.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
APP_CSS = HERE / "ticker" / "src" / "app.css"

BEGIN = "  /* BEGIN GENERATED — ui/palette.py --css */"
END = "  /* END GENERATED */"

# --------------------------------------------------- the roles, (light, dark)
ROLES: dict[str, tuple[str, str]] = {
    "INK":        ("#1e1e1e", "#d7d9e0"),   # body text
    "MUTED":      ("#8a8a84", "#7f838f"),   # secondary — captions, meta
    "FAINT":      ("#b4b4ae", "#565a66"),   # tertiary — labels, timestamps
    "GROUND":     ("#fbfbf9", "#14151a"),   # the page itself
    "GROUND_ALT": ("#f2f2ee", "#1b1d24"),   # bands and rows on it
    "RULE":       ("#e3e3de", "#2a2d37"),   # borders and dividers
    "NAVY":       ("#2456a6", "#8f9bff"),   # the person, and the surface
                                            # they touch
    "GREEN":      ("#2c6e49", "#9ad6a5"),   # settled and load-bearing;
                                            # narrower-than
    "GOLD":       ("#b8860b", "#ffd23f"),   # what is OWED; leads-to
    "GOLD_DIM":   ("#8a6a1a", "#e6c35a"),   # the softer gold — marked text
    "GOLD_WASH":  ("#fffbe6", "#3a3115"),   # its background wash
    "PURPLE":     ("#7b5ea7", "#b3a4e0"),   # the coordinator's own act;
                                            # protects
    "RED":        ("#c0392b", "#ff5c5c"),   # private data, opposition,
                                            # refusal
    "AFFORD":     ("#8a7b3d", "#cfc08a"),   # where the user may act
}

# LIGHT ONLY, and deliberately so: these five appear in the drawings and
# nowhere else, and inventing a dark counterpart nothing renders would be
# five more values for a later reader to disagree with.
DIAGRAM: dict[str, str] = {
    "CHARCOAL": "#3a3a3a",     # memory at rest
    "TEAL":     "#1f7a8c",     # a register READ
    "MAROON":   "#8c3a4a",     # a register WRITE
    "OCHRE":    "#a8791f",     # the register files on disk
    "SLATE":    "#5f6b7a",     # subprocess invocation, its own relation
}

LIGHT = {k: v[0] for k, v in ROLES.items()} | DIAGRAM
DARK = {k: v[1] for k, v in ROLES.items()}

# The bare names are the LIGHT column, because the two Python consumers —
# issue_draw.py and the work/graph tools — both draw on white.
INK, MUTED, FAINT = LIGHT["INK"], LIGHT["MUTED"], LIGHT["FAINT"]
GROUND, GROUND_ALT, RULE = LIGHT["GROUND"], LIGHT["GROUND_ALT"], LIGHT["RULE"]
NAVY, GREEN, GOLD = LIGHT["NAVY"], LIGHT["GREEN"], LIGHT["GOLD"]
GOLD_DIM, GOLD_WASH = LIGHT["GOLD_DIM"], LIGHT["GOLD_WASH"]
PURPLE, RED, AFFORD = LIGHT["PURPLE"], LIGHT["RED"], LIGHT["AFFORD"]
CHARCOAL, TEAL = DIAGRAM["CHARCOAL"], DIAGRAM["TEAL"]
MAROON, OCHRE, SLATE = DIAGRAM["MAROON"], DIAGRAM["OCHRE"], DIAGRAM["SLATE"]

# ------------------------------------------------------------------- the TUI
# FOUR-BIT, RULED. `circling.py` renders inside somebody's terminal, and a
# terminal's sixteen colours are that person's own theme. Emitting 24-bit
# would make the room match this file and stop matching them — worse on a
# light profile, and not ours to decide. So the TUI shares the ROLE and the
# terminal keeps the value. These are the exact codes circling.py already
# used, so nothing on screen moves; what changes is that they now have names
# that mean the same thing here as they do in the other two surfaces.
ANSI: dict[str, str] = {
    "GREEN": "\x1b[32m",     # prompts
    "RED": "\x1b[31m",       # !! errors
    "TEAL": "\x1b[36m",      # chrome — cyan is 4-bit's nearest teal
    "OFF": "\x1b[0m",
}


def ansi(role: str) -> str:
    """The terminal code for a role, or the reset when it has none. Never
    raises: a missing colour must not be able to stop a circle drawing."""
    return ANSI.get(role, ANSI["OFF"])


# ------------------------------------------------------------------- the CSS
# css custom property -> (role, comment). The comments are generated too, so
# the reason a colour exists lives beside its value rather than in the file
# that merely spends it.
CSS_TOKENS: list[tuple[str, str, str]] = [
    ("--bg", "GROUND", ""),
    ("--bg-band", "GROUND_ALT", ""),
    ("--border", "RULE", ""),
    ("--text", "INK", ""),
    ("--text-dim", "MUTED", ""),
    ("--text-faint", "FAINT", ""),
    ("--accent", "NAVY", ""),
    ("--warn-bg", "GOLD_WASH", ""),
    ("--warn-text", "GOLD_DIM", ""),
    ("--affordance", "AFFORD",
     "where the user may act: the input band, the lower-pane tabs, the "
     "text fields in them and their chips carry this while idle and drop "
     "to --accent once selected or focused"),
    ("--status-ok", "GREEN", "the lower band's status line, and the "
     "completion line the close prints"),
    ("--status-warn", "GOLD", ""),
    ("--status-err", "RED", ""),
]


def _wrap(text: str, width: int = 68) -> list[str]:
    out, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            out.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        out.append(line)
    return out


def css_block() -> str:
    """The generated region of app.css, markers included."""
    lines = [BEGIN,
             "  /* Generated by ui/palette.py — the DARK column of its roles.",
             "     Do not edit between the markers; `python ui/palette.py",
             "     --check` refuses a commit where this and the palette have",
             "     drifted apart. */"]
    for name, role, why in CSS_TOKENS:
        if why:
            lines.append("")
            for i, ln in enumerate(_wrap(why)):
                lines.append(f"  /* {ln}" if i == 0 else f"     {ln}")
            lines[-1] += " */"
        lines.append(f"  {name}: {DARK[role]};")
    lines.append(END)
    return "\n".join(lines)


def check_css(path: pathlib.Path | None = None) -> list[str]:
    """Complaints, empty when app.css matches. A LIST rather than a raise so
    the gate can report every problem at once."""
    path = path or APP_CSS
    if not path.is_file():
        return [f"{path}: not in this tree — the Ticker's tokens are "
                f"generated from this palette"]
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        return [f"{path.name}: no generated region — it must contain the "
                f"BEGIN/END markers `python ui/palette.py --css` prints"]
    got = text[text.index(BEGIN):text.index(END) + len(END)]
    if got.replace("\r\n", "\n") != css_block():
        return [f"{path.name}: the generated region has drifted from "
                f"ui/palette.py — run `python ui/palette.py --css` and "
                f"replace the block between the markers"]
    return []


def main() -> int:
    argv = sys.argv[1:]
    if "--css" in argv:
        print(css_block())
        return 0
    if "--check" in argv:
        bad = check_css()
        for b in bad:
            print(f"  FAIL  {b}")
        if not bad:
            print(f"  OK    app.css matches the palette "
                  f"({len(CSS_TOKENS)} token(s) generated)")
        return 1 if bad else 0
    print("  palette — role, on light, on dark\n")
    for name, (lo, dk) in ROLES.items():
        print(f"  {name:<12} {lo}   {dk}")
    print("\n  light only (the drawings)\n")
    for name, v in DIAGRAM.items():
        print(f"  {name:<12} {v}")
    print("\n  terminal, 4-bit — the role is shared, the value is the "
          "person's own\n")
    for name, code in ANSI.items():
        print(f"  {name:<12} {code!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
