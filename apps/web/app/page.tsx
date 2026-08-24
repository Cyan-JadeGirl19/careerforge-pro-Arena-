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
    <main className="centered" style={{ textAlign: "center" }}>
      <div className="hero-logo" />
      <div className="eyebrow">Remote-SA career accelerator</div>
      <h1 style={{ fontSize: 34, marginTop: 10 }}>
        CareerForge{" "}
        <span style={{ background: "linear-gradient(90deg, var(--brand-2), var(--brand-deep))", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
          Pro
        </span>
      </h1>
      <p className="lede" style={{ margin: "14px auto 0" }}>
        CV-first career acceleration for South Africans pursuing remote work globally. Upload your
        CV; the program prepares the rest. You approve anything sensitive.
      </p>
      <p className="muted" style={{ marginTop: 26 }}>
        <span className={loaded && session ? "dot" : "dot off"} style={{ marginRight: 8 }} />
        Loading your workspace…
      </p>
    </main>
  );
}
