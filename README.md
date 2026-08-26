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

**One click:** double-click `start.command` (macOS) or `start.bat`
(Windows) — first run creates the API virtualenv + web dependencies,
then both servers start and stay up with clean logs.

```bash
bash start.sh     # same thing, from a terminal
```

Manual / Makefile (if you prefer):

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
- `POST /api/v1/videos/{id}/media-upload` → store a take/upload (consent + likeness confirmation)
- `POST /api/v1/videos/{id}/media/{mid}/analyze` → transparent quality report
- `POST /api/v1/videos/{id}/media/{mid}/enhance` → colour/audio/framing/captions → MP4 (job)
- `POST /api/v1/videos/{id}/media/{mid}/export-mp4` / `export-audio` → MP4 / MP3
- `POST /api/v1/videos/{id}/captions` → WebVTT from your text (proportional timing)
- `POST /api/v1/videos/{id}/media/{mid}/trim` → cut [start,end] → new MP4 (job)
- `POST /api/v1/videos/{id}/media-headshot` → approved headshot for the intro card
- `POST /api/v1/videos/{id}/intro-card` → name/role/headshot intro video + thumbnail (job)
- `GET /api/v1/videos/{id}/media/{mid}/download`, `DELETE` same
- `GET /api/v1/jobs/video/{job_id}` → background job status
- `POST /api/v1/profiles/{id}/auto-pipeline` → full review queue in one call
- `POST /api/v1/applications/{id}/status` → tracker stage updates
- `POST /api/v1/applications/{id}/followup-sequence` → 3-touch follow-up (standard/quick/gentle)
- `POST /api/v1/followups/{id}/gmail-draft` → files that touch as a Gmail draft

Gmail outreach (drafts only — the app never sends):

- `GET /api/v1/profiles/{id}/gmail/status`, `POST …/gmail/authorize`, `POST …/gmail/disconnect`
- `GET /api/v1/gmail/oauth/callback` (candidate's own Google account, `gmail.modify` scope only)
- `POST /api/v1/recruiters/{id}/gmail-draft` → files the email in your own Gmail Drafts
- `GET /api/v1/profiles/{id}/outreach/drafts` → list filed drafts

Sensitive operations return `409 CONSENT_REQUIRED` until the candidate has
granted the matching consent (see `ConsentItem` in the contract).

## Hosted deployment (LIVE)

**Public app:** https://careerforge-web-w90j.onrender.com
**API docs:** https://careerforge-api-h5yp.onrender.com/docs

Everything runs on Render (free tier): web + API + Postgres.
Push to `main` → auto-deploys. See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**
for URLs, env vars, backups and rollback.

## Planned production architecture

- Frontend: Next.js/React — `apps/web`
- API: FastAPI — `apps/api`
- Database: PostgreSQL (SQLite for local dev/tests)
- Object storage: encrypted document/media storage (Phase 1+)
- CI/CD: GitHub Actions with tests, contract checks, health checks
- Monitoring: structured logs, uptime checks, error reporting

See `docs/ROADMAP.md` and `REVIEW.md` for the product and engineering plan.
