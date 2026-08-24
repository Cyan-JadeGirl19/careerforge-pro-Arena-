"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { Reference, ReferenceDocument } from "../../../../../packages/contracts/types";

const TYPE_LABEL: Record<string, string> = {
  current: "Current",
  former: "Former",
  academic: "Academic",
  personal: "Personal",
};

export default function ReferencesPage() {
  const { session } = useSession();
  const pid = session?.profileId ?? "";

  const [refs, setRefs] = useState<Reference[]>([]);
  const [form, setForm] = useState({
    name: "",
    title: "",
    relationship: "",
    company: "",
    email: "",
    phone: "",
    type: "current",
    notes: "",
    permission_confirmed: false,
  });
  const [listFile, setListFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [docs, setDocs] = useState<Record<string, ReferenceDocument[]>>({});
  const fileInputs = useRef<Record<string, HTMLInputElement | null>>({});

  const load = useCallback(async () => {
    if (!pid) return;
    try {
      setRefs(await api.listReferences(pid));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load references.");
    }
  }, [pid]);

  useEffect(() => {
    load();
  }, [load]);

  const fail = (e: unknown, fallback: string) =>
    setError(e instanceof ApiError ? e.message : fallback);

  const addRef = async () => {
    if (!pid || !form.name.trim()) return;
    setBusy("add");
    setError(null);
    setInfo(null);
    try {
      await api.createReference(pid, {
        name: form.name.trim(),
        title: form.title.trim() || null,
        relationship: form.relationship.trim() || null,
        company: form.company.trim() || null,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
        type: form.type,
        notes: form.notes.trim() || null,
        permission_confirmed: form.permission_confirmed,
      });
      setForm({
        name: "", title: "", relationship: "", company: "", email: "",
        phone: "", type: "current", notes: "", permission_confirmed: false,
      });
      await load();
    } catch (e) {
      fail(e, "Could not add the reference. Enable the reference consent in Settings first.");
    } finally {
      setBusy(null);
    }
  };

  const parseList = async () => {
    if (!pid || !listFile) return;
    setBusy("parse");
    setError(null);
    setInfo(null);
    try {
      const created = await api.parseReferenceList(pid, listFile);
      setListFile(null);
      await load();
      setInfo(
        `Added ${created.length} reference(s) from the list. None are marked as permission-confirmed - confirm each one before it can be shared.`,
      );
    } catch (e) {
      fail(e, "Could not read that file.");
    } finally {
      setBusy(null);
    }
  };

  const patch = async (id: string, body: Record<string, unknown>) => {
    try {
      await api.updateReference(id, body);
      await load();
    } catch (e) {
      fail(e, "Could not update.");
    }
  };

  const remove = async (id: string, name: string) => {
    if (!window.confirm(`Delete ${name}? Their uploaded documents are removed too.`)) return;
    try {
      await api.deleteReference(id);
      await load();
    } catch (e) {
      fail(e, "Could not delete.");
    }
  };

  const toggleDocs = async (ref: Reference) => {
    if (expanded === ref.id) {
      setExpanded(null);
      return;
    }
    setExpanded(ref.id);
    try {
      await refreshDocs(ref.id);
    } catch {
      setDocs((d) => ({ ...d, [ref.id]: [] }));
    }
  };

  const refreshDocs = async (refId: string) => {
    const updated = await api.listReferenceDocuments(refId);
    setDocs((d) => ({ ...d, [refId]: updated }));
  };

  const uploadDoc = async (ref: Reference, file: File) => {
    try {
      await api.uploadReferenceDocument(ref.id, file);
      await refreshDocs(ref.id);
    } catch (e) {
      fail(e, "Upload failed (PDF, DOCX or TXT, max 5 MB).");
    }
  };

  const removeDoc = async (refId: string, docId: string) => {
    try {
      await api.deleteReferenceDocument(docId);
      await refreshDocs(refId);
    } catch (e) {
      fail(e, "Could not delete the document.");
    }
  };

  return (
    <div>
      <div className="eyebrow">References and Profile</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Private Reference Manager</h1>
      <p className="muted" style={{ margin: "0 0 16px" }}>
        References are private by default and never appear on your CVs. They are attached only to
        applications you select, and only after you confirm you have permission to share each
        person&rsquo;s details.
      </p>

      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      {info && <div className="alert info">{info}</div>}

      <div className="grid2">
        <div className="card">
          <h3>Add a reference</h3>
          <div className="grid2">
            <div className="field">
              <label>Name *</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="field">
              <label>Title</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
          </div>
          <div className="grid2">
            <div className="field">
              <label>Relationship</label>
              <input
                value={form.relationship}
                onChange={(e) => setForm({ ...form, relationship: e.target.value })}
                placeholder="former manager"
              />
            </div>
            <div className="field">
              <label>Company</label>
              <input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
            </div>
          </div>
          <div className="grid2">
            <div className="field">
              <label>Email</label>
              <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div className="field">
              <label>Phone</label>
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </div>
          </div>
          <div className="grid2">
            <div className="field">
              <label>Type</label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                <option value="current">Current</option>
                <option value="former">Former</option>
                <option value="academic">Academic</option>
                <option value="personal">Personal</option>
              </select>
            </div>
            <div className="field">
              <label>Notes</label>
              <input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="may contact after interview"
              />
            </div>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.permission_confirmed}
              onChange={(e) => setForm({ ...form, permission_confirmed: e.target.checked })}
            />
            <span>
              <b>I confirm I have permission to share this person&rsquo;s contact details.</b>
              <p>Required before the reference can be attached to any application.</p>
            </span>
          </label>
          <button className="btn" onClick={addRef} disabled={busy === "add" || !form.name.trim()}>
            {busy === "add" ? "Adding…" : "Add reference"}
          </button>
        </div>

        <div className="card">
          <h3>Upload a reference list</h3>
          <p className="muted">
            PDF, DOCX or TXT. Names and contact details are parsed into separate references - all
            starting with permission <b>unconfirmed</b>.
          </p>
          <div className="field">
            <label>Reference list file</label>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(e) => setListFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <button className="btn secondary" onClick={parseList} disabled={busy === "parse" || !listFile}>
            {busy === "parse" ? "Parsing…" : "Parse and add"}
          </button>
        </div>
      </div>

      <hr className="divider" />

      <div className="stack">
        <p className="muted" style={{ margin: 0 }}>
          {refs.length} reference{refs.length === 1 ? "" : "s"}
        </p>
        {refs.map((r) => (
          <div className="item" key={r.id}>
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <h4 style={{ margin: 0 }}>
                {r.name} {r.title ? `· ${r.title}` : ""} {r.company ? `@ ${r.company}` : ""}
              </h4>
              <div className="row">
                <span className="chip neutral">{TYPE_LABEL[r.type] ?? r.type}</span>
                {r.permission_confirmed ? (
                  <span className="chip" title="Permission to share confirmed">
                    ✓ permission confirmed
                  </span>
                ) : (
                  <span className="chip missing" title="Confirm before sharing">
                    ⚠ permission not confirmed
                  </span>
                )}
                {r.approved ? null : <span className="chip missing">not approved</span>}
              </div>
            </div>
            <p>
              {[r.relationship, r.phone, r.email].filter(Boolean).join(" · ") || "no contact details yet"}
              {r.notes ? ` · ${r.notes}` : ""}
            </p>
            <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
              <button
                className="btn secondary"
                style={{ padding: "6px 10px", fontSize: 12 }}
                onClick={() => patch(r.id, { permission_confirmed: !r.permission_confirmed })}
              >
                {r.permission_confirmed ? "revoke confirmation" : "confirm permission"}
              </button>
              <button
                className="btn secondary"
                style={{ padding: "6px 10px", fontSize: 12 }}
                onClick={() => patch(r.id, { approved: !r.approved })}
              >
                {r.approved ? "un-approve" : "approve for sharing"}
              </button>
              <button
                className="btn secondary"
                style={{ padding: "6px 10px", fontSize: 12 }}
                onClick={() => toggleDocs(r)}
              >
                documents ({(docs[r.id] || r.documents || []).length})
              </button>
              <button
                className="btn secondary"
                style={{ padding: "6px 10px", fontSize: 12, color: "var(--red)" }}
                onClick={() => remove(r.id, r.name)}
              >
                delete
              </button>
            </div>
            {expanded === r.id && (
              <div style={{ marginTop: 10 }}>
                {(docs[r.id] || r.documents || []).map((d) => (
                  <div key={d.id} className="row" style={{ marginBottom: 6 }}>
                    <a className="btn secondary" style={{ padding: "6px 10px", fontSize: 12 }} href={`/api/v1/documents/${d.id}/download`}>
                      ⬇ {d.filename}
                    </a>
                    <button
                      className="btn secondary"
                      style={{ padding: "6px 10px", fontSize: 12, color: "var(--red)" }}
                      onClick={() => removeDoc(r.id, d.id)}
                    >
                      delete doc
                    </button>
                  </div>
                ))}
                <input
                  ref={(el) => {
                    fileInputs.current[r.id] = el;
                  }}
                  type="file"
                  accept=".pdf,.docx,.txt"
                  style={{ fontSize: 13 }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadDoc(r, f);
                    e.target.value = "";
                  }}
                />
              </div>
            )}
          </div>
        ))}
        {refs.length === 0 && (
          <div className="empty">No references yet. Add one or upload a reference list.</div>
        )}
      </div>
    </div>
  );
}
