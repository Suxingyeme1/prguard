# ADR 0001: Build the deterministic core before agents

Status: Accepted (2026-08-18)

Agent output is treated as an untrusted proposal. Git state, patch application, verification,
timeouts, policy gates, and terminal outcomes are deterministic services. No LLM dependency or
orchestrator is included in Phase 0/1. This preserves attribution and gives all later A/B groups
the same verifier.

