(function initializeSereinTypingFocus(global) {
  "use strict";

  const DEFAULT_FOCUS_BAND = Object.freeze({
    startRatio: 0.55,
    targetRatio: 0.60,
    endRatio: 0.65,
  });

  function clamp(value, minimum, maximum) {
    return Math.min(Math.max(value, minimum), maximum);
  }

  function normalizeFocusBand(focusBand = {}) {
    const startRatio = readRatio(focusBand.startRatio, DEFAULT_FOCUS_BAND.startRatio);
    const endRatio = readRatio(focusBand.endRatio, DEFAULT_FOCUS_BAND.endRatio);
    const minimum = Math.min(startRatio, endRatio);
    const maximum = Math.max(startRatio, endRatio);

    return {
      startRatio: minimum,
      targetRatio: clamp(
        readRatio(focusBand.targetRatio, DEFAULT_FOCUS_BAND.targetRatio),
        minimum,
        maximum,
      ),
      endRatio: maximum,
    };
  }

  function readRatio(value, fallback) {
    const number = Number(value);

    return Number.isFinite(number) ? clamp(number, 0, 1) : fallback;
  }

  function resolveVisibleViewport(bounds) {
    const containerTop = Number(bounds.containerTop);
    const containerBottom = Number(bounds.containerBottom);
    const viewportTop = Number(bounds.viewportTop);
    const viewportBottom = Number(bounds.viewportBottom);
    const top = Math.max(containerTop, viewportTop);
    const bottom = Math.min(containerBottom, viewportBottom);

    if (![top, bottom].every(Number.isFinite) || bottom <= top) {
      return null;
    }

    return { top, bottom, height: bottom - top };
  }

  function resolveScrollAdjustment(options) {
    const visibleTop = Number(options.visibleTop);
    const visibleBottom = Number(options.visibleBottom);
    const caretTop = Number(options.caretTop);
    const scrollTop = Number(options.scrollTop);
    const scrollHeight = Number(options.scrollHeight);
    const clientHeight = Number(options.clientHeight);
    const engaged = Boolean(options.engaged);
    const band = normalizeFocusBand(options.focusBand);

    if (![visibleTop, visibleBottom, caretTop, scrollTop, scrollHeight, clientHeight].every(Number.isFinite)) {
      return { delta: 0, targetScrollTop: scrollTop, reason: "invalid-geometry" };
    }

    const visibleHeight = visibleBottom - visibleTop;
    const maximumScrollTop = Math.max(0, scrollHeight - clientHeight);
    const bandTop = visibleTop + visibleHeight * band.startRatio;
    const targetTop = visibleTop + visibleHeight * band.targetRatio;
    const bandBottom = visibleTop + visibleHeight * band.endRatio;

    if (visibleHeight <= 0 || maximumScrollTop <= 0) {
      return {
        delta: 0,
        targetScrollTop: clamp(scrollTop, 0, maximumScrollTop),
        bandTop,
        targetTop,
        bandBottom,
        reason: "no-scroll-space",
      };
    }

    if (!engaged && caretTop <= bandBottom) {
      return {
        delta: 0,
        targetScrollTop: clamp(scrollTop, 0, maximumScrollTop),
        bandTop,
        targetTop,
        bandBottom,
        reason: "not-engaged",
      };
    }

    if (engaged && caretTop >= bandTop && caretTop <= bandBottom) {
      return {
        delta: 0,
        targetScrollTop: clamp(scrollTop, 0, maximumScrollTop),
        bandTop,
        targetTop,
        bandBottom,
        reason: "inside-band",
      };
    }

    const requestedScrollTop = scrollTop + caretTop - targetTop;
    const targetScrollTop = clamp(requestedScrollTop, 0, maximumScrollTop);

    return {
      delta: targetScrollTop - scrollTop,
      targetScrollTop,
      bandTop,
      targetTop,
      bandBottom,
      reason: targetScrollTop === requestedScrollTop ? "adjust" : "clamped",
    };
  }

  function createController(options) {
    const textarea = options.textarea;
    const scrollContainer = options.scrollContainer;
    const resize = typeof options.resize === "function" ? options.resize : () => {};
    const onDebug = typeof options.onDebug === "function" ? options.onDebug : () => {};
    const focusBand = normalizeFocusBand(options.focusBand);
    const mirror = createCaretMirror(textarea.ownerDocument);
    const visualViewport = textarea.ownerDocument.defaultView?.visualViewport || null;
    const state = {
      composing: false,
      destroyed: false,
      engaged: false,
      frameId: null,
      pendingComposedInput: false,
      suspended: false,
      lastMeasurement: null,
    };

    function mount() {
      textarea.addEventListener("input", handleInput);
      textarea.addEventListener("compositionstart", handleCompositionStart);
      textarea.addEventListener("compositionend", handleCompositionEnd);
      scrollContainer.addEventListener("wheel", suspendForManualScroll, { passive: true });
      scrollContainer.addEventListener("touchmove", suspendForManualScroll, { passive: true });
      scrollContainer.addEventListener("pointerdown", handlePointerDown, { passive: true });
      scrollContainer.addEventListener("keydown", handleScrollKey);
      visualViewport?.addEventListener("resize", handleViewportChange, { passive: true });
      visualViewport?.addEventListener("scroll", handleViewportChange, { passive: true });
    }

    function destroy() {
      if (state.destroyed) {
        return;
      }

      state.destroyed = true;
      cancelScheduledFollow();
      textarea.removeEventListener("input", handleInput);
      textarea.removeEventListener("compositionstart", handleCompositionStart);
      textarea.removeEventListener("compositionend", handleCompositionEnd);
      scrollContainer.removeEventListener("wheel", suspendForManualScroll);
      scrollContainer.removeEventListener("touchmove", suspendForManualScroll);
      scrollContainer.removeEventListener("pointerdown", handlePointerDown);
      scrollContainer.removeEventListener("keydown", handleScrollKey);
      visualViewport?.removeEventListener("resize", handleViewportChange);
      visualViewport?.removeEventListener("scroll", handleViewportChange);
      mirror.remove();
    }

    function reset() {
      cancelScheduledFollow();
      state.composing = false;
      state.engaged = false;
      state.pendingComposedInput = false;
      state.suspended = false;
      state.lastMeasurement = null;
    }

    function handleInput(event) {
      resize();

      if (event.isComposing || state.composing) {
        state.pendingComposedInput = true;
        onDebug("composition input resized", inspect());
        return;
      }

      resumeAndSchedule("input");
    }

    function handleCompositionStart() {
      state.composing = true;
      state.pendingComposedInput = false;
      cancelScheduledFollow();
      onDebug("composition started", inspect());
    }

    function handleCompositionEnd() {
      state.composing = false;
      if (state.pendingComposedInput) {
        state.pendingComposedInput = false;
        resumeAndSchedule("composition-end");
      }
    }

    function resumeAndSchedule(source) {
      const wasSuspended = state.suspended;

      state.suspended = false;
      if (wasSuspended) {
        state.engaged = true;
      }
      scheduleFollow(source);
    }

    function handlePointerDown(event) {
      if (event.target === scrollContainer) {
        suspendForManualScroll();
      }
    }

    function handleScrollKey(event) {
      if (["PageDown", "PageUp"].includes(event.key)) {
        suspendForManualScroll();
      }
    }

    function suspendForManualScroll() {
      if (textarea.ownerDocument.activeElement !== textarea) {
        return;
      }

      state.suspended = true;
      cancelScheduledFollow();
      onDebug("typing follow suspended", inspect());
    }

    function handleViewportChange() {
      if (state.engaged && !state.suspended && textarea.ownerDocument.activeElement === textarea) {
        scheduleFollow("visual-viewport");
      }
    }

    function scheduleFollow(source) {
      if (state.destroyed || state.composing || state.suspended) {
        return;
      }

      cancelScheduledFollow();
      state.frameId = global.requestAnimationFrame(() => {
        state.frameId = null;
        followCaret(source);
      });
    }

    function cancelScheduledFollow() {
      if (state.frameId !== null) {
        global.cancelAnimationFrame(state.frameId);
        state.frameId = null;
      }
    }

    function followCaret(source) {
      if (state.destroyed || state.suspended || textarea.ownerDocument.activeElement !== textarea) {
        return;
      }

      const viewport = measureVisibleViewport(scrollContainer, visualViewport);
      const caret = measureTextareaCaret(textarea, mirror);

      if (!viewport || !caret) {
        onDebug("typing follow skipped", { source, reason: "measurement-unavailable" });
        return;
      }

      const decision = resolveScrollAdjustment({
        visibleTop: viewport.top,
        visibleBottom: viewport.bottom,
        caretTop: caret.top,
        scrollTop: scrollContainer.scrollTop,
        scrollHeight: scrollContainer.scrollHeight,
        clientHeight: scrollContainer.clientHeight,
        engaged: state.engaged,
        focusBand,
      });

      if (!state.engaged && caret.top > decision.bandBottom) {
        state.engaged = true;
      }

      if (decision.delta) {
        setScrollTopWithoutSmooth(scrollContainer, decision.targetScrollTop);
      }

      state.lastMeasurement = {
        source,
        caretTop: caret.top,
        caretLineHeight: caret.lineHeight,
        visibleTop: viewport.top,
        visibleBottom: viewport.bottom,
        visibleHeight: viewport.height,
        bandTop: decision.bandTop,
        bandBottom: decision.bandBottom,
        targetTop: decision.targetTop,
        adjustment: decision.delta,
        decision: decision.reason,
      };
      onDebug("typing focus resolved", inspect());
    }

    function inspect() {
      return {
        composing: state.composing,
        engaged: state.engaged,
        suspended: state.suspended,
        framePending: state.frameId !== null,
        focusBand: { ...focusBand },
        lastMeasurement: state.lastMeasurement ? { ...state.lastMeasurement } : null,
      };
    }

    return { destroy, inspect, mount, reset };
  }

  function measureVisibleViewport(scrollContainer, visualViewport) {
    const containerRect = scrollContainer.getBoundingClientRect();
    const viewportTop = visualViewport ? visualViewport.offsetTop : 0;
    const viewportBottom = visualViewport
      ? visualViewport.offsetTop + visualViewport.height
      : scrollContainer.ownerDocument.defaultView.innerHeight;

    return resolveVisibleViewport({
      containerTop: containerRect.top,
      containerBottom: containerRect.bottom,
      viewportTop,
      viewportBottom,
    });
  }

  function createCaretMirror(document) {
    const mirror = document.createElement("div");

    mirror.dataset.sereinTypingCaretMirror = "true";
    mirror.setAttribute("aria-hidden", "true");
    mirror.style.position = "fixed";
    mirror.style.insetBlockStart = "0";
    mirror.style.insetInlineStart = "-10000px";
    mirror.style.visibility = "hidden";
    mirror.style.pointerEvents = "none";
    mirror.style.whiteSpace = "pre-wrap";
    document.body.append(mirror);
    return mirror;
  }

  function measureTextareaCaret(textarea, mirror) {
    const selectionStart = textarea.selectionStart;

    if (!Number.isFinite(selectionStart)) {
      return null;
    }

    const styles = textarea.ownerDocument.defaultView.getComputedStyle(textarea);
    const marker = textarea.ownerDocument.createElement("span");
    const mirrorProperties = [
      "borderBlockEndWidth",
      "borderBlockStartWidth",
      "borderInlineEndWidth",
      "borderInlineStartWidth",
      "boxSizing",
      "direction",
      "fontFamily",
      "fontSize",
      "fontStyle",
      "fontWeight",
      "letterSpacing",
      "lineHeight",
      "paddingBlockEnd",
      "paddingBlockStart",
      "paddingInlineEnd",
      "paddingInlineStart",
      "tabSize",
      "textAlign",
      "textIndent",
      "textTransform",
      "wordBreak",
      "wordSpacing",
    ];

    mirrorProperties.forEach((property) => {
      mirror.style[property] = styles[property];
    });
    mirror.style.inlineSize = `${textarea.clientWidth}px`;
    mirror.style.overflowWrap = styles.overflowWrap || "break-word";
    mirror.replaceChildren();
    mirror.append(textarea.ownerDocument.createTextNode(textarea.value.slice(0, selectionStart)));
    marker.textContent = "\u200b";
    mirror.append(marker);

    const textareaRect = textarea.getBoundingClientRect();
    const mirrorRect = mirror.getBoundingClientRect();
    const markerRect = marker.getBoundingClientRect();
    const lineHeight = Number.parseFloat(styles.lineHeight) || markerRect.height || 0;

    return {
      top: textareaRect.top + markerRect.top - mirrorRect.top - textarea.scrollTop,
      lineHeight,
    };
  }

  function setScrollTopWithoutSmooth(scrollContainer, top) {
    const previousBehavior = scrollContainer.style.scrollBehavior;

    scrollContainer.style.scrollBehavior = "auto";
    scrollContainer.scrollTop = Math.max(0, top);
    scrollContainer.style.scrollBehavior = previousBehavior;
  }

  global.SereinTypingFocus = Object.freeze({
    createController,
    normalizeFocusBand,
    resolveScrollAdjustment,
    resolveVisibleViewport,
  });
})(typeof window === "undefined" ? globalThis : window);
