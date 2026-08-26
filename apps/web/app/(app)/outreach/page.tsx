"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { GmailStatus, OutreachDraftRow } from "../../../../../packages/contracts/types";

export default function OutreachPage() {
  const { session } = useSession();
  const [gmail, setGmail] = useState<GmailStatus | null>(null);
  const [drafts, setDrafts] = useState<OutreachDraftRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    try {
      const [g, d] = await Promise.all([
        api.gmailStatus(session.profileId),
        api.listOutreachDrafts(session.profileId),
      ]);
      setGmail(g);
      setDrafts(d);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load outreach.");
    }
  }, [session]);

  useEffect(() => {
    load();
    // The Google OAuth redirect lands here with ?gmail=connected
    const params = new URLSearchParams(window.location.search);
    if (params.get("gmail") === "connected") {
      setInfo("Gmail connected — you can now file outreach drafts in your own Gmail.");
      window.history.replaceState(null, "", "/outreach");
    }
  }, [load]);

  const connect = async () => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const { auth_url } = await api.gmailAuthorize(session.profileId);
      window.open(auth_url, "_blank", "width=600,height=720");
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const st = await api.gmailStatus(session.profileId);
        if (st.connected) {
          setGmail(st);
          setInfo("Gmail connected.");
          return;
        }
      }
      setError("We couldn't detect the connection yet - check the popup, then reload.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the Google sign-in.");
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    if (!session) return;
    setBusy(true);
    try {
      await api.gmailDisconnect(session.profileId);
      setGmail(await api.gmailStatus(session.profileId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Disconnect failed.");
    } finally {
      setBusy(false);
    }
  };

  if (!session) return null;

  return (
    <div>
      <div className="eyebrow">Gmail Outreach</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Drafts only — you stay in control</h1>
      <p className="muted" style={{ margin: "0 0 18px" }}>
        CareerForge writes the email from your real experience and files it as a draft in
        <b> your own Gmail</b>. It cannot read or send mail (scope: create drafts only). You
        review each draft, edit it if you like, and click send yourself.
      </p>
      {error && <div className="alert error">{error}</div>}
      {info && <div className="alert ok">{info}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Your Gmail</h3>
        {gmail?.connected ? (
          <div className="row" style={{ alignItems: "center" }}>
            <span>
              Connected as <b>{gmail.email}</b>
            </span>
            <button className="btn secondary" onClick={disconnect} disabled={busy}>
              {busy ? "Working…" : "Disconnect"}
            </button>
          </div>
        ) : (
          <div className="row" style={{ alignItems: "center", gap: 12 }}>
            <button className="btn" onClick={connect} disabled={busy}>
              {busy ? "Waiting for sign-in…" : "Connect your own Google account"}
            </button>
            <span className="muted" style={{ fontSize: 12.5 }}>
              Free - no card, no code from us: you sign in to Google yourself. If the
              deployment has no Google client configured yet, the button will tell you.
            </span>
          </div>
        )}
        <ul className="muted" style={{ fontSize: 13, marginTop: 12, paddingLeft: 18, margin: "12px 0 0" }}>
          <li>Limit of <b>20 drafts per hour</b> — keeps you out of spam filters and respectful to recruiters.</li>
          <li>Suppressed contacts can never receive a draft. If anyone asks you to stop, mark them suppressed in Recruiter Finder.</li>
          <li>Unverified (pattern-guessed) emails are never used — only confirmed addresses.</li>
        </ul>
      </div>

      <div className="card">
        <h3>Drafts filed in your Gmail</h3>
        {drafts.length === 0 ? (
          <p className="muted">
            No drafts yet. Go to <b>Recruiter Finder</b>, open a contact, draft the outreach and
            hit “Create Gmail draft”.
          </p>
        ) : (
          <div className="stack">
            {drafts.map((d) => (
              <div className="item" key={d.id}>
                <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                  <b style={{ fontSize: 14 }}>{d.subject}</b>
                  <span className="chip neutral">{d.tone}</span>
                  <span className="muted" style={{ fontSize: 12.5 }}>
                    to {d.to_email}
                    {d.recruiter_name ? ` · ${d.recruiter_name}` : ""}
                    {" · "}
                    {new Date(d.created_at).toLocaleString()}
                  </span>
                  <span style={{ flex: 1 }} />
                  <button
                    className="btn secondary"
                    style={{ padding: "5px 10px", fontSize: 12.5 }}
                    onClick={() => setExpanded(expanded === d.id ? null : d.id)}
                  >
                    {expanded === d.id ? "Hide" : "View"}
                  </button>
                  {d.gmail_url && (
                    <a
                      className="btn secondary"
                      style={{ padding: "5px 10px", fontSize: 12.5 }}
                      href={d.gmail_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open in Gmail
                    </a>
                  )}
                </div>
                {expanded === d.id && (
                  <pre className="script" style={{ marginTop: 10, whiteSpace: "pre-wrap" }}>
                    {d.body}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
