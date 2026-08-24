"use client";

import { useEffect, useRef, useState } from "react";

interface TeleprompterProps {
  text: string;
  /** Approximate seconds the delivery should take (drives scroll speed). */
  targetSeconds: number;
}

/**
 * Scrolling teleprompter for recording. Speed is derived from the script
 * length and the target delivery time, so a 180s script scrolls at roughly
 * 150 words/minute.
 */
export default function Teleprompter({ text, targetSeconds }: TeleprompterProps) {
  const [running, setRunning] = useState(false);
  const [speedFactor, setSpeedFactor] = useState(1);
  const scrollRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    if (!running || !scrollRef.current) return;
    const words = text.trim().split(/\s+/).length || 1;
    const msPerWord = (targetSeconds * 1000 * speedFactor) / words;
    let last = performance.now();
    let pos = 0;

    const step = (now: number) => {
      const el = scrollRef.current;
      if (!el) return;
      // scroll proportionally: full height over the target duration
      const totalMs = targetSeconds * 1000 * speedFactor;
      const max = el.scrollHeight - el.clientHeight;
      pos += (max / totalMs) * (now - last);
      last = now;
      if (pos >= max) {
        el.scrollTop = max;
        setRunning(false);
        return;
      }
      el.scrollTop = pos;
      rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [running, text, targetSeconds, speedFactor]);

  const reset = () => {
    setRunning(false);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  };

  return (
    <div>
      <div
        ref={scrollRef}
        style={{
          height: 260,
          overflowY: "auto",
          border: "1px solid var(--line)",
          borderRadius: 10,
          padding: "28px 34px",
          background: "#fff",
        }}
      >
        <p style={{ fontSize: 22, lineHeight: 1.7, margin: 0 }}>{text}</p>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap", alignItems: "center" }}>
        <button className="btn" onClick={() => setRunning((r) => !r)}>
          {running ? "Pause" : "Start"}
        </button>
        <button className="btn secondary" onClick={reset}>
          Reset
        </button>
        <label style={{ fontSize: 13, color: "var(--muted)", display: "flex", alignItems: "center", gap: 6 }}>
          Speed
          <input
            type="range"
            min={0.5}
            max={2}
            step={0.1}
            value={speedFactor}
            onChange={(e) => setSpeedFactor(Number(e.target.value))}
          />
          {speedFactor.toFixed(1)}×
        </label>
        <span style={{ fontSize: 13, color: "var(--muted)" }}>
          ~{Math.round(text.trim().split(/\s+/).length / (targetSeconds / 60))} words/min at 1×
        </span>
      </div>
    </div>
  );
}
