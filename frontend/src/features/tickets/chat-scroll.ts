// Remember the reader's position before React appends messages, not after the
// new content has increased scrollHeight. Resize observation also follows images.
export function createChatScroll(list: HTMLDivElement, onNewMessages: (visible: boolean) => void) {
  let following = true;
  let count = 0;
  let pendingMessages = false;
  let frame = 0;
  let active = true;

  function jumpToBottom() {
    following = true;
    pendingMessages = false;
    list.scrollTo({ top: list.scrollHeight, behavior: "instant" });
    onNewMessages(false);
  }

  function onScroll() {
    following = list.scrollHeight - list.scrollTop - list.clientHeight <= 96;
    if (following) {
      pendingMessages = false;
      onNewMessages(false);
    }
  }

  function schedule() {
    if (!active || frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      if (following) jumpToBottom();
      else if (pendingMessages) onNewMessages(true);
    });
  }

  const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(schedule);
  list.addEventListener("scroll", onScroll, { passive: true });

  return {
    sync(messageCount: number) {
      if (messageCount > count) pendingMessages = true;
      count = messageCount;
      observer?.disconnect();
      observer?.observe(list);
      for (const child of Array.from(list.children)) observer?.observe(child);
      schedule();
    },
    jumpToBottom,
    dispose() {
      active = false;
      cancelAnimationFrame(frame);
      observer?.disconnect();
      list.removeEventListener("scroll", onScroll);
    }
  };
}
