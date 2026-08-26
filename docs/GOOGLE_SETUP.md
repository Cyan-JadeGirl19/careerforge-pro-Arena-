# Gmail Outreach setup (candidate-provided Google OAuth client)

The Gmail module uses the **candidate's own free Google Cloud project**.
This keeps the app free, needs no paid Google quota, and means the app
stores no Google credentials of its own. Everything below is free and
takes ~10 minutes.

## What the app is allowed to do (and never)

- **Can:** create draft emails in the connected account's Gmail
  (scope: `gmail.modify` only).
- **Cannot:** read mail, send mail, see contacts, or use the account
  for anything else. The candidate always clicks send themselves.

## One-time setup (per deployment)

1. Go to https://console.cloud.google.com → create (or open) a project.
2. **APIs & Services → Library** → enable **Gmail API**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External** (you can test with your own account while
     in *Testing* status).
   - Fill in the app name (e.g. "CareerForge Pro") and your email.
   - Scopes: you can leave the default; the app only ever requests
     `gmail.modify`.
4. **APIs & Services → Credentials → Create credentials → OAuth client
   ID**:
   - Application type: **Web application**.
   - **Authorized redirect URI** (must match exactly):
     ```
     https://careerforge-api-h5yp.onrender.com/api/v1/gmail/oauth/callback
     ```
     (Change this if the API URL ever changes; keep it in sync with the
     `CF_GMAIL_REDIRECT_URI` env var.)
   - Create → copy the **Client ID** and **Client Secret**.

## Set env vars on Render (careerforge-api service → Environment)

| Key | Value |
|---|---|
| `CF_GOOGLE_CLIENT_ID` | the client ID from step 4 |
| `CF_GOOGLE_CLIENT_SECRET` | the client secret from step 4 |
| `CF_GMAIL_REDIRECT_URI` | *(optional)* default is the production API URL above |
| `CF_WEB_URL` | *(optional)* default is the production web URL |
| `CF_OAUTH_SECRET_KEY` | *(recommended)* any long random string — used to encrypt the stored Gmail refresh token. Without it the app generates one and stores it in the database. |

Redeploy after changing env vars.

## Verifying

- Settings / Outreach page → **Connect your own Google account** → sign
  in → the page returns and shows the connected address.
- Recruiter Finder → open a contact with a confirmed email → **Create
  Gmail draft** → it lands in the contact's … i.e. the *candidate's*
  Gmail **Drafts** folder.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Gmail is not configured on this deployment yet" (503) | Set `CF_GOOGLE_CLIENT_ID` / `CF_GOOGLE_CLIENT_SECRET` on Render and redeploy. |
| `redirect_uri_mismatch` from Google | The redirect URI in Google Console must match `CF_GMAIL_REDIRECT_URI` exactly (scheme + host + path). |
| "Could not refresh the Google token" on draft creation | Reconnect Gmail from Settings (tokens can be revoked by Google). |
| Connection not detected after sign-in | The popup window must stay open until the redirect lands on the Outreach page; then reload. |
