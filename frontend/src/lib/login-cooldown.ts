/** Convert Retry-After to an absolute deadline; never invent a fallback window. */
export function retryAfterDeadline(value: string | null, now = Date.now()): number | undefined {
  if (!value?.trim()) return undefined;
  const header = value.trim();
  const deadline = /^\d+$/.test(header)
    ? now + Number(header) * 1000
    : /^[A-Za-z]{3}, /.test(header) ? Date.parse(header) : NaN;
  return Number.isSafeInteger(deadline) ? Math.max(now, deadline) : undefined;
}

export function remainingSeconds(deadline: number, now = Date.now()): number {
  return Math.max(0, Math.ceil((deadline - now) / 1000));
}

export function loginSubmissionDisabled(pending: boolean, seconds: number): boolean {
  return pending || seconds > 0;
}

/** Absolute time avoids drift when a background tab throttles timers. */
export function watchLoginCooldown(
  deadline: number,
  update: (seconds: number) => void,
  clock = Date.now,
  schedule: (tick: () => void) => () => void = (tick) => {
    const timer = setInterval(tick, 250);
    return () => clearInterval(timer);
  },
): () => void {
  let active = true;
  const cancel = schedule(() => {
    if (!active) return;
    const seconds = remainingSeconds(deadline, clock());
    update(seconds);
    if (seconds === 0) {
      active = false;
      cancel();
    }
  });
  return () => { active = false; cancel(); };
}
