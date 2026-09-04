# Visual terminal demo

Run the complete deterministic walkthrough from the repository root:

```bash
uv run --extra demo prguard demo
```

No API key, network service, prepared Task JSON, or target repository is required. PRGuard creates a
small disposable Git repository containing a deliberately incomplete `clamp()` implementation and
three tests. The first structured edit fixes only the lower bound, so the fixed pytest command
reports one failure. The Harness returns that evidence for the one permitted repair, which enforces
both bounds and passes all three tests.

The terminal timeline displays:

1. natural-language task acceptance and exact Commit freezing;
2. Base pytest readiness and detached Worktree preparation;
3. Implementer reads, structured edit, and Candidate Patch size;
4. exact test argv, exit code, failed assertion, and repair feedback;
5. successful retry, colorized final Git Patch, Artifact directory, and Manifest.

This is a presentation layer over the production `FixRunner`, edit materializer, verification
Harness, and recursive Manifest verifier. Only the model response is scripted, keeping the first
experience deterministic and free. Use `--no-color` for logs and `--output PATH` to select the
Artifact parent directory.

The demo covers test-driven Implementer repair. Independent Reviewer behavior remains demonstrated
by the frozen Click real-PR evidence; it is not simulated in this introductory screen.
