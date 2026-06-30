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

  const FALLBACK_PAGE_NAME = "Serein";
  const FUTURE_FEED_SORT_TIMESTAMP = "9999-12-31T23:59:59+00:00";
  const API_BASE = readApiBase();
  const dataAdapter = window.SereinData.createDataAdapter({ apiBase: API_BASE });
  window.SereinDataAdapter = dataAdapter;
  const settings = readInteractionSettings();
  const authState = {
    authenticated: false,
    initialized: false,
  };
  let draftCreatedAt = createLocalTimestamp();
  const loadState = {
    visibleStartIndex: 0,
    status: "idle",
    errorMessage: "",
    laterStatus: "complete",
    laterErrorMessage: "",
  };
  const feedState = {
    entries: [],
    olderCursor: null,
    newerCursor: null,
    hasOlder: false,
    hasNewer: false,
    atLatest: true,
    transition: "idle",
    dataStatus: "idle",
    dataErrorMessage: "",
    targetDate: null,
    jumpStatus: "idle",
    jumpErrorMessage: "",
  };
  const groupOpenState = new Map();
  const loadDebugState = {
    enabled: readLoadDebugPreference(),
    history: [],
    lastScrollProbeAt: 0,
  };
  const indexDebugState = {
    history: [],
  };
  let loadCheckAfterLayoutChangeRunning = false;
  let pendingLoadCheckAfterLayoutChange = false;
  let activeNewEntryContentControl = null;
  let pendingNewEntryMessage = "";
  let pendingSavedEntryId = null;
  let sidebarCalendarCursor = null;
  let calendarJumpSequence = 0;
  const sidebarCalendarDateState = {
    status: "idle",
    dates: [],
    errorMessage: "",
  };

  registerIndexDebugTools();
  void bootApplication();

  async function bootApplication() {
    initializePageNameState();
    renderLockScreen({ state: "checking" });

    try {
      const session = await dataAdapter.getSession();

      if (session.authenticated) {
        void startDiaryApplication();
        return;
      }

      renderLockScreen();
    } catch (error) {
      renderLockScreen({
        state: "error",
        message: createAuthErrorMessage(error),
      });
    }
  }

  async function startDiaryApplication() {
    if (authState.initialized) {
      renderFeed({ focusNewEntry: true, scrollToEnd: true });
      return;
    }

    authState.authenticated = true;
    authState.initialized = true;
    initializeEditorExperimentState();
    initializeLayoutDebugState();
    renderFeedLoading();
    await initializeLoadedWindow();
    renderFeed({ focusNewEntry: true, scrollToEnd: true });
    app.addEventListener("scroll", handleScroll, { passive: true });
    registerLoadDebugTools();
    registerLayoutDebugTools();
    registerEditorExperimentTools();
    createSidebarShell();
  }

  function renderLockScreen(options = {}) {
    const { state = "idle", message = "" } = options;
    const shell = document.createElement("section");
    const card = document.createElement("form");
    const title = document.createElement("h1");
    const passwordWrap = document.createElement("div");
    const password = document.createElement("input");
    const togglePassword = document.createElement("button");
    const actions = document.createElement("div");
    const submit = document.createElement("button");
    const retry = document.createElement("button");
    const status = document.createElement("p");
    const isChecking = state === "checking";
    const isError = state === "error";

    shell.className = "lock-screen";
    shell.setAttribute("aria-label", "Serein lock screen");
    card.className = "lock-card";
    title.className = "lock-title";
    title.textContent = normalizePageName(readPageNamePreference());
    passwordWrap.className = "lock-password-wrap";
    password.className = "lock-password";
    password.type = "password";
    password.name = "password";
    password.placeholder = "输入日记锁屏密码。";
    password.autocomplete = "current-password";
    password.setAttribute("aria-label", "锁屏密码");
    password.disabled = isChecking;
    togglePassword.className = "lock-password-toggle";
    togglePassword.type = "button";
    togglePassword.title = "显示密码";
    togglePassword.setAttribute("aria-label", "显示密码");
    togglePassword.setAttribute("aria-pressed", "false");
    togglePassword.disabled = isChecking;
    togglePassword.innerHTML = createEyeIconSvg();
    actions.className = "lock-actions";
    submit.className = "lock-submit";
    submit.type = "submit";
    submit.textContent = isChecking ? "检查中…" : "登录";
    submit.disabled = isChecking;
    retry.className = "lock-retry";
    retry.type = "button";
    retry.textContent = "重试连接";
    retry.hidden = !isError;
    status.className = "lock-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");
    status.textContent = isChecking ? "正在确认会话状态……" : message;

    togglePassword.addEventListener("click", () => {
      const nextVisible = password.type === "password";

      password.type = nextVisible ? "text" : "password";
      togglePassword.title = nextVisible ? "隐藏密码" : "显示密码";
      togglePassword.setAttribute("aria-label", nextVisible ? "隐藏密码" : "显示密码");
      togglePassword.setAttribute("aria-pressed", String(nextVisible));
      password.focus({ preventScroll: true });
    });
    card.addEventListener("submit", (event) => {
      event.preventDefault();
      void submitLockPassword(card, password, submit, status);
    });
    retry.addEventListener("click", () => {
      void bootApplication();
    });

    passwordWrap.append(password, togglePassword);
    actions.append(retry, submit);
    card.append(title, passwordWrap, actions, status);
    shell.append(card);
    app.replaceChildren(shell);

    if (!isChecking) {
      requestAnimationFrame(() => {
        password.focus({ preventScroll: true });
      });
    }
  }

  async function submitLockPassword(card, password, submit, status) {
    const value = password.value;

    if (!value) {
      status.textContent = "请输入密码。";
      password.focus({ preventScroll: true });
      return;
    }

    card.dataset.loading = "true";
    password.disabled = true;
    submit.disabled = true;
    submit.textContent = "验证中…";
    status.textContent = "正在验证……";

    try {
      const session = await dataAdapter.login(value);

      if (!session.authenticated) {
        throw new Error("登录未完成。");
      }

      void startDiaryApplication();
    } catch (error) {
      card.dataset.loading = "false";
      password.disabled = false;
      submit.disabled = false;
      submit.textContent = "登录";
      status.textContent = createAuthErrorMessage(error);
      password.select();
      password.focus({ preventScroll: true });
    }
  }

  function createAuthErrorMessage(error) {
    if (error?.status === 401) {
      return "密码不正确。";
    }

    return "无法连接 Serein 后端，请确认 API 服务和反向代理已启动。";
  }

  function readApiBase() {
    const meta = document.querySelector('meta[name="serein-api-base"]');
    const value = meta?.content?.trim() || "/api/v1";

    return value.replace(/\/$/u, "");
  }

  function createEyeIconSvg() {
    return [
      '<svg viewBox="0 0 24 24" aria-hidden="true">',
      '<path class="eye-outline" d="M3.8 12s2.9-5.1 8.2-5.1 8.2 5.1 8.2 5.1-2.9 5.1-8.2 5.1S3.8 12 3.8 12Z"></path>',
      '<circle class="eye-pupil" cx="12" cy="12" r="2.35"></circle>',
      '<path class="eye-slash" d="M5.2 18.8 18.8 5.2"></path>',
      "</svg>",
    ].join("");
  }

  function renderFeedLoading() {
    const feed = document.createElement("section");
    const loading = document.createElement("div");

    feed.className = "diary-feed is-loading";
    feed.setAttribute("aria-label", "Diary entries");
    loading.className = "load-control is-loading";
    loading.setAttribute("role", "status");
    loading.setAttribute("aria-live", "polite");
    loading.innerHTML = '<span class="load-control-spinner" aria-hidden="true"></span><span class="load-control-message">正在读取日记……</span>';
    feed.append(loading);
    app.replaceChildren(feed);
  }

  function renderFeed(options = {}) {
    const {
      focusNewEntry = false,
      scrollToEnd = false,
      scrollToDate = null,
      scrollToEntryId = null,
    } = options;
    const feed = document.createElement("section");
    const readingSamples = getReadingSamples();
    const entriesPerDate = countEntriesPerDate(readingSamples);
    const feedItems = createFeedItems(readingSamples);

    feed.className = "diary-feed";
    feed.dataset.status = feedState.dataStatus;
    feed.dataset.transition = feedState.transition;
    feed.setAttribute("aria-label", "Diary entries");
    feed.append(createLoadControl());
    if (isBackendDataSource() && feedState.dataStatus === "ready" && readingSamples.length === 0) {
      feed.append(createEmptyBackendNotice());
    }

    groupItemsByDate(feedItems).forEach((yearGroup) => {
      const year = createGroup("diary-year", yearGroup.year, `year:${yearGroup.year}`);

      yearGroup.months.forEach((monthGroup) => {
        const month = createGroup(
          "diary-month",
          monthGroup.month,
          `month:${yearGroup.year}-${monthGroup.month}`,
        );

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
    if (feedState.targetDate && !feedState.atLatest) {
      feed.append(createLoadLaterControl());
    }

    const layers = [feed];

    layers.push(createReturnToLatestButton());
    if (feedState.transition !== "idle") {
      layers.push(createFeedTransitionOverlay());
    }

    app.replaceChildren(...layers);
    updateReturnToLatestButtonVisibility();

    if (scrollToEnd) {
      requestAnimationFrame(() => {
        scrollToNewEntry();
        updateReturnToLatestButtonVisibility();
        window.setTimeout(() => {
          scrollToNewEntry();
          updateReturnToLatestButtonVisibility();
        }, 0);
      });
    }
    if (scrollToDate) {
      requestAnimationFrame(() => {
        scrollToDateEntry(scrollToDate);
      });
    }
    if (scrollToEntryId) {
      requestAnimationFrame(() => {
        scrollToEntry(scrollToEntryId);
        updateReturnToLatestButtonVisibility();
      });
    }
  }

  function createReturnToLatestButton() {
    const button = document.createElement("button");

    button.className = "window-mode-return";
    button.type = "button";
    button.title = "回到此刻";
    button.setAttribute("aria-label", "回到此刻");
    button.hidden = true;
    button.innerHTML = createDownArrowIconSvg();
    button.addEventListener("click", () => {
      void returnToLatestFeed();
    });
    return button;
  }

  function createFeedTransitionOverlay() {
    const overlay = document.createElement("div");
    const status = document.createElement("div");

    overlay.className = "feed-transition-overlay";
    overlay.setAttribute("aria-live", "polite");
    overlay.setAttribute("role", "status");
    status.className = "feed-transition-status";
    status.textContent = "加载中";
    overlay.append(status);
    return overlay;
  }

  function createDownArrowIconSvg() {
    return [
      '<svg viewBox="0 0 24 24" aria-hidden="true">',
      '<path d="M12 5v14"></path>',
      '<path d="m6 13 6 6 6-6"></path>',
      "</svg>",
    ].join("");
  }

  function createEmptyBackendNotice() {
    const notice = document.createElement("section");
    const title = document.createElement("p");
    const text = document.createElement("p");

    notice.className = "empty-backend-notice";
    notice.setAttribute("aria-label", "No saved diary entries");
    title.className = "empty-backend-title";
    title.textContent = "还没有已保存的日记";
    text.className = "empty-backend-text";
    text.textContent = "下面就是此刻。写完后，日记会出现在这条时间流里。";
    notice.append(title, text);
    return notice;
  }

  function getReadingSamples() {
    return getAllReadingSamples().slice(loadState.visibleStartIndex);
  }

  function getAllReadingSamples() {
    if (isBackendDataSource()) {
      return feedState.entries;
    }

    return window.SereinMockEntries
      .filter((sample) => sample.ui.mode === "reading")
      .slice()
      .sort((left, right) => (
        left.data.metadata.created_at.localeCompare(right.data.metadata.created_at)
      ));
  }

  function createFeedItems(readingSamples) {
    const items = readingSamples.map((sample) => ({
      type: "entry",
      createdAt: sample.data.metadata.created_at,
      sortAt: sample.data.metadata.created_at,
      sample,
    }));

    if (feedState.atLatest) {
      items.push({
        type: "new",
        createdAt: getNewEntryFeedTimestamp(readingSamples),
        sortAt: FUTURE_FEED_SORT_TIMESTAMP,
      });
    }

    return items.sort((left, right) => left.sortAt.localeCompare(right.sortAt));
  }

  function getNewEntryFeedTimestamp(readingSamples) {
    const latestEntry = readingSamples.at(-1);
    const latestEntryCreatedAt = latestEntry?.data?.metadata?.created_at || "";

    return latestEntryCreatedAt && latestEntryCreatedAt > draftCreatedAt
      ? latestEntryCreatedAt
      : draftCreatedAt;
  }

  async function initializeLoadedWindow() {
    if (isBackendDataSource()) {
      await initializeBackendLoadedWindow();
      return;
    }

    const total = getAllReadingSamples().length;

    loadState.visibleStartIndex = Math.max(0, total - settings.initialCount);
    loadState.status = loadState.visibleStartIndex === 0 ? "complete" : "idle";
    feedState.olderCursor = null;
    loadState.laterStatus = "complete";
    loadState.laterErrorMessage = "";
    feedState.newerCursor = null;
    feedState.hasOlder = false;
    feedState.hasNewer = false;
    feedState.atLatest = true;
    feedState.targetDate = null;
    feedState.jumpStatus = "idle";
    feedState.jumpErrorMessage = "";
    feedState.dataStatus = "ready";
    feedState.dataErrorMessage = "";
  }

  async function initializeBackendLoadedWindow() {
    feedState.dataStatus = "loading";
    feedState.dataErrorMessage = "";
    loadState.status = "loading";
    loadState.errorMessage = "";
    loadState.visibleStartIndex = 0;
    feedState.olderCursor = null;
    loadState.laterStatus = "complete";
    loadState.laterErrorMessage = "";
    feedState.newerCursor = null;
    feedState.hasOlder = false;
    feedState.hasNewer = false;
    feedState.atLatest = true;
    feedState.targetDate = null;
    feedState.jumpStatus = "idle";
    feedState.jumpErrorMessage = "";

    try {
      const page = await dataAdapter.listEntries({ limit: settings.initialCount });
      const samples = await loadEntryDetailsForSummaries(page.items || []);

      feedState.entries = samples;
      feedState.dataStatus = "ready";
      feedState.hasOlder = Boolean(page.page?.has_older);
      feedState.hasNewer = Boolean(page.page?.has_newer);
      feedState.atLatest = !feedState.hasNewer;
      loadState.status = feedState.hasOlder ? "idle" : "complete";
      loadState.laterStatus = feedState.hasNewer ? "idle" : "complete";
      feedState.olderCursor = page.page?.older_cursor || null;
      feedState.newerCursor = page.page?.newer_cursor || null;
    } catch (error) {
      feedState.entries = [];
      feedState.dataStatus = "error";
      feedState.dataErrorMessage = createDataErrorMessage(error);
      loadState.status = "error";
      loadState.errorMessage = feedState.dataErrorMessage;
    }
  }

  async function loadEntryDetailsForSummaries(items) {
    const details = await Promise.all(
      items.map((item) => dataAdapter.getEntry(item.id)),
    );

    return details.map(apiEntryToSample);
  }

  function apiEntryToSample(entry) {
    return {
      ui: {
        mode: "reading",
        cursor: entry.cursor || null,
      },
      data: {
        metadata: {
          schema_version: 1,
          id: entry.id,
          created_at: entry.created_at,
          ...(entry.title ? { title: entry.title } : {}),
          ...(entry.deleted ? { deleted_at: entry.deleted_at || true } : {}),
        },
        content: entry.content || "",
        comments: {
          schema_version: 1,
          comments: entry.comments || [],
        },
        mediaManifest: {
          schema_version: 1,
          media: entry.media || [],
        },
      },
    };
  }

  function isBackendDataSource() {
    return dataAdapter.source === "backend";
  }

  function createDataErrorMessage(error) {
    if (error?.code) {
      return `${error.code}：${error.message}`;
    }

    return error instanceof Error ? error.message : "未知错误";
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
    const content = document.createElement(isTiptapExperimentEnabled() ? "div" : "textarea");
    const message = document.createElement("p");
    const header = document.createElement("div");
    const actions = document.createElement("div");
    const toolbar = document.createElement("div");
    const cancel = document.createElement("button");
    const draftStatus = document.createElement("span");
    const save = document.createElement("button");

    const contentControl = createNewEntryContentControl(content, message, toolbar);
    activeNewEntryContentControl = contentControl;

    form.className = "new-entry-form";
    title.className = "new-entry-title-input";
    title.name = "title";
    title.placeholder = "标题";
    title.setAttribute("aria-label", "Diary title");
    content.className = "new-entry-content-input";
    content.setAttribute("aria-label", "Diary content");
    if (content instanceof HTMLTextAreaElement) {
      content.name = "content";
      content.placeholder = "写下此刻……";
      content.rows = 1;
    } else {
      content.classList.add("tiptap-editor-shell");
      content.dataset.placeholder = "写下此刻……";
    }
    message.className = "new-entry-message";
    message.setAttribute("role", "status");
    message.textContent = pendingNewEntryMessage;
    pendingNewEntryMessage = "";
    header.className = "new-entry-header";
    actions.className = "new-entry-actions";
    toolbar.className = "tiptap-toolbar";
    toolbar.setAttribute("aria-label", "Tiptap formatting toolbar");
    toolbar.hidden = content instanceof HTMLTextAreaElement;
    cancel.className = "new-entry-cancel";
    cancel.type = "button";
    cancel.textContent = "×";
    cancel.title = "取消保存";
    cancel.setAttribute("aria-label", "取消保存");
    draftStatus.className = "new-entry-draft-status";
    draftStatus.title = "草稿状态（暂未启用）";
    draftStatus.setAttribute("role", "img");
    draftStatus.setAttribute("aria-label", "草稿状态（暂未启用）");
    draftStatus.setAttribute("aria-hidden", "true");
    save.className = "new-entry-save";
    save.type = "submit";
    save.textContent = "✓";
    save.title = "保存日记";
    save.setAttribute("aria-label", "保存日记");

    contentControl.mount();

    cancel.addEventListener("click", () => {
      form.reset();
      contentControl.clear();
      message.textContent = "已清空未保存内容。";
      title.focus({ preventScroll: true });
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();

      void handleNewEntrySubmit({
        title,
        contentControl,
        message,
        form,
        cancel,
        save,
      });
    });

    async function handleNewEntrySubmit(controls) {
      const rawBody = controls.contentControl.readMarkdown();
      const body = rawBody.trim();
      const titleValue = controls.title.value.trim();

      if (!body) {
        message.textContent = "请先写下一些内容。";
        contentControl.focus();
        return;
      }

      if (isBackendDataSource()) {
        setNewEntrySavingState(controls, true);
        message.textContent = "正在保存……";
        let shouldRestoreSavingState = true;
        try {
          const created = await dataAdapter.createEntry({
            title: titleValue,
            content: rawBody,
          });
          form.reset();
          contentControl.clear();
          insertCreatedEntryIntoFeed(created);
          invalidateSidebarCalendarDates();
          draftCreatedAt = createLocalTimestamp();
          pendingNewEntryMessage = "已保存。";
          pendingSavedEntryId = created.id;
          renderFeed({ scrollToEntryId: created.id });
          shouldRestoreSavingState = false;
        } catch (error) {
          message.textContent = `保存失败：${createDataErrorMessage(error)}`;
          contentControl.focus();
        } finally {
          if (shouldRestoreSavingState) {
            setNewEntrySavingState(controls, false);
          }
        }
        return;
      }

      addStaticEntry(titleValue, body);
      renderFeed({ focusNewEntry: true, scrollToEnd: true });
    }

    actions.append(draftStatus, cancel, save);
    header.append(title);
    form.append(header, toolbar, content, message, actions);
    body.append(form);
    area.append(date, body);
    if (focusNewEntry) {
      requestAnimationFrame(() => {
        contentControl.resize();
        contentControl.focus();
      });
    } else {
      contentControl.resize();
    }

    return area;
  }

  function insertCreatedEntryIntoFeed(entry) {
    mergeFeedSamples([apiEntryToSample(entry)]);
    feedState.dataStatus = "ready";
    feedState.dataErrorMessage = "";
    feedState.targetDate = null;
    feedState.jumpStatus = "idle";
    feedState.jumpErrorMessage = "";
    feedState.hasNewer = false;
    feedState.atLatest = true;
    feedState.newerCursor = null;
    loadState.laterStatus = "complete";
    loadState.laterErrorMessage = "";
    debugLoad("created entry inserted into feed", {
      entryId: entry.id,
      createdAt: entry.created_at,
      totalEntries: feedState.entries.length,
    });
  }

  function invalidateSidebarCalendarDates() {
    sidebarCalendarDateState.status = "idle";
    sidebarCalendarDateState.dates = [];
    sidebarCalendarDateState.errorMessage = "";
  }

  function setNewEntrySavingState(controls, saving) {
    const isSaving = Boolean(saving);

    controls.title.disabled = isSaving;
    controls.cancel.disabled = isSaving;
    controls.save.disabled = isSaving;
    controls.contentControl.setDisabled?.(isSaving);
    controls.save.setAttribute("aria-busy", String(isSaving));
  }

  function createNewEntryContentControl(content, message, toolbar) {
    if (content instanceof HTMLTextAreaElement) {
      return createTextareaContentControl(content);
    }

    return createTiptapContentControl(content, message, toolbar);
  }

  function createTextareaContentControl(content) {
    return {
      kind: "textarea",
      mount() {
        content.addEventListener("input", () => {
          resizeContentInput(content);
        });
      },
      readMarkdown() {
        return content.value;
      },
      clear() {
        content.value = "";
        resizeContentInput(content);
      },
      setDisabled(disabled) {
        content.disabled = Boolean(disabled);
      },
      focus() {
        content.focus({ preventScroll: true });
      },
      resize() {
        resizeContentInput(content);
      },
    };
  }

  function createTiptapContentControl(content, message, toolbar) {
    const state = {
      editor: null,
      loadError: null,
    };

    return {
      kind: "tiptap",
      mount() {
        content.setAttribute("role", "textbox");
        content.setAttribute("aria-multiline", "true");
        content.tabIndex = 0;
        message.textContent = "Tiptap demo 正在加载……";
        renderTiptapToolbar(toolbar, state);
        void initializeTiptapEditor(content, state, message, toolbar);
      },
      readMarkdown() {
        if (state.editor) {
          return exportTiptapMarkdown(state.editor);
        }

        return content.textContent || "";
      },
      clear() {
        if (state.editor) {
          state.editor.commands.clearContent(true);
          return;
        }

        content.textContent = "";
      },
      setDisabled(disabled) {
        if (state.editor) {
          state.editor.setEditable(!disabled);
          return;
        }

        content.contentEditable = disabled ? "false" : "true";
      },
      focus() {
        if (state.editor) {
          state.editor.commands.focus("end");
          return;
        }

        content.focus({ preventScroll: true });
      },
      resize() {
        // Tiptap grows with content through normal document flow.
      },
    };
  }

  async function initializeTiptapEditor(element, state, message, toolbar) {
    try {
      const [{ Editor }, { default: StarterKit }, { default: Placeholder }] = await Promise.all([
        import("https://esm.sh/@tiptap/core@2.11.7"),
        import("https://esm.sh/@tiptap/starter-kit@2.11.7"),
        import("https://esm.sh/@tiptap/extension-placeholder@2.11.7"),
      ]);

      state.editor = new Editor({
        element,
        extensions: [
          StarterKit.configure({
            heading: {
              levels: [2, 3],
            },
          }),
          Placeholder.configure({
            placeholder: element.dataset.placeholder || "写下此刻……",
          }),
        ],
        content: "",
        editorProps: {
          attributes: {
            class: "tiptap-prose",
          },
        },
        onCreate() {
          updateTiptapToolbarState(toolbar, state.editor);
        },
        onSelectionUpdate() {
          updateTiptapToolbarState(toolbar, state.editor);
        },
        onUpdate() {
          updateTiptapToolbarState(toolbar, state.editor);
        },
      });
      updateTiptapToolbarState(toolbar, state.editor);
      message.textContent = "Tiptap demo 已启用；当前仅验证前端输入和 Markdown 输出。";
    } catch (error) {
      state.loadError = error;
      element.contentEditable = "true";
      element.classList.add("tiptap-editor-fallback");
      message.textContent = "Tiptap demo 加载失败，已回退为浏览器原生输入区域。";
      console.warn("[Serein editor] Tiptap demo failed to load.", error);
    }
  }

  function renderTiptapToolbar(toolbar, state) {
    const groups = [
      [
        { label: "P", title: "段落", command: (editor) => editor.chain().focus().setParagraph().run(), active: (editor) => editor.isActive("paragraph") },
        { label: "H2", title: "二级标题", command: (editor) => editor.chain().focus().toggleHeading({ level: 2 }).run(), active: (editor) => editor.isActive("heading", { level: 2 }) },
        { label: "H3", title: "三级标题", command: (editor) => editor.chain().focus().toggleHeading({ level: 3 }).run(), active: (editor) => editor.isActive("heading", { level: 3 }) },
      ],
      [
        { label: "B", title: "粗体", command: (editor) => editor.chain().focus().toggleBold().run(), active: (editor) => editor.isActive("bold") },
        { label: "I", title: "斜体", command: (editor) => editor.chain().focus().toggleItalic().run(), active: (editor) => editor.isActive("italic") },
        { label: "S", title: "删除线", command: (editor) => editor.chain().focus().toggleStrike().run(), active: (editor) => editor.isActive("strike") },
        { label: "`", title: "行内代码", command: (editor) => editor.chain().focus().toggleCode().run(), active: (editor) => editor.isActive("code") },
      ],
      [
        { label: "•", title: "无序列表", command: (editor) => editor.chain().focus().toggleBulletList().run(), active: (editor) => editor.isActive("bulletList") },
        { label: "1.", title: "有序列表", command: (editor) => editor.chain().focus().toggleOrderedList().run(), active: (editor) => editor.isActive("orderedList") },
        { label: "❝", title: "引用", command: (editor) => editor.chain().focus().toggleBlockquote().run(), active: (editor) => editor.isActive("blockquote") },
        { label: "{ }", title: "代码块", command: (editor) => editor.chain().focus().toggleCodeBlock().run(), active: (editor) => editor.isActive("codeBlock") },
      ],
      [
        { label: "↶", title: "撤销", command: (editor) => editor.chain().focus().undo().run() },
        { label: "↷", title: "重做", command: (editor) => editor.chain().focus().redo().run() },
      ],
    ];

    toolbar.replaceChildren();
    groups.forEach((group) => {
      const groupElement = document.createElement("div");

      groupElement.className = "tiptap-toolbar-group";
      group.forEach((item) => {
        const button = document.createElement("button");

        button.className = "tiptap-toolbar-button";
        button.type = "button";
        button.textContent = item.label;
        button.title = item.title;
        button.setAttribute("aria-label", item.title);
        button.tabIndex = -1;
        button.disabled = true;
        button.addEventListener("click", () => {
          if (!state.editor) {
            return;
          }

          item.command(state.editor);
          updateTiptapToolbarState(toolbar, state.editor);
        });
        groupElement.append(button);
      });
      toolbar.append(groupElement);
    });
  }

  function updateTiptapToolbarState(toolbar, editor) {
    if (!toolbar || !editor) {
      return;
    }

    [...toolbar.querySelectorAll(".tiptap-toolbar-button")].forEach((button) => {
      button.disabled = false;
    });

    setToolbarButtonState(toolbar, "段落", editor.isActive("paragraph"));
    setToolbarButtonState(toolbar, "二级标题", editor.isActive("heading", { level: 2 }));
    setToolbarButtonState(toolbar, "三级标题", editor.isActive("heading", { level: 3 }));
    setToolbarButtonState(toolbar, "粗体", editor.isActive("bold"));
    setToolbarButtonState(toolbar, "斜体", editor.isActive("italic"));
    setToolbarButtonState(toolbar, "删除线", editor.isActive("strike"));
    setToolbarButtonState(toolbar, "行内代码", editor.isActive("code"));
    setToolbarButtonState(toolbar, "无序列表", editor.isActive("bulletList"));
    setToolbarButtonState(toolbar, "有序列表", editor.isActive("orderedList"));
    setToolbarButtonState(toolbar, "引用", editor.isActive("blockquote"));
    setToolbarButtonState(toolbar, "代码块", editor.isActive("codeBlock"));
  }

  function setToolbarButtonState(toolbar, label, isActive) {
    const button = [...toolbar.querySelectorAll(".tiptap-toolbar-button")]
      .find((candidate) => candidate.getAttribute("aria-label") === label);

    if (button) {
      button.setAttribute("aria-pressed", String(Boolean(isActive)));
    }
  }

  function exportTiptapMarkdown(editor) {
    const json = editor.getJSON();

    return tiptapNodeToMarkdown(json).trim();
  }

  function tiptapNodeToMarkdown(node) {
    if (!node) {
      return "";
    }

    if (node.type === "doc") {
      return (node.content || [])
        .map(tiptapNodeToMarkdown)
        .filter(Boolean)
        .join("\n\n");
    }

    if (node.type === "paragraph") {
      return tiptapInlineContentToMarkdown(node.content || []);
    }

    if (node.type === "heading") {
      const level = Math.min(Math.max(node.attrs?.level || 2, 1), 6);
      const text = tiptapInlineContentToMarkdown(node.content || []);

      return `${"#".repeat(level)} ${text}`;
    }

    if (node.type === "blockquote") {
      return tiptapNodeChildrenToMarkdown(node)
        .split("\n")
        .map((line) => `> ${line}`)
        .join("\n");
    }

    if (node.type === "bulletList") {
      return (node.content || [])
        .map((child) => `- ${tiptapNodeToMarkdown(child)}`)
        .join("\n");
    }

    if (node.type === "orderedList") {
      return (node.content || [])
        .map((child, index) => `${index + 1}. ${tiptapNodeToMarkdown(child)}`)
        .join("\n");
    }

    if (node.type === "listItem") {
      return tiptapNodeChildrenToMarkdown(node);
    }

    if (node.type === "codeBlock") {
      return "```\n" + tiptapInlineContentToMarkdown(node.content || []) + "\n```";
    }

    if (node.type === "horizontalRule") {
      return "---";
    }

    return tiptapNodeChildrenToMarkdown(node);
  }

  function tiptapNodeChildrenToMarkdown(node) {
    return (node.content || [])
      .map(tiptapNodeToMarkdown)
      .filter(Boolean)
      .join("\n");
  }

  function tiptapInlineContentToMarkdown(content) {
    return content.map((node) => {
      if (node.type === "text") {
        return applyTiptapMarks(escapeMarkdownText(node.text || ""), node.marks || []);
      }

      if (node.type === "hardBreak") {
        return "\n";
      }

      return tiptapNodeToMarkdown(node);
    }).join("");
  }

  function applyTiptapMarks(text, marks) {
    return marks.reduce((value, mark) => {
      if (mark.type === "bold") {
        return `**${value}**`;
      }
      if (mark.type === "italic") {
        return `*${value}*`;
      }
      if (mark.type === "strike") {
        return `~~${value}~~`;
      }
      if (mark.type === "code") {
        return "`" + value.replace(/`/g, "\\`") + "`";
      }
      if (mark.type === "link") {
        return `[${value}](${mark.attrs?.href || ""})`;
      }

      return value;
    }, text);
  }

  function escapeMarkdownText(text) {
    return text.replace(/\\/g, "\\\\");
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
      message.textContent = feedState.dataStatus === "loading"
        ? "正在读取日记……"
        : "正在拉取更早的日记……";
      control.append(spinner, message);
    } else if (loadState.status === "error") {
      const retry = document.createElement("button");
      const isInitialBackendError = (
        isBackendDataSource()
        && feedState.dataStatus === "error"
        && feedState.entries.length === 0
      );
      const isWindowJumpError = (
        Boolean(feedState.targetDate)
        && feedState.jumpStatus === "error"
        && Boolean(feedState.targetDate)
      );

      message.textContent = isWindowJumpError
        ? `无法跳转日期：${loadState.errorMessage}`
        : isInitialBackendError
        ? `无法读取日记：${loadState.errorMessage}`
        : `拉取信息失败：${loadState.errorMessage}`;
      retry.className = "load-control-retry";
      retry.type = "button";
      retry.textContent = isInitialBackendError ? "重新读取" : "重试";
      retry.addEventListener("click", () => {
        debugLoad("retry clicked");
        if (isWindowJumpError) {
          void jumpToCalendarDate(feedState.targetDate);
          return;
        }
        if (isBackendDataSource() && feedState.dataStatus === "error") {
          void retryBackendInitialLoad();
          return;
        }
        void loadEarlierEntries({ source: "retry" });
      });
      control.append(message, retry);
    } else if (loadState.status === "complete") {
      message.textContent = "这里是日记的起点。";
      control.append(message);
    } else {
      control.hidden = true;
      control.append(message);
    }

    return control;
  }

  function createLoadLaterControl() {
    const control = document.createElement("div");
    const spinner = document.createElement("span");
    const message = document.createElement("span");

    control.className = `load-control load-later-control is-${loadState.laterStatus}`;
    control.setAttribute("role", "status");
    control.setAttribute("aria-live", "polite");
    spinner.className = "load-control-spinner";
    spinner.setAttribute("aria-hidden", "true");
    message.className = "load-control-message";

    if (loadState.laterStatus === "loading") {
      message.textContent = "正在拉取更晚的日记……";
      control.append(spinner, message);
    } else if (loadState.laterStatus === "error") {
      const retry = document.createElement("button");

      message.textContent = `拉取信息失败：${loadState.laterErrorMessage}`;
      retry.className = "load-control-retry";
      retry.type = "button";
      retry.textContent = "重试";
      retry.addEventListener("click", () => {
        void loadLaterEntries({ source: "retry" });
      });
      control.append(message, retry);
    } else if (loadState.laterStatus === "complete") {
      message.textContent = "已加载此窗口之后的日记内容";
      control.append(message);
    } else {
      control.hidden = true;
      control.append(message);
    }

    return control;
  }

  function handleScroll() {
    const verbose = shouldLogScrollProbe();

    updateReturnToLatestButtonVisibility();

    if (verbose) {
      debugLoad("scroll probe", {
        reason: "throttled-scroll-state",
        distanceToBottom: Math.round(app.scrollHeight - app.scrollTop - app.clientHeight),
      });
    }

    if (shouldLoadEarlierEntries({ source: "scroll", verbose })) {
      debugLoad("scroll triggered earlier-load");
      void loadEarlierEntries({ source: "scroll" });
    }

    if (shouldLoadLaterEntries({ source: "scroll", verbose })) {
      debugLoad("scroll triggered later-load");
      void loadLaterEntries({ source: "scroll" });
    }
  }

  function updateReturnToLatestButtonVisibility() {
    const button = app.querySelector(".window-mode-return");

    if (!button) {
      return;
    }

    button.hidden = !shouldShowReturnToLatestButton();
  }

  function shouldShowReturnToLatestButton() {
    if (feedState.transition !== "idle") {
      return false;
    }

    const newEntry = app.querySelector(".new-entry");

    if (!newEntry) {
      return true;
    }

    const appTop = app.getBoundingClientRect().top;
    const newEntryTop = newEntry.getBoundingClientRect().top;

    return Math.abs(newEntryTop - appTop) > settings.returnButtonTopTolerance;
  }

  function scheduleLoadCheckAfterLayoutChange() {
    pendingLoadCheckAfterLayoutChange = true;
    debugLoad("scheduled post-layout load check");

    requestAnimationFrame(() => {
      void loadEarlierEntriesUntilStable();
    });
  }

  async function loadEarlierEntriesUntilStable() {
    if (loadCheckAfterLayoutChangeRunning) {
      debugLoad("post-layout load check skipped because another check is running");
      return;
    }

    loadCheckAfterLayoutChangeRunning = true;
    debugLoad("post-layout load check started");

    try {
      let attempts = 0;
      const maxAttempts = 20;

      pendingLoadCheckAfterLayoutChange = false;

      while (attempts < maxAttempts && shouldLoadEarlierEntriesAfterLayoutChange({
        source: "post-layout",
        verbose: true,
      })) {
        attempts += 1;
        debugLoad("post-layout load attempt", { attempt: attempts, maxAttempts });

        const loaded = await loadEarlierEntries({ source: "post-layout", attempt: attempts });
        if (!loaded) {
          debugLoad("post-layout load loop stopped because load returned false", {
            attempt: attempts,
          });
          break;
        }

        await waitForNextFrame();
      }

      if (attempts >= maxAttempts) {
        debugLoad("post-layout load loop reached safety limit", { maxAttempts });
      } else if (loadState.status === "loading") {
        pendingLoadCheckAfterLayoutChange = true;
        debugLoad("post-layout load check paused until current load completes", { attempts });
      } else {
        debugLoad("post-layout load check reached stable state", { attempts });
      }
    } finally {
      loadCheckAfterLayoutChangeRunning = false;
      debugLoad("post-layout load check finished");
    }
  }

  function shouldLoadEarlierEntries(options = {}) {
    const { source = "unknown", verbose = false } = options;

    if (feedState.transition !== "idle") {
      debugShouldLoad(false, "blocked-by-feed-transition", {
        source,
        verbose,
        direction: "earlier",
        transition: feedState.transition,
      });
      return false;
    }

    if (loadState.status === "loading" || loadState.status === "complete") {
      debugShouldLoad(false, "blocked-by-status", { source, verbose, direction: "earlier" });
      return false;
    }

    if (isBackendDataSource()) {
      if (!feedState.olderCursor) {
        loadState.status = "complete";
        debugShouldLoad(false, "backend-no-earlier-content", {
          source,
          verbose,
          direction: "earlier",
        });
        renderFeed();
        return false;
      }
    } else if (loadState.visibleStartIndex <= 0) {
      loadState.status = "complete";
      debugShouldLoad(false, "no-earlier-content", { source, verbose, direction: "earlier" });
      renderFeed();
      return false;
    }

    const entries = getVisibleEntries();
    if (entries.length === 0) {
      const shouldLoad = app.scrollTop <= app.clientHeight;

      debugShouldLoad(shouldLoad, "no-visible-entries", {
        source,
        verbose,
        direction: "earlier",
        scrollTop: app.scrollTop,
        clientHeight: app.clientHeight,
      });
      return shouldLoad;
    }

    const triggerIndex = Math.min(
      Math.max(settings.triggerEntryIndex, 1),
      entries.length,
    ) - 1;
    const triggerEntry = entries[triggerIndex];

    const shouldLoad = app.scrollTop <= triggerEntry.offsetTop;

    debugShouldLoad(shouldLoad, "trigger-entry-threshold", {
      source,
      verbose,
      direction: "earlier",
      triggerIndex,
      triggerEntryId: triggerEntry.dataset.entryId,
      triggerOffsetTop: triggerEntry.offsetTop,
      scrollTop: app.scrollTop,
      visibleEntryCount: entries.length,
    });
    return shouldLoad;
  }

  function shouldLoadEarlierEntriesAfterLayoutChange(options = {}) {
    const { source = "unknown", verbose = false } = options;

    if (loadState.status === "loading" || loadState.status === "complete") {
      debugShouldLoad(false, "blocked-by-status", { source, verbose, direction: "earlier" });
      return false;
    }

    if (isBackendDataSource()) {
      if (!feedState.olderCursor) {
        loadState.status = "complete";
        debugShouldLoad(false, "backend-no-earlier-content", {
          source,
          verbose,
          direction: "earlier",
        });
        renderFeed();
        return false;
      }
    } else if (loadState.visibleStartIndex <= 0) {
      loadState.status = "complete";
      debugShouldLoad(false, "no-earlier-content", { source, verbose, direction: "earlier" });
      renderFeed();
      return false;
    }

    const overflow = app.scrollHeight - app.clientHeight;
    const shouldLoad = overflow <= settings.layoutFillTolerance;

    debugShouldLoad(shouldLoad, "layout-fill-threshold", {
      source,
      verbose,
      direction: "earlier",
      scrollHeight: app.scrollHeight,
      clientHeight: app.clientHeight,
      overflow,
      layoutFillTolerance: settings.layoutFillTolerance,
    });
    return shouldLoad;
  }

  function shouldLoadLaterEntries(options = {}) {
    const { source = "unknown", verbose = false } = options;

    if (feedState.transition !== "idle") {
      debugShouldLoad(false, "blocked-by-feed-transition", {
        source,
        verbose,
        direction: "later",
        transition: feedState.transition,
      });
      return false;
    }

    if (!feedState.hasNewer || feedState.atLatest) {
      debugShouldLoad(false, "no-newer-window-content", { source, verbose, direction: "later" });
      return false;
    }
    if (loadState.laterStatus === "loading" || loadState.laterStatus === "complete") {
      debugShouldLoad(false, "later-blocked-by-status", {
        source,
        verbose,
        direction: "later",
        laterStatus: loadState.laterStatus,
      });
      return false;
    }
    if (!feedState.newerCursor) {
      loadState.laterStatus = "complete";
      debugShouldLoad(false, "no-later-content", { source, verbose, direction: "later" });
      renderFeed();
      return false;
    }

    const distanceToBottom = app.scrollHeight - app.scrollTop - app.clientHeight;
    const threshold = Math.max(app.clientHeight * 0.25, settings.laterTriggerDistance);
    const shouldLoad = distanceToBottom <= threshold;

    debugShouldLoad(shouldLoad, "later-bottom-threshold", {
      source,
      verbose,
      direction: "later",
      distanceToBottom: Math.round(distanceToBottom),
      threshold: Math.round(threshold),
    });
    return shouldLoad;
  }

  async function loadEarlierEntries(options = {}) {
    const { source = "unknown", attempt = null } = options;

    if (loadState.status === "loading" || loadState.status === "complete") {
      debugLoad("loadEarlierEntries blocked", { source, attempt });
      return false;
    }

    const anchor = getScrollAnchor();

    debugLoad("loadEarlierEntries started", { source, attempt, anchor });

    loadState.status = "loading";
    loadState.errorMessage = "";
    renderFeedRestoringAnchor(anchor);
    debugLoad("loading control rendered", { source, attempt, anchor });

    if (isBackendDataSource()) {
      return loadEarlierBackendEntries({ source, attempt, anchor });
    }

    try {
      await simulateLoadingDelay();

      if (window.SereinMockLoadFailure === true) {
        throw new Error("模拟网络异常");
      }

      /*
       * Re-read the anchor after the loading control has been rendered.
       * Otherwise the final render would restore the pre-loading position and
       * visibly jump by the height of the temporary loading bar.
       */
      const anchorBeforeFinalRender = getScrollAnchor() || anchor;
      const previousVisibleStartIndex = loadState.visibleStartIndex;

      loadState.visibleStartIndex = Math.max(
        0,
        loadState.visibleStartIndex - settings.pageSize,
      );
      loadState.status = loadState.visibleStartIndex === 0 ? "complete" : "idle";
      renderFeedRestoringAnchor(anchorBeforeFinalRender);
      debugLoad("loadEarlierEntries completed", {
        source,
        attempt,
        previousVisibleStartIndex,
        nextVisibleStartIndex: loadState.visibleStartIndex,
        anchorBeforeFinalRender,
      });
      runPendingLoadCheckAfterLoadSettles();
      return true;
    } catch (error) {
      /*
       * The error control can also differ in height from the loading control,
       * so restore from the currently visible anchor here as well.
       */
      const anchorBeforeErrorRender = getScrollAnchor() || anchor;

      loadState.status = "error";
      loadState.errorMessage = error instanceof Error ? error.message : "未知错误";
      renderFeedRestoringAnchor(anchorBeforeErrorRender);
      debugLoad("loadEarlierEntries failed", {
        source,
        attempt,
        errorMessage: loadState.errorMessage,
        anchorBeforeErrorRender,
      });
      runPendingLoadCheckAfterLoadSettles();
      return false;
    }
  }

  async function loadEarlierBackendEntries(options = {}) {
    const { source = "unknown", attempt = null, anchor = null } = options;

    try {
      if (!feedState.olderCursor) {
        loadState.status = "complete";
        renderFeedRestoringAnchor(anchor);
        return false;
      }

      const page = await dataAdapter.listEntries({
        limit: settings.pageSize,
        olderThan: feedState.olderCursor,
      });
      const anchorBeforeFinalRender = getScrollAnchor() || anchor;
      const previousLoadedEntries = feedState.entries.length;
      const earlierSamples = await loadEntryDetailsForSummaries(page.items || []);
      const existingIds = new Set(feedState.entries.map((sample) => sample.data.metadata.id));
      const newSamples = earlierSamples.filter((sample) => (
        !existingIds.has(sample.data.metadata.id)
      ));

      feedState.entries = sortSamplesChronologically([...newSamples, ...feedState.entries]);
      feedState.dataStatus = "ready";
      feedState.hasOlder = Boolean(page.page?.has_older);
      loadState.status = feedState.hasOlder ? "idle" : "complete";
      feedState.olderCursor = page.page?.older_cursor || null;
      trimFeedWindowAroundAnchor(anchorBeforeFinalRender);
      renderFeedRestoringAnchor(anchorBeforeFinalRender);
      debugLoad("backend earlier entries loaded", {
        source,
        attempt,
        previousLoadedEntries,
        nextLoadedEntries: feedState.entries.length,
        loadedThisPage: newSamples.length,
        hasOlder: page.page?.has_older,
        olderCursor: feedState.olderCursor,
      });
      runPendingLoadCheckAfterLoadSettles();
      return newSamples.length > 0 || Boolean(page.page?.has_older);
    } catch (error) {
      const anchorBeforeErrorRender = getScrollAnchor() || anchor;

      loadState.status = "error";
      loadState.errorMessage = createDataErrorMessage(error);
      renderFeedRestoringAnchor(anchorBeforeErrorRender);
      debugLoad("backend earlier load failed", {
        source,
        attempt,
        errorMessage: loadState.errorMessage,
      });
      runPendingLoadCheckAfterLoadSettles();
      return false;
    }
  }

  async function loadLaterEntries(options = {}) {
    const { source = "unknown", attempt = null } = options;

    if (!feedState.hasNewer || feedState.atLatest) {
      return false;
    }
    if (loadState.laterStatus === "loading" || loadState.laterStatus === "complete") {
      debugLoad("loadLaterEntries blocked", { source, attempt });
      return false;
    }

    const anchor = getScrollAnchor();

    loadState.laterStatus = "loading";
    loadState.laterErrorMessage = "";
    renderFeedRestoringAnchor(anchor);

    try {
      if (!feedState.newerCursor) {
        loadState.laterStatus = "complete";
        renderFeedRestoringAnchor(anchor);
        return false;
      }

      const page = await dataAdapter.listEntries({
        limit: settings.pageSize,
        newerThan: feedState.newerCursor,
      });
      const anchorBeforeFinalRender = getScrollAnchor() || anchor;
      const laterSamples = await loadEntryDetailsForSummaries(page.items || []);
      const previousLoadedEntries = feedState.entries.length;

      mergeFeedSamples(laterSamples);
      feedState.hasNewer = Boolean(page.page?.has_newer);
      feedState.atLatest = !feedState.hasNewer;
      loadState.laterStatus = feedState.hasNewer ? "idle" : "complete";
      feedState.newerCursor = page.page?.newer_cursor || null;
      trimFeedWindowAroundAnchor(anchorBeforeFinalRender);
      renderFeedRestoringAnchor(anchorBeforeFinalRender);
      debugLoad("later entries loaded", {
        source,
        attempt,
        previousLoadedEntries,
        nextLoadedEntries: feedState.entries.length,
        loadedThisPage: laterSamples.length,
        hasNewer: page.page?.has_newer,
        newerCursor: feedState.newerCursor,
      });
      return laterSamples.length > 0 || Boolean(page.page?.has_newer);
    } catch (error) {
      const anchorBeforeErrorRender = getScrollAnchor() || anchor;

      loadState.laterStatus = "error";
      loadState.laterErrorMessage = createDataErrorMessage(error);
      renderFeedRestoringAnchor(anchorBeforeErrorRender);
      debugLoad("later load failed", {
        source,
        attempt,
        errorMessage: loadState.laterErrorMessage,
      });
      return false;
    }
  }

  async function retryBackendInitialLoad() {
    renderFeedLoading();
    await initializeBackendLoadedWindow();
    renderFeed({ focusNewEntry: true, scrollToEnd: true });
  }

  async function returnToLatestFeed() {
    calendarJumpSequence += 1;
    const jumpSequence = calendarJumpSequence;
    const transitionDelay = wait(settings.jumpTransitionMinWaitMs);

    feedState.transition = "leaving";
    feedState.jumpStatus = "loading";
    feedState.jumpErrorMessage = "";
    renderFeed();
    await initializeLoadedWindow();
    await transitionDelay;
    if (jumpSequence !== calendarJumpSequence) {
      return;
    }
    feedState.transition = "entering";
    renderFeed({ focusNewEntry: true, scrollToEnd: true });
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        feedState.transition = "idle";
        const feed = app.querySelector(".diary-feed");
        if (feed) {
          feed.dataset.transition = "idle";
        }
        const overlay = app.querySelector(".feed-transition-overlay");
        overlay?.remove();
        updateReturnToLatestButtonVisibility();
      });
    });
  }

  function mergeFeedSamples(samples) {
    const byId = new Map(
      feedState.entries.map((sample) => [sample.data.metadata.id, sample]),
    );

    samples.forEach((sample) => {
      byId.set(sample.data.metadata.id, sample);
    });
    feedState.entries = sortSamplesChronologically([...byId.values()]);
    feedState.dataStatus = "ready";
  }

  function trimFeedWindowAroundAnchor(anchor) {
    if (!shouldTrimFeedWindow(anchor)) {
      return false;
    }

    const anchorIndex = findFeedSampleIndexById(anchor.id);

    if (anchorIndex < 0) {
      debugLoad("window trim skipped", { reason: "anchor-not-found", anchor });
      return false;
    }

    const previousEntries = feedState.entries;
    const maxEntries = settings.windowTrimMaxEntries;
    const keepBefore = settings.windowTrimKeepBefore;
    const keepAfter = settings.windowTrimKeepAfter;
    const startIndex = Math.max(0, anchorIndex - keepBefore);
    const endIndex = Math.min(previousEntries.length, anchorIndex + keepAfter + 1);

    if (previousEntries.length <= maxEntries || endIndex - startIndex >= previousEntries.length) {
      return false;
    }

    const nextEntries = previousEntries.slice(startIndex, endIndex);
    const trimmedOlder = startIndex > 0;
    const trimmedNewer = endIndex < previousEntries.length;

    feedState.entries = nextEntries;

    if (trimmedOlder) {
      const firstKeptCursor = getSampleCursor(nextEntries[0]);

      feedState.hasOlder = true;
      loadState.status = "idle";
      if (firstKeptCursor) {
        feedState.olderCursor = firstKeptCursor;
      }
    }

    if (trimmedNewer) {
      const lastKeptCursor = getSampleCursor(nextEntries.at(-1));

      feedState.hasNewer = true;
      feedState.atLatest = false;
      loadState.laterStatus = "idle";
      if (lastKeptCursor) {
        feedState.newerCursor = lastKeptCursor;
      }
    }

    debugLoad("window trimmed", {
      anchor,
      previousEntries: previousEntries.length,
      nextEntries: nextEntries.length,
      startIndex,
      endIndex,
      trimmedOlder,
      trimmedNewer,
      olderCursorPresent: Boolean(feedState.olderCursor),
      newerCursorPresent: Boolean(feedState.newerCursor),
    });
    return true;
  }

  function shouldTrimFeedWindow(anchor) {
    return Boolean(
      isBackendDataSource()
      && settings.windowTrimEnabled
      && anchor?.id
      && feedState.entries.length > settings.windowTrimMaxEntries,
    );
  }

  function findFeedSampleIndexById(entryId) {
    return feedState.entries.findIndex((sample) => sample.data.metadata.id === entryId);
  }

  function getSampleCursor(sample) {
    return sample?.ui?.cursor || null;
  }

  function sortSamplesChronologically(samples) {
    return samples.sort((left, right) => (
      left.data.metadata.created_at.localeCompare(right.data.metadata.created_at)
      || left.data.metadata.id.localeCompare(right.data.metadata.id)
    ));
  }

  function runPendingLoadCheckAfterLoadSettles() {
    if (!pendingLoadCheckAfterLayoutChange || loadState.status === "loading") {
      return;
    }

    debugLoad("resuming pending post-layout load check after load settled");
    requestAnimationFrame(() => {
      void loadEarlierEntriesUntilStable();
    });
  }

  function waitForNextFrame() {
    return new Promise((resolve) => {
      requestAnimationFrame(resolve);
    });
  }

  function getScrollAnchor() {
    const appTop = app.getBoundingClientRect().top;
    const entries = getVisibleEntries();
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

  function getVisibleEntries() {
    return [...app.querySelectorAll(".diary-entry")].filter((entry) => (
      entry.getClientRects().length > 0
    ));
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

  function scrollToDateEntry(date) {
    const target = app.querySelector(`[data-entry-date="${date}"]`);

    if (!target) {
      return;
    }

    setScrollTopInstant(Math.max(0, target.offsetTop - settings.jumpTargetOffset));
  }

  function scrollToEntry(entryId) {
    const target = app.querySelector(`[data-entry-id="${entryId}"]`);

    if (!target) {
      debugLoad("scroll to created entry skipped", {
        reason: "entry-not-found",
        entryId,
      });
      return;
    }

    setScrollTopInstant(Math.max(0, target.offsetTop - settings.jumpTargetOffset));
    debugLoad("scrolled to created entry", { entryId });
  }

  function setScrollTopInstant(top) {
    const previousBehavior = app.style.scrollBehavior;

    app.style.scrollBehavior = "auto";
    app.scrollTop = Math.max(0, top);
    app.style.scrollBehavior = previousBehavior;
    requestAnimationFrame(updateReturnToLatestButtonVisibility);
  }

  function simulateLoadingDelay() {
    return wait(settings.simulatedDelayMs);
  }

  function wait(milliseconds) {
    return new Promise((resolve) => {
      window.setTimeout(resolve, Math.max(0, milliseconds));
    });
  }

  function registerLoadDebugTools() {
    window.SereinDebugLoad = {
      clearLogs: clearLoadDebugLogs,
      dumpLogs: dumpLoadDebugLogs,
      dumpReport: dumpLoadDebugReport,
      inspect: inspectLoadState,
      setEnabled: setLoadDebugEnabled,
      get enabled() {
        return loadDebugState.enabled;
      },
    };

    debugLoad("debug tools registered", {
      hint: "Use SereinDebugLoad.inspect(), SereinDebugLoad.dumpReport(), SereinDebugLoad.dumpLogs(), or SereinDebugLoad.setEnabled(false).",
    });
  }

  function registerIndexDebugTools() {
    if (window.SereinDebugIndex) {
      return;
    }

    window.SereinDebugIndex = {
      clear: clearIndexDebugLogs,
      dumpReport: dumpIndexDebugReport,
      inspect: inspectIndexDebugState,
    };

    debugIndex("debug tools registered", {
      hint: "Use SereinDebugIndex.dumpReport() after testing rebuild-index.",
    });
  }

  function inspectIndexDebugState() {
    const snapshot = createIndexDebugSnapshot();

    console.table(snapshot);
    return snapshot;
  }

  function clearIndexDebugLogs() {
    indexDebugState.history = [];
    console.info("[Serein index] logs cleared");
  }

  function dumpIndexDebugReport() {
    const report = {
      generatedAt: new Date().toISOString(),
      snapshot: createIndexDebugSnapshot(),
      recentLogs: indexDebugState.history.slice(-80),
      note: "Safe to share: this report excludes diary bodies, passwords, cookies, sessions, and private file paths.",
    };

    console.log(JSON.stringify(report, null, 2));
    return report;
  }

  function debugIndex(message, details = {}) {
    const payload = {
      timestamp: new Date().toISOString(),
      message,
      ...createIndexDebugSnapshot(),
      ...details,
    };

    indexDebugState.history.push(payload);
    if (indexDebugState.history.length > 160) {
      indexDebugState.history.shift();
    }

    console.info(`[Serein index] ${message}`, payload);
  }

  function createIndexDebugSnapshot() {
    return {
      dataSource: dataAdapter.source,
      apiBase: API_BASE,
      rebuildPath: `${API_BASE.replace(/\/$/u, "")}/entries/rebuild-index`,
      resolvedRebuildUrl: resolveDebugUrl(`${API_BASE.replace(/\/$/u, "")}/entries/rebuild-index`),
      pagePath: window.location.pathname,
      pageSearch: window.location.search,
      authenticated: authState.authenticated,
      feedDataStatus: feedState.dataStatus,
      loadedEntries: feedState.entries.length,
      calendarDateStatus: sidebarCalendarDateState.status,
    };
  }

  function resolveDebugUrl(path) {
    try {
      return new URL(path, window.location.href).href;
    } catch {
      return String(path || "");
    }
  }

  function setLoadDebugEnabled(enabled) {
    loadDebugState.enabled = Boolean(enabled);
    writeLoadDebugPreference(loadDebugState.enabled);
    console.info(`[Serein load] debug ${loadDebugState.enabled ? "enabled" : "disabled"}`);
    return loadDebugState.enabled;
  }

  function inspectLoadState() {
    const snapshot = createLoadDebugSnapshot();

    console.table(snapshot);
    return snapshot;
  }

  function clearLoadDebugLogs() {
    loadDebugState.history = [];
    console.info("[Serein load] logs cleared");
  }

  function dumpLoadDebugLogs() {
    const logs = loadDebugState.history.slice();

    console.log(JSON.stringify(logs, null, 2));
    return logs;
  }

  function dumpLoadDebugReport() {
    const report = {
      generatedAt: new Date().toISOString(),
      snapshot: createLoadDebugSnapshot(),
      recentLogs: loadDebugState.history.slice(-120),
      note: "Safe to share: this report excludes diary bodies, passwords, cookies, and private file paths.",
    };

    console.log(JSON.stringify(report, null, 2));
    return report;
  }

  function debugShouldLoad(shouldLoad, reason, details = {}) {
    if (!details.verbose && !shouldLoad) {
      return;
    }

    const direction = details.direction === "later" ? "Later" : "Earlier";

    debugLoad(`shouldLoad${direction}Entries -> ${shouldLoad}`, {
      reason,
      ...details,
    });
  }

  function debugLoad(message, details = {}) {
    if (!loadDebugState.enabled) {
      return;
    }

    const payload = {
      timestamp: new Date().toISOString(),
      message,
      ...createLoadDebugSnapshot(),
      ...details,
    };

    loadDebugState.history.push(payload);
    if (loadDebugState.history.length > 300) {
      loadDebugState.history.shift();
    }

    console.info(`[Serein load] ${message}`, payload);
  }

  function createLoadDebugSnapshot() {
    const totalReadingEntries = getAllReadingSamples().length;
    const visibleEntries = getVisibleEntries();
    const firstVisibleEntry = visibleEntries[0];
    const lastVisibleEntry = visibleEntries[visibleEntries.length - 1];
    const distanceToBottom = app.scrollHeight - app.scrollTop - app.clientHeight;
    const topTriggerEntry = visibleEntries[
      Math.min(Math.max(settings.triggerEntryIndex, 1), visibleEntries.length) - 1
    ];

    return {
      dataSource: dataAdapter.source,
      dataStatus: feedState.dataStatus,
      targetDate: feedState.targetDate,
      atLatest: feedState.atLatest,
      hasOlder: feedState.hasOlder,
      hasNewer: feedState.hasNewer,
      olderCursorPresent: Boolean(feedState.olderCursor),
      newerCursorPresent: Boolean(feedState.newerCursor),
      status: loadState.status,
      errorMessage: loadState.errorMessage,
      laterStatus: loadState.laterStatus,
      laterErrorMessage: loadState.laterErrorMessage,
      visibleStartIndex: loadState.visibleStartIndex,
      totalReadingEntries,
      loadedReadingEntries: totalReadingEntries - loadState.visibleStartIndex,
      visibleDomEntries: visibleEntries.length,
      firstVisibleEntryId: firstVisibleEntry?.dataset.entryId || null,
      lastVisibleEntryId: lastVisibleEntry?.dataset.entryId || null,
      scrollTop: Math.round(app.scrollTop),
      clientHeight: Math.round(app.clientHeight),
      scrollHeight: Math.round(app.scrollHeight),
      distanceToBottom: Math.round(distanceToBottom),
      isScrollable: app.scrollHeight > app.clientHeight,
      triggerEntryIndexSetting: settings.triggerEntryIndex,
      topTriggerEntryId: topTriggerEntry?.dataset.entryId || null,
      topTriggerOffsetTop: topTriggerEntry ? Math.round(topTriggerEntry.offsetTop) : null,
      laterTriggerDistance: settings.laterTriggerDistance,
      laterTriggerThreshold: Math.round(Math.max(app.clientHeight * 0.25, settings.laterTriggerDistance)),
      pageSize: settings.pageSize,
      windowTrimEnabled: settings.windowTrimEnabled,
      windowTrimMaxEntries: settings.windowTrimMaxEntries,
      windowTrimKeepBefore: settings.windowTrimKeepBefore,
      windowTrimKeepAfter: settings.windowTrimKeepAfter,
      pendingPostLayoutCheck: pendingLoadCheckAfterLayoutChange,
      postLayoutCheckRunning: loadCheckAfterLayoutChangeRunning,
    };
  }

  function shouldLogScrollProbe() {
    if (!loadDebugState.enabled) {
      return false;
    }

    const now = Date.now();

    if (now - loadDebugState.lastScrollProbeAt < 750) {
      return false;
    }

    loadDebugState.lastScrollProbeAt = now;
    return true;
  }

  function readLoadDebugPreference() {
    try {
      const stored = window.localStorage.getItem("serein-load-debug");

      return stored === null ? true : stored === "true";
    } catch {
      return true;
    }
  }

  function writeLoadDebugPreference(enabled) {
    try {
      window.localStorage.setItem("serein-load-debug", String(enabled));
    } catch {
      // Ignore storage failures; console debugging still works for this session.
    }
  }

  function createSidebarShell() {
    const button = document.createElement("button");
    const backdrop = document.createElement("div");
    const sidebar = document.createElement("aside");
    const header = document.createElement("div");
    const close = document.createElement("button");
    const nav = document.createElement("nav");
    const panels = document.createElement("div");
    const sidebarId = "serein-sidebar";

    button.className = "sidebar-menu-button";
    button.type = "button";
    button.title = "打开面板（Ctrl+K）";
    button.setAttribute("aria-label", "打开面板");
    button.setAttribute("aria-controls", sidebarId);
    button.setAttribute("aria-expanded", "false");
    button.innerHTML = "<span></span><span></span><span></span>";

    backdrop.className = "sidebar-backdrop";
    backdrop.hidden = true;

    sidebar.className = "app-sidebar";
    sidebar.id = sidebarId;
    sidebar.hidden = true;
    sidebar.setAttribute("aria-label", "信息与设置面板");
    sidebar.setAttribute("aria-modal", "true");
    sidebar.setAttribute("role", "dialog");

    header.className = "app-sidebar-header";
    close.className = "app-sidebar-close";
    close.type = "button";
    close.textContent = "×";
    close.title = "关闭面板";
    close.setAttribute("aria-label", "关闭面板");

    nav.className = "app-sidebar-nav";
    nav.setAttribute("aria-label", "面板页面");
    panels.className = "app-sidebar-panels";

    createSidebarPages().forEach((page, index) => {
      const tab = document.createElement("button");
      const panel = document.createElement("section");
      const panelTitle = document.createElement("h3");
      const placeholder = document.createElement("p");
      const selected = index === 0;

      tab.className = "app-sidebar-tab";
      tab.type = "button";
      tab.innerHTML = page.icon;
      tab.title = page.label;
      tab.setAttribute("aria-label", page.label);
      tab.setAttribute("aria-controls", page.panelId);
      tab.setAttribute("aria-selected", String(selected));
      tab.dataset.tooltip = page.tooltip;
      tab.dataset.sidebarPage = page.id;

      panel.className = "app-sidebar-panel";
      panel.id = page.panelId;
      panel.dataset.sidebarPage = page.id;
      panel.hidden = !selected;
      panelTitle.className = "app-sidebar-panel-title";
      panelTitle.textContent = page.label;
      placeholder.className = "app-sidebar-placeholder";
      placeholder.textContent = page.placeholder;

      tab.addEventListener("click", () => {
        setSidebarPage(page.id);
      });

      if (page.id === "calendar") {
        panel.append(createSidebarCalendar());
      } else if (page.id === "settings") {
        panel.append(createSidebarSettingsPanel());
      } else {
        panel.append(panelTitle);
        panel.append(placeholder);
      }
      nav.append(tab);
      panels.append(panel);
    });

    header.append(nav, close);
    sidebar.append(header, panels);
    document.body.append(button, backdrop, sidebar);

    button.addEventListener("click", () => {
      setSidebarOpen(!isSidebarOpen(), { button, backdrop, sidebar });
    });
    close.addEventListener("click", () => {
      setSidebarOpen(false, { button, backdrop, sidebar });
      button.focus({ preventScroll: true });
    });
    backdrop.addEventListener("click", () => {
      setSidebarOpen(false, { button, backdrop, sidebar });
      button.focus({ preventScroll: true });
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isSidebarOpen()) {
        setSidebarOpen(false, { button, backdrop, sidebar });
        button.focus({ preventScroll: true });
        return;
      }

      if (event.key.toLowerCase() === "k" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        setSidebarOpen(!isSidebarOpen(), { button, backdrop, sidebar });
      }
    });
  }

  function setSidebarOpen(open, elements = {}) {
    const button = elements.button || document.querySelector(".sidebar-menu-button");
    const backdrop = elements.backdrop || document.querySelector(".sidebar-backdrop");
    const sidebar = elements.sidebar || document.querySelector(".app-sidebar");
    const nextOpen = Boolean(open);
    const transitionMs = 180;

    if (nextOpen) {
      if (backdrop) {
        backdrop.hidden = false;
      }
      if (sidebar) {
        sidebar.hidden = false;
      }
      requestAnimationFrame(() => {
        document.body.dataset.sidebarOpen = "true";
      });
    } else {
      document.body.dataset.sidebarOpen = "false";
      window.setTimeout(() => {
        if (isSidebarOpen()) {
          return;
        }
        if (backdrop) {
          backdrop.hidden = true;
        }
        if (sidebar) {
          sidebar.hidden = true;
        }
      }, transitionMs);
    }

    if (button) {
      button.setAttribute("aria-expanded", String(nextOpen));
      button.title = nextOpen ? "关闭面板（Ctrl+K）" : "打开面板（Ctrl+K）";
      button.setAttribute("aria-label", nextOpen ? "关闭面板" : "打开面板");
    }

    if (sidebar && nextOpen) {
      sidebar.querySelector(".app-sidebar-close")?.focus({ preventScroll: true });
    }
  }

  function isSidebarOpen() {
    return document.body.dataset.sidebarOpen === "true";
  }

  function createSidebarPages() {
    return [
      {
        id: "calendar",
        label: "日期",
        tooltip: "日历",
        panelId: "serein-sidebar-calendar",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4.5" y="5.5" width="15" height="14" rx="2"></rect><path d="M8 3.8v3.4M16 3.8v3.4M5 10h14"></path></svg>',
        placeholder: "日期页面占位。后续可放日历、日期跳转和时间范围导航。",
      },
      {
        id: "stats",
        label: "统计",
        tooltip: "统计",
        panelId: "serein-sidebar-stats",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19h14"></path><rect x="6" y="11" width="3" height="6" rx="1"></rect><rect x="11" y="7" width="3" height="10" rx="1"></rect><rect x="16" y="4" width="3" height="13" rx="1"></rect></svg>',
        placeholder: "统计页面占位。后续可放写作天数、条目数量和媒体统计。",
      },
      {
        id: "settings",
        label: "设置",
        tooltip: "设置",
        panelId: "serein-sidebar-settings",
        icon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19.4 13.5c.07-.48.1-.98.1-1.5s-.03-1.02-.1-1.5l1.9-1.48-1.9-3.3-2.36.95a8.3 8.3 0 0 0-2.58-1.5L14.1 2.7h-4.2l-.36 2.47a8.3 8.3 0 0 0-2.58 1.5L4.6 5.72l-1.9 3.3 1.9 1.48c-.07.48-.1.98-.1 1.5s.03 1.02.1 1.5l-1.9 1.48 1.9 3.3 2.36-.95a8.3 8.3 0 0 0 2.58 1.5l.36 2.47h4.2l.36-2.47a8.3 8.3 0 0 0 2.58-1.5l2.36.95 1.9-3.3-1.9-1.48Z"></path><circle cx="12" cy="12" r="3.2"></circle></svg>',
        placeholder: "设置页面占位。后续可放主题、编辑器、导出和账户相关设置。",
      },
    ];
  }

  function setSidebarPage(pageId) {
    debugCalendar("setSidebarPage", { pageId });
    document.querySelectorAll(".app-sidebar-tab").forEach((tab) => {
      tab.setAttribute("aria-selected", String(tab.dataset.sidebarPage === pageId));
    });

    document.querySelectorAll(".app-sidebar-panel").forEach((panel) => {
      panel.hidden = panel.dataset.sidebarPage !== pageId;
    });

    if (pageId === "calendar") {
      const calendar = document.querySelector(".sidebar-calendar");

      if (calendar) {
        debugCalendar("calendar page activated; ensuring dates");
        void ensureSidebarCalendarDates(calendar);
      } else {
        debugCalendar("calendar page activated but calendar node is missing");
      }
    }
  }

  function createSidebarSettingsPanel() {
    const settingsPanel = document.createElement("div");

    settingsPanel.className = "sidebar-settings";
    settingsPanel.append(
      createSidebarTextSetting({
        id: "serein-setting-page-name",
        label: "页面名称",
        description: "用于浏览器标签页标题。",
        value: readPageNamePreference(),
        settingName: "page-name",
        placeholder: readPageNameToken(),
        onInput(value) {
          setPageName(value);
        },
      }),
      createSidebarSelectSetting({
        id: "serein-setting-layout-debug",
        label: "布局调试",
        description: "显示页面各组件的边框，用于检查排版。",
        value: isLayoutDebugModeEnabled() ? "on" : "off",
        options: [
          { value: "off", label: "关闭" },
          { value: "on", label: "开启" },
        ],
        settingName: "layout-debug",
        onChange(value) {
          setLayoutDebugMode(value === "on");
        },
      }),
      createSidebarSelectSetting({
        id: "serein-setting-editor-mode",
        label: "编辑器模式",
        description: isTiptapExperimentAvailable()
          ? "切换原生文本框和 Tiptap 实验控件。"
          : "正式写作固定使用离线 Textarea。",
        value: isTiptapExperimentEnabled() ? "tiptap" : "textarea",
        disabled: !isTiptapExperimentAvailable(),
        options: [
          { value: "textarea", label: "Textarea" },
          { value: "tiptap", label: "Tiptap demo", disabled: !isTiptapExperimentAvailable() },
        ],
        settingName: "editor-mode",
        onChange(value) {
          setTiptapExperimentEnabled(value === "tiptap");
          renderFeed({ focusNewEntry: true, scrollToEnd: true });
        },
      }),
      createSidebarActionSetting({
        id: "serein-setting-rebuild-index",
        label: "重建索引",
        description: "手动导入 entries 后刷新服务器端列表索引。",
        buttonLabel: "重建",
        disabled: !isBackendDataSource(),
        disabledMessage: "mock 模式不需要重建索引。",
        onAction: rebuildEntryIndexFromSettings,
      }),
    );

    return settingsPanel;
  }

  function createSidebarTextSetting(config) {
    const row = document.createElement("div");
    const heading = document.createElement("div");
    const input = document.createElement("input");

    row.className = "sidebar-setting-row";
    heading.className = "sidebar-setting-heading";
    input.className = "sidebar-setting-input";
    input.id = config.id;
    input.type = "text";
    input.value = config.value;
    input.placeholder = config.placeholder;
    input.dataset.setting = config.settingName;
    input.autocomplete = "off";
    input.addEventListener("input", () => {
      config.onInput(input.value);
    });

    heading.append(createSidebarSettingLabel(config), input);
    row.append(heading);

    return row;
  }

  function createSidebarSelectSetting(config) {
    const row = document.createElement("div");
    const heading = document.createElement("div");
    const select = document.createElement("select");

    row.className = "sidebar-setting-row";
    heading.className = "sidebar-setting-heading";
    select.className = "sidebar-setting-select";
    select.id = config.id;
    select.dataset.setting = config.settingName;
    config.options.forEach((optionConfig) => {
      const option = document.createElement("option");

      option.value = optionConfig.value;
      option.textContent = optionConfig.label;
      option.disabled = Boolean(optionConfig.disabled);
      select.append(option);
    });
    select.value = config.value;
    select.disabled = Boolean(config.disabled);
    select.addEventListener("change", () => {
      config.onChange(select.value);
    });

    heading.append(createSidebarSettingLabel(config), select);
    row.append(heading);

    return row;
  }

  function createSidebarActionSetting(config) {
    const row = document.createElement("div");
    const heading = document.createElement("div");
    const button = document.createElement("button");
    const status = document.createElement("p");

    row.className = "sidebar-setting-row";
    heading.className = "sidebar-setting-heading";
    button.className = "sidebar-setting-button";
    button.id = config.id;
    button.type = "button";
    button.textContent = config.buttonLabel;
    button.disabled = Boolean(config.disabled);
    status.className = "sidebar-setting-status";
    status.setAttribute("role", "status");
    status.textContent = config.disabled ? config.disabledMessage || "" : "";
    button.addEventListener("click", async () => {
      button.disabled = true;
      status.textContent = "正在重建……";
      try {
        const result = await config.onAction();

        status.textContent = createIndexRebuildStatusMessage(result);
      } catch (error) {
        status.textContent = `重建失败：${createDataErrorMessage(error)}`;
      } finally {
        button.disabled = Boolean(config.disabled);
      }
    });

    heading.append(createSidebarSettingLabel(config), button);
    row.append(heading, status);

    return row;
  }

  function createSidebarSettingLabel(config) {
    const labelWrap = document.createElement("div");
    const label = document.createElement("label");
    const description = document.createElement("p");

    labelWrap.className = "sidebar-setting-label-wrap";
    label.className = "sidebar-setting-label";
    label.htmlFor = config.id;
    label.textContent = config.label;
    description.className = "sidebar-setting-description";
    description.textContent = config.description;

    labelWrap.append(label, description);
    return labelWrap;
  }

  async function rebuildEntryIndexFromSettings() {
    const startedAt = performance.now();

    debugIndex("rebuild index requested", {
      source: "settings",
    });

    try {
      const result = await dataAdapter.rebuildIndex();

      debugIndex("rebuild index completed", {
        durationMs: Math.round(performance.now() - startedAt),
        result: createSafeIndexRebuildResult(result),
      });
      sidebarCalendarDateState.status = "idle";
      sidebarCalendarDateState.dates = [];
      sidebarCalendarDateState.errorMessage = "";
      await initializeLoadedWindow();
      renderFeed({ scrollToEnd: true });
      debugIndex("feed refreshed after rebuild", {
        durationMs: Math.round(performance.now() - startedAt),
        result: createSafeIndexRebuildResult(result),
      });
      return result;
    } catch (error) {
      debugIndex("rebuild index failed", {
        durationMs: Math.round(performance.now() - startedAt),
        error: createSafeApiErrorDebug(error),
      });
      throw error;
    }
  }

  function createIndexRebuildStatusMessage(result) {
    const total = Number(result?.total_entries || 0);
    const visible = Number(result?.visible_entries || 0);
    const deleted = Number(result?.deleted_entries || 0);

    return `已重建：${visible} 篇可见，${deleted} 篇已删除，共 ${total} 篇。`;
  }

  function createSafeIndexRebuildResult(result) {
    return {
      rebuilt: Boolean(result?.rebuilt),
      totalEntries: Number(result?.total_entries || 0),
      visibleEntries: Number(result?.visible_entries || 0),
      deletedEntries: Number(result?.deleted_entries || 0),
    };
  }

  function createSafeApiErrorDebug(error) {
    return {
      name: error?.name || null,
      message: error instanceof Error ? error.message : String(error || "未知错误"),
      status: Number.isFinite(error?.status) ? error.status : null,
      code: error?.code || null,
      body: summarizeApiErrorBody(error?.body),
    };
  }

  function summarizeApiErrorBody(body) {
    if (!body || typeof body !== "object") {
      return null;
    }

    const apiError = body.error || body.detail?.error || null;

    if (apiError) {
      return {
        error: {
          code: apiError.code || null,
          message: apiError.message || null,
        },
      };
    }
    if (typeof body.detail === "string") {
      return { detail: body.detail };
    }

    return { keys: Object.keys(body).slice(0, 8) };
  }

  function createSidebarCalendar() {
    const calendar = document.createElement("section");
    const controls = document.createElement("div");
    const yearRow = document.createElement("div");
    const monthRow = document.createElement("div");
    const previousYear = document.createElement("button");
    const previousMonth = document.createElement("button");
    const yearLabel = document.createElement("button");
    const monthLabel = document.createElement("button");
    const nextMonth = document.createElement("button");
    const nextYear = document.createElement("button");
    const picker = document.createElement("div");
    const grid = document.createElement("div");
    const status = document.createElement("p");
    const cursor = getSidebarCalendarCursor();

    debugCalendar("createSidebarCalendar", {
      initialCursor: cursor,
      dateState: createCalendarDateStateSnapshot(),
    });
    calendar.className = "sidebar-calendar";
    controls.className = "sidebar-calendar-controls";
    yearRow.className = "sidebar-calendar-row sidebar-calendar-year-row";
    monthRow.className = "sidebar-calendar-row sidebar-calendar-month-row";
    yearLabel.className = "sidebar-calendar-label-button sidebar-calendar-year-label";
    monthLabel.className = "sidebar-calendar-label-button sidebar-calendar-month-label";
    picker.className = "sidebar-calendar-picker";
    picker.hidden = true;
    grid.className = "sidebar-calendar-grid";
    status.className = "sidebar-calendar-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");

    yearLabel.type = "button";
    monthLabel.type = "button";
    yearLabel.setAttribute("aria-label", "选择年份");
    monthLabel.setAttribute("aria-label", "选择月份");
    yearLabel.addEventListener("click", () => {
      toggleSidebarCalendarPicker(calendar, "year");
    });
    monthLabel.addEventListener("click", () => {
      toggleSidebarCalendarPicker(calendar, "month");
    });
    configureCalendarControl(previousYear, "‹‹", "上一年", () => {
      moveSidebarCalendar(calendar, -1, 0);
    });
    configureCalendarControl(previousMonth, "‹", "上一月", () => {
      moveSidebarCalendar(calendar, 0, -1);
    });
    configureCalendarControl(nextMonth, "›", "下一月", () => {
      moveSidebarCalendar(calendar, 0, 1);
    });
    configureCalendarControl(nextYear, "››", "下一年", () => {
      moveSidebarCalendar(calendar, 1, 0);
    });

    calendar.dataset.year = String(cursor.year);
    calendar.dataset.month = String(cursor.month);
    calendar.dataset.autoCursor = "true";
    yearRow.append(previousYear, yearLabel, nextYear);
    monthRow.append(previousMonth, monthLabel, nextMonth);
    controls.append(yearRow, monthRow);
    calendar.append(controls, picker, status, grid);
    calendar.addEventListener("pointerdown", (event) => {
      event.stopPropagation();
    });
    document.addEventListener("pointerdown", () => {
      closeSidebarCalendarPicker(calendar);
    });
    renderSidebarCalendar(calendar);
    debugCalendar("initial render complete; ensuring dates");
    void ensureSidebarCalendarDates(calendar);

    return calendar;
  }

  function configureCalendarControl(button, text, label, onClick) {
    button.className = "sidebar-calendar-control";
    button.type = "button";
    button.textContent = text;
    button.title = label;
    button.setAttribute("aria-label", label);
    button.addEventListener("click", onClick);
  }

  function getSidebarCalendarCursor() {
    if (sidebarCalendarCursor) {
      return sidebarCalendarCursor;
    }

    const latestDate = getSidebarCalendarDates().at(-1) || getCalendarDate(createLocalTimestamp());
    const [year, month] = latestDate.split("-").map(Number);

    sidebarCalendarCursor = normalizeCalendarCursor({ year, month });
    return sidebarCalendarCursor;
  }

  function moveSidebarCalendar(calendar, yearDelta, monthDelta) {
    const currentYear = Number(calendar.dataset.year);
    const currentMonth = Number(calendar.dataset.month);
    const nextDate = new Date(currentYear, currentMonth - 1 + monthDelta, 1);

    nextDate.setFullYear(nextDate.getFullYear() + yearDelta);
    const nextCursor = normalizeCalendarCursor({
      year: nextDate.getFullYear(),
      month: nextDate.getMonth() + 1,
    });

    if (
      nextCursor.year === Number(calendar.dataset.year)
      && nextCursor.month === Number(calendar.dataset.month)
    ) {
      debugCalendar("move ignored because cursor did not change", {
        yearDelta,
        monthDelta,
        nextCursor,
      });
      return;
    }

    sidebarCalendarCursor = nextCursor;
    calendar.dataset.autoCursor = "false";
    calendar.dataset.year = String(sidebarCalendarCursor.year);
    calendar.dataset.month = String(sidebarCalendarCursor.month);
    closeSidebarCalendarPicker(calendar);
    debugCalendar("moveSidebarCalendar", {
      yearDelta,
      monthDelta,
      nextCursor,
    });
    renderSidebarCalendar(calendar);
  }

  function renderSidebarCalendar(calendar) {
    const year = Number(calendar.dataset.year);
    const month = Number(calendar.dataset.month);
    const yearLabel = calendar.querySelector(".sidebar-calendar-year-label");
    const monthLabel = calendar.querySelector(".sidebar-calendar-month-label");
    const grid = calendar.querySelector(".sidebar-calendar-grid");
    const status = calendar.querySelector(".sidebar-calendar-status");
    const previousYear = calendar.querySelector('[aria-label="上一年"]');
    const previousMonth = calendar.querySelector('[aria-label="上一月"]');
    const nextMonth = calendar.querySelector('[aria-label="下一月"]');
    const nextYear = calendar.querySelector('[aria-label="下一年"]');
    const diaryDates = new Set(getSidebarCalendarDates());
    const firstDay = new Date(year, month - 1, 1);
    const daysInMonth = new Date(year, month, 0).getDate();
    const leadingEmptyDays = firstDay.getDay();
    const weekdays = ["日", "一", "二", "三", "四", "五", "六"];

    if (!yearLabel || !monthLabel || !grid) {
      debugCalendar("render skipped because required calendar nodes are missing", {
        hasYearLabel: Boolean(yearLabel),
        hasMonthLabel: Boolean(monthLabel),
        hasGrid: Boolean(grid),
      });
      return;
    }

    debugCalendar("renderSidebarCalendar", {
      year,
      month,
      dateState: createCalendarDateStateSnapshot(),
      markedCountInMonth: [...diaryDates].filter((date) => (
        date.startsWith(`${year}-${String(month).padStart(2, "0")}-`)
      )).length,
    });
    yearLabel.textContent = `${year} 年`;
    monthLabel.textContent = `${String(month).padStart(2, "0")} 月`;
    if (previousYear) {
      previousYear.disabled = false;
    }
    if (previousMonth) {
      previousMonth.disabled = false;
    }
    if (nextMonth) {
      nextMonth.disabled = isCalendarFuture(year, month + 1);
    }
    if (nextYear) {
      nextYear.disabled = isCalendarFuture(year + 1, month);
    }
    if (status) {
      renderSidebarCalendarStatus(status, calendar);
    }
    grid.replaceChildren();
    weekdays.forEach((weekday) => {
      const cell = document.createElement("span");

      cell.className = "sidebar-calendar-weekday";
      cell.textContent = weekday;
      grid.append(cell);
    });

    for (let index = 0; index < leadingEmptyDays; index += 1) {
      const cell = document.createElement("span");

      cell.className = "sidebar-calendar-empty";
      grid.append(cell);
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const date = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
      const hasEntry = diaryDates.has(date);
      const cell = document.createElement(hasEntry ? "button" : "span");

      cell.className = `sidebar-calendar-day${hasEntry ? " has-entry" : ""}`;
      cell.textContent = String(day);
      if (hasEntry) {
        cell.type = "button";
        cell.title = `跳转到 ${date}`;
        cell.setAttribute("aria-label", `跳转到 ${date}`);
        cell.addEventListener("click", () => {
          handleCalendarDateJump(date);
        });
      }
      grid.append(cell);
    }
  }

  function getMockDiaryDates() {
    return [...new Set(getAllReadingSamples().map((sample) => (
      getCalendarDate(sample.data.metadata.created_at)
    )))].sort();
  }

  function getSidebarCalendarDates() {
    if (sidebarCalendarDateState.status === "ready") {
      return sidebarCalendarDateState.dates;
    }

    debugCalendar("using fallback calendar dates before backend dates are ready", {
      dateState: createCalendarDateStateSnapshot(),
    });
    return getMockDiaryDates();
  }

  async function ensureSidebarCalendarDates(calendar, options = {}) {
    const { force = false } = options;

    debugCalendar("ensureSidebarCalendarDates called", {
      force,
      dateState: createCalendarDateStateSnapshot(),
      hasCalendar: Boolean(calendar),
      cursor: calendar ? {
        year: calendar.dataset.year,
        month: calendar.dataset.month,
        autoCursor: calendar.dataset.autoCursor,
      } : null,
    });
    if (!force && (
      sidebarCalendarDateState.status === "loading"
      || sidebarCalendarDateState.status === "ready"
    )) {
      debugCalendar("ensure skipped because dates are already loading or ready", {
        dateState: createCalendarDateStateSnapshot(),
      });
      renderSidebarCalendar(calendar);
      return;
    }

    sidebarCalendarDateState.status = "loading";
    sidebarCalendarDateState.errorMessage = "";
    renderSidebarCalendar(calendar);
    debugCalendar("requesting entry dates", {
      adapterSource: dataAdapter.source,
    });

    try {
      const result = await dataAdapter.getEntryDates();
      const dates = normalizeSidebarCalendarDates(result);

      debugCalendar("entry dates loaded", {
        rawCount: Array.isArray(result?.dates) ? result.dates.length : null,
        normalizedCount: dates.length,
      });
      sidebarCalendarDateState.status = "ready";
      sidebarCalendarDateState.dates = dates;
      sidebarCalendarDateState.errorMessage = "";
      if (calendar.dataset.autoCursor !== "false") {
        const latestDate = dates.at(-1) || getCalendarDate(createLocalTimestamp());
        const [year, month] = latestDate.split("-").map(Number);

        sidebarCalendarCursor = normalizeCalendarCursor({ year, month });
        calendar.dataset.year = String(sidebarCalendarCursor.year);
        calendar.dataset.month = String(sidebarCalendarCursor.month);
      }
      renderSidebarCalendar(calendar);
    } catch (error) {
      sidebarCalendarDateState.status = "error";
      sidebarCalendarDateState.errorMessage = createDataErrorMessage(error);
      renderSidebarCalendar(calendar);
      debugCalendar("entry dates failed", {
        errorMessage: sidebarCalendarDateState.errorMessage,
        status: error?.status || null,
        code: error?.code || null,
      });
      console.warn("[Serein calendar] Failed to load entry dates.", error);
    }
  }

  function normalizeSidebarCalendarDates(result) {
    const rawDates = Array.isArray(result?.dates) ? result.dates : [];

    return [...new Set(
      rawDates
        .map((item) => String(item?.date || "").slice(0, 10))
        .filter((date) => /^\d{4}-\d{2}-\d{2}$/u.test(date)),
    )].sort();
  }

  function renderSidebarCalendarStatus(status, calendar) {
    status.className = "sidebar-calendar-status";

    if (sidebarCalendarDateState.status === "loading") {
      status.textContent = "正在读取日期……";
      return;
    }

    if (sidebarCalendarDateState.status === "error") {
      const retry = document.createElement("button");

      status.classList.add("is-error");
      status.textContent = `日期读取失败：${sidebarCalendarDateState.errorMessage}`;
      retry.className = "sidebar-calendar-status-retry";
      retry.type = "button";
      retry.textContent = "重试";
      retry.addEventListener("click", () => {
        void ensureSidebarCalendarDates(calendar, { force: true });
      });
      status.append(" ", retry);
      return;
    }

    if (sidebarCalendarDateState.status === "ready" && sidebarCalendarDateState.dates.length === 0) {
      status.textContent = "暂无已保存日记日期";
      return;
    }

    status.textContent = "";
  }

  function toggleSidebarCalendarPicker(calendar, mode) {
    const picker = calendar.querySelector(".sidebar-calendar-picker");

    if (!picker) {
      return;
    }

    if (!picker.hidden && picker.dataset.mode === mode) {
      closeSidebarCalendarPicker(calendar);
      return;
    }

    renderSidebarCalendarPicker(calendar, mode);
  }

  function closeSidebarCalendarPicker(calendar) {
    const picker = calendar.querySelector(".sidebar-calendar-picker");

    if (picker) {
      picker.hidden = true;
      delete picker.dataset.mode;
    }
  }

  function renderSidebarCalendarPicker(calendar, mode) {
    const picker = calendar.querySelector(".sidebar-calendar-picker");
    const year = Number(calendar.dataset.year);
    const month = Number(calendar.dataset.month);
    const limit = getCalendarFutureLimit();

    if (!picker) {
      return;
    }

    picker.replaceChildren();
    picker.hidden = false;
    picker.dataset.mode = mode;
    picker.classList.toggle("is-year-picker", mode === "year");
    picker.classList.toggle("is-month-picker", mode === "month");

    if (mode === "year") {
      const years = getSelectableCalendarYears();

      debugCalendar("render year picker", {
        selectedYear: year,
        yearCount: years.length,
        firstYear: years[0] || null,
        lastYear: years.at(-1) || null,
        dateState: createCalendarDateStateSnapshot(),
      });
      years.forEach((selectableYear) => {
        const option = createSidebarCalendarPickerOption(
          `${selectableYear} 年`,
          selectableYear === year,
          () => {
            const nextCursor = normalizeCalendarCursor({ year: selectableYear, month });

            setSidebarCalendarCursor(calendar, nextCursor);
          },
        );

        picker.append(option);
      });
      scrollSelectedCalendarPickerOptionIntoView(picker);
      return;
    }

    for (let selectableMonth = 1; selectableMonth <= 12; selectableMonth += 1) {
      if (year === limit.year && selectableMonth > limit.month) {
        break;
      }

      const option = createSidebarCalendarPickerOption(
        `${String(selectableMonth).padStart(2, "0")} 月`,
        selectableMonth === month,
        () => {
          setSidebarCalendarCursor(calendar, { year, month: selectableMonth });
        },
      );

      picker.append(option);
    }
    scrollSelectedCalendarPickerOptionIntoView(picker);
  }

  function createSidebarCalendarPickerOption(label, selected, onClick) {
    const option = document.createElement("button");

    option.className = "sidebar-calendar-picker-option";
    option.type = "button";
    option.textContent = label;
    option.setAttribute("aria-selected", String(selected));
    option.addEventListener("click", onClick);
    return option;
  }

  function setSidebarCalendarCursor(calendar, cursor) {
    sidebarCalendarCursor = normalizeCalendarCursor(cursor);
    calendar.dataset.autoCursor = "false";
    calendar.dataset.year = String(sidebarCalendarCursor.year);
    calendar.dataset.month = String(sidebarCalendarCursor.month);
    closeSidebarCalendarPicker(calendar);
    renderSidebarCalendar(calendar);
  }

  function scrollSelectedCalendarPickerOptionIntoView(picker) {
    requestAnimationFrame(() => {
      picker.querySelector('[aria-selected="true"]')?.scrollIntoView({
        block: "center",
      });
    });
  }

  function getSelectableCalendarYears() {
    const diaryYears = getSidebarCalendarDates().map((date) => Number(date.slice(0, 4)));
    const currentYear = getCalendarFutureLimit().year;
    const firstYear = Math.min(...diaryYears, currentYear);
    const years = [];

    for (let year = firstYear; year <= currentYear; year += 1) {
      years.push(year);
    }

    return years;
  }

  function createCalendarDateStateSnapshot() {
    return {
      status: sidebarCalendarDateState.status,
      count: sidebarCalendarDateState.dates.length,
      errorMessage: sidebarCalendarDateState.errorMessage || "",
    };
  }

  function debugCalendar(message, details = {}) {
    console.info(`[Serein calendar] ${message}`, details);
  }

  function normalizeCalendarCursor(cursor) {
    const limit = getCalendarFutureLimit();
    let year = Number(cursor.year);
    let month = Number(cursor.month);

    if (!Number.isFinite(year)) {
      year = limit.year;
    }
    if (!Number.isFinite(month)) {
      month = limit.month;
    }
    if (year > limit.year) {
      year = limit.year;
      month = limit.month;
    }
    if (year === limit.year && month > limit.month) {
      month = limit.month;
    }
    if (month < 1) {
      month = 1;
    }
    if (month > 12) {
      month = 12;
    }

    return { year, month };
  }

  function isCalendarFuture(year, month) {
    const normalized = normalizeCalendarMonth(year, month);
    const limit = getCalendarFutureLimit();

    return (
      normalized.year > limit.year
      || (normalized.year === limit.year && normalized.month > limit.month)
    );
  }

  function normalizeCalendarMonth(year, month) {
    const date = new Date(Number(year), Number(month) - 1, 1);

    return {
      year: date.getFullYear(),
      month: date.getMonth() + 1,
    };
  }

  function getCalendarFutureLimit() {
    const now = new Date();

    return {
      year: now.getFullYear(),
      month: now.getMonth() + 1,
    };
  }

  function handleCalendarDateJump(date) {
    void jumpToCalendarDate(date);
  }

  async function jumpToCalendarDate(date) {
    const targetDate = String(date || "").slice(0, 10);

    if (!/^\d{4}-\d{2}-\d{2}$/u.test(targetDate)) {
      return;
    }

    calendarJumpSequence += 1;
    const jumpSequence = calendarJumpSequence;
    const transitionDelay = wait(settings.jumpTransitionMinWaitMs);

    feedState.transition = "leaving";
    feedState.jumpStatus = "loading";
    feedState.jumpErrorMessage = "";
    setSidebarOpen(false);
    renderFeed();

    try {
      const windowResult = await dataAdapter.getEntryWindow({
        date: targetDate,
        olderCount: settings.jumpBeforeCount,
        newerCount: settings.jumpAfterCount,
      });
      const samples = await loadEntryDetailsForSummaries(windowResult.items || []);
      const windowInfo = windowResult.window || {};

      await transitionDelay;
      if (jumpSequence !== calendarJumpSequence) {
        return;
      }
      feedState.entries = sortSamplesChronologically(samples);
      feedState.targetDate = targetDate;
      feedState.transition = "entering";
      feedState.jumpStatus = "ready";
      feedState.jumpErrorMessage = "";
      feedState.dataStatus = "ready";
      loadState.visibleStartIndex = 0;
      feedState.hasOlder = Boolean(windowInfo.has_older);
      feedState.hasNewer = Boolean(windowInfo.has_newer);
      feedState.atLatest = !feedState.hasNewer;
      loadState.status = feedState.hasOlder ? "idle" : "complete";
      loadState.errorMessage = "";
      feedState.olderCursor = windowInfo.older_cursor || null;
      loadState.laterStatus = feedState.hasNewer ? "idle" : "complete";
      loadState.laterErrorMessage = "";
      feedState.newerCursor = windowInfo.newer_cursor || null;
      renderFeed({ scrollToDate: targetDate });
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          feedState.transition = "idle";
          const feed = app.querySelector(".diary-feed");
          if (feed) {
            feed.dataset.transition = "idle";
          }
          const overlay = app.querySelector(".feed-transition-overlay");
          overlay?.remove();
          updateReturnToLatestButtonVisibility();
        });
      });
    } catch (error) {
      await transitionDelay;
      if (jumpSequence !== calendarJumpSequence) {
        return;
      }
      feedState.targetDate = targetDate;
      feedState.transition = "idle";
      feedState.atLatest = false;
      feedState.hasOlder = false;
      feedState.hasNewer = false;
      feedState.jumpStatus = "error";
      feedState.jumpErrorMessage = createDataErrorMessage(error);
      feedState.dataStatus = "error";
      feedState.dataErrorMessage = feedState.jumpErrorMessage;
      feedState.entries = [];
      loadState.status = "error";
      loadState.errorMessage = feedState.jumpErrorMessage;
      loadState.laterStatus = "complete";
      feedState.olderCursor = null;
      feedState.newerCursor = null;
      renderFeed();
      console.warn("[Serein calendar] Date jump failed.", {
        message: feedState.jumpErrorMessage,
      });
    }
  }

  function initializePageNameState() {
    setPageName(readPageNamePreference(), { persist: false });
  }

  function setPageName(value, options = {}) {
    const { persist = true } = options;
    const nextValue = String(value || "");
    const title = normalizePageName(nextValue);

    document.title = title;

    if (persist) {
      writePageNamePreference(nextValue);
    }

    return title;
  }

  function normalizePageName(value) {
    return String(value || "").trim() || readPageNameToken();
  }

  function readPageNamePreference() {
    try {
      const storedValue = window.localStorage.getItem("serein-page-name");
      return storedValue === null ? readPageNameToken() : storedValue;
    } catch {
      return readPageNameToken();
    }
  }

  function writePageNamePreference(value) {
    try {
      const nextValue = String(value || "");
      if (nextValue.trim()) {
        window.localStorage.setItem("serein-page-name", nextValue);
      } else {
        window.localStorage.removeItem("serein-page-name");
      }
    } catch {
      // Ignore storage failures; the page title still updates for this session.
    }
  }

  function readPageNameToken() {
    const styles = window.getComputedStyle(document.documentElement);
    const rawValue = styles.getPropertyValue("--page-name").trim();

    return parseCssStringToken(rawValue) || FALLBACK_PAGE_NAME;
  }

  function parseCssStringToken(value) {
    if (!value) {
      return "";
    }

    const quote = value[0];
    if (quote === '"' || quote === "'") {
      const endIndex = findCssStringEnd(value, quote);

      if (endIndex > 0) {
        return value
          .slice(1, endIndex)
          .replace(/\\(["'\\])/gu, "$1")
          .trim();
      }
    }

    return value.trim();
  }

  function findCssStringEnd(value, quote) {
    let escaped = false;

    for (let index = 1; index < value.length; index += 1) {
      const character = value[index];

      if (escaped) {
        escaped = false;
        continue;
      }

      if (character === "\\") {
        escaped = true;
        continue;
      }

      if (character === quote) {
        return index;
      }
    }

    return -1;
  }

  function registerEditorExperimentTools() {
    window.SereinEditorExperiment = {
      dumpMarkdown: dumpCurrentEditorMarkdown,
      getMode: () => (isTiptapExperimentEnabled() ? "tiptap" : "textarea"),
      setTiptapEnabled(enabled) {
        setTiptapExperimentEnabled(enabled);
        renderFeed({ focusNewEntry: true, scrollToEnd: true });
        return isTiptapExperimentEnabled();
      },
    };
  }

  function dumpCurrentEditorMarkdown() {
    const markdown = activeNewEntryContentControl?.readMarkdown() || "";

    console.log(markdown);
    return markdown;
  }

  function initializeEditorExperimentState() {
    if (isTiptapExperimentAvailable() && readEditorExperimentPreference()) {
      document.documentElement.dataset.editorExperiment = "tiptap";
    } else {
      delete document.documentElement.dataset.editorExperiment;
    }
  }

  function setTiptapExperimentEnabled(enabled, options = {}) {
    const {
      persist = true,
      select = document.querySelector('[data-setting="editor-mode"]'),
    } = options;
    const requestedEnabled = Boolean(enabled);
    const nextEnabled = requestedEnabled && isTiptapExperimentAvailable();

    if (requestedEnabled && !nextEnabled) {
      console.info("[Serein editor] Tiptap demo is only available in mock mode; backend writing uses Textarea.");
    }

    if (nextEnabled) {
      document.documentElement.dataset.editorExperiment = "tiptap";
    } else {
      delete document.documentElement.dataset.editorExperiment;
    }

    if (persist && (!requestedEnabled || nextEnabled)) {
      writeEditorExperimentPreference(nextEnabled);
    }

    if (select) {
      select.value = nextEnabled ? "tiptap" : "textarea";
      select.disabled = !isTiptapExperimentAvailable();
    }

    return nextEnabled;
  }

  function isTiptapExperimentEnabled() {
    return (
      isTiptapExperimentAvailable()
      && document.documentElement.dataset.editorExperiment === "tiptap"
    );
  }

  function isTiptapExperimentAvailable() {
    return dataAdapter.source === "mock";
  }

  function readEditorExperimentPreference() {
    try {
      return window.localStorage.getItem("serein-editor-experiment") === "tiptap";
    } catch {
      return false;
    }
  }

  function writeEditorExperimentPreference(enabled) {
    try {
      window.localStorage.setItem("serein-editor-experiment", enabled ? "tiptap" : "textarea");
    } catch {
      // Ignore storage failures; the toggle still works for this session.
    }
  }

  function readInteractionSettings() {
    const styles = window.getComputedStyle(document.documentElement);

    return {
      initialCount: readIntegerToken(styles, "--load-initial-count", 6),
      pageSize: readIntegerToken(styles, "--load-page-size", 4),
      triggerEntryIndex: readIntegerToken(styles, "--load-trigger-entry-index", 5),
      simulatedDelayMs: readIntegerToken(styles, "--load-simulated-delay-ms", 1000),
      layoutFillTolerance: readNonNegativeIntegerToken(styles, "--load-layout-fill-tolerance", 0),
      laterTriggerDistance: readNonNegativeIntegerToken(styles, "--load-later-trigger-distance", 160),
      jumpBeforeCount: readNonNegativeIntegerToken(styles, "--jump-before-count", 12),
      jumpAfterCount: readNonNegativeIntegerToken(styles, "--jump-after-count", 12),
      jumpTargetOffset: readNonNegativeIntegerToken(styles, "--jump-target-scroll-offset", 96),
      jumpTransitionMinWaitMs: readNonNegativeIntegerToken(styles, "--jump-transition-min-wait-ms", 280),
      returnButtonTopTolerance: readNonNegativeIntegerToken(styles, "--return-button-top-tolerance", 8),
      windowTrimEnabled: readBooleanToken(styles, "--window-trim-enabled", false),
      windowTrimMaxEntries: readIntegerToken(styles, "--window-trim-max-entries", 120),
      windowTrimKeepBefore: readNonNegativeIntegerToken(styles, "--window-trim-keep-before", 48),
      windowTrimKeepAfter: readNonNegativeIntegerToken(styles, "--window-trim-keep-after", 48),
    };
  }

  function readIntegerToken(styles, name, fallback) {
    const value = Number.parseInt(styles.getPropertyValue(name), 10);

    return Number.isFinite(value) && value > 0 ? value : fallback;
  }

  function readNonNegativeIntegerToken(styles, name, fallback) {
    const value = Number.parseInt(styles.getPropertyValue(name), 10);

    return Number.isFinite(value) && value >= 0 ? value : fallback;
  }

  function readBooleanToken(styles, name, fallback) {
    const value = styles.getPropertyValue(name).trim().toLowerCase();

    if (["1", "true", "yes", "on"].includes(value)) {
      return true;
    }
    if (["0", "false", "no", "off"].includes(value)) {
      return false;
    }

    return fallback;
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

  function createGroup(className, label, stateKey) {
    const group = document.createElement("section");
    const summary = document.createElement("button");
    const content = document.createElement("div");
    const contentId = `group-${className}-${label}-${createMockUuid()}`;
    const isOpen = groupOpenState.get(stateKey) !== false;

    group.className = className;
    group.dataset.open = String(isOpen);
    group.dataset.groupKey = stateKey;
    summary.className = "diary-group-summary";
    summary.type = "button";
    summary.textContent = label;
    summary.setAttribute("aria-expanded", String(isOpen));
    summary.setAttribute("aria-controls", contentId);
    content.className = "diary-group-content";
    content.id = contentId;
    content.hidden = !isOpen;
    summary.addEventListener("click", () => {
      const isOpen = group.dataset.open !== "false";
      const nextOpen = !isOpen;

      groupOpenState.set(stateKey, nextOpen);
      group.dataset.open = String(nextOpen);
      summary.setAttribute("aria-expanded", String(nextOpen));
      content.hidden = !nextOpen;
      debugLoad("group toggled", {
        stateKey,
        nextOpen,
        className,
        label,
      });

      if (!nextOpen) {
        scheduleLoadCheckAfterLayoutChange();
      }
    });
    group.append(summary, content);

    return { details: group, content };
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
    if (metadata.id === pendingSavedEntryId) {
      entry.classList.add("is-newly-saved");
      window.setTimeout(() => {
        if (pendingSavedEntryId === metadata.id) {
          pendingSavedEntryId = null;
        }
        app.querySelector(`[data-entry-id="${metadata.id}"]`)?.classList.remove("is-newly-saved");
      }, 1400);
    }
    entry.dataset.entryId = metadata.id;
    entry.dataset.entryDate = calendarDate;
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
    appendMarkdownBlocks(content, data.content);

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

  function appendMarkdownBlocks(container, markdown) {
    const lines = String(markdown || "").replace(/\r\n?/gu, "\n").split("\n");
    let index = 0;

    while (index < lines.length) {
      const line = lines[index];

      if (!line.trim()) {
        index += 1;
        continue;
      }

      if (/^```/u.test(line.trim())) {
        const code = [];
        index += 1;
        while (index < lines.length && !/^```/u.test(lines[index].trim())) {
          code.push(lines[index]);
          index += 1;
        }
        if (index < lines.length) {
          index += 1;
        }
        appendCodeBlock(container, code.join("\n"));
        continue;
      }

      if (/^---+\s*$/u.test(line.trim())) {
        container.append(document.createElement("hr"));
        index += 1;
        continue;
      }

      const heading = line.match(/^(#{1,4})\s+(.+)$/u);
      if (heading) {
        const level = Math.min(heading[1].length + 2, 6);
        const element = document.createElement(`h${level}`);
        appendInlineMarkdown(element, heading[2].trim());
        container.append(element);
        index += 1;
        continue;
      }

      if (/^>\s?/u.test(line)) {
        const quoteLines = [];
        while (index < lines.length && /^>\s?/u.test(lines[index])) {
          quoteLines.push(lines[index].replace(/^>\s?/u, ""));
          index += 1;
        }
        const quote = document.createElement("blockquote");
        appendMarkdownBlocks(quote, quoteLines.join("\n"));
        container.append(quote);
        continue;
      }

      if (/^\s*[-*]\s+/u.test(line)) {
        const list = document.createElement("ul");
        while (index < lines.length && /^\s*[-*]\s+/u.test(lines[index])) {
          appendListItem(list, lines[index].replace(/^\s*[-*]\s+/u, ""));
          index += 1;
        }
        container.append(list);
        continue;
      }

      if (/^\s*\d+[.)]\s+/u.test(line)) {
        const list = document.createElement("ol");
        while (index < lines.length && /^\s*\d+[.)]\s+/u.test(lines[index])) {
          appendListItem(list, lines[index].replace(/^\s*\d+[.)]\s+/u, ""));
          index += 1;
        }
        container.append(list);
        continue;
      }

      const paragraphLines = [];
      while (
        index < lines.length &&
        lines[index].trim() &&
        !isMarkdownBlockStart(lines[index])
      ) {
        paragraphLines.push(lines[index]);
        index += 1;
      }
      appendParagraph(container, paragraphLines);
    }
  }

  function isMarkdownBlockStart(line) {
    const trimmed = line.trim();
    return (
      /^```/u.test(trimmed) ||
      /^---+\s*$/u.test(trimmed) ||
      /^(#{1,4})\s+/u.test(line) ||
      /^>\s?/u.test(line) ||
      /^\s*[-*]\s+/u.test(line) ||
      /^\s*\d+[.)]\s+/u.test(line)
    );
  }

  function appendParagraph(container, lines) {
    const paragraph = document.createElement("p");

    lines.forEach((line, lineIndex) => {
      if (lineIndex > 0) {
        paragraph.append(document.createElement("br"));
      }
      appendInlineMarkdown(paragraph, line);
    });
    container.append(paragraph);
  }

  function appendListItem(list, markdown) {
    const item = document.createElement("li");
    appendInlineMarkdown(item, markdown);
    list.append(item);
  }

  function appendCodeBlock(container, code) {
    const pre = document.createElement("pre");
    const codeElement = document.createElement("code");

    codeElement.textContent = code;
    pre.append(codeElement);
    container.append(pre);
  }

  function appendInlineMarkdown(container, markdown) {
    let remaining = markdown;

    while (remaining) {
      const token = findNextInlineToken(remaining);

      if (!token) {
        container.append(remaining);
        return;
      }

      if (token.index > 0) {
        container.append(remaining.slice(0, token.index));
      }

      appendInlineToken(container, token);
      remaining = remaining.slice(token.index + token.match[0].length);
    }
  }

  function findNextInlineToken(text) {
    const patterns = [
      { type: "code", regex: /`([^`]+)`/u },
      { type: "image", regex: /!\[([^\]]*)\]\(([^)]+)\)/u },
      { type: "link", regex: /\[([^\]]+)\]\(([^)]+)\)/u },
      { type: "strong", regex: /\*\*([^*]+)\*\*/u },
      { type: "strong", regex: /__([^_]+)__/u },
      { type: "delete", regex: /~~([^~]+)~~/u },
      { type: "em", regex: /(^|[^\*])\*([^*]+)\*/u },
      { type: "em", regex: /(^|[^_])_([^_]+)_/u },
    ];

    return patterns.reduce((closest, pattern) => {
      const match = pattern.regex.exec(text);

      if (!match) {
        return closest;
      }

      const index = match.index + (pattern.type === "em" && match[1] ? match[1].length : 0);
      const adjustedMatch = pattern.type === "em"
        ? [match[0].slice(match[1].length), match[2]]
        : match;

      if (!closest || index < closest.index) {
        return { ...pattern, index, match: adjustedMatch };
      }

      return closest;
    }, null);
  }

  function appendInlineToken(container, token) {
    const elementByType = {
      code: "code",
      strong: "strong",
      delete: "del",
      em: "em",
    };

    if (token.type === "link") {
      appendMarkdownLink(container, token.match[1], token.match[2]);
      return;
    }

    if (token.type === "image") {
      appendMarkdownImagePlaceholder(container, token.match[1], token.match[2]);
      return;
    }

    const element = document.createElement(elementByType[token.type] || "span");
    if (token.type === "code") {
      element.textContent = token.match[1];
    } else {
      appendInlineMarkdown(element, token.match[1]);
    }
    container.append(element);
  }

  function appendMarkdownLink(container, text, href) {
    const link = document.createElement("a");

    link.textContent = text;
    if (isSafeMarkdownUrl(href)) {
      link.href = href;
      link.rel = "noreferrer";
    }
    container.append(link);
  }

  function appendMarkdownImagePlaceholder(container, alt, src) {
    const placeholder = document.createElement("span");

    placeholder.className = "markdown-media-placeholder";
    placeholder.textContent = alt ? `图片：${alt}` : "图片";
    placeholder.title = src;
    container.append(placeholder);
  }

  function isSafeMarkdownUrl(url) {
    return /^(https?:|mailto:|#|media:)/iu.test(String(url || "").trim());
  }

  function registerLayoutDebugTools() {
    window.SereinDebugLayout = {
      inspect: inspectLayout,
      setDebugMode: setLayoutDebugMode,
      toggleDebugMode: toggleLayoutDebugMode,
    };
  }

  function toggleLayoutDebugMode() {
    return setLayoutDebugMode(!isLayoutDebugModeEnabled());
  }

  function initializeLayoutDebugState() {
    setLayoutDebugMode(readLayoutDebugPreference(), { persist: false });
  }

  function setLayoutDebugMode(enabled, options = {}) {
    const {
      persist = true,
      select = document.querySelector('[data-setting="layout-debug"]'),
    } = options;
    const nextEnabled = Boolean(enabled);

    if (nextEnabled) {
      document.documentElement.dataset.layoutDebug = "true";
    } else {
      delete document.documentElement.dataset.layoutDebug;
    }

    if (persist) {
      writeLayoutDebugPreference(nextEnabled);
    }

    if (select) {
      select.value = nextEnabled ? "on" : "off";
    }

    return nextEnabled;
  }

  function isLayoutDebugModeEnabled() {
    return document.documentElement.dataset.layoutDebug === "true";
  }

  function readLayoutDebugPreference() {
    try {
      return window.localStorage.getItem("serein-layout-debug") === "true";
    } catch {
      return false;
    }
  }

  function writeLayoutDebugPreference(enabled) {
    try {
      window.localStorage.setItem("serein-layout-debug", String(enabled));
    } catch {
      // Ignore storage failures; the in-page toggle still works for this session.
    }
  }

  function inspectLayout(options = {}) {
    const entryIndex = Number(options.entryIndex || 0);
    const feed = document.querySelector(".diary-feed");
    const year = document.querySelector(".diary-year");
    const yearSummary = document.querySelector(".diary-year > .diary-group-summary");
    const yearContent = document.querySelector(".diary-year > .diary-group-content");
    const month = document.querySelector(".diary-month");
    const monthSummary = document.querySelector(".diary-month > .diary-group-summary");
    const monthContent = document.querySelector(".diary-month > .diary-group-content");
    const entries = [...document.querySelectorAll(".diary-entry, .new-entry")];
    const entry = entries[entryIndex];
    const date = entry?.querySelector(".entry-date");
    const body = entry?.querySelector(".entry-body");

    if (!feed || !year || !month || !entry || !date || !body) {
      console.warn("[Serein layout] Missing layout nodes.", {
        feed,
        year,
        month,
        entry,
        date,
        body,
      });
      return null;
    }

    const entryColumns = parseGridColumns(getComputedStyle(entry).gridTemplateColumns);
    const entryRect = getRect(entry);
    const predicted = predictEntryColumns(entryRect.left, entryColumns);
    const viewportCenter = window.innerWidth / 2;
    const yearRect = getRect(year);
    const bodyRect = getRect(body);
    const bodyCenter = bodyRect.left + bodyRect.width / 2;
    const yearCenter = yearRect.left + yearRect.width / 2;

    const boxes = [
      ["viewport", { left: 0, right: window.innerWidth, width: window.innerWidth }],
      ["feed", getRect(feed)],
      ["year", yearRect],
      ["year summary", getRect(yearSummary)],
      ["year content", getRect(yearContent)],
      ["month", getRect(month)],
      ["month summary", getRect(monthSummary)],
      ["month content", getRect(monthContent)],
      ["entry", entryRect],
      ["date", getRect(date)],
      ["body", bodyRect],
      ["predicted date", predicted.date],
      ["predicted date gap", predicted.dateGap],
      ["predicted body", predicted.body],
      ["predicted right placeholder", predicted.rightPlaceholder],
    ].map(([name, rect]) => ({
      name,
      left: round(rect.left),
      right: round(rect.right),
      width: round(rect.width),
      center: round(rect.left + rect.width / 2),
    }));

    const columns = {
      date: round(entryColumns[0] || 0),
      dateContentGap: round(entryColumns[1] || 0),
      body: round(entryColumns[2] || 0),
      rightPlaceholder: round(entryColumns[3] || 0),
      entryColumnSum: round(entryColumns.reduce((sum, value) => sum + value, 0)),
      entryActualWidth: round(entryRect.width),
    };

    const centers = {
      viewportCenter: round(viewportCenter),
      yearCenter: round(yearCenter),
      bodyCenter: round(bodyCenter),
      bodyMinusViewportCenter: round(bodyCenter - viewportCenter),
      bodyMinusYearCenter: round(bodyCenter - yearCenter),
    };

    const result = {
      entryIndex,
      boxes,
      columns,
      centers,
    };

    console.group("[Serein layout]");
    console.table(boxes);
    console.table([columns]);
    console.table([centers]);
    console.groupEnd();

    return result;
  }

  function getRect(element) {
    if (!element) {
      return { left: 0, right: 0, width: 0 };
    }

    const rect = element.getBoundingClientRect();
    return {
      left: rect.left,
      right: rect.right,
      width: rect.width,
    };
  }

  function parseGridColumns(value) {
    return value
      .split(/\s+/u)
      .map((part) => Number.parseFloat(part))
      .filter((value) => Number.isFinite(value));
  }

  function predictEntryColumns(left, columns) {
    const [date = 0, dateGap = 0, body = 0, rightPlaceholder = 0] = columns;
    const dateLeft = left;
    const dateRight = dateLeft + date;
    const gapLeft = dateRight;
    const gapRight = gapLeft + dateGap;
    const bodyLeft = gapRight;
    const bodyRight = bodyLeft + body;
    const placeholderLeft = bodyRight;
    const placeholderRight = placeholderLeft + rightPlaceholder;

    return {
      date: { left: dateLeft, right: dateRight, width: date },
      dateGap: { left: gapLeft, right: gapRight, width: dateGap },
      body: { left: bodyLeft, right: bodyRight, width: body },
      rightPlaceholder: {
        left: placeholderLeft,
        right: placeholderRight,
        width: rightPlaceholder,
      },
    };
  }

  function round(value) {
    return Math.round(value * 100) / 100;
  }
}());
