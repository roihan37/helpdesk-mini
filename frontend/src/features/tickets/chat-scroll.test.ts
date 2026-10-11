import assert from "node:assert/strict";
import test, { type TestContext } from "node:test";
import { createChatScroll } from "./chat-scroll.ts";

function setup(t: TestContext) {
  const frames = new Map<number, FrameRequestCallback>();
  let nextFrame = 0;
  let resize: ResizeObserverCallback | undefined;
  let disconnected = false;
  const originals = new Map(
    ["requestAnimationFrame", "cancelAnimationFrame", "ResizeObserver"].map((key) =>
      [key, Object.getOwnPropertyDescriptor(globalThis, key)] as const
    )
  );
  Object.assign(globalThis, {
    requestAnimationFrame(callback: FrameRequestCallback) {
      frames.set(++nextFrame, callback);
      return nextFrame;
    },
    cancelAnimationFrame(id: number) { frames.delete(id); },
    ResizeObserver: class {
      constructor(callback: ResizeObserverCallback) { resize = callback; }
      observe() {}
      disconnect() { disconnected = true; }
    }
  });
  const list = Object.assign(new EventTarget(), {
    scrollHeight: 1000,
    clientHeight: 400,
    scrollTop: 0,
    children: [],
    scrollTo(options: ScrollToOptions) {
      assert.equal(options.behavior, "instant");
      this.scrollTop = Math.max(0, (options.top ?? 0) - this.clientHeight);
    }
  });
  let visible = false;
  const scroll = createChatScroll(list as unknown as HTMLDivElement, (value) => { visible = value; });
  t.after(() => {
    scroll.dispose();
    for (const [key, descriptor] of originals) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else Reflect.deleteProperty(globalThis, key);
    }
  });
  function flush() {
    const pending = [...frames.values()];
    frames.clear();
    for (const callback of pending) callback(0);
  }
  return {
    list, scroll, flush,
    visible: () => visible,
    resized: () => resize?.([], {} as ResizeObserver),
    disconnected: () => disconnected,
    pending: () => frames.size,
    moveTo(top: number) {
      list.scrollTop = top;
      list.dispatchEvent(new Event("scroll"));
    }
  };
}

test("initial history and a tall incoming message auto-scroll using the previous position", (t) => {
  const chat = setup(t);
  chat.scroll.sync(10);
  chat.flush();
  assert.equal(chat.list.scrollTop, 600);
  chat.moveTo(600);
  chat.list.scrollHeight += 600; // Taller than the old 96px post-append threshold.
  chat.scroll.sync(11);
  chat.flush();
  assert.equal(chat.list.scrollTop, 1200);
  assert.equal(chat.visible(), false);
});

test("reading older messages is preserved; scrolling down clears the button without a click", (t) => {
  const chat = setup(t);
  chat.scroll.sync(10);
  chat.flush();
  chat.moveTo(200);
  chat.list.scrollHeight += 200;
  chat.scroll.sync(11);
  chat.flush();
  assert.equal(chat.list.scrollTop, 200);
  assert.equal(chat.visible(), true);
  chat.moveTo(800);
  assert.equal(chat.visible(), false);
  chat.list.scrollHeight += 300;
  chat.scroll.sync(12);
  chat.flush();
  assert.equal(chat.list.scrollTop, 1100);
  assert.equal(chat.visible(), false);
});

test("near-bottom readers follow messages and explicit jump clears pending activity", (t) => {
  const chat = setup(t);
  chat.scroll.sync(10);
  chat.flush();
  chat.moveTo(520);
  chat.list.scrollHeight += 200;
  chat.scroll.sync(11);
  chat.flush();
  assert.equal(chat.list.scrollTop, 800);
  chat.moveTo(0);
  chat.list.scrollHeight += 200;
  chat.scroll.sync(12);
  chat.flush();
  assert.equal(chat.visible(), true);
  chat.scroll.jumpToBottom();
  assert.equal(chat.list.scrollTop, 1000);
  assert.equal(chat.visible(), false);
});

test("image and viewport resizing follow the bottom but do not interrupt older-history readers", (t) => {
  const chat = setup(t);
  chat.scroll.sync(10);
  chat.flush();
  chat.list.scrollHeight += 300;
  chat.resized();
  chat.flush();
  assert.equal(chat.list.scrollTop, 900);
  chat.moveTo(100);
  chat.list.scrollHeight += 300;
  chat.resized();
  chat.flush();
  assert.equal(chat.list.scrollTop, 100);
  assert.equal(chat.visible(), false);
});

test("receipt-only updates do not create new-message notifications; cleanup cancels pending work", (t) => {
  const chat = setup(t);
  chat.scroll.sync(10);
  chat.flush();
  chat.moveTo(0);
  chat.scroll.sync(10);
  chat.flush();
  assert.equal(chat.visible(), false);
  chat.list.scrollHeight += 200;
  chat.scroll.sync(11);
  assert.equal(chat.pending(), 1);
  chat.scroll.dispose();
  chat.resized(); // A previously queued observer callback must not restart work.
  assert.equal(chat.pending(), 0);
  assert.equal(chat.disconnected(), true);
  chat.moveTo(800);
  chat.flush();
  assert.equal(chat.list.scrollTop, 800);
  assert.equal(chat.visible(), false);
});
