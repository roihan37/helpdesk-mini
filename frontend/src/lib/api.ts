import { API_URL } from "./env.ts";
import { retryAfterDeadline } from "./login-cooldown.ts";
import type {
  AccessTokenResponse,
  ApiErrorPayload,
  CurrentUser,
  LoginResponse,
} from "@/types/api";

let accessToken: string | null = null;
let refreshPromise: Promise<string> | null = null;
let authEpoch = 0;
let cookieRequestQueue: Promise<void> = Promise.resolve();
const authLossListeners = new Set<() => void>();
const tokenListeners = new Set<(token: string | null) => void>();

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
    public retryAt?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getAccessToken() {
  return accessToken;
}

export function getAuthEpoch() {
  return authEpoch;
}

function assertCurrentSession(epoch: number) {
  if (epoch !== authEpoch) throw new DOMException("The account session changed.", "AbortError");
}

function beginSessionChange() {
  authEpoch += 1;
  refreshPromise = null;
  setAccessToken(null);
  return authEpoch;
}

// Login and logout both mutate the HttpOnly cookie. Preserve invocation order
// even when a caller switches accounts before the preceding request finishes.
function queueCookieRequest<T>(request: () => Promise<T>): Promise<T> {
  const operation = cookieRequestQueue.then(request);
  cookieRequestQueue = operation.then(() => {}, () => {});
  return operation;
}

export function setAccessToken(token: string | null) {
  if (token === accessToken) return;
  accessToken = token;
  tokenListeners.forEach((listener) => listener(token));
}

export function onAccessTokenChanged(listener: (token: string | null) => void) {
  tokenListeners.add(listener);
  return () => { tokenListeners.delete(listener); };
}

export function onAuthLost(listener: () => void) {
  authLossListeners.add(listener);
  return () => {
    authLossListeners.delete(listener);
  };
}

function reportAuthLoss() {
  beginSessionChange();
  authLossListeners.forEach((listener) => listener());
}

async function parseResponse<T>(response: Response, envelope = false): Promise<T> {
  const retryAt = response.status === 429
    ? retryAfterDeadline(response.headers.get("Retry-After")) : undefined;
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
      retryAt,
    );
  }
  if (!payload || !("data" in payload)) {
    throw new ApiError(500, "INVALID_RESPONSE", "The server returned an invalid response.");
  }
  return (envelope ? payload : payload.data) as T;
}

export async function refreshAccessToken() {
  if (!refreshPromise) {
    const refreshEpoch = authEpoch;
    const operation = cookieRequestQueue.then(() => {
      assertCurrentSession(refreshEpoch);
      return fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
    })
      .then(parseResponse<AccessTokenResponse>)
      .then((data) => {
        assertCurrentSession(refreshEpoch);
        setAccessToken(data.access_token);
        return data.access_token;
      })
      .catch((error) => {
        assertCurrentSession(refreshEpoch);
        reportAuthLoss();
        throw error;
      })
      .finally(() => {
        if (refreshPromise === operation) refreshPromise = null;
      });
    refreshPromise = operation;
  }
  return refreshPromise;
}

interface RequestOptions extends RequestInit {
  auth?: boolean;
  retryAuth?: boolean;
  envelope?: boolean;
  responseType?: "json" | "blob";
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}) {
  const requestEpoch = authEpoch;
  const { auth = true, retryAuth = true, envelope = false, responseType = "json", headers, ...init } = options;
  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");
  if (init.body && !(init.body instanceof FormData)) requestHeaders.set("Content-Type", "application/json");
  if (auth && accessToken) requestHeaders.set("Authorization", `Bearer ${accessToken}`);

  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: requestHeaders,
      credentials: "include",
    });
    if (auth) assertCurrentSession(requestEpoch);

    if (response.status === 401 && auth && retryAuth) {
      try {
        await refreshAccessToken();
      } catch {
        assertCurrentSession(requestEpoch);
        throw new ApiError(401, "AUTHENTICATION_REQUIRED", "Your session has expired.");
      }
      assertCurrentSession(requestEpoch);
      return apiRequest<T>(path, { ...options, retryAuth: false });
    }
    const data = response.ok && responseType === "blob"
      ? await response.blob() as T
      : await parseResponse<T>(response, envelope);
    if (auth) assertCurrentSession(requestEpoch);
    return data;
  } catch (error) {
    if (auth) assertCurrentSession(requestEpoch);
    throw error;
  }
}

export async function login(email: string, password: string) {
  const epoch = beginSessionChange();
  const data = await queueCookieRequest(() => {
    assertCurrentSession(epoch);
    return apiRequest<LoginResponse>("/auth/login", {
      method: "POST",
      auth: false,
      retryAuth: false,
      body: JSON.stringify({ email, password }),
    });
  });
  // The response-body refresh token is deliberately discarded. The HttpOnly cookie is authoritative.
  assertCurrentSession(epoch);
  setAccessToken(data.access_token);
  return apiRequest<CurrentUser>("/auth/me", { retryAuth: false });
}

export async function logout() {
  beginSessionChange();
  await queueCookieRequest(async () => {
    const response = await fetch(`${API_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) await parseResponse<never>(response);
  });
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
    const detail = item as {
      loc?: unknown[];
      msg?: string
    };
    const path = detail.loc?.filter((part): part is string => typeof part === "string") ?? [];
    const field = path.at(-1);
    if (typeof field === "string" && typeof detail.msg === "string") {
      errors[field] = detail.msg;
      if (path.length > 1) errors[path.slice(-2).join(".")] = detail.msg;
    }
  }
  return errors;
}
