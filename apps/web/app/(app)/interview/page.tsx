"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type {
  InterviewSession,
  Job,
  RoleRecommendation,
} from "../../../../../packages/contracts/types";

export default function InterviewCoachPage() {
  const { session } = useSession();
  const pid = session?.profileId ?? "";

  const [role, setRole] = useState("");
  const [roles, setRoles] = useState<RoleRecommendation[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobId, setJobId] = useState("");
  const [sessionOut, setSessionOut] = useState<InterviewSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  // practice mode
  const [practice, setPractice] = useState(false);
  const [idx, setIdx] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);

  useEffect(() => {
    if (!pid) return;
    (async () => {
      try {
        setJobs((await api.searchJobs({ sa_only: false, sort: "newest" })).slice(0, 30));
        // suggested roles from a quick CV-based recommendation
        try {
          setRoles(await api.recommendRoles(pid));
        } catch {
          setRoles([]);
        }
      } catch {
        // non-fatal
      }
    })();
  }, [pid]);

  const generate = async () => {
    if (!pid || !role.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const job = jobs.find((j) => j.id === jobId);
      const s = await api.generateInterview(pid, {
        role: role.trim(),
        jd_id: job?.id ?? null,
        jd_text: null,
      });
      setSessionOut(s);
      setPractice(false);
      setIdx(0);
      setShowAnswer(false);
      setExpanded(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not generate the interview.");
    } finally {
      setBusy(false);
    }
  };

  const groups = sessionOut
    ? sessionOut.questions.reduce<Record<string, typeof sessionOut.questions>>((acc, q) => {
        (acc[q.category] = acc[q.category] || []).push(q);
        return acc;
      }, {})
    : {};

  return (
    <div>
      <div className="eyebrow">Interview Coach</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Practise before it counts</h1>
      <p className="muted" style={{ margin: "0 0 16px" }}>
        Mock questions for your target role, with prepared answers built from your <b>real</b> CV.
        Wherever an answer says [Add: …], that part is yours to write - the app never invents your
        experience.
      </p>

      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}

      <div className="card">
        <div className="grid2">
          <div className="field">
            <label>Target role</label>
            <input
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="e.g. Customer Success Manager"
            />
          </div>
          <div className="field">
            <label>Base it on a specific job (optional)</label>
            <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              <option value="">None - role only</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.title} {j.company ? `@ ${j.company}` : ""}
                </option>
              ))}
            </select>
          </div>
        </div>
        {roles.length > 0 && (
          <div className="row" style={{ flexWrap: "wrap", marginBottom: 10 }}>
            <span className="muted">Suggested for your CV:</span>
            {roles.map((r) => (
              <button
                key={r.role}
                type="button"
                className="chip brand"
                style={{ cursor: "pointer" }}
                onClick={() => setRole(r.role)}
              >
                {r.role} ({r.match_pct}%)
              </button>
            ))}
          </div>
        )}
        <button className="btn" onClick={generate} disabled={busy || !role.trim()}>
          {busy ? "Building your interview…" : "Generate mock interview"}
        </button>
      </div>

      {sessionOut && !practice && (
        <div className="stack" style={{ marginTop: 18 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b style={{ fontSize: 15 }}>
              {sessionOut.questions.length} questions for {sessionOut.role}
            </b>
            <button className="btn secondary" onClick={() => setPractice(true)}>
              Practice mode →
            </button>
          </div>
          {Object.entries(groups).map(([cat, qs]) => (
            <div className="card" key={cat}>
              <h3>{cat}</h3>
              <div className="stack">
                {qs.map((q, i) => {
                  const key = `${cat}-${i}`;
                  return (
                    <div className="item" key={key}>
                      <b style={{ fontSize: 14 }}>{q.question}</b>
                      {q.evidence_used.length > 0 && (
                        <div style={{ marginTop: 4 }}>
                          {q.evidence_used.map((e) => (
                            <span key={e} className="chip" title="From your CV">
                              from CV
                            </span>
                          ))}
                        </div>
                      )}
                      <div
                        style={{
                          marginTop: 8,
                          fontSize: 12,
                          color: "var(--muted)",
                          cursor: "pointer",
                        }}
                        onClick={() => setExpanded(expanded === key ? null : key)}
                      >
                        {expanded === key ? "▲ hide prepared answer" : "▼ show prepared answer"}
                      </div>
                      {expanded === key && (
                        <pre className="script" style={{ marginTop: 8 }}>
                          {q.prepared_answer}
                        </pre>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          <p className="muted">{sessionOut.note}</p>
        </div>
      )}

      {sessionOut && practice && (
        <div className="card" style={{ marginTop: 18, textAlign: "center", padding: "34px 24px" }}>
          <div className="muted" style={{ marginBottom: 10 }}>
            Question {idx + 1} of {sessionOut.questions.length} · {sessionOut.questions[idx].category}
          </div>
          <div style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.5, marginBottom: 18 }}>
            {sessionOut.questions[idx].question}
          </div>
          {showAnswer ? (
            <pre className="script" style={{ textAlign: "left", marginBottom: 16 }}>
              {sessionOut.questions[idx].prepared_answer}
            </pre>
          ) : (
            <p className="muted">
              Answer out loud first - then check the prepared answer if you like.
            </p>
          )}
          <div className="row" style={{ justifyContent: "center", flexWrap: "wrap" }}>
            <button
              className="btn secondary"
              disabled={idx === 0}
              onClick={() => {
                setIdx((i) => Math.max(0, i - 1));
                setShowAnswer(false);
              }}
            >
              ← Previous
            </button>
            <button className="btn secondary" onClick={() => setShowAnswer((s) => !s)}>
              {showAnswer ? "Hide answer" : "Show prepared answer"}
            </button>
            <button
              className="btn"
              disabled={idx === sessionOut.questions.length - 1}
              onClick={() => {
                setIdx((i) => Math.min(sessionOut.questions.length - 1, i + 1));
                setShowAnswer(false);
              }}
            >
              Next →
            </button>
            <button className="btn secondary" onClick={() => setPractice(false)}>
              ← Back to list
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
