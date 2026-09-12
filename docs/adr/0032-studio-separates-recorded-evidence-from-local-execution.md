# ADR 0032: Studio separates recorded evidence from local execution

## Status

Accepted.

## Decision

Studio has two product states with different truth claims:

1. A static, hosted page introduces the local workflow and exposes **recorded examples**. A recorded
   example is a frozen evidence reader. It may show an upstream Issue, Patch, review decision,
   abbreviated evidence hashes, and the steps that already happened. It must state that it does not
   call a model or write a repository.
2. An authenticated loopback Studio session is a **local workspace**. It presents one task at a
   time: describe the request, inspect the frozen run contract, explicitly approve it, observe
   execution, then inspect/download the Patch and evidence produced by that exact run.

The UI must not present disabled fields from a recorded case as an editable task form, display a
recorded success next to a READY status, or call a Fix-only result “review ready.” The local Fix
result says that deterministic verification passed and explicitly records that Independent Review
did not run.

Product copy uses message identifiers and explicit Chinese/English catalogs. It does not scan or
mutate the DOM to translate text. Commands, source paths, hashes, user input, and recorded evidence
are data, not UI copy, and remain byte-for-byte unchanged when the language changes.

The browser adapter owns only authenticated local API state and retry/poll behavior. The view owns
rendering. This prevents hidden replay or live screens from competing over shared header state,
and makes a transient browser disconnect visible without implying that backend work was cancelled.

## Consequences

The first screen leads with the job a developer wants to do rather than an Agent dashboard:
prepare a task, inspect what will run, verify a Patch, and retrieve evidence. Safety details still
exist, but appear at the approval and evidence boundaries where a human needs them.

Studio remains dependency-free static HTML/CSS/JavaScript and the local server keeps its fixed
asset allowlist and CSP. This ADR changes presentation and truthful state disclosure; it does not
grant the browser new command, filesystem, provider, cancellation, or Reviewer authority.

The browser still runs only the existing Fix path. Integrating independent review into the local
workspace requires a separate backend/API decision rather than a cosmetic UI state.
