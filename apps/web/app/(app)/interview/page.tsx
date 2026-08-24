import ComingSoon from "../../../components/coming-soon";

export default function Page() {
  return (
    <ComingSoon
      title="Interview Coach"
      icon="🎤"
      phase="Phase 4"
      points={["Role-specific mock interviews with STAR-mapped questions","Employment-gap and red-flag question preparation","South Africa-specific remote questions (timezone, connectivity, payments)","Feedback and improvement plans per session"]}
    />
  );
}
