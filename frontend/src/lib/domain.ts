import type { Message, Role, TicketStatus } from "@/types/api";

export const statusLabels: Record<TicketStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
  closed: "Closed",
};

export const roleLabels: Record<Role, string> = {
  admin: "Admin",
  agent: "Agent",
  customer: "Customer",
};

export function safeReturnPath(value: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/tickets";
  return value;
}

export function nextTicketStatus(role: Role, status: TicketStatus) {
  if (role === "customer") return status === "resolved" ? "open" : null;
  const next: Partial<Record<TicketStatus, TicketStatus>> = {
    open: "in_progress",
    in_progress: "resolved",
    resolved: "closed",
  };
  return next[status] ?? null;
}

export function mergeMessages(current: Message[], incoming: Message[]) {
  const byId = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) byId.set(message.id, message);
  return [...byId.values()].sort(
    (a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id),
  );
}

export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
