// Lightweight API client for the Speeky Onboarding backend.
// Handles bearer-token storage and one automatic access-token refresh on 401.

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const ACCESS_KEY = "speeky_access";
const REFRESH_KEY = "speeky_refresh";

export type ApiError = {
  status: number;
  code?: string;
  message: string;
  detail?: any;
};

export function getAccess(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefresh(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh?: string) {
  localStorage.setItem(ACCESS_KEY, access);
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

function normalizeError(status: number, body: any): ApiError {
  const detail = body?.detail;
  if (detail && typeof detail === "object") {
    return {
      status,
      code: detail.code,
      message: detail.message || detail.msg || "Request failed",
      detail,
    };
  }
  if (typeof detail === "string") {
    return { status, message: detail };
  }
  return { status, message: body?.message || `Request failed (${status})` };
}

async function rawFetch(path: string, options: RequestInit, withAuth: boolean): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (withAuth) {
    const token = getAccess();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefresh();
  if (!refresh) return false;
  const resp = await rawFetch(
    "/auth/refresh",
    { method: "POST", body: JSON.stringify({ refresh_token: refresh }) },
    false,
  );
  if (!resp.ok) return false;
  const data = await resp.json();
  setTokens(data.access_token);
  return true;
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
  opts: { auth?: boolean } = {},
): Promise<T> {
  const withAuth = opts.auth ?? true;
  let resp = await rawFetch(path, options, withAuth);

  if (resp.status === 401 && withAuth && getRefresh()) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      resp = await rawFetch(path, options, withAuth);
    }
  }

  const text = await resp.text();
  const body = text ? JSON.parse(text) : null;

  if (!resp.ok) {
    throw normalizeError(resp.status, body);
  }
  return body as T;
}

// --- Typed helpers ---------------------------------------------------------

export type User = {
  id: string;
  email: string;
  username: string | null;
  display_name: string | null;
  photo_url: string | null;
  preferred_language: string;
  learning_goal: string;
  auth_provider: string;
  is_verified: boolean;
  uses_private_relay: boolean;
  is_pending_deletion: boolean;
  score: number;
  skill_level: string;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
};

export const api = {
  register: (body: any) => apiFetch("/auth/register", { method: "POST", body: JSON.stringify(body) }, { auth: false }),
  verifyEmail: (token: string) =>
    apiFetch("/auth/verify-email", { method: "POST", body: JSON.stringify({ token }) }, { auth: false }),
  resendVerification: (email: string) =>
    apiFetch("/auth/resend-verification", { method: "POST", body: JSON.stringify({ email }) }, { auth: false }),
  login: (email: string, password: string) =>
    apiFetch<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, { auth: false }),
  appleSso: (body: any) =>
    apiFetch<TokenResponse>("/auth/sso/apple", { method: "POST", body: JSON.stringify(body) }, { auth: false }),
  googleSso: (body: any) =>
    apiFetch<TokenResponse>("/auth/sso/google", { method: "POST", body: JSON.stringify(body) }, { auth: false }),
  forgotPassword: (email: string) =>
    apiFetch("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) }, { auth: false }),
  resetPassword: (token: string, new_password: string) =>
    apiFetch("/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password }) }, { auth: false }),

  me: () => apiFetch<User>("/profile"),
  updateProfile: (body: any) => apiFetch<User>("/profile", { method: "PATCH", body: JSON.stringify(body) }),
  updateGoal: (learning_goal: string) =>
    apiFetch<User>("/profile/goal", { method: "PUT", body: JSON.stringify({ learning_goal }) }),
  goals: () => apiFetch<{ goals: { key: string; label: string }[] }>("/profile/goals", {}, { auth: false }),

  sessions: () => apiFetch<any[]>("/sessions"),
  terminateSession: (id: string) => apiFetch(`/sessions/${id}`, { method: "DELETE" }),
  logoutAll: () => apiFetch("/sessions/logout-all?keep_current=true", { method: "POST" }),

  consents: () => apiFetch<any[]>("/privacy/consents"),
  updateConsent: (consent_type: string, granted: boolean) =>
    apiFetch("/privacy/consents", { method: "PUT", body: JSON.stringify({ consent_type, granted }) }),
  consentHistory: () => apiFetch<any[]>("/privacy/consents/history"),

  deletionStatus: () => apiFetch<any>("/account/deletion-status"),
  requestDeletion: (password?: string) =>
    apiFetch("/account/delete", { method: "POST", body: JSON.stringify({ password, confirm: true }) }),
  cancelDeletion: () => apiFetch("/account/delete/cancel", { method: "POST" }),

  logout: (refresh_token: string) =>
    apiFetch("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token }) }, { auth: false }),
};
