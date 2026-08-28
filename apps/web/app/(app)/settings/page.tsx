"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { ConsentItem, ConsentOut, GmailStatus, ProfileOut, StorageUsage } from "../../../../../packages/contracts/types";

const CONSENT_INFO: Record<ConsentItem, string> = {
  profile_processing: "Store and analyse your CV to build your CV versions.",
  job_matching: "Compare your profile with job descriptions you provide.",
  recruiter_contact: "Look up publicly displayed recruiter or job-poster details.",
  outreach_sending: "Draft personalised outreach emails (never sent without your approval).",
  reference_sharing: "Include your references only in applications you approve.",
  media_use: "Process photos, audio or video you explicitly approve.",
  video_recording: "Generate scripts for voice/video application responses.",
};

export default function SettingsPage() {
  const { session, logout } = useSession();
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [consents, setConsents] = useState<ConsentOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState("");
  const [gmail, setGmail] = useState<GmailStatus | null>(null);
  const [gmailBusy, setGmailBusy] = useState(false);
  const [storage, setStorage] = useState<StorageUsage | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    try {
      setProfile(await api.getProfile(session.profileId));
      setConsents(await api.listConsents(session.profileId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load settings.");
    }
  }, [session]);

  const loadGmail = useCallback(async () => {
    if (!session) return;
    try {
      setGmail(await api.gmailStatus(session.profileId));
    } catch {
      setGmail(null);
    }
    api
      .storageUsage(session.profileId)
      .then(setStorage)
      .catch(() => setStorage(null));
  }, [session]);

  const fmtBytes = (n: number) =>
    n >= 1024 * 1024 ? `${(n / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(0, Math.round(n / 1024))} KB`;

  useEffect(() => {
    load();
    loadGmail();
  }, [load, loadGmail]);

  if (!session) return null;

  const toggle = async (item: ConsentItem, granted: boolean) => {
    try {
      if (granted) {
        await api.grantConsent(session.profileId, { item, granted: true });
      } else {
        await api.revokeConsent(session.profileId, item);
      }
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update consent.");
    }
  };

  const active = (item: ConsentItem) =>
    consents.find((c) => c.item === item)?.granted &&
    consents.find((c) => c.item === item)?.revoked_at === null;

  const exportData = async () => {
    if (!session) return;
    const blob = new Blob([JSON.stringify({ profile, consents }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "careerforge-my-data.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  };

  const connectGmail = async () => {
    if (!session) return;
    setGmailBusy(true);
    setError(null);
    try {
      const { auth_url } = await api.gmailAuthorize(session.profileId);
      window.open(auth_url, "_blank", "width=600,height=720");
      // The Google redirect lands on the Outreach page; poll for the
      // connection to appear (user completes sign-in in the popup).
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        const st = await api.gmailStatus(session.profileId);
        if (st.connected) {
          setGmail(st);
          setError(null);
          return;
        }
      }
      setError("We couldn't detect the connection yet - check the popup, then reload this page.");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.message}`
          : "Could not start the Google sign-in.",
      );
    } finally {
      setGmailBusy(false);
    }
  };

  const disconnectGmail = async () => {
    if (!session) return;
    setGmailBusy(true);
    try {
      await api.gmailDisconnect(session.profileId);
      setGmail(await api.gmailStatus(session.profileId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Disconnect failed.");
    } finally {
      setGmailBusy(false);
    }
  };

  const erase = async () => {
    if (!session || confirmDelete !== "ERASE") return;
    try {
      await api.deleteProfile(session.profileId);
      logout();
      window.location.href = "/onboarding";
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Deletion failed.");
    }
  };

  return (
    <div>
      <div className="eyebrow">Settings / Privacy</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>You control everything</h1>
      <p className="muted" style={{ margin: "0 0 18px" }}>
        Consents are separate and revocable. Deletion removes your profile and everything derived
        from it.
      </p>
      {error && <div className="alert error">{error}</div>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Profile</h3>
        {profile && (
          <table className="table">
            <tbody>
              <tr>
                <td>Name</td>
                <td>
                  {profile.first_name ?? "—"} {profile.last_name ?? ""}
                </td>
              </tr>
              <tr>
                <td>Timezone</td>
                <td>{profile.timezone}</td>
              </tr>
              <tr>
                <td>Member since</td>
                <td>{new Date(profile.created_at).toLocaleDateString()}</td>
              </tr>
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Consents</h3>
        {(Object.keys(CONSENT_INFO) as ConsentItem[]).map((item) => {
          const isOn = active(item);
          return (
            <label key={item} className="checkbox">
              <input type="checkbox" checked={isOn} onChange={(e) => toggle(item, e.target.checked)} />
              <span>
                <b>
                  {item.replace(/_/g, " ")}
                  {item === "profile_processing" && <span className="chip neutral"> required</span>}
                </b>
                <p>{CONSENT_INFO[item]}</p>
              </span>
            </label>
          );
        })}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Gmail (optional)</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Connect your own Google account to create outreach emails as drafts in your Gmail.
          Least-privilege scope: the app can <b>only create drafts</b> in your own mailbox — it
          cannot read mail, send mail, or see your contacts. You review every draft and click
          send yourself.
        </p>
        {gmail?.connected ? (
          <div className="row" style={{ alignItems: "center" }}>
            <span style={{ fontSize: 14 }}>
              Connected as <b>{gmail.email}</b>
              {gmail.connected_at ? ` · since ${new Date(gmail.connected_at).toLocaleDateString()}` : ""}
            </span>
            <button className="btn secondary" onClick={disconnectGmail} disabled={gmailBusy}>
              {gmailBusy ? "Working…" : "Disconnect"}
            </button>
          </div>
        ) : (
          <button className="btn" onClick={connectGmail} disabled={gmailBusy}>
            {gmailBusy ? "Waiting for sign-in…" : "Connect Gmail"}
          </button>
        )}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Storage</h3>
        {storage ? (
          <table className="table">
            <tbody>
              <tr>
                <td>Database total (free hosting limit: 1 GB)</td>
                <td>{storage.database_size}</td>
              </tr>
              <tr>
                <td>Video media ({storage.video_media_count} file{storage.video_media_count === 1 ? "" : "s"})</td>
                <td>{fmtBytes(storage.video_media_bytes)}</td>
              </tr>
              <tr>
                <td>Reference documents</td>
                <td>{fmtBytes(storage.reference_document_bytes)}</td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="muted">Loading…</p>
        )}
        <p className="muted" style={{ fontSize: 12.5 }}>
          Video files take the most space. Delete old takes in the Voice/Video Studio to free
          room. Large uploads are auto-compressed on the server, so new videos stay small.
        </p>
      </div>

      <div className="card">
        <h3>Your data</h3>
        <div className="row">
          <button className="btn secondary" onClick={exportData}>
            Export my data (JSON)
          </button>
        </div>
        <hr className="divider" />
        <div className="alert info">
          Erasing is permanent: profile, CVs, versions, applications, letters, scripts and
          consents. Type <b>ERASE</b> to confirm.
        </div>
        <div className="row">
          <input
            value={confirmDelete}
            onChange={(e) => setConfirmDelete(e.target.value)}
            placeholder="ERASE"
            style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "9px 11px" }}
          />
          <button
            className="btn"
            style={{ background: "var(--red)" }}
            onClick={erase}
            disabled={confirmDelete !== "ERASE"}
          >
            Delete everything
          </button>
        </div>
      </div>
    </div>
  );
}
