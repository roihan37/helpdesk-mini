import { API_URL } from "@/lib/env";
import type {
  AccessTokenResponse,
  ApiErrorPayload,
  CurrentUser,
  LoginResponse,
} from "@/types/api";

let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
let authEpoch = 0;
const authLossListeners = new Set<() => void>();

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getAccessToken() {
  return accessToken;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function onAuthLost(listener: () => void) {
  authLossListeners.add(listener);
  return () => {
    authLossListeners.delete(listener);
  };
}

function reportAuthLoss() {
  authEpoch += 1;
  accessToken = null;
  authLossListeners.forEach((listener) => listener());
}

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = (await response.json().catch(() => null)) as
    | { data?: T }
    | ApiErrorPayload
    | null;
  if (!response.ok) {
    const error = payload && "error" in payload ? payload.error : undefined;
    throw new ApiError(
      response.status,
      error?.code ?? "REQUEST_FAILED",
      error?.message ?? "Something went wrong. Try again.",
      error?.details,
    );
  }
  if (!payload || !("data" in payload)) {
    throw new ApiError(500, "INVALID_RESPONSE", "The server returned an invalid response.");
  }
  return payload.data as T;
}

export async function refreshAccessToken() {
  if (!refreshPromise) {
    const refreshEpoch = authEpoch;
    refreshPromise = fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    })
      .then(parseResponse<AccessTokenResponse>)
      .then((data) => {
        if (refreshEpoch !== authEpoch) {
          throw new ApiError(401, "AUTHENTICATION_REQUIRED", "Your session has ended.");
        }
        setAccessToken(data.access_token);
        return data.access_token;
      })
      .catch((error) => {
        reportAuthLoss();
        throw error;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions extends RequestInit {
  auth?: boolean;
  retryAuth?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}) {
  const { auth = true, retryAuth = true, headers, ...init } = options;
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (init.body) requestHeaders.set("Content-Type", "application/json");
  if (auth && accessToken) requestHeaders.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: requestHeaders,
    credentials: "include",
  });

  if (response.status === 401 && auth && retryAuth) {
    try {
      await refreshAccessToken();
    } catch {
      throw new ApiError(401, "AUTHENTICATION_REQUIRED", "Your session has expired.");
    }
    return apiRequest<T>(path, { ...options, retryAuth: false });
  }
  return parseResponse<T>(response);
}

export async function login(email: string, password: string) {
  const data = await apiRequest<LoginResponse>("/auth/login", {
    method: "POST",
    auth: false,
    retryAuth: false,
    body: JSON.stringify({ email, password }),
  });
  // The response-body refresh token is deliberately discarded. The HttpOnly cookie is authoritative.
  authEpoch += 1;
  setAccessToken(data.access_token);
  return apiRequest<CurrentUser>("/auth/me", { retryAuth: false });
}

export async function logout() {
  const response = await fetch(`${API_URL}/auth/logout`, {
    method: "POST",
    credentials: "include",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) await parseResponse<never>(response);
  authEpoch += 1;
  setAccessToken(null);
}

export function friendlyError(error: unknown, fallback = "Something went wrong. Try again.") {
  if (error instanceof ApiError) {
    if (error.status === 403) return "You do not have permission to perform this action.";
    return error.message || fallback;
  }
  return fallback;
}

export function validationErrors(error: unknown) {
  if (!(error instanceof ApiError) || error.status !== 422 || !Array.isArray(error.details)) return {};
  const errors: Record<string, string> = {};
  for (const item of error.details) {
    if (!item || typeof item !== "object") continue;
    const detail = item as { loc?: unknown[]; msg?: string };
    const path = detail.loc?.filter((part): part is string => typeof part === "string") ?? [];
    const field = path.at(-1);
    if (typeof field === "string" && typeof detail.msg === "string") {
      errors[field] = detail.msg;
      if (path.length > 1) errors[path.slice(-2).join(".")] = detail.msg;
    }
  }
  return errors;
}
