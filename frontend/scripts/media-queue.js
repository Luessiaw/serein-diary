/* Pure helpers for preserving mixed local/Immich media order. */
(function (root) {
  "use strict";

  function localItems(files) {
    return Array.from(files || []).map((file) => ({ source: "local", file, name: file.name }));
  }

  function appendImmichUnique(queue, incoming) {
    const known = new Set(
      (queue || []).filter((item) => item.source === "immich").map((item) => item.assetId),
    );
    return [
      ...(queue || []),
      ...(incoming || []).filter((item) => !known.has(item.assetId)),
    ];
  }

  function nextOperation(queue, maxBatch = 20) {
    if (!queue?.length) return null;
    if (queue[0].source === "local") {
      return { source: "local", count: 1, items: [queue[0]] };
    }
    const items = [];
    while (items.length < maxBatch && queue[items.length]?.source === "immich") {
      items.push(queue[items.length]);
    }
    return { source: "immich", count: items.length, items };
  }

  const api = { appendImmichUnique, localItems, nextOperation };
  root.SereinMediaQueue = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window === "undefined" ? globalThis : window);
