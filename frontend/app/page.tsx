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
        <p className="eyebrow">SLADeck · Portfolio MVP</p>
        <h1>Keep operational requests owned, visible, and on time.</h1>
        <p className="lede">
          SLADeck is a team workspace for managing requests, responsibilities,
          priorities, and service-level deadlines.
        </p>
        <div className="actions"><a className="button-link" href="/register">Create account</a><a className="back" href="/login">Sign in</a></div>
      </section>

      <section className="panel">
        <h2>Your operational workspace</h2>
        <ul>
          {foundations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
