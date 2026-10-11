import assert from "node:assert/strict";
import test from "node:test";
import { queryKeys } from "../../lib/query.ts";
import { readTicketListFilters, ticketListApiPath, ticketListHref, ticketSearchDelay } from "./ticket-list-query.ts";

test("ticket filters use validated pagination defaults", () => {
  assert.deepEqual(readTicketListFilters(new URLSearchParams()), {
    status: undefined, search: "", page: 1, page_size: 20,
  });
  for (const invalid of ["0", "-1", "1.5", "invalid", "2147483648"]) {
    assert.equal(readTicketListFilters(new URLSearchParams({ page: invalid })).page, 1);
  }
  assert.equal(readTicketListFilters(new URLSearchParams("page_size=101")).page_size, 20);
  assert.equal(readTicketListFilters(new URLSearchParams("status=invalid")).status, undefined);
});

test("ticket search and status are encoded in the server request and cache key", () => {
  const filters = readTicketListFilters(new URLSearchParams("search=%20Billing+%26+login%20&status=open&page=2&page_size=5"));
  assert.deepEqual(filters, { status: "open", search: "Billing & login", page: 2, page_size: 5 });
  const params = new URLSearchParams(ticketListApiPath(filters).split("?")[1]);
  assert.equal(params.get("search"), "Billing & login");
  assert.equal(params.get("status"), "open");
  assert.equal(params.get("page"), "2");
  assert.equal(params.get("page_size"), "5");
  for (const change of [{ page: 3 }, { search: "other" }, { status: "closed" }, { page_size: 10 }]) {
    assert.notDeepEqual(queryKeys.tickets(filters), queryKeys.tickets({ ...filters, ...change }));
  }
  assert.equal(queryKeys.tickets(filters)[0], "tickets"); // existing prefix invalidations still work
  assert.equal(ticketSearchDelay, 350);
});

test("changing search or status resets to the first page while preserving other filters", () => {
  const current = "search=billing&status=open&page=4&page_size=5";
  const search = new URLSearchParams(ticketListHref(current, { search: "  invoice  " }).split("?")[1]);
  assert.equal(search.get("search"), "invoice");
  assert.equal(search.get("status"), "open");
  assert.equal(search.get("page_size"), "5");
  assert.equal(search.has("page"), false);
  const status = new URLSearchParams(ticketListHref(current, { status: "resolved" }).split("?")[1]);
  assert.equal(status.get("search"), "billing");
  assert.equal(status.get("status"), "resolved");
  assert.equal(status.has("page"), false);
});

test("next and previous pages preserve the active search and status", () => {
  const current = "search=billing&status=open&page=2&page_size=5";
  const next = ticketListHref(current, { page: 3 });
  assert.deepEqual(readTicketListFilters(new URLSearchParams(next.split("?")[1])), {
    search: "billing", status: "open", page: 3, page_size: 5,
  });
  const previous = ticketListHref(next.split("?")[1], { page: 1 });
  assert.equal(new URLSearchParams(previous.split("?")[1]).has("page"), false);
  assert.equal(readTicketListFilters(new URLSearchParams(previous.split("?")[1])).search, "billing");
});

test("clear filters removes search, status, and page, including an empty search", () => {
  assert.equal(ticketListHref("search=billing&status=open&page=3", { search: "", status: "" }), "/tickets");
  assert.equal(ticketListHref("search=billing&page=3", { search: "   " }), "/tickets");
});
