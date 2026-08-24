import ComingSoon from "../../../components/coming-soon";

export default function Page() {
  return (
    <ComingSoon
      title="Job Finder"
      icon="🔍"
      phase="Phase 2"
      points={["Permitted sources: Indeed, CareerJunction, PNet, LinkedIn public jobs, remote boards","SA eligibility, timezone (UTC+2), payment (Deel/Wise) and work-authorisation filters","Match scores with transparent weighting","Saved searches and source citations"]}
    />
  );
}
