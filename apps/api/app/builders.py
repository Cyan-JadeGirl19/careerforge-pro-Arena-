"""CV version builders and per-job tailoring.

Rules enforced here (agreed product requirements):
- Never add employers, qualifications, certifications, or achievements
  that are not in the candidate's own source text.
- Metrics are only ever the candidate's own, or explicitly flagged in
  the report for confirmation.
- Tailored versions reorder and surface what the candidate actually has;
  missing requirements are reported as gaps, never filled in.
"""
import re
from datetime import datetime, timezone

from .content import (
    CvContent,
    EducationItem,
    ExperienceItem,
    LAYOUT_ATS,
    LAYOUT_MODERN,
    LAYOUT_ROLE,
)
from .parsing import ParsedCv

KIND_ATS = "master_ats"
KIND_MODERN = "master_modern"
KIND_ROLE = "master_role"
KIND_CUSTOM = "custom"

#: Role keyword sets for the Role-Specialist master and custom versions.
ROLE_KEYWORDS: dict[str, list[str]] = {
    "customer success": [
        "customer success", "customer service", "onboarding", "retention",
        "churn", "csat", "support", "satisfaction", "account management",
        "renewals", "upsell",
    ],
    "customer support": [
        "customer support", "customer service", "tickets", "csat", "sla",
        "escalations", "help desk", "satisfaction", "communication",
        "remote",
    ],
    "operations": [
        "operations", "process improvement", "workflow", "efficiency",
        "data analysis", "reporting", "stakeholder", "excel", "coordination",
        "compliance",
    ],
    "operations analyst": [
        "operations", "data analysis", "reporting", "excel",
        "process improvement", "stakeholder", "metrics", "workflow",
        "python", "sql",
    ],
    "marketing": [
        "marketing", "content creation", "social media", "campaigns",
        "seo", "email marketing", "copywriting", "analytics", "brand",
        "digital marketing",
    ],
    "data analysis": [
        "data analysis", "sql", "python", "excel", "reporting", "dashboards",
        "statistics", "visualisation", "power bi", "tableau",
    ],
    "frontend": [
        "frontend", "javascript", "typescript", "react", "html", "css",
        "accessibility", "responsive", "testing", "ui", "ux",
    ],
    "product": [
        "product", "user research", "roadmap", "stakeholder", "agile",
        "backlog", "a/b testing", "metrics", "ux",
    ],
    "sales": [
        "sales", "pipeline", "prospect", "negotiation", "crm", "revenue",
        "accounts", "outreach", "targets",
    ],
    "admin": [
        "administration", "data entry", "scheduling", "records", "filing",
        "correspondence", "excel", "organisation", "confidentiality",
    ],
    "project management": [
        "project management", "agile", "scrum", "jira", "stakeholder",
        "timeline", "budget", "delivery", "risk",
    ],
    "recruitment": [
        "recruitment", "talent acquisition", "sourcing", "screening",
        "interviewing", "onboarding", "ats", "employer branding",
    ],
}

#: Two/three-word skills recognised in job descriptions.
SKILL_PHRASES = [
    "customer success", "customer service", "project management",
    "data analysis", "stakeholder management", "process improvement",
    "time management", "team leadership", "quality assurance",
    "cross-functional", "risk management", "budget management",
    "business analysis", "financial analysis", "account management",
    "client relations", "market research", "content creation",
    "social media", "digital marketing", "email marketing",
    "technical writing", "user research", "product development",
    "graphic design", "supply chain", "inventory management",
    "report writing", "data entry", "power bi", "machine learning",
]

STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will",
    "have", "has", "that", "this", "from", "who", "what", "when", "where",
    "how", "why", "not", "but", "all", "can", "would", "should", "could",
    "able", "work", "working", "works", "role", "roles", "job", "jobs",
    "experience", "required", "required", "including", "include",
    "includes", "strong", "good", "excellent", "proven", "track", "record",
    "team", "teams", "environment", "company", "companies", "candidate",
    "candidates", "we", "us", "they", "their", "them", "then", "than",
    "more", "most", "other", "such", "each", "every", "any", "some",
    "new", "use", "used", "using", "well", "able", "plus", "also",
    "must", "may", "like", "one", "two", "three", "years", "year",
    "years", "relevant", "related", "knowledge", "skills", "skill",
    "understanding", "familiarity", "familiar", "ability", "abilities",
    "ensure", "ensures", "help", "helps", "day", "daily", "across",
    "within", "between", "into", "over", "under", "after", "before",
    "while", "during", "based", "via", "per", "etc", "e.g", "i.e",
    "remote", "hybrid", "on-site", "site", "full-time", "part-time",
    "benefits", "salary", "compensation", "benefit", "offer", "offers",
    "apply", "application", "applications", "qualifications",
    "responsibilities", "requirements", "preferred", "ideal", "about",
    "who", "whom", "which", "those", "these", "there", "here", "now",
}


def _year_values(text: str) -> list[int]:
    return [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", text)]


def _years_of_experience(parsed: ParsedCv) -> int | None:
    years = []
    for entry in parsed.experience:
        years.extend(_year_values(entry.get("dates", "")))
    if not years:
        return None
    earliest = min(years)
    span = datetime.now(timezone.utc).year - earliest
    return max(0, min(span, 40))


def _latest_role(parsed: ParsedCv) -> str:
    for entry in parsed.experience:
        if entry.get("title"):
            return entry["title"].strip()
    return ""


def _factual_summary(parsed: ParsedCv, role_focus: str | None = None) -> str:
    """Draft a summary strictly from the candidate's own data."""
    if parsed.summary:
        return parsed.summary
    parts: list[str] = []
    role = role_focus or _latest_role(parsed)
    span = _years_of_experience(parsed)
    if role and span:
        parts.append(f"{role} with {span} years of experience.")
    elif role:
        parts.append(role + ".")
    top = next(
        (b for e in parsed.experience for b in e["bullets"] if re.search(r"\d", b)),
        None,
    )
    if top:
        parts.append("Most recently: " + top.strip().rstrip("."))
    skills = parsed.skills[:4]
    if skills:
        parts.append("Core strengths: " + ", ".join(skills) + ".")
    return " ".join(parts)


def _order_skills(skills: list[str], prefer: list[str]) -> list[str]:
    """Move preferred (role/JD) skills forward without duplicates."""
    lowered = {s.lower(): s for s in skills}
    ordered: list[str] = []
    for p in prefer:
        hit = lowered.get(p.lower())
        if hit and hit not in ordered:
            ordered.append(hit)
    for s in skills:
        if s not in ordered:
            ordered.append(s)
    return ordered


def _relevance(bullet: str, keywords: list[str]) -> int:
    low = bullet.lower()
    return sum(1 for k in keywords if k in low)


def _build_content(parsed: ParsedCv, layout: str, role_focus: str | None) -> CvContent:
    years = _years_of_experience(parsed)
    latest = _latest_role(parsed)
    headline_bits = [b for b in (latest, f"{years} yrs experience" if years else None, parsed.location) if b]
    content = CvContent.from_dict(
        {
            **parsed.content_kwargs(),
            "headline": " | ".join(headline_bits),
            "summary": _factual_summary(parsed, role_focus),
            "skills": list(parsed.skills),
            "experience": list(parsed.experience),
            "education": list(parsed.education),
            "certifications": list(parsed.certifications),
            "projects": list(parsed.projects),
            "languages": list(parsed.languages),
            "layout": layout,
            "role_focus": role_focus,
        }
    )
    return content


def build_master_ats(parsed: ParsedCv) -> CvContent:
    """ATS Enterprise: single column, parser-safe, keyword-forward."""
    content = _build_content(parsed, LAYOUT_ATS, None)
    # keyword-forward skill ordering (factual set, reordered only)
    return content


def build_master_modern(parsed: ParsedCv) -> CvContent:
    """Modern Professional: subtle hierarchy, impact-first ordering."""
    content = _build_content(parsed, LAYOUT_MODERN, None)
    # Impact-first: quantified bullets within each role move to the top.
    for e in content.experience:
        if e.bullets:
            quantified = [b for b in e.bullets if re.search(r"\d", b)]
            rest = [b for b in e.bullets if b not in quantified]
            e.bullets = quantified + rest
    return content


def build_master_role(parsed: ParsedCv, role_focus: str) -> CvContent:
    """Role Specialist: focused on the strongest target role."""
    content = _build_content(parsed, LAYOUT_ROLE, role_focus)
    keys = ROLE_KEYWORDS.get(role_focus.lower(), [role_focus.lower()])
    content.skills = _order_skills(content.skills, keys)
    for e in content.experience:
        if e.bullets:
            e.bullets = sorted(e.bullets, key=lambda b: _relevance(b, keys), reverse=True)
    return content


def top_roles_for_cv(parsed: ParsedCv, top_n: int = 3) -> list[str]:
    """The best-fit roles from the candidate's OWN profile.

    Primary signal: skill overlap with the role keyword sets (transparent,
    from app/roles.py). Fallbacks so a thinner profile still gets masters:
    the candidate's latest real title, then a generic remote role.
    """
    from .roles import recommend_roles

    roles = [r["role"] for r in recommend_roles(parsed, top_n=top_n)]
    latest = _latest_role(parsed)
    if latest and latest.lower() not in {r.lower() for r in roles}:
        roles.append(latest)
    if not roles:
        roles = ["Remote Professional"]
    seen: set[str] = set()
    out: list[str] = []
    for r in roles:
        if r.lower() not in seen:
            seen.add(r.lower())
            out.append(r)
    return out[:top_n]


def _prettify_term(term: str, skills: list[str]) -> str:
    """Prefer the candidate's own fuller skill wording ("stakeholder
    management" over the bare keyword "stakeholder")."""
    for s in skills:
        if term.lower() in s.lower():
            return s
    return term


def _custom_summary(parsed: ParsedCv, role_focus: str, keys: list[str]) -> str:
    """Honest repositioning summary for a custom role.

    If the role matches the candidate's latest title, keep the factual
    summary. Otherwise build a pivot summary strictly from real data:
    their actual latest title + years, plus the role-relevant skills
    they genuinely have. Never claims role experience.
    """
    if parsed.experience and (parsed.experience[0].get("title") or "").lower() == role_focus.lower():
        return _factual_summary(parsed, role_focus)
    years = _years_of_experience(parsed)
    latest = _latest_role(parsed)
    opener = (
        f"{latest} with {years} years of experience"
        if latest and years
        else latest or "Professional"
    )
    corpus = (
        parsed.summary
        + " "
        + " ".join(parsed.skills)
        + " "
        + " ".join(b for e in parsed.experience for b in e.get("bullets", []))
    ).lower()
    matched = [
        _prettify_term(k, parsed.skills)
        for k in keys
        if len(k) > 3 and k.lower() in corpus and k.lower() != role_focus.lower()
    ]
    if matched:
        return (
            f"{opener}, bringing {', '.join(m.lower() for m in matched[:3])} "
            f"to {role_focus}."
        )
    strengths = [s for s in parsed.skills[:2]]
    extra = ""
    if strengths:
        extra = (
            " My profile shows solid "
            + " and ".join(s.lower() for s in strengths)
            + "."
        )
    return f"{opener}, moving into {role_focus}.{extra}"


def build_custom(
    parsed: ParsedCv,
    role_focus: str,
    emphasize: list[str] | None = None,
    exclude: list[str] | None = None,
) -> tuple[CvContent, list[str]]:
    """Unlimited custom versions, e.g. a Marketing CV from operations
    experience. Repositions genuine, transferable experience only and
    returns transparent notes explaining what matched / what's missing.
    """
    content = _build_content(parsed, LAYOUT_ROLE, role_focus)
    keys = list(emphasize or [])
    keys += [
        k
        for k in ROLE_KEYWORDS.get(role_focus.lower(), [role_focus.lower()])
        if k not in [x.lower() for x in keys]
    ]

    # Role-targeted headline (positioning for the target role; the
    # summary below stays strictly factual).
    years = _years_of_experience(parsed)
    headline = [role_focus]
    if years:
        headline.append(f"{years} yrs experience")
    if parsed.location:
        headline.append(parsed.location)
    content.headline = " | ".join(headline)
    content.summary = _custom_summary(parsed, role_focus, keys)

    content.skills = _order_skills(content.skills, keys)
    for e in content.experience:
        if e.bullets:
            e.bullets = sorted(e.bullets, key=lambda b: _relevance(b, keys), reverse=True)
    if exclude:
        excl = [x.lower() for x in exclude]
        drop = lambda t: any(x in t.lower() for x in excl)  # noqa: E731
        content.skills = [s for s in content.skills if not drop(s)]
        for e in content.experience:
            e.bullets = [b for b in e.bullets if not drop(b)]
        content.projects = [p for p in content.projects if not drop(p)]
        content.certifications = [c for c in content.certifications if not drop(c)]

    notes: list[str] = []
    corpus = (
        parsed.summary
        + " "
        + " ".join(parsed.skills)
        + " "
        + " ".join(b for e in parsed.experience for b in e.get("bullets", []))
    ).lower()
    matched = [
        _prettify_term(k, parsed.skills)
        for k in keys
        if len(k) > 3 and k.lower() in corpus and k.lower() != role_focus.lower()
    ]
    if matched:
        notes.append(
            f"Skills matched to {role_focus}: {', '.join(matched[:5])} - moved to the front."
        )
    else:
        strengths = ", ".join(s.lower() for s in parsed.skills[:3])
        notes.append(
            f"No {role_focus}-specific skills found in your CV yet, so this version "
            "emphasises your transferable strengths"
            + (f" ({strengths})" if strengths else "")
            + f". Add real {role_focus} experience to your CV to strengthen it."
        )
    if emphasize:
        notes.append("Emphasised: " + ", ".join(emphasize[:6]) + ".")
    if exclude:
        notes.append("Excluded: " + ", ".join(exclude[:6]) + ".")
    return content, notes


# --- job description keywords ---------------------------------------------


def extract_jd_keywords(jd_text: str, top_n: int = 24) -> list[str]:
    low = jd_text.lower()
    counts: dict[str, int] = {}
    for phrase in SKILL_PHRASES:
        if phrase in low:
            counts[phrase] = counts.get(phrase, 0) + 3
    for word in re.findall(r"[a-z][a-z.+#-]{2,}", low):
        w = word.strip(".,+#-")
        if len(w) < 3 or w in STOPWORDS or w.isdigit():
            continue
        counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [w for w, _ in ranked[:top_n]]


# --- tailoring rewrite engine ---------------------------------------------
#
# Curated, domain-conservative bridges: for a JD keyword, the surface
# forms that count as evidence a bullet already demonstrates it. Used
# ONLY to re-label a bullet in the job's own wording ("Customer support:
# resolved 25+ issues daily…") - the underlying fact is never changed.
# No bridge = no rewrite for that keyword.

KEYWORD_BRIDGES: dict[str, tuple[str, ...]] = {
    "customer support": ("ticket", "customer issue", "help desk", "support", "customer service", "customer inquiry"),
    "customer service": ("customer", "client", "service level", "sla", "inquiry"),
    "customer success": ("customer", "csat", "onboard", "retention", "renewal", "churn"),
    "retention": ("csat", "satisfaction", "repeat", "churn", "retain"),
    "churn": ("retention", "cancell", "satisfaction", "lost customer"),
    "account management": ("account", "client", "customer", "portfolio", "renewal"),
    "crm": ("salesforce", "hubspot", "zoho", "dynamics 365", "dynamics", "customer database"),
    "stakeholder management": ("stakeholder", "cross-functional", "cross functional"),
    "data analysis": ("excel", "sql", "data set", "dataset", "metric", "dashboard", "spreadsheet", "analytics"),
    "reporting": ("report", "dashboard", "metric", "spreadsheet", "kpi"),
    "process improvement": ("workflow", "efficien", "streamline", "optimis", "reduced", "faster", "improv"),
    "onboarding": ("onboard", "new customer", "new client", "induction", "kick-off", "kickoff"),
    "escalation": ("escalat", "complex issue", "priority issue", "urgent"),
    "team leadership": ("led a", "lead a", "managed a team", "mentored", "trained", "supervised"),
    "training": ("trained", "training", "mentor", "coach", "knowledge base"),
    "negotiation": ("negotiat", "pricing", "contract", "commercial", "vendor"),
    "sales": ("revenue", "pipeline", "prospect", "deal", "target", "quota"),
    "marketing": ("campaign", "content", "seo", "social media", "email list", "newsletter"),
    "content creation": ("content", "wrote", "writing", "copy", "article", "blog"),
    "email marketing": ("email", "newsletter", "campaign"),
    "product": ("roadmap", "backlog", "user research", "a/b", "feature"),
    "project management": ("project", "timeline", "delivery", "milestone", "scope"),
    "agile": ("sprint", "scrum", "agile", "jira", "backlog", "standup"),
    "quality assurance": ("quality", "test", "qa", "compliance", "standard"),
    "time management": ("priority", "deadline", "schedule", "concurrent", "simultaneous"),
    "communication": ("stakeholder", "present", "documentation", "wrote", "briefing", "escalat"),
    "documentation": ("documentation", "knowledge base", "wrote", "manual", "guide"),
}


def _label_for(keyword: str) -> str:
    if keyword.isalpha() and len(keyword) <= 4:
        return keyword.upper()
    return keyword.title()


def _relabel_bullet(bullet: str, keywords: list[str]) -> tuple[str, str | None]:
    """Prepend the best JD keyword label whose evidence the bullet
    already contains. Returns (new_bullet, keyword_or_None)."""
    low = bullet.lower()
    for kw in keywords:
        if kw in low:
            continue  # already in the job's own words
        bridge = KEYWORD_BRIDGES.get(kw)
        if not bridge:
            continue
        if any(term in low for term in bridge):
            return f"{_label_for(kw)}: {bullet[0].lower()}{bullet[1:]}", kw
    return bullet, None


def _role_relevance(entry, keywords: list[str]) -> int:
    """JD-keyword presence in one experience entry (object or dict)."""
    if isinstance(entry, dict):
        title, company, bullets = entry.get("title", ""), entry.get("company", ""), entry.get("bullets", [])
    else:
        title, company, bullets = entry.title, entry.company, entry.bullets or []
    text = " ".join([title, company] + list(bullets)).lower()
    return sum(1 for k in keywords if k in text)


#: Single generic words that read badly in a CV summary even when they
#: technically match. Multi-word phrases are unaffected.
_GENERIC_SUMMARY_WORDS = {
    "customer", "customers", "client", "clients", "team", "data", "work",
    "service", "services", "tools", "management", "people", "users",
    "product", "business", "experience", "skills", "company", "manager",
    "support", "remote", "role", "roles",
}
_ACRONYMS = {
    "saas": "SaaS", "csat": "CSAT", "sla": "SLA", "crm": "CRM", "seo": "SEO",
    "sql": "SQL", "kpi": "KPI", "erp": "ERP", "cms": "CMS", "api": "API",
}


def _display_keyword(kw: str) -> str:
    if kw.lower() in _ACRONYMS:
        return _ACRONYMS[kw.lower()]
    if " " in kw:
        return kw.title()
    return kw


def _targeted_summary(
    summary: str, jd_title: str, keywords: list[str], corpus: str
) -> tuple[str, list[str]]:
    """Append a JD-targeted sentence using ONLY keywords the candidate's
    own corpus already supports. Prefers specific phrases over generic
    single words. Returns (new_summary, keywords_added_display)."""
    original = (summary or "").strip().rstrip(".")
    picked: list[str] = []
    for k in keywords:
        if len(k) <= 3 or k not in corpus:
            continue
        if k.lower() in _GENERIC_SUMMARY_WORDS:
            continue
        if jd_title and k.lower() in jd_title.lower():
            continue
        if any(
            k.lower() == p.lower() or k.lower() in p.lower() or p.lower() in k.lower()
            for p in picked
        ):
            continue
        picked.append(_display_keyword(k))
        if len(picked) == 3:
            break
    if not picked or not original:
        return summary, []
    role = jd_title or "this role"
    return (
        original
        + f" - applying to the {role} role with direct experience in {', '.join(picked)}."
    ), picked


# --- tailoring --------------------------------------------------------------


def tailor(
    content: CvContent,
    parsed: ParsedCv,
    jd_title: str,
    jd_text: str,
    jd_id: str,
) -> tuple[CvContent, dict]:
    """Create a job-specific version: rewrites in the job's own wording.

    The rewrite engine (summary sentence, bullet re-labels, experience
    reordering) uses only the candidate's real facts + the JD's keywords.
    Every added keyword is verified against the candidate's own corpus;
    missing requirements are reported as gaps, never filled in.
    """
    out = content.clone()
    keywords = extract_jd_keywords(jd_text)
    corpus = content.all_text() + " " + parsed.summary.lower()

    present: list[dict] = []
    gaps: list[str] = []
    surfaced: list[str] = []
    for kw in keywords:
        in_corpus = kw in corpus
        present.append({"keyword": kw, "in_candidate_profile": in_corpus})
        if in_corpus:
            # Surface genuinely-supported keywords into the skills block.
            if kw not in [s.lower() for s in out.skills] and len(kw) > 3:
                out.skills.insert(0, kw)
                surfaced.append(kw)
        else:
            gaps.append(
                f"'{kw}' appears in the job description but not in your CV. "
                "If you have evidence for it, add it to your profile first."
            )

    # 1) Rewrite the summary: JD-targeted sentence, supported keywords only.
    out.summary, summary_added = _targeted_summary(
        out.summary, jd_title, keywords, corpus
    )

    # 2) Re-label bullets in the job's wording (fact never changes),
    #    up to 4 per CV so the document stays natural.
    relabelled: list[dict] = []
    relabel_cap = 4
    for e in out.experience:
        if relabel_cap <= 0:
            break
        for i, b in enumerate(e.bullets or []):
            if relabel_cap <= 0:
                break
            new_b, kw = _relabel_bullet(b, keywords)
            if kw:
                e.bullets[i] = new_b
                relabelled.append({"bullet": new_b, "keyword": kw, "original": b})
                relabel_cap -= 1

    # 3) Reorder experience: the role with the most JD-relevant content
    #    leads (stable - chronology preserved within equal relevance).
    before = [e.title for e in out.experience]
    out.experience = sorted(
        out.experience, key=lambda e: _role_relevance(e, keywords), reverse=True
    )
    roles_reordered = [e.title for e in out.experience] != before

    # 4) Keyword-forward skill ordering (factual set, reordered only).
    out.skills = _order_skills(out.skills, keywords)
    out.role_focus = jd_title
    out.job_description_version = jd_id
    out.generation_timestamp = datetime.now(timezone.utc).isoformat()

    needs_confirmation = [
        g for g in gaps
    ]
    report = {
        "jd_title": jd_title,
        "keywords": present,
        "surfaced_keywords": surfaced,
        "gaps": gaps,
        "needs_confirmation": needs_confirmation,
        "summary_keywords_added": summary_added,
        "bullets_relabelled": relabelled,
        "roles_reordered": roles_reordered,
        "coverage": (
            round(
                100 * sum(1 for p in present if p["in_candidate_profile"])
                / max(1, len(present)),
                1,
            )
            if present
            else 0.0
        ),
        "note": (
            "Rewrites use the job's own keywords around your real facts: "
            "the summary gains a targeting sentence (supported keywords only), "
            "matching bullets are re-labelled in the job's wording, and your "
            "most relevant role leads. Coverage shows which of the job's key "
            "terms your profile already supports. Gaps are questions to answer "
            "with real evidence - they are never filled in automatically."
        ),
    }
    return out, report
