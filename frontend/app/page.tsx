import Link from "next/link";

const foundations = [
  "Multi-tenant organizations",
  "Role-based permissions",
  "Request ownership and priorities",
  "SLA deadlines and escalations",
];

export default function HomePage() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">SLADeck · Operations workspace</p>
        <h1>Keep operational requests owned, visible, and on time.</h1>
        <p className="lede">
          Manage requests, responsibilities, priorities, and service-level
          deadlines from one team workspace.
        </p>
        <div className="actions">
          <Link className="button" href="/login">Sign in</Link>
          <Link className="button secondary" href="/register">Create account</Link>
        </div>
      </section>
      <section className="panel">
        <h2>Product foundation</h2>
        <ul>
          {foundations.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </section>
    </main>
  );
}
