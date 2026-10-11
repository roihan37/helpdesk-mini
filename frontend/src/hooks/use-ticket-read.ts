"use client";

import { apiRequest, getAccessToken, onAccessTokenChanged } from "@/lib/api";
import { mergeMessages } from "@/lib/domain";
import { queryKeys } from "@/lib/query";
import type { Message } from "@/types/api";
import { useQueryClient } from "@tanstack/react-query";
import { type RefObject, useEffect, useRef, useState } from "react";

function compareSequence(left: string, right: string) {
  return left.length - right.length || (left > right ? 1 : left < right ? -1 : 0);
}

function latestMessage(messages: Message[]) {
  let latest: Message | null = null;
  for (const message of messages) {
    // Do not acknowledge incomplete/pre-migration history or lose BIGINT precision.
    if (!message.sequence || !/^[1-9][0-9]*$/.test(message.sequence)) return null;
    if (!latest || compareSequence(message.sequence, latest.sequence!) > 0) {
      latest = message;
    }
  }
  return latest;
}

export function useTicketRead(
  ticketId: string,
  userId: string,
  messages: Message[],
  ready: boolean,
  listRef: RefObject<HTMLDivElement | null>
) {
  const queryClient = useQueryClient();
  const scope = `${userId}:${ticketId}`;
  const snapshot = useRef({ messages, ready });
  const scheduleRef = useRef<(() => void) | null>(null);
  const retryRef = useRef<(() => void) | null>(null);
  const [failure, setFailure] = useState({ scope: "", message: "" });

  useEffect(() => {
    if (!userId) return;
    let active = true;
    let frame = 0;
    let request: AbortController | null = null;
    let acknowledged = "0";
    let failed = false;
    let verified: { message: Message; ids: Set<string> } | null = null;

    function isViewed() {
      const list = listRef.current;
      if (
        !snapshot.current.ready ||
        !getAccessToken() ||
        document.visibilityState !== "visible" ||
        !list ||
        !list.clientHeight
      ) return false;
      // Do not acknowledge an image that has not successfully rendered yet.
      if (list.querySelector('[data-attachment-pending="true"]')) return false;
      if (list.scrollHeight - list.scrollTop - list.clientHeight > 8) return false;
      const last = list.lastElementChild;
      if (!last) return false;
      const end = last.getBoundingClientRect().bottom;
      const bounds = list.getBoundingClientRect();
      return (
        end > Math.max(0, bounds.top) &&
        end <= Math.min(window.innerHeight, bounds.bottom) + 1
      );
    }

    function schedule() {
      if (active && !frame) frame = requestAnimationFrame(check);
    }

    function check() {
      frame = 0;
      if (!active || failed || request || !isViewed()) return;
      const latest = latestMessage(snapshot.current.messages);
      if (!latest || compareSequence(latest.sequence!, acknowledged) <= 0) return;
      if (verified) {
        const rendered = new Set(snapshot.current.messages.map((message) => message.id));
        if (
          compareSequence(latest.sequence!, verified.message.sequence!) < 0 ||
          !Array.from(verified.ids).every((id) => rendered.has(id))
        ) return;
        void acknowledge(verified.message);
      } else {
        void reconcile(latest);
      }
    }

    async function reconcile(observed: Message) {
      const controller = new AbortController();
      request = controller;
      try {
        // A later socket event may arrive before an earlier committed message.
        // Reconcile once per observed batch, then wait for the complete render.
        const history = await apiRequest<Message[]>(
          `/tickets/${encodeURIComponent(ticketId)}/messages`,
          { signal: controller.signal }
        );
        if (!active) return;
        const boundary = history.find(
          (message) => message.id === observed.id && message.sequence === observed.sequence
        );
        if (!boundary || !latestMessage(history)) throw new Error("Incomplete read boundary");
        verified = {
          message: boundary,
          ids: new Set(
            history
              .filter((message) => compareSequence(message.sequence!, boundary.sequence!) <= 0)
              .map((message) => message.id)
          )
        };
        queryClient.setQueryData<Message[]>(
          queryKeys.messages(ticketId),
          (current = []) => mergeMessages(current, history)
        );
      } catch {
        if (active && !controller.signal.aborted) reportFailure();
      } finally {
        request = null;
        schedule();
      }
    }

    async function acknowledge(boundary: Message) {
      const controller = new AbortController();
      request = controller;
      try {
        await apiRequest<{ ticket_id: string; unread_count: number }>(
          `/tickets/${encodeURIComponent(ticketId)}/read`,
          {
            method: "POST",
            body: JSON.stringify({ last_message_id: boundary.id }),
            signal: controller.signal
          }
        );
        if (!active) return;
        acknowledged = boundary.sequence!;
        verified = null;
        setFailure({ scope, message: "" });
        // Never force zero: messages beyond the observed boundary remain unread.
        void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      } catch {
        if (active && !controller.signal.aborted) reportFailure();
      } finally {
        request = null;
        schedule();
      }
    }

    function reportFailure() {
      failed = true;
      setFailure({ scope, message: "Unread status could not be saved." });
    }

    scheduleRef.current = schedule;
    retryRef.current = () => {
      failed = false;
      setFailure({ scope, message: "" });
      schedule();
    };
    const unsubscribe = onAccessTokenChanged((token) => {
      if (token === null) {
        active = false;
        request?.abort();
        cancelAnimationFrame(frame);
      } else schedule();
    });
    document.addEventListener("visibilitychange", schedule);
    window.addEventListener("scroll", schedule, true);
    window.addEventListener("focus", schedule);
    window.addEventListener("resize", schedule);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
    if (listRef.current) observer?.observe(listRef.current);
    const images = new MutationObserver(schedule);
    if (listRef.current) images.observe(listRef.current, {
      subtree: true, childList: true, attributes: true, attributeFilter: ["data-attachment-pending"]
    });
    schedule();
    return () => {
      active = false;
      request?.abort();
      cancelAnimationFrame(frame);
      observer?.disconnect();
      images.disconnect();
      unsubscribe();
      document.removeEventListener("visibilitychange", schedule);
      window.removeEventListener("scroll", schedule, true);
      window.removeEventListener("focus", schedule);
      window.removeEventListener("resize", schedule);
      scheduleRef.current = null;
      retryRef.current = null;
    };
  }, [ticketId, userId, scope, queryClient, listRef]);

  useEffect(() => {
    snapshot.current = { messages, ready };
    scheduleRef.current?.();
  }, [messages, ready]);

  return {
    error: failure.scope === scope ? failure.message : "",
    retry: () => retryRef.current?.()
  };
}
