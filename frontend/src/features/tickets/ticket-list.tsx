"use client";

import { Alert, Badge, Button, EmptyState, Field, Select, Skeleton } from "@/components/ui";
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
  const tickets = useQuery({ queryKey: queryKeys.tickets(status), queryFn: () => apiRequest<TicketListItem[]>(`/tickets${status ? `?status=${encodeURIComponent(status)}` : ""}`) });
  function updateStatus(value: string) {
    const next = new URLSearchParams(searchParams.toString());
    if (value) next.set("status", value); else next.delete("status");
    router.replace(`/tickets${next.size ? `?${next}` : ""}`);
  }
  return <div className="page-stack"><header className="page-header"><div><h1>{user?.role === "customer" ? "My tickets" : "Tickets"}</h1><p>{user?.role === "customer" ? "Track your support conversations and their progress." : "Review support requests for your business."}</p></div>{user?.role === "customer" ? <Link className="button button-primary" href="/tickets/new">New ticket</Link> : null}</header><div className="filter-row"><Field label="Status" name="status-filter"><Select id="status-filter" value={status ?? ""} onChange={(event) => updateStatus(event.target.value)}><option value="">All statuses</option>{statuses.map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}</Select></Field>{tickets.isFetching && !tickets.isLoading ? <span className="updating" role="status">Updating…</span> : null}</div>{tickets.isError ? <Alert tone="error">Tickets could not be loaded. Check your connection and try again. <Button variant="quiet" onClick={() => void tickets.refetch()}>Retry</Button></Alert> : null}{tickets.isLoading ? <TicketListSkeleton /> : null}{tickets.data && tickets.data.length === 0 ? status ? <EmptyState title="No tickets match this status" action={<Button variant="secondary" onClick={() => updateStatus("")}>Clear filter</Button>}>Try another status to see more tickets.</EmptyState> : <EmptyState title={user?.role === "customer" ? "No tickets yet" : "No tickets in this business yet"} action={user?.role === "customer" ? <Link className="button button-primary" href="/tickets/new">New ticket</Link> : undefined}>{user?.role === "customer" ? "Create a ticket to begin a support conversation." : "New support requests will appear here."}</EmptyState> : null}{tickets.data && tickets.data.length > 0 ? <TicketRows tickets={tickets.data} /> : null}</div>;
}

function TicketRows({ tickets }: { tickets: TicketListItem[] }) {
  return <><div className="table-wrap ticket-table"><table><thead><tr><th>Subject</th><th>Status</th><th>Priority</th><th>Assigned to</th><th>Latest activity</th></tr></thead><tbody>{tickets.map((ticket) => <tr key={ticket.id}><td><Link href={`/tickets/${encodeURIComponent(ticket.id)}`}>{ticket.subject}</Link><span>{ticket.category}</span></td><td><Badge kind={ticket.status}>{statusLabels[ticket.status]}</Badge></td><td><Badge kind={ticket.priority}>{ticket.priority[0].toUpperCase() + ticket.priority.slice(1)}</Badge></td><td>{ticket.assigned_agent?.name ?? "Unassigned"}</td><td><time dateTime={ticket.updated_at}>{formatDateTime(ticket.updated_at)}</time></td></tr>)}</tbody></table></div><ul className="ticket-list-mobile">{tickets.map((ticket) => <li key={ticket.id}><Link href={`/tickets/${encodeURIComponent(ticket.id)}`}><strong>{ticket.subject}</strong><span className="badge-row"><Badge kind={ticket.status}>{statusLabels[ticket.status]}</Badge><Badge kind={ticket.priority}>{ticket.priority}</Badge></span><span>{ticket.assigned_agent?.name ?? "Unassigned"} · <time dateTime={ticket.updated_at}>{formatDateTime(ticket.updated_at)}</time></span></Link></li>)}</ul></>;
}

function TicketListSkeleton() { return <div className="table-wrap" role="status" aria-label="Loading tickets"><div className="skeleton-list">{Array.from({ length: 5 }, (_, index) => <Skeleton key={index} className="skeleton-row" />)}</div></div>; }
