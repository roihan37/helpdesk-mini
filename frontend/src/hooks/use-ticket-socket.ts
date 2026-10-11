"use client";

import { getAccessToken, onAccessTokenChanged, refreshAccessToken } from "@/lib/api";
import { applyReadReceipts, mergeMessages, sequenceAtMost } from "@/lib/domain";
import { WS_URL } from "@/lib/env";
import { queryKeys } from "@/lib/query";
import type { Message, MessageReadData, MessageReader, TicketDetail, WebSocketEvent } from "@/types/api";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

export type ConnectionState = "connecting" | "connected" | "reconnecting" | "offline" | "unauthorized";

function parseEvent(raw: string): WebSocketEvent | null {
  try {
    const value = JSON.parse(raw) as {
      type?: unknown;
      data?: unknown
    };
    if (!value || typeof value !== "object" || typeof value.type !== "string" || !value.data || typeof value.data !== "object") return null;
    if (value.type === "message.created" || value.type === "ticket.status_changed" || value.type === "error") return value as WebSocketEvent;
    const data = value.data as Record<string, unknown>;
    const validReader = typeof data.ticket_id === "string" && typeof data.user_id === "string" &&
      typeof data.name === "string" && (data.role === "agent" || data.role === "customer");
    if (validReader && (value.type === "typing.start" || value.type === "typing.stop")) return value as WebSocketEvent;
    if (validReader && value.type === "message.read" && typeof data.last_read_sequence === "string" &&
      /^[1-9]\d{0,18}$/.test(data.last_read_sequence)) return value as WebSocketEvent;
  } catch {
    return null;
  }
  return null;
}

export function useTicketSocket(ticketId: string, enabled: boolean, currentUserId: string, canSend = false, messages: Message[] = []) {
  const queryClient = useQueryClient();
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingBody = useRef<string | null>(null);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [connectKey, setConnectKey] = useState(0);
  const [authToken, setAuthToken] = useState(getAccessToken);
  const [typingUsers, setTypingUsers] = useState<MessageReader[]>([]);
  const typingTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const outgoingTyping = useRef(false);
  const lastTypingStart = useRef(-Infinity);
  const receipts = useRef(new Map<string, MessageReadData>());
  const refreshedForClose = useRef(false);

  const stopTyping = useCallback(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = null;
    if (outgoingTyping.current && socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: "typing.stop" }));
    }
    outgoingTyping.current = false;
  }, []);

  const clearTyping = useCallback(() => {
    typingTimers.current.forEach(clearTimeout);
    typingTimers.current.clear();
    setTypingUsers([]);
  }, []);

  useEffect(() => onAccessTokenChanged(setAuthToken), []);

  useEffect(() => {
    receipts.current.clear();
    refreshedForClose.current = false;
    lastTypingStart.current = -Infinity;
  }, [ticketId, currentUserId]);

  useEffect(() => {
    // Reapply committed boundaries when a history fetch or a delayed message
    // races a receipt event. This is local cache reconciliation, not polling.
    if (!getAccessToken()) return;
    const updated = applyReadReceipts(messages, receipts.current.values(), currentUserId);
    if (updated !== messages) queryClient.setQueryData(queryKeys.messages(ticketId), updated);
  }, [messages, currentUserId, queryClient, ticketId]);

  useEffect(() => {
    if (!canSend) stopTyping();
  }, [canSend, stopTyping]);

  useEffect(() => {
    function onVisibility() {
      if (document.visibilityState !== "visible") stopTyping();
    }
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", stopTyping);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", stopTyping);
    };
  }, [stopTyping]);

  useEffect(() => {
    let active = true;
    setSending(false);
    pendingBody.current = null;
    async function connect() {
      if (!enabled || !active) return;
      const token = getAccessToken();
      if (!token || !currentUserId) {
        setConnection("unauthorized");
        return;
      }
      setConnection(retryRef.current ? "reconnecting" : "connecting");
      const socket = new WebSocket(`${WS_URL}/ws/tickets/${encodeURIComponent(ticketId)}?token=${encodeURIComponent(token)}`);
      socketRef.current = socket;
      socket.onopen = () => {
        if (!active) {
          socket.close();
          return;
        }
        retryRef.current = 0;
        refreshedForClose.current = false;
        setConnection("connected");
        setError("");
        void Promise.all([
          queryClient.invalidateQueries({ queryKey: queryKeys.messages(ticketId) }),
          queryClient.invalidateQueries({ queryKey: queryKeys.ticket(ticketId) })
        ]);
      };
      socket.onmessage = (messageEvent) => {
        if (!active || socketRef.current !== socket || getAccessToken() !== token) return;
        const event = parseEvent(String(messageEvent.data));
        if (!event) return;
        if (event.type === "message.created" && event.data.ticket_id === ticketId) {
          queryClient.setQueryData<Message[]>(
            queryKeys.messages(ticketId),
            (current = []) => applyReadReceipts(mergeMessages(current, [event.data]), receipts.current.values(), currentUserId)
          );
          queryClient.setQueryData<TicketDetail>(
            queryKeys.ticket(ticketId),
            (current) => current ? { ...current, updated_at: event.data.created_at } : current
          );
          if (event.data.sender_id === currentUserId && event.data.body === pendingBody.current) {
            pendingBody.current = null;
            setSending(false);
          }
        } else if (event.type === "ticket.status_changed" && event.data.ticket_id === ticketId) {
          queryClient.setQueryData<TicketDetail>(
            queryKeys.ticket(ticketId),
            (current) => current ? { ...current, status: event.data.status, updated_at: event.data.updated_at } : current
          );
          if (event.data.status === "closed") {
            stopTyping();
            clearTyping();
          }
        } else if ((event.type === "typing.start" || event.type === "typing.stop") &&
          event.data.ticket_id === ticketId && event.data.user_id !== currentUserId) {
          const reader = event.data;
          const previous = typingTimers.current.get(reader.user_id);
          if (previous) clearTimeout(previous);
          typingTimers.current.delete(reader.user_id);
          if (event.type === "typing.stop") {
            setTypingUsers((current) => current.filter((user) => user.user_id !== reader.user_id));
          } else {
            const ticket = queryClient.getQueryData<TicketDetail>(queryKeys.ticket(ticketId));
            if (ticket?.status === "closed") return;
            setTypingUsers((current) => [...current.filter((user) => user.user_id !== reader.user_id), reader]);
            typingTimers.current.set(reader.user_id, setTimeout(() => {
              typingTimers.current.delete(reader.user_id);
              setTypingUsers((current) => current.filter((user) => user.user_id !== reader.user_id));
            }, 6000));
          }
        } else if (event.type === "message.read" && event.data.ticket_id === ticketId && event.data.user_id !== currentUserId) {
          const previous = receipts.current.get(event.data.user_id);
          if (!previous || sequenceAtMost(previous.last_read_sequence, event.data.last_read_sequence)) {
            receipts.current.set(event.data.user_id, event.data);
            queryClient.setQueryData<Message[]>(queryKeys.messages(ticketId), (current = []) =>
              applyReadReceipts(current, receipts.current.values(), currentUserId));
          }
        } else if (event.type === "error") {
          setError(event.data.message);
          setSending(false);
          pendingBody.current = null;
          if (event.data.code === "TICKET_CLOSED") {
            stopTyping();
            clearTyping();
            void queryClient.invalidateQueries({ queryKey: queryKeys.ticket(ticketId) });
          }
        }
      };
      socket.onclose = (closeEvent) => {
        if (!active || socketRef.current !== socket) return;
        stopTyping();
        clearTyping();
        if (socketRef.current === socket) socketRef.current = null;
        setSending(false);
        pendingBody.current = null;
        if (!active || closeEvent.code === 1000) return;
        if (closeEvent.code === 1008) {
          if (!refreshedForClose.current && getAccessToken()) {
            refreshedForClose.current = true;
            setConnection("reconnecting");
            void refreshAccessToken().then((refreshed) => {
              // JWT refresh can return the same access token within one second.
              if (active && refreshed === token) setConnectKey((key) => key + 1);
            }).catch(() => {
              if (active) setConnection("unauthorized");
            });
            return;
          }
          setConnection("unauthorized");
          setError("Session expired or access unavailable.");
          return;
        }
        if (retryRef.current >= 3) {
          setConnection("offline");
          setError("Connection lost. Messages cannot be sent.");
          return;
        }
        retryRef.current += 1;
        setConnection("reconnecting");
        timerRef.current = setTimeout(() => void connect(), 2 ** (retryRef.current - 1) * 1000);
      };
      socket.onerror = () => { /* onclose owns recovery and avoids exposing the token-bearing URL. */ };
    }
    if (enabled) void connect();
    return () => {
      active = false;
      if (timerRef.current) clearTimeout(timerRef.current);
      stopTyping();
      clearTyping();
      if (!getAccessToken()) receipts.current.clear();
      socketRef.current?.close(1000);
      socketRef.current = null;
    };
  }, [authToken, clearTyping, connectKey, currentUserId, enabled, queryClient, stopTyping, ticketId]);

  function typing(hasText: boolean) {
    if (!hasText || !canSend || !getAccessToken() || document.visibilityState !== "visible" ||
      socketRef.current?.readyState !== WebSocket.OPEN || sending) {
      stopTyping();
      return;
    }
    const now = performance.now();
    if (now - lastTypingStart.current >= 2000) {
      socketRef.current.send(JSON.stringify({ type: "typing.start" }));
      outgoingTyping.current = true;
      lastTypingStart.current = now;
    }
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(stopTyping, 2500);
  }

  function send(body: string) {
    const clean = body.trim();
    if (!canSend || !getAccessToken() || !clean || clean.length > 5000 || socketRef.current?.readyState !== WebSocket.OPEN || sending) return false;
    stopTyping();
    pendingBody.current = clean;
    setSending(true);
    setError("");
    socketRef.current.send(JSON.stringify({ type: "message.send", body: clean }));
    return true;
  }
  return {
    connection,
    error,
    sending,
    send,
    typing,
    stopTyping,
    typingUsers,
    retry: () => {
      retryRef.current = 0;
      setError("");
      setConnectKey((key) => key + 1);
    }
  };
}
