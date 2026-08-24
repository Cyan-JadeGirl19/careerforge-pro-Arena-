# CareerForge Pro — review and MVP scope

## What changed in the specification

The brief is ambitious and has a strong user outcome, but several promises should be revised before production:

- **Do not promise ATS scores of 95% or AI-detector passage.** ATS implementations and AI detectors are opaque, variable, and often contradictory. Report transparent checks and job-description keyword coverage instead.
- **Never invent metrics.** A metric should be supplied by the candidate, backed by evidence, or clearly labelled as a placeholder to validate. Plausibility is not proof.
- **Treat scraping and auto-apply as gated integrations.** Use licensed APIs, feeds, or user-directed browser assistance; obtain consent and require review before submission. Do not bypass CAPTCHAs, access controls, or platform restrictions.
- **Email discovery needs a lawful basis and verification policy.** Avoid SMTP probing by default, minimize personal data, log consent/legitimate-interest decisions, and include unsubscribe controls.
- **Salary, tax, visa, and payment guidance needs dated sources and a disclaimer.** It should not present legal or tax advice as fact.
- **Separate MVP from platform scale.** Start with local CV analysis, job tracking, tailored documents, and export. Add OAuth, storage, job feeds, and automation only after privacy/security review.

## Included working MVP

`index.html` is a no-build, mobile-responsive prototype with:

- Dashboard with CV health, application metrics, and recommended roles
- Local CV text analysis with explainable keyword signals
- South-Africa-oriented mock job feed with match and feasibility labels
- Outreach draft composer that explicitly does not send email
- Application tracker Kanban
- Local-data deletion control

All data is mock/local in this prototype. No external assets, APIs, scraping, OAuth, Gmail connection, or automatic application submission is enabled.

## Recommended production phases

1. **Foundation:** authentication, consent, encrypted profile store, deletion/export, audit log.
2. **Core value:** PDF/DOCX parsing, evidence-backed CV editor, JD comparison, DOCX/PDF/plain-text export.
3. **Discovery:** licensed job feeds, deduplication, freshness, timezone/eligibility filters, source citations.
4. **Communication:** Gmail OAuth with least-privilege scopes, drafts first, rate limits, unsubscribe and suppression list.
5. **Assistance:** browser-side prefill with mandatory user confirmation; no unattended submissions.
6. **Trust:** benchmark methodology, source dates, accessibility testing, security assessment, POPIA/GDPR counsel.

## Important data model fields

Candidate evidence should include `claim`, `source`, `verified`, `last_verified_at`, and `candidate_approved`. Every generated document should retain `source_profile_version`, `job_description_version`, and `generation_timestamp`.
