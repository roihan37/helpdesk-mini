import type { TicketStatus } from "@/types/api";

export const ticketStatuses: TicketStatus[] = ["open", "in_progress", "resolved", "closed"];
export const ticketSearchDelay = 350;

export interface TicketListFilters {
  status?: TicketStatus;
  search: string;
  page: number;
  page_size: number;
}

function positiveInteger(value: string | null, fallback: number, maximum: number) {
  const parsed = Number(value);
  return value && /^[1-9]\d*$/.test(value) && parsed <= maximum ? parsed : fallback;
}

export function readTicketListFilters(params: Pick<URLSearchParams, "get">): TicketListFilters {
  const rawStatus = params.get("status");
  return {
    status: ticketStatuses.includes(rawStatus as TicketStatus) ? rawStatus as TicketStatus : undefined,
    search: (params.get("search") ?? "").trim(),
    page: positiveInteger(params.get("page"), 1, 2_147_483_647),
    page_size: positiveInteger(params.get("page_size"), 20, 100),
  };
}

export function ticketListApiPath(filters: TicketListFilters) {
  const params = new URLSearchParams({ page: String(filters.page), page_size: String(filters.page_size) });
  if (filters.status) params.set("status", filters.status);
  if (filters.search) params.set("search", filters.search);
  return `/tickets?${params}`;
}

export function ticketListHref(
  current: string,
  changes: { status?: string; search?: string; page?: number },
) {
  const params = new URLSearchParams(current);
  for (const key of ["status", "search"] as const) {
    if (key in changes) {
      const value = changes[key]?.trim();
      if (value) params.set(key, value); else params.delete(key);
    }
  }
  if ("status" in changes || "search" in changes || changes.page === 1) {
    params.delete("page");
  } else if (changes.page !== undefined) {
    params.set("page", String(changes.page));
  }
  return `/tickets${params.size ? `?${params}` : ""}`;
}
