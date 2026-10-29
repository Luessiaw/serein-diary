"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

/*
 * createEntry() 依赖完整的浏览器 DOM，无法在 node 里整体执行。这里固定住
 * "什么条目需要来源提示、提示由哪几部分构成" 这两条规则，防止后续改动把
 * 标记挪回放不下的日期栏，或者重新引入多余的文字行。
 */
const read = (...segments) =>
  fs.readFileSync(path.join(__dirname, "..", ...segments), "utf8");

const appSource = read("scripts", "app.js");
const baseCss = read("styles", "base.css");
const tokenCss = read("styles", "tokens.css");

test("only ai-dialogue entries are marked", () => {
  assert.match(
    appSource,
    /if \(metadata\.source_kind === "ai-dialogue"\) \{/,
    "来源提示必须放在 ai-dialogue 的条件分支里",
  );
});

test("the marker is the short AI badge, not a descriptive line", () => {
  const literal = appSource.match(/badge\.textContent = "([^"]+)"/);
  assert.ok(literal, "找不到角标文案赋值");
  assert.equal(literal[1], "AI");
  // 曾经把"对话整理"作为可见文字渲染在正文区，四个字太长；现在只保留角标。
  // 注意 aria-label 里的"由对话整理生成"是给读屏的描述，必须保留。
  assert.doesNotMatch(appSource, /textContent = "对话整理"/);
  assert.doesNotMatch(appSource, /className = "entry-origin"/);
  // 角标需要无障碍名称，纯 "AI" 对读屏无意义。
  assert.match(appSource, /setAttribute\("aria-label", "[^"]+"\)/);
});

test("the badge lives in the reading area, not the date column", () => {
  assert.match(appSource, /reading\.append\(badge\)/);
  assert.doesNotMatch(appSource, /date\.append\(badge\)/);
  // entry-reading 已是定位上下文，角标才能绝对定位到右上角。
  assert.match(baseCss, /\.entry-reading \{[^}]*position: relative;/);
});

test("ai entries get a distinct surface while human entries keep none", () => {
  assert.match(
    baseCss,
    /\.diary-entry\[data-origin-kind="ai-dialogue"\] \.entry-body \{\s*background: var\(--color-entry-ai-surface\)/,
    "AI 条目需要一个区别于纸色的底色",
  );
  // 底色只能作用在 .entry-body，否则会把左侧日期栏一起刷上颜色。
  assert.doesNotMatch(
    baseCss,
    /\.diary-entry\[data-origin-kind="ai-dialogue"\]\s*\{\s*background:/,
  );
});

test("badge text is white and every visual value comes from tokens", () => {
  assert.match(tokenCss, /--color-entry-ai-badge-text:\s*#ffffff/);
  const badgeRule = baseCss.match(/\.entry-origin-badge \{[\s\S]*?\n\}/);
  assert.ok(badgeRule, "找不到 .entry-origin-badge 规则");
  const rule = badgeRule[0];
  assert.match(rule, /color: var\(--color-entry-ai-badge-text\)/);
  // 组件里不应出现硬编码颜色，全部经 token 控制。
  assert.doesNotMatch(rule, /#[0-9a-fA-F]{3,8}\b/);
});
