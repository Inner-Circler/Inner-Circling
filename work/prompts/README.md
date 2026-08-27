# prompts/

**Written by `coordinator/prompt_capture.py` at circle open. Never by
hand.**

`prompts/<OT>/<part>.md` plus a `manifest.json`, one directory per
circle. Each file is the VERBATIM system prompt that part ran — the
program it executed, not a summary of it.

The manifest records each block's byte offset, length and sha256, so the
original bytes slice out exactly. `prompt_capture.py --verify` re-slices
and re-hashes every capture.

**This directory is empty on purpose.** It fills as circles are held.

**These files inherit the privacy of what they capture.** A prompt
embeds the part's own identity file verbatim. Treat this directory
exactly as you treat `parts/`.
