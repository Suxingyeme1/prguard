# PRGuard Studio

PRGuard Studio is the browser-based evidence replay for the repository's two flagship workflows:

- `attrs #1575`: a held-out Issue-to-Patch run accepted by an independent Reviewer;
- `Click #3199`: a green candidate where independent review found and repaired a regression.

The page is intentionally an evidence viewer, not a simulated live model call. Its hashes, test
counts, timing, and verdicts are copied from the checked public evidence packages. The source fields
are read-only so changing the displayed Issue cannot silently reuse unrelated recorded results.

Run it from the repository root:

```bash
python3 -m http.server 4317 --bind 127.0.0.1 --directory demo-ui/dist
```

Then open <http://127.0.0.1:4317/>. No package install, API key, or server-side process is required.

The next product boundary is a separate authenticated local adapter that streams a real `fix` run.
Until that adapter owns repository selection, execution approval, and artifact reads, Studio stays
read-only and makes that boundary visible.
