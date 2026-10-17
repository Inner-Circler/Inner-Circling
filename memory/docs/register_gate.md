# REGISTER_GATE.PY(1)

## NAME
register_gate.py — the REGISTER gate: the one gate every write to the record passes. Moved out of
`record_model.py` on 2026-09-03 (cohesion re-homing stage 9, NEXT.md B99); the name is
`docs/REGISTER_GATE_DESIGN.md`'s own.

## SYNOPSIS
    import register_gate as RG
    RG.record_tree_compare(baseline_dir, candidate_dir[, today=..., ...])   the paired gate, at every live /close
    RG.record_tree_verify(root)                                            the single-tree half, --selftest
    RG.register_summarise(findings) -> (fails, warns, oks)

No `main()`. `transaction.Transaction.validate()` and `circle_audit.py` are its two drivers.

## DESCRIPTION
`record_model.py` keeps the structural MODEL of the memory files — `Finding` and `_f`, the primitives
(`sha`, `read_bytes`, `decode`, `line_endings`, `headings`, `preamble`), the entry parser and
`LongTerm`, and the three comparisons (`compare_long_term`, `compare_headed`, `compare_append_only`).
This module composes them into the gate and reads them as `M`. Every function is the verbatim body
it had in `record_model.py`; only the file moved.

`record_tree_compare()` walks `_tree_files()` of a baseline and a candidate, judges every markdown file by
its kind, then every TOML register by its `REGISTERS` spec (`register_compare()`: append-only,
mutable-fields-only, register_dumps() fixed points, caps, id sequence, date order, chain target, state
vocabulary). `record_tree_verify()` is the same without a baseline (`register_verify()`). The spec
table's caps and orders are IMPORTED from each register's own module through late readers (`_ch_cap`,
`_tp_cap`, `_tp_order`, `_mem_cap`, `_mem_order`, `_so_order`, `_cj_cap`, `_cj_order`) — the
one-fact-one-home rule `system_unique_home_verify.py` enforces elsewhere. All but the two topic readers
return a literal copy when that import fails; `test_register_gate.py` forces the failure and holds each
ORDER copy equal to its register's own. It writes nothing, anywhere, ever.

## DEPENDENCIES
Standard library: `datetime`, `pathlib`, `re`, `tomllib`/`tomli` (inside `_load_register`). Sibling
modules: `record_model` (as `M`), `proposal_manager` and `practice_manager` (their `ORDER` tuples, read by
`REGISTERS`), `REGISTER_CLASS` (inside `_fixed_point`), and the late cap readers'
`circle_history_manager`, `topic_manager`, `remember_manager`, `circle_observation_manager`,
`circle_journal_manager`.

## EXTERNAL FILES
Read only: every file `_tree_files()` names under parts/ and self/ of the trees it is handed.

## NETWORK ACCESS
None.

## OPERATION
The rulings and reasoning are in the function docstrings and the section comment above `REGISTERS`
(R188, R191, R255), which moved with the bodies. Probes: `coordinator/tests/test_register_gate.py`,
`test_circle_observation_manager.py`, `test_TRANSACTION_CLASS.py`, `test_circle_audit_lock.py`;
`circle_audit.py --selftest` runs the single-tree half against the live tree.
