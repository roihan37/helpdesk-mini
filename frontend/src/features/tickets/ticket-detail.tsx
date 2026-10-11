"use client";

import { Icon } from "@/components/icon";
import { Alert, Avatar, Badge, Button, EmptyState, LoadingPanel, Select, Textarea } from "@/components/ui";
import { useAuth } from "@/features/auth/auth-provider";
import { ApiError, apiRequest, friendlyError, onAccessTokenChanged } from "@/lib/api";
import { formatDateTime, mergeMessages, nextTicketStatus, roleLabels, statusLabels } from "@/lib/domain";
import { queryKeys } from "@/lib/query";
import type { Message, TicketDetail, TicketStatus, User } from "@/types/api";
import { type ConnectionState, useTicketSocket } from "@/hooks/use-ticket-socket";
import { useTicketRead } from "@/hooks/use-ticket-read";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import Image from "next/image";
import { ChatImage } from "@/features/tickets/chat-image";
import { useParams } from "next/navigation";
import { type FormEvent, useEffect, useRef, useState } from "react";

export function TicketDetailPage() {
  const params = useParams<{ id: string }>();
  const ticketId = params.id;
  const ticket = useQuery({
    queryKey: queryKeys.ticket(ticketId),
    queryFn: () => apiRequest<TicketDetail>(`/tickets/${encodeURIComponent(ticketId)}`),
    enabled: Boolean(ticketId)
  });
  const messages = useQuery({
    queryKey: queryKeys.messages(ticketId),
    queryFn: () => apiRequest<Message[]>(`/tickets/${encodeURIComponent(ticketId)}/messages`),
    enabled: Boolean(ticket.data)
  });
  if (ticket.isLoading || (ticket.data && messages.isLoading)) return <LoadingPanel label="Loading ticket and conversation…" />;
  if (ticket.error instanceof ApiError && ticket.error.status === 404) return <NotFound />;
  if (ticket.isError) return <div className="centered-state">
    <Alert tone="error">This ticket could not be loaded. Try again.</Alert>
    <Button onClick={() => void ticket.refetch()}>Retry</Button>
  </div>;
  if (!ticket.data) return null;
  return <TicketWorkspace
    key={ticketId}
    ticket={ticket.data}
    messages={messages.data ?? []}
    messagesError={messages.isError}
    messagesReady={messages.isSuccess && !messages.isFetching && !messages.isError}
    retryMessages={() => void messages.refetch()}
  />;
}

function NotFound() {
  return <div className="centered-state">
    <EmptyState
      title="Ticket not found or unavailable"
      action={<Link className="button button-secondary" href="/tickets">Back to tickets</Link>}
    >The ticket may not exist or you may not have access.</EmptyState>
  </div>;
}

function TicketWorkspace({ ticket, messages, messagesError, messagesReady, retryMessages }: {
  ticket: TicketDetail;
  messages: Message[];
  messagesError: boolean;
  messagesReady: boolean;
  retryMessages: () => void
}) {
  const { user } = useAuth();
  const canSend = Boolean(user && user.role !== "admin" && ticket.status !== "closed");
  const socket = useTicketSocket(ticket.id, !messagesError, user?.id ?? "", canSend, messages);
  return <div className="page-stack ticket-detail">
    <header className="ticket-header">
      <Link href="/tickets" className="back-link"><Icon name="arrowLeft" />Back to tickets</Link>
      <div className="ticket-title-row">
        <div>
          <h1>{ticket.subject}</h1>
          <div className="badge-row">
            <Badge kind={ticket.status}>{statusLabels[ticket.status]}</Badge>
            <span className={`priority priority-${ticket.priority}`}><span />{ticket.priority} priority</span>
            <span className="ticket-category">{ticket.category}</span>
          </div>
        </div>
        <ConnectionStatus state={socket.connection} />
      </div>
    </header>
    <div className="ticket-grid">
      <Conversation
        ticket={ticket}
        messages={messages}
        currentUserId={user?.id ?? ""}
        role={user?.role}
        canSend={canSend}
        socket={socket}
        messagesError={messagesError}
        messagesReady={messagesReady}
        retryMessages={retryMessages}
      />
      <TicketDetails ticket={ticket} />
    </div>
  </div>;
}

function ConnectionStatus({ state }: { state: ConnectionState }) {
  const labels: Record<ConnectionState, string> = {
    connecting: "Connecting…",
    connected: "Live",
    reconnecting: "Reconnecting…",
    offline: "Connection lost",
    unauthorized: "Session expired"
  };
  return <span className={`connection connection-${state}`} role="status">
    <span aria-hidden="true" />
    {labels[state]}
  </span>;
}

function Conversation({ ticket, messages, currentUserId, role, canSend, socket, messagesError, messagesReady, retryMessages }: {
  ticket: TicketDetail;
  messages: Message[];
  currentUserId: string;
  role?: string;
  canSend: boolean;
  socket: ReturnType<typeof useTicketSocket>;
  messagesError: boolean;
  messagesReady: boolean;
  retryMessages: () => void
}) {
  const [draft, setDraft] = useState("");
  const queryClient = useQueryClient();
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const upload = useRef<AbortController | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const previousCount = useRef(0);
  const read = useTicketRead(ticket.id, currentUserId, messages, messagesReady, listRef);
  const [showNew, setShowNew] = useState(false);
  useEffect(() => {
    if (!image) { setPreview(""); return; }
    const url = URL.createObjectURL(image);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [image]);
  useEffect(() => {
    const unsubscribe = onAccessTokenChanged((token) => {
      if (token === null) { upload.current?.abort(); setImage(null); setDraft(""); }
    });
    return () => { upload.current?.abort(); unsubscribe(); };
  }, []);
  useEffect(() => {
    if (!canSend) { upload.current?.abort(); setImage(null); socket.stopTyping(); }
  }, [canSend, socket.stopTyping]);
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const nearBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 96;
    if (previousCount.current === 0 || nearBottom) list.scrollTop = list.scrollHeight;
    else if (messages.length > previousCount.current) setShowNew(true);
    previousCount.current = messages.length;
  }, [messages.length]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSend || uploading || upload.current || socket.sending || socket.connection !== "connected") return;
    if (!image) { if (socket.send(draft)) setDraft(""); return; }
    const controller = new AbortController();
    upload.current = controller;
    const body = new FormData();
    body.append("image", image);
    body.append("caption", draft.trim());
    setUploading(true);
    setUploadError("");
    socket.stopTyping();
    try {
      const message = await apiRequest<Message>(`/tickets/${encodeURIComponent(ticket.id)}/messages/attachment`, {
        method: "POST", body, signal: controller.signal
      });
      if (controller.signal.aborted) return;
      queryClient.setQueryData<Message[]>(queryKeys.messages(ticket.id), (current = []) => mergeMessages(current, [message]));
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      void queryClient.invalidateQueries({ queryKey: queryKeys.ticket(ticket.id) });
      setImage(null);
      setDraft("");
    } catch (error) {
      if (!controller.signal.aborted) {
        setUploadError(`${friendlyError(error, "Upload failed.")} Check the conversation before retrying if the connection was interrupted.`);
        void queryClient.invalidateQueries({ queryKey: queryKeys.messages(ticket.id) });
      }
    } finally {
      if (upload.current === controller) {
        upload.current = null;
        setUploading(false);
      }
    }
  }
  function jumpToNew() {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
    setShowNew(false);
  }
  return <section className="conversation" aria-labelledby="conversation-title">
    <header className="conversation-heading">
      <div className="panel-heading">
        <Icon name="message" />
        <h2 id="conversation-title">Conversation</h2>
      </div>
      <span>{ticket.status === "closed" || role === "admin" ? "Read-only" : "Ticket chat"}</span>
    </header>
    {messagesError
      ? <div className="panel-feedback">
        <Alert tone="error">Messages could not be loaded. <Button variant="quiet" onClick={retryMessages}>Retry</Button></Alert>
      </div>
      : null}
    {read.error && !messagesError ? <div className="panel-feedback">
      <Alert tone="warning">{read.error} <Button variant="quiet" onClick={read.retry}>Retry</Button></Alert>
    </div> : null}
    <div className="message-list" ref={listRef}>
      {messages.length === 0 && !messagesError
        ? <EmptyState title="No messages yet">Conversation history will appear here.</EmptyState>
        : messages.map((message) => <article
          key={message.id}
          className={message.sender_id === currentUserId ? "message message-own" : "message"}
        >
          <Avatar name={message.sender_name} small />
          <div className="message-content">
            <header>
              <strong>{message.sender_name}</strong>
              <span className="message-role">{roleLabels[message.sender_role]}</span>
            </header>
            {message.attachment ? <div className="message-bubble">
              <ChatImage ticketId={ticket.id} attachment={message.attachment} />
              {message.body ? <p className="attachment-caption">{message.body}</p> : null}
            </div> : message.body ? <p className="message-bubble">{message.body}</p> : null}
            <div className="message-meta">
              <time dateTime={message.created_at}>{formatDateTime(message.created_at)}</time>
              {message.sender_id === currentUserId ? <span className="message-receipt">
                {message.read_by?.length
                  ? `Seen by ${message.read_by.map((reader) => reader.name).join(", ")}`
                  : "Sent"}
              </span> : null}
            </div>
          </div>
        </article>)}
    </div>
    <div className="typing-indicator" role="status" aria-live="polite" aria-atomic="true">
      {ticket.status !== "closed" && socket.typingUsers.length > 0
        ? `${socket.typingUsers.map((user) => user.name).join(", ")} ${socket.typingUsers.length === 1 ? "is" : "are"} typing…`
        : ""}
    </div>
    {showNew
      ? <Button className="new-messages" variant="secondary" onClick={jumpToNew}>New messages</Button>
      : null}
    <div className="composer">
      {uploadError ? <Alert tone="error">{uploadError}</Alert> : null}
      {uploading ? <div role="status" className="attachment-progress"><progress aria-label="Uploading image" /> Uploading image…</div> : null}
      {socket.error
        ? <Alert tone="error">
          {socket.error}
          {socket.connection === "offline"
            ? <Button variant="quiet" onClick={socket.retry}>Retry</Button>
            : null}
        </Alert>
        : null}
      {ticket.status === "closed"
        ? <p className="read-only-note"><Icon name="lock" />This ticket is closed. Conversation history is read-only.</p>
        : role === "admin"
          ? <p className="read-only-note"><Icon name="lock" />Admins can review this conversation but cannot send messages.</p>
          : <form onSubmit={submit}>
            <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (!file) return;
                if (!canSend || uploading) return;
                if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024 || file.size === 0) {
                  setUploadError("Choose a JPEG, PNG, or WebP image up to 5 MB."); return;
                }
                setUploadError(""); setImage(file);
              }} />
            {image ? <div className="attachment-preview">
              {preview ? <Image src={preview} alt="Selected image preview" width={80} height={80} unoptimized /> : null}
              <span>{image.name}</span>
              <Button type="button" variant="quiet" disabled={uploading} onClick={() => setImage(null)}>Remove image</Button>
            </div> : null}
            <label htmlFor="message-body">Reply to conversation</label>
            <Textarea
              id="message-body"
              placeholder={image ? "Add an optional caption…" : "Write a message…"}
              aria-describedby="message-help"
              value={draft}
              onChange={(event) => {
                setDraft(event.target.value);
                socket.typing(Boolean(event.target.value.trim()));
              }}
              onBlur={socket.stopTyping}
              maxLength={5000}
              rows={3}
              disabled={!canSend || socket.connection !== "connected" || socket.sending || uploading}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
            />
            <div className="composer-footer">
              <span id="message-help">
                {socket.connection === "connected"
                  ? "Enter to send · Shift+Enter for a new line"
                  : "Messages are available when the connection is live."}
              </span>
              <Button type="button" variant="secondary" onClick={() => fileInput.current?.click()}
                disabled={!canSend || socket.connection !== "connected" || socket.sending || uploading}>Attach image</Button>
              <Button
                type="submit"
                disabled={(!draft.trim() && !image) || !canSend || socket.connection !== "connected" || socket.sending || uploading}
              >
                <Icon name="send" />
                {socket.sending ? "Sending…" : "Send message"}
              </Button>
            </div>
          </form>}
    </div>
  </section>;
}

function TicketDetails({ ticket }: { ticket: TicketDetail }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState("");
  const agents = useQuery({
    queryKey: queryKeys.users,
    queryFn: () => apiRequest<User[]>("/users"),
    enabled: user?.role === "admin"
  });
  const updateTicket = useMutation({
    mutationFn: (payload: {
      status?: TicketStatus;
      assigned_agent_id?: string
    }) => apiRequest<TicketDetail>(
      `/tickets/${encodeURIComponent(ticket.id)}`,
      { method: "PATCH", body: JSON.stringify(payload) }
    ),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKeys.ticket(ticket.id), updated);
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      setFeedback("Ticket updated.");
    },
    onError: (error) => {
      setFeedback(error instanceof ApiError && error.status === 409
        ? "This ticket changed since you opened it. The latest details have been loaded."
        : friendlyError(error));
      void queryClient.invalidateQueries({ queryKey: queryKeys.ticket(ticket.id) });
    }
  });
  const next = user ? nextTicketStatus(user.role, ticket.status) : null;
  const canClaim = user?.role === "agent" && !ticket.assigned_agent_id;
  const canAssign = user?.role === "admin" && ticket.status !== "closed";
  const nextLabel = next === "open" ? "Reopen ticket" : next ? `Move to ${statusLabels[next]}` : null;
  function detailsContent(id: string) {
    return <div className="details-content">
      <dl>
        <div>
          <dt>Customer</dt>
          <dd>{ticket.customer.name}</dd>
        </div>
        <div>
          <dt>Category</dt>
          <dd>{ticket.category}</dd>
        </div>
        <div>
          <dt>Assigned agent</dt>
          <dd>{ticket.assigned_agent?.name ?? "Unassigned"}</dd>
        </div>
        <div>
          <dt>Created</dt>
          <dd>
            <time dateTime={ticket.created_at}>{formatDateTime(ticket.created_at)}</time>
          </dd>
        </div>
        <div>
          <dt>Latest activity</dt>
          <dd>
            <time dateTime={ticket.updated_at}>{formatDateTime(ticket.updated_at)}</time>
          </dd>
        </div>
      </dl>
      {feedback
        ? <Alert tone={feedback === "Ticket updated." ? "success" : "error"}>{feedback}</Alert>
        : null}
      {canAssign
        ? <div className="action-block">
          <label htmlFor={`assign-agent-${id}`}>Assign agent</label>
          <Select
            id={`assign-agent-${id}`}
            value={ticket.assigned_agent_id ?? ""}
            disabled={agents.isLoading || updateTicket.isPending}
            onChange={(event) => {
              if (event.target.value) updateTicket.mutate({ assigned_agent_id: event.target.value });
            }}
          >
            <option value="" disabled>Select an agent</option>
            {agents.data?.filter((person) => person.role === "agent").map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
          </Select>
          {agents.isError ? <span className="field-error">Agents could not be loaded.</span> : null}
        </div>
        : null}
      <div className="detail-actions">
        {canClaim
          ? <Button
            variant="secondary"
            disabled={updateTicket.isPending}
            onClick={() => user && updateTicket.mutate({ assigned_agent_id: user.id })}
          >
            {updateTicket.isPending ? "Updating…" : "Take ticket"}
          </Button>
          : null}
        {nextLabel
          ? <Button
            disabled={updateTicket.isPending}
            onClick={() => next && updateTicket.mutate({ status: next })}
          >
            {updateTicket.isPending ? "Updating…" : nextLabel}
          </Button>
          : null}
      </div>
    </div>;
  }
  return <aside className="ticket-aside">
    <h2 className="desktop-details">Ticket details</h2>
    <div className="desktop-details">{detailsContent("desktop")}</div>
    <details className="mobile-details">
      <summary>Ticket details and actions</summary>
      {detailsContent("mobile")}
    </details>
  </aside>;
}
