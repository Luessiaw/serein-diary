/* P2 仅以阅读态渲染已保存样本，暂不涉及持久化。 */
(function () {
  "use strict";

  const app = document.getElementById("app");

  if (!app) {
    throw new Error("Serein application mount point is missing.");
  }

  renderFeed();

  function renderFeed() {
    const feed = document.createElement("section");
    const readingSamples = getReadingSamples();
    const entriesPerDate = countEntriesPerDate(readingSamples);

    feed.className = "diary-feed";
    feed.setAttribute("aria-label", "Diary entries");

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

    feed.append(createNewEntryArea());
    app.replaceChildren(feed);
  }

  function getReadingSamples() {
    return window.SereinMockEntries
      .filter((sample) => sample.ui.mode === "reading")
      .slice()
      .sort((left, right) => (
        left.data.metadata.created_at.localeCompare(right.data.metadata.created_at)
      ));
  }

  function createNewEntryArea() {
    const area = document.createElement("section");
    const date = document.createElement("p");

    area.className = "new-entry";
    area.setAttribute("aria-label", "New diary entry");
    date.className = "entry-date new-entry-date";
    date.textContent = "现在";

    const form = document.createElement("form");
    const title = document.createElement("input");
    const content = document.createElement("textarea");
    const message = document.createElement("p");
    const actions = document.createElement("div");
    const cancel = document.createElement("button");
    const saveDraft = document.createElement("button");
    const save = document.createElement("button");

    form.className = "new-entry-form";
    title.className = "new-entry-title-input";
    title.name = "title";
    title.placeholder = "标题";
    title.setAttribute("aria-label", "Diary title");
    content.className = "new-entry-content-input";
    content.name = "content";
    content.placeholder = "写下此刻……";
    content.rows = 8;
    content.setAttribute("aria-label", "Diary content");
    message.className = "new-entry-message";
    message.setAttribute("role", "status");
    actions.className = "new-entry-actions";
    cancel.className = "new-entry-cancel";
    cancel.type = "button";
    cancel.textContent = "取消";
    saveDraft.className = "new-entry-save-draft";
    saveDraft.type = "button";
    saveDraft.textContent = "保存草稿";
    save.className = "new-entry-save";
    save.type = "submit";
    save.textContent = "保存";

    cancel.addEventListener("click", () => {
      form.reset();
      message.textContent = "已清空未保存内容。";
      title.focus();
    });
    saveDraft.addEventListener("click", () => {
      message.textContent = "保存草稿将在后端阶段提供；当前内容仍只保留在本页。";
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();

      const body = content.value.trim();
      if (!body) {
        message.textContent = "请先写下一些内容。";
        content.focus();
        return;
      }

      addStaticEntry(title.value.trim(), body);
      renderFeed();
    });

    actions.append(cancel, saveDraft, save);
    form.append(title, content, message, actions);
    area.append(date, form);
    requestAnimationFrame(() => content.focus());

    return area;
  }

  function addStaticEntry(title, content) {
    const metadata = {
      schema_version: 1,
      id: createMockUuid(),
      created_at: createLocalTimestamp(),
    };

    if (title) {
      metadata.title = title;
    }

    window.SereinMockEntries = [
      ...window.SereinMockEntries.filter((sample) => sample.ui.mode !== "new"),
      {
        ui: { mode: "reading" },
        data: {
          metadata,
          content,
          comments: { schema_version: 1, comments: [] },
          mediaManifest: { schema_version: 1, media: [] },
        },
      },
      createNewDraft(),
    ];
  }

  function createNewDraft() {
    return {
      ui: { mode: "new" },
      data: {
        metadata: {
          schema_version: 1,
          id: null,
          created_at: null,
        },
        content: "",
        comments: { schema_version: 1, comments: [] },
        mediaManifest: { schema_version: 1, media: [] },
      },
    };
  }

  function createMockUuid() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }

    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
      const value = Math.floor(Math.random() * 16);
      const nibble = character === "x" ? value : (value & 0x3) | 0x8;

      return nibble.toString(16);
    });
  }

  function createLocalTimestamp() {
    const now = new Date();
    const offsetMinutes = -now.getTimezoneOffset();
    const sign = offsetMinutes >= 0 ? "+" : "-";
    const offsetHours = Math.floor(Math.abs(offsetMinutes) / 60);
    const offsetRemainder = Math.abs(offsetMinutes) % 60;
    const pad = (value) => String(value).padStart(2, "0");

    return [
      now.getFullYear(),
      pad(now.getMonth() + 1),
      pad(now.getDate()),
    ].join("-") + `T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}${sign}${pad(offsetHours)}:${pad(offsetRemainder)}`;
  }

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
