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
