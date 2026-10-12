import assert from "node:assert/strict";
import { test } from "node:test";
import { loginSubmissionDisabled, remainingSeconds, retryAfterDeadline, watchLoginCooldown } from "./login-cooldown.ts";

test("Retry-After parses actual seconds and HTTP dates without a fallback duration", () => {
  const now = Date.parse("Mon, 12 Oct 2026 00:00:00 GMT");
  assert.equal(retryAfterDeadline(" 37 ", now), now + 37000);
  assert.equal(retryAfterDeadline("Mon, 12 Oct 2026 00:01:00 GMT", now), now + 60000);
  assert.equal(retryAfterDeadline("Sun, 11 Oct 2026 00:00:00 GMT", now), now);
  assert.equal(retryAfterDeadline("0", now), now);
  for (const value of [null, "", "bad", "-1", "1.5", "999999999999999999999"]) {
    assert.equal(retryAfterDeadline(value, now), undefined);
  }
});

test("countdown rounds up, blocks submission, handles suspended tabs and stops at expiry", () => {
  let now = 1000;
  let tick = () => {};
  let cancelled = 0;
  let seconds = remainingSeconds(3500, now);
  const stop = watchLoginCooldown(3500, (value) => { seconds = value; }, () => now, (callback) => {
    tick = callback;
    return () => { cancelled += 1; };
  });
  assert.equal(seconds, 3);
  assert.equal(loginSubmissionDisabled(false, seconds), true);
  now = 2500;
  tick();
  assert.equal(seconds, 1);
  now = 10000;
  tick();
  assert.equal(seconds, 0);
  assert.equal(loginSubmissionDisabled(false, seconds), false);
  assert.equal(loginSubmissionDisabled(true, seconds), true);
  assert.equal(cancelled, 1);
  stop();
});

test("unmount cleanup prevents subsequent timer updates", () => {
  let tick = () => {};
  let updates = 0;
  let cancelled = false;
  const stop = watchLoginCooldown(10000, () => { updates += 1; }, () => 0, (callback) => {
    tick = callback;
    return () => { cancelled = true; };
  });
  stop();
  tick();
  assert.equal(cancelled, true);
  assert.equal(updates, 0);
});

test("ordinary failures and fresh page state introduce no client delay", () => {
  assert.equal(remainingSeconds(0, 1000), 0);
  assert.equal(loginSubmissionDisabled(false, 0), false);
});
