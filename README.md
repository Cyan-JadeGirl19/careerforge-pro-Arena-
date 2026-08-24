# CareerForge Pro

CareerForge Pro is a CV-first career acceleration platform for South African professionals pursuing remote work globally.

## Current status

This repository currently contains the first no-build interactive MVP prototype. It demonstrates the product direction without requiring API keys or external services.

### Included

- Dashboard
- CV Studio with transparent keyword analysis
- South Africa-oriented job feed with source filters
- Outreach draft composer
- Application tracker
- Privacy/settings screen

## Product principles

- Interview-focused, not application-volume-focused
- Job-specific CV tailoring
- Evidence-backed claims only
- Human-sounding, plain professional writing
- User approval before sending, sharing, or submitting
- POPIA-conscious privacy and data minimisation
- Permitted job-source integrations only

## Run locally

Open `index.html` directly, or run:

```bash
python3 -m http.server 8000 --bind 0.0.0.0
```

Then visit `http://localhost:8000`.

## Planned production architecture

- Frontend: Next.js/React
- API: FastAPI
- Database: PostgreSQL
- Object storage: encrypted document/media storage
- CI/CD: GitHub Actions with preview deployments, tests, health checks, and rollback
- Monitoring: structured logs, uptime checks, and error monitoring

See `docs/ROADMAP.md` and `REVIEW.md` for the product and engineering plan.
