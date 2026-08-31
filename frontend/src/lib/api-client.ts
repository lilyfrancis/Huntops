import { tokenStorage } from "./token-storage";
import type { ApiErrorBody } from "./types";

const API_BASE = ""; // same-origin in dev via the Vite proxy, and in prod behind one domain

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// Concurrent 401s share one refresh call instead of each firing their own.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = tokenStorage.getRefresh();
  if (!refreshToken) return null;

  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) return null;
        const body = (await res.json()) as { access_token: string };
        tokenStorage.setAccess(body.access_token);
        return body.access_token;
      })
      .catch(() => null)
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  isForm?: boolean;
  skipAuth?: boolean;
  skipRetry?: boolean;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, isForm, skipAuth, skipRetry, headers, ...rest } = options;

  const finalHeaders = new Headers(headers);
  if (!isForm && body !== undefined) {
    finalHeaders.set("Content-Type", "application/json");
  }
  if (!skipAuth) {
    const token = tokenStorage.getAccess();
    if (token) finalHeaders.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...rest,
    headers: finalHeaders,
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  });

  if (res.status === 401 && !skipAuth && !skipRetry) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      return request<T>(path, { ...options, skipRetry: true });
    }
    tokenStorage.clear();
    window.dispatchEvent(new CustomEvent("huntops:unauthorized"));
    throw new ApiError(401, "Session expired — please sign in again");
  }

  if (res.status === 204) return undefined as T;

  let json: unknown = null;
  try {
    json = await res.json();
  } catch {
    // no body — fine for some 2xx responses
  }

  if (!res.ok) {
    const detail = (json as ApiErrorBody | null)?.detail;
    throw new ApiError(res.status, detail || res.statusText || "Request failed");
  }

  return json as T;
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, { ...options, method: "PUT", body }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "DELETE" }),
};
