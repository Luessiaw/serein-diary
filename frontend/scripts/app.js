/* P1 renders visual placeholders only; no entry state or persistence exists yet. */
(function () {
  "use strict";

  const app = document.getElementById("app");

  if (!app) {
    throw new Error("Serein application mount point is missing.");
  }

  const feed = document.createElement("section");
  feed.className = "placeholder-feed";
  feed.setAttribute("aria-label", "Diary placeholders");

  window.SereinMockEntries.forEach((placeholder) => {
    const entry = document.createElement("article");
    const text = document.createElement("p");

    entry.className = "placeholder-entry";
    entry.dataset.placeholderId = placeholder.id;
    entry.style.setProperty("--placeholder-min-height", placeholder.height);
    text.textContent = placeholder.text;
    entry.append(text);
    feed.append(entry);
  });

  app.replaceChildren(feed);
}());
