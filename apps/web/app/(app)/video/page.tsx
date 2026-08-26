"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import { deleteRecording, listRecordings, saveRecording } from "../../../lib/media-store";
import Recorder from "../../../components/recorder";
import Teleprompter from "../../../components/teleprompter";
import type {
  Application,
  VideoJob,
  VideoMedia,
  VideoQualityReport,
  VideoResponse,
} from "../../../../../packages/contracts/types";

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

const FRAMINGS = [
  { value: "none", label: "Keep original size" },
  { value: "16x9", label: "16:9 landscape (standard)" },
  { value: "9x16", label: "9:16 vertical (phone)" },
  { value: "1x1", label: "1:1 square" },
];

function fmtSize(n: number): string {
  return n >= 1024 * 1024
    ? `${(n / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(n / 1024))} KB`;
}

const STATUS_STYLE: Record<string, { bg: string; fg: string; glyph: string }> = {
  pass: { bg: "#e8f6ee", fg: "#1d7a46", glyph: "✓" },
  warn: { bg: "#fff6e0", fg: "#9a6a08", glyph: "!" },
  fail: { bg: "#fdecec", fg: "#b03030", glyph: "✕" },
};

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
  const [lastTake, setLastTake] = useState<Blob | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState<string | null>(null);

  // --- studio (server-side) state ---
  const [consent, setConsent] = useState(false);
  const [serverBusy, setServerBusy] = useState<string | null>(null);
  const [jobNote, setJobNote] = useState<string | null>(null);
  const [report, setReport] = useState<{ mediaId: string; report: VideoQualityReport } | null>(null);
  const [capText, setCapText] = useState("");
  const [capPreview, setCapPreview] = useState<Record<string, string>>({});
  const [enh, setEnh] = useState({
    auto: true,
    normalize: true,
    brightness: 0,
    contrast: 0,
    saturation: 0,
    framing: "none" as "none" | "16x9" | "9x16" | "1x1",
    burn: false,
  });
  const [enhanceSource, setEnhanceSource] = useState<string>("");
  const [trimFor, setTrimFor] = useState<string | null>(null);
  const [trimStart, setTrimStart] = useState(0);
  const [trimEnd, setTrimEnd] = useState(0);
  const [introName, setIntroName] = useState("");
  const [introRole, setIntroRole] = useState("");
  const [introSeconds, setIntroSeconds] = useState(3);

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
    setReport(null);
    setVideo(a?.videos[0] ?? null);
    setScript(a?.videos[0]?.script_text ?? "");
    setEnhanceSource("");
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
    setLastTake(blob);
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
        } ${"Send it to the studio below to enhance, caption and export it."}`,
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

  // --- studio helpers ---

  const runJob = async (jobId: string): Promise<Record<string, unknown> | null> => {
    for (let i = 0; i < 300; i++) {
      const st: VideoJob = await api.getVideoJob(jobId);
      if (st.status !== "running") {
        setJobNote(null);
        if (st.status === "failed") throw new Error(st.error || "Processing failed.");
        return st.result;
      }
      setJobNote(`${st.phase}… ${Math.round(st.progress * 100)}%`);
      await new Promise((r) => setTimeout(r, 1500));
    }
    setJobNote(null);
    throw new Error("Still processing — give it a minute, then check back.");
  };

  const refreshVideo = async () => {
    if (!app) return;
    const fresh = await api.getApplication(app.id);
    setApp(fresh);
    setApps((all) => all.map((a) => (a.id === fresh.id ? fresh : a)));
    setVideo(fresh.videos.find((v) => v.id === video?.id) ?? fresh.videos[0] ?? null);
  };

  const ensureVideo = async (): Promise<string> => {
    if (video) return video.id;
    if (!app) throw new Error("Pick an application first.");
    const v = await api.createVideo(app.id, {
      question: question.trim() || "Why are you a good fit for this role?",
      key_points: keyPoints.split(",").map((s) => s.trim()).filter(Boolean),
      exclusions: exclusions.split(",").map((s) => s.trim()).filter(Boolean),
      tone,
      target_seconds: targetSeconds,
      mode: "recording",
    });
    setVideo(v);
    setApp((a) => (a ? { ...a, videos: [...a.videos, v] } : a));
    return v.id;
  };

  const sendToStudio = async (blob: Blob, filename: string) => {
    if (!consent) {
      setError("Tick the consent first — we need your confirmation that the face and voice are yours (or you have permission).");
      return;
    }
    setServerBusy("upload");
    setError(null);
    setSavedNote(null);
    try {
      const vid = await ensureVideo();
      const v = await api.uploadVideoMedia(vid, blob, filename, consent);
      setVideo(v);
      await refreshVideo();
      setReport(null);
      setSavedNote("Uploaded and stored privately with this application. Run the quality check, then enhance and export.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const onFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    void sendToStudio(f, f.name || "video.mp4");
  };

  const doAnalyze = async (mediaId: string) => {
    if (!video) return;
    setServerBusy("analyze");
    setError(null);
    try {
      const res = await api.analyzeVideoMedia(video.id, mediaId);
      setReport({ mediaId, report: res.report });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Quality check failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const doEnhance = async () => {
    if (!video || !enhanceSource) return;
    setServerBusy("enhance");
    setError(null);
    try {
      const job = await api.enhanceVideoMedia(video.id, enhanceSource, {
        auto_enhance: enh.auto,
        normalize_audio: enh.normalize,
        brightness: enh.brightness,
        contrast: enh.contrast,
        saturation: enh.saturation,
        framing: enh.framing,
        burn_captions: enh.burn,
      });
      const result = await runJob(job.job_id);
      await refreshVideo();
      if (result && typeof result.media_id === "string" && result.report) {
        setReport({
          mediaId: result.media_id as string,
          report: result.report as VideoQualityReport,
        });
      }
      setSavedNote("Enhanced MP4 ready — review the preview and quality check, then download.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Enhance failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const doExportMp4 = async (mediaId: string) => {
    if (!video) return;
    setServerBusy("mp4");
    setError(null);
    try {
      const job = await api.exportVideoMp4(video.id, mediaId);
      await runJob(job.job_id);
      await refreshVideo();
      setSavedNote("MP4 conversion ready in your files below.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "MP4 conversion failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const doTrim = async (mediaId: string) => {
    if (!video) return;
    setServerBusy("trim");
    setError(null);
    try {
      const job = await api.trimVideoMedia(video.id, mediaId, {
        start: trimStart,
        end: trimEnd,
      });
      const result = await runJob(job.job_id);
      await refreshVideo();
      setTrimFor(null);
      if (result && typeof result.media_id === "string" && result.report) {
        setReport({ mediaId: result.media_id as string, report: result.report as VideoQualityReport });
      }
      setSavedNote("Trimmed MP4 ready in your files below.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Trim failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const doHeadshot = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!video || !f) return;
    if (!consent) {
      setError("Tick the consent first — we need your confirmation that this photo is you (or you have permission).");
      return;
    }
    setServerBusy("headshot");
    setError(null);
    try {
      const v = await api.uploadHeadshot(video.id, f, f.name || "headshot.jpg", consent);
      setVideo(v);
      await refreshVideo();
      setSavedNote("Headshot stored privately — now build your intro card.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Headshot upload failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const doIntroCard = async () => {
    if (!video) return;
    setServerBusy("intro");
    setError(null);
    try {
      const job = await api.buildIntroCard(video.id, {
        name: introName,
        role: introRole,
        seconds: introSeconds,
      });
      const result = await runJob(job.job_id);
      await refreshVideo();
      if (result && typeof result.media_id === "string" && result.report) {
        setReport({ mediaId: result.media_id as string, report: result.report as VideoQualityReport });
      }
      setSavedNote("Intro card video and thumbnail ready in your files below.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Intro card failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const doExportAudio = async (mediaId: string) => {
    if (!video) return;
    setServerBusy("audio");
    setError(null);
    try {
      const v = await api.exportVideoAudio(video.id, mediaId);
      setVideo(v);
      await refreshVideo();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Audio export failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const doCaptions = async () => {
    if (!video) return;
    setServerBusy("captions");
    setError(null);
    try {
      const v = await api.generateVideoCaptions(video.id, {
        transcript: capText,
        use_script: !capText.trim(),
      });
      setVideo(v);
      await refreshVideo();
      const cap = (v.media ?? []).find((m) => m.kind === "captions");
      if (cap) {
        const txt = await fetch(api.videoMediaUrl(video.id, cap.id)).then((r) => r.text());
        setCapPreview((p) => ({ ...p, [cap.id]: txt }));
      }
      setSavedNote("Captions built from your text (timed proportionally — review before you send).");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not build captions.");
    } finally {
      setServerBusy(null);
    }
  };

  const doDeleteMedia = async (mediaId: string) => {
    if (!video) return;
    setServerBusy("delete");
    try {
      await api.deleteVideoMedia(video.id, mediaId);
      if (report?.mediaId === mediaId) setReport(null);
      await refreshVideo();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Delete failed.");
    } finally {
      setServerBusy(null);
    }
  };

  const showCapPreview = async (mediaId: string) => {
    if (!video || capPreview[mediaId]) return;
    const txt = await fetch(api.videoMediaUrl(video.id, mediaId)).then((r) => r.text());
    setCapPreview((p) => ({ ...p, [mediaId]: txt }));
  };

  const media: VideoMedia[] = video?.media ?? [];
  const videoMedia = media.filter((m) => m.kind === "original" || m.kind === "enhanced");
  const hasCaptions = media.some((m) => m.kind === "captions");
  const hasHeadshot = media.some((m) => m.kind === "headshot");
  const effectiveSource =
    enhanceSource && videoMedia.some((m) => m.id === enhanceSource)
      ? enhanceSource
      : videoMedia[videoMedia.length - 1]?.id ?? "";

  if (!session) return null;

  return (
    <div>
      <div className="eyebrow">Voice/Video Application Studio</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Recorded responses, done well</h1>
      <p className="muted" style={{ margin: "0 0 18px" }}>
        Paste the employer's exact question, tell the program what to include, and get a natural
        script. Record with the teleprompter — 30 seconds up to 3 minutes — then send it to the
        studio to check quality, enhance (colour, audio, framing), caption and export as MP4 or MP3.
        Each question gets its own saved response.
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
              take stays in this browser until you send it to the studio.
            </p>
            <Recorder onRecording={onRecording} />
            {previewUrl && (
              <div className="row" style={{ marginTop: 10 }}>
                <a className="btn" href={previewUrl} download={`response-${targetSeconds}s.webm`}>
                  Download this take ({Math.round(previewSeconds)}s)
                </a>
                {lastTake && (
                  <button
                    className="btn secondary"
                    onClick={() => sendToStudio(lastTake, `take-${Math.round(previewSeconds)}s.webm`)}
                    disabled={serverBusy !== null}
                  >
                    {serverBusy === "upload" ? "Uploading…" : "Send this take to the studio →"}
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="card">
            <h3>4 · Studio — quality check, enhance & export</h3>
            <p className="muted">
              Enhancement is real file processing on <b>your own footage</b>: colour/lighting,
              audio level, framing and captions. CareerForge Pro never creates a synthetic face or
              voice. Captions are timed from the text you provide (not speech recognition) — review
              them before you send. Files are stored privately with this application.
            </p>

            <label style={{ display: "flex", gap: 8, alignItems: "flex-start", margin: "10px 0", fontSize: 13.5, lineHeight: 1.45 }}>
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
                style={{ marginTop: 3 }}
              />
              <span>
                <b>Consent:</b> I confirm the face and voice in this video are mine, or I have
                permission to use this material. Required before upload and export.
              </span>
            </label>

            <div className="row" style={{ flexWrap: "wrap" }}>
              <label className="btn secondary" style={{ cursor: "pointer" }}>
                {serverBusy === "upload" ? "Uploading…" : "Upload a video file…"}
                <input type="file" accept="video/mp4,video/webm,video/quicktime,video/x-m4v" onChange={onFilePick} hidden disabled={serverBusy !== null || !consent} />
              </label>
              <span className="muted" style={{ fontSize: 12.5 }}>
                MP4, WebM or MOV, up to 150 MB. Or use “Send this take to the studio” above after recording.
              </span>
            </div>

            {media.length > 0 && (
              <>
                <h4 style={{ margin: "18px 0 8px", fontSize: 14 }}>Your files</h4>
                <div className="stack">
                  {media.map((m) => (
                    <div className="item" key={m.id}>
                      {(m.kind === "original" || m.kind === "enhanced") && (
                        <video src={api.videoMediaUrl(video!.id, m.id)} controls style={{ width: "100%", maxWidth: 420, borderRadius: 8, background: "#101216", marginBottom: 8 }} />
                      )}
                      {(m.kind === "headshot" || m.kind === "thumbnail") && (
                        <img src={api.videoMediaUrl(video!.id, m.id)} alt={m.filename} style={{ width: 200, maxHeight: 150, objectFit: "cover", borderRadius: 8, marginBottom: 8 }} />
                      )}
                      <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                        <span
                          style={{
                            fontSize: 11.5,
                            fontWeight: 700,
                            padding: "3px 8px",
                            borderRadius: 999,
                            background: m.kind === "enhanced" ? "#e8f0fe" : "#eef0f3",
                            color: m.kind === "enhanced" ? "#1a56b0" : "#444",
                            textTransform: "capitalize",
                          }}
                        >
                          {m.kind}
                        </span>
                        <span className="muted" style={{ fontSize: 12.5 }}>
                          {m.filename} · {fmtSize(m.size)}
                          {m.duration ? ` · ${Math.round(m.duration)}s` : ""}
                        </span>
                        <span style={{ flex: 1 }} />
                        {(m.kind === "original" || m.kind === "enhanced") && (
                          <>
                            <button className="btn secondary" onClick={() => doAnalyze(m.id)} disabled={serverBusy !== null}>
                              {serverBusy === "analyze" ? "Checking…" : "Quality check"}
                            </button>
                            <button
                              className="btn secondary"
                              onClick={() => {
                                const d = m.duration ?? 0;
                                setTrimStart(0);
                                setTrimEnd(Math.max(0, Math.round(d)));
                                setTrimFor(trimFor === m.id ? null : m.id);
                              }}
                              disabled={serverBusy !== null}
                            >
                              Trim
                            </button>
                            {m.kind === "original" && (
                              <button className="btn secondary" onClick={() => doExportMp4(m.id)} disabled={serverBusy !== null}>
                                {serverBusy === "mp4" ? "Converting…" : "Convert to MP4"}
                              </button>
                            )}
                            <button className="btn secondary" onClick={() => doExportAudio(m.id)} disabled={serverBusy !== null}>
                              {serverBusy === "audio" ? "Working…" : "MP3 audio"}
                            </button>
                          </>
                        )}
                        {m.kind === "captions" && (
                          <>
                            <button className="btn secondary" onClick={() => showCapPreview(m.id)} disabled={serverBusy !== null}>
                              View
                            </button>
                          </>
                        )}
                        <a className="btn secondary" href={api.videoMediaUrl(video!.id, m.id)} download={m.filename}>
                          Download
                        </a>
                        <button className="btn secondary" style={{ color: "var(--red)" }} onClick={() => doDeleteMedia(m.id)} disabled={serverBusy !== null}>
                          Delete
                        </button>
                      </div>
                      {m.kind === "captions" && capPreview[m.id] && (
                        <pre style={{ background: "#14161a", color: "#d7dae0", borderRadius: 8, padding: 12, fontSize: 12, lineHeight: 1.5, maxHeight: 220, overflow: "auto", margin: "8px 0 0", whiteSpace: "pre-wrap" }}>
                          {capPreview[m.id]}
                        </pre>
                      )}
                      {trimFor === m.id && (
                        <div className="row" style={{ marginTop: 8, flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                          <label style={{ fontSize: 13 }}>
                            From (s){" "}
                            <input type="number" min={0} step={0.5} value={trimStart} onChange={(e) => setTrimStart(Number(e.target.value))} style={{ width: 70, border: "1px solid var(--line)", borderRadius: 6, padding: "5px 8px" }} />
                          </label>
                          <label style={{ fontSize: 13 }}>
                            To (s){m.duration ? ` of ${Math.round(m.duration)}` : ""}{" "}
                            <input type="number" min={0} step={0.5} value={trimEnd} onChange={(e) => setTrimEnd(Number(e.target.value))} style={{ width: 70, border: "1px solid var(--line)", borderRadius: 6, padding: "5px 8px" }} />
                          </label>
                          <button className="btn" onClick={() => doTrim(m.id)} disabled={serverBusy !== null || trimEnd <= trimStart}>
                            {serverBusy === "trim" ? "Trimming…" : "Trim → MP4"}
                          </button>
                          <span className="muted" style={{ fontSize: 12.5 }}>Cuts out everything before/after — the original stays untouched.</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                {videoMedia.length > 0 && (
                  <>
                    <h4 style={{ margin: "18px 0 8px", fontSize: 14 }}>Enhance & build MP4</h4>
                    <div className="grid2">
                      <div className="field" style={{ marginBottom: 0 }}>
                        <label>Source file</label>
                        <select value={effectiveSource} onChange={(e) => setEnhanceSource(e.target.value)} disabled={serverBusy !== null}>
                          {videoMedia.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.kind === "enhanced" ? "Enhanced" : "Original"} — {m.filename}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="field" style={{ marginBottom: 0 }}>
                        <label>Framing</label>
                        <select value={enh.framing} onChange={(e) => setEnh({ ...enh, framing: e.target.value as typeof enh.framing })} disabled={serverBusy !== null}>
                          {FRAMINGS.map((f) => (
                            <option key={f.value} value={f.value}>{f.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="row" style={{ marginTop: 10, flexWrap: "wrap", gap: 14 }}>
                      <label style={{ fontSize: 13.5, display: "flex", gap: 6, alignItems: "center" }}>
                        <input type="checkbox" checked={enh.auto} onChange={(e) => setEnh({ ...enh, auto: e.target.checked })} />
                        Auto colour & lighting (mild)
                      </label>
                      <label style={{ fontSize: 13.5, display: "flex", gap: 6, alignItems: "center" }}>
                        <input type="checkbox" checked={enh.normalize} onChange={(e) => setEnh({ ...enh, normalize: e.target.checked })} />
                        Normalize audio level
                      </label>
                      <label style={{ fontSize: 13.5, display: "flex", gap: 6, alignItems: "center" }}>
                        <input type="checkbox" checked={enh.burn} onChange={(e) => setEnh({ ...enh, burn: e.target.checked })} disabled={!hasCaptions || serverBusy !== null} />
                        Burn captions into video{!hasCaptions ? " (none yet)" : ""}
                      </label>
                    </div>
                    <div className="grid2" style={{ marginTop: 10 }}>
                      {(
                        [
                          ["brightness", "Brightness"],
                          ["contrast", "Contrast"],
                          ["saturation", "Colour"],
                        ] as const
                      ).map(([key, label]) => (
                        <div key={key} className="field" style={{ marginBottom: 0 }}>
                          <label>{label} ({enh[key] > 0 ? `+${enh[key]}` : enh[key]})</label>
                          <input
                            type="range"
                            min={-10}
                            max={10}
                            value={enh[key]}
                            onChange={(e) => setEnh({ ...enh, [key]: Number(e.target.value) })}
                            style={{ width: "100%" }}
                          />
                        </div>
                      ))}
                    </div>
                    <div className="row" style={{ marginTop: 12, alignItems: "center" }}>
                      <button className="btn" onClick={doEnhance} disabled={serverBusy !== null || !effectiveSource}>
                        {serverBusy === "enhance" ? `Enhancing… ${jobNote ?? ""}` : "Enhance → build MP4"}
                      </button>
                      {jobNote && serverBusy !== "enhance" && <span className="muted" style={{ fontSize: 12.5 }}>{jobNote}</span>}
                      <span className="muted" style={{ fontSize: 12.5 }}>
                        Takes a minute or two on long videos. The original is never modified.
                      </span>
                    </div>
                  </>
                )}

                <h4 style={{ margin: "18px 0 8px", fontSize: 14 }}>Captions (WebVTT)</h4>
                <div className="field">
                  <label>What you say in the video</label>
                  <textarea
                    value={capText}
                    onChange={(e) => setCapText(e.target.value)}
                    placeholder="Paste a rough transcript of what you say — or leave empty and tick 'use my script'."
                    style={{ minHeight: 90 }}
                  />
                </div>
                <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                  <button className="btn secondary" onClick={() => setCapText(script)} disabled={!script || serverBusy !== null}>
                    Use my script
                  </button>
                  <button className="btn" onClick={doCaptions} disabled={serverBusy !== null}>
                    {serverBusy === "captions" ? "Building…" : "Generate captions"}
                  </button>
                  <span className="muted" style={{ fontSize: 12.5 }}>
                    Timed proportionally across the video from your text — review the cues before
                    exporting. Not speech recognition.
                  </span>
                </div>

                <h4 style={{ margin: "18px 0 8px", fontSize: 14 }}>Headshot & intro card</h4>
                <p className="muted" style={{ marginTop: 0 }}>
                  Add your face before the answer starts: a 2–10 second intro card with your
                  name, role and headshot, plus a thumbnail image for the application portal.
                  Uses your approved photo and your real video — nothing synthetic.
                </p>
                <div className="grid2">
                  <div className="field" style={{ marginBottom: 0 }}>
                    <label>Headshot (JPG/PNG, your photo)</label>
                    <input type="file" accept="image/jpeg,image/png,image/webp" onChange={doHeadshot} disabled={serverBusy !== null || !consent} />
                  </div>
                  <div className="field" style={{ marginBottom: 0 }}>
                    <label>Intro length</label>
                    <select value={introSeconds} onChange={(e) => setIntroSeconds(Number(e.target.value))}>
                      {[2, 3, 5, 8].map((s) => (
                        <option key={s} value={s}>{s} seconds</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="grid2" style={{ marginTop: 10 }}>
                  <div className="field" style={{ marginBottom: 0 }}>
                    <label>Name (blank = your profile name)</label>
                    <input value={introName} onChange={(e) => setIntroName(e.target.value)} placeholder="e.g. Thando Ndlovu" />
                  </div>
                  <div className="field" style={{ marginBottom: 0 }}>
                    <label>Role (blank = your latest CV role)</label>
                    <input value={introRole} onChange={(e) => setIntroRole(e.target.value)} placeholder="e.g. Support Team Lead" />
                  </div>
                </div>
                <div className="row" style={{ marginTop: 12, flexWrap: "wrap", gap: 10, alignItems: "center" }}>
                  <button className="btn" onClick={doIntroCard} disabled={serverBusy !== null || !videoMedia.length || !hasHeadshot}>
                    {serverBusy === "intro" ? `Building… ${jobNote ?? ""}` : "Build intro card + thumbnail"}
                  </button>
                  <span className="muted" style={{ fontSize: 12.5 }}>
                    Prepends the card to your latest video file (the original is kept) and makes a
                    1280×720 thumbnail PNG. Takes a minute.
                  </span>
                </div>
              </>
            )}
          </div>

          {report && (
            <div className="card">
              <h3>
                Quality check{" "}
                <span
                  style={{
                    fontSize: 12.5,
                    fontWeight: 700,
                    padding: "3px 10px",
                    borderRadius: 999,
                    background: report.report.summary.ready ? "#e8f6ee" : "#fff6e0",
                    color: report.report.summary.ready ? "#1d7a46" : "#9a6a08",
                    marginLeft: 8,
                  }}
                >
                  {report.report.summary.ready
                    ? `Ready — ${report.report.summary.pass} pass · ${report.report.summary.warn} note(s)`
                    : `Needs attention — ${report.report.summary.fail} fail · ${report.report.summary.warn} note(s)`}
                </span>
              </h3>
              <div className="stack" style={{ marginTop: 10 }}>
                {report.report.checks.map((c) => {
                  const s = STATUS_STYLE[c.status] ?? STATUS_STYLE.pass;
                  return (
                    <div className="row" key={c.id} style={{ alignItems: "flex-start" }}>
                      <span
                        style={{
                          width: 22,
                          height: 22,
                          borderRadius: 999,
                          background: s.bg,
                          color: s.fg,
                          fontSize: 12,
                          fontWeight: 800,
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          flexShrink: 0,
                          marginTop: 1,
                        }}
                      >
                        {s.glyph}
                      </span>
                      <div style={{ minWidth: 0 }}>
                        <b style={{ fontSize: 13.5 }}>{c.label}</b>{" "}
                        <span className="muted" style={{ fontSize: 12.5 }}>— {c.detail}</span>
                        {c.tip && <div className="muted" style={{ fontSize: 12.5, marginTop: 2 }}>{c.tip}</div>}
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="muted" style={{ marginTop: 12, fontSize: 12.5 }}>{report.report.note}</p>
            </div>
          )}

          <div className="card">
            <h3>Saved responses for this application</h3>
            <p className="muted">
              Local takes stay private to this browser. Once sent to the studio they are stored with
              the application and appear in “Your files” above.
            </p>
            {recordings.length === 0 ? (
              <p className="muted">No saved recordings yet.</p>
            ) : (
              <div className="stack">
                {recordings.map((r) => (
                  <div className="item" key={r.id}>
                    <video src={URL.createObjectURL(r.blob)} controls style={{ width: "100%", borderRadius: 8, background: "#101216", marginBottom: 8 }} />
                    <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                      <button className="btn secondary" onClick={() => download(r.blob, `response-${Math.round(r.seconds)}s.webm`)}>
                        Download
                      </button>
                      <button
                        className="btn secondary"
                        onClick={() => sendToStudio(r.blob, `take-${Math.round(r.seconds)}s.webm`)}
                        disabled={serverBusy !== null}
                      >
                        {serverBusy === "upload" ? "Uploading…" : "Send to studio →"}
                      </button>
                      <button className="btn secondary" style={{ color: "var(--red)" }} onClick={() => removeRecording(r.id)}>
                        Delete
                      </button>
                      <span className="muted" style={{ fontSize: 12.5 }}>
                        {Math.round(r.seconds)}s · {new Date(r.createdAt).toLocaleDateString()}
                      </span>
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
