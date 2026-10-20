"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

type AuthFormProps = { mode: "login" | "signup" };

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const signup = mode === "signup";

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage(null);
    setPending(true);
    const data = new FormData(event.currentTarget);
    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: data.get("email"), password: data.get("password") }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        setMessage(typeof body?.detail === "string" ? body.detail : "We could not complete that request. Check your details and try again.");
        return;
      }
      router.push("/home");
      router.refresh();
    } catch {
      setMessage("PathAid cannot reach the service right now. Please try again shortly.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="auth-page">
      <section className="auth-panel" aria-labelledby="auth-title">
        <Link className="brand" href="/" aria-label="PathAid home"><span className="brand-mark" aria-hidden="true">◒</span><span>PathAid</span></Link>
        <div className="auth-heading">
          <p className="eyebrow">{signup ? "Create your private profile" : "Welcome back"}</p>
          <h1 id="auth-title">{signup ? "Start finding support" : "Log in to PathAid"}</h1>
          <p>{signup ? "Your profile helps compare reviewed requirements without predicting awards." : "Return to your profile and current recommendations."}</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="email">Email address</label>
          <input id="email" name="email" type="email" autoComplete="email" required maxLength={254} />
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" autoComplete={signup ? "new-password" : "current-password"} required minLength={12} maxLength={256} aria-describedby={signup ? "password-help" : undefined} />
          {signup && <p className="field-help" id="password-help">Use at least 12 characters. PathAid stores a secure password hash.</p>}
          {message && <div className="form-error" role="alert">{message}</div>}
          <button className="button button-primary auth-submit" disabled={pending} type="submit">{pending ? "Please wait…" : signup ? "Create account" : "Log in"}</button>
        </form>
        <p className="auth-switch">{signup ? "Already have an account?" : "New to PathAid?"} <Link href={signup ? "/login" : "/signup"}>{signup ? "Log in" : "Create an account"}</Link></p>
      </section>
      <aside className="auth-assurance" aria-label="PathAid privacy approach">
        <div><p className="eyebrow">Clear by design</p><h2>Your answers support matching. They do not guarantee an award.</h2></div>
        <ul><li>Eligibility stays rule based</li><li>Sensitive questions are optional</li><li>You can edit or delete your account</li></ul>
      </aside>
    </div>
  );
}
