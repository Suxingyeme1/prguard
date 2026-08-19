# Minimal fixture cases

These five templates exercise the deterministic Phase 1 state machine: successful patch,
verification failure, pass-to-pass regression, `git apply --check` failure, and process-group
timeout. They intentionally contain no gold patch, defect label, or hidden test.

Templates are copied into `benchmark/generated`, initialized as independent Git repositories, and
assigned concrete base commits by `scripts/materialize_fixtures.py`.

