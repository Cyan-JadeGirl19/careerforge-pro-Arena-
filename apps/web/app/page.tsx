"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "../lib/session";

export default function LandingPage() {
  const router = useRouter();
  const { session, loaded } = useSession();

  useEffect(() => {
    if (!loaded) return;
    router.replace(session ? "/dashboard" : "/onboarding");
  }, [loaded, session, router]);

  return (
    <main style={{ maxWidth: 640, margin: "0 auto", padding: "80px 20px", textAlign: "center" }}>
      <div className="eyebrow">Remote-SA career accelerator</div>
      <h1 style={{ fontSize: 34 }}>
        CareerForge <span style={{ color: "var(--brand)" }}>Pro</span>
      </h1>
      <p className="lede" style={{ margin: "12px auto 0" }}>
        CV-first career acceleration for South Africans pursuing remote work globally. Upload your
        CV; the program prepares the rest. You approve anything sensitive.
      </p>
      <p className="muted">Loading your workspace…</p>
    </main>
  );
}
