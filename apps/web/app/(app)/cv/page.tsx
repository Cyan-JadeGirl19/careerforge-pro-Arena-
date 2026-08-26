"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError, exportUrl } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type {
  CvAnalysisOut,
  CvOut,
  CvVersion,
  ParsedCv,
  TailoredCv,
} from "../../../../../packages/contracts/types";

const KIND_LABEL: Record<string, string> = {
  master_ats: "ATS Enterprise (legacy)",
  master_modern: "Modern Professional (legacy)",
  master_role: "Master",
  custom: "Custom",
};

export default function CvStudioPage() {
  const { session } = useSession();
  const [cv, setCv] = useState<CvOut | null>(null);
  const [parsed, setParsed] = useState<ParsedCv | null>(null);
  const [analysis, setAnalysis] = useState<CvAnalysisOut | null>(null);
  const [versions, setVersions] = useState<CvVersion[]>([]);
  const [tailored, setTailored] = useState<TailoredCv | null>(null);

  // intake
  const [paste, setPaste] = useState("");
  const [file, setFile] = useState<File | null>(null);
  // tailoring
  const [jdTitle, setJdTitle] = useState("");
  const [jdCompany, setJdCompany] = useState("");
  const [jdText, setJdText] = useState("");
  const [jdId, setJdId] = useState<string | null>(null);
  // custom version
  const [customRole, setCustomRole] = useState("");
  const [customEmph, setCustomEmph] = useState("");
  const [customExcl, setCustomExcl] = useState("");
  // state
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown) =>
    setError(e instanceof ApiError ? `${e.message} (${e.code})` : "Something went wrong.");

  const refresh = useCallback(async (cvId: string) => {
    const p = await api.getParsedCv(cvId);
    setParsed(p);
    try {
      setAnalysis(await api.latestAnalysis(cvId));
    } catch {
      setAnalysis(null);
    }
    setVersions(await api.listVersions(cvId));
  }, []);

  useEffect(() => {
    if (!session) return;
    (async () => {
      try {
        const all = await api.listCvs(session.profileId);
        if (all.length > 0) {
          const latest = all[all.length - 1];
          setCv(latest);
          await refresh(latest.id);
        }
      } catch {
        // no CVs yet
      }
    })();
  }, [session, refresh]);

  const savePasted = async () => {
    if (!session || paste.trim().length < 40) return;
    setBusy("saving");
    setError(null);
    try {
      const newCv = await api.createCv(session.profileId, { title: "Master CV", text: paste.trim() });
      setCv(newCv);
      setPaste("");
      await refresh(newCv.id);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const upload = async () => {
    if (!session || !file) return;
    setBusy("uploading");
    setError(null);
    try {
      const { cv: newCv, parsed: p } = await api.uploadCv(session.profileId, file);
      setCv(newCv);
      setParsed(p);
      setFile(null);
      await refresh(newCv.id);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const analyze = async () => {
    if (!cv) return;
    setBusy("analyzing");
    setError(null);
    try {
      setAnalysis(await api.analyzeCv(cv.id));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const buildMasters = async () => {
    if (!cv) return;
    setBusy("masters");
    setError(null);
    try {
      setVersions(await api.buildMasters(cv.id));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const createCustom = async () => {
    if (!cv || !customRole.trim()) return;
    setBusy("custom");
    setError(null);
    try {
      const v = await api.createVersion(cv.id, {
        kind: "custom",
        role_focus: customRole.trim(),
        emphasize: customEmph.split(",").map((s) => s.trim()).filter(Boolean),
        exclude: customExcl.split(",").map((s) => s.trim()).filter(Boolean),
      });
      setVersions((vs) => [...vs, v]);
      setCustomRole("");
      setCustomEmph("");
      setCustomExcl("");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const addJd = async () => {
    if (!session || !jdTitle.trim() || jdText.trim().length < 40) return;
    setBusy("jd");
    setError(null);
    try {
      const jd = await api.createJobDescription(session.profileId, {
        title: jdTitle.trim(),
        company: jdCompany.trim() || null,
        text: jdText.trim(),
      });
      setJdId(jd.id);
      setJdText("");
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const tailor = async (versionId?: string) => {
    if (!cv || !jdId) return;
    const vid = versionId ?? versions[0]?.id;
    if (!vid) return;
    setBusy("tailor");
    setError(null);
    try {
      const res = await api.tailorVersion(vid, jdId);
      setTailored(await api.getTailored(res.tailored_cv_id));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <div className="eyebrow">CV Studio</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Your CV, your versions</h1>
      <p className="muted" style={{ margin: "0 0 20px" }}>
        Upload once; the program builds and exports. Everything stays truthful to your real
        experience.
      </p>
      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}

      <div className="grid2">
        <div className="card">
          <h3>1 · Intake</h3>
          <div className="field">
            <label>Upload PDF / DOCX</label>
            <input type="file" accept=".pdf,.docx,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </div>
          <div className="field">
            <label>…or paste your CV text</label>
            <textarea value={paste} onChange={(e) => setPaste(e.target.value)} placeholder="Paste your CV here…" />
          </div>
          <div className="row">
            <button className="btn" onClick={upload} disabled={!file || !!busy}>
              {busy === "uploading" ? "Parsing…" : "Upload & parse"}
            </button>
            <button className="btn secondary" onClick={savePasted} disabled={paste.trim().length < 40 || !!busy}>
              {busy === "saving" ? "Saving…" : "Save pasted CV"}
            </button>
          </div>
          {cv && (
            <p className="muted" style={{ marginTop: 10 }}>
              Current CV: <b>{cv.title}</b> (v{cv.version}, {cv.source_type}) · {cv.text?.length ?? 0} chars
            </p>
          )}
        </div>

        <div className="card">
          <h3>2 · Parsed review</h3>
          {!parsed ? (
            <p className="muted">Your structured CV appears here after intake.</p>
          ) : (
            <>
              <div className="field">
                <label>Name</label>
                <input readOnly value={parsed.name} />
              </div>
              <div className="row">
                <div className="field" style={{ flex: 1 }}>
                  <label>Email</label>
                  <input readOnly value={parsed.email} />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label>Location</label>
                  <input readOnly value={parsed.location} />
                </div>
              </div>
              <div className="field">
                <label>Skills detected</label>
                <div>
                  {parsed.skills.map((s) => (
                    <span className="chip" key={s}>
                      {s}
                    </span>
                  ))}
                </div>
              </div>
              {parsed.experience.length > 0 && (
                <p className="muted">
                  {parsed.experience.length} role(s) parsed:{" "}
                  {parsed.experience.map((e) => e.title || e.company).join(", ")}
                </p>
              )}
              {parsed.extraction_notes.length > 0 && (
                <div className="alert info">
                  <b>Please confirm:</b>
                  <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
                    {parsed.extraction_notes.map((n) => (
                      <li key={n}>{n}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <hr className="divider" />

      {cv && (
        <>
          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h3 style={{ margin: 0 }}>3 · Analysis (transparent checks)</h3>
              <button className="btn secondary" onClick={analyze} disabled={!!busy}>
                {busy === "analyzing" ? "Analysing…" : "Analyse CV"}
              </button>
            </div>
            {analysis ? (
              <div className="grid2" style={{ marginTop: 14 }}>
                <div>
                  {analysis.checks.map((c) => (
                    <div key={c.check} style={{ padding: "4px 0", fontSize: 14 }}>
                      {c.passed ? "✅" : "⚠️"} <b>{c.check}</b> <span className="muted">— {c.detail}</span>
                    </div>
                  ))}
                </div>
                <div>
                  <b style={{ fontSize: 14 }}>Keyword map</b>
                  <div style={{ marginTop: 6 }}>
                    {analysis.keywords.map((k) => (
                      <span className={`chip ${k.present ? "" : "missing"}`} key={k.keyword}>
                        {k.present ? "✓ " : "+ "}
                        {k.keyword}
                      </span>
                    ))}
                  </div>
                  {analysis.gaps.length > 0 && (
                    <ul style={{ fontSize: 13, color: "var(--muted)", marginTop: 10, paddingLeft: 18 }}>
                      {analysis.gaps.map((g) => (
                        <li key={g}>{g}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ) : (
              <p className="muted">Run the analysis to see exactly what was checked — no mystery scores.</p>
            )}
          </div>

          <div className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h3 style={{ margin: 0 }}>4 · Your CV versions</h3>
              <button className="btn" onClick={buildMasters} disabled={!!busy}>
                {busy === "masters" ? "Building…" : "Build masters for my top roles"}
              </button>
            </div>
            <p className="muted" style={{ margin: "6px 0 12px" }}>
              The program finds up to three roles your skills already match (from your own CV)
              and builds one master per role — each single-column and parser-safe, reordered so
              that role's skills come first. Nothing is invented. Plus unlimited custom versions
              below.
            </p>
            <div className="stack">
              {versions.map((v) => (
                <div className="item" key={v.id}>
                  <h4>
                    {v.title} <span className="chip neutral">{KIND_LABEL[v.kind] ?? v.kind}</span>
                  </h4>
                  <p>{v.content.headline || v.content.summary.slice(0, 120)}</p>
                  {v.content.summary && (
                    <p className="muted" style={{ fontSize: 13 }}>
                      {v.content.summary}
                    </p>
                  )}
                  {v.notes && v.notes.length > 0 && (
                    <div className="alert info" style={{ marginTop: 8 }}>
                      {v.notes.map((n, k) => (
                        <div key={k}>• {n}</div>
                      ))}
                    </div>
                  )}
                  <div className="actions">
                    <a className="btn" href={exportUrl("versions", v.id, "docx")}>
                      DOCX
                    </a>
                    <a className="btn secondary" href={exportUrl("versions", v.id, "pdf")}>
                      PDF
                    </a>
                    <a className="btn secondary" href={exportUrl("versions", v.id, "txt")}>
                      Text
                    </a>
                    <a className="btn secondary" href={exportUrl("versions", v.id, "json")}>
                      JSON
                    </a>
                  </div>
                </div>
              ))}
              {versions.length === 0 && (
                <div className="empty">No versions yet — build the three masters with one click.</div>
              )}
            </div>
            <hr className="divider" />
            <h3 style={{ fontSize: 14 }}>Create a custom version</h3>
            <div className="grid2">
              <div className="field">
                <label>Target role (e.g. Marketing Manager)</label>
                <input value={customRole} onChange={(e) => setCustomRole(e.target.value)} />
              </div>
              <div className="field">
                <label>Emphasise (comma-separated)</label>
                <input
                  value={customEmph}
                  onChange={(e) => setCustomEmph(e.target.value)}
                  placeholder="communication, data analysis"
                />
              </div>
            </div>
            <div className="field">
              <label>Exclude (comma-separated)</label>
              <input
                value={customExcl}
                onChange={(e) => setCustomExcl(e.target.value)}
                placeholder="onboarding, internal tools"
              />
            </div>
            <button className="btn secondary" onClick={createCustom} disabled={!customRole.trim() || !!busy}>
              {busy === "custom" ? "Creating…" : "Create custom version"}
            </button>
            <p className="muted" style={{ marginTop: 8 }}>
              Custom versions reposition your genuine, transferable experience only. If you lack
              evidence for a claim, the app will ask rather than invent.
            </p>
          </div>

          <div className="card">
            <h3>5 · Tailor to a specific job</h3>
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
                style={{ minHeight: 160 }}
              />
            </div>
            <div className="row">
              <button className="btn secondary" onClick={addJd} disabled={!jdTitle.trim() || jdText.trim().length < 40 || !!busy}>
                {busy === "jd" ? "Saving…" : "Save job description"}
              </button>
              {jdId && versions.length > 0 && (
                <button className="btn" onClick={() => tailor()} disabled={!!busy}>
                  {busy === "tailor" ? "Tailoring…" : "Tailor best version to this job"}
                </button>
              )}
            </div>

            {tailored && (
              <div style={{ marginTop: 18 }} className="stack">
                <div className="item">
                  <h4>
                    Tailored: {tailored.title}{" "}
                    <span className="chip brand">{tailored.report.coverage}% keyword coverage</span>
                  </h4>
                  <p>
                    <b>Keywords in the JD:</b>
                  </p>
                  <div>
                    {tailored.report.keywords.map((k) => (
                      <span className={`chip ${k.in_candidate_profile ? "" : "missing"}`} key={k.keyword}>
                        {k.in_candidate_profile ? "✓ " : "+ "}
                        {k.keyword}
                      </span>
                    ))}
                  </div>
                  {tailored.report.gaps.length > 0 && (
                    <>
                      <p style={{ marginTop: 8 }}>
                        <b>Gaps (answer these with real evidence — they are never filled in):</b>
                      </p>
                      <ul style={{ fontSize: 13, color: "var(--muted)", paddingLeft: 18 }}>
                        {tailored.report.gaps.map((g) => (
                          <li key={g}>{g}</li>
                        ))}
                      </ul>
                    </>
                  )}
                  <div className="actions">
                    <a className="btn" href={exportUrl("tailored", tailored.id, "docx")}>
                      Download tailored DOCX
                    </a>
                    <a className="btn secondary" href={exportUrl("tailored", tailored.id, "pdf")}>
                      PDF
                    </a>
                    <a className="btn secondary" href={exportUrl("tailored", tailored.id, "txt")}>
                      Text
                    </a>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
