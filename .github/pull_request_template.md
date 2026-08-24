## What

One paragraph: what this PR changes and why.

## Module

Dashboard / CV Studio / Cover Letter / Job Finder / Recruiter Finder /
Voice-Video Studio / Outreach / Tracker / Interview Coach / Skills-Salary /
Portfolio / References / Settings / Infra

## Checks

- [ ] `make test` (API) passes
- [ ] `cd apps/web && npm run typecheck && npm run build` passes
- [ ] OpenAPI contract re-exported if API changed (`make openapi`)
- [ ] No secrets, personal data, or mock candidate data in fixtures that looks real
- [ ] New sensitive action is consent-gated and documented
- [ ] UI states: empty, loading, error — no blank screens or dead buttons

## Screenshots / notes

(If relevant.)
