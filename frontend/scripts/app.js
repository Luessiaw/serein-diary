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
  const groupOpenState = new Map();
  const loadDebugState = {
    enabled: readLoadDebugPreference(),
    history: [],
  };
  let loadCheckAfterLayoutChangeRunning = false;
  let pendingLoadCheckAfterLayoutChange = false;
  let activeNewEntryContentControl = null;

  initializeEditorExperimentState();
  initializeLoadedWindow();
  renderFeed({ focusNewEntry: true, scrollToEnd: true });
  app.addEventListener("scroll", handleScroll, { passive: true });
  registerLoadDebugTools();
  registerLayoutDebugTools();
  createSidebarShell();
  createEditorExperimentToggle();
  createLayoutDebugToggle();

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

      const body = contentControl.readMarkdown().trim();
      if (!body) {
        message.textContent = "请先写下一些内容。";
        contentControl.focus();
        return;
      }

      addStaticEntry(title.value.trim(), body);
      renderFeed({ focusNewEntry: true, scrollToEnd: true });
    });

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
      message.textContent = "正在拉取更早的日记……";
      control.append(spinner, message);
    } else if (loadState.status === "error") {
      const retry = document.createElement("button");

      message.textContent = `拉取信息失败：${loadState.errorMessage}`;
      retry.className = "load-control-retry";
      retry.type = "button";
      retry.textContent = "重试";
      retry.addEventListener("click", () => {
        debugLoad("retry clicked");
        void loadEarlierEntries({ source: "retry" });
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
    if (!shouldLoadEarlierEntries({ source: "scroll" })) {
      return;
    }

    debugLoad("scroll triggered earlier-load");
    void loadEarlierEntries({ source: "scroll" });
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

    if (loadState.status === "loading" || loadState.status === "complete") {
      debugShouldLoad(false, "blocked-by-status", { source, verbose });
      return false;
    }

    if (loadState.visibleStartIndex <= 0) {
      loadState.status = "complete";
      debugShouldLoad(false, "no-earlier-content", { source, verbose });
      renderFeed();
      return false;
    }

    const entries = getVisibleEntries();
    if (entries.length === 0) {
      const shouldLoad = app.scrollTop <= app.clientHeight;

      debugShouldLoad(shouldLoad, "no-visible-entries", {
        source,
        verbose,
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
      debugShouldLoad(false, "blocked-by-status", { source, verbose });
      return false;
    }

    if (loadState.visibleStartIndex <= 0) {
      loadState.status = "complete";
      debugShouldLoad(false, "no-earlier-content", { source, verbose });
      renderFeed();
      return false;
    }

    const overflow = app.scrollHeight - app.clientHeight;
    const shouldLoad = overflow <= settings.layoutFillTolerance;

    debugShouldLoad(shouldLoad, "layout-fill-threshold", {
      source,
      verbose,
      scrollHeight: app.scrollHeight,
      clientHeight: app.clientHeight,
      overflow,
      layoutFillTolerance: settings.layoutFillTolerance,
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

  function registerLoadDebugTools() {
    window.SereinDebugLoad = {
      clearLogs: clearLoadDebugLogs,
      dumpLogs: dumpLoadDebugLogs,
      inspect: inspectLoadState,
      setEnabled: setLoadDebugEnabled,
      get enabled() {
        return loadDebugState.enabled;
      },
    };

    debugLoad("debug tools registered", {
      hint: "Use SereinDebugLoad.inspect(), SereinDebugLoad.dumpLogs(), or SereinDebugLoad.setEnabled(false).",
    });
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

  function debugShouldLoad(shouldLoad, reason, details = {}) {
    if (!details.verbose && !shouldLoad) {
      return;
    }

    debugLoad(`shouldLoadEarlierEntries -> ${shouldLoad}`, {
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

    return {
      status: loadState.status,
      visibleStartIndex: loadState.visibleStartIndex,
      totalReadingEntries,
      loadedReadingEntries: totalReadingEntries - loadState.visibleStartIndex,
      visibleDomEntries: visibleEntries.length,
      firstVisibleEntryId: firstVisibleEntry?.dataset.entryId || null,
      lastVisibleEntryId: lastVisibleEntry?.dataset.entryId || null,
      scrollTop: Math.round(app.scrollTop),
      clientHeight: Math.round(app.clientHeight),
      scrollHeight: Math.round(app.scrollHeight),
      triggerEntryIndexSetting: settings.triggerEntryIndex,
      pageSize: settings.pageSize,
      pendingPostLayoutCheck: pendingLoadCheckAfterLayoutChange,
      postLayoutCheckRunning: loadCheckAfterLayoutChangeRunning,
    };
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
    const title = document.createElement("h2");
    const close = document.createElement("button");
    const placeholder = document.createElement("p");
    const sidebarId = "serein-sidebar";

    button.className = "sidebar-menu-button";
    button.type = "button";
    button.title = "打开侧边栏";
    button.setAttribute("aria-label", "打开侧边栏");
    button.setAttribute("aria-controls", sidebarId);
    button.setAttribute("aria-expanded", "false");
    button.innerHTML = "<span></span><span></span><span></span>";

    backdrop.className = "sidebar-backdrop";
    backdrop.hidden = true;

    sidebar.className = "app-sidebar";
    sidebar.id = sidebarId;
    sidebar.hidden = true;
    sidebar.setAttribute("aria-label", "信息与设置侧边栏");
    sidebar.setAttribute("aria-modal", "true");
    sidebar.setAttribute("role", "dialog");

    header.className = "app-sidebar-header";
    title.className = "app-sidebar-title";
    title.textContent = "Serein";
    close.className = "app-sidebar-close";
    close.type = "button";
    close.textContent = "×";
    close.title = "关闭侧边栏";
    close.setAttribute("aria-label", "关闭侧边栏");
    placeholder.className = "app-sidebar-placeholder";
    placeholder.textContent = "侧边栏框架已就绪。信息、设置和导航内容将在后续阶段加入。";

    header.append(title, close);
    sidebar.append(header, placeholder);
    document.body.append(button, backdrop, sidebar);

    button.addEventListener("click", () => {
      setSidebarOpen(true, { button, backdrop, sidebar });
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
      if (event.key !== "Escape" || !isSidebarOpen()) {
        return;
      }

      setSidebarOpen(false, { button, backdrop, sidebar });
      button.focus({ preventScroll: true });
    });
  }

  function setSidebarOpen(open, elements = {}) {
    const button = elements.button || document.querySelector(".sidebar-menu-button");
    const backdrop = elements.backdrop || document.querySelector(".sidebar-backdrop");
    const sidebar = elements.sidebar || document.querySelector(".app-sidebar");
    const nextOpen = Boolean(open);

    document.body.dataset.sidebarOpen = String(nextOpen);

    if (button) {
      button.setAttribute("aria-expanded", String(nextOpen));
      button.title = nextOpen ? "关闭侧边栏" : "打开侧边栏";
      button.setAttribute("aria-label", nextOpen ? "关闭侧边栏" : "打开侧边栏");
    }

    if (backdrop) {
      backdrop.hidden = !nextOpen;
    }

    if (sidebar) {
      sidebar.hidden = !nextOpen;
      if (nextOpen) {
        sidebar.querySelector(".app-sidebar-close")?.focus({ preventScroll: true });
      }
    }
  }

  function isSidebarOpen() {
    return document.body.dataset.sidebarOpen === "true";
  }

  function createEditorExperimentToggle() {
    const button = document.createElement("button");

    registerEditorExperimentTools();
    button.className = "editor-experiment-toggle";
    button.type = "button";
    button.title = "切换新建区编辑器实验";
    button.setAttribute("aria-label", "切换新建区编辑器实验");
    setTiptapExperimentEnabled(readEditorExperimentPreference(), { persist: false, button });
    button.addEventListener("click", () => {
      setTiptapExperimentEnabled(!isTiptapExperimentEnabled(), { button });
      renderFeed({ focusNewEntry: true, scrollToEnd: true });
    });
    document.body.append(button);
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
    if (readEditorExperimentPreference()) {
      document.documentElement.dataset.editorExperiment = "tiptap";
    }
  }

  function setTiptapExperimentEnabled(enabled, options = {}) {
    const { persist = true, button = document.querySelector(".editor-experiment-toggle") } = options;
    const nextEnabled = Boolean(enabled);

    if (nextEnabled) {
      document.documentElement.dataset.editorExperiment = "tiptap";
    } else {
      delete document.documentElement.dataset.editorExperiment;
    }

    if (persist) {
      writeEditorExperimentPreference(nextEnabled);
    }

    if (button) {
      button.textContent = nextEnabled ? "Tiptap demo" : "Textarea";
      button.setAttribute("aria-pressed", String(nextEnabled));
    }

    return nextEnabled;
  }

  function isTiptapExperimentEnabled() {
    return document.documentElement.dataset.editorExperiment === "tiptap";
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

  function registerLayoutDebugTools() {
    window.SereinDebugLayout = {
      inspect: inspectLayout,
      setDebugMode: setLayoutDebugMode,
      toggleDebugMode: toggleLayoutDebugMode,
    };
  }

  function createLayoutDebugToggle() {
    const button = document.createElement("button");
    const initialEnabled = readLayoutDebugPreference();

    button.className = "layout-debug-toggle";
    button.type = "button";
    button.title = "切换布局调试边框";
    button.setAttribute("aria-label", "切换布局调试边框");
    setLayoutDebugMode(initialEnabled, { persist: false, button });
    button.addEventListener("click", () => {
      toggleLayoutDebugMode(button);
    });
    document.body.append(button);
  }

  function toggleLayoutDebugMode(button = document.querySelector(".layout-debug-toggle")) {
    return setLayoutDebugMode(!isLayoutDebugModeEnabled(), { button });
  }

  function setLayoutDebugMode(enabled, options = {}) {
    const { persist = true, button = document.querySelector(".layout-debug-toggle") } = options;
    const nextEnabled = Boolean(enabled);

    if (nextEnabled) {
      document.documentElement.dataset.layoutDebug = "true";
    } else {
      delete document.documentElement.dataset.layoutDebug;
    }

    if (persist) {
      writeLayoutDebugPreference(nextEnabled);
    }

    if (button) {
      button.textContent = nextEnabled ? "Debug mode" : "Normal mode";
      button.setAttribute("aria-pressed", String(nextEnabled));
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
