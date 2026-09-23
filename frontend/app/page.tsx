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
        <p className="eyebrow">SLADeck · Early Development</p>
        <h1>Keep operational requests owned, visible, and on time.</h1>
        <p className="lede">
          SLADeck is a team workspace for managing requests, responsibilities,
          priorities, and service-level deadlines.
        </p>
        <div className="status">Foundation stack is running.</div>
      </section>

      <section className="panel">
        <h2>Planned product foundation</h2>
        <ul>
          {foundations.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
    </main>
  );
}
