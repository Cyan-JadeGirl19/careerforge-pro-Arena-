/**
 * Browser API client.
 *
 * Always calls same-origin `/api/v1/*`; the Next.js server proxies those
 * requests to the backend (see next.config.mjs rewrites). No hardcoded
 * browser localhost URLs.
 */
import type {
  Application,
  ApplicationStatus,
  AutoPipelineResult,
  ConsentGrant,
  ConsentOut,
  CoverLetter,
  CvAnalysisOut,
  CvCreate,
  CvOut,
  CvVersion,
  HealthOut,
  Job,
  JobDescription,
  OutreachDraft,
  ParsedCv,
  RecruiterContact,
  Reference,
  ReferenceDocument,
  SavedSearch,
  SourceStatus,
  ProfileCreate,
  ProfileOut,
  ProfileUpdate,
  RoleRecommendation,
  TailoredCv,
  VideoResponse,
} from "../../../packages/contracts/types";

const BASE = "/api/v1";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let code = "API_ERROR";
    let message = `API ${res.status}`;
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === "string") message = detail;
      else if (detail && typeof detail === "object") {
        code = detail.code || code;
        message = detail.message || message;
      }
    } catch {
      // non-JSON error body
    }
    throw new ApiError(res.status, code, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function exportUrl(kind: "versions" | "tailored" | "cvs", id: string, format: string): string {
  const base =
    kind === "versions"
      ? `/api/v1/cv-versions/${id}/export`
      : kind === "tailored"
        ? `/api/v1/tailored/${id}/export`
        : `/api/v1/cvs/${id}/export`;
  return `${base}?format=${format}`;
}

export const api = {
  health: () => request<HealthOut>("/health"),

  // profiles & consents
  createProfile: (body: ProfileCreate) =>
    request<ProfileOut>("/profiles", { method: "POST", body: JSON.stringify(body) }),
  getProfile: (id: string) => request<ProfileOut>(`/profiles/${id}`),
  updateProfile: (id: string, body: ProfileUpdate) =>
    request<ProfileOut>(`/profiles/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteProfile: (id: string) => request<void>(`/profiles/${id}`, { method: "DELETE" }),

  grantConsent: (profileId: string, body: ConsentGrant) =>
    request<ConsentOut>(`/profiles/${profileId}/consents`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listConsents: (profileId: string) => request<ConsentOut[]>(`/profiles/${profileId}/consents`),
  revokeConsent: (profileId: string, item: ConsentGrant["item"]) =>
    request<void>(`/profiles/${profileId}/consents/${item}`, { method: "DELETE" }),

  // CVs
  createCv: (profileId: string, body: CvCreate) =>
    request<CvOut>(`/profiles/${profileId}/cvs`, { method: "POST", body: JSON.stringify(body) }),
  listCvs: (profileId: string) => request<CvOut[]>(`/profiles/${profileId}/cvs`),
  getCv: (id: string) => request<CvOut>(`/cvs/${id}`),
  analyzeCv: (id: string) => request<CvAnalysisOut>(`/cvs/${id}/analyze`, { method: "POST" }),
  latestAnalysis: (id: string) => request<CvAnalysisOut>(`/cvs/${id}/analysis/latest`),
  getParsedCv: (id: string) => request<ParsedCv>(`/cvs/${id}/parsed`),
  uploadCv: async (profileId: string, file: File): Promise<{ cv: CvOut; parsed: ParsedCv }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/profiles/${profileId}/cvs/upload`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let message = `Upload failed (${res.status})`;
      try {
        const body = await res.json();
        if (body?.detail?.message) message = body.detail.message;
      } catch {
        // ignore
      }
      throw new ApiError(res.status, "UPLOAD_FAILED", message);
    }
    const body = await res.json();
    const { parsed, ...cv } = body;
    return { cv, parsed };
  },

  // CV versions
  listVersions: (cvId: string) => request<CvVersion[]>(`/cvs/${cvId}/versions`),
  buildMasters: (cvId: string, roleFocus?: string) =>
    request<CvVersion[]>(`/cvs/${cvId}/versions/build-masters`, {
      method: "POST",
      body: JSON.stringify({ role_focus: roleFocus || null }),
    }),
  createVersion: (
    cvId: string,
    body: { kind: string; role_focus?: string | null; emphasize?: string[]; exclude?: string[] },
  ) =>
    request<CvVersion>(`/cvs/${cvId}/versions`, { method: "POST", body: JSON.stringify(body) }),
  getVersion: (id: string) => request<CvVersion>(`/cv-versions/${id}`),

  // jobs, tailoring, applications
  createJobDescription: (
    profileId: string,
    body: { title: string; company?: string | null; source_url?: string | null; text: string },
  ) =>
    request<JobDescription>(`/profiles/${profileId}/job-descriptions`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  tailorVersion: (versionId: string, jdId: string) =>
    request<{ tailored_cv_id: string; report: TailoredCv["report"] }>(
      `/cv-versions/${versionId}/tailor`,
      { method: "POST", body: JSON.stringify({ jd_id: jdId }) },
    ),
  getTailored: (id: string) => request<TailoredCv>(`/tailored/${id}`),

  recommendRoles: (profileId: string) =>
    request<RoleRecommendation[]>(`/profiles/${profileId}/roles/recommend`, {
      method: "POST",
      body: "{}",
    }),
  createApplication: (profileId: string, body: { jd_id: string; notes?: string }) =>
    request<Application>(`/profiles/${profileId}/applications`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listApplications: (profileId: string) =>
    request<Application[]>(`/profiles/${profileId}/applications`),
  getApplication: (id: string) => request<Application>(`/applications/${id}`),
  tailorApplication: (id: string) =>
    request<{ tailored_cv_id: string; report: TailoredCv["report"] }>(
      `/applications/${id}/tailor`,
      { method: "POST", body: "{}" },
    ),
  updateApplicationStatus: (id: string, status: ApplicationStatus, notes?: string) =>
    request<Application>(`/applications/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, notes }),
    }),

  // cover letters
  createLetter: (applicationId: string, tone?: string) =>
    request<CoverLetter>(`/applications/${applicationId}/cover-letter`, {
      method: "POST",
      body: JSON.stringify({ tone: tone || "direct" }),
    }),

  // voice / video
  createVideo: (
    applicationId: string,
    body: {
      question: string;
      key_points?: string[];
      exclusions?: string[];
      tone?: string;
      target_seconds?: number;
      mode?: string;
    },
  ) =>
    request<VideoResponse>(`/applications/${applicationId}/videos`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  regenerateVideo: (
    videoId: string,
    body: {
      question: string;
      key_points?: string[];
      exclusions?: string[];
      tone?: string;
      target_seconds?: number;
      mode?: string;
    },
  ) =>
    request<VideoResponse>(`/videos/${videoId}/regenerate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateVideoMedia: (videoId: string, media_status: "uploaded" | "ready") =>
    request<VideoResponse>(`/videos/${videoId}/media`, {
      method: "POST",
      body: JSON.stringify({ media_status }),
    }),

  // autonomous pipeline
  autoPipeline: (profileId: string, cvId: string, jdIds: string[]) =>
    request<AutoPipelineResult>(`/profiles/${profileId}/auto-pipeline`, {
      method: "POST",
      body: JSON.stringify({ cv_id: cvId, jd_ids: jdIds }),
    }),

  // jobs
  searchJobs: (
    params: {
      q?: string;
      source?: string;
      sa_only?: boolean;
      max_age_days?: number;
      sort?: string;
      profile_id?: string;
    } = {},
  ) => {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
    });
    const s = qs.toString();
    return request<Job[]>(`/jobs${s ? `?${s}` : ""}`);
  },
  syncJobs: () =>
    request<{ sources: SourceStatus[]; total_jobs: number }>("/jobs/sync", {
      method: "POST",
      body: "{}",
    }),
  jobHealth: () => request<SourceStatus[]>("/jobs/health"),
  getJob: (id: string, profileId?: string) =>
    request<Job>(`/jobs/${id}${profileId ? `?profile_id=${profileId}` : ""}`),
  jobToApplication: (jobId: string, profileId: string) =>
    request<{ application_id: string; existing: boolean }>(
      `/jobs/${jobId}/to-application?profile_id=${profileId}`,
      { method: "POST", body: "{}" },
    ),
  addJobUrl: (profileId: string, url: string) =>
    request<Job>(`/jobs/add-url?profile_id=${profileId}`, {
      method: "POST",
      body: JSON.stringify({ url }),
    }),
  listSavedSearches: (profileId: string) =>
    request<SavedSearch[]>(`/jobs/profiles/${profileId}/saved-searches`),
  saveSearch: (profileId: string, name: string, filters: Record<string, unknown>) =>
    request<SavedSearch>(`/jobs/profiles/${profileId}/saved-searches`, {
      method: "POST",
      body: JSON.stringify({ name, filters }),
    }),
  deleteSearch: (profileId: string, searchId: string) =>
    request<void>(`/jobs/profiles/${profileId}/saved-searches/${searchId}`, {
      method: "DELETE",
    }),

  // recruiters
  listRecruiters: (profileId: string, includeSuppressed = false) =>
    request<RecruiterContact[]>(
      `/profiles/${profileId}/recruiters${includeSuppressed ? "?include_suppressed=true" : ""}`,
    ),
  extractRecruiters: (
    profileId: string,
    body: { url: string; company?: string },
  ) =>
    request<RecruiterContact[]>(`/profiles/${profileId}/recruiters/extract`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  createRecruiter: (profileId: string, body: Record<string, unknown>) =>
    request<RecruiterContact>(`/profiles/${profileId}/recruiters`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateRecruiter: (contactId: string, body: Record<string, unknown>) =>
    request<RecruiterContact>(`/recruiters/${contactId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteRecruiter: (contactId: string) =>
    request<void>(`/recruiters/${contactId}`, { method: "DELETE" }),
  outreachDraft: (contactId: string, body: { job_title?: string; tone?: string }) =>
    request<OutreachDraft>(`/recruiters/${contactId}/outreach`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  // references
  listReferences: (profileId: string, includeSuppressed = false) =>
    request<Reference[]>(
      `/profiles/${profileId}/references${includeSuppressed ? "?include_suppressed=true" : ""}`,
    ),
  createReference: (profileId: string, body: Record<string, unknown>) =>
    request<Reference>(`/profiles/${profileId}/references`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateReference: (refId: string, body: Record<string, unknown>) =>
    request<Reference>(`/references/${refId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteReference: (refId: string) =>
    request<void>(`/references/${refId}`, { method: "DELETE" }),
  uploadReferenceDocument: async (refId: string, file: File): Promise<ReferenceDocument> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`/api/v1/references/${refId}/documents`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new ApiError(res.status, "UPLOAD_FAILED", "Upload failed");
    return res.json();
  },
  listReferenceDocuments: (refId: string) =>
    request<ReferenceDocument[]>(`/references/${refId}/documents`),
  deleteReferenceDocument: (docId: string) =>
    request<void>(`/documents/${docId}`, { method: "DELETE" }),
  parseReferenceList: async (profileId: string, file: File): Promise<Reference[]> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`/api/v1/profiles/${profileId}/references/parse-list`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) {
      let msg = "Could not read that file";
      try {
        const b = await res.json();
        if (b?.detail?.message) msg = b.detail.message;
      } catch {
        // ignore
      }
      throw new ApiError(res.status, "PARSE_FAILED", msg);
    }
    return res.json();
  },
  attachReferences: (
    appId: string,
    body: { references_requested: string; reference_ids: string[] },
  ) =>
    request<Application>(`/applications/${appId}/references`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
