import { Skeleton } from "@/components/ui";

const rows = Array.from({ length: 5 }, (_, index) => index);

function TextLines() {
  return <div className="skeleton-stack">
    <Skeleton className="skeleton-line" />
    <Skeleton className="skeleton-line skeleton-short" />
  </div>;
}

function FieldSkeleton() {
  return <div className="skeleton-stack">
    <Skeleton className="skeleton-line skeleton-short" />
    <Skeleton className="skeleton-control" />
  </div>;
}

export function AuthSkeleton({ label, registration = false }: { label: string; registration?: boolean }) {
  return <main className="auth-page" role="status">
    <span className="sr-only">{label}</span>
    <div className={`auth-layout${registration ? " auth-layout-wide" : ""}`} aria-hidden="true">
      <Skeleton className="skeleton-brand" />
      <div className="auth-panel">
        <div className="auth-heading skeleton-stack">
          <Skeleton className="skeleton-title" />
          <Skeleton className="skeleton-line" />
        </div>
        <div className="form-stack">
          {registration ? <>
            <div className="form-section form-stack">
              <Skeleton className="skeleton-line skeleton-short" />
              <FieldSkeleton />
              <FieldSkeleton />
              <Skeleton className="skeleton-line" />
            </div>
            <div className="form-section form-stack">
              <Skeleton className="skeleton-line skeleton-short" />
              <div className="form-pair"><FieldSkeleton /><FieldSkeleton /></div>
              <FieldSkeleton />
            </div>
          </> : <><FieldSkeleton /><FieldSkeleton /></>}
          <Skeleton className="skeleton-control" />
          <Skeleton className="skeleton-line skeleton-short" />
        </div>
      </div>
    </div>
  </main>;
}

function ListSkeleton({ team = false }: { team?: boolean }) {
  const headings = team ? ["Name", "Email", "Role", "Created"] : ["Subject", "Status", "Priority", "Assigned", "Latest activity"];
  return <>
    <div className={`table-wrap ${team ? "team-table" : "ticket-table"}`} aria-hidden="true">
      <table>
        <thead><tr>{headings.map((heading) => <th key={heading}>{heading}</th>)}</tr></thead>
        <tbody>{rows.map((row) => <tr key={row}>
          <td>{team ? <div className="person-cell"><Skeleton className="skeleton-avatar" /><TextLines /></div> : <TextLines />}</td>
          <td><Skeleton className={team ? "skeleton-line" : "skeleton-badge"} /></td>
          <td><Skeleton className="skeleton-badge" /></td>
          <td>{team ? <Skeleton className="skeleton-line" /> : <div className="person-cell"><Skeleton className="skeleton-avatar" /><Skeleton className="skeleton-line" /></div>}</td>
          {!team ? <td><Skeleton className="skeleton-line" /></td> : null}
        </tr>)}</tbody>
      </table>
    </div>
    <ul className={team ? "team-list-mobile" : "ticket-list-mobile"} aria-hidden="true">
      {rows.map((row) => <li className="skeleton-mobile-row" key={row}>
        {team ? <div className="person-cell"><Skeleton className="skeleton-avatar" /><TextLines /></div> : <TextLines />}
        <div className="badge-row"><Skeleton className="skeleton-badge" />{!team ? <Skeleton className="skeleton-badge" /> : null}</div>
        <div className="mobile-ticket-meta"><Skeleton className="skeleton-line skeleton-short" /><Skeleton className="skeleton-line skeleton-short" /></div>
      </li>)}
    </ul>
  </>;
}

export function TicketListSkeleton() {
  return <div role="status">
    <span className="sr-only">Loading tickets…</span>
    <ListSkeleton />
  </div>;
}

export function TeamSkeleton() {
  return <div role="status">
    <span className="sr-only">Loading team…</span>
    <ListSkeleton team />
  </div>;
}

export function TicketDetailSkeleton() {
  return <div className="page-stack ticket-detail" role="status">
    <span className="sr-only">Loading ticket and conversation…</span>
    <div className="ticket-header" aria-hidden="true">
      <Skeleton className="skeleton-line skeleton-short" />
      <div className="ticket-title-row">
        <div className="skeleton-detail-title skeleton-stack">
          <Skeleton className="skeleton-title" />
          <div className="badge-row"><Skeleton className="skeleton-badge" /><Skeleton className="skeleton-badge" /></div>
        </div>
        <Skeleton className="skeleton-badge" />
      </div>
    </div>
    <div className="ticket-grid" aria-hidden="true">
      <div className="conversation">
        <div className="conversation-heading"><Skeleton className="skeleton-line skeleton-short" /></div>
        <div className="message-list">
          {Array.from({ length: 3 }, (_, index) => <div className={`message skeleton-message${index === 1 ? " message-own" : ""}`} key={index}>
            <Skeleton className="skeleton-avatar" />
            <div className="message-content skeleton-stack">
              <Skeleton className="skeleton-line skeleton-short" />
              <Skeleton className="skeleton-message-bubble" />
              <Skeleton className="skeleton-line skeleton-short" />
            </div>
          </div>)}
        </div>
        <div className="composer skeleton-stack">
          <Skeleton className="skeleton-composer" />
          <div className="composer-footer"><Skeleton className="skeleton-line" /><Skeleton className="skeleton-badge" /></div>
        </div>
      </div>
      <div className="ticket-aside skeleton-details">
        <Skeleton className="skeleton-line" />
        <div className="skeleton-stack skeleton-details-body">
          {rows.map((row) => <TextLines key={row} />)}
          <Skeleton className="skeleton-control" />
        </div>
      </div>
    </div>
  </div>;
}

export function WorkspaceSkeleton({ label = "Loading application…", pathname = "/tickets" }: { label?: string; pathname?: string }) {
  const detail = pathname.startsWith("/tickets/") && pathname !== "/tickets/new";
  return <div role="status">
    <span className="sr-only">{label}</span>
    <div className="sidebar skeleton-sidebar" aria-hidden="true">
      <Skeleton className="skeleton-brand" />
      <Skeleton className="skeleton-control" />
      <Skeleton className="skeleton-control" />
    </div>
    <div className="app-column" aria-hidden="true">
      <div className="topbar" aria-hidden="true"><Skeleton className="skeleton-line" /><Skeleton className="skeleton-avatar" /></div>
      <div className="main-content">
        {detail ? <TicketDetailSkeleton /> : <div className={`page-stack${pathname === "/tickets/new" ? " form-page" : ""}`}>
          <div className="page-header skeleton-stack" aria-hidden="true"><Skeleton className="skeleton-title" /><Skeleton className="skeleton-line" /></div>
          {pathname === "/tickets/new" ? <div className="form-surface form-stack" aria-hidden="true">
            <TextLines />
            <FieldSkeleton />
            <div className="form-pair"><FieldSkeleton /><FieldSkeleton /></div>
            <div className="skeleton-stack"><Skeleton className="skeleton-line skeleton-short" /><Skeleton className="skeleton-composer" /></div>
            <div className="form-actions form-surface-actions"><Skeleton className="skeleton-badge" /><Skeleton className="skeleton-badge" /></div>
          </div> : <div className="data-panel">
            <div className="panel-toolbar" aria-hidden="true"><Skeleton className="skeleton-control skeleton-filter" /></div>
            {pathname === "/admin/users" ? <TeamSkeleton /> : <TicketListSkeleton />}
          </div>}
        </div>}
      </div>
    </div>
  </div>;
}
