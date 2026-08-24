"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Local-first session. Accounts arrive later (Phase 1 production), but the
 * app needs a current candidate profile to work with. The profile id is
 * stored in localStorage; all data lives server-side.
 */
export interface Session {
  profileId: string;
  firstName: string;
}

const KEY = "cf_session_v1";

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw) as Session;
    return s && s.profileId ? s : null;
  } catch {
    return null;
  }
}

export function saveSession(s: Session) {
  window.localStorage.setItem(KEY, JSON.stringify(s));
}

export function clearSession() {
  window.localStorage.removeItem(KEY);
}

export function useSession() {
  const [session, setSessionState] = useState<Session | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setSessionState(getSession());
    setLoaded(true);
  }, []);

  const login = useCallback((s: Session) => {
    saveSession(s);
    setSessionState(s);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setSessionState(null);
  }, []);

  return { session, loaded, login, logout };
}
