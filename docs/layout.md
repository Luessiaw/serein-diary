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
- 年、月、日和正文都使用“三列布局”：左侧控件列、中央正文列、右侧对称占位列。
- 新建日记也放在当前年/月分组里；它没有持久化 `created_at`，但前端用打开页面时的临时时间归组。
- 窄屏下 `.diary-year`、`.diary-month`、`.diary-entry`、`.new-entry` 会退回普通块布局。

## 横向对齐参数

优先修改 `tokens.css` 的“阅读布局”分组：

```css
--reading-width: 46rem;
--year-control-width: 8rem;
--month-control-width: 4rem;
--date-control-width: 3.5rem;
--control-content-gap: clamp(0.75rem, 2vw, 1.5rem);
--page-gutter: clamp(1rem, 4vw, 3rem);
```

- `--reading-width`：正文列宽度，只影响正文，不包含年/月/日控件。
- `--year-control-width`：年份左侧控件列宽度。
- `--month-control-width`：月份左侧控件列宽度。
- `--date-control-width`：日期/“现在”左侧控件列宽度。
- `--control-content-gap`：左侧控件列与正文列之间的距离。
- `--page-gutter`：整个滚动区左右边距，主要防止窄屏贴边。

如果要让正文更宽，只改 `--reading-width`。如果要让年/月/日更靠近正文，改
`--control-content-gap`。如果某一类控件的数字太挤或太松，分别改对应的
`--*-control-width`。

## 纵向对齐参数

这些 token 影响年、月、条目之间的垂直节奏：

```css
--feed-padding-block: var(--space-6);
--year-gap: var(--feed-gap);
--year-month-gap: var(--space-3);
--month-date-gap: var(--space-3);
--group-summary-padding-block: var(--space-1);
--year-control-padding-block-start: 0;
--month-control-padding-block-start: 0;
--date-control-padding-block-start: 0;
--title-gap: var(--space-1);
--paragraph-gap: var(--space-2);
```

- `--feed-padding-block`：整个日记流顶部和底部留白。
- `--year-gap`：年份组之间的距离。
- `--year-month-gap`：同一年内月份组之间的距离，也影响多个月份之间的垂直间隔。
- `--month-date-gap`：同一月份内日记条目之间的距离，也影响多个日期之间的垂直间隔。
- `--group-summary-padding-block`：年/月控件自身的上下 padding。它会影响年/月与日期的视觉对齐。
- `--year-control-padding-block-start`：年份数字距离本行顶部的微调值。
- `--month-control-padding-block-start`：月份数字距离本行顶部的微调值。
- `--date-control-padding-block-start`：日期数字距离本行顶部的微调值。
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

## 对应的 CSS 规则

如果 token 不够用，再看 `base.css` 中这些区域：

- `.diary-feed`：整体滚动内容的 grid 和页面 padding。
- `.diary-year`：年份组的三列布局。
- `.diary-month`：月份组的三列布局。
- `.diary-group-summary`：年/月文字与折叠符号。
- `.diary-group-content`：年/月下方内容区域，目前与 summary 共享第一行以实现顶部对齐。
- `.diary-entry`：已有日记的三列布局。
- `.entry-date`：日期和时间的竖向显示。
- `.new-entry`：新建日记的三列布局、分隔线、写作区高度和底部留白。

建议先改 token，再改 `base.css`。若需要新增 token，应放入 `tokens.css` 并在本文补充说明。
