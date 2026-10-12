"use client";

import { getAccessToken, onAccessTokenChanged, refreshAccessToken } from "@/lib/api";
import { WS_URL } from "@/lib/env";
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { startTicketListSubscription, type ListConnectionState } from "./ticket-list-live-socket";

const notices = {
  "ticket.created": "New ticket activity",
  "ticket.message_created": "New message activity",
  "ticket.status_changed": "Ticket status changed",
  "ticket.assignment_changed": "Ticket assignment changed"
};
const LiveContext = createContext<{ notice: string; ticketIds: string[]; connection: ListConnectionState }>({ notice: "", ticketIds: [], connection: "connecting" });

export function TicketListLiveProvider({ userId, children }: { userId: string | null; children: ReactNode }) {
  const queryClient = useQueryClient();
  const [activity, setActivity] = useState<{ userId: string; notice: string; ticketIds: string[] }>({ userId: "", notice: "", ticketIds: [] });
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
        if (event.type === "ticket.read") return;
        const notice = notices[event.type];
        if (noticeTimer) clearTimeout(noticeTimer);
        setActivity((previous) => ({
          userId,
          notice,
          ticketIds: [...new Set([...(previous.userId === userId ? previous.ticketIds : []), event.data.ticket_id])].slice(-50)
        }));
        noticeTimer = setTimeout(() => setActivity({ userId, notice: "", ticketIds: [] }), 4000);
      }
    });
    return () => {
      stop();
      if (noticeTimer) clearTimeout(noticeTimer);
    };
  }, [queryClient, userId]);
  return <LiveContext.Provider value={{ notice: activity.userId === userId ? activity.notice : "", ticketIds: activity.userId === userId ? activity.ticketIds : [], connection }}>{children}</LiveContext.Provider>;
}

export function useTicketListLive() {
  return useContext(LiveContext);
}
