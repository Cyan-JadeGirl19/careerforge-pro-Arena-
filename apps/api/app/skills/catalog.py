"""Curated free-course catalog, salary benchmarks, and negotiation scripts.

Honesty rules (agreed):
- Courses are real, free (or free-to-audit) resources, with URLs. Links
  change - each entry is dated and the UI says "verify before enrolling".
- Salary figures are DIRECTIONAL 2026-08 ranges commonly seen in remote
  postings open to Africa. They are not income promises and not tax or
  legal advice.
- Payment/tax guidance is informational only; candidates are pointed to
  a tax practitioner for SARS advice.
"""

CATALOG_AS_OF = "2026-08"

# skill keyword -> list of (title, provider, url, note)
FREE_COURSES: dict[str, list[dict]] = {
    "python": [
        {
            "title": "Python for Everybody",
            "provider": "Coursera (University of Michigan, free to audit)",
            "url": "https://www.coursera.org/specializations/python",
            "note": "The standard free Python start. Audit for free; pay only if you want the certificate.",
        },
        {
            "title": "FreeCodeCamp - Python for Beginners",
            "provider": "freeCodeCamp (fully free, YouTube + website)",
            "url": "https://www.freecodecamp.org/learn/scientific-computing-with-python/",
            "note": "Project-based, no signup wall.",
        },
    ],
    "sql": [
        {
            "title": "SQLBolt",
            "provider": "SQLBolt (free, interactive)",
            "url": "https://sqlbolt.com/",
            "note": "Best free hands-on SQL intro.",
        },
        {
            "title": "Mode SQL Tutorial",
            "provider": "Mode Analytics (free)",
            "url": "https://mode.com/sql-tutorial/",
            "note": "Practical, analytics-focused SQL.",
        },
    ],
    "excel": [
        {
            "title": "Excel Skills for Business",
            "provider": "Coursera (Macquarie University, free to audit)",
            "url": "https://www.coursera.org/specializations/excel",
            "note": "Covers formulas, data tools, and dashboards.",
        },
        {
            "title": "Microsoft Support - Excel free courses",
            "provider": "Microsoft (free)",
            "url": "https://support.microsoft.com/en-us/excel/training-courses",
            "note": "Official, short, practical modules.",
        },
    ],
    "data analysis": [
        {
            "title": "Google Data Analytics Certificate",
            "provider": "Coursera (Google; free trial + financial aid available)",
            "url": "https://www.coursera.org/professional-certificates/google-data-analytics",
            "note": "The most recognised free/aid-accessible data certificate.",
        },
        {
            "title": "FreeCodeCamp - Data Analysis with Python",
            "provider": "freeCodeCamp (free)",
            "url": "https://www.freecodecamp.org/learn/data-analysis-with-python/",
            "note": "NumPy/pandas practice with real datasets.",
        },
    ],
    "agile": [
        {
            "title": "Agile with Atlassian Jira",
            "provider": "Atlassian (free)",
            "url": "https://www.atlassian.com/agile/overview",
            "note": "Practical agile/Jira fundamentals.",
        },
    ],
    "project management": [
        {
            "title": "Google Project Management Certificate",
            "provider": "Coursera (Google; free trial + financial aid available)",
            "url": "https://www.coursera.org/professional-certificates/google-project-management",
            "note": "Covers planning, agile, and stakeholder communication.",
        },
    ],
    "communication": [
        {
            "title": "Improving Communication Skills",
            "provider": "Coursera (University of Illinois, free to audit)",
            "url": "https://www.coursera.org/learn/improving-communication-skills",
            "note": "Written + verbal clarity, professional contexts.",
        },
    ],
    "customer success": [
        {
            "title": "Customer Service Foundations",
            "provider": "HubSpot Academy (free, certificate included)",
            "url": "https://academy.hubspot.com/courses/customer-service",
            "note": "Free with a shareable certificate - great for CVs.",
        },
    ],
    "customer service": [
        {
            "title": "Customer Service Foundations",
            "provider": "HubSpot Academy (free, certificate included)",
            "url": "https://academy.hubspot.com/courses/customer-service",
            "note": "Free with a shareable certificate - great for CVs.",
        },
    ],
    "marketing": [
        {
            "title": "Google Digital Marketing & E-commerce",
            "provider": "Coursera (Google; free trial + financial aid available)",
            "url": "https://www.coursera.org/professional-certificates/google-digital-marketing",
            "note": "Covers channels, campaigns, and measurement.",
        },
        {
            "title": "Inbound Marketing",
            "provider": "HubSpot Academy (free, certificate included)",
            "url": "https://academy.hubspot.com/courses/inbound-marketing",
            "note": "Free certificate; practical content marketing.",
        },
    ],
    "social media": [
        {
            "title": "Social Media Marketing",
            "provider": "HubSpot Academy (free, certificate included)",
            "url": "https://academy.hubspot.com/courses/social-media-marketing",
            "note": "Free certificate; channels, strategy, measurement.",
        },
    ],
    "frontend": [
        {
            "title": "Responsive Web Design",
            "provider": "freeCodeCamp (free, certified)",
            "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/",
            "note": "HTML/CSS fundamentals with projects.",
        },
        {
            "title": "The Odin Project - Full Stack",
            "provider": "The Odin Project (free)",
            "url": "https://www.theodinproject.com/",
            "note": "Full curriculum, community-supported.",
        },
    ],
    "javascript": [
        {
            "title": "JavaScript Algorithms and Data Structures",
            "provider": "freeCodeCamp (free, certified)",
            "url": "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/",
            "note": "From basics to real projects.",
        },
    ],
    "typescript": [
        {
            "title": "TypeScript Handbook",
            "provider": "Microsoft (free, official)",
            "url": "https://www.typescriptlang.org/docs/handbook/intro.html",
            "note": "Read + build; pair with any JS project.",
        },
    ],
    "power bi": [
        {
            "title": "Microsoft Learn - Power BI",
            "provider": "Microsoft Learn (free learning paths)",
            "url": "https://learn.microsoft.com/en-us/training/powerplatform/power-bi",
            "note": "Official paths; practice datasets included.",
        },
    ],
    "stakeholder management": [
        {
            "title": "Stakeholder Communication (Google PM Certificate unit)",
            "provider": "Coursera (Google; financial aid available)",
            "url": "https://www.coursera.org/professional-certificates/google-project-management",
            "note": "The planning/communication units are the relevant part.",
        },
    ],
}

# role keyword set (shared with builders) -> the skills that matter for it
ROLE_SKILLS = {
    "customer success": [
        "customer success", "customer service", "communication", "data analysis",
        "stakeholder management", "excel",
    ],
    "customer support": [
        "customer service", "communication", "excel", "data analysis", "stakeholder management",
    ],
    "operations": [
        "data analysis", "excel", "project management", "stakeholder management", "communication",
    ],
    "operations analyst": [
        "data analysis", "excel", "sql", "python", "reporting", "stakeholder management",
    ],
    "data analysis": ["python", "sql", "excel", "data analysis", "power bi", "communication"],
    "frontend": ["frontend", "javascript", "typescript", "communication"],
    "marketing": ["marketing", "social media", "content creation", "data analysis", "communication"],
    "project management": [
        "project management", "agile", "stakeholder management", "communication", "excel",
    ],
    "sales": ["communication", "crm", "data analysis", "stakeholder management"],
    "recruitment": ["communication", "stakeholder management", "data analysis", "crm"],
}

# Directional monthly rates commonly seen in 2026-08 remote postings that
# are open to South African contractors. NOT income promises.
SALARY_BENCHMARKS: dict[str, dict] = {
    "customer success manager": {"usd_month": [4000, 7000], "note": "Mid-senior remote, Africa-open postings"},
    "customer success": {"usd_month": [3500, 6500], "note": "Mid-level remote, Africa-open postings"},
    "customer support": {"usd_month": [2000, 3500], "note": "Remote support roles, Africa-open"},
    "operations analyst": {"usd_month": [3000, 5500], "note": "Remote ops/BI analyst roles"},
    "data analyst": {"usd_month": [4000, 7000], "note": "Remote analyst roles"},
    "frontend engineer": {"usd_month": [5000, 9000], "note": "Remote frontend, Africa-open"},
    "software developer": {"usd_month": [5000, 9000], "note": "Remote developer, Africa-open"},
    "marketing specialist": {"usd_month": [3000, 5500], "note": "Remote marketing, Africa-open"},
    "project coordinator": {"usd_month": [2500, 4500], "note": "Remote coordination roles"},
    "virtual assistant": {"usd_month": [1500, 3000], "note": "Remote admin/VA roles"},
    "administrator": {"usd_month": [1800, 3200], "note": "Remote admin roles"},
}

SALARY_DISCLAIMER = (
    "Directional monthly rates seen in 2026-08 remote postings open to South African "
    "contractors. Ranges vary widely by company, seniority and currency. Verify against "
    "live jobs before negotiating. This is not an income promise, and not tax or legal "
    "advice - for SARS treatment of foreign income, consult a South African tax practitioner."
)

NEGOTIATION_SCRIPTS = [
    {
        "name": "Opening (first rate question)",
        "text": (
            "Thank you for the offer details. Based on the scope we discussed and the "
            "directional market range for this kind of role, I was expecting between "
            "[LOW USD] and [HIGH USD] per month. I'm flexible on structure (contractor vs "
            "EOR) - what's your room on rate?"
        ),
    },
    {
        "name": "Anchoring to evidence",
        "text": (
            "Given [specific achievement from your CV - e.g. the CSAT improvement you "
            "delivered], I believe I can be productive in this role quickly. Would it be "
            "possible to move the rate closer to [TARGET USD]?"
        ),
    },
    {
        "name": "If they anchor low (geo-adjustment pushback)",
        "text": (
            "I understand budgets differ. I'm based in South Africa (UTC+2) with full "
            "overlap to European hours and a track record of [one real result]. If the "
            "base rate is fixed, could we look at [a quarterly review tied to outcomes / "
            "a bonus for the first 90 days]?"
        ),
    },
    {
        "name": "Payment structure",
        "text": (
            "For payments I'm set up for Deel/Wise/Payoneer - whichever is easiest on "
            "your side. Could you confirm the payment currency and cycle?"
        ),
    },
]

PAYMENT_GUIDANCE = [
    "Deel, Remote.com and similar EOR platforms handle contracts, payroll and local "
    "compliance - common for Africa-based contractors. Many employers prefer this.",
    "Wise and Payoneer make receiving USD/EUR practical; a local SA bank account plus "
    "Wise is a typical setup.",
    "If you're a contractor (not an employee), SARS still expects you to declare "
    "foreign-sourced income. A tax practitioner will tell you how your specific setup "
    "is treated - this platform does not give tax advice.",
    "Keep every contract, invoice and payment record - you'll want them for tax season "
    "and for proof of income.",
]
