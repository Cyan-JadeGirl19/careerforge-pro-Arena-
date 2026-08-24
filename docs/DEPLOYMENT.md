# Deployment Guide

## LIVE deployment (as of 2026-08-24)

Everything runs on **Render** (free tier):

| What | URL |
|---|---|
| **Public app** | https://careerforge-web-w90j.onrender.com |
| **API** (health) | https://careerforge-api-h5yp.onrender.com/api/v1/health |
| **API docs** (Swagger) | https://careerforge-api-h5yp.onrender.com/docs |
| Web service dashboard | https://dashboard.render.com/web/srv-da6c4c0u01pc73a4rld0 |
| API service dashboard | https://dashboard.render.com/web/srv-da6bklmk1f9s73dsli9g |
| Postgres dashboard | `careerforge-db` (dpg-da6bjkqjobas73bjc430-a) |

Architecture:

```
Browser ──> careerforge-web-w90j.onrender.com   (Render: Next.js web service)
                │  /api/v1/*  (same-origin proxy, CF_API_URL env var)
                ▼
        careerforge-api-h5yp.onrender.com       (Render: FastAPI service)
                │  internal connection string
                ▼
        Render managed PostgreSQL (free)
```

## Updating (changes go live automatically)

Both services have **auto-deploy on**: push to `main` on GitHub → Render
rebuilds and redeploys. From this workspace: `bash scripts/push.sh`.

Free-tier note: Render free web services **sleep after ~15 minutes of
inactivity**. The first request after idle takes ~30-60 s to wake up.
This is normal. (Optional later: Starter plan removes sleep.)

## Rollback

1. Open the service dashboard (links above).
2. **Deployments** tab → find the last known-good commit →
   **Re-select commit** → deploy.
   (Or from here: tell the workspace which commit to redeploy.)

## Environment variables (set on Render, not in the repo)

API service (`careerforge-api`):
- `CF_ENVIRONMENT=production`
- `CF_DATABASE_URL` = the **internal** Postgres connection string
  (the external TLS edge is flaky with libpq; internal is the reliable
  path from Render services)
- `CF_CORS_ORIGINS` = `["https://careerforge-web-w90j.onrender.com"]`
  (update here if the web URL ever changes)

Web service (`careerforge-web`):
- `CF_API_URL` = `https://careerforge-api-h5yp.onrender.com`
  (the same-origin proxy target; update if the API URL ever changes)

## Backups

- Render → Postgres dashboard → **Backups** → Create backup (free tier
  includes periodic backups; you can also create manual ones and download
  the `.sql` dump).
- User erasure works in-app (Settings → Delete everything) and via
  `DELETE /api/v1/profiles/{id}`.

## If you ever want Vercel for the web app

Optional: Vercel + this repo (Root Directory `apps/web`, env var
`CF_API_URL` = the API URL). Everything currently runs fine on Render;
switching is a preference, not a requirement.

## Known production behaviour

- First request after idle: 30-60 s (free-tier sleep) - normal.
- API stays up even if the DB is briefly unreachable: health reports
  `database: "down"` and schema init retries automatically.
- Job feed sources (We Work Remotely, RemoteOK, Remotive) are fetched
  server-side on demand by `POST /api/v1/jobs/sync`; failures of one
  source never block the others.
