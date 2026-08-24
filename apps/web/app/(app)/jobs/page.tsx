"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { Job, SavedSearch, SourceStatus } from "../../../../../packages/contracts/types";

const SOURCE_LABEL: Record<string, string> = {
  wwr: "We Work Remotely",
  remoteok: "RemoteOK",
  remotive: "Remotive",
  adzuna: "Adzuna",
  user_url: "Your link",
};

function ageLabel(postedAt: string | null): string {
  if (!postedAt) return "age unknown";
  const d = new Date(postedAt).getTime();
  if (Number.isNaN(d)) return "age unknown";
  const days = Math.floor((Date.now() - d) / 86400000);
  if (days <= 0) return "today";
  if (days === 1) return "1 day";
  if (days < 30) return `${days} days`;
  return `${Math.floor(days / 30)} mo`;
}

export default function JobFinderPage() {
  const { session } = useSession();
  const pid = session?.profileId ?? "";

  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [health, setHealth] = useState<SourceStatus[]>([]);
  const [selected, setSelected] = useState<Job | null>(null);
  const [saved, setSaved] = useState<SavedSearch[]>([]);

  // filters
  const [q, setQ] = useState("");
  const [source, setSource] = useState("all");
  const [saOnly, setSaOnly] = useState(true);
  const [maxAge, setMaxAge] = useState(0);
  const [sort, setSort] = useState("newest");

  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [urlInput, setUrlInput] = useState("");
  const [nameInput, setNameInput] = useState("");

  const loadJobs = useCallback(async () => {
    try {
      const rows = await api.searchJobs({
        q: q || undefined,
        source: source === "all" ? undefined : source,
        sa_only: saOnly,
        max_age_days: maxAge || undefined,
        sort,
        profile_id: pid || undefined,
      });
      setJobs(rows);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load jobs.");
    }
  }, [q, source, saOnly, maxAge, sort, pid]);

  const loadHealth = useCallback(async () => {
    try {
      setHealth(await api.jobHealth());
    } catch {
      // non-fatal
    }
  }, []);

  const loadSaved = useCallback(async () => {
    if (!pid) return;
    try {
      setSaved(await api.listSavedSearches(pid));
    } catch {
      // non-fatal
    }
  }, [pid]);

  useEffect(() => {
    loadHealth();
    loadSaved();
  }, [loadHealth, loadSaved]);

  useEffect(() => {
    const t = setTimeout(loadJobs, 250);
    return () => clearTimeout(t);
  }, [loadJobs]);

  const sync = async () => {
    setSyncing(true);
    setError(null);
    setSyncResult(null);
    try {
      const r = await api.syncJobs();
      const bits = r.sources.map(
        (s) => `${s.source}: ${s.status}${s.error ? ` (${s.error})` : ""}`,
      );
      setSyncResult(`Sync done. ${bits.join(" · ")}. Total in pool: ${r.total_jobs}.`);
      await Promise.all([loadJobs(), loadHealth()]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Sync failed.");
    } finally {
      setSyncing(false);
    }
  };

  const openJob = async (j: Job) => {
    setError(null);
    try {
      const full = await api.getJob(j.id, pid || undefined);
      setSelected(full);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not open the job.");
    }
  };

  const createPackage = async (j: Job) => {
    if (!pid) return;
    setBusy("package");
    setError(null);
    try {
      const r = await api.jobToApplication(j.id, pid);
      window.location.href = `/applications/${r.application_id}`;
    } catch (e) {
      setError(
        e instanceof ApiError
          ? `${e.message} (${e.code}) — you need a CV and job-matching consent before packages can be built.`
          : "Could not create the package.",
      );
    } finally {
      setBusy(null);
    }
  };

  const addUrl = async () => {
    if (!pid || !urlInput.trim()) return;
    setBusy("url");
    setError(null);
    try {
      const j = await api.addJobUrl(pid, urlInput.trim());
      setUrlInput("");
      setSelected(j);
      await loadJobs();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not read that page.");
    } finally {
      setBusy(null);
    }
  };

  const saveSearch = async () => {
    if (!pid || !nameInput.trim()) return;
    try {
      await api.saveSearch(pid, nameInput.trim(), {
        q: q || null,
        source: source === "all" ? null : source,
        sa_only: saOnly,
        max_age_days: maxAge || null,
        sort,
      });
      setNameInput("");
      await loadSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save the search.");
    }
  };

  const applySearch = (s: SavedSearch) => {
    const f = s.filters || {};
    setQ((f.q as string) || "");
    setSource((f.source as string) || "all");
    setSaOnly(Boolean(f.sa_only ?? true));
    setMaxAge(Number(f.max_age_days || 0));
    setSort((f.sort as string) || "newest");
  };

  const removeSearch = async (id: string) => {
    if (!pid) return;
    try {
      await api.deleteSearch(pid, id);
      await loadSaved();
    } catch {
      // non-fatal
    }
  };

  return (
    <div>
      <div className="eyebrow">Job Finder</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Remote roles open to South Africa</h1>
      <p className="muted" style={{ margin: "0 0 16px" }}>
        Live listings from permitted public feeds. Eligibility and payment signals are read from the
        employer's own text — never guessed. One click turns a job into a full application package.
      </p>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <b style={{ fontSize: 14 }}>Sources</b>
            <div className="row" style={{ marginTop: 6 }}>
              {health.map((h) => (
                <span
                  key={h.source}
                  className={`chip ${h.enabled ? (h.status === "error" ? "missing" : "") : "neutral"}`}
                  title={h.error || ""}
                >
                  {SOURCE_LABEL[h.source] ?? h.source} · {h.fetched ?? 0}
                </span>
              ))}
            </div>
          </div>
          <button className="btn" onClick={sync} disabled={syncing}>
            {syncing ? "Syncing feeds…" : "Refresh jobs"}
          </button>
        </div>
        {syncResult && <div className="alert info" style={{ marginTop: 10, marginBottom: 0 }}>{syncResult}</div>}
        <p className="muted" style={{ marginTop: 8, marginBottom: 0 }}>
          LinkedIn, Indeed, CareerJunction and PNet have no permitted public feed, so they are not
          scraped. You can still add any single job by pasting its link below.
        </p>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="row" style={{ flexWrap: "wrap" }}>
          <input
            placeholder="Search role, skill or company…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ flex: 2, minWidth: 180, border: "1px solid var(--line)", borderRadius: 8, padding: "9px 11px" }}
          />
          <select value={source} onChange={(e) => setSource(e.target.value)} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "9px 11px" }}>
            <option value="all">All sources</option>
            <option value="wwr">We Work Remotely</option>
            <option value="remoteok">RemoteOK</option>
            <option value="remotive">Remotive</option>
            <option value="adzuna">Adzuna</option>
            <option value="user_url">Your links</option>
          </select>
          <select value={maxAge} onChange={(e) => setMaxAge(Number(e.target.value))} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "9px 11px" }}>
            <option value={0}>Any age</option>
            <option value={2}>Posted ≤ 2 days</option>
            <option value={7}>Posted ≤ 7 days</option>
            <option value={14}>Posted ≤ 14 days</option>
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value)} style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "9px 11px" }}>
            <option value="newest">Newest</option>
            <option value="oldest">Oldest</option>
          </select>
          <label className="checkbox" style={{ padding: 0 }}>
            <input type="checkbox" checked={saOnly} onChange={(e) => setSaOnly(e.target.checked)} />
            <span>
              <b>Open to SA</b>
            </span>
          </label>
        </div>

        <hr className="divider" />
        <div className="row" style={{ flexWrap: "wrap" }}>
          <b style={{ fontSize: 13 }}>Saved searches:</b>
          {saved.length === 0 && <span className="muted">none yet</span>}
          {saved.map((s) => (
            <span key={s.id} className="chip brand" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <a href="#" onClick={(e) => { e.preventDefault(); applySearch(s); }}>
                {s.name}
              </a>
              <a href="#" onClick={(e) => { e.preventDefault(); removeSearch(s.id); }} title="Delete">
                ✕
              </a>
            </span>
          ))}
          <input
            placeholder="Name this search"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            style={{ width: 150, border: "1px solid var(--line)", borderRadius: 8, padding: "6px 9px", fontSize: 13 }}
          />
          <button className="btn secondary" onClick={saveSearch} disabled={!nameInput.trim()} style={{ padding: "7px 12px" }}>
            Save search
          </button>
        </div>

        <hr className="divider" />
        <div className="row">
          <input
            placeholder="Add any job by link (e.g. a PNet or CareerJunction posting)…"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            style={{ flex: 1, border: "1px solid var(--line)", borderRadius: 8, padding: "9px 11px" }}
          />
          <button className="btn secondary" onClick={addUrl} disabled={busy === "url" || !urlInput.trim()}>
            {busy === "url" ? "Reading…" : "Add by link"}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}

      {selected && (
        <div className="card" style={{ marginBottom: 16, borderLeft: "4px solid var(--brand)" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <h3 style={{ margin: 0 }}>
              {selected.title} {selected.company ? `@ ${selected.company}` : ""}
            </h3>
            <button className="btn secondary" onClick={() => setSelected(null)} style={{ padding: "6px 12px" }}>
              Close
            </button>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <span className={`chip ${selected.open_to_sa === "yes" ? "" : selected.open_to_sa === "no" ? "missing" : "neutral"}`}>
              SA: {selected.open_to_sa}
            </span>
            {selected.payment_signals.map((p) => (
              <span key={p} className="chip brand">
                {p}
              </span>
            ))}
            {selected.remote_type !== "unknown" && <span className="chip">{selected.remote_type}</span>}
            <span className="chip neutral">{ageLabel(selected.posted_at)}</span>
            {selected.salary_text && <span className="chip">{selected.salary_text}</span>}
          </div>
          {selected.match && (
            <div style={{ marginTop: 10 }}>
              <b style={{ fontSize: 13 }}>
                Match {Math.round(selected.match.score)}% — skills {Math.round(selected.match.components.skills)}% ·
                experience {Math.round(selected.match.components.experience)}% · keywords{" "}
                {Math.round(selected.match.components.keywords)}% · feasibility{" "}
                {Math.round(selected.match.components.feasibility)}% · freshness{" "}
                {Math.round(selected.match.components.freshness)}%
              </b>
              {selected.match.skill_hits.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  {selected.match.skill_hits.map((s) => (
                    <span key={s} className="chip">
                      {s}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
          {selected.description && (
            <pre className="script" style={{ maxHeight: 300, overflowY: "auto", marginTop: 12 }}>
              {selected.description}
            </pre>
          )}
          <div className="row" style={{ marginTop: 12 }}>
            <button className="btn" onClick={() => createPackage(selected)} disabled={busy === "package"}>
              {busy === "package" ? "Building package…" : "Create application package"}
            </button>
            {selected.url && (
              <a className="btn secondary" href={selected.url} target="_blank" rel="noreferrer">
                Open source listing
              </a>
            )}
          </div>
          <p className="muted" style={{ marginTop: 8 }}>
            Creating a package picks your best CV version, tailors it to this job, and writes a cover
            letter. Nothing is submitted — you review and approve in the Applications page.
          </p>
        </div>
      )}

      <div className="stack">
        <p className="muted" style={{ margin: 0 }}>
          {jobs.length} job{jobs.length === 1 ? "" : "s"} shown
        </p>
        {jobs.map((j) => (
          <div className="item" key={j.id} onClick={() => openJob(j)} style={{ cursor: "pointer" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h4 style={{ margin: 0 }}>
                {j.title} {j.company ? `@ ${j.company}` : ""}
              </h4>
              {j.match && (
                <span className="chip brand" title="Match score">
                  {Math.round(j.match.score)}%
                </span>
              )}
            </div>
            <p>
              <span className={`chip ${j.open_to_sa === "yes" ? "" : j.open_to_sa === "no" ? "missing" : "neutral"}`}>
                SA {j.open_to_sa}
              </span>{" "}
              <span className="muted">
                [{SOURCE_LABEL[j.source] ?? j.source}] {ageLabel(j.posted_at)}
                {j.payment_signals.length > 0 && ` · pays via ${j.payment_signals.join("/")}`}
              </span>
            </p>
          </div>
        ))}
        {jobs.length === 0 && <div className="empty">No jobs match. Try widening the filters or refresh.</div>}
      </div>
    </div>
  );
}
