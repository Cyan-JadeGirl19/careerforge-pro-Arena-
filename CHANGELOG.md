# Changelog

## 0.9.0 - 2026-08-24

Skills & Salary + Portfolio Builder (Phase 3/4 completion):

- Skills gap analysis vs any target role: present/missing skills,
  high-ROI flag (skills other target roles also need)
- Free-course catalogue (SQLBolt, freeCodeCamp, HubSpot Academy,
  Google certificates on Coursera, Microsoft Learn, Atlassian,
  The Odin Project) with URLs, dated (2026-08) and "verify before
  enrolling" notes
- 90-day learning plan: weeks 1-9 split across up to 3 skills
  (course + real project), weeks 10-12 applying
- Directional salary benchmarks (USD + ZAR monthly) for common
  remote roles open to Africa, with LIVE USD/ZAR rate
  (open.er-api.com, static fallback labelled), and an explicit
  disclaimer: not income promises, not tax/legal advice (SARS
  pointer included)
- Negotiation scripts (opening, evidence anchoring,
  geo-adjustment pushback, payment structure) + contractor
  payment guidance (Deel/Wise/Payoneer/EOR)
- Portfolio Builder: projects, GitHub repos (auto-pull public
  repo metadata + README, one user-directed fetch), writing
  samples, design, links; feature/approve/delete; public
  portfolio page renders APPROVED items only
- 113 API tests passing; both modules verified live end-to-end

## 0.8.0 - 2026-08-24

Follow-ups + Interview Coach:

- Follow-ups auto-scheduled by the program: 5 days after 'applied',
  3 days after 'interview' (one per kind, no duplicates), with a
  plain-language draft the candidate edits and sends themselves
- Dashboard 'Follow-ups to send' card (due/overdue, draft preview,
  mark sent/skip) and per-application follow-up section with manual
  scheduling
- Manual follow-up drafts are consent-gated (outreach_sending);
  marking sent/skipped is bookkeeping and needs no consent
- Interview Coach: mock interview for any target role, optionally
  grounded in a specific job's JD; categories: Core, Behavioural
  (STAR from real CV bullets), Role-specific (JD keywords),
  Red flag/gap (auto-detected employment gaps), South Africa remote
  set (time zones, setup, payments, why-SA), Close
- Prepared answers are STAR scaffolds built from the candidate's OWN
  CV content; [Add: …] markers show what is genuinely the
  candidate's to write - nothing is invented
- Practice mode: one question at a time, answer out loud, reveal
  prepared answer
- 103 API tests passing; both flows verified live end-to-end

## 0.7.0 - 2026-08-24

References Manager (Phase 3, first slice):

- Private Reference Manager: name, title, relationship, company,
  email/phone, type (current/former/academic/personal), notes
- Reference letters/lists upload (PDF/DOCX/TXT, 5 MB), private storage,
  download + delete
- Reference list parser: names + contacts extracted from uploaded
  lists; every parsed reference starts permission-UNCONFIRMED
- Permission confirmation is mandatory before any sharing; revocation
  clears the confirmation timestamp
- Application integration: "does the employer ask for references?"
  (yes/no/unspecified), select confirmed+approved references, attach
  per application, warnings for missing contact details, downloadable
  reference sheet (TXT)
- References hidden from CVs by default (they only exist on the
  application package)
- Erasure deletes references, documents, and private storage files
- 93 API tests passing; live flow verified end-to-end

## 0.7.1 - 2026-08-24 (references UI)

- References Manager page: add form with permission checkbox,
  list upload + parse, permission/approve toggles, document
  upload/download/delete per reference
- Application detail: references section (requested yes/no/unspecified,
  eligible-reference selection with inline warnings, save per
  application, reference sheet download)

## 0.6.0 - 2026-08-24

Recruiter Finder (Phase 2, second slice):

- Extract publicly displayed recruiter/poster details from one
  user-provided public page (names via strict validated patterns,
  public LinkedIn /in/ URLs, published emails)
- Compliance-critical: only VISIBLE page text is read - scripts and
  ad pixels are stripped first (verified against a real page whose
  adroll_email pixel would have produced a false contact)
- Nav/footer fragments rejected as names (strict candidate
  validation); pattern-suggested emails clearly labelled unverified
- Manual contacts, verify, suppress, delete; source + date kept
- Outreach DRAFTS (never sent): personalised from the candidate's
  real CV + the job, plain language, banned-phrasing checked,
  unverified-email and no-email warnings surfaced
- Consent-gated: recruiter_contact for discovery, outreach_sending
  for drafts
- 83 API tests passing; live flow verified end-to-end

## 0.5.0 - 2026-08-24

Job Finder (Phase 2, first slice):

- Live job feeds from permitted public sources only: We Work Remotely
  (RSS), RemoteOK (JSON), Remotive (API), Adzuna (official API, optional
  free key - best for SA listings). LinkedIn/Indeed/PNet/CareerJunction
  are NOT scraped (no permitted public feed); any single job can be
  added by pasting its link (user-directed).
- Per-source feature flags + per-source error isolation: one broken
  source never stops the app
- SA-eligibility signals computed transparently from employer text
  (open to SA: yes/no/unknown, timezone, Deel/Wise/Payoneer/EOR
  payment signals, remote/hybrid/onsite)
- Transparent match scoring with visible weights (skills 40,
  experience 20, keywords 20, feasibility 10, freshness 10)
- Deduplication + freshness; saved searches
- One-click hand-off: job -> application package (best CV version,
  tailored CV, cover letter) with nothing submitted
- Web UI: refresh, filters, eligibility + payment chips, match
  breakdown, job detail, add-by-link, saved searches
- 69 API tests passing; live sync verified (180 real jobs ingested)

## 0.4.0 - 2026-08-24

Autonomous studio (the "upload your CV, the program does the rest" layer):

- Target-role recommendation: top-3 roles from the candidate's own skill
  overlap, with matched/missing evidence and reasons
- Application packages: one record per job tying together the tailored
  CV, cover letter, video responses, and tracker status
  (saved → ready → applied → phone screen → interview → offer →
  rejected → archived)
- Human-authentic cover letters: factual only, one concrete JD
  requirement quoted, no banned AI-style phrasing (checked), unique per
  job, acronym-aware
- Voice/Video Application Studio (server): question + instructions
  (key points, exclusions, tone) + length 30/60/90/120/180s → natural
  spoken script from the candidate's real CV + JD; per-question
  responses with version history; consent-gated (video_recording,
  media_use for AI-assisted modes); scripts are never padded with
  invented content
- Auto-pipeline endpoint: CV + job list → best-master selection,
  tailored CV, cover letter, video script per job in one call,
  surfaced as a review queue. Nothing is sent or submitted.
- Regression fixes: years-of-experience regex (capture-group bug that
  produced "40 years"), acronym preservation in speech/letters,
  requirement-phrase extraction from JDs
- 52 API tests passing; OpenAPI contract re-exported

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
