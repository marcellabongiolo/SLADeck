"use client";

import { useEffect, useState } from "react";
import { me, User } from "../../lib/api";
import { clearSession, getAccessToken } from "../../lib/session";

export default function DashboardPage() {
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      window.location.href = "/login";
      return;
    }

    me(token)
      .then(setUser)
      .catch(() => {
        clearSession();
        window.location.href = "/login";
      });
  }, []);

  if (error) {
    return <main className="auth-shell"><p className="error">{error}</p></main>;
  }

  return (
    <main className="dashboard-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">SLADeck workspace</p>
          <h1>Operational overview</h1>
        </div>
        <button
          className="secondary"
          onClick={() => {
            clearSession();
            window.location.href = "/login";
          }}
        >
          Sign out
        </button>
      </header>
      <section className="dashboard-card">
        {user ? (
          <>
            <p className="muted">Signed in as</p>
            <h2>{user.full_name}</h2>
            <p className="muted">{user.email}</p>
            <p className="status">Authenticated successfully.</p>
          </>
        ) : (
          <p className="muted">Loading workspace...</p>
        )}
      </section>
    </main>
  );
}
