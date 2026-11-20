# Security and privacy

This anonymous public simulation must never contain confidential or personal records.

## Implemented
- Random visitor bearer tokens; token hashes stored; HttpOnly SameSite=Strict cookies; Secure for HTTPS origin.
- Four-hour expiry; isolated reset and CSRF/cookie rotation.
- Scoped queries and composite tenant foreign keys.
- Backend simulated Reviewer checks and version-bound approval hashes.
- Immutable money, prices and approvals.
- CSRF, Host/Origin checks, cross-site rejection and no CORS grants.
- Strict same-origin CSP; no third-party fonts, trackers, inline scripts or dynamic HTML from user input.
- Static allowlist; databases, source and configuration are not served.
- Parameterized SQL, atomic writes, bounded text/JSON/CSV/Decimal input.
- Bounded concurrency, workspace creation, records and writes.
- No real sending, external execution, model key or business connector.

## Limits
Demo persona switching is intentionally open in each visitor workspace; it is not production authentication or independently verified human approval. Protect the visitor cookie like any bearer capability. There is no account recovery or cross-device login.

SQLite is unencrypted. Logical expiry is checked on every request; physical cleanup runs at the next new workspace. Free hosting may discard the filesystem sooner. Do not enter real data.

The HTTP implementation is for a bounded demonstration behind a TLS proxy, not unrestricted production use. Real deployment with actual business data would require stronger identity, encryption, monitoring, storage and abuse controls.

Do not expose local Chrome debugging ports when running optional checks.

## Publication checks
Run tools/public_scan.py before release and again with --history after committing. It checks source content, restricted filenames, credential-like patterns, local user paths, PNG text metadata, PDF text, and reachable Git commit blobs/metadata. Supply any private restricted phrases with --deny-file; their values are not copied into reports.

A zero finding is not a guarantee of legal ownership or exhaustive secret detection. Review staged files and screenshots manually too. Actual .env files, databases, logs, keys and browser profiles are ignored. No secret is required to start.

## Reporting
Use the repository owner's private reporting channel once available. Do not paste a working cookie or private content into public issues.
