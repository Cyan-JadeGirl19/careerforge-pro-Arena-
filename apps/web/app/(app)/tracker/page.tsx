"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { Application, ApplicationStatus } from "../../../../../packages/contracts/types";

const COLUMNS: ApplicationStatus[] = [
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

export default function TrackerPage() {
  const { session } = useSession();
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    try {
      setApps(await api.listApplications(session.profileId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the tracker.");
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  const move = async (id: string, status: ApplicationStatus) => {
    try {
      await api.updateApplicationStatus(id, status);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not move the card.");
    }
  };

  if (!session) return null;

  const applied = (apps ?? []).filter((a) => a.status === "applied").length;
  const interviews = (apps ?? []).filter((a) => a.status === "interview").length;
  const conversion = applied ? Math.round((interviews / applied) * 100) : null;

  return (
    <div>
      <div className="eyebrow">Application Tracker</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Momentum, made visible</h1>
      <p className="muted" style={{ margin: "0 0 16px" }}>
        The metric that matters is interviews, not volume:{" "}
        <b>
          {conversion === null ? "—" : `${conversion}%`}
        </b>{" "}
        interview conversion on applied roles.
      </p>
      {error && <div className="alert error">{error}</div>}
      {!apps ? (
        <div className="empty">Loading…</div>
      ) : (
        <div className="kanban wide">
          {COLUMNS.map((col) => {
            const cards = apps.filter((a) => a.status === col);
            return (
              <div className="column" key={col}>
                <h4>
                  {LABEL[col]} ({cards.length})
                </h4>
                {cards.length === 0 && <span className="muted" style={{ fontSize: 12 }}>—</span>}
                {cards.map((a) => (
                  <div className="ticket" key={a.id}>
                    <b>{a.jd_title}</b>
                    <span>{a.jd_company ?? ""}</span>
                    <span style={{ marginTop: 4 }}>
                      CV {a.tailored_cv_id ? "✓" : "⏳"} · Letter {a.letter ? "✓" : "⏳"} · Video{" "}
                      {a.videos.length ? "✓" : "—"}
                    </span>
                    <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <Link
                        href={`/applications/${a.id}`}
                        style={{ fontSize: 12, color: "var(--brand)", fontWeight: 700 }}
                      >
                        Open
                      </Link>
                      <select
                        value={a.status}
                        onChange={(e) => move(a.id, e.target.value as ApplicationStatus)}
                        style={{ fontSize: 12, padding: "3px 5px", borderRadius: 6, border: "1px solid var(--line)" }}
                      >
                        {COLUMNS.map((s) => (
                          <option key={s} value={s}>
                            → {LABEL[s]}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
