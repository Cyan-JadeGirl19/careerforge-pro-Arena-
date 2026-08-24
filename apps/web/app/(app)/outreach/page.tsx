import ComingSoon from "../../../components/coming-soon";

export default function Page() {
  return (
    <ComingSoon
      title="Gmail Outreach"
      icon="📧"
      phase="Phase 3"
      points={["Gmail OAuth with least-privilege scopes","Drafts first - nothing sends without your approval","Throttling, unsubscribe handling and suppression lists","3-touch follow-up sequences with tracking"]}
    />
  );
}
