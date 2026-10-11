import assert from "node:assert/strict";
import test from "node:test";
import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { parseTicketListEvent, startTicketListSubscription, type ListSocket } from "./ticket-list-live-socket.ts";

const ticketId = "11111111-1111-4111-8111-111111111111";
const event = { type: "ticket.created", data: { ticket_id: ticketId, updated_at: "2026-10-11T00:00:00Z" } };
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

class Socket implements ListSocket {
  onopen: ListSocket["onopen"] = null;
  onmessage: ListSocket["onmessage"] = null;
  onclose: ListSocket["onclose"] = null;
  onerror: ListSocket["onerror"] = null;
  closed = false;
  readonly token: string;
  constructor(token: string) { this.token = token; }
  close() { this.closed = true; }
  open() { this.onopen?.(new Event("open")); }
  receive(value: unknown) { this.onmessage?.({ data: JSON.stringify(value) } as MessageEvent); }
  disconnect(code = 1006) { this.onclose?.({ code } as CloseEvent); }
}

function fixture(initialToken = "access-one") {
  let clock = 0;
  let token: string | null = initialToken;
  let listener: ((token: string | null) => void) | null = null;
  let refreshes = 0;
  let invalidations = 0;
  let notifications = 0;
  const timers = new Set<{ at: number; callback: () => void }>();
  const sockets: Socket[] = [];
  const states: string[] = [];
  const stop = startTicketListSubscription({
    getToken: () => token,
    subscribeToken: (next) => { listener = next; return () => { listener = null; }; },
    refreshToken: async () => {
      refreshes++;
      token = `refreshed-${refreshes}`;
      listener?.(token);
      return token;
    },
    connect: (value) => { const socket = new Socket(value); sockets.push(socket); return socket; },
    schedule: (callback, delay) => {
      const timer = { at: clock + delay, callback };
      timers.add(timer);
      return () => { timers.delete(timer); };
    },
    now: () => clock,
    invalidate: async () => { invalidations++; },
    notify: () => { notifications++; },
    stateChanged: (value) => { states.push(value); }
  });
  return {
    sockets, states, stop, timers,
    get refreshes() { return refreshes; },
    get invalidations() { return invalidations; },
    get notifications() { return notifications; },
    changeToken(value: string | null) { token = value; listener?.(value); },
    advance(ms: number) {
      const target = clock + ms;
      for (;;) {
        const next = [...timers].filter((item) => item.at <= target).sort((a, b) => a.at - b.at)[0];
        if (!next) break;
        clock = next.at;
        timers.delete(next);
        next.callback();
      }
      clock = target;
    }
  };
}

test("accepts only supported minimal ticket-list events", () => {
  assert.deepEqual(parseTicketListEvent(JSON.stringify(event)), event);
  for (const value of ["bad json", JSON.stringify({ ...event, type: "message.created" }), JSON.stringify({ ...event, data: { ticket_id: "bad", updated_at: "no date" } }), null]) {
    assert.equal(parseTicketListEvent(value), null);
  }
});

test("one subscription coalesces activity and ignores duplicate/invalid notifications", async () => {
  const f = fixture();
  f.sockets[0].open();
  await flush();
  f.sockets[0].receive(event);
  f.sockets[0].receive(event);
  f.sockets[0].receive({ ...event, type: "ticket.message_created" });
  f.sockets[0].receive({ type: "unknown" });
  assert.equal(f.notifications, 2);
  assert.equal(f.invalidations, 1);
  f.advance(250);
  await flush();
  assert.equal(f.invalidations, 2);
  assert.equal(f.sockets.length, 1);
  f.stop();
});

test("reconnect refetches missed activity and ignores callbacks from the old socket", async () => {
  const f = fixture();
  const old = f.sockets[0];
  old.open();
  await flush();
  const staleMessage = old.onmessage;
  old.disconnect();
  f.advance(1000);
  assert.equal(f.sockets.length, 2);
  f.sockets[1].open();
  await flush();
  staleMessage?.({ data: JSON.stringify(event) } as MessageEvent);
  assert.equal(f.invalidations, 2);
  assert.equal(f.notifications, 0);
  assert.equal(old.closed, true);
  f.stop();
});

test("token refresh replaces, never parallels, the session socket", () => {
  const f = fixture();
  f.changeToken("access-two");
  f.changeToken("access-two");
  assert.equal(f.sockets.length, 2);
  assert.equal(f.sockets[0].closed, true);
  assert.equal(f.sockets.filter((socket) => !socket.closed).length, 1);
  f.stop();
});

test("auth rejection refreshes once and does not loop on persistent rejection", async () => {
  const f = fixture();
  f.sockets[0].disconnect(1008);
  await flush();
  assert.equal(f.refreshes, 1);
  assert.equal(f.sockets.length, 2);
  f.sockets[1].disconnect(1008);
  await flush();
  f.advance(60000);
  assert.equal(f.refreshes, 1);
  assert.equal(f.states.at(-1), "offline");
  f.stop();
});

test("access token expiry triggers refresh without real-time sleeps", async () => {
  const token = `header.${Buffer.from(JSON.stringify({ exp: 20 })).toString("base64url")}.signature`;
  const f = fixture(token);
  f.sockets[0].open();
  f.advance(10000);
  await flush();
  assert.equal(f.refreshes, 1);
  assert.equal(f.sockets[0].closed, true);
  assert.equal(f.sockets.length, 2);
  f.stop();
});

test("logout and unmount cancel sockets, retries and pending activity", async () => {
  for (const logout of [true, false]) {
    const f = fixture();
    f.sockets[0].receive(event);
    f.sockets[0].disconnect();
    if (logout) f.changeToken(null);
    else f.stop();
    f.advance(60000);
    await flush();
    f.changeToken("another-user");
    assert.equal(f.sockets.length, 1);
    assert.equal(f.sockets[0].closed, true);
    assert.equal(f.invalidations, 0);
    assert.equal(f.timers.size, 0);
    f.stop();
  }
});

test("list invalidation preserves paginated envelopes, search and status query keys", async () => {
  const client = new QueryClient();
  const filters = { page: 2, page_size: 20, search: "support", status: "open" };
  const key = ["tickets", filters];
  const payload = { data: [], pagination: { page: 2, page_size: 20, total_items: 25, total_pages: 2 } };
  client.setQueryData(key, payload);
  client.setQueryData(["ticket", ticketId], { id: ticketId });
  await client.invalidateQueries({ queryKey: ["tickets"] }, { cancelRefetch: true });
  assert.deepEqual(client.getQueryData(key), payload);
  assert.equal(client.getQueryState(key)?.isInvalidated, true);
  assert.equal(client.getQueryState(["ticket", ticketId])?.isInvalidated, false);
  assert.deepEqual(key[1], filters);
  client.clear();
});

test("an activity event supersedes an in-flight pre-event list response", async () => {
  const client = new QueryClient();
  const key = ["tickets", { page: 2, search: "support", status: "open" }];
  const payload = (total: number) => ({ data: [], pagination: { page: 2, page_size: 20, total_items: total, total_pages: 2 } });
  client.setQueryData(key, payload(21));
  let requests = 0;
  let finishOldRequest: (value: ReturnType<typeof payload>) => void = () => {};
  const observer = new QueryObserver(client, {
    queryKey: key,
    staleTime: Infinity,
    queryFn: () => {
      requests++;
      return requests === 1
        ? new Promise<ReturnType<typeof payload>>((resolve) => { finishOldRequest = resolve; })
        : Promise.resolve(payload(23));
    }
  });
  const unsubscribe = observer.subscribe(() => {});
  try {
    const oldRequest = client.refetchQueries({ queryKey: key });
    const activity = client.invalidateQueries({ queryKey: ["tickets"] }, { cancelRefetch: true });
    finishOldRequest(payload(22));
    await Promise.all([oldRequest, activity]);
    assert.equal(requests, 2);
    assert.deepEqual(client.getQueryData(key), payload(23));
  } finally {
    unsubscribe();
    client.clear();
  }
});
