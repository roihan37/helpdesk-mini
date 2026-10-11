"use client";

import { Icon } from "@/components/icon";
import { Alert, Avatar, Badge, Button, EmptyState, Field, Input, Select, Skeleton } from "@/components/ui";
import { TicketListSkeleton } from "@/components/loading-skeletons";
import { useAuth } from "@/features/auth/auth-provider";
import { apiRequest } from "@/lib/api";
import { formatDateTime, statusLabels } from "@/lib/domain";
import { queryKeys } from "@/lib/query";
import type { TicketListItem, TicketListResponse } from "@/types/api";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { readTicketListFilters, ticketListApiPath, ticketListHref, ticketSearchDelay, ticketStatuses } from "./ticket-list-query";
import { useTicketListLive } from "./ticket-list-live-provider";

export function TicketListPage() {
  const { user } = useAuth();
  const live = useTicketListLive();
  const router = useRouter();
  const searchParams = useSearchParams();
  const params = searchParams.toString();
  const filters = readTicketListFilters(searchParams);
  const { status, search, page } = filters;
  const [isNavigating, startTransition] = useTransition();
  const [draft, setDraft] = useState({ source: search, value: search });
  // Reconcile URL navigation without remounting the input or losing keyboard focus.
  if (draft.source !== search) setDraft({ source: search, value: search });
  const searchInput = draft.source === search ? draft.value : search;
  const searchPending = searchInput.trim() !== search;
  useEffect(() => {
    if (!searchPending) return;
    const timer = setTimeout(() => {
      startTransition(() => {
        router.replace(ticketListHref(params, { search: searchInput }), { scroll: false });
      });
    }, ticketSearchDelay);
    return () => clearTimeout(timer);
  }, [params, router, searchInput, searchPending]);
  const tickets = useQuery({
    queryKey: queryKeys.tickets(filters),
    queryFn: () => apiRequest<TicketListResponse>(ticketListApiPath(filters), { envelope: true }),
    // Retain pagination layout during navigation, but never show old rows as new results.
    placeholderData: keepPreviousData
  });
  function updateStatus(value: string) {
    startTransition(() => {
      router.replace(ticketListHref(params, { status: value, search: searchInput }), { scroll: false });
    });
  }
  function updatePage(value: number) {
    startTransition(() => {
      router.replace(ticketListHref(params, { page: value }), { scroll: false });
    });
  }
  const items = tickets.data?.data;
  const pagination = tickets.data?.pagination;
  const resultsLoading = searchPending || isNavigating || tickets.isLoading || tickets.isPlaceholderData;
  const loadingLabel = searchPending || (resultsLoading && search)
    ? "Searching tickets…"
    : resultsLoading
      ? status ? "Filtering tickets…" : "Loading tickets…"
      : tickets.isFetching ? "Updating tickets…" : "";
  return <div className="page-stack">
    <header className="page-header">
      <div>
        <h1>{user?.role === "customer" ? "My tickets" : "Tickets"}</h1>
        <p>
          {user?.role === "customer"
            ? "Your support requests, conversations, and progress in one place."
            : "Manage your business’s support requests and keep conversations moving."}
        </p>
      </div>
      {user?.role === "customer"
        ? <Link className="button button-primary" href="/tickets/new"><Icon name="plus" />New ticket</Link>
        : null}
    </header>
    {live.notice ? <Alert>{live.notice}</Alert> : null}
    {live.connection === "reconnecting"
      ? <Alert>Live updates are disconnected. Reconnecting automatically; you can still use the ticket list.</Alert>
      : null}
    {live.connection === "offline"
      ? <Alert>Live updates are unavailable. You can still use the ticket list; sign in again if your session has expired.</Alert>
      : null}
    <section className="data-panel" aria-label="Ticket list">
      <div className="panel-toolbar">
        <div className="panel-heading">
          <Icon name="tickets" />
          <h2>{status ? statusLabels[status] : "All tickets"}</h2>
          {resultsLoading
            ? <Skeleton className="skeleton-ticket-count" />
            : pagination ? <span className="count-label">{pagination.total_items}</span> : null}
        </div>
        <div className="ticket-filter-tools">
          <div className="filter-row ticket-filters">
            <Field label="Search" name="ticket-search">
              <Input
                id="ticket-search"
                type="search"
                placeholder="Search subjects"
                maxLength={150}
                value={searchInput}
                onChange={(event) => setDraft({ source: search, value: event.target.value })}
              />
            </Field>
            <Field label="Status" name="status-filter">
              <Select
                id="status-filter"
                value={status ?? ""}
                onChange={(event) => updateStatus(event.target.value)}
              >
                <option value="">All statuses</option>
                {ticketStatuses.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}
              </Select>
            </Field>
          </div>
          <span className="ticket-filter-status" role="status" aria-live="polite" aria-atomic="true">
            {loadingLabel ? <><span className="ticket-loading-dot" aria-hidden="true" />{loadingLabel}</> : null}
          </span>
        </div>
      </div>
      <div className="ticket-results" aria-busy={resultsLoading || tickets.isFetching}>
        {tickets.isError && !resultsLoading
          ? <div className="panel-feedback">
            <Alert tone="error">Tickets could not be loaded. Check your connection and try again. <Button variant="quiet" onClick={() => void tickets.refetch()}>Retry</Button></Alert>
          </div>
          : null}
        {resultsLoading ? <TicketListSkeleton /> : null}
        {!resultsLoading && items && items.length === 0
          ? pagination && pagination.total_items > 0
            ? <EmptyState
              title="No tickets on this page"
              action={<Button variant="secondary" onClick={() => updatePage(1)}>Go to first page</Button>}
            >Tickets may have changed since this page was opened.</EmptyState>
            : search || status
            ? <EmptyState
              title="No tickets match these filters"
              action={<Button variant="secondary" onClick={() => startTransition(() => router.replace(ticketListHref(params, { status: "", search: "" }), { scroll: false }))}>Clear filters</Button>}
            >Try a different subject or status to see more tickets.</EmptyState>
            : <EmptyState
              title={user?.role === "customer" ? "No tickets yet" : "No tickets in this business yet"}
              action={user?.role === "customer"
                ? <Link className="button button-primary" href="/tickets/new"><Icon name="plus" />New ticket</Link>
                : undefined}
            >
              {user?.role === "customer"
                ? "Create a ticket to begin a support conversation."
                : "New support requests will appear here."}
            </EmptyState>
          : null}
        {!resultsLoading && items && items.length > 0 ? <TicketRows tickets={items} /> : null}
      </div>
      {pagination
        ? <div className="panel-footer ticket-pagination">
          <span role="status" aria-live="polite">
            {resultsLoading
              ? <Skeleton className="skeleton-ticket-summary" />
              : <>{pagination.total_items} {pagination.total_items === 1 ? "ticket" : "tickets"} · Latest activity first</>}
          </span>
          <nav aria-label="Ticket pagination">
            <Button variant="secondary" disabled={page <= 1 || tickets.isFetching || resultsLoading} onClick={() => updatePage(page - 1)}>Previous</Button>
            <span className="ticket-page-info">{resultsLoading
              ? <Skeleton className="skeleton-ticket-page" />
              : <>Page {pagination.page} of {Math.max(1, pagination.total_pages)}</>}</span>
            <Button variant="secondary" disabled={page >= pagination.total_pages || tickets.isFetching || resultsLoading} onClick={() => updatePage(page + 1)}>Next</Button>
          </nav>
        </div>
        : null}
    </section>
  </div>;
}

function TicketRows({ tickets }: { tickets: TicketListItem[] }) {
  return <>
    <div className="table-wrap ticket-table">
      <table>
        <thead>
          <tr>
            <th scope="col">Subject</th>
            <th scope="col">Status</th>
            <th scope="col">Priority</th>
            <th scope="col">Assigned to</th>
            <th scope="col">Latest activity</th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((ticket) => <tr key={ticket.id}>
            <td>
              <span className="ticket-subject-row">
                <Link href={`/tickets/${encodeURIComponent(ticket.id)}`}>{ticket.subject}</Link>
                {(ticket.unread_count ?? 0) > 0 && <UnreadBadge count={ticket.unread_count ?? 0} />}
              </span>
              <span className="cell-secondary">{ticket.category}</span>
            </td>
            <td>
              <Badge kind={ticket.status}>{statusLabels[ticket.status]}</Badge>
            </td>
            <td>
              <span className={`priority priority-${ticket.priority}`}>
                <span aria-hidden="true" />
                {ticket.priority}
              </span>
            </td>
            <td>
              {ticket.assigned_agent
                ? <span className="person-cell">
                  <Avatar name={ticket.assigned_agent.name} small />
                  {ticket.assigned_agent.name}
                </span>
                : <span className="unassigned">Unassigned</span>}
            </td>
            <td className="date-cell">
              <time dateTime={ticket.updated_at}>{formatDateTime(ticket.updated_at)}</time>
            </td>
          </tr>)}
        </tbody>
      </table>
    </div>
    <ul className="ticket-list-mobile">
      {tickets.map((ticket) => <li key={ticket.id}>
        <Link href={`/tickets/${encodeURIComponent(ticket.id)}`}>
          <span className="mobile-ticket-heading">
            <span>
              <span className="ticket-subject-row">
                <strong>{ticket.subject}</strong>
                {(ticket.unread_count ?? 0) > 0 && <UnreadBadge count={ticket.unread_count ?? 0} />}
              </span>
              <span className="cell-secondary">{ticket.category}</span>
            </span>
            <Icon name="arrowRight" />
          </span>
          <span className="badge-row">
            <Badge kind={ticket.status}>{statusLabels[ticket.status]}</Badge>
            <span className={`priority priority-${ticket.priority}`}>
              <span aria-hidden="true" />
              {ticket.priority}
            </span>
          </span>
          <span className="mobile-ticket-meta">
            <span>{ticket.assigned_agent?.name ?? "Unassigned"}</span>
            <time dateTime={ticket.updated_at}>{formatDateTime(ticket.updated_at)}</time>
          </span>
        </Link>
      </li>)}
    </ul>
  </>;
}

function UnreadBadge({ count }: { count: number }) {
  return <span className="unread-badge" aria-label={`${count} unread messages`}>{count}</span>;
}
