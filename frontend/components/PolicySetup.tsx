"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { createPolicy, SLAPolicy } from "../lib/api";

export default function PolicySetup({ token, organizationId, onCreated }: {
  token: string;
  organizationId: string;
  onCreated: (policy: SLAPolicy) => void;
}) {
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const data = new FormData(event.currentTarget);
    const name = String(data.get("name") ?? "").trim();
    const first = Number(data.get("first"));
    const resolution = Number(data.get("resolution"));
    if (name.length < 2 || !Number.isInteger(first) || !Number.isInteger(resolution) ||
        first < 1 || first > 43200 || resolution < first || resolution > 525600) {
      setError("Enter a policy name and valid deadlines; resolution must be at least the first response time.");
      return;
    }
    setPending(true);
    setError("");
    try {
      const policy = await createPolicy(token, organizationId, {
        name, first_response_minutes: first, resolution_minutes: resolution,
      });
      if (active.current) onCreated(policy);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to create SLA policy.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="dashboard-card policy-setup">
      <h2>Create your first SLA policy</h2>
      <p className="muted">A policy sets the deadlines for new requests. Owners, admins and managers can create policies.</p>
      <form onSubmit={submit} aria-busy={pending}>
        <label>Policy name<input name="name" required minLength={2} maxLength={120} defaultValue="Standard support" /></label>
        <label>First response (minutes)<input name="first" type="number" required min={1} max={43200} step={1} defaultValue={60} /></label>
        <label>Resolution (minutes)<input name="resolution" type="number" required min={1} max={525600} step={1} defaultValue={480} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={pending}>{pending ? "Saving…" : "Create SLA policy"}</button>
      </form>
    </section>
  );
}
