# Studio browser checks

The lightweight state/parser suite needs only Node 20 or later:

```bash
node --test tests/browser/*.test.cjs
```

The full-browser suite uses a separately pinned development-only Playwright dependency. It launches
one fresh loopback Studio server per test with an ephemeral token and temporary repository. Model
credentials are cleared in its child environment. No paid model or company server is used.
Git, worktrees, pytest, approval and downloads are real; model replies alone are scripted.

From the PRGuard root:

```bash
uv sync --frozen --extra dev --no-editable
npm ci --prefix tests/browser
cd tests/browser
npx playwright install chromium
npm run test:e2e
```

`PRGUARD_TEST_PYTHON` can select another Python interpreter with PRGuard's test dependencies. By
default the launcher uses the repository's `.venv/bin/python`. Every case stops its own server
normally and removes only its temporary fixture directory. Screenshots and browser traces are
kept under ignored `test-results/` on failure. They may include ephemeral test session tokens;
do not publish diagnostic bundles without inspecting them.

If Google Chrome is already installed, `PRGUARD_TEST_CHANNEL=chrome npm run test:e2e` can use it
instead of downloading Playwright Chromium. This creates a separate test profile, not a connection
to your personal browser session. CI uses the version-pinned Playwright Chromium build.

Coverage: explicit approval, reviewed Fix, actual Patch download SHA-256, keyboard tabs, refresh
without another start, task selection, narrow-layout overflow, Chinese/English source preservation,
invalid-version recovery with retained request, literal rendering of HTML-like Issue text, and a
static setup guide that sends no execution request. A simulated Reviewer outage must withhold
final Patch delivery even after initial tests pass. Python integration tests separately cover
authentication/Origin, source preservation, immutable workflow approval and failed delivery gates.

These are Chromium functional checks, not a cross-browser or accessibility certification.
Playwright is not required to install or run PRGuard Studio.

Reference: [Playwright assertions](https://playwright.dev/docs/test-assertions) and
[download API](https://playwright.dev/docs/api/class-download).
