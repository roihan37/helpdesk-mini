import assert from "node:assert/strict";
import { after, beforeEach, test } from "node:test";
import { QueryClient } from "@tanstack/react-query";

process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
process.env.NEXT_PUBLIC_WS_URL = "ws://localhost:8000";
const { apiRequest, getAccessToken, login, logout, onAuthLost, refreshAccessToken } = await import("./api.ts");
const originalFetch = globalThis.fetch;
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
const response = (data: unknown, status = 200) => new Response(JSON.stringify({ data }), { status });
const user = (email: string) => ({ id: email, email, business_id: email.split("@")[1], role: "agent", name: email });
const defaultFetch: typeof fetch = async (input, init) => {
  const path = String(input);
  if (path.endsWith("/auth/logout")) return new Response(null, { status: 204 });
  if (path.endsWith("/auth/login")) {
    const { email } = JSON.parse(String(init?.body));
    return response({ access_token: email, refresh_token: "discarded" });
  }
  if (path.endsWith("/auth/me")) return response(user(getAccessToken()!));
  throw new Error("Unexpected request");
};
beforeEach(async () => { globalThis.fetch = defaultFetch; await logout(); });
after(() => { globalThis.fetch = originalFetch; });
const northstar = "agent@northstar.example";
const orbit = "agent@orbit.example";

test("login preserves 429 Retry-After deadline and does not retry credentials", async (context) => {
  context.mock.method(Date, "now", () => 1000);
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response(JSON.stringify({ error: { code: "AUTH_RATE_LIMITED", message: "Too many login attempts." } }), {
      status: 429, headers: { "Retry-After": "37" },
    });
  };
  await assert.rejects(login(northstar, "test-only"), (error: unknown) => {
    const failure = error as { status: number; code: string; retryAt: number };
    assert.equal(failure.status, 429);
    assert.equal(failure.code, "AUTH_RATE_LIMITED");
    assert.equal(failure.retryAt, 38000);
    return true;
  });
  assert.equal(calls, 1);
});

test("ordinary login 401 has no cooldown even if an unrelated Retry-After is present", async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ error: { code: "AUTH_INVALID_CREDENTIALS", message: "Invalid email or password." } }), {
    status: 401, headers: { "Retry-After": "37" },
  });
  await assert.rejects(login(northstar, "test-only"), (error: unknown) => {
    const failure = error as { status: number; retryAt?: number };
    assert.equal(failure.status, 401);
    assert.equal(failure.retryAt, undefined);
    return true;
  });
});

test("ordinary login and authenticated requests use the current access token", async () => {
  assert.deepEqual(await login(northstar, "test-only"), user(northstar));
  globalThis.fetch = async (_input, init) => {
    assert.equal(new Headers(init?.headers).get("Authorization"), `Bearer ${northstar}`);
    return response({ unread_count: 2 });
  };
  assert.deepEqual(await apiRequest("/tickets"), { unread_count: 2 });
});

test("logout removes the token immediately, before the cookie request completes", async () => {
  await login(northstar, "test-only");
  const pending = deferred<Response>();
  globalThis.fetch = () => pending.promise;
  const operation = logout();
  const tokenDuringLogout = getAccessToken();
  pending.resolve(new Response(null, { status: 204 }));
  await operation;
  assert.equal(tokenDuringLogout, null);
});

test("a previous account's delayed success cannot resolve into the new session", async () => {
  await login(northstar, "test-only");
  const pending = deferred<Response>();
  globalThis.fetch = (input, init) => String(input).endsWith("/tickets") ? pending.promise : defaultFetch(input, init);
  const oldRequest = apiRequest("/tickets");
  const rejected = assert.rejects(oldRequest, { name: "AbortError" });
  await login(orbit, "test-only");
  pending.resolve(response({ private_ticket: "northstar", unread_count: 9 }));
  await rejected;
  assert.equal(getAccessToken(), orbit);
});

test("a previous account's delayed 401 never refreshes or retries as the new account", async () => {
  await login(northstar, "test-only");
  const pending = deferred<Response>();
  let refreshes = 0;
  let ticketRequests = 0;
  globalThis.fetch = (input, init) => {
    if (String(input).endsWith("/tickets")) { ticketRequests++; return pending.promise; }
    if (String(input).endsWith("/auth/refresh")) { refreshes++; return Promise.resolve(response({ access_token: orbit })); }
    return defaultFetch(input, init);
  };
  const rejected = assert.rejects(apiRequest("/tickets"), { name: "AbortError" });
  await login(orbit, "test-only");
  pending.resolve(response(null, 401));
  await rejected;
  assert.equal(refreshes, 0);
  assert.equal(ticketRequests, 1);
});

test("an old refresh failure does not remove the new account or emit auth loss", async () => {
  await login(northstar, "test-only");
  const pending = deferred<Response>();
  globalThis.fetch = (input, init) => String(input).endsWith("/auth/refresh") ? pending.promise : defaultFetch(input, init);
  let losses = 0;
  const unsubscribe = onAuthLost(() => { losses++; });
  try {
    const rejected = assert.rejects(refreshAccessToken());
    await login(orbit, "test-only");
    pending.resolve(response(null, 401));
    await rejected;
    assert.equal(getAccessToken(), orbit);
    assert.equal(losses, 0);
  } finally { unsubscribe(); }
});

test("body parsing is also fenced against an account switch", async () => {
  await login(northstar, "test-only");
  const body = deferred<{ data: unknown }>();
  globalThis.fetch = (input, init) => String(input).endsWith("/tickets")
    ? Promise.resolve({ ok: true, status: 200, json: () => body.promise } as Response)
    : defaultFetch(input, init);
  const rejected = assert.rejects(apiRequest("/tickets"), { name: "AbortError" });
  await flush();
  await login(orbit, "test-only");
  body.resolve({ data: { private_ticket: "northstar" } });
  await rejected;
});

test("logout cookie clearing finishes before the next login writes its cookie", async () => {
  await login(northstar, "test-only");
  const pending = deferred<Response>();
  const calls: string[] = [];
  globalThis.fetch = (input, init) => {
    const path = String(input);
    calls.push(path);
    return path.endsWith("/auth/logout") ? pending.promise : defaultFetch(input, init);
  };
  const ending = logout();
  const entering = login(orbit, "test-only");
  await flush();
  assert.equal(calls.some((path) => path.endsWith("/auth/login")), false);
  pending.resolve(new Response(null, { status: 204 }));
  await ending;
  assert.deepEqual(await entering, user(orbit));
  assert.equal(getAccessToken(), orbit);
});

test("rapid login switching cannot restore an older account or reorder cookie writes", async () => {
  const pending = deferred<Response>();
  let loginRequests = 0;
  globalThis.fetch = (input, init) => {
    if (String(input).endsWith("/auth/login") && ++loginRequests === 1) return pending.promise;
    return defaultFetch(input, init);
  };
  const rejected = assert.rejects(login(northstar, "test-only"), { name: "AbortError" });
  await flush();
  const entering = login(orbit, "test-only");
  await flush();
  assert.equal(loginRequests, 1);
  pending.resolve(response({ access_token: northstar }));
  await rejected;
  assert.deepEqual(await entering, user(orbit));
  assert.equal(getAccessToken(), orbit);
});

test("old refresh completion cannot clear or replace the new session's single-flight refresh", async () => {
  await login(northstar, "test-only");
  const old = deferred<Response>();
  const current = deferred<Response>();
  let refreshes = 0;
  globalThis.fetch = (input, init) => String(input).endsWith("/auth/refresh")
    ? (++refreshes === 1 ? old.promise : current.promise)
    : defaultFetch(input, init);
  const rejected = assert.rejects(refreshAccessToken(), { name: "AbortError" });
  await flush();
  await login(orbit, "test-only");
  const newRefresh = refreshAccessToken();
  await flush();
  old.resolve(response({ access_token: northstar }));
  await rejected;
  const sharedRefresh = refreshAccessToken();
  await flush();
  assert.equal(refreshes, 2);
  current.resolve(response({ access_token: "orbit-refreshed" }));
  assert.deepEqual(await Promise.all([newRefresh, sharedRefresh]), ["orbit-refreshed", "orbit-refreshed"]);
  assert.equal(getAccessToken(), "orbit-refreshed");
});

test("clearing the query cache and switching accounts prevents late mutation cache writes", async () => {
  await login(northstar, "test-only");
  const client = new QueryClient();
  const pending = deferred<Response>();
  globalThis.fetch = (input, init) => String(input).endsWith("/tickets") ? pending.promise : defaultFetch(input, init);
  const mutation = client.getMutationCache().build(client, {
    mutationFn: () => apiRequest("/tickets", { method: "POST", body: "{}" }),
    onSuccess: (data) => { client.setQueryData(["tickets"], data); }
  });
  const rejected = assert.rejects(mutation.execute(undefined), { name: "AbortError" });
  await flush();
  client.clear();
  await login(orbit, "test-only");
  client.setQueryData(["tickets"], { business: "orbit", unread_count: 0 });
  pending.resolve(response({ business: "northstar", unread_count: 7 }));
  await rejected;
  assert.deepEqual(client.getQueryData(["tickets"]), { business: "orbit", unread_count: 0 });
  client.clear();
});

test("a failed logout still removes local credentials and does not poison the login queue", async () => {
  await login(northstar, "test-only");
  globalThis.fetch = (input, init) => String(input).endsWith("/auth/logout")
    ? Promise.reject(new TypeError("Network unavailable")) : defaultFetch(input, init);
  const rejected = assert.rejects(logout(), TypeError);
  assert.equal(getAccessToken(), null);
  await rejected;
  assert.deepEqual(await login(orbit, "test-only"), user(orbit));
});
