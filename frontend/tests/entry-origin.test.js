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

test("badge stays legible on the ai card surface", () => {
  const surface = tokenCss.match(/--color-entry-ai-surface:\s*(#[0-9a-fA-F]{6})/);
  const scrim = tokenCss.match(/--color-entry-ai-badge-scrim:\s*rgb\(([^)]+)\)/);
  const badgeFg = tokenCss.match(/--color-entry-ai-badge-text:\s*(#[0-9a-fA-F]{6})/);
  assert.ok(surface, "找不到卡片底色 token");
  assert.ok(scrim, "找不到角标底衬 token");
  assert.ok(badgeFg, "找不到角标文字颜色 token");

  // 角标没有实底，白字实际压在「半透明底衬 + 卡片底色」的合成色上，
  // 所以要先把两者按 alpha 合成再算对比度，直接拿 scrim 的颜色会算错。
  const [r, g, b, alpha = "1"] = scrim[1].split(/[\s,/]+/).filter(Boolean);
  const composite = compositeOver(
    `#${toHex(r)}${toHex(g)}${toHex(b)}`,
    Number(alpha),
    surface[1],
  );
  const contrast = relativeLuminanceRatio(badgeFg[1], composite);

  // 角标字号只有 0.62rem，对比度必须明显高于 WCAG AA 的 4.5:1 才不显虚。
  assert.ok(
    contrast >= 4.5,
    `角标文字与底部的对比度只有 ${contrast.toFixed(2)}:1（合成色 ${composite}），小字号下会看不清`,
  );

  // 白字：若底衬太淡，卡片再浅也不可读，这条防止有人只调卡片不调底衬。
  assert.equal(badgeFg[1].toLowerCase(), "#ffffff");
});

test("ai card body text still meets contrast on the darker surface", () => {
  const surface = tokenCss.match(/--color-entry-ai-surface:\s*(#[0-9a-fA-F]{6})/);
  const ink = tokenCss.match(/--color-ink:\s*(#[0-9a-fA-F]{6})/);
  assert.ok(surface && ink, "找不到卡片底色或正文颜色 token");
  const contrast = relativeLuminanceRatio(ink[1], surface[1]);
  assert.ok(
    contrast >= 4.5,
    `正文在 AI 卡片底色上只有 ${contrast.toFixed(2)}:1，加深卡片前必须重新检查`,
  );
});

test("badge visual values come from tokens, never hardcoded", () => {
  const badgeRule = baseCss.match(/\.entry-origin-badge \{[\s\S]*?\n\}/);
  assert.ok(badgeRule, "找不到 .entry-origin-badge 规则");
  const rule = badgeRule[0];
  assert.match(rule, /color: var\(--color-entry-ai-badge-text\)/);
  assert.match(rule, /background: var\(--color-entry-ai-badge-scrim\)/);
  assert.doesNotMatch(rule, /#[0-9a-fA-F]{3,8}\b/);
  assert.doesNotMatch(rule, /rgb[a]?\(/);
});

function relativeLuminance(hex) {
  const channels = hex.replace("#", "").match(/../g).map((h) => {
    const v = parseInt(h, 16) / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function relativeLuminanceRatio(a, b) {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

function toHex(value) {
  return Number(value).toString(16).padStart(2, "0");
}

function compositeOver(fgHex, alpha, bgHex) {
  const fg = fgHex.replace("#", "").match(/../g).map((h) => parseInt(h, 16));
  const bg = bgHex.replace("#", "").match(/../g).map((h) => parseInt(h, 16));
  const mixed = fg.map((v, i) => Math.round(v * alpha + bg[i] * (1 - alpha)));
  return `#${mixed.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}
