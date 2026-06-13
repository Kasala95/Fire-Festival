"""Run-history persistence (SQLite).

Layer 1 of the run-history feature: a tiny schema + migration over stdlib
``sqlite3`` so completed runs can be stored, listed, and re-opened. No external
database server and no migration framework — the harness keeps its zero-infra
property. The JSON files under ``runs/`` remain the source of truth; this DB is
an indexed, queryable view on top for the history dashboard.
"""
