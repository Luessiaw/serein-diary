/* Data adapter for switching Serein between mock data and backend API data. */
(function () {
  "use strict";

  const DEFAULT_PAGE_LIMIT = 30;

  function createDataAdapter(options = {}) {
    const source = normalizeDataSource(
      options.source || readMetaContent("serein-data-source") || "backend",
    );
    const apiClient = options.apiClient || window.SereinApi.createApiClient(options);

    if (source === "backend") {
      return createBackendAdapter(apiClient);
    }

    return createMockAdapter();
  }

  function createBackendAdapter(apiClient) {
    return {
      source: "backend",
      getSession() {
        return apiClient.requestJson("/auth/session");
      },
      login(password) {
        return apiClient.requestJson("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password }),
        });
      },
      logout() {
        return apiClient.requestJson("/auth/logout", { method: "POST" });
      },
      listEntries(options = {}) {
        const params = createSearchParams({
          limit: options.limit,
          older_than: options.olderThan,
          newer_than: options.newerThan,
          include_deleted: options.includeDeleted,
        });
        return apiClient.requestJson(`/entries${params}`);
      },
      getEntryWindow(options = {}) {
        const params = createSearchParams({
          date: options.date,
          older_count: options.olderCount,
          newer_count: options.newerCount,
          include_deleted: options.includeDeleted,
        });
        return apiClient.requestJson(`/entries/window${params}`);
      },
      getEntry(entryId) {
        return apiClient.requestJson(`/entries/${encodeURIComponent(entryId)}`);
      },
      createEntry(payload) {
        return apiClient.requestJson("/entries", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: payload?.title || null,
            content: payload?.content || "",
          }),
        });
      },
      deleteEntry(entryId) {
        return apiClient.requestJson(`/entries/${encodeURIComponent(entryId)}`, {
          method: "DELETE",
        });
      },
      getEntryDates(options = {}) {
        const params = createSearchParams({
          from: options.from,
          to: options.to,
          include_deleted: options.includeDeleted,
        });
        return apiClient.requestJson(`/entries/dates${params}`);
      },
      listComments(entryId) {
        return apiClient.requestJson(`/entries/${encodeURIComponent(entryId)}/comments`);
      },
      createComment(entryId, payload) {
        return apiClient.requestJson(`/entries/${encodeURIComponent(entryId)}/comments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload || {}),
        });
      },
      deleteComment(entryId, commentId) {
        return apiClient.requestJson(
          `/entries/${encodeURIComponent(entryId)}/comments/${encodeURIComponent(commentId)}`,
          { method: "DELETE" },
        );
      },
      uploadMedia(entryId, payload) {
        const form = new FormData();
        form.append("file", payload.file);
        if (payload.alt) {
          form.append("alt", payload.alt);
        }
        return apiClient.requestJson(`/entries/${encodeURIComponent(entryId)}/media`, {
          method: "POST",
          body: form,
        });
      },
      getMediaUrl(entryId, mediaId) {
        return `${apiClient.apiBase}/entries/${encodeURIComponent(entryId)}/media/${encodeURIComponent(mediaId)}`;
      },
    };
  }

  function createMockAdapter() {
    return {
      source: "mock",
      async getSession() {
        return { authenticated: true, subject: "mock-admin" };
      },
      async login() {
        return { authenticated: true, subject: "mock-admin" };
      },
      async logout() {
        return { authenticated: false, subject: null };
      },
      async listEntries(options = {}) {
        const limit = normalizeLimit(options.limit);
        const includeDeleted = Boolean(options.includeDeleted);
        const summaries = getMockEntryDetails()
          .filter((entry) => includeDeleted || !entry.deleted)
          .map(detailToSummary);
        if (options.olderThan && options.newerThan) {
          throw createMockError(
            "invalid_request",
            "olderThan and newerThan cannot be used together",
            400,
          );
        }
        const pageSource = options.olderThan
          ? summaries.filter((entry) => compareEntryToCursor(entry, options.olderThan) < 0)
          : options.newerThan
            ? summaries.filter((entry) => compareEntryToCursor(entry, options.newerThan) > 0)
            : summaries;
        const items = options.newerThan ? pageSource.slice(0, limit) : pageSource.slice(-limit);
        const hasMore = pageSource.length > limit;

        return {
          items,
          page: {
            limit,
            has_older: options.newerThan ? Boolean(items.length) : hasMore,
            has_newer: options.olderThan ? Boolean(items.length) : hasMore && Boolean(options.newerThan),
            older_cursor: !options.newerThan && hasMore && items.length ? items[0].cursor : null,
            newer_cursor: options.newerThan && hasMore && items.length ? items.at(-1).cursor : null,
          },
        };
      },
      async getEntryWindow(options = {}) {
        const olderCount = normalizeWindowCount(options.olderCount, "older_count");
        const newerCount = normalizeWindowCount(options.newerCount, "newer_count");
        const date = String(options.date || "").slice(0, 10);
        const includeDeleted = Boolean(options.includeDeleted);
        const summaries = getMockEntryDetails()
          .filter((entry) => includeDeleted || !entry.deleted)
          .map(detailToSummary);
        const targetIndices = summaries.reduce((indices, entry, index) => {
          if (entry.created_at.slice(0, 10) === date) {
            indices.push(index);
          }
          return indices;
        }, []);

        if (targetIndices.length === 0) {
          return {
            items: [],
            window: {
              target_date: date,
              older_count: olderCount,
              newer_count: newerCount,
              target_count: 0,
              has_older: false,
              has_newer: false,
              older_cursor: null,
              newer_cursor: null,
            },
          };
        }

        const startIndex = Math.max(0, targetIndices[0] - olderCount);
        const endIndex = Math.min(summaries.length, targetIndices.at(-1) + newerCount + 1);
        const items = summaries.slice(startIndex, endIndex);
        const hasOlder = startIndex > 0;
        const hasNewer = endIndex < summaries.length;

        return {
          items,
          window: {
            target_date: date,
            older_count: olderCount,
            newer_count: newerCount,
            target_count: targetIndices.length,
            has_older: hasOlder,
            has_newer: hasNewer,
            older_cursor: hasOlder && items.length ? items[0].cursor : null,
            newer_cursor: hasNewer && items.length ? items.at(-1).cursor : null,
          },
        };
      },
      async getEntry(entryId) {
        const detail = getMockEntryDetails().find((entry) => entry.id === entryId);
        if (!detail) {
          throw createMockError("entry_not_found", "Entry not found", 404);
        }
        return detail;
      },
      async createEntry(payload) {
        const content = String(payload?.content || "");
        if (!content.trim()) {
          throw createMockError("invalid_request", "content must not be blank", 400);
        }

        const createdAt = createLocalTimestamp();
        const id = crypto.randomUUID ? crypto.randomUUID() : createFallbackUuid();
        const mockEntry = {
          ui: { mode: "reading" },
          data: {
            metadata: {
              schema_version: 1,
              id,
              created_at: createdAt,
              ...(payload?.title ? { title: String(payload.title).trim() } : {}),
            },
            content,
            comments: { schema_version: 1, comments: [] },
            mediaManifest: { schema_version: 1, media: [] },
          },
        };

        window.SereinMockEntries = [
          ...getMockEntries().filter((sample) => sample.ui.mode !== "new"),
          mockEntry,
          ...getMockEntries().filter((sample) => sample.ui.mode === "new"),
        ];
        return mockSampleToDetail(mockEntry);
      },
      async deleteEntry(entryId) {
        const sample = getMockEntries().find((entry) => entry.data.metadata.id === entryId);
        if (!sample) {
          throw createMockError("entry_not_found", "Entry not found", 404);
        }
        sample.data.metadata.deleted_at = createLocalTimestamp();
        return mockSampleToDetail(sample);
      },
      async getEntryDates(options = {}) {
        const includeDeleted = Boolean(options.includeDeleted);
        const counts = new Map();

        getMockEntryDetails().forEach((entry) => {
          if (!includeDeleted && entry.deleted) {
            return;
          }
          const date = entry.created_at.slice(0, 10);
          if (!isDateInRange(date, options.from, options.to)) {
            return;
          }
          counts.set(date, (counts.get(date) || 0) + 1);
        });

        return {
          dates: [...counts.entries()]
            .sort(([left], [right]) => left.localeCompare(right))
            .map(([date, count]) => ({ date, count })),
        };
      },
      async listComments(entryId) {
        return { comments: (await this.getEntry(entryId)).comments };
      },
      async createComment() {
        throw createMockError("not_implemented", "Mock comments are not implemented", 400);
      },
      async deleteComment() {
        throw createMockError("not_implemented", "Mock comments are not implemented", 400);
      },
      async uploadMedia() {
        throw createMockError("not_implemented", "Mock media upload is not implemented", 400);
      },
      getMediaUrl(entryId, mediaId) {
        return `mock-media:${entryId}:${mediaId}`;
      },
    };
  }

  function getMockEntryDetails() {
    return getMockEntries()
      .filter((sample) => sample.ui.mode === "reading")
      .map(mockSampleToDetail)
      .sort((left, right) => (
        left.created_at.localeCompare(right.created_at) || left.id.localeCompare(right.id)
      ));
  }

  function mockSampleToDetail(sample) {
    const metadata = sample.data.metadata;
    const comments = normalizeMockComments(sample.data.comments);
    const media = normalizeMockMedia(sample);
    const deleted = Boolean(metadata.deleted_at);
    const cursor = encodeMockCursor(metadata.created_at, metadata.id);

    return {
      id: metadata.id,
      created_at: metadata.created_at,
      cursor,
      title: metadata.title || null,
      content: sample.data.content || "",
      content_excerpt: createExcerpt(sample.data.content || ""),
      comments,
      media,
      comment_count: comments.length,
      media_count: media.length,
      deleted,
    };
  }

  function detailToSummary(detail) {
    return {
      id: detail.id,
      created_at: detail.created_at,
      cursor: detail.cursor,
      title: detail.title,
      content_excerpt: detail.content_excerpt,
      comment_count: detail.comment_count,
      media_count: detail.media_count,
      deleted: detail.deleted,
    };
  }

  function normalizeMockComments(commentsFile) {
    return (commentsFile?.comments || []).map((comment) => ({
      id: comment.id,
      created_at: comment.created_at,
      content: comment.content || comment.body || "",
      anchor: normalizeMockAnchor(comment.anchor),
    }));
  }

  function normalizeMockAnchor(anchor) {
    if (!anchor) {
      return null;
    }
    if (anchor.type === "quote") {
      return anchor;
    }
    return {
      type: "quote",
      selected_text: anchor.selected_text || anchor.quote || "",
      prefix: anchor.prefix || "",
      suffix: anchor.suffix || "",
    };
  }

  function normalizeMockMedia(sample) {
    const entryId = sample.data.metadata.id;
    const manifestItems = sample.data.mediaManifest?.media || sample.data.media_manifest?.media || [];

    return manifestItems.map((item) => ({
      id: item.id,
      kind: item.kind,
      url: `mock-media:${entryId}:${item.id}`,
      alt: item.alt || null,
      created_at: item.created_at || null,
    }));
  }

  function createSearchParams(values) {
    const params = new URLSearchParams();

    Object.entries(values).forEach(([key, value]) => {
      if (value === undefined || value === null || value === false || value === "") {
        return;
      }
      params.set(key, String(value));
    });

    const serialized = params.toString();
    return serialized ? `?${serialized}` : "";
  }

  function compareEntryToCursor(entry, cursor) {
    const decoded = decodeMockCursor(cursor);
    if (entry.created_at !== decoded.createdAt) {
      return entry.created_at.localeCompare(decoded.createdAt);
    }
    return entry.id.localeCompare(decoded.id);
  }

  function encodeMockCursor(createdAt, id) {
    return window.btoa(unescape(encodeURIComponent(`${createdAt}|${id}`)))
      .replace(/=+$/u, "")
      .replace(/\+/gu, "-")
      .replace(/\//gu, "_");
  }

  function decodeMockCursor(cursor) {
    try {
      const base64 = String(cursor).replace(/-/gu, "+").replace(/_/gu, "/");
      const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
      const decoded = decodeURIComponent(escape(window.atob(padded)));
      const [createdAt, id] = decoded.split("|");
      if (!createdAt || !id) {
        throw new Error("Invalid cursor payload.");
      }
      return { createdAt, id };
    } catch (error) {
      throw createMockError("invalid_cursor", "Invalid pagination cursor", 400, error);
    }
  }

  function normalizeLimit(limit) {
    const value = Number(limit || DEFAULT_PAGE_LIMIT);
    if (!Number.isFinite(value) || value < 1) {
      throw createMockError("invalid_request", "limit must be at least 1", 400);
    }
    return Math.min(Math.floor(value), 100);
  }

  function normalizeWindowCount(count, fieldName) {
    const value = Number(count ?? 12);
    if (!Number.isFinite(value) || value < 0) {
      throw createMockError("invalid_request", `${fieldName} must be at least 0`, 400);
    }
    return Math.min(Math.floor(value), 100);
  }

  function isDateInRange(date, from, to) {
    if (from && date < from) {
      return false;
    }
    if (to && date > to) {
      return false;
    }
    return true;
  }

  function createExcerpt(content) {
    const excerpt = String(content || "").replace(/\s+/gu, " ").trim();
    return excerpt.length > 120 ? `${excerpt.slice(0, 119).trimEnd()}…` : excerpt;
  }

  function createLocalTimestamp() {
    const now = new Date();
    const offsetMinutes = -now.getTimezoneOffset();
    const sign = offsetMinutes >= 0 ? "+" : "-";
    const absoluteMinutes = Math.abs(offsetMinutes);
    const offsetHours = String(Math.floor(absoluteMinutes / 60)).padStart(2, "0");
    const offsetRestMinutes = String(absoluteMinutes % 60).padStart(2, "0");
    const local = new Date(now.getTime() + offsetMinutes * 60 * 1000)
      .toISOString()
      .slice(0, 19);

    return `${local}${sign}${offsetHours}:${offsetRestMinutes}`;
  }

  function createFallbackUuid() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/gu, (char) => {
      const random = Math.floor(Math.random() * 16);
      const value = char === "x" ? random : (random & 0x3) | 0x8;
      return value.toString(16);
    });
  }

  function createMockError(code, message, status, cause) {
    const error = new Error(message);
    error.name = "SereinMockDataError";
    error.code = code;
    error.status = status;
    error.cause = cause;
    return error;
  }

  function getMockEntries() {
    return window.SereinMockEntries || [];
  }

  function normalizeDataSource(value) {
    return value === "backend" ? "backend" : "mock";
  }

  function readMetaContent(name) {
    return window.SereinApi?.readMetaContent(name) || "";
  }

  window.SereinData = {
    createDataAdapter,
  };
})();
