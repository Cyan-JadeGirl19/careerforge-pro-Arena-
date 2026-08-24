import Link from "next/link";

export const dynamic = "force-dynamic";

type Health = {
  status: string;
  version: string;
  environment: string;
  database: string;
};

async function fetchHealth(): Promise<Health | null> {
  try {
    const backend = process.env.CF_API_URL ?? "http://127.0.0.1:8001";
    const res = await fetch(`${backend}/api/v1/health`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Health;
  } catch {
    return null;
  }
}

const MODULES: Array<{ name: string; desc: string; state: "done" | "progress" | "planned" }> = [
  { name: "Dashboard", desc: "Central action and approval queue.", state: "planned" },
  { name: "CV Studio", desc: "Parse, analyse, build and export master CVs.", state: "progress" },
  { name: "Cover Letter Builder", desc: "Plain, candidate-voiced letters per job.", state: "progress" },
  { name: "Job Finder", desc: "Permitted sources, SA-eligibility filters.", state: "planned" },
  { name: "Recruiter Finder", desc: "Publicly displayed contacts only.", state: "planned" },
  { name: "Voice/Video Studio", desc: "Recorded responses with teleprompter.", state: "progress" },
  { name: "Gmail Outreach", desc: "Drafts first, throttled, consent-gated.", state: "planned" },
  { name: "Application Tracker", desc: "Stage pipeline with follow-ups.", state: "progress" },
  { name: "Interview Coach", desc: "Prepared answers, honest practice.", state: "planned" },
  { name: "Skills and Salary", desc: "Dated sources, clear disclaimers.", state: "planned" },
  { name: "Portfolio Builder", desc: "Work samples with approval flow.", state: "planned" },
  { name: "References and Profile", desc: "Private by default, approved before sharing.", state: "progress" },
  { name: "Settings / Privacy", desc: "Consents, export, erasure, audit trail.", state: "progress" },
];

export default async function HomePage() {
  const health = await fetchHealth();
  return (
    <main className="wrap">
      <div className="eyebrow">Remote-SA career accelerator</div>
      <h1>CareerForge Pro</h1>
      <p className="lede">
        CV-first career acceleration for South Africans pursuing remote work
        globally. The system prepares everything automatically; sensitive
        actions only happen after your explicit approval.
      </p>

      <div className="statusline">
        <span
          className={`badge ${health ? "ok" : "down"}`}
          title={health ? `API v${health.version} · db ${health.database}` : "API not reachable"}
        >
          {health ? `API v${health.version} · db ${health.database}` : "API offline"}
        </span>
        <span>Phase 1 — stable CV-first core</span>
      </div>

      <div className="actions">
        <Link className="btn" href="/prototype.html">
          Open no-build MVP prototype
        </Link>
        <a
          className="btn secondary"
          href="https://github.com/Cyan-JadeGirl19/careerforge-pro-Arena-"
          target="_blank"
          rel="noreferrer"
        >
          Source on GitHub
        </a>
      </div>

      <h2>Modules</h2>
      <div className="grid">
        {MODULES.map((m) => (
          <div className="module" key={m.name}>
            <h3>{m.name}</h3>
            <p>{m.desc}</p>
            <span className={`badge ${m.state}`}>{m.state}</span>
          </div>
        ))}
      </div>
    </main>
  );
}
