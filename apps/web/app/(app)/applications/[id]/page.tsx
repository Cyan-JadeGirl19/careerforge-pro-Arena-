"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, exportUrl } from "../../../../lib/api";
import { useSession } from "../../../../lib/session";
import type {
  Application,
  ApplicationStatus,
  FollowUp,
  Reference,
  TailoredCv,
} from "../../../../../../packages/contracts/types";

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

export default function ApplicationDetailPage({ params }: { params: { id: string } }) {
  const id = params.id;
  const { session } = useSession();
  const [app, setApp] = useState<Application | null>(null);
  const [tailored, setTailored] = useState<TailoredCv | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [letter, setLetter] = useState<string>("");
  const [allRefs, setAllRefs] = useState<Reference[]>([]);
  const [selRefs, setSelRefs] = useState<Set<string>>(new Set());
  const [refRequested, setRefRequested] = useState("unspecified");
  const [followups, setFollowups] = useState<FollowUp[]>([]);
  const [fuDays, setFuDays] = useState(5);

  const load = useCallback(async () => {
    try {
      const a = await api.getApplication(id);
      setApp(a);
      setRefRequested(a.references_requested || "unspecified");
      setSelRefs(new Set(a.references?.map((r) => r.id) ?? []));
      if (a.tailored_cv_id) {
        setTailored(await api.getTailored(a.tailored_cv_id));
      }
      if (a.letter) setLetter(a.letter.text);
      if (session) {
        setAllRefs(await api.listReferences(session.profileId));
        const allFus = await api.listFollowups(session.profileId);
        setFollowups(allFus.filter((f) => f.application_id === a.id));
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load this application.");
    }
  }, [id, session]);

  const addFollowup = async () => {
    setBusy("fu");
    setError(null);
    try {
      await api.createFollowup(id, { kind: "custom", due_days: fuDays });
      await load();
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.message} (${e.code}) — enable the outreach consent in Settings to create drafts.`
          : "Could not create the follow-up.",
      );
    } finally {
      setBusy(null);
    }
  };

  const actFollowup = async (fid: string, status: "sent" | "skipped") => {
    try {
      await api.updateFollowup(fid, { status });
      setFollowups((f) => f.filter((x) => x.id !== fid));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update the follow-up.");
    }
  };

  useEffect(() => {
    load();
  }, [load]);

  const attachRefs = async () => {
    setBusy("refs");
    setError(null);
    try {
      const a = await api.attachReferences(id, {
        references_requested: refRequested,
        reference_ids: Array.from(selRefs),
      });
      setApp(a);
      setRefRequested(a.references_requested);
      setSelRefs(new Set(a.references?.map((r) => r.id) ?? []));
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.message} (${e.code})`
          : "Could not attach references.",
      );
    } finally {
      setBusy(null);
    }
  };

  const ensureTailored = async () => {
    setBusy("tailor");
    setError(null);
    try {
      const res = await api.tailorApplication(id);
      setTailored(await api.getTailored(res.tailored_cv_id));
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? `${e.message} (${e.code})` : "Tailoring failed.");
    } finally {
      setBusy(null);
    }
  };

  const generateLetter = async (tone: string) => {
    setBusy("letter");
    setError(null);
    try {
      const l = await api.createLetter(id, tone);
      setLetter(l.text);
      setApp((a) => (a ? { ...a, letter: l } : a));
      if (l.quality_issues.length > 0) {
        setError(`Letter note: ${l.quality_issues.join(" ")}`);
      }
    } catch (e) {
      setError(e instanceof ApiError ? `${e.message} (${e.code})` : "Letter generation failed.");
    } finally {
      setBusy(null);
    }
  };

  const setStatus = async (status: ApplicationStatus) => {
    try {
      setApp(await api.updateApplicationStatus(id, status));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update status.");
    }
  };

  if (!app) {
    return error ? <div className="alert error">{error}</div> : <div className="empty">Loading…</div>;
  }

  return (
    <div>
      <Link href="/applications" className="muted">
        ← All applications
      </Link>
      <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
        <h1 style={{ fontSize: 22, margin: "6px 0 0" }}>
          {app.jd_title} {app.jd_company ? `@ ${app.jd_company}` : ""}
        </h1>
        <select
          value={app.status}
          onChange={(e) => setStatus(e.target.value as ApplicationStatus)}
          style={{ padding: "8px 10px", borderRadius: 8, border: "1px solid var(--line)" }}
        >
          {(Object.keys(LABEL) as ApplicationStatus[]).map((s) => (
            <option key={s} value={s}>
              {LABEL[s]}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="alert error" style={{ marginTop: 12 }}>
          {error}
        </div>
      )}

      <div className="stack" style={{ marginTop: 18 }}>
        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>Tailored CV</h3>
            {!tailored && (
              <button className="btn" onClick={ensureTailored} disabled={!!busy}>
                {busy === "tailor" ? "Tailoring…" : "Create tailored CV"}
              </button>
            )}
          </div>
          {tailored ? (
            <>
              <p style={{ fontSize: 14 }}>
                <span className="chip brand">{tailored.report.coverage}% keyword coverage</span>{" "}
                <span className="muted">{tailored.title}</span>
              </p>
              <div>
                {tailored.report.keywords.slice(0, 14).map((k) => (
                  <span key={k.keyword} className={`chip ${k.in_candidate_profile ? "" : "missing"}`}>
                    {k.in_candidate_profile ? "✓ " : "+ "}
                    {k.keyword}
                  </span>
                ))}
              </div>
              {tailored.report.gaps.length > 0 && (
                <div className="alert info" style={{ marginTop: 10 }}>
                  Gaps to answer with real evidence: {tailored.report.gaps.slice(0, 3).join(" · ")}
                  {tailored.report.gaps.length > 3 ? " …" : ""}
                </div>
              )}
              <div className="actions">
                <a className="btn" href={exportUrl("tailored", tailored.id, "docx")}>
                  Download DOCX
                </a>
                <a className="btn secondary" href={exportUrl("tailored", tailored.id, "pdf")}>
                  PDF
                </a>
                <a className="btn secondary" href={exportUrl("tailored", tailored.id, "txt")}>
                  Text
                </a>
                <a className="btn secondary" href={exportUrl("tailored", tailored.id, "json")}>
                  JSON
                </a>
              </div>
            </>
          ) : (
            <p className="muted">
              The tailored CV is job-specific: your best master version, rewritten around this JD,
              with keywords surfaced only where your profile supports them.
            </p>
          )}
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>Cover letter</h3>
            <div className="row">
              <button className="btn secondary" onClick={() => generateLetter("direct")} disabled={!!busy}>
                {busy === "letter" ? "Writing…" : app.letter ? "Regenerate (direct)" : "Generate (direct)"}
              </button>
              <button className="btn secondary" onClick={() => generateLetter("warm")} disabled={!!busy}>
                Warm tone
              </button>
            </div>
          </div>
          {letter ? (
            <pre className="script" style={{ marginTop: 12 }}>{letter}</pre>
          ) : (
            <p className="muted">
              Plain, specific, written around this job — no template boilerplate. Generate it, edit
              in any app if you like, and it stays saved here.
            </p>
          )}
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>References</h3>
            <Link href="/references" className="muted">
              manage references →
            </Link>
          </div>
          <p className="muted">
            Hidden from your CVs. Attached only here, and only with your confirmed permission.
          </p>
          <div className="field">
            <label>Does this employer ask for references?</label>
            <select
              value={refRequested}
              onChange={(e) => setRefRequested(e.target.value)}
            >
              <option value="unspecified">Not specified</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
          {allRefs.length > 0 ? (
            <div className="stack">
              {allRefs.map((r) => {
                const eligible = r.approved && r.permission_confirmed;
                const hasContact = Boolean(r.email || r.phone);
                return (
                  <label
                    key={r.id}
                    className="checkbox"
                    style={{ cursor: eligible ? "pointer" : "not-allowed", opacity: eligible ? 1 : 0.6 }}
                  >
                    <input
                      type="checkbox"
                      disabled={!eligible}
                      checked={selRefs.has(r.id)}
                      onChange={(e) => {
                        const next = new Set(selRefs);
                        if (e.target.checked) next.add(r.id);
                        else next.delete(r.id);
                        setSelRefs(next);
                      }}
                    />
                    <span>
                      <b>{r.name}</b>
                      {r.title ? ` · ${r.title}` : ""} {r.company ? `@ ${r.company}` : ""}
                      {!r.permission_confirmed && (
                        <span className="chip missing" style={{ marginLeft: 6 }}>
                          permission not confirmed
                        </span>
                      )}
                      {!r.approved && (
                        <span className="chip missing" style={{ marginLeft: 6 }}>
                          not approved
                        </span>
                      )}
                      {eligible && !hasContact && (
                        <span className="chip missing" style={{ marginLeft: 6 }}>
                          no contact details
                        </span>
                      )}
                    </span>
                  </label>
                );
              })}
              <button
                className="btn"
                onClick={attachRefs}
                disabled={busy === "refs"}
              >
                {busy === "refs" ? "Attaching…" : "Save references for this application"}
              </button>
            </div>
          ) : (
            <p className="muted">No references saved yet.</p>
          )}
          {app.references && app.references.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <b style={{ fontSize: 13 }}>Attached to this application:</b>
              <div style={{ marginTop: 6 }}>
                {app.references.map((r) => (
                  <span key={r.id} className="chip" style={{ marginRight: 6 }}>
                    {r.name}
                    {r.missing.length > 0 && " ⚠"}
                  </span>
                ))}
              </div>
              <a
                className="btn secondary"
                href={`/api/v1/applications/${id}/references/summary`}
                style={{ marginTop: 10, display: "inline-block" }}
              >
                Download reference sheet (TXT)
              </a>
            </div>
          )}
        </div>

        <div className="card">
          <h3>Follow-ups</h3>
          <p className="muted">
            Scheduled automatically: 5 days after applying, 3 days after an interview. Drafts are
            yours to edit and send.
          </p>
          {followups.length > 0 && (
            <div className="stack" style={{ marginBottom: 12 }}>
              {followups.map((f) => {
                const overdue = new Date(f.due_at).getTime() < Date.now();
                return (
                  <div className="item" key={f.id}>
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <span className="chip neutral">{f.kind.replace(/_/g, " ")}</span>
                      <span className={`chip ${overdue ? "missing" : "brand"}`}>
                        {overdue ? "due now" : `due ${new Date(f.due_at).toLocaleDateString()}`}
                      </span>
                    </div>
                    <pre className="script" style={{ margin: "8px 0", maxHeight: 150, overflowY: "auto" }}>
                      {f.draft_text}
                    </pre>
                    <div className="row">
                      <button className="btn" onClick={() => actFollowup(f.id, "sent")}>
                        Mark sent
                      </button>
                      <button className="btn secondary" onClick={() => actFollowup(f.id, "skipped")}>
                        Skip
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <div className="row">
            <select
              value={fuDays}
              onChange={(e) => setFuDays(Number(e.target.value))}
              style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "8px 10px" }}
            >
              <option value={2}>in 2 days</option>
              <option value={5}>in 5 days</option>
              <option value={7}>in 7 days</option>
              <option value={10}>in 10 days</option>
            </select>
            <button className="btn secondary" onClick={addFollowup} disabled={busy === "fu"}>
              {busy === "fu" ? "Scheduling…" : "Schedule another follow-up"}
            </button>
          </div>
        </div>

        <div className="card">
          <h3>Recorded responses</h3>
          {app.videos.length > 0 ? (
            <div className="stack">
              {app.videos.map((v) => (
                <div className="item" key={v.id}>
                  <h4>“{v.question.length > 80 ? v.question.slice(0, 80) + "…" : v.question}”</h4>
                  <p>
                    {v.target_seconds}s target · {v.tone} · v{v.script_version} · media: {v.media_status}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <p className="muted">No recorded responses yet.</p>
          )}
          <Link className="btn" href={`/video?app=${app.id}`} style={{ marginTop: 12 }}>
            Open Voice/Video Studio
          </Link>
        </div>
      </div>
    </div>
  );
}
