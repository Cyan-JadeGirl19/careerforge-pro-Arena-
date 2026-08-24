# Changelog

## 0.3.0 - 2026-08-24

Document engine (CV core, continued):

- PDF/DOCX/TXT CV upload with immediate structured parsing (pypdf, python-docx); extraction notes flag anything needing candidate confirmation
- Three master CV builders: ATS Enterprise, Modern Professional, Role Specialist (`build-masters` builds all three in one action)
- Unlimited custom CV versions with role focus, emphasize and exclude lists (transferable-skills repositioning only — never invented experience)
- Job descriptions + per-job tailoring: keyword extraction, coverage report, surfaced keywords, gaps flagged for real evidence — nothing fabricated
- Exports for every version: DOCX, PDF, plain text, JSON (single-column, parser-safe)
- Per-application records retain JD id, surfaced keywords, confirmation list, timestamps
- 32 API tests passing; OpenAPI contract re-exported
- Governance: LICENSE (MIT), SECURITY.md, CODE_OF_CONDUCT.md, issue + PR templates
- ROADMAP: video responses up to 3 minutes (user-confirmed), hosting/ops requirements recorded

## 0.2.0 - 2026-08-24

- Expanded MVP into modular monorepo structure:
  - `apps/web`: Next.js 14 frontend (typed API client, server-side API proxy, module status page)
  - `apps/api`: FastAPI backend with versioned `/api/v1` routes
  - `packages/contracts`: shared TypeScript API contract
- Candidate profile model with POPIA-aligned erasure
- Explicit, purpose-scoped, revocable consent model (7 consent items) enforced on sensitive endpoints
- CV records with transparent analysis engine (checks, keyword map, gaps — no fabricated ATS score)
- Versioned OpenAPI contract at `docs/openapi/v1.json` with CI staleness check
- GitHub Actions CI: API tests + web typecheck/build on PRs
- Docker Compose for local Postgres + API + web; Makefile local launcher
- 16 API tests (health, profiles, consents, CVs)
- Restored no-build MVP; also served by Next at `/prototype.html`

## 0.1.0 - 2026-08-24

- Added CV-first interactive MVP prototype.
- Added dashboard, CV analysis, job feed, outreach draft, tracker, and privacy screen.
- Added initial product and compliance review.
