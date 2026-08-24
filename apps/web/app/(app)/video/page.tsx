"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import { deleteRecording, listRecordings, saveRecording } from "../../../lib/media-store";
import Recorder from "../../../components/recorder";
import Teleprompter from "../../../components/teleprompter";
import type { Application, VideoResponse } from "../../../../../packages/contracts/types";

const LENGTHS = [30, 60, 90, 120, 180] as const;
const LENGTH_LABEL: Record<number, string> = {
  30: "30 seconds",
  60: "1 minute",
  90: "1.5 minutes",
  120: "2 minutes",
  180: "3 minutes",
};

const QUESTIONS = [
  "Tell us a bit about yourself and why you are a good fit for this role.",
  "Why do you want to work with us?",
  "Why are you suitable for this role?",
  "Describe a difficult customer interaction and how you handled it.",
  "Explain a project you completed that you are proud of.",
  "Why should we hire you remotely from South Africa?",
  "Record a short sales pitch.",
];

export default function VideoStudioPage() {
  const { session } = useSession();
  const [apps, setApps] = useState<Application[]>([]);
  const [app, setApp] = useState<Application | null>(null);
  const [question, setQuestion] = useState("");
  const [keyPoints, setKeyPoints] = useState("");
  const [exclusions, setExclusions] = useState("");
  const [tone, setTone] = useState("natural");
  const [targetSeconds, setTargetSeconds] = useState<number>(60);
  const [video, setVideo] = useState<VideoResponse | null>(null);
  const [script, setScript] = useState("");
  const [recordings, setRecordings] = useState<Array<{ id: string; blob: Blob; seconds: number; createdAt: string }>>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewSeconds, setPreviewSeconds] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  const loadRecordings = useCallback(async (applicationId?: string) => {
    try {
      const all = await listRecordings(applicationId);
      setRecordings(all);
    } catch {
      // no recordings
    }
  }, []);

  useEffect(() => {
    if (!session) return;
    (async () => {
      try {
        const all = await api.listApplications(session.profileId);
        setApps(all);
        const url = new URLSearchParams(window.location.search);
        const wanted = url.get("app");
        const initial = (wanted && all.find((a) => a.id === wanted)) || all[0] || null;
        if (initial) {
          setApp(initial);
          setVideo(initial.videos[0] ?? null);
          if (initial.videos[0]) setScript(initial.videos[0].script_text);
        }
        if (initial) await loadRecordings(initial.id);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Could not load applications.");
      }
    })();
  }, [session, loadRecordings]);

  const selectApp = async (id: string) => {
    const a = apps.find((x) => x.id === id) || null;
    setApp(a);
    setError(null);
    setSavedNote(null);
    setVideo(a?.videos[0] ?? null);
    setScript(a?.videos[0]?.script_text ?? "");
    await loadRecordings(id);
  };

  const body = () => ({
    question: question.trim(),
    key_points: keyPoints.split(",").map((s) => s.trim()).filter(Boolean),
    exclusions: exclusions.split(",").map((s) => s.trim()).filter(Boolean),
    tone,
    target_seconds: targetSeconds,
    mode: "recording",
  });

  const generate = async () => {
    if (!app || !question.trim()) return;
    setBusy(true);
    setError(null);
    setSavedNote(null);
    try {
      const v = await api.createVideo(app.id, body());
      setVideo(v);
      setScript(v.script_text);
      setApp((a) => (a ? { ...a, videos: [...a.videos, v] } : a));
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.message} (${e.code}) — video consent is required in Settings for this module.`
          : "Could not generate the script.",
      );
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    if (!video || !question.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const v = await api.regenerateVideo(video.id, body());
      setVideo(v);
      setScript(v.script_text);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not regenerate.");
    } finally {
      setBusy(false);
    }
  };

  const onRecording = async (blob: Blob, seconds: number) => {
    if (!app) return;
    const url = URL.createObjectURL(blob);
    setPreviewUrl(url);
    setPreviewSeconds(seconds);
    const id = `rec-${Date.now()}`;
    try {
      await saveRecording({
        id,
        applicationId: app.id,
        blob,
        createdAt: new Date().toISOString(),
        seconds,
      });
      await loadRecordings(app.id);
      if (video) await api.updateVideoMedia(video.id, "uploaded");
      setSavedNote(
        `Saved locally (private to this browser). ${
          Math.abs(seconds - targetSeconds) <= targetSeconds * 0.25
            ? "Length looks right."
            : `It's ${Math.round(seconds)}s vs your ${targetSeconds}s target — you can re-record or trim later.`
        }`,
      );
    } catch {
      setSavedNote("Recording captured in this session; could not persist to local storage.");
    }
  };

  const download = (blob: Blob, name: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  };

  const removeRecording = async (id: string) => {
    await deleteRecording(id);
    await loadRecordings(app?.id);
  };

  if (!session) return null;

  return (
    <div>
      <div className="eyebrow">Voice/Video Application Studio</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Recorded responses, done well</h1>
      <p className="muted" style={{ margin: "0 0 18px" }}>
        Paste the employer's exact question, tell the program what to include, and get a natural
        script. Record with the teleprompter — 30 seconds up to 3 minutes. Each question gets its
        own saved response.
      </p>
      {error && <div className="alert error">{error}</div>}
      {savedNote && <div className="alert ok">{savedNote}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="field">
          <label>Application</label>
          <select value={app?.id ?? ""} onChange={(e) => selectApp(e.target.value)} disabled={apps.length === 0}>
            {apps.length === 0 && <option value="">No applications yet — create one in the Applications page</option>}
            {apps.map((a) => (
              <option key={a.id} value={a.id}>
                {a.jd_title} {a.jd_company ? `@ ${a.jd_company}` : ""}
              </option>
            ))}
          </select>
        </div>
      </div>

      {app && (
        <div className="stack">
          <div className="card">
            <h3>1 · The question</h3>
            <div className="field">
              <label>Employer's exact question</label>
              <textarea value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Paste the question exactly as written…" />
            </div>
            <div>
              {QUESTIONS.map((q) => (
                <button key={q} type="button" className="btn ghost" style={{ padding: "6px 10px", fontSize: 12, marginRight: 6, marginBottom: 6 }} onClick={() => setQuestion(q)}>
                  {q.slice(0, 52)}…
                </button>
              ))}
            </div>
            <div className="grid2">
              <div className="field">
                <label>Key points to include (comma-separated)</label>
                <input value={keyPoints} onChange={(e) => setKeyPoints(e.target.value)} placeholder="my remote setup, European hours" />
              </div>
              <div className="field">
                <label>Do not mention (comma-separated)</label>
                <input value={exclusions} onChange={(e) => setExclusions(e.target.value)} placeholder="PayFast, salary" />
              </div>
            </div>
            <div className="row">
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Tone</label>
                <select value={tone} onChange={(e) => setTone(e.target.value)}>
                  <option value="natural">Natural</option>
                  <option value="formal">Formal</option>
                  <option value="warm">Warm</option>
                  <option value="direct">Direct</option>
                </select>
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label>Length</label>
                <select value={targetSeconds} onChange={(e) => setTargetSeconds(Number(e.target.value))}>
                  {LENGTHS.map((l) => (
                    <option key={l} value={l}>
                      {LENGTH_LABEL[l]}
                    </option>
                  ))}
                </select>
              </div>
              <button className="btn" onClick={generate} disabled={busy || !question.trim()}>
                {busy ? "Working…" : video ? "Generate new script" : "Generate script"}
              </button>
            </div>
          </div>

          {script && (
            <div className="card">
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h3 style={{ margin: 0 }}>2 · Your script (edit anything)</h3>
                {video && (
                  <button className="btn secondary" onClick={regenerate} disabled={busy}>
                    Regenerate
                  </button>
                )}
              </div>
              <p className="muted">
                Built only from your real CV plus your key points. Acronyms stay readable; nothing is
                invented.
              </p>
              <textarea
                value={script}
                onChange={(e) => setScript(e.target.value)}
                style={{ minHeight: 140, width: "100%", border: "1px solid var(--line)", borderRadius: 8, padding: 12, fontSize: 15, lineHeight: 1.6 }}
              />
              <div style={{ marginTop: 16 }}>
                <b style={{ fontSize: 14 }}>Teleprompter</b>
                <div style={{ marginTop: 8 }}>
                  <Teleprompter text={script} targetSeconds={targetSeconds} />
                </div>
              </div>
            </div>
          )}

          <div className="card">
            <h3>3 · Record</h3>
            <p className="muted">
              Light on your face, quiet space, look at the camera. As many takes as you like — the
              take never leaves this browser until you choose to download it.
            </p>
            <Recorder onRecording={onRecording} />
            {previewUrl && (
              <div className="row" style={{ marginTop: 10 }}>
                <a className="btn" href={previewUrl} download={`response-${targetSeconds}s.webm`}>
                  Download this take ({Math.round(previewSeconds)}s)
                </a>
              </div>
            )}
          </div>

          <div className="card">
            <h3>Saved responses for this application</h3>
            {recordings.length === 0 ? (
              <p className="muted">No saved recordings yet.</p>
            ) : (
              <div className="stack">
                {recordings.map((r) => (
                  <div className="item" key={r.id}>
                    <video src={URL.createObjectURL(r.blob)} controls style={{ width: "100%", borderRadius: 8, background: "#101216", marginBottom: 8 }} />
                    <div className="row">
                      <button className="btn secondary" onClick={() => download(r.blob, `response-${Math.round(r.seconds)}s.webm`)}>
                        Download
                      </button>
                      <button className="btn secondary" style={{ color: "var(--red)" }} onClick={() => removeRecording(r.id)}>
                        Delete
                      </button>
                      <span className="muted">{Math.round(r.seconds)}s · {new Date(r.createdAt).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
