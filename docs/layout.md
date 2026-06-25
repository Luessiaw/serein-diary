# 布局说明

本文说明当前静态前端的 HTML 嵌套结构，以及手动调整视觉对齐时应优先修改的
CSS token。当前布局主要由 `frontend/scripts/app.js` 生成 DOM，由
`frontend/styles/base.css` 消费 `frontend/styles/tokens.css` 中的变量。

## HTML 嵌套结构

页面入口只有一个滚动容器：

```html
<main id="app" class="diary-scroll-region">
  <section class="diary-feed">
    <div class="load-control">...</div>

    <details class="diary-year" open>
      <summary class="diary-group-summary">2026</summary>
      <div class="diary-group-content">
        <details class="diary-month" open>
          <summary class="diary-group-summary">06</summary>
          <div class="diary-group-content">
            <article class="diary-entry">
              <time class="entry-date">
                <span class="entry-day">24</span>
                <span class="entry-time">19:10</span>
              </time>
              <div class="entry-body">
                <h2 class="entry-title">标题</h2>
                <div class="entry-content">
                  <p>正文</p>
                </div>
              </div>
            </article>

            <section class="new-entry">
              <p class="entry-date new-entry-date">现在</p>
              <div class="entry-body new-entry-body">
                <form class="new-entry-form">...</form>
              </div>
            </section>
          </div>
        </details>
      </div>
    </details>
  </section>
</main>
```

几点需要记住：

- 年份、月份使用原生 `<details>` / `<summary>`，所以折叠功能来自浏览器。
- 当前布局是三层嵌套网格：年份盒子包住月份盒子，月份盒子包住日记条目盒子，
  日记条目盒子再包住日期和正文。年、月、日因此处在同一条真实布局链上，而
  不是靠 padding 临时偏移。
- 新建日记也放在当前年/月分组里；它没有持久化 `created_at`，但前端用打开页面时的临时时间归组。
- 窄屏下 `.diary-year`、`.diary-month`、`.diary-entry`、`.new-entry` 会退回普通块布局。

抽象成盒子关系如下：

```text
Box-year
├── year label: 2026
└── Box-month
    ├── month label: 06
    └── Box-entry
        ├── date label: 25 / 12:35
        └── body: 正文
```

对应的横向列关系是：

```text
[年] [年-月间距] [月] [月-日间距] [日] [日-正文间距] [正文]
```

为了让正文而不是整条时间轴保持居中，CSS 会在正文右侧自动保留一块与左侧
“年 + 年月间距 + 月 + 月日间距 + 日 + 日正文间距”等宽的隐形空间。

## 横向对齐参数

优先修改 `tokens.css` 的“阅读布局”分组：

```css
--reading-width: 46rem;
--year-control-width: 8rem;
--month-control-width: 4rem;
--date-control-width: 3.5rem;
--year-month-inline-gap: var(--space-1);
--month-date-inline-gap: var(--space-1);
--date-content-gap: clamp(0.25rem, 2vw, 0.5rem);
--page-gutter: clamp(1rem, 4vw, 3rem);
```

- `--reading-width`：正文列宽度，只影响正文，不包含年/月/日控件。
- `--year-control-width`：年份左侧控件列宽度。
- `--month-control-width`：月份左侧控件列宽度。
- `--date-control-width`：日期/“现在”左侧控件列宽度。
- `--year-month-inline-gap`：年份列与月份列之间的横向距离。
- `--month-date-inline-gap`：月份列与日期列之间的横向距离。
- `--date-content-gap`：日期列与正文列之间的横向距离。
- `--page-gutter`：整个滚动区左右边距，主要防止窄屏贴边。

如果要让正文更宽，只改 `--reading-width`。如果要让年、月、日彼此靠近或远离，
分别改 `--year-month-inline-gap` 和 `--month-date-inline-gap`。如果要让日期靠近
或远离正文，改 `--date-content-gap`。如果某一类控件的数字太挤或太松，分别改
对应的 `--*-control-width`。

年/月控件内部是“箭头 + label”的小网格，并且默认左对齐。因此：

- `--year-control-width` / `--month-control-width` 控制整个年/月控件列宽。
- `--group-summary-chevron-gap` 控制箭头与年/月数字之间的距离。
- `--year-month-inline-gap` / `--month-date-inline-gap` 控制控件列与下一层列之间的距离。

实现上不再使用 `padding-inline` 给日记条目补偿年/月空间。年、月、日和正文
分别处在嵌套 grid 的真实列中，因此优先改这些 token，而不是直接给
`.diary-entry`、`.diary-month` 或 `.diary-year` 增加横向 padding。

## 纵向对齐参数

这些 token 影响年、月、条目之间的垂直节奏：

```css
--feed-padding-block: var(--space-6);
--year-block-gap: var(--year-gap);
--month-block-gap: var(--year-month-block-gap);
--entry-block-gap: var(--month-date-block-gap);
--group-summary-padding-block: var(--space-1);
--group-summary-chevron-gap: var(--space-1);
--year-control-padding-block-start: 0;
--month-control-padding-block-start: 0;
--date-control-padding-block-start: 0;
--entry-body-padding-block-start: var(--group-summary-padding-block);
--title-gap: var(--space-1);
--paragraph-gap: var(--space-2);
```

- `--feed-padding-block`：整个日记流顶部和底部留白。
- `--year-block-gap`：年份组之间的距离。
- `--month-block-gap`：同一年内月份组之间的距离。
- `--entry-block-gap`：同一月份内日记条目之间的距离。
- `--group-summary-padding-block`：年/月控件自身的上下 padding。它会影响年/月与日期的视觉对齐。
- `--group-summary-chevron-gap`：年/月折叠箭头与文字之间的距离。
- `--year-control-padding-block-start`：年份数字距离本行顶部的微调值。
- `--month-control-padding-block-start`：月份数字距离本行顶部的微调值。
- `--date-control-padding-block-start`：日期数字距离本行顶部的微调值。
- `--entry-body-padding-block-start`：正文/标题距离本行顶部的微调值，用于让正文首行与年、月、日对齐。
- `--title-gap`：标题与日期/正文之间的距离。
- `--paragraph-gap`：正文段落之间的距离。

如果目标是“年、月、日顶部严格对齐”，优先让 `--group-summary-padding-block`
接近 `0`，再用 `--year-control-padding-block-start`、
`--month-control-padding-block-start` 和 `--date-control-padding-block-start`
做细微补偿，并确认年、月、日字号和 line-height 接近。

## 字号与行高

这些 token 影响年、月、日的实际视觉高度：

```css
--font-size-year: 1.2rem;
--font-size-month: 1.2rem;
--font-size-date: 1.2rem;
--font-size-entry-time: 0.78rem;
--letter-spacing-date: 0.08em;
```

- 年、月、日可以独立控制字号，即使当前默认一致。
- 同日多篇日记时，时间显示为日期下方第二行，由 `--font-size-entry-time` 控制。
- `--letter-spacing-date` 会影响日期数字宽度和视觉密度。

## 布局调试边框

`tokens.css` 中保留了一个默认关闭的布局调试开关。需要检查年、月、日、正文
和右侧占位列的真实边界时，只需要修改一个参数：

```css
--debug-layout-enabled: 1;
```

关闭时恢复为：

```css
--debug-layout-enabled: 0;
```

边框宽度、透明度和右侧占位列的调试高度也在 `tokens.css` 中，但通常不需要改。
因为 CSS 不能直接在 `calc()` 中使用 `true` / `false`，所以这里使用 `0` / `1`
作为开关值。

颜色约定：

- 灰色：年份容器和年份文字。
- 蓝色：月份容器和月份文字。
- 绿色：分组内容、日记条目和日期列。
- 紫色：正文列。
- 橙色：右侧隐形占位列。

## 年/月折叠箭头

年份和月份前面的折叠箭头不是字体字符，而是使用静态图片
`frontend/assets/pull-arrow.png`。图片默认为展开状态的下拉箭头；折叠状态通过
旋转同一张图片实现。

需要微调图标时，优先修改 `base.css` 中 `.diary-group-summary` 的这一组局部变量：

```css
--chevron-image-url;
--chevron-box-size;
--chevron-icon-size;
--chevron-opacity;
--chevron-state-rotation;
```

如果希望替换箭头形状，通常只需要替换 `frontend/assets/pull-arrow.png`，并保持
文件名不变；如果想保留多套素材，则新增图片后修改 `--chevron-image-url`。

## 对应的 CSS 规则

如果 token 不够用，再看 `base.css` 中这些区域：

- `.diary-feed`：整体滚动内容的 grid 和页面 padding。
- `.diary-year`：年份盒子，负责“年 / 年月间距 / 月份区域”三列。
- `.diary-month`：月份盒子，负责“月 / 月日间距 / 条目区域”三列。
- `.diary-group-summary`：年/月文字与折叠符号。
- `.diary-group-content`：年/月右侧内容区域，与 summary 共享第一行以实现顶部对齐。
- `.diary-entry`：已有日记的“日 / 日正文间距 / 正文 / 右侧隐形占位”布局。
- `.entry-date`：日期和时间的竖向显示。
- `.new-entry`：新建日记的“现在 / 日正文间距 / 写作区 / 右侧隐形占位”布局、分隔线、写作区高度和底部留白。

建议先改 token，再改 `base.css`。若需要新增 token，应放入 `tokens.css` 并在本文补充说明。
