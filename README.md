# CareerForge Pro

CareerForge Pro is a CV-first career acceleration platform for South African professionals pursuing remote work globally.

## Repository layout

```
├── index.html                  # No-build interactive MVP prototype (works standalone)
├── apps/
│   ├── web/                    # Next.js 14 frontend (production app)
│   │   ├── app/                # App Router pages
│   │   ├── lib/api.ts          # Typed browser API client (same-origin /api/v1)
│   │   └── public/prototype.html  # MVP served by Next at /prototype.html
│   └── api/                    # FastAPI backend
│       ├── app/                # config, db, models, schemas, analysis, routes
│       ├── scripts/export_openapi.py
│       └── tests/              # pytest suite
├── packages/contracts/         # Shared typed API contract (TypeScript mirror)
├── docs/
│   ├── openapi/v1.json         # Versioned OpenAPI contract (CI-checked)
│   ├── ROADMAP.md
│   └── REVIEW.md
├── .github/workflows/ci.yml    # Tests + build on every PR
├── docker-compose.yml          # Local Postgres + API + web
└── Makefile                    # install / test / dev-api / dev-web / openapi
```

## Product principles

- Interview-focused, not application-volume-focused
- Job-specific CV tailoring
- Evidence-backed claims only (claim → source → verified → candidate-approved)
- Transparent CV checks, never a fabricated "95% ATS" score
- Human-sounding, plain professional writing
- Explicit, revocable consent before any sensitive action
- User approval before sending, sharing, or submitting
- POPIA-conscious privacy and data minimisation
- Permitted job-source integrations only

## Run locally

### MVP prototype (no build)

Open `index.html` directly, or run:

```bash
python3 -m http.server 8000 --bind 0.0.0.0
```

### Production apps (API + web)

```bash
make install     # pip (apps/api) + npm (apps/web)
make dev-api     # FastAPI on :8001, docs at /docs
make dev-web     # Next.js on :3000, proxies /api/v1 to the API
make test        # pytest suite
```

Or with Docker (Postgres + API + web):

```bash
docker compose up --build
```

Configuration is via `CF_` environment variables — see `.env.example`.
Production/staging environments must point at PostgreSQL.

## API

Versioned under `/api/v1`. Machine-readable contract: `docs/openapi/v1.json`
(re-export with `make openapi`; CI fails if it is stale).

Current v1 endpoints:

- `GET /api/v1/health`
- `POST/GET/PATCH/DELETE /api/v1/profiles[...]`
- `POST/GET/DELETE /api/v1/profiles/{id}/consents[...]`
- `POST /api/v1/profiles/{id}/cvs` (paste), `POST /api/v1/profiles/{id}/cvs/upload` (PDF/DOCX/TXT)
- `GET /api/v1/cvs/{id}`, `GET /api/v1/cvs/{id}/parsed`
- `POST /api/v1/cvs/{id}/analyze`, `GET /api/v1/cvs/{id}/analysis/latest`
- `POST /api/v1/cvs/{id}/versions` (master_ats | master_modern | master_role | custom)
- `POST /api/v1/cvs/{id}/versions/build-masters` (all three in one action)
- `GET /api/v1/cvs/{id}/versions`, `GET /api/v1/cvs/{id}/export`
- `POST /api/v1/profiles/{id}/job-descriptions`
- `POST /api/v1/cv-versions/{id}/tailor` → job-specific CV + coverage report
- `GET /api/v1/cv-versions/{id}`, `GET /api/v1/cv-versions/{id}/export`
- `GET /api/v1/tailored/{id}`, `GET /api/v1/tailored/{id}/export`
- Exports: `docx`, `pdf`, `txt`, `json` — single-column, parser-safe

Autonomous studio (upload CV → program does the rest):

- `POST /api/v1/profiles/{id}/roles/recommend` → top-3 target roles
- `POST /api/v1/profiles/{id}/applications` → application package (auto-selects best CV version)
- `GET /api/v1/profiles/{id}/applications`, `GET /api/v1/applications/{id}`
- `POST /api/v1/applications/{id}/tailor` → job-specific CV + coverage report
- `POST /api/v1/applications/{id}/cover-letter` → human-authentic letter
- `POST /api/v1/applications/{id}/videos` → voice/video script (30–180s)
- `POST /api/v1/videos/{id}/regenerate`, `POST /api/v1/videos/{id}/media`
- `POST /api/v1/profiles/{id}/auto-pipeline` → full review queue in one call
- `POST /api/v1/applications/{id}/status` → tracker stage updates

Sensitive operations return `409 CONSENT_REQUIRED` until the candidate has
granted the matching consent (see `ConsentItem` in the contract).

## Hosted deployment

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** for the full walk-through.
In short:

- **API + Postgres** → [Render](https://render.com) (Blueprint: `render.yaml` —
  one click). Health: `https://<api>/api/v1/health`, docs: `https://<api>/docs`.
- **Web** → [Vercel](https://vercel.com) (import this repo, Root Directory
  `apps/web`, env var `CF_API_URL` = the Render URL).
- Push to `main` → both auto-redeploy. Branches get Vercel preview URLs.
  Rollback is one click on either platform.

## Planned production architecture

- Frontend: Next.js/React — `apps/web`
- API: FastAPI — `apps/api`
- Database: PostgreSQL (SQLite for local dev/tests)
- Object storage: encrypted document/media storage (Phase 1+)
- CI/CD: GitHub Actions with tests, contract checks, health checks
- Monitoring: structured logs, uptime checks, error reporting

See `docs/ROADMAP.md` and `REVIEW.md` for the product and engineering plan.
