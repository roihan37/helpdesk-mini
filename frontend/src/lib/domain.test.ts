import assert from "node:assert/strict";
import test from "node:test";
import { applyReadReceipts, mergeMessages, nextTicketStatus, safeReturnPath, sequenceAtMost } from "./domain.ts";
import type { Message, MessageReadData } from "@/types/api";

test(
  "safeReturnPath accepts local paths and rejects external redirects",
  () => {
    assert.equal(safeReturnPath("/tickets/123?status=open"), "/tickets/123?status=open");
    assert.equal(safeReturnPath("//attacker.example"), "/tickets");
    assert.equal(safeReturnPath("https://attacker.example"), "/tickets");
  }
);

test(
  "ticket transitions exposed by the UI follow the role matrix",
  () => {
    assert.equal(nextTicketStatus("agent", "open"), "in_progress");
    assert.equal(nextTicketStatus("admin", "resolved"), "closed");
    assert.equal(nextTicketStatus("customer", "resolved"), "open");
    assert.equal(nextTicketStatus("customer", "open"), null);
    assert.equal(nextTicketStatus("agent", "closed"), null);
  }
);

test(
  "message reconciliation deduplicates IDs and orders deterministically",
  () => {
    const base: Omit<Message, "id" | "created_at"> = {
      ticket_id: "ticket",
      sender_id: "sender",
      sender_name: "User",
      sender_role: "agent",
      body: "body",
      sequence: "1",
      read_by: [],
      attachment: null,
    };
    const late: Message = { ...base, id: "b", created_at: "2026-01-02T00:00:00Z" };
    const early: Message = { ...base, id: "a", created_at: "2026-01-01T00:00:00Z" };
    assert.deepEqual(mergeMessages([late], [early, late]).map((message) => message.id), ["a", "b"]);
  }
);

const outgoing: Message = {
  id: "message", ticket_id: "ticket", sender_id: "sender", sender_name: "Agent",
  sender_role: "agent", body: "Hello", sequence: "9007199254740993",
  created_at: "2026-01-01T00:00:00Z", read_by: [], attachment: null,
};
const receipt: MessageReadData = {
  ticket_id: "ticket", user_id: "customer", name: "Customer", role: "customer",
  last_read_sequence: "9007199254740993",
};

test("receipt boundaries retain PostgreSQL bigint precision", () => {
  assert.equal(sequenceAtMost("9007199254740993", "9007199254740992"), false);
  assert.equal(sequenceAtMost("9", "10"), true);
  assert.equal(sequenceAtMost("10", "10"), true);
});

test("receipts affect only the current author's observed messages in the same ticket", () => {
  const incoming = { ...outgoing, id: "incoming", sender_id: "customer" };
  const unseen = { ...outgoing, id: "unseen", sequence: "9007199254740994" };
  const messages = [outgoing, incoming, unseen];
  for (const ignored of [
    { ...receipt, ticket_id: "another-ticket" },
    { ...receipt, user_id: "sender" },
    { ...receipt, last_read_sequence: "9007199254740992" },
  ]) assert.equal(applyReadReceipts(messages, [ignored], "sender"), messages);
  const updated = applyReadReceipts(messages, [receipt], "sender");
  assert.deepEqual(updated[0].read_by?.map((reader) => reader.user_id), ["customer"]);
  assert.equal(updated[1], incoming);
  assert.equal(updated[2], unseen);
  assert.equal(applyReadReceipts(updated, [receipt, receipt], "sender"), updated);
});

test("reader states remain recipient-specific during duplicate and reconnect reconciliation", () => {
  const read = applyReadReceipts([outgoing], [receipt], "sender");
  const second = { ...receipt, user_id: "second-agent", name: "Second agent", role: "agent" } as const;
  const both = applyReadReceipts(read, [second], "sender");
  assert.deepEqual(both[0].read_by?.map((reader) => reader.user_id), ["customer", "second-agent"]);
  const restored = mergeMessages(both, [outgoing, outgoing]);
  assert.equal(restored.length, 1);
  assert.deepEqual(restored[0].read_by, both[0].read_by);
});

test("attachment metadata survives message reconciliation without duplicate messages", () => {
  const attached: Message = { ...outgoing, attachment: {
    id: "image", mime_type: "image/png", byte_size: 200, width: 8, height: 6,
  } };
  const reconciled = mergeMessages([attached], [attached, attached]);
  assert.equal(reconciled.length, 1);
  assert.deepEqual(reconciled[0].attachment, attached.attachment);
});
