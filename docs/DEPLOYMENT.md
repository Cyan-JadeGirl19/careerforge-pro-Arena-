# Deployment Guide (Vercel + Render)

Goal: a stable public URL where **changes go live automatically** when you
push to `main`, with previews, health checks, and one-click rollback.

```
Browser ──> https://careerforge.vercel.app        (Vercel: Next.js web)
                │  /api/v1/*  (same-origin proxy)
                ▼
         https://careerforge-api.onrender.com     (Render: FastAPI)
                │
                ▼
         Render managed PostgreSQL                (your data)
```

The browser only ever talks to the Vercel URL. Vercel proxies `/api/v1/*`
to the API server-side, so no localhost URLs, no CORS pain, and the API
URL is never exposed to the browser.

---

## Step 1 — API + database on Render (≈5 minutes)

1. Go to **https://render.com** → **Log in with GitHub** (authorise
   Render to see your repositories).
2. In the dashboard click **New → Blueprint**.
3. Select the repository **`careerforge-pro-Arena-`** (main branch).
   Render reads `render.yaml` and shows:
   - `careerforge-api` (web service, Python)
   - `careerforge-db` (PostgreSQL, free)
4. Click **Apply** (accept the free plan).
5. Wait ~3–5 minutes for the first build. Then:
   - **App URL**: copy it from the service page
     (looks like `https://careerforge-api.onrender.com`).
   - **Health check**: open `https://<your-api-url>/api/v1/health` —
     you should see `{"status":"ok","database":"up",...}`.

> Free-tier note: Render's free web service **sleeps after 15 minutes of
> inactivity**. The first request after sleep takes ~30–60 s to wake it.
> That's normal. (Optional later: the $7/mo Starter plan removes sleep.)

## Step 2 — Web app on Vercel (≈5 minutes)

1. Go to **https://vercel.com** → **Continue with GitHub**.
2. **Add New → Project** → import **`careerforge-pro-Arena-`**.
3. In the setup screen:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: type `apps/web` ← **important**
   - **Environment Variables**: add
     - `CF_API_URL` = `https://<your-api-url>`  (the Render URL from Step 1)
4. Click **Deploy**. Wait ~1–2 minutes.
5. Open your Vercel URL (e.g. `https://careerforge-pro-arena-<xyz>.vercel.app`):
   - You should land on the app.
   - **Test the proxy**: open
     `https://<your-vercel-url>/api/v1/health` — it should return the
     same JSON as the API health check.
6. Back in Render: update `CF_CORS_ORIGINS` on the API service to
   `'["https://<your-vercel-url>"]'` (Settings → Environment), so direct
   API calls from your domain are also allowed. (The proxy means the app
   works even before you do this.)

## Done — that's your stable public URL

Share the Vercel URL. Everything is now live:
onboarding → CV upload → masters → jobs (live feeds) → tailored
applications → video studio → tracker → interview prep → skills/salary →
portfolio.

---

## Day-to-day: how changes go live

```
you push to main  →  Render rebuilds the API (health check gates it)
                  →  Vercel rebuilds the web
                  →  live on your URL
```

- **Preview deploys (web)**: push to a branch → Vercel auto-creates a
  preview URL for that branch. Review it, merge to `main`, done.
- **Rollback**:
  - Vercel → project → **Deployments** → pick an older deployment →
    **Promote**.
  - Render → service → **Deployments** → **Re-select commit** → deploy.
- **Debug**:
  - Render → service → **Logs** (live, searchable per request).
  - Vercel → project → **Logs**.
  - API health: `https://<api>/api/v1/health`.
  - API docs: `https://<api>/docs` (Swagger UI) — handy for testing.
- **CI**: GitHub Actions runs API tests + web build on every push/PR
  (green check on the commit).

## Data & backups

- Your data lives in Render's managed Postgres.
- **Backups**: free tier → take a manual backup occasionally
  (Render → database → **Backups → Create backup**, then download the
  `.sql` dump). Or `pg_dump` on demand.
- **User erasure** works in-app (Settings → Delete everything) and also
  via `DELETE /api/v1/profiles/{id}`.
- Reference documents are stored in the database itself, so they survive
  deploys. (Upgrade path when scale demands: encrypted object storage.)

## Security checklist (already in place)

- No secrets in the repo — everything via Render/Vercel env vars
  (`CF_DATABASE_URL`, `CF_CORS_ORIGINS`, …). `.env*` is git-ignored.
- Production API **refuses to start** without a PostgreSQL URL.
- Consent-gated sensitive actions; erasure is complete.
- Job feeds: permitted public sources only, per-source feature flags.

## Optional later

- Adzuna key (more SA listings): create a free account at adzuna.com,
  add `CF_ADZUNA_APP_ID` + `CF_ADZUNA_API_KEY` on Render, and set
  `CF_JOB_SOURCES` to `'["wwr","remoteok","remotive","adzuna"]'`
  (Settings → Environment → add a variable).
- Gmail OAuth: create a free Google Cloud OAuth client, add the
  client id/secret as Render env vars when the Gmail module lands.
- Custom domain: buy a domain (or use a free subdomain), point it at
  Vercel in **Settings → Domains**.
