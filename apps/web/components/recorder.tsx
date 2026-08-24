"use client";

import { useEffect, useRef, useState } from "react";

interface RecorderProps {
  /** Called with the recorded blob + duration when a take completes. */
  onRecording: (blob: Blob, seconds: number) => void;
}

/**
 * Browser video + audio recorder (MediaRecorder). The take plays back for
 * review; the candidate can re-record as many times as needed. Nothing is
 * uploaded anywhere - the blob is handed to the caller.
 */
export default function Recorder({ onRecording }: RecorderProps) {
  const [status, setStatus] = useState<"idle" | "recording" | "done" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [seconds, setSeconds] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  };

  useEffect(() => {
    return () => {
      stopStream();
      if (timerRef.current) clearInterval(timerRef.current);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: true,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp8,opus")
        ? "video/webm;codecs=vp8,opus"
        : "video/webm";
      const rec = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 2_500_000 });
      chunksRef.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      rec.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "video/webm" });
        setPreviewUrl(URL.createObjectURL(blob));
        setStatus("done");
        onRecording(blob, (Date.now() - startRef.current) / 1000);
        stopStream();
        if (videoRef.current) videoRef.current.srcObject = null;
      };
      recorderRef.current = rec;
      startRef.current = Date.now();
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
      rec.start(500);
      setStatus("recording");
    } catch (e) {
      setStatus("error");
      setError(
        "Camera/microphone access was blocked or unavailable. Allow access in your browser and try again.",
      );
      stopStream();
    }
  };

  const stop = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    recorderRef.current?.stop();
  };

  const cancel = () => {
    if (status === "recording") stop();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setSeconds(0);
    setStatus("idle");
  };

  return (
    <div>
      <video
        ref={videoRef}
        playsInline
        muted
        style={{
          width: "100%",
          borderRadius: 10,
          background: "#101216",
          display: previewUrl ? "none" : "block",
          aspectRatio: "16/9",
        }}
      />
      {previewUrl && (
        <video
          key={previewUrl}
          src={previewUrl}
          controls
          playsInline
          style={{ width: "100%", borderRadius: 10, background: "#101216", aspectRatio: "16/9" }}
        />
      )}
      {status === "error" && <p style={{ color: "var(--red)" }}>{error}</p>}
      <div style={{ display: "flex", gap: 8, marginTop: 10, alignItems: "center", flexWrap: "wrap" }}>
        {status !== "recording" ? (
          <button className="btn" onClick={start}>
            {status === "done" ? "Re-record take" : "Start recording"}
          </button>
        ) : (
          <button className="btn" style={{ background: "var(--red)" }} onClick={stop}>
            Stop ({seconds}s)
          </button>
        )}
        {(status === "recording" || status === "done") && (
          <button className="btn secondary" onClick={cancel}>
            Discard
          </button>
        )}
        <span style={{ fontSize: 13, color: "var(--muted)" }}>
          {status === "recording"
            ? "Recording… speak naturally, look at the camera."
            : status === "done"
              ? "Review your take, then save it below."
              : "Make sure you have light on your face and a quiet space."}
        </span>
      </div>
    </div>
  );
}
