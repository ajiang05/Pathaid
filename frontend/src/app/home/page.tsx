"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type SessionState = "loading" | "authenticated" | "anonymous" | "unavailable";

export default function HomePage() {
  const [state, setState] = useState<SessionState>("loading");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/auth/session", { credentials: "same-origin", signal: controller.signal })
      .then((response) => setState(response.ok ? "authenticated" : response.status === 401 ? "anonymous" : "unavailable"))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("unavailable");
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="home-page">
      <header className="site-header">
        <Link className="brand" href="/"><span className="brand-mark" aria-hidden="true">◒</span><span>PathAid</span></Link>
      </header>
      <section className="home-welcome" aria-live="polite">
        {state === "loading" && <><p className="eyebrow">Loading your account</p><h1>Preparing your PathAid home…</h1></>}
        {state === "authenticated" && <><p className="eyebrow">Account ready</p><h1>Welcome to PathAid.</h1><p>Your profile and personalized recommendation screens are the next implementation slice.</p></>}
        {state === "anonymous" && <><p className="eyebrow">Session expired</p><h1>Log in to continue.</h1><p>Your account is still safe. Start a new session to reach your profile.</p><Link className="button button-primary" href="/login">Log in</Link></>}
        {state === "unavailable" && <><p className="eyebrow">Service unavailable</p><h1>PathAid cannot load your account.</h1><p>Check that the backend is running, then refresh this page.</p></>}
      </section>
    </main>
  );
}
