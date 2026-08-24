"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import type { PortfolioItem } from "../../../../../packages/contracts/types";

const TYPE_LABEL: Record<string, string> = {
  project: "Project",
  github_repo: "GitHub repo",
  writing_sample: "Writing sample",
  design: "Design",
  link: "Link",
};

export default function PortfolioPage() {
  const { session } = useSession();
  const pid = session?.profileId ?? "";

  const [items, setItems] = useState<PortfolioItem[]>([]);
  const [form, setForm] = useState({
    title: "",
    type: "project",
    description: "",
    url: "",
    tech_tags: "",
  });
  const [githubRepo, setGithubRepo] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!pid) return;
    try {
      setItems(await api.listPortfolio(pid));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load the portfolio.");
    }
  }, [pid]);

  useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    if (!pid || !form.title.trim()) return;
    setBusy("add");
    setError(null);
    setInfo(null);
    try {
      await api.addPortfolioItem(pid, {
        title: form.title.trim(),
        type: form.type,
        description: form.description.trim() || null,
        url: form.url.trim() || null,
        tech_tags: form.tech_tags.trim(),
        approved: false,
      });
      setForm({ title: "", type: "project", description: "", url: "", tech_tags: "" });
      await load();
      setInfo("Added as UNAPPROVED - it stays private to you until you approve it.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not add the item.");
    } finally {
      setBusy(null);
    }
  };

  const pullGithub = async () => {
    if (!pid || !githubRepo.trim()) return;
    setBusy("gh");
    setError(null);
    setInfo(null);
    try {
      const item = await api.pullGithubRepo(pid, githubRepo.trim());
      setGithubRepo("");
      await load();
      setInfo(
        `Pulled "${item.title}"${item.stars ? ` (★${item.stars})` : ""} as an unapproved item - review it, then approve.`,
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not read that repo.");
    } finally {
      setBusy(null);
    }
  };

  const patch = async (id: string, body: Record<string, unknown>) => {
    try {
      await api.updatePortfolioItem(id, body);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update the item.");
    }
  };

  const remove = async (id: string, title: string) => {
    if (!window.confirm(`Delete "${title}" from your portfolio?`)) return;
    try {
      await api.deletePortfolioItem(id);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not delete the item.");
    }
  };

  return (
    <div>
      <div className="eyebrow">Portfolio Builder</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>Show your work, not just your CV</h1>
      <p className="muted" style={{ margin: "0 0 16px" }}>
        Projects, repos, writing samples and links. Everything is private until you <b>approve</b>{" "}
        it - only approved items appear on your public portfolio page.
      </p>

      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      {info && <div className="alert info">{info}</div>}

      <div className="grid2">
        <div className="card">
          <h3>Add an item</h3>
          <div className="grid2">
            <div className="field">
              <label>Title *</label>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            </div>
            <div className="field">
              <label>Type</label>
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                {Object.entries(TYPE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label>What it is / what you built</label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              style={{ minHeight: 80 }}
            />
          </div>
          <div className="grid2">
            <div className="field">
              <label>Link</label>
              <input
                value={form.url}
                onChange={(e) => setForm({ ...form, url: e.target.value })}
                placeholder="https://…"
              />
            </div>
            <div className="field">
              <label>Tech (comma-separated)</label>
              <input
                value={form.tech_tags}
                onChange={(e) => setForm({ ...form, tech_tags: e.target.value })}
                placeholder="React, Python"
              />
            </div>
          </div>
          <button className="btn" onClick={add} disabled={busy === "add" || !form.title.trim()}>
            {busy === "add" ? "Adding…" : "Add (stays private)"}
          </button>
        </div>

        <div className="card">
          <h3>Pull from GitHub</h3>
          <p className="muted">
            One public repo at a time. Pulls the description, language and README - saved as an
            unapproved item for you to review.
          </p>
          <div className="field">
            <label>Repository (owner/repo)</label>
            <input
              value={githubRepo}
              onChange={(e) => setGithubRepo(e.target.value)}
              placeholder="octocat/hello-world"
            />
          </div>
          <button className="btn secondary" onClick={pullGithub} disabled={busy === "gh" || !githubRepo.trim()}>
            {busy === "gh" ? "Pulling…" : "Pull repo"}
          </button>
          <hr className="divider" />
          <h3>Public page</h3>
          <p className="muted">
            Only approved items are shown. Your page:{" "}
            <a href={api.portfolioPageUrl(pid)} target="_blank" rel="noreferrer">
              open →
            </a>
          </p>
          <p className="muted" style={{ fontSize: 12 }}>
            (Free subdomain hosting lands with the deployment phase.)
          </p>
        </div>
      </div>

      <hr className="divider" />

      <div className="stack">
        <p className="muted" style={{ margin: 0 }}>
          {items.length} item{items.length === 1 ? "" : "s"}
        </p>
        {items.map((it) => (
          <div className="item" key={it.id}>
            <div className="row" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
              <h4 style={{ margin: 0 }}>
                {it.title}
                {it.featured ? " ★" : ""}
              </h4>
              <div className="row">
                <span className="chip neutral">{TYPE_LABEL[it.type] ?? it.type}</span>
                {it.approved ? (
                  <span className="chip">✓ approved (public)</span>
                ) : (
                  <span className="chip missing">private (unapproved)</span>
                )}
              </div>
            </div>
            {it.description && <p>{it.description}</p>}
            <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
              {it.url && (
                <a href={it.url} target="_blank" rel="noreferrer" className="chip brand">
                  open →
                </a>
              )}
              {it.tech_tags && (
                <span className="muted" style={{ fontSize: 12 }}>
                  {it.tech_tags}
                </span>
              )}
            </div>
            <div className="row" style={{ marginTop: 10, flexWrap: "wrap", gap: 6 }}>
              <button
                className="btn secondary"
                style={{ padding: "6px 10px", fontSize: 12 }}
                onClick={() => patch(it.id, { approved: !it.approved })}
              >
                {it.approved ? "un-approve (hide)" : "approve (make public)"}
              </button>
              <button
                className="btn secondary"
                style={{ padding: "6px 10px", fontSize: 12 }}
                onClick={() => patch(it.id, { featured: !it.featured })}
              >
                {it.featured ? "un-feature" : "feature"}
              </button>
              <button
                className="btn secondary"
                style={{ padding: "6px 10px", fontSize: 12, color: "var(--red)" }}
                onClick={() => remove(it.id, it.title)}
              >
                delete
              </button>
            </div>
          </div>
        ))}
        {items.length === 0 && (
          <div className="empty">No items yet. Add a project or pull a GitHub repo.</div>
        )}
      </div>
    </div>
  );
}
