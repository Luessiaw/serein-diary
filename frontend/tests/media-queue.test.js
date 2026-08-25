"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const queue = require("../scripts/media-queue.js");

test("groups only consecutive Immich items and preserves mixed order", () => {
  const items = [
    { source: "immich", assetId: "one" },
    { source: "immich", assetId: "two" },
    { source: "local", file: {} },
    { source: "immich", assetId: "three" },
  ];
  assert.deepEqual(queue.nextOperation(items).items.map((item) => item.assetId), ["one", "two"]);
  assert.equal(queue.nextOperation(items.slice(2)).source, "local");
});

test("does not append an Immich asset already queued", () => {
  const result = queue.appendImmichUnique(
    [{ source: "immich", assetId: "one" }],
    [{ source: "immich", assetId: "one" }, { source: "immich", assetId: "two" }],
  );
  assert.deepEqual(result.map((item) => item.assetId), ["one", "two"]);
});
