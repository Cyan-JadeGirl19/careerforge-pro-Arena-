/**
 * TypeScript API contract — mirrors the FastAPI v1 schemas
 * (canonical: apps/api/app/schemas.py, exported as docs/openapi/v1.json).
 */

export type ConsentItem =
  | "profile_processing"
  | "job_matching"
  | "recruiter_contact"
  | "outreach_sending"
  | "reference_sharing"
  | "media_use"
  | "video_recording";

export interface ProfileCreate {
  first_name?: string | null;
  last_name?: string | null;
  timezone?: string;
  work_authority?: string;
  summary?: string | null;
}

export interface ProfileUpdate {
  first_name?: string | null;
  last_name?: string | null;
  timezone?: string | null;
  work_authority?: string | null;
  summary?: string | null;
}

export interface ProfileOut {
  id: string;
  first_name: string | null;
  last_name: string | null;
  timezone: string;
  work_authority: string;
  summary: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ConsentGrant {
  item: ConsentItem;
  granted?: boolean;
  notes?: string | null;
}

export interface ConsentOut {
  id: string;
  item: ConsentItem;
  granted: boolean;
  notes: string | null;
  granted_at: string;
  revoked_at: string | null;
  created_at: string;
}

export interface CvCreate {
  title?: string;
  text: string;
  source_type?: "paste" | "upload";
}

export interface CvOut {
  id: string;
  profile_id: string;
  version: number;
  title: string;
  text: string;
  source_type: string;
  created_at: string;
}

export interface CheckResult {
  check: string;
  passed: boolean;
  detail: string;
}

export interface KeywordStatus {
  keyword: string;
  present: boolean;
}

export interface CvAnalysisOut {
  id: string;
  cv_id: string;
  checks: CheckResult[];
  keywords: KeywordStatus[];
  gaps: string[];
  created_at: string;
  note: string;
}

export interface HealthOut {
  status: string;
  version: string;
  environment: string;
  database: string;
}

// ---- studio: parsed CV, versions, JDs, tailoring, applications, video ----

export interface ParsedExperience {
  title: string;
  company: string;
  dates: string;
  bullets: string[];
}

export interface ParsedEducation {
  degree: string;
  institution: string;
  year: string;
}

export interface ParsedCv {
  name: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
  summary: string;
  experience: ParsedExperience[];
  education: ParsedEducation[];
  skills: string[];
  certifications: string[];
  projects: string[];
  languages: string[];
  other_sections: Record<string, string[]>;
  extraction_notes: string[];
}

export interface CvContent {
  name: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
  headline: string;
  summary: string;
  skills: string[];
  experience: ParsedExperience[];
  education: ParsedEducation[];
  certifications: string[];
  projects: string[];
  languages: string[];
  layout: string;
  role_focus: string | null;
  source_profile_version: string | null;
  job_description_version: string | null;
  generation_timestamp: string;
}

export interface CvVersion {
  id: string;
  profile_id: string;
  base_cv_id: string;
  kind: "master_ats" | "master_modern" | "master_role" | "custom";
  title: string;
  role_focus: string | null;
  content: CvContent;
  created_at: string;
}

export interface JobDescription {
  id: string;
  profile_id: string;
  title: string;
  company: string | null;
  source_url: string | null;
  text: string;
  created_at: string;
}

export interface TailoredKeyword {
  keyword: string;
  in_candidate_profile: boolean;
}

export interface TailoredReport {
  jd_title: string;
  keywords: TailoredKeyword[];
  surfaced_keywords: string[];
  gaps: string[];
  needs_confirmation: string[];
  coverage: number;
  note: string;
}

export interface TailoredCv {
  id: string;
  profile_id: string;
  version_id: string;
  jd_id: string;
  title: string;
  content: CvContent;
  report: TailoredReport;
  created_at: string;
}

export interface RoleRecommendation {
  role: string;
  match_pct: number;
  matched: string[];
  missing: string[];
  reason: string;
}

export interface CoverLetter {
  id: string;
  application_id: string;
  text: string;
  tone: string;
  quality_issues: string[];
  created_at: string;
}

export interface VideoResponse {
  id: string;
  application_id: string;
  question: string;
  key_points: string | null;
  exclusions: string | null;
  tone: string;
  target_seconds: number;
  mode: "recording" | "enhance" | "ai_assisted";
  script_text: string;
  script_version: number;
  media_status: "none" | "uploaded" | "ready";
  ai_disclosed: boolean;
  delete_media_after_export: boolean;
  created_at: string;
  updated_at: string;
}

export type ApplicationStatus =
  | "saved" | "ready" | "applied" | "phone_screen"
  | "interview" | "offer" | "rejected" | "archived";

export interface Application {
  id: string;
  profile_id: string;
  jd_title: string;
  jd_company: string | null;
  cv_version_id: string | null;
  tailored_cv_id: string | null;
  status: ApplicationStatus;
  notes: string | null;
  letter: CoverLetter | null;
  videos: VideoResponse[];
  created_at: string;
  updated_at: string;
}

export interface AutoPipelineResult {
  applications: Application[];
  skipped: Array<{ jd_id: string; reason: unknown }>;
}

// ---- jobs ----

export interface JobMatch {
  score: number;
  components: Record<string, number>;
  skill_hits: string[];
  keyword_hits: string[];
  weights: Record<string, number>;
}

export interface Job {
  id: string;
  source: string;
  title: string;
  company: string | null;
  location: string | null;
  url: string | null;
  tags: string;
  salary_text: string | null;
  posted_at: string | null;
  fetched_at: string;
  open_to_sa: "yes" | "no" | "unknown";
  sa_signals: string[];
  global_signals: string[];
  exclude_signals: string[];
  payment_signals: string[];
  timezone_signals: string[];
  remote_type: string;
  match: JobMatch | null;
  description?: string;
}

export interface SourceStatus {
  source: string;
  enabled: boolean;
  status?: string | null;
  fetched?: number | null;
  added?: number | null;
  error?: string | null;
  last_sync?: string | null;
}

export interface SavedSearch {
  id: string;
  name: string;
  filters: Record<string, unknown>;
  created_at: string;
}

// ---- recruiters ----

export interface RecruiterContact {
  id: string;
  profile_id: string;
  source: string;
  source_url: string | null;
  name: string | null;
  title: string | null;
  company: string | null;
  profile_url: string | null;
  email: string | null;
  email_status: "none" | "published" | "pattern_suggested";
  suggested_emails: string[];
  job_title: string | null;
  notes: string | null;
  verified: boolean;
  verified_at: string | null;
  suppressed: boolean;
  created_at: string;
}

export interface OutreachDraft {
  draft: string;
  issues: string[];
}
