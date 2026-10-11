"use client";

import { Icon } from "@/components/icon";
import { Alert, Avatar, Badge, Button, EmptyState, Field, Select, Skeleton } from "@/components/ui";
import { useAuth } from "@/features/auth/auth-provider";
import { apiRequest } from "@/lib/api";
import { formatDateTime, statusLabels } from "@/lib/domain";
import { queryKeys } from "@/lib/query";
import type { TicketListItem, TicketStatus } from "@/types/api";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

const statuses: TicketStatus[] = ["open", "in_progress", "resolved", "closed"];

export function TicketListPage() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const rawStatus = searchParams.get("status");
  const status = statuses.includes(rawStatus as TicketStatus) ? rawStatus as TicketStatus : undefined;
  const tickets = useQuery({
    queryKey: queryKeys.tickets(status),
    queryFn: () => apiRequest<TicketListItem[]>(`/tickets${status ? `?status=${encodeURIComponent(status)}` : ""}`)
  });
  function updateStatus(value: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set("status", value); else next.delete("status");
    router.replace(`/tickets${next.size ? `?${next}` : ""}`);
  }
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
    <section className="data-panel" aria-label="Ticket list">
      <div className="panel-toolbar">
        <div className="panel-heading">
          <Icon name="tickets" />
          <h2>{status ? statusLabels[status] : "All tickets"}</h2>
          {tickets.data ? <span className="count-label">{tickets.data.length}</span> : null}
        </div>
        <div className="filter-row">
          <Field label="Status" name="status-filter">
            <Select
              id="status-filter"
              value={status ?? ""}
              onChange={(event) => updateStatus(event.target.value)}
            >
              <option value="">All statuses</option>
              {statuses.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}
            </Select>
          </Field>
          {tickets.isFetching && !tickets.isLoading
            ? <span className="updating" role="status">Updating…</span>
            : null}
        </div>
      </div>
      {tickets.isError
        ? <div className="panel-feedback">
          <Alert tone="error">Tickets could not be loaded. Check your connection and try again. <Button variant="quiet" onClick={() => void tickets.refetch()}>Retry</Button></Alert>
        </div>
        : null}
      {tickets.isLoading ? <TicketListSkeleton /> : null}
      {tickets.data && tickets.data.length === 0
        ? status
          ? <EmptyState
            title="No tickets match this status"
            action={<Button variant="secondary" onClick={() => updateStatus("")}>Clear filter</Button>}
          >Try another status to see more tickets.</EmptyState>
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
      {tickets.data && tickets.data.length > 0 ? <TicketRows tickets={tickets.data} /> : null}
      {tickets.data && tickets.data.length > 0
        ? <div className="panel-footer">
          <span>{tickets.data.length} {tickets.data.length === 1 ? "ticket" : "tickets"}{status ? ` · ${statusLabels[status]}` : ""}</span>
          <span>Latest activity first</span>
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
              <Link href={`/tickets/${encodeURIComponent(ticket.id)}`}>{ticket.subject}</Link>
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
              <strong>{ticket.subject}</strong>
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

function TicketListSkeleton() {
  return <div className="table-wrap" role="status" aria-label="Loading tickets">
    <div className="skeleton-list">
      {Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="skeleton-row" />)}
    </div>
  </div>;
}
