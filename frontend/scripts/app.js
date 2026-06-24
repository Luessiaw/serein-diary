/* P2 仅以阅读态渲染已保存样本，暂不涉及持久化。 */
(function () {
  "use strict";

  const app = document.getElementById("app");

  if (!app) {
    throw new Error("Serein application mount point is missing.");
  }

  const feed = document.createElement("section");
  feed.className = "diary-feed";
  feed.setAttribute("aria-label", "Diary entries");

  const readingSamples = window.SereinMockEntries.filter(
    (sample) => sample.ui.mode !== "new",
  );

  readingSamples.forEach((sample) => {
    const entry = document.createElement("article");
    const date = document.createElement("time");
    const content = document.createElement("div");
    const { data, ui } = sample;

    entry.className = "diary-entry";
    entry.dataset.entryId = data.metadata.id;
    entry.dataset.entryMode = ui.mode;
    date.className = "entry-date";
    date.dateTime = data.metadata.date;
    date.textContent = formatDate(data.metadata.date);
    content.className = "entry-content";
    appendMarkdownParagraphs(content, data.content);

    entry.append(date);
    if (data.metadata.title) {
      const title = document.createElement("h2");
      title.className = "entry-title";
      title.textContent = data.metadata.title;
      entry.append(title);
    }
    entry.append(content);
    feed.append(entry);
  });

  app.replaceChildren(feed);

  function formatDate(date) {
    return date.replaceAll("-", ".");
  }

  function appendMarkdownParagraphs(container, markdown) {
    markdown.split(/\n{2,}/u).forEach((paragraph) => {
      const element = document.createElement("p");
      const lines = paragraph.split("\n");

      lines.forEach((line, index) => {
        if (index > 0) {
          element.append(document.createElement("br"));
        }
        element.append(line);
      });
      container.append(element);
    });
  }
}());
