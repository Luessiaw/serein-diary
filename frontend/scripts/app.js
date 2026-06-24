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

  const readingSamples = window.SereinMockEntries
    .filter((sample) => sample.ui.mode === "reading")
    .slice()
    .sort((left, right) => (
      left.data.metadata.created_at.localeCompare(right.data.metadata.created_at)
    ));
  const entriesPerDate = countEntriesPerDate(readingSamples);

  groupEntriesByDate(readingSamples).forEach((yearGroup) => {
    const year = createGroup("diary-year", `${yearGroup.year}年`);

    yearGroup.months.forEach((monthGroup) => {
      const month = createGroup("diary-month", `${Number(monthGroup.month)}月`);

      monthGroup.entries.forEach((sample) => {
        month.content.append(createEntry(sample, entriesPerDate));
      });
      year.content.append(month.details);
    });
    feed.append(year.details);
  });

  app.replaceChildren(feed);

  function createGroup(className, label) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const content = document.createElement("div");

    details.className = className;
    details.open = true;
    summary.className = "diary-group-summary";
    summary.textContent = label;
    content.className = "diary-group-content";
    details.append(summary, content);

    return { details, content };
  }

  function createEntry(sample, entriesByDate) {
    const entry = document.createElement("article");
    const date = document.createElement("time");
    const content = document.createElement("div");
    const { data, ui } = sample;
    const { metadata } = data;
    const calendarDate = getCalendarDate(metadata.created_at);

    entry.className = "diary-entry";
    entry.dataset.entryId = metadata.id;
    entry.dataset.entryMode = ui.mode;
    date.className = "entry-date";
    date.dateTime = metadata.created_at;
    date.textContent = formatEntryDate(
      calendarDate,
      metadata.created_at,
      entriesByDate.get(calendarDate),
    );
    content.className = "entry-content";
    appendMarkdownParagraphs(content, data.content);

    entry.append(date);
    if (metadata.title) {
      const title = document.createElement("h2");
      title.className = "entry-title";
      title.textContent = metadata.title;
      entry.append(title);
    }
    entry.append(content);

    return entry;
  }

  function groupEntriesByDate(entries) {
    const years = new Map();

    entries.forEach((sample) => {
      const [year, month] = getCalendarDate(
        sample.data.metadata.created_at,
      ).split("-");
      let yearGroup = years.get(year);

      if (!yearGroup) {
        yearGroup = { year, months: new Map() };
        years.set(year, yearGroup);
      }
      if (!yearGroup.months.has(month)) {
        yearGroup.months.set(month, []);
      }
      yearGroup.months.get(month).push(sample);
    });

    return [...years.values()].map((yearGroup) => ({
      year: yearGroup.year,
      months: [...yearGroup.months.entries()].map(([month, entries]) => ({
        month,
        entries,
      })),
    }));
  }

  function countEntriesPerDate(entries) {
    return entries.reduce((counts, sample) => {
      const calendarDate = getCalendarDate(sample.data.metadata.created_at);
      counts.set(calendarDate, (counts.get(calendarDate) || 0) + 1);
      return counts;
    }, new Map());
  }

  function formatEntryDate(date, createdAt, entriesOnDate) {
    const day = Number(date.slice(-2));
    const time = createdAt.slice(11, 16);

    return entriesOnDate > 1 ? `${day}日 ${time}` : `${day}日`;
  }

  function getCalendarDate(createdAt) {
    return createdAt.slice(0, 10);
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
