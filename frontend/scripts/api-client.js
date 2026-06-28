/* Minimal fetch wrapper for Serein API calls. */
(function () {
  "use strict";

  function createApiClient(options = {}) {
    const apiBase = normalizeApiBase(options.apiBase || readMetaContent("serein-api-base") || "/api/v1");

    return {
      apiBase,
      requestJson(path, requestOptions = {}) {
        return requestJson(`${apiBase}${normalizeApiPath(path)}`, requestOptions);
      },
    };
  }

  async function requestJson(url, options = {}) {
    const response = await window.fetch(url, {
      cache: "no-store",
      credentials: "same-origin",
      ...options,
    });

    let body = null;
    try {
      body = await response.json();
    } catch {
      // Empty or non-JSON responses are handled below.
    }

    if (!response.ok) {
      throw createApiError(response, body);
    }

    return body || {};
  }

  function createApiError(response, body) {
    const apiError = body?.error || body?.detail?.error || null;
    const message = apiError?.message || body?.detail || `请求失败：${response.status}`;
    const error = new Error(message);

    error.name = "SereinApiError";
    error.status = response.status;
    error.code = apiError?.code || null;
    error.body = body;
    return error;
  }

  function normalizeApiBase(value) {
    const trimmed = String(value || "/api/v1").trim() || "/api/v1";
    return trimmed.replace(/\/$/u, "");
  }

  function normalizeApiPath(path) {
    const value = String(path || "");
    return value.startsWith("/") ? value : `/${value}`;
  }

  function readMetaContent(name) {
    return document.querySelector(`meta[name="${name}"]`)?.content?.trim() || "";
  }

  window.SereinApi = {
    createApiClient,
    readMetaContent,
  };
})();
