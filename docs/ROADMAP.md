# CareerForge Pro roadmap

## Product north star (user-confirmed 2026-08-24)

The goal is **qualified interview conversion for candidates who have been
unemployed for six months or more** — not volume of CVs sent. The system is
an autonomous career agent: the candidate uploads their CV and the program
does the rest (analysis, target roles, three masters, job matching, per-job
CV, cover letter, voice/video responses, outreach drafts, tracking,
follow-ups). Sensitive actions surface in a single approval queue.

**The Voice/Video Application Studio is a main feature** (many applications
request recorded responses), not a later-phase add-on. Video responses up to
3 minutes.

## Phase 1 — Stable CV-first core

- Candidate profile and consent
- PDF/DOCX parsing
- Evidence-backed CV analysis
- Three master CVs and unlimited custom versions
- Job-specific tailoring
- DOCX/PDF/plain-text export
- Cover letters
- Application tracker

## Phase 2 — Job and recruiter discovery

- Approved/licensed job feeds
- Indeed, CareerJunction, PNet, and permitted LinkedIn public job data
- Deduplication and freshness checks
- SA eligibility, timezone, payment, and work-authorisation filters
- Public recruiter/job-poster details only

## Phase 3 — Communication and references

- Gmail OAuth drafts
- Approved references and attachments
- Follow-up reminders
- Consent, suppression, and deletion controls

## Phase 4 — Media and coaching

- Voice application studio
- Video recording and enhancement
- Consent-based image/voice workflows
- Interview coach
- Portfolio builder

### Video/voice requirements (user-confirmed 2026-08-24)

- Response lengths up to **3 minutes** (presets 30s / 60s / 90s / 2min / 3min) — many applications request 3-minute videos.
- Candidate pastes the exact employer question plus instructions: key points, exclusions, tone, length.
- Script generated from CV + job description + question; multiple questions per application, each with its own saved response and version history.
- Browser recording with teleprompter, captions, transcript, trimming, audio cleanup, lighting/framing guidance, MP4/MP3 export.
- Upload-and-enhance existing video: audio, lighting/colour, framing, pauses, captions, background; approved headshot as thumbnail/intro card/profile panel.
- Optional consented image/voice likeness production (disclosed, audited, candidate-approved). Default: real recording + professional enhancement.
- Quality checks before export: addresses the question, within requested length, pacing, pauses, audio clarity, lighting, correct company/role names, no unsupported claims, captions match speech.

## Hosting and operations (user-confirmed 2026-08-24)

- Must run smoothly and easily: one-click local launcher, zero-config startup, readable diagnostics.
- Hosted: changes go live quickly via automatic deployments from GitHub, with preview URLs, health checks, one-click rollback, and live debug/fix workflow.
- Must behave like a paid product: autosave, no lost work, no broken links, helpful error codes, monitoring.

## Reliability requirements

- GitHub source control
- Automated tests on pull requests
- Preview deployments
- Production health checks
- Monitoring and error reporting
- Database and storage backups
- One-click rollback
- No secrets committed to the repository
