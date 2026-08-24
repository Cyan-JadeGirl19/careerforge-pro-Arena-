"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import { saveSession } from "../../lib/session";
import type { ConsentItem } from "../../../../packages/contracts/types";

const CONSENTS: Array<{ item: ConsentItem; title: string; desc: string; required?: boolean }> = [
  {
    item: "profile_processing",
    title: "Process my CV",
    desc: "Store and analyse your CV to build your master CV versions. Required to use the app.",
    required: true,
  },
  {
    item: "job_matching",
    title: "Match me to jobs",
    desc: "Compare your profile with job descriptions you provide, and tailor your CV per job.",
  },
  {
    item: "recruiter_contact",
    title: "Find public recruiter contacts",
    desc: "Look up publicly displayed recruiter or job-poster details for roles you apply to.",
  },
  {
    item: "outreach_sending",
    title: "Prepare outreach emails",
    desc: "Draft personalised emails. Nothing is ever sent without your approval.",
  },
  {
    item: "video_recording",
    title: "Generate voice/video scripts",
    desc: "Create response scripts for applications that ask for a recorded introduction.",
  },
  {
    item: "media_use",
    title: "Use my approved media",
    desc: "Process photos, audio or video that you explicitly approve (headshots, recordings).",
  },
  {
    item: "reference_sharing",
    title: "Share my references",
    desc: "Include your references only in applications you select and approve.",
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [timezone, setTimezone] = useState("Africa/Johannesburg");
  const [consents, setConsents] = useState<Record<string, boolean>>({
    profile_processing: true,
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const finish = async () => {
    if (!consents.profile_processing) {
      setError("You need to allow CV processing to use the app.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const profile = await api.createProfile({
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
        timezone,
      });
      for (const c of CONSENTS) {
        if (consents[c.item]) {
          await api.grantConsent(profile.id, { item: c.item, granted: true });
        }
      }
      saveSession({ profileId: profile.id, firstName: firstName.trim() || "Candidate" });
      router.replace("/dashboard");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong creating your profile.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="centered">
      <div className="hero-logo" />
      <div className="eyebrow">Welcome to CareerForge Pro</div>
      <h1 style={{ marginTop: 10 }}>
        {step === 1 ? "Let's set you up" : "Choose what you're comfortable with"}
      </h1>
      <p className="muted">
        CV-first career acceleration for South Africans pursuing remote work. The program does the
        preparation; you approve anything sensitive.
      </p>

      <div className="row" style={{ gap: 8, margin: "18px 0 16px" }}>
        <span className={`chip ${step === 1 ? "brand" : "neutral"}`}>1 · About you</span>
        <span className={`chip ${step === 2 ? "brand" : "neutral"}`}>2 · Your permissions</span>
      </div>

      <div className="card">
        {step === 1 ? (
          <>
            <div className="field">
              <label>First name</label>
              <input
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="Thando"
                autoFocus
              />
            </div>
            <div className="field">
              <label>Last name (optional)</label>
              <input value={lastName} onChange={(e) => setLastName(e.target.value)} placeholder="Ndlovu" />
            </div>
            <div className="field">
              <label>Timezone</label>
              <select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
                <option value="Africa/Johannesburg">Africa/Johannesburg (UTC+2)</option>
                <option value="Africa/Cape_Town">Africa/Cape_Town (UTC+2)</option>
                <option value="Africa/Nairobi">Africa/Nairobi (UTC+3)</option>
                <option value="Europe/London">Europe/London (UTC+0/+1)</option>
                <option value="Europe/Berlin">Europe/Berlin (UTC+1/+2)</option>
              </select>
            </div>
            {error && <div className="alert error">{error}</div>}
            <button className="btn" onClick={() => setStep(2)} disabled={!firstName.trim() || busy}>
              Continue
            </button>
          </>
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              Every consent is separate and can be revoked anytime in Settings. We never share your
              data, and you can delete everything at any time.
            </p>
            {CONSENTS.map((c) => (
              <label key={c.item} className="checkbox">
                <input
                  type="checkbox"
                  disabled={c.required}
                  checked={consents[c.item] ?? false}
                  onChange={(e) => setConsents((s) => ({ ...s, [c.item]: e.target.checked }))}
                />
                <span>
                  <b>{c.title}</b>
                  {c.required && <span className="chip neutral"> required</span>}
                  <p>{c.desc}</p>
                </span>
              </label>
            ))}
            {error && <div className="alert error">{error}</div>}
            <div className="row">
              <button className="btn" onClick={finish} disabled={busy}>
                {busy ? "Setting up…" : "Create my profile"}
              </button>
              <button className="btn secondary" onClick={() => setStep(1)}>
                Back
              </button>
            </div>
          </>
        )}
      </div>
      <p className="muted" style={{ marginTop: 18 }}>
        Your data is processed for the purposes you consent to, nothing else. Deletion is one click
        in Settings / Privacy.
      </p>
    </main>
  );
}
