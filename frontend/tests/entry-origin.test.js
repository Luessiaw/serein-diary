"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

/*
 * createEntry() 依赖完整的浏览器 DOM，无法在 node 里整体执行。这里只把
 * "什么情况下显示来源标记、显示在哪里" 这两条规则固定下来，防止后续改动把
 * 标记挪回放不下的日期栏。
 */
const appSource = fs.readFileSync(
  path.join(__dirname, "..", "scripts", "app.js"),
  "utf8",
);

test("marks only ai-dialogue entries as 对话整理", () => {
  const literal = appSource.match(/origin\.textContent = "([^"]+)"/);
  assert.ok(literal, "找不到来源标记的文案赋值");
  assert.equal(literal[1], "对话整理");
  assert.match(
    appSource,
    /metadata\.source_kind === "ai-dialogue"/,
    "只有 ai-dialogue 才应显示来源标记",
  );
});

test("renders the marker inside the reading area, not the date column", () => {
  // 日期栏是固定 --date-control-width 的窄列；把四个字放进去会溢出到正文。
  assert.match(appSource, /header\.prepend\(origin\)/);
  assert.doesNotMatch(appSource, /date\.append\(origin\)/);
});

test("human entries render exactly as before", () => {
  // 手写条目不创建 .entry-origin 节点，entry-header 与正文保持原样。
  assert.match(
    appSource,
    /if \(metadata\.source_kind === "ai-dialogue"\) \{/,
    "标记必须放在条件分支里，不能让手写条目也生成空节点",
  );
});
