"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { Application, CvAnalysisOut, CvOut, RoleRecommendation } from "../../../../../packages/contracts/types";

export default function DashboardPage() {
  const { session } = useSession();
  const [cvs, setCvs] = useState<CvOut[] | null>(null);
  const [analysis, setAnalysis] = useState<CvAnalysisOut | null>(null);
  const [roles, setRoles] = useState<RoleRecommendation[] | null>(null);
  const [apps, setApps] = useState<Application[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    try {
      const allCvs = await api.listCvs(session.profileId);
      setCvs(allCvs);
      if (allCvs.length > 0) {
        const latest = allCvs[allCvs.length - 1];
        try {
          setAnalysis(await api.latestAnalysis(latest.id));
        } catch {
          setAnalysis(null);
        }
        try {
          setRoles(await api.recommendRoles(session.profileId));
        } catch {
          setRoles(null);
        }
      }
      setApps(await api.listApplications(session.profileId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load your dashboard.");
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  if (!session) return null;
  const queue = (apps ?? []).filter((a) => a.status === "saved" || a.status === "ready");
  const applied = (apps ?? []).filter((a) => a.status === "applied" || a.status === "phone_screen" || a.status === "interview").length;
  const interviews = (apps ?? []).filter((a) => a.status === "interview").length;
  const passed = analysis ? analysis.checks.filter((c) => c.passed).length : 0;

  return (
    <div>
      <h1 style={{ fontSize: 24, margin: "0 0 4px" }}>
        Good to see you, {session.firstName}
      </h1>
      <p className="muted" style={{ margin: "0 0 22px" }}>
        The program does the preparation; you approve anything sensitive.
      </p>

      {error && <div className="alert error">{error}</div>}

      {!cvs || !apps ? (
        <div className="empty">Loading your workspace…</div>
      ) : cvs.length === 0 ? (
        <div className="card">
          <h3>Your first step</h3>
          <p style={{ margin: "0 0 14px", fontSize: 14 }}>
            Upload your CV (PDF or DOCX) or paste the text. The program will parse it, build your
            three master CVs, recommend target roles, and prepare everything else for your review.
          </p>
          <Link className="btn" href="/cv">
            Go to CV Studio
          </Link>
        </div>
      ) : (
        <div className="stack">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 }}>
            <div className="card">
              <div className="muted">CV versions built</div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>{cvs.length}</div>
            </div>
            <div className="card">
              <div className="muted">Applications in play</div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>{applied}</div>
            </div>
            <div className="card">
              <div className="muted">Interviews</div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>{interviews}</div>
            </div>
            <div className="card">
              <div className="muted">CV checks passing</div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>
                {analysis ? `${passed}/${analysis.checks.length}` : "—"}
              </div>
            </div>
          </div>

          {queue.length > 0 && (
            <div className="card">
              <h3>Needs your review ({queue.length})</h3>
              <div className="stack">
                {queue.map((a) => (
                  <div className="item" key={a.id}>
                    <h4>{a.jd_title} {a.jd_company ? `@ ${a.jd_company}` : ""}</h4>
                    <p>
                      Tailored CV: {a.tailored_cv_id ? "ready" : "pending"} · Letter:{" "}
                      {a.letter ? "ready" : "pending"} · Video: {a.videos.length > 0 ? "ready" : "not prepared"}
                    </p>
                    <div className="actions">
                      <Link className="btn" href={`/applications/${a.id}`}>
                        Review package
                      </Link>
                      <Link className="btn secondary" href="/tracker">
                        Open tracker
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="grid2">
            <div className="card">
              <h3>Recommended target roles</h3>
              {roles && roles.length > 0 ? (
                <div className="stack">
                  {roles.map((r) => (
                    <div className="item" key={r.role}>
                      <h4>
                        {r.role} <span className="chip brand">{r.match_pct}% match</span>
                      </h4>
                      <p>{r.reason}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">Role recommendations appear after your CV is analysed.</p>
              )}
              <Link className="btn secondary" href="/cv" style={{ marginTop: 10 }}>
                Build CV versions
              </Link>
            </div>
            <div className="card">
              <h3>CV health (transparent checks)</h3>
              {analysis ? (
                <>
                  {analysis.checks.map((c) => (
                    <div key={c.check} style={{ display: "flex", gap: 8, alignItems: "baseline", padding: "4px 0" }}>
                      <span>{c.passed ? "✅" : "⚠️"}</span>
                      <span style={{ fontSize: 14 }}>
                        <b>{c.check}</b> — <span className="muted">{c.detail}</span>
                      </span>
                    </div>
                  ))}
                  {analysis.gaps.length > 0 && (
                    <div className="alert info">
                      {analysis.gaps.length} improvement gap(s).{" "}
                      <Link href="/cv">Open CV Studio</Link>
                    </div>
                  )}
                </>
              ) : (
                <p className="muted">Run the analysis in CV Studio to see transparent checks.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
