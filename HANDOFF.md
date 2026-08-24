# CareerForge Pro — session handoff

Date: 2026-08-24

## Product mission

CareerForge Pro is a free, CV-first career acceleration platform for South Africans pursuing remote work globally. It is designed for people who may have been job hunting for six months or more. The primary success metric is qualified interview conversion, not number of CVs sent.

Core flow:

**Upload CV → Analyse → Build three master CVs → Choose target roles → Find suitable jobs → Tailor CV per job → Cover letter → Voice/video response when required → Review/approve → Apply → Follow up → Track → Learn and improve**

## Agreed product requirements

### CV-first autonomous flow

After CV upload, the program should do as much of the work as possible:

- Parse and structure the CV.
- Identify missing information, weak bullets, formatting issues, and unsupported claims.
- Recommend the three strongest target roles.
- Build three master CV versions.
- Find suitable jobs through permitted sources.
- Select the best CV version for each job.
- Tailor a CV to each serious application.
- Generate a cover letter and application answers.
- Find permitted public recruiter/job-poster details.
- Prepare outreach drafts.
- Add approved references when requested.
- Create tracker records and reminders.
- Recommend next actions and learn from outcomes.

The system is a human-supervised autonomous career agent: it performs preparation automatically, but sensitive actions require approval.

### Three master CV versions

1. ATS Enterprise: single column, parser-safe, no graphics/tables/text boxes.
2. Modern Professional: ATS-safe with subtle visual hierarchy.
3. Role Specialist: focused on the strongest target role.

The candidate can also request unlimited custom versions, e.g. a Marketing CV even if marketing was not one of the initial top three. Custom versions must be downloadable as DOCX, PDF, plain text, and JSON.

Every application should receive a job-specific tailored version. Do not promise a universal 95% ATS score. Instead report transparent ATS compatibility, keyword coverage, formatting checks, and gaps. The CV must be tailored for relevance and recruiter visibility.

### Truth and metrics

Never fabricate employers, degrees, certifications, responsibilities, achievements, or metrics. The program may suggest where a metric would strengthen a bullet and ask targeted questions, but unconfirmed estimates must be clearly labelled and approved by the candidate before use.

### Human writing

CVs, cover letters, emails, interview answers, LinkedIn content, and portfolio copy must be plain, specific, natural, and candidate-voiced. Avoid generic AI-style language, clichés, keyword stuffing, and unnecessary jargon. Do not promise AI-detector bypassing. Recruiters should see truthful, relevant, human-sounding writing.

### Job and recruiter discovery

Requested sources include Indeed, CareerJunction, PNet, and LinkedIn, plus remote boards and company career pages. Use approved APIs, licensed data, public listings where permitted, RSS/feeds, or user-provided URLs. Do not bypass logins, CAPTCHAs, robots rules, access controls, or platform terms.

Recruiter finder may collect publicly displayed poster/recruiter names, titles, company, public profile URL, public business email, and source/verification date. Guessed email patterns must be labelled unverified. No hidden/private email harvesting or mass spam. Outreach requires consent/legitimate-interest review, throttling, unsubscribe handling, POPIA/GDPR safeguards, and user approval before sending.

### Video and voice application studio — main feature

This is a core module because many modern applications request recorded responses, especially in customer support, sales, recruitment, education, hospitality, media, and remote roles.

Capabilities:

- Candidate pastes the exact employer question.
- Candidate provides instructions, key points, exclusions, desired tone, and length.
- Generate a tailored 30/60/90-second natural script from CV, JD, and question.
- Support multiple questions and separate saved responses for every application.
- Browser recording, teleprompter, captions, transcript, trimming, audio cleanup, lighting/framing guidance, export.
- Upload an existing video and improve audio, lighting, colour, framing, pauses, captions, and background.
- Use a different approved candidate headshot as thumbnail, intro card, or profile panel.
- Optional consented image/voice likeness production using the candidate’s own approved media.

Safeguards: explicit consent, candidate owns/controls media, final approval, no impersonation, no identity verification/live interview use, no invented claims, private-by-default storage, deletion/revocation controls, disclose synthetic/heavily reconstructed media where appropriate. Default should be real recording plus professional enhancement.

### References

Private Reference Manager module:

- Name, title, company, relationship, email/phone, type, notes.
- Upload reference letters/reference lists.
- Permission confirmation.
- References hidden from CV by default.
- Include only when requested or explicitly selected.
- Candidate approval before sharing.
- Encrypt/delete in production.

### UI/UX

Professional, beautiful, mobile-first, accessible, easy to use, minimal clicks. Every module has its own dedicated space and must not lose functionality:

- Dashboard
- CV Studio
- Cover Letter Builder
- Job Finder
- Recruiter Finder
- Voice/Video Application Studio
- Gmail Outreach
- Application Tracker
- Interview Coach
- Skills and Salary
- Portfolio Builder
- References and Profile
- Settings / Privacy

Dashboard is the central action and approval queue. Show clear progress, autosave, status, helpful errors, no broken links or blank screens.

### Reliability and production

Must behave like a dependable paid product even though free:

- Modular frontend/backend architecture.
- Proven stack: Next.js/React, FastAPI, PostgreSQL, encrypted object storage.
- GitHub source control.
- CI tests on pull requests.
- Preview deployments before production.
- Automated health checks, error monitoring, structured logs, uptime monitoring.
- Automatic backups, restore plan, one-click rollback.
- Feature flags to disable broken integrations without taking down app.
- Environment validation and no secrets committed.
- Shared typed API contracts, versioned routes, no hardcoded browser localhost URLs.
- Unit, API, browser, mobile, accessibility, upload, export, security, and end-to-end tests.
- Staged releases; core CV flow first, integrations later.
- Autosave and version history so work is never lost.
- Clear user-facing error codes and support diagnostics.

Hosted changes should go: code → tests → preview → review → production health check → automatic rollback on failure. A one-click/local launcher can be provided for development, but production should use a stable hosted URL.

## Current workspace files

- `index.html`: no-build interactive MVP; dashboard, CV keyword analysis, mock SA-oriented jobs with source filters, outreach draft, tracker, settings.
- `README.md`: project overview and local run instructions.
- `REVIEW.md`: product, compliance, and architecture review.
- `CHANGELOG.md`: initial history.
- `docs/ROADMAP.md`: phased roadmap.
- `.gitignore`: secrets, dependencies, builds, local data.
- `careerforge-pro-mvp.zip`: downloadable package for GitHub web upload.
- `HANDOFF.md`: this handoff document.

## Local Git state

Repository initialized at `/home/user`.
Branch: `main`.
Remote:

`https://github.com/Cyan-JadeGirl19/careerforge-pro-Arena-.git`

Commits:

- `e7ff55f Create CareerForge Pro CV-first MVP prototype`
- `f4b021b Add repository documentation and roadmap`
- Current handoff commit should be created after this file is added.

## GitHub status

Repository was confirmed public and empty via GitHub web. Local remote and branch are correct. Push from this workspace failed because GitHub credentials are not exposed to the workspace (`could not read Username for 'https://github.com'`). Do not paste a token into chat. If no Arena repository connector is available, upload the contents of `careerforge-pro-mvp.zip` through GitHub’s web interface.

## Next recommended build steps

1. Commit this handoff.
2. Expand MVP into a real project structure while preserving current functionality.
3. Build candidate profile schema and consent model.
4. Add CV PDF/DOCX parsing and evidence-backed analysis.
5. Add three master CV builder, custom versions, per-job tailoring, and export.
6. Add tests and GitHub Actions before major integrations.
7. Add approved job feeds and recruiter discovery.
8. Add references, Gmail drafts, and video studio.
9. Add production deployment, backups, monitoring, privacy/security review.

## Guardrails

Do not claim guaranteed interviews, universal 95% ATS, AI-detector passage, or 90% of jobs requiring videos without current evidence. Focus on measurable interview conversion and transparent methodology. Never bypass site protections or fabricate candidate information.
