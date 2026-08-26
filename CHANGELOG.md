# Changelog

## 0.17.0 - 2026-08-26

Tailored CVs now **re-write** for the job, not just reorder (user
request: "give the best keywords and details"):

- **Summary rewrite** — gains a targeting sentence using only
  JD keywords the candidate's own CV already supports
  ("…applying to the Customer Success Manager role with direct
  experience in Stakeholder Management, SaaS"). Generic words and
  keywords inside the job title are filtered; unsupported keywords are
  never claimed.
- **Bullet re-labels** — matching bullets are rewritten in the job's
  own wording via a conservative domain bridge table
  ("Customer Success: led a remote team of 4 support agents…",
  "Retention: built a knowledge base…"). The underlying fact is never
  changed (numbers/claims preserved, up to 4 per CV).
- **Experience reordering** — the role with the most JD-relevant
  content leads the CV (chronology preserved within ties).
- Full transparency in the report + UI: which keywords were added to
  the summary, which bullets were re-written (and how), and whether
  roles were reordered. Gaps are still flagged, never filled in.
- 159 API tests passing (9 new engine + integration tests), web build
  green, contract re-exported

## 0.16.0 - 2026-08-26

Custom versions now visibly reposition for the chosen role (bug fix:
typing "marketing" produced a CV identical to the base CV):

- **Role-targeted headline** on custom versions
  (e.g. "Marketing | 7 yrs experience | Johannesburg")
- **Honest pivot summary** built from real data only: the candidate's
  actual latest title + years, plus the role-relevant skills they
  genuinely have ("bringing data analysis and stakeholder management
  to operations") or an explicit "moving into {role}" when none
  match. Never claims role experience.
- **Transparent notes under each custom version** in the UI: which
  skills matched the role (and were moved to the front) or — when
  nothing matches — "No marketing-specific skills found in your CV
  yet… add real marketing experience to strengthen it", plus what was
  emphasised/excluded. Notes are UI-only, never part of the exported
  CV.
- 152 API tests passing (2 new), web build green, contract re-exported

## 0.15.0 - 2026-08-26

CV builders are now **role-based, not style-based** (user correction:
"ATS Enterprise and Modern Professional are not job roles"):

- `build-masters` now finds up to **three roles the candidate's own CV
  already matches** (skill overlap with the role keyword sets - the
  same transparent recommender behind "recommend roles") and builds one
  master per role, e.g. *Master CV — Customer Support*,
  *Master CV — Project Management*, *Master CV — Operations*.
- Every master is single-column and parser-safe; each is reordered so
  that role's skills and matching bullets come first. Fallbacks for
  thinner profiles: the candidate's latest real title, then a generic
  remote role. `role_focus` still pins the first master to a chosen
  role.
- The autonomous application flow (create application / auto-pipeline)
  builds the same role-based set, pinned to the job title.
- Old ATS Enterprise / Modern Professional versions stay exported as-is
  (legacy label in the UI).
- 150 API tests passing (2 new: one-per-top-role + pin-role-first),
  contract unchanged, web build green

## 0.14.0 - 2026-08-26

Job Finder: **English-speaking jobs only** (user requirement):

- Every job posting is now classified at ingest: `english` | `other` |
  `unknown`, via a transparent multilingual heuristic (function-word
  comparison across EN/DE/FR/ES/PT + non-Latin script detection — no
  ML, no network calls, nothing invented).
- Search filters to **English-only by default** (`english_only=true`);
  unclassified jobs are hidden from the default view but remain visible
  with the toggle off. The Job Finder page has an "English-speaking
  jobs only" checkbox (on by default) and it's part of saved searches.
- Existing jobs in production are classified automatically: a
  backfill runs at startup and after every sync (idempotent, cheap).
- 149 API tests passing (8 new: detector for EN/DE/FR/CJK/short text,
  normalize, filter on/off, backfill), web typecheck+build green,
  OpenAPI contract re-exported

## 0.13.0 - 2026-08-26

3-touch follow-up sequences + one-click local launcher:

- **3-touch follow-up sequences** (Phase 3 feature complete): start a
  sequence on any applied/phone-screen application — Standard (5/10/17
  days), Quick (3/7/12) or Gentle (7/14/21). Each touch gets its own
  plain, human draft written from your real CV (touch 1 uses real
  evidence; touch 3 is an explicit "last note").
- **Etiquette enforced server-side**: at most one outstanding follow-up
  — touch 2's Gmail draft is blocked until touch 1 is marked sent or
  skipped; follow-ups stop being draftable once the application moves
  to interview/offer/rejected.
- **Follow-up → Gmail draft**: reuses the drafts-only Gmail connection;
  recipient must be a non-suppressed recruiter contact matching THIS
  job (title, then company) with a published email — wrong-company
  follow-ups are impossible; shared 20/hour throttle with outreach.
- UI: application page shows touch chips, due/overdue, sent/skipped
  states, sequence picker, and per-touch "Create Gmail draft" /
  "Open in Gmail".
- **One-click local launcher** (reliability spec): `start.command`
  (macOS double-click) / `start.bat` (Windows double-click) /
  `start.sh` (terminal). First run creates the venv + installs web
  deps; then both servers start with readiness checks and a status
  banner; Ctrl-C / closing the windows stops everything. Smoke-tested
  live (API + web + same-origin proxy all green).
- 141 API tests passing (8 new), web typecheck+build green, OpenAPI
  contract re-exported, README updated

## 0.12.0 - 2026-08-26

Video Studio: trimming, headshot intro card, thumbnail:

- **Trim** — cut any [start, end] range out of a take → new MP4
  (background job, validated against the measured duration, originals
  untouched)
- **Approved headshot** — upload (JPG/PNG/WebP, ≤5 MB) stored privately
  against the video response, gated by the same likeness confirmation
- **Intro card** — 2–10s 1280×720 card (name, role, headshot) prepended
  to the latest video → MP4. Name/role default from the profile +
  latest CV role. Rendered with Pillow (fonts committed to the repo, so
  it works on hosts without system fonts — the bundled ffmpeg has no
  drawtext)
- **Thumbnail** — 1280×720 PNG frame for application portals, made
  automatically with the intro card
- API: `media/{mid}/trim`, `media-headshot`, `intro-card` (all jobs
  where heavy); 4 new tests (133 total), web typecheck+build green,
  OpenAPI contract re-exported

## 0.11.1 - 2026-08-25

- README endpoint list updated with the Video Studio media + Gmail
  outreach routes
- Render auto-deploy switched to On Commit on both services (previous
  "After CI Checks Pass" mode was not triggering); this commit doubles
  as the end-to-end verification (health reports 0.3.1 once live)

## 0.11.0 - 2026-08-25

Gmail Outreach (Phase 3 module ships, drafts-only by design):

- **Candidate's own Google account** via OAuth 2.0 (candidate-provided
  free OAuth client, setup in `docs/GOOGLE_SETUP.md`). The app stores
  no Google credentials of its own.
- **Least-privilege scope: `gmail.modify`** — the app can create
  drafts in the candidate's Gmail and nothing else (no read, no send,
  no contacts). The candidate always clicks send themselves.
- Refresh token stored Fernet-encrypted at rest (env key
  `CF_OAUTH_SECRET_KEY` or auto-generated DB key).
- Draft creation per recruiter contact: reuses the real-evidence
  outreach writer; hard gates — outreach consent, not suppressed,
  confirmed email only, Gmail connected, **20 drafts/hour** throttle.
- Every filed draft is recorded (to/subject/body/gmail draft id) and
  listed on the new Outreach page with "Open in Gmail".
- UI: Settings + Outreach connect/disconnect (popup sign-in with
  polling), Recruiter Finder "Create Gmail draft" button, Outreach
  page no longer a stub.
- API: `gmail/status`, `gmail/authorize`, `gmail/oauth/callback`,
  `gmail/disconnect`, `outreach/drafts`, `recruiters/{id}/gmail-draft`.
- 129 API tests passing (10 new: state machine, consent gate,
  unconfigured 503, encrypted-at-rest token, suppression, no-email,
  throttle).

## 0.10.0 - 2026-08-25

Video Studio production build (the main feature lands):

- **Server-side media storage** — recordings/uploads are stored privately
  against the application (DB-backed, survives Render's ephemeral disk).
  Upload gate: purpose-scoped `media_use` consent **plus** an explicit
  likeness confirmation (face/voice are yours or you have permission),
  recorded on the video response.
- **Quality checks (transparent, file-based)** — length vs target and
  3-minute cap, resolution, frame rate, audio presence, loudness, pauses
  (silence detection), lighting (luma). Pass/warn/fail with plain-language
  tips; the report is stored with the file. No invented scores.
- **Real enhancement** (bundled static ffmpeg, H.264/AAC output):
  colour & lighting (eq), audio normalisation (loudnorm to -16 LUFS),
  framing (16:9 letterbox, 9:16 vertical, 1:1 square), caption burn-in.
  Runs as a background job so long renders never hit free-tier request
  timeouts; the original file is never modified.
- **Captions (WebVTT)** — built from the candidate's own transcript or
  their script, timed proportionally across the measured duration,
  previewable and downloadable, burnable into the video. Clearly labelled
  as text-based timing, not speech recognition.
- **Exports** — MP4 (H.264, faststart) conversion of WebM/MOV originals,
  enhanced MP4, and MP3 audio extraction.
- API: `media-upload`, `analyze`, `enhance`, `export-mp4`,
  `export-audio`, `captions`, `download`, `delete`, `jobs/video/{id}`;
  `VideoOut` now carries `media[]` and `likeness_consent`.
- 119 API tests passing (6 new end-to-end tests run the real encode
  pipeline: upload → quality → captions → 9:16 enhance with burned
  captions → MP3 → MP4 conversion).

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
