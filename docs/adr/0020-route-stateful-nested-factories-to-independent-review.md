# ADR 0020: Route changed stateful nested factories to Independent Review

Status: Accepted (2026-09-02)

## Context

`review-routing-v1` recommended skipping Independent Review for the PrettyTable #474 source-only
Patch. The Patch was small, changed one analyzed Python symbol, selected its only statically
reachable test module, and had low caller fan-in. All 338 existing tests passed. A same-Patch
Reviewer nevertheless found a confirmed cross-table regression: the nested HTML parser retained
`max_row_width` across table boundaries.

The failure is not explained by Patch size or caller count. It is a lifecycle risk inside a
factory-returned state machine. Adding a repository-, path-, or symbol-name exception would be
overfit and unauditable.

## Decision

Create the immutable policy version `review-routing-v2`. Preserve every v1 Artifact unchanged.

Add the deterministic factor `stateful_nested_factory_changed` with weight 5, equal to the Review
threshold. It applies when all of the following are true in the bounded candidate AST:

1. a changed Python function contains a directly nested class;
2. that function directly returns the nested class from its body;
3. at least one instance attribute is written in two or more methods of that class.

The Artifact records the changed symbol, returned class, and bounded attribute names. Parse, file,
and symbol-analysis failures continue to use the existing fail-closed path. The factor uses no
Issue text, model claim, evaluator label, repository identity, or executed code.

The top-level Issue-to-PR Manifest binds the actual policy version from its routing result. Runs
that fail before routing bind the current policy version so their failure artifacts remain valid.

## Consequences

The frozen PrettyTable candidate changes from `skip` 0/5 to `review` 5/5. Humanize and the
normalization fixture keep their prior recommendations, and existing stateless low-risk integration
cases continue to skip.

This policy was designed after observing the PrettyTable failure. Its replay is a regression check,
not unbiased effectiveness evidence. v2 remains opt-in for selective mode until held-out,
manually labelled real-repository cases establish an acceptable False-Skip and False-Route tradeoff.

The static signal is intentionally narrow. It does not detect every state machine, module-level
cache, ordinary top-level class, closure mutation, dynamic attribute, or lifecycle bug. Broadening
those categories requires new failure evidence and another policy version.
