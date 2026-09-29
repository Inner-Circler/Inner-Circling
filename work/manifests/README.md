# work/manifests/

Empty delegate, shipped so the directory exists. This delegate
ships the directory with nothing in it; git does not track empty
directories, so this README is what keeps the directory present in a
clone.

**Nothing in the product WRITES this directory.** One thing reads it:
`memory/record_verify.py`'s corruption sweep parses every JSON file here
at circle open and in `circle_audit.py` phase 0, so a damaged manifest refuses
a circle rather than surfacing later.

So in an install the directory stays empty unless you put a JSON file
here yourself — and anything you do put here is read, and must parse,
before every circle opens.
