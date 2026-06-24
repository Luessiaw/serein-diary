/* P2 consumes entry-shaped static samples only; no persistence exists yet. */
(function () {
  "use strict";

  const app = document.getElementById("app");

  if (!app) {
    throw new Error("Serein application mount point is missing.");
  }

  const feed = document.createElement("section");
  feed.className = "placeholder-feed";
  feed.setAttribute("aria-label", "Diary placeholders");

  window.SereinMockEntries.forEach((sample) => {
    const entry = document.createElement("article");
    const text = document.createElement("p");
    const { data, ui } = sample;

    entry.className = "placeholder-entry";
    entry.dataset.entryId = data.metadata.id || "new-entry";
    entry.dataset.entryMode = ui.mode;
    entry.style.setProperty("--placeholder-min-height", ui.placeholderHeight);
    text.textContent = data.content.split("\n")[0] || "下一篇日记会在这里出现。";
    entry.append(text);
    feed.append(entry);
  });

  app.replaceChildren(feed);
}());
