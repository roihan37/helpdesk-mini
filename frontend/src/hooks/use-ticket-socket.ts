"use client";

import { getAccessToken, refreshAccessToken } from "@/lib/api";
import { mergeMessages } from "@/lib/domain";
import { WS_URL } from "@/lib/env";
import { queryKeys } from "@/lib/query";
import type { Message, TicketDetail, TicketListItem, WebSocketEvent } from "@/types/api";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

export type ConnectionState = "connecting" | "connected" | "reconnecting" | "offline" | "unauthorized";

function parseEvent(raw: string): WebSocketEvent | null {
  try {
    const value = JSON.parse(raw) as { type?: unknown; data?: unknown };
    if (!value || typeof value !== "object" || typeof value.type !== "string" || !value.data || typeof value.data !== "object") return null;
    if (value.type === "message.created" || value.type === "ticket.status_changed" || value.type === "error") return value as WebSocketEvent;
  } catch { return null; }
  return null;
}

export function useTicketSocket(ticketId: string, enabled: boolean, currentUserId: string) {
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingBody = useRef<string | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [connectKey, setConnectKey] = useState(0);

  useEffect(() => {
    let active = true;
    async function connect() {
      if (!enabled || !active) return;
      let token = getAccessToken();
      if (!token) {
        try { token = await refreshAccessToken(); }
        catch { if (active) setConnection("unauthorized"); return; }
      }
      if (!active) return;
      setConnection(retryRef.current ? "reconnecting" : "connecting");
      const socket = new WebSocket(`${WS_URL}/ws/tickets/${encodeURIComponent(ticketId)}?token=${encodeURIComponent(token)}`);
      socketRef.current = socket;
      socket.onopen = () => {
        if (!active) { socket.close(); return; }
        retryRef.current = 0; setConnection("connected"); setError("");
        void Promise.all([queryClient.invalidateQueries({ queryKey: queryKeys.messages(ticketId) }), queryClient.invalidateQueries({ queryKey: queryKeys.ticket(ticketId) })]);
      };
      socket.onmessage = (messageEvent) => {
        const event = parseEvent(String(messageEvent.data));
        if (!event) return;
        if (event.type === "message.created" && event.data.ticket_id === ticketId) {
          queryClient.setQueryData<Message[]>(queryKeys.messages(ticketId), (current = []) => mergeMessages(current, [event.data]));
          queryClient.setQueryData<TicketDetail>(queryKeys.ticket(ticketId), (current) => current ? { ...current, updated_at: event.data.created_at } : current);
          queryClient.setQueriesData<TicketListItem[]>({ queryKey: ["tickets"] }, (current) => current?.map((ticket) => ticket.id === ticketId ? { ...ticket, updated_at: event.data.created_at } : ticket));
          if (event.data.sender_id === currentUserId && event.data.body === pendingBody.current) { pendingBody.current = null; setSending(false); }
        } else if (event.type === "ticket.status_changed" && event.data.ticket_id === ticketId) {
          queryClient.setQueryData<TicketDetail>(queryKeys.ticket(ticketId), (current) => current ? { ...current, status: event.data.status, updated_at: event.data.updated_at } : current);
          queryClient.setQueriesData<TicketListItem[]>({ queryKey: ["tickets"] }, (current) => current?.map((ticket) => ticket.id === ticketId ? { ...ticket, status: event.data.status, updated_at: event.data.updated_at } : ticket));
        } else if (event.type === "error") {
          setError(event.data.message); setSending(false); pendingBody.current = null;
          if (event.data.code === "TICKET_CLOSED") void queryClient.invalidateQueries({ queryKey: queryKeys.ticket(ticketId) });
        }
      };
      socket.onclose = (closeEvent) => {
        if (socketRef.current === socket) socketRef.current = null;
        setSending(false); pendingBody.current = null;
        if (!active || closeEvent.code === 1000) return;
        if (closeEvent.code === 1008) { setConnection("unauthorized"); setError("Session expired or access unavailable."); return; }
        if (retryRef.current >= 3) { setConnection("offline"); setError("Connection lost. Messages cannot be sent."); return; }
        retryRef.current += 1; setConnection("reconnecting");
        timerRef.current = setTimeout(() => void connect(), 2 ** (retryRef.current - 1) * 1000);
      };
      socket.onerror = () => { /* onclose owns recovery and avoids exposing the token-bearing URL. */ };
    }
    if (enabled) void connect();
    return () => { active = false; if (timerRef.current) clearTimeout(timerRef.current); socketRef.current?.close(1000); socketRef.current = null; };
  }, [connectKey, currentUserId, enabled, queryClient, ticketId]);

  function send(body: string) {
    const clean = body.trim();
    if (!clean || clean.length > 5000 || socketRef.current?.readyState !== WebSocket.OPEN || sending) return false;
    pendingBody.current = clean; setSending(true); setError("");
    socketRef.current.send(JSON.stringify({ type: "message.send", body: clean }));
    return true;
  }
  return { connection, error, sending, send, retry: () => { retryRef.current = 0; setError(""); setConnectKey((key) => key + 1); } };
}
