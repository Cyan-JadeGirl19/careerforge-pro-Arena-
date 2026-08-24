"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { Application, ApplicationStatus } from "../../../../../packages/contracts/types";

const STATUSES: ApplicationStatus[] = [
  "saved", "ready", "applied", "phone_screen", "interview", "offer", "rejected", "archived",
];
const LABEL: Record<ApplicationStatus, string> = {
  saved: "Saved",
  ready: "Ready",
  applied: "Applied",
  phone_screen: "Phone Screen",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  archived: "Archived",
};

export default function ApplicationsPage() {
  const { session } = useSession();
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jdTitle, setJdTitle] = useState("");
  const [jdCompany, setJdCompany] = useState("");
  const [jdText, setJdText] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!session) return;
    try {
      setApps(await api.listApplications(session.profileId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load applications.");
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    if (!session || !jdTitle.trim() || jdText.trim().length < 40) return;
    setBusy(true);
    setError(null);
    try {
      const jd = await api.createJobDescription(session.profileId, {
        title: jdTitle.trim(),
        company: jdCompany.trim() || null,
        text: jdText.trim(),
      });
      await api.createApplication(session.profileId, { jd_id: jd.id });
      setJdTitle("");
      setJdCompany("");
      setJdText("");
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.message} (${e.code})` : "Could not create application.");
    } finally {
      setBusy(false);
    }
  };

  const setStatus = async (id: string, status: ApplicationStatus) => {
    try {
      await api.updateApplicationStatus(id, status);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update status.");
    }
  };

  return (
    <div>
      <div className="eyebrow">Applications</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Your application packages</h1>
      <p className="muted" style={{ margin: "0 0 20px" }}>
        Each job gets a tailored CV, a human-sounding cover letter, and — when the employer asks — a
        recorded response. You approve before anything is sent.
      </p>
      {error && <div className="alert error">{error}</div>}

      <div className="card" style={{ marginBottom: 18 }}>
        <h3>Add a job</h3>
        <div className="grid2">
          <div className="field">
            <label>Job title</label>
            <input value={jdTitle} onChange={(e) => setJdTitle(e.target.value)} />
          </div>
          <div className="field">
            <label>Company</label>
            <input value={jdCompany} onChange={(e) => setJdCompany(e.target.value)} />
          </div>
        </div>
        <div className="field">
          <label>Job description</label>
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the full job description…"
          />
        </div>
        <button className="btn" onClick={create} disabled={busy || !jdTitle.trim() || jdText.trim().length < 40}>
          {busy ? "Creating…" : "Create application package"}
        </button>
      </div>

      {!apps ? (
        <div className="empty">Loading…</div>
      ) : apps.length === 0 ? (
        <div className="empty">No applications yet. Add a job above and the program prepares the package.</div>
      ) : (
        <div className="stack">
          {apps.map((a) => (
            <div className="item" key={a.id}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h4 style={{ margin: 0 }}>
                  {a.jd_title} {a.jd_company ? `@ ${a.jd_company}` : ""}
                </h4>
                <span className={`status-badge status-${a.status}`}>{LABEL[a.status]}</span>
              </div>
              <p>
                Tailored CV: {a.tailored_cv_id ? "✅" : "⏳"} · Letter: {a.letter ? "✅" : "⏳"} ·
                Video: {a.videos.length > 0 ? `✅ ${a.videos.length}` : "—"}
              </p>
              <div className="actions">
                <Link className="btn" href={`/applications/${a.id}`}>
                  Open package
                </Link>
                <select
                  value={a.status}
                  onChange={(e) => setStatus(a.id, e.target.value as ApplicationStatus)}
                  style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}
                >
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>
                      {LABEL[s]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
