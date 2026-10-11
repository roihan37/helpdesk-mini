import type { Message, MessageReadData, Role, TicketStatus } from "@/types/api";

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
  for (const message of incoming) {
    const previous = byId.get(message.id);
    const readers = new Map((previous?.read_by ?? []).map((reader) => [reader.user_id, reader]));
    for (const reader of message.read_by ?? []) readers.set(reader.user_id, reader);
    byId.set(message.id, { ...message, read_by: [...readers.values()] });
  }
  return [...byId.values()].sort(
    (a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id),
  );
}

export function sequenceAtMost(sequence: string, boundary: string) {
  return sequence.length < boundary.length || (sequence.length === boundary.length && sequence <= boundary);
}

export function applyReadReceipts(messages: Message[], receipts: Iterable<MessageReadData>, senderId: string) {
  const boundaries = [...receipts];
  let changed = false;
  const updated = messages.map((message) => {
    if (message.sender_id !== senderId || !message.sequence) return message;
    const readers = new Map((message.read_by ?? []).map((reader) => [reader.user_id, reader]));
    let added = false;
    for (const receipt of boundaries) {
      if (receipt.ticket_id !== message.ticket_id || receipt.user_id === senderId || readers.has(receipt.user_id)) continue;
      if (sequenceAtMost(message.sequence, receipt.last_read_sequence)) {
        readers.set(receipt.user_id, { user_id: receipt.user_id, name: receipt.name, role: receipt.role });
        added = true;
      }
    }
    if (!added) return message;
    changed = true;
    return { ...message, read_by: [...readers.values()] };
  });
  return changed ? updated : messages;
}

export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
