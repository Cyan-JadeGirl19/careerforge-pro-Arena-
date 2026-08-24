"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { NAV } from "./nav";
import { useSession } from "../../lib/session";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { session, loaded } = useSession();
  const [health, setHealth] = useState<string | null>(null);

  useEffect(() => {
    if (loaded && !session) router.replace("/onboarding");
  }, [loaded, session, router]);

  useEffect(() => {
    let alive = true;
    fetch("/api/v1/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => alive && setHealth(d ? `API v${d.version}` : "API offline"))
      .catch(() => alive && setHealth("API offline"));
    return () => {
      alive = false;
    };
  }, []);

  if (!loaded) return null;

  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          CareerForge <span>Pro</span>
        </div>
        <nav className="nav">
          {NAV.map((group) => (
            <div key={group.section}>
              <small>{group.section}</small>
              {group.items.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={pathname?.startsWith(item.href) ? "active" : ""}
                >
                  <span aria-hidden>{item.icon}</span> {item.label}
                </Link>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidefoot">
          <div className="userrow">
            <div className="avatar" style={{ width: 32, height: 32, fontSize: 11 }}>
              {session ? session.firstName.slice(0, 2).toUpperCase() : "…"}
            </div>
            {session ? session.firstName : "…"}
          </div>
          <div>
            <span className={health && health.startsWith("API v") ? "dot" : "dot off"} style={{ marginRight: 8 }} />
            {health ?? "Connecting…"}
          </div>
        </div>
      </aside>
      <div className="content">
        <div className="topbar">
          <div />
          <a
            href="/settings"
            className="muted"
            style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 8 }}
          >
            <div className="avatar">{session ? session.firstName.slice(0, 2).toUpperCase() : "…"}</div>
          </a>
        </div>
        {children}
      </div>
    </div>
  );
}
