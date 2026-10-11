import type { TicketListEvent } from "../../types/api.ts";

export type ListConnectionState = "connecting" | "connected" | "reconnecting" | "offline";
export interface ListSocket {
  onopen: ((event: Event) => void) | null;
  onmessage: ((event: MessageEvent) => void) | null;
  onclose: ((event: CloseEvent) => void) | null;
  onerror: ((event: Event) => void) | null;
  close(code?: number): void;
}

interface Options {
  getToken(): string | null;
  refreshToken(): Promise<string>;
  subscribeToken(listener: (token: string | null) => void): () => void;
  connect(token: string): ListSocket;
  schedule(callback: () => void, delay: number): () => void;
  now(): number;
  invalidate(): Promise<unknown>;
  notify(event: TicketListEvent): void;
  stateChanged(state: ListConnectionState): void;
}

export function parseTicketListEvent(raw: unknown): TicketListEvent | null {
  if (typeof raw !== "string") return null;
  try {
    const event = JSON.parse(raw) as TicketListEvent;
    if (!event || !["ticket.created", "ticket.message_created", "ticket.status_changed", "ticket.assignment_changed", "ticket.read"].includes(event.type)) return null;
    if (!event.data || typeof event.data.ticket_id !== "string" ||
      !/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(event.data.ticket_id) ||
      typeof event.data.updated_at !== "string" || !Number.isFinite(Date.parse(event.data.updated_at))) return null;
    return event;
  } catch {
    return null;
  }
}

function expiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"))) as { exp?: unknown };
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

// A session owns one socket. Injected timers/transport keep lifecycle tests deterministic.
export function startTicketListSubscription(options: Options): () => void {
  let active = true;
  let socket: ListSocket | null = null;
  let socketToken: string | null = null;
  let retry = 0;
  let rejectedRetry = false;
  let refreshing = false;
  let cancelRetry: (() => void) | null = null;
  let cancelExpiry: (() => void) | null = null;
  let cancelInvalidation: (() => void) | null = null;
  let invalidating = false;
  let pendingInvalidation = false;
  const seen = new Set<string>();

  function detach() {
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
      socket.close(1000);
    }
    socket = null;
    socketToken = null;
  }

  function requestInvalidation(immediate = false) {
    if (!active) return;
    if (invalidating) {
      pendingInvalidation = true;
      return;
    }
    if (cancelInvalidation && !immediate) return;
    cancelInvalidation?.();
    const run = () => {
      cancelInvalidation = null;
      if (!active) return;
      invalidating = true;
      void options.invalidate().catch(() => { /* REST query owns its error UI. */ }).finally(() => {
        invalidating = false;
        if (pendingInvalidation && active) {
          pendingInvalidation = false;
          requestInvalidation();
        }
      });
    };
    if (immediate) run();
    else cancelInvalidation = options.schedule(run, 250);
  }

  async function refresh() {
    if (!active || refreshing) return;
    refreshing = true;
    try {
      const token = await options.refreshToken();
      if (active) connect(token);
    } catch {
      if (active) {
        detach();
        options.stateChanged("offline");
      }
    } finally {
      refreshing = false;
    }
  }

  function connect(token: string) {
    if (!active || (socket && socketToken === token)) return;
    cancelRetry?.();
    cancelExpiry?.();
    detach();
    options.stateChanged(retry ? "reconnecting" : "connecting");
    const current = options.connect(token);
    socket = current;
    socketToken = token;
    const expiresAt = expiry(token);
    if (expiresAt !== null) cancelExpiry = options.schedule(() => void refresh(), Math.max(1000, expiresAt - options.now() - 10000));
    current.onopen = () => {
      if (!active || socket !== current) return;
      retry = 0;
      rejectedRetry = false;
      options.stateChanged("connected");
      // Reconcile database state after reconnect, including events missed offline.
      requestInvalidation(true);
    };
    current.onmessage = ({ data }) => {
      if (!active || socket !== current) return;
      const event = parseTicketListEvent(data);
      if (!event) return;
      const key = `${event.type}:${event.data.ticket_id}:${event.data.updated_at}`;
      if (seen.has(key)) return;
      seen.add(key);
      if (seen.size > 200) seen.delete(seen.values().next().value!);
      requestInvalidation();
      options.notify(event);
    };
    current.onclose = ({ code }) => {
      if (!active || socket !== current) return;
      detach();
      cancelExpiry?.();
      if (code === 1008) {
        options.stateChanged("offline");
        if (!rejectedRetry) {
          rejectedRetry = true;
          void refresh();
        }
        return;
      }
      options.stateChanged("reconnecting");
      cancelRetry = options.schedule(() => {
        const nextToken = options.getToken();
        if (nextToken) connect(nextToken);
        else void refresh();
      }, Math.min(30000, 1000 * 2 ** Math.min(retry++, 5)));
    };
    current.onerror = () => { /* onclose owns recovery; never log token-bearing URLs. */ };
  }

  const unsubscribe = options.subscribeToken((token) => {
    if (token) connect(token);
    else stop();
  });
  function stop() {
    active = false;
    unsubscribe();
    cancelRetry?.();
    cancelExpiry?.();
    cancelInvalidation?.();
    detach();
  }
  const initial = options.getToken();
  if (initial) connect(initial);
  else void refresh();
  return stop;
}
