/* P2 仅以阅读态渲染已保存样本，暂不涉及持久化。 */
(function () {
  "use strict";

  const app = document.getElementById("app");

  if (!app) {
    throw new Error("Serein application mount point is missing.");
  }

  if ("scrollRestoration" in window.history) {
    window.history.scrollRestoration = "manual";
  }

  const settings = readInteractionSettings();
  let draftCreatedAt = createLocalTimestamp();
  const loadState = {
    visibleStartIndex: 0,
    status: "idle",
    errorMessage: "",
  };

  initializeLoadedWindow();
  renderFeed({ focusNewEntry: true, scrollToEnd: true });
  app.addEventListener("scroll", handleScroll, { passive: true });

  function renderFeed(options = {}) {
    const { focusNewEntry = false, scrollToEnd = false } = options;
    const feed = document.createElement("section");
    const readingSamples = getReadingSamples();
    const entriesPerDate = countEntriesPerDate(readingSamples);
    const feedItems = createFeedItems(readingSamples);

    feed.className = "diary-feed";
    feed.setAttribute("aria-label", "Diary entries");
    feed.append(createLoadControl());

    groupItemsByDate(feedItems).forEach((yearGroup) => {
      const year = createGroup("diary-year", yearGroup.year);

      yearGroup.months.forEach((monthGroup) => {
        const month = createGroup("diary-month", String(Number(monthGroup.month)));

        monthGroup.items.forEach((item) => {
          if (item.type === "new") {
            month.content.append(createNewEntryArea({ focusNewEntry }));
          } else {
            month.content.append(createEntry(item.sample, entriesPerDate));
          }
        });
        year.content.append(month.details);
      });
      feed.append(year.details);
    });

    app.replaceChildren(feed);

    if (scrollToEnd) {
      requestAnimationFrame(() => {
        scrollToNewEntry();
        window.setTimeout(scrollToNewEntry, 0);
      });
    }
  }

  function getReadingSamples() {
    return getAllReadingSamples().slice(loadState.visibleStartIndex);
  }

  function getAllReadingSamples() {
    return window.SereinMockEntries
      .filter((sample) => sample.ui.mode === "reading")
      .slice()
      .sort((left, right) => (
        left.data.metadata.created_at.localeCompare(right.data.metadata.created_at)
      ));
  }

  function createFeedItems(readingSamples) {
    return [
      ...readingSamples.map((sample) => ({
        type: "entry",
        createdAt: sample.data.metadata.created_at,
        sample,
      })),
      {
        type: "new",
        createdAt: draftCreatedAt,
      },
    ].sort((left, right) => left.createdAt.localeCompare(right.createdAt));
  }

  function initializeLoadedWindow() {
    const total = getAllReadingSamples().length;

    loadState.visibleStartIndex = Math.max(0, total - settings.initialCount);
    loadState.status = loadState.visibleStartIndex === 0 ? "complete" : "idle";
  }

  function createNewEntryArea({ focusNewEntry }) {
    const area = document.createElement("section");
    const date = document.createElement("p");
    const body = document.createElement("div");

    area.className = "new-entry";
    area.setAttribute("aria-label", "New diary entry");
    date.className = "entry-date new-entry-date";
    date.textContent = "现在";
    body.className = "entry-body new-entry-body";

    const form = document.createElement("form");
    const title = document.createElement("input");
    const content = document.createElement("textarea");
    const message = document.createElement("p");
    const header = document.createElement("div");
    const actions = document.createElement("div");
    const cancel = document.createElement("button");
    const draftStatus = document.createElement("span");
    const save = document.createElement("button");

    form.className = "new-entry-form";
    title.className = "new-entry-title-input";
    title.name = "title";
    title.placeholder = "标题";
    title.setAttribute("aria-label", "Diary title");
    content.className = "new-entry-content-input";
    content.name = "content";
    content.placeholder = "写下此刻……";
    content.rows = 1;
    content.setAttribute("aria-label", "Diary content");
    message.className = "new-entry-message";
    message.setAttribute("role", "status");
    header.className = "new-entry-header";
    actions.className = "new-entry-actions";
    cancel.className = "new-entry-cancel";
    cancel.type = "button";
    cancel.textContent = "×";
    cancel.title = "取消保存";
    cancel.setAttribute("aria-label", "取消保存");
    draftStatus.className = "new-entry-draft-status";
    draftStatus.title = "草稿状态（暂未启用）";
    draftStatus.setAttribute("role", "img");
    draftStatus.setAttribute("aria-label", "草稿状态（暂未启用）");
    save.className = "new-entry-save";
    save.type = "submit";
    save.textContent = "✓";
    save.title = "保存日记";
    save.setAttribute("aria-label", "保存日记");

    content.addEventListener("input", () => {
      resizeContentInput(content);
    });

    cancel.addEventListener("click", () => {
      form.reset();
      message.textContent = "已清空未保存内容。";
      title.focus({ preventScroll: true });
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();

      const body = content.value.trim();
      if (!body) {
        message.textContent = "请先写下一些内容。";
        content.focus({ preventScroll: true });
        return;
      }

      addStaticEntry(title.value.trim(), body);
      renderFeed({ focusNewEntry: true, scrollToEnd: true });
    });

    actions.append(draftStatus, cancel, save);
    header.append(title, actions);
    form.append(header, content, message);
    body.append(form);
    area.append(date, body);
    if (focusNewEntry) {
      requestAnimationFrame(() => {
        resizeContentInput(content);
        content.focus({ preventScroll: true });
      });
    } else {
      resizeContentInput(content);
    }

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
    draftCreatedAt = createLocalTimestamp();
    loadState.status = loadState.visibleStartIndex === 0 ? "complete" : "idle";
  }

  function createLoadControl() {
    const control = document.createElement("div");
    const spinner = document.createElement("span");
    const message = document.createElement("span");

    control.className = `load-control is-${loadState.status}`;
    control.setAttribute("role", "status");
    control.setAttribute("aria-live", "polite");
    spinner.className = "load-control-spinner";
    spinner.setAttribute("aria-hidden", "true");
    message.className = "load-control-message";

    if (loadState.status === "loading") {
      message.textContent = "正在拉取更早的日记……";
      control.append(spinner, message);
    } else if (loadState.status === "error") {
      const retry = document.createElement("button");

      message.textContent = `拉取信息失败：${loadState.errorMessage}`;
      retry.className = "load-control-retry";
      retry.type = "button";
      retry.textContent = "重试";
      retry.addEventListener("click", () => {
        void loadEarlierEntries();
      });
      control.append(message, retry);
    } else if (loadState.status === "complete") {
      message.textContent = "已加载所有日记内容";
      control.append(message);
    } else {
      control.hidden = true;
      control.append(message);
    }

    return control;
  }

  function handleScroll() {
    if (!shouldLoadEarlierEntries()) {
      return;
    }

    void loadEarlierEntries();
  }

  function shouldLoadEarlierEntries() {
    if (loadState.status === "loading" || loadState.status === "complete") {
      return false;
    }

    if (loadState.visibleStartIndex <= 0) {
      loadState.status = "complete";
      renderFeed();
      return false;
    }

    const entries = [...app.querySelectorAll(".diary-entry")];
    if (entries.length === 0) {
      return false;
    }

    const triggerIndex = Math.min(
      Math.max(settings.triggerEntryIndex, 1),
      entries.length,
    ) - 1;
    const triggerEntry = entries[triggerIndex];

    return app.scrollTop <= triggerEntry.offsetTop;
  }

  async function loadEarlierEntries() {
    if (loadState.status === "loading" || loadState.status === "complete") {
      return;
    }

    const anchor = getScrollAnchor();

    loadState.status = "loading";
    loadState.errorMessage = "";
    renderFeedRestoringAnchor(anchor);

    try {
      await simulateLoadingDelay();

      if (window.SereinMockLoadFailure === true) {
        throw new Error("模拟网络异常");
      }

      loadState.visibleStartIndex = Math.max(
        0,
        loadState.visibleStartIndex - settings.pageSize,
      );
      loadState.status = loadState.visibleStartIndex === 0 ? "complete" : "idle";
      renderFeedRestoringAnchor(anchor);
    } catch (error) {
      loadState.status = "error";
      loadState.errorMessage = error instanceof Error ? error.message : "未知错误";
      renderFeedRestoringAnchor(anchor);
    }
  }

  function getScrollAnchor() {
    const appTop = app.getBoundingClientRect().top;
    const entries = [...app.querySelectorAll(".diary-entry")];
    const visibleEntry = entries.find((entry) => (
      entry.getBoundingClientRect().bottom >= appTop
    ));

    if (!visibleEntry) {
      return null;
    }

    return {
      id: visibleEntry.dataset.entryId,
      top: visibleEntry.getBoundingClientRect().top,
    };
  }

  function renderFeedRestoringAnchor(anchor) {
    renderFeed();

    if (!anchor) {
      return;
    }

    const anchoredEntry = app.querySelector(`[data-entry-id="${anchor.id}"]`);

    if (!anchoredEntry) {
      return;
    }

    setScrollTopInstant(
      app.scrollTop + anchoredEntry.getBoundingClientRect().top - anchor.top,
    );
  }

  function scrollToNewEntry() {
    const newEntry = app.querySelector(".new-entry");

    if (!newEntry) {
      setScrollTopInstant(app.scrollHeight - app.clientHeight);
      return;
    }

    setScrollTopInstant(newEntry.offsetTop);
  }

  function setScrollTopInstant(top) {
    const previousBehavior = app.style.scrollBehavior;

    app.style.scrollBehavior = "auto";
    app.scrollTop = Math.max(0, top);
    app.style.scrollBehavior = previousBehavior;
  }

  function simulateLoadingDelay() {
    return new Promise((resolve) => {
      window.setTimeout(resolve, settings.simulatedDelayMs);
    });
  }

  function readInteractionSettings() {
    const styles = window.getComputedStyle(document.documentElement);

    return {
      initialCount: readIntegerToken(styles, "--load-initial-count", 6),
      pageSize: readIntegerToken(styles, "--load-page-size", 4),
      triggerEntryIndex: readIntegerToken(styles, "--load-trigger-entry-index", 5),
      simulatedDelayMs: readIntegerToken(styles, "--load-simulated-delay-ms", 1000),
    };
  }

  function readIntegerToken(styles, name, fallback) {
    const value = Number.parseInt(styles.getPropertyValue(name), 10);

    return Number.isFinite(value) && value > 0 ? value : fallback;
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

  function resizeContentInput(content) {
    content.style.blockSize = "auto";
    content.style.blockSize = `${content.scrollHeight}px`;
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
    const body = document.createElement("div");
    const content = document.createElement("div");
    const { data, ui } = sample;
    const { metadata } = data;
    const calendarDate = getCalendarDate(metadata.created_at);

    entry.className = "diary-entry";
    entry.dataset.entryId = metadata.id;
    entry.dataset.entryMode = ui.mode;
    body.className = "entry-body";
    date.className = "entry-date";
    date.dateTime = metadata.created_at;
    appendEntryDate(
      date,
      calendarDate,
      metadata.created_at,
      entriesByDate.get(calendarDate),
    );
    content.className = "entry-content";
    appendMarkdownParagraphs(content, data.content);

    entry.append(date, body);
    if (metadata.title) {
      const title = document.createElement("h2");
      title.className = "entry-title";
      title.textContent = metadata.title;
      body.append(title);
    }
    body.append(content);

    return entry;
  }

  function groupItemsByDate(items) {
    const years = new Map();

    items.forEach((item) => {
      const [year, month] = getCalendarDate(
        item.createdAt,
      ).split("-");
      let yearGroup = years.get(year);

      if (!yearGroup) {
        yearGroup = { year, months: new Map() };
        years.set(year, yearGroup);
      }
      if (!yearGroup.months.has(month)) {
        yearGroup.months.set(month, []);
      }
      yearGroup.months.get(month).push(item);
    });

    return [...years.values()].map((yearGroup) => ({
      year: yearGroup.year,
      months: [...yearGroup.months.entries()].map(([month, items]) => ({
        month,
        items,
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

  function appendEntryDate(container, date, createdAt, entriesOnDate) {
    const day = document.createElement("span");
    const time = document.createElement("span");

    day.className = "entry-day";
    day.textContent = date.slice(-2);

    container.append(day);

    if (entriesOnDate <= 1) {
      return;
    }

    time.className = "entry-time";
    time.textContent = createdAt.slice(11, 16);
    container.append(time);
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
