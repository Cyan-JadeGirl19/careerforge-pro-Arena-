"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type {
  NegotiationScript,
  Plan90d,
  RoleRecommendation,
  SalaryBenchmark,
  SkillsGaps,
} from "../../../../../packages/contracts/types";

export default function SkillsSalaryPage() {
  const { session } = useSession();
  const pid = session?.profileId ?? "";

  const [role, setRole] = useState("");
  const [roles, setRoles] = useState<RoleRecommendation[]>([]);
  const [gaps, setGaps] = useState<SkillsGaps | null>(null);
  const [plan, setPlan] = useState<Plan90d | null>(null);
  const [salary, setSalary] = useState<SalaryBenchmark | null>(null);
  const [scripts, setScripts] = useState<NegotiationScript[]>([]);
  const [payment, setPayment] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!pid) return;
    (async () => {
      try {
        setScripts((await api.negotiationScripts()).scripts);
        setPayment((await api.paymentGuidance()).points);
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

  const analyze = async () => {
    if (!pid || !role.trim()) return;
    setBusy(true);
    setError(null);
    setGaps(null);
    setPlan(null);
    setSalary(null);
    try {
      const [g, p, s] = await Promise.all([
        api.skillsGaps(pid, role.trim()),
        api.plan90d(pid, role.trim()),
        api.salaryBenchmark(role.trim()),
      ]);
      setGaps(g);
      setPlan(p);
      setSalary(s);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not build the analysis.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="eyebrow">Skills and Salary</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>
        Close the gap. Know your worth.
      </h1>
      <p className="muted" style={{ margin: "0 0 16px" }}>
        Honest gap analysis against your target role, a realistic 90-day plan with free courses,
        and directional salary benchmarks - with the disclaimers where they belong.
      </p>

      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}

      <div className="card">
        <div className="field" style={{ maxWidth: 420 }}>
          <label>Target role</label>
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="e.g. Operations Analyst"
          />
        </div>
        {roles.length > 0 && (
          <div className="row" style={{ flexWrap: "wrap", marginBottom: 10 }}>
            <span className="muted">From your CV:</span>
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
        <button className="btn" onClick={analyze} disabled={busy || !role.trim()}>
          {busy ? "Analysing…" : "Analyse gaps + salary"}
        </button>
      </div>

      {gaps && (
        <div className="stack" style={{ marginTop: 18 }}>
          <div className="grid2">
            <div className="card">
              <h3>Skills for {gaps.role}</h3>
              <b style={{ fontSize: 13 }}>You have</b>
              <div style={{ marginTop: 6 }}>
                {gaps.present.length ? (
                  gaps.present.map((s) => (
                    <span key={s} className="chip">
                      ✓ {s}
                    </span>
                  ))
                ) : (
                  <span className="muted">none of the listed skills yet</span>
                )}
              </div>
              <b style={{ fontSize: 13, display: "block", marginTop: 12 }}>Missing</b>
              <div style={{ marginTop: 6 }}>
                {gaps.missing.length ? (
                  gaps.missing.map((s) => (
                    <span key={s} className={`chip ${gaps.high_roi.includes(s) ? "brand" : "missing"}`}>
                      {gaps.high_roi.includes(s) ? "★ " : ""}
                      {s}
                    </span>
                  ))
                ) : (
                  <span className="chip">✓ none — full coverage</span>
                )}
              </div>
              <p className="muted" style={{ marginTop: 10, fontSize: 12 }}>
                ★ = other common target roles need this skill too (high ROI). Catalog as of{" "}
                {gaps.catalog_as_of}.
              </p>
            </div>

            <div className="card">
              <h3>Free courses for the gaps</h3>
              {gaps.courses.length ? (
                <div className="stack">
                  {gaps.courses.map((c) => (
                    <div className="item" key={c.url + c.skill}>
                      <b style={{ fontSize: 14 }}>{c.title}</b>
                      <p>
                        {c.skill} · {c.provider}
                      </p>
                      <a href={c.url} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>
                        open course →
                      </a>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No catalogue entry for these gaps yet.</p>
              )}
              <p className="muted" style={{ fontSize: 12 }}>
                Free or free-to-audit; verify links before enrolling.
              </p>
            </div>
          </div>

          {plan && (
            <div className="card">
              <h3>Your 90-day plan</h3>
              <div className="stack">
                {plan.weeks.map((w) => (
                  <div className="item" key={w.weeks}>
                    <b style={{ fontSize: 14 }}>
                      Weeks {w.weeks}: {w.focus}
                    </b>
                    <p>{w.detail}</p>
                    {w.url && (
                      <a href={w.url} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>
                        open resource →
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {salary && (
            <div className="card">
              <h3>Salary benchmark — {salary.role}</h3>
              {salary.found && salary.usd_month ? (
                <>
                  <div className="row" style={{ gap: 24, flexWrap: "wrap" }}>
                    <div>
                      <div className="muted" style={{ fontSize: 12 }}>
                        USD / month (directional)
                      </div>
                      <b style={{ fontSize: 20 }}>
                        ${salary.usd_month[0].toLocaleString()} – $
                        {salary.usd_month[1].toLocaleString()}
                      </b>
                    </div>
                    <div>
                      <div className="muted" style={{ fontSize: 12 }}>
                        ZAR / month (at {salary.rate.usd_zar.toFixed(2)} USD/ZAR,{" "}
                        {salary.rate.source})
                      </div>
                      <b style={{ fontSize: 20 }}>
                        R{salary.zar_month![0].toLocaleString()} – R
                        {salary.zar_month![1].toLocaleString()}
                      </b>
                    </div>
                  </div>
                  <p className="muted" style={{ fontSize: 13 }}>
                    {salary.note}
                  </p>
                </>
              ) : (
                <p className="muted">{salary.note}</p>
              )}
              <div className="alert info" style={{ marginTop: 10 }}>
                {salary.disclaimer}
              </div>
            </div>
          )}

          {scripts.length > 0 && (
            <div className="card">
              <h3>Negotiation scripts (fill the brackets)</h3>
              <div className="stack">
                {scripts.map((s) => (
                  <div className="item" key={s.name}>
                    <b style={{ fontSize: 14 }}>{s.name}</b>
                    <pre className="script" style={{ marginTop: 8 }}>
                      {s.text}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card">
            <h3>Paying yourself as a contractor (informational)</h3>
            <ul style={{ color: "var(--muted)", fontSize: 14, paddingLeft: 20, lineHeight: 1.9 }}>
              {payment.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
