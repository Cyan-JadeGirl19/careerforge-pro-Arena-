"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { Application } from "../../../../../packages/contracts/types";

export default function LettersPage() {
  const { session } = useSession();
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    try {
      setApps(await api.listApplications(session.profileId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load letters.");
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  const generate = async (id: string, tone: string) => {
    setBusyId(id);
    setError(null);
    try {
      await api.createLetter(id, tone);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Letter generation failed.");
    } finally {
      setBusyId(null);
    }
  };

  if (!session) return null;

  return (
    <div>
      <div className="eyebrow">Cover Letter Builder</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>One letter per job, in your voice</h1>
      <p className="muted" style={{ margin: "0 0 18px" }}>
        Plain, specific, and written around each job. No "I am excited to apply…" energy. Letters
        are stored with each application.
      </p>
      {error && <div className="alert error">{error}</div>}
      {!apps ? (
        <div className="empty">Loading…</div>
      ) : apps.length === 0 ? (
        <div className="empty">
          No applications yet. <Link href="/applications">Create one</Link> and its letter will live here.
        </div>
      ) : (
        <div className="stack">
          {apps.map((a) => (
            <div className="item" key={a.id}>
              <h4>
                {a.jd_title} {a.jd_company ? `@ ${a.jd_company}` : ""}
              </h4>
              {a.letter ? (
                <>
                  <pre className="script">{a.letter.text}</pre>
                  {a.letter.quality_issues.length > 0 && (
                    <div className="alert info">{a.letter.quality_issues.join(" ")}</div>
                  )}
                </>
              ) : (
                <p className="muted">No letter yet.</p>
              )}
              <div className="actions">
                <button
                  className="btn"
                  onClick={() => generate(a.id, "direct")}
                  disabled={busyId === a.id}
                >
                  {busyId === a.id ? "Writing…" : a.letter ? "Regenerate (direct)" : "Generate (direct)"}
                </button>
                <button className="btn secondary" onClick={() => generate(a.id, "warm")} disabled={busyId === a.id}>
                  Warm tone
                </button>
                <Link className="btn secondary" href={`/applications/${a.id}`}>
                  Open application
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
