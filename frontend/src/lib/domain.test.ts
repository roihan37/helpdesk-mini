import assert from "node:assert/strict";
import test from "node:test";
import { mergeMessages, nextTicketStatus, safeReturnPath } from "./domain.ts";
import type { Message } from "@/types/api";

test("safeReturnPath accepts local paths and rejects external redirects", () => {
  assert.equal(safeReturnPath("/tickets/123?status=open"), "/tickets/123?status=open");
  assert.equal(safeReturnPath("//attacker.example"), "/tickets");
  assert.equal(safeReturnPath("https://attacker.example"), "/tickets");
});

test("ticket transitions exposed by the UI follow the role matrix", () => {
  assert.equal(nextTicketStatus("agent", "open"), "in_progress");
  assert.equal(nextTicketStatus("admin", "resolved"), "closed");
  assert.equal(nextTicketStatus("customer", "resolved"), "open");
  assert.equal(nextTicketStatus("customer", "open"), null);
  assert.equal(nextTicketStatus("agent", "closed"), null);
});

test("message reconciliation deduplicates IDs and orders deterministically", () => {
  const base = { ticket_id: "ticket", sender_id: "sender", sender_name: "User", sender_role: "agent", body: "body" } as const;
  const late: Message = { ...base, id: "b", created_at: "2026-01-02T00:00:00Z" };
  const early: Message = { ...base, id: "a", created_at: "2026-01-01T00:00:00Z" };
  assert.deepEqual(mergeMessages([late], [early, late]).map((message) => message.id), ["a", "b"]);
});
