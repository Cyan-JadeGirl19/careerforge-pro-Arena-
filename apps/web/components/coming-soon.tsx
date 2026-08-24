interface ComingSoonProps {
  title: string;
  icon: string;
  phase: string;
  points: string[];
}

export default function ComingSoon({ title, icon, phase, points }: ComingSoonProps) {
  return (
    <div>
      <div className="eyebrow">Module</div>
      <h1 style={{ fontSize: 24, margin: "6px 0 4px" }}>
        <span aria-hidden>{icon}</span> {title}
      </h1>
      <div className="card" style={{ marginTop: 16 }}>
        <span className="chip brand">Building next — {phase}</span>
        <p className="muted" style={{ marginTop: 10 }}>
          This module keeps its own dedicated space (no features are lost or merged elsewhere). The
          core CV → tailored application → video response flow is live while this is built.
        </p>
        <b style={{ fontSize: 14 }}>What it will include</b>
        <ul style={{ color: "var(--muted)", fontSize: 14, paddingLeft: 20, lineHeight: 1.8 }}>
          {points.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
