"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { ConsentItem, ConsentOut, ProfileOut } from "../../../../../packages/contracts/types";

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

  const load = useCallback(async () => {
    if (!session) return;
    try {
      setProfile(await api.getProfile(session.profileId));
      setConsents(await api.listConsents(session.profileId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load settings.");
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

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
