# Security policy

## Reporting a vulnerability

Please use GitHub's private **Report a vulnerability** flow in the repository Security tab. Do not
open a public issue for credential exposure, command-policy bypass, path traversal, manifest
verification bypass, model-context leakage, or worktree escape.

Include a minimal reproduction, affected commit or version, impact, and sanitized evidence. Do not
include real API keys or private repository contents. You should receive an initial response within
seven days; disclosure timing will be coordinated after a fix is available.

## Supported versions

The current `0.5.x` line receives security fixes. Earlier development snapshots are unsupported.

## Security boundary

PRGuard constrains its own orchestration: commands use validated argv forms and `shell=False`, model
tools provide bounded reads, patches pass path policy, runs use detached worktrees, and artifacts are
hashed. Those controls do not make arbitrary repository tests safe to execute.

Until container, network, and resource isolation is implemented, run untrusted repositories only in
an externally isolated disposable environment. Tests inherit the effective host-user permissions
and may access resources available to that user. Provider-backed runs can transmit source bytes
requested through bounded read tools to the selected model service.

The full assumptions, protected assets, threats, and residual risks are documented in the
[threat model](docs/threat-model.md).
