/**
 * Browser API client.
 *
 * Always calls same-origin `/api/v1/*`; the Next.js server proxies those
 * requests to the backend (see next.config.mjs rewrites). No hardcoded
 * browser localhost URLs.
 */
import type {
  ConsentGrant,
  ConsentOut,
  CvAnalysisOut,
  CvCreate,
  CvOut,
  HealthOut,
  ProfileCreate,
  ProfileOut,
  ProfileUpdate,
} from "../../../packages/contracts/types";

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      // non-JSON error body
    }
    throw new Error(`API ${res.status}: ${JSON.stringify(detail)}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => request<HealthOut>("/health"),

  createProfile: (body: ProfileCreate) =>
    request<ProfileOut>("/profiles", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getProfile: (id: string) => request<ProfileOut>(`/profiles/${id}`),
  updateProfile: (id: string, body: ProfileUpdate) =>
    request<ProfileOut>(`/profiles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteProfile: (id: string) =>
    request<void>(`/profiles/${id}`, { method: "DELETE" }),

  grantConsent: (profileId: string, body: ConsentGrant) =>
    request<ConsentOut>(`/profiles/${profileId}/consents`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listConsents: (profileId: string) =>
    request<ConsentOut[]>(`/profiles/${profileId}/consents`),
  revokeConsent: (profileId: string, item: ConsentGrant["item"]) =>
    request<void>(`/profiles/${profileId}/consents/${item}`, {
      method: "DELETE",
    }),

  createCv: (profileId: string, body: CvCreate) =>
    request<CvOut>(`/profiles/${profileId}/cvs`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listCvs: (profileId: string) => request<CvOut[]>(`/profiles/${profileId}/cvs`),
  getCv: (id: string) => request<CvOut>(`/cvs/${id}`),
  analyzeCv: (id: string) =>
    request<CvAnalysisOut>(`/cvs/${id}/analyze`, { method: "POST" }),
  latestAnalysis: (id: string) =>
    request<CvAnalysisOut>(`/cvs/${id}/analysis/latest`),
};
