# ADR 0003: Content-address every run artifact

Status: Accepted (2026-08-18)

Run outputs use canonical UTF-8 JSON and SHA-256 hashes. `manifest.json` lists every other artifact
and includes a hash of its own payload excluding that hash field. Reproduction verifies bytes and
then re-executes only when explicitly requested; integrity verification never runs repository code.
