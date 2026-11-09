"use client";

import { FormEvent, useState } from "react";
import { login, me, register } from "../lib/api";
import { clearSession, saveSession } from "../lib/session";

export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const registering = mode === "register";
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const data = new FormData(event.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    const password = String(data.get("password") ?? "");
    const fullName = String(data.get("full_name") ?? "").trim();
    if (registering && fullName.length < 2) {
      setError("Enter a name with at least two characters.");
      return;
    }
    setPending(true);
    setError("");
    let accountCreated = false;
    try {
      if (registering) {
        await register({ email, password, full_name: fullName });
        accountCreated = true;
      }
      const tokens = await login(email, password);
      await me(tokens.access_token);
      saveSession(tokens.access_token, tokens.refresh_token);
      window.location.assign("/dashboard");
    } catch (cause) {
      clearSession();
      const message = cause instanceof Error ? cause.message : "Unable to sign in.";
      setError(accountCreated ? "Your account was created. Please sign in to continue. " + message : message);
      setPending(false);
    }
  }

  return (
    <main className="auth-shell">
      <a className="back" href="/">← SLADeck</a>
      <section className="auth-card">
        <p className="eyebrow">SLADeck workspace</p>
        <h1>{registering ? "Create your account" : "Welcome back"}</h1>
        <p className="muted">{registering ? "Start organizing your team's requests." : "Sign in to your workspace."}</p>
        <form onSubmit={submit} aria-busy={pending}>
          {registering && <label>Full name<input name="full_name" autoComplete="name" required minLength={2} maxLength={160} /></label>}
          <label>Email<input name="email" type="email" autoComplete="email" required /></label>
          <label>Password<input name="password" type="password" autoComplete={registering ? "new-password" : "current-password"} required minLength={registering ? 10 : 1} maxLength={128} /></label>
          {registering && <p className="muted">Use at least 10 characters.</p>}
          {error && <p className="error" role="alert">{error}</p>}
          <button type="submit" disabled={pending}>{pending ? "Please wait…" : registering ? "Create account" : "Sign in"}</button>
        </form>
        <p>{registering ? "Already have an account? " : "New to SLADeck? "}<a href={registering ? "/login" : "/register"}>{registering ? "Sign in" : "Create account"}</a></p>
      </section>
    </main>
  );
}
