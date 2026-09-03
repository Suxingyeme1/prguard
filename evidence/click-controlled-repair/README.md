# Click #3199 controlled-repair evidence

Frozen: 2026-09-03

PRGuard: 0.10.6

This package closes a real-repository Demo B without using a Gold Patch:

1. the exact Click #3199 candidate passed 1323 tests and 9 changed-test replays;
2. an independent read-only Reviewer reported one P2 extension-point regression;
3. a fresh Implementer context received only the Issue, candidate Patch, structured finding, green
   verification evidence, and normal bounded repository tools;
4. the Implementer made four structured edits and emitted one complete replacement Patch;
5. the deterministic Harness passed 1324 full-suite tests and 10 changed-test replays;
6. an Agent-invisible evaluator confirmed that a custom `Context.lookup_default()` override works
   at Base, fails on the original candidate, and works again after repair.

The repair model did not receive the evaluator, later upstream fix, maintainer label, or any Gold
Patch. It used 20 read/navigation tool calls, 215,956 input tokens, 14,823 output tokens, and
196,992 cached tokens over 254.8 seconds. The earlier live Independent Review took 291.6 seconds;
these costs remain part of the evidence rather than being omitted from the success claim.

`repair-summary.json` binds the original candidate, public finding, delivered Patch, evaluator,
private raw report, recursive Manifest, and archive by SHA-256. The raw archive hash matched across
server and workstation, all five nested Manifests verified, and a credential-pattern scan was clean.
