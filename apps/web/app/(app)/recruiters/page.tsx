import ComingSoon from "../../../components/coming-soon";

export default function Page() {
  return (
    <ComingSoon
      title="Recruiter Finder"
      icon="👤"
      phase="Phase 2"
      points={["Publicly displayed job-poster and recruiter details only","Public profile URLs and published company recruiting contacts","Guessed email patterns clearly labelled unverified","Source and verification date for every contact; POPIA/GDPR records"]}
    />
  );
}
