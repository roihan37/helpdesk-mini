"use client";

import { getAccessToken, onAccessTokenChanged, refreshAccessToken } from "@/lib/api";
import { WS_URL } from "@/lib/env";
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { startTicketListSubscription, type ListConnectionState } from "./ticket-list-live-socket";

const notices = {
  "ticket.created": "New ticket activity. Your list is updating.",
  "ticket.message_created": "New message activity. Your list is updating.",
  "ticket.status_changed": "Ticket status changed. Your list is updating.",
  "ticket.assignment_changed": "Ticket assignment changed. Your list is updating."
};
const LiveContext = createContext<{ notice: string; connection: ListConnectionState }>({ notice: "", connection: "connecting" });

export function TicketListLiveProvider({ userId, children }: { userId: string | null; children: ReactNode }) {
  const queryClient = useQueryClient();
  const [activity, setActivity] = useState({ userId: "", notice: "" });
  const [connection, setConnection] = useState<ListConnectionState>("connecting");
  useEffect(() => {
    if (!userId) return;
    let noticeTimer: ReturnType<typeof setTimeout> | null = null;
    const stop = startTicketListSubscription({
      getToken: getAccessToken,
      refreshToken: refreshAccessToken,
      subscribeToken: onAccessTokenChanged,
      connect: (token) => new WebSocket(`${WS_URL}/ws/tickets?token=${encodeURIComponent(token)}`),
      schedule: (callback, delay) => {
        const timer = setTimeout(callback, delay);
        return () => clearTimeout(timer);
      },
      now: Date.now,
      invalidate: () => queryClient.invalidateQueries({ queryKey: ["tickets"] }, { cancelRefetch: true }),
      stateChanged: setConnection,
      notify: (event) => {
        if (noticeTimer) clearTimeout(noticeTimer);
        setActivity({ userId, notice: notices[event.type] });
        noticeTimer = setTimeout(() => setActivity({ userId, notice: "" }), 4000);
      }
    });
    return () => {
      stop();
      if (noticeTimer) clearTimeout(noticeTimer);
    };
  }, [queryClient, userId]);
  return <LiveContext.Provider value={{ notice: activity.userId === userId ? activity.notice : "", connection }}>{children}</LiveContext.Provider>;
}

export function useTicketListLive() {
  return useContext(LiveContext);
}
