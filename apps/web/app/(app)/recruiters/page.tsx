"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { Job } from "../../../../../packages/contracts/types";

interface Contact {
  id: string;
  name: string | null;
  title: string | null;
  company: string | null;
  profile_url: string | null;
  email: string | null;
  email_status: "none" | "published" | "pattern_suggested";
  suggested_emails: string[];
  job_title: string | null;
  notes: string | null;
  verified: boolean;
  suppressed: boolean;
  source: string;
  source_url: string | null;
  created_at: string;
}

function EmailBadge({ c }: { c: Contact }) {
  if (c.email_status === "published") {
    return (
      <span className="chip" title="Published on the public page">
        {c.email} ✓ published
      </span>
    );
  }
  if (c.email_status === "pattern_suggested" && c.suggested_emails.length > 0) {
    return (
      <span className="chip missing" title="Guessed pattern - NOT verified">
        ⚠ unverified: {c.suggested_emails.join(", ")}
      </span>
    );
  }
  if (c.email) return <span className="chip">{c.email}</span>;
  return <span className="chip neutral">no email</span>;
}

export default function RecruiterFinderPage() {
  const { session } = useSession();
  const pid = session?.profileId ?? "";

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<Contact | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [draftIssues, setDraftIssues] = useState<string[]>([]);

  // forms
  const [urlInput, setUrlInput] = useState("");
  const [companyInput, setCompanyInput] = useState("");
  const [form, setForm] = useState({
    name: "",
    title: "",
    company: "",
    email: "",
    profile_url: "",
    job_title: "",
    notes: "",
  });
  const [outreachJob, setOutreachJob] = useState("");
  const [outreachTone, setOutreachTone] = useState("direct");

  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    if (!pid) return;
    try {
      const [cs, js] = await Promise.all([
        api.listRecruiters(pid),
        api.searchJobs({ sa_only: false, sort: "newest" }).catch(() => [] as Job[]),
      ]);
      setContacts(cs);
      setJobs(js);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load contacts.");
    }
  }, [pid]);

  useEffect(() => {
    load();
  }, [load]);

  const fail = (e: unknown, fallback: string) =>
    setError(e instanceof ApiError ? e.message : fallback);

  const doExtract = async () => {
    if (!pid || !urlInput.trim()) return;
    setBusy("extract");
    setError(null);
    setInfo(null);
    try {
      const found = await api.extractRecruiters(pid, {
        url: urlInput.trim(),
        company: companyInput.trim() || undefined,
      });
      setUrlInput("");
      setCompanyInput("");
      await load();
      setInfo(
        found.length === 0
          ? "No publicly displayed recruiter details on that page. That's common - add the contact manually below, or try the company's careers page."
          : `Found ${found.length} public contact(s) and added them. Pattern-suggested emails are unverified - confirm before use.`,
      );
    } catch (e) {
      fail(e, "Could not read that page.");
    } finally {
      setBusy(null);
    }
  };

  const doManual = async () => {
    if (!pid) return;
    setBusy("manual");
    setError(null);
    try {
      await api.createRecruiter(pid, {
        name: form.name.trim() || null,
        title: form.title.trim() || null,
        company: form.company.trim() || null,
        email: form.email.trim() || null,
        profile_url: form.profile_url.trim() || null,
        job_title: form.job_title.trim() || null,
        notes: form.notes.trim() || null,
        email_status: form.email.trim() ? "published" : "none",
      });
      setForm({ name: "", title: "", company: "", email: "", profile_url: "", job_title: "", notes: "" });
      await load();
    } catch (e) {
      fail(e, "Could not add the contact.");
    } finally {
      setBusy(null);
    }
  };

  const patchContact = async (id: string, patch: Record<string, unknown>) => {
    try {
      await api.updateRecruiter(id, patch);
      await load();
    } catch (e) {
      fail(e, "Could not update the contact.");
    }
  };

  const doOutreach = async () => {
    if (!selected) return;
    setBusy("outreach");
    setError(null);
    setCopied(false);
    try {
      const r = await api.outreachDraft(selected.id, {
        job_title: outreachJob || selected.job_title || undefined,
        tone: outreachTone,
      });
      setDraft(r.draft);
      setDraftIssues(r.issues);
    } catch (e) {
      fail(
        e,
        "Could not draft the outreach. You need the outreach consent enabled in Settings.",
      );
    } finally {
      setBusy(null);
    }
  };

  const copy = async () => {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(draft);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard may be blocked
    }
  };

  const active = contacts.filter((c) => !c.suppressed);

  return (
    <div>
      <div className="eyebrow">Recruiter Finder</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>
        Publicly displayed recruiter &amp; poster details
      </h1>
      <p className="muted" style={{ margin: "0 0 16px" }}>
        We only capture what employers display publicly: names, titles, public profile links, and
        published emails. Guessed email patterns are clearly marked <b>unverified</b>. No login
        bypass, no hidden data, no mass harvesting. Outreach is a draft you approve - nothing is
        sent.
      </p>

      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      {info && <div className="alert info">{info}</div>}

      <div className="grid2">
        <div className="card">
          <h3>Add from a job page link</h3>
          <div className="field">
            <label>Job posting URL (one public page)</label>
            <input
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://www.careerjunction.co.za/job/…"
            />
          </div>
          <div className="field">
            <label>Company (helps label the contact)</label>
            <input
              value={companyInput}
              onChange={(e) => setCompanyInput(e.target.value)}
              placeholder="Acme"
            />
          </div>
          <button className="btn" onClick={doExtract} disabled={busy === "extract" || !urlInput.trim()}>
            {busy === "extract" ? "Reading page…" : "Extract public details"}
          </button>
        </div>

        <div className="card">
          <h3>Add manually</h3>
          <div className="grid2">
            <div className="field">
              <label>Name</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="field">
              <label>Title</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
          </div>
          <div className="grid2">
            <div className="field">
              <label>Company</label>
              <input value={form.company} onChange={(e) => setForm({ ...form, company: e.target.value })} />
            </div>
            <div className="field">
              <label>Email (as published)</label>
              <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
          </div>
          <div className="grid2">
            <div className="field">
              <label>Public profile URL</label>
              <input
                value={form.profile_url}
                onChange={(e) => setForm({ ...form, profile_url: e.target.value })}
                placeholder="https://linkedin.com/in/…"
              />
            </div>
            <div className="field">
              <label>Job title</label>
              <input value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} />
            </div>
          </div>
          <div className="field">
            <label>Notes</label>
            <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
          <button className="btn secondary" onClick={doManual} disabled={busy === "manual"}>
            {busy === "manual" ? "Adding…" : "Add contact"}
          </button>
        </div>
      </div>

      <hr className="divider" />

      <div className="stack">
        <p className="muted" style={{ margin: 0 }}>
          {active.length} contact{active.length === 1 ? "" : "s"}
        </p>
        {active.map((c) => (
          <div
            className="item"
            key={c.id}
            onClick={() => {
              setSelected(c);
              setDraft(null);
              setOutreachJob(c.job_title || "");
            }}
            style={{ cursor: "pointer", borderLeft: selected?.id === c.id ? "4px solid var(--brand)" : "1px solid var(--line)" }}
          >
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h4 style={{ margin: 0 }}>
                {c.name ?? "Unknown recruiter"} {c.title ? `· ${c.title}` : ""} {c.company ? `@ ${c.company}` : ""}
              </h4>
              <div className="row" onClick={(e) => e.stopPropagation()}>
                <button
                  className="btn secondary"
                  style={{ padding: "5px 10px", fontSize: 12 }}
                  onClick={() => patchContact(c.id, { verified: !c.verified })}
                >
                  {c.verified ? "✓ verified" : "mark verified"}
                </button>
                <button
                  className="btn secondary"
                  style={{ padding: "5px 10px", fontSize: 12 }}
                  onClick={() => patchContact(c.id, { suppressed: true })}
                >
                  suppress
                </button>
              </div>
            </div>
            <div className="row" style={{ marginTop: 6 }}>
              <EmailBadge c={c} />
              {c.profile_url && (
                <a className="chip brand" href={c.profile_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                  linked profile
                </a>
              )}
              {c.source_url && (
                <a className="chip neutral" href={c.source_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                  source
                </a>
              )}
              {c.job_title && <span className="chip neutral">{c.job_title}</span>}
            </div>
          </div>
        ))}
        {active.length === 0 && (
          <div className="empty">No contacts yet. Add one from a job link or manually.</div>
        )}
      </div>

      {selected && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>
            Outreach draft for {selected.name ?? "this contact"}
            {selected.company ? ` @ ${selected.company}` : ""}
          </h3>
          <p className="muted">
            Draft only - it is never sent. Review it, edit if you like, and send it yourself
            (Gmail integration arrives in Phase 3 with your approval at every step).
          </p>
          <div className="row" style={{ flexWrap: "wrap" }}>
            <select
              value={outreachJob}
              onChange={(e) => setOutreachJob(e.target.value)}
              style={{ flex: 2, minWidth: 200, border: "1px solid var(--line)", borderRadius: 8, padding: "9px 11px" }}
            >
              <option value="">Job title (default: {selected.job_title || "n/a"})</option>
              {(jobs.length ? jobs : []).slice(0, 30).map((j) => (
                <option key={j.id} value={j.title}>
                  {j.title} {j.company ? `@ ${j.company}` : ""}
                </option>
              ))}
            </select>
            <select
              value={outreachTone}
              onChange={(e) => setOutreachTone(e.target.value)}
              style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "9px 11px" }}
            >
              <option value="direct">Direct</option>
              <option value="warm">Warm</option>
            </select>
            <button className="btn" onClick={doOutreach} disabled={busy === "outreach"}>
              {busy === "outreach" ? "Drafting…" : "Draft outreach"}
            </button>
          </div>
          {draft && (
            <>
              <pre className="script" style={{ marginTop: 12 }}>{draft}</pre>
              {draftIssues.length > 0 && (
                <div className="alert info" style={{ marginTop: 10 }}>
                  {draftIssues.map((i, k) => (
                    <div key={k}>• {i}</div>
                  ))}
                </div>
              )}
              <button className="btn secondary" onClick={copy} style={{ marginTop: 10 }}>
                {copied ? "Copied ✓" : "Copy to clipboard"}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
