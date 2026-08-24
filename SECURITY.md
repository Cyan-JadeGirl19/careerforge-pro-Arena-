# Security Policy

## Scope

CareerForge Pro handles sensitive personal data (CVs, references, voice and
video media, contact details). Security is a core requirement, not an
afterthought.

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

Email: security@careerforge.pro (or create a private vulnerability report
on GitHub for this repository).

We aim to acknowledge reports within 48 hours and will work with you on a
fix and responsible disclosure.

## Current posture

- Explicit, purpose-scoped, revocable consent for all sensitive actions.
- Candidate data erasure (POPIA) via `DELETE /api/v1/profiles/{id}`.
- Secrets are environment-only (`.env*` is git-ignored; no tokens in code).
- Versioned API routes with a machine-checked OpenAPI contract.
- CI on every pull request: API tests, web typecheck and build.
- CORS restricted to configured origins; credentials only for allowlisted hosts.

## Planned (before production launch)

- AuthN/AuthZ (accounts + sessions) — nothing sensitive is accessible
  anonymously once accounts exist.
- Encryption at rest for document and media storage; encrypted backups.
- Rate limiting and upload validation (type, size, content).
- Security review / penetration test before public launch.
- POPIA/GDPR counsel review.
