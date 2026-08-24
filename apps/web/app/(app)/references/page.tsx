import ComingSoon from "../../../components/coming-soon";

export default function Page() {
  return (
    <ComingSoon
      title="References and Profile"
      icon="🤝"
      phase="Phase 3"
      points={["Private reference manager: contacts, letters, permissions","Hidden from CVs by default - attached only when requested","Permission confirmation before any sharing","LinkedIn consistency checks and remote-readiness profile"]}
    />
  );
}
