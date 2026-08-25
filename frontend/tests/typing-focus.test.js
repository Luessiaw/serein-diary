"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

require("../scripts/typing-focus.js");

const { resolveScrollAdjustment, resolveVisibleViewport } = globalThis.SereinTypingFocus;
const focusBand = { startRatio: 0.55, targetRatio: 0.60, endRatio: 0.65 };

function decide(overrides = {}) {
  return resolveScrollAdjustment({
    visibleTop: 0,
    visibleBottom: 1000,
    caretTop: 600,
    scrollTop: 500,
    scrollHeight: 3000,
    clientHeight: 1000,
    engaged: true,
    focusBand,
    ...overrides,
  });
}

test("does not move while the caret remains inside the focus band", () => {
  assert.equal(decide({ caretTop: 620 }).delta, 0);
  assert.equal(decide({ caretTop: 620 }).reason, "inside-band");
});

test("does not engage short-form writing above the lower threshold", () => {
  const decision = decide({ caretTop: 120, engaged: false });

  assert.equal(decision.delta, 0);
  assert.equal(decision.reason, "not-engaged");
});

test("moves a caret below the band back to the target", () => {
  const decision = decide({ caretTop: 700, engaged: false });

  assert.equal(decision.delta, 100);
  assert.equal(decision.targetScrollTop, 600);
});

test("moves an engaged caret above the band back to the target", () => {
  const decision = decide({ caretTop: 400 });

  assert.equal(decision.delta, -200);
  assert.equal(decision.targetScrollTop, 300);
});

test("clamps movement at the scroll boundaries", () => {
  const topDecision = decide({ caretTop: 100, scrollTop: 50 });
  const bottomDecision = decide({ caretTop: 900, scrollTop: 1950 });

  assert.equal(topDecision.targetScrollTop, 0);
  assert.equal(topDecision.delta, -50);
  assert.equal(bottomDecision.targetScrollTop, 2000);
  assert.equal(bottomDecision.delta, 50);
});

test("does not move when the container has no scrollable space", () => {
  const decision = decide({ scrollTop: 0, scrollHeight: 800, clientHeight: 1000 });

  assert.equal(decision.delta, 0);
  assert.equal(decision.reason, "no-scroll-space");
});

test("intersects the container with a mobile visual viewport", () => {
  assert.deepEqual(resolveVisibleViewport({
    containerTop: 0,
    containerBottom: 900,
    viewportTop: 120,
    viewportBottom: 620,
  }), {
    top: 120,
    bottom: 620,
    height: 500,
  });
});
