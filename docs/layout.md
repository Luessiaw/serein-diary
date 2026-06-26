# 布局说明

本文说明当前静态前端的 HTML 嵌套结构，以及手动调整视觉对齐时应优先修改的
CSS token。当前布局主要由 `frontend/scripts/app.js` 生成 DOM，由
`frontend/styles/base.css` 消费 `frontend/styles/tokens.css` 中的变量。

## HTML 嵌套结构

页面入口只有一个滚动容器：

```html
<button class="sidebar-menu-button">...</button>
<div class="sidebar-backdrop"></div>
<aside class="app-sidebar">
  <div class="app-sidebar-header">
    <nav class="app-sidebar-nav">
      <button class="app-sidebar-tab">日期</button>
      <button class="app-sidebar-tab">统计</button>
      <button class="app-sidebar-tab">设置</button>
    </nav>
    <button class="app-sidebar-close">关闭</button>
  </div>
  <div class="app-sidebar-panels">...</div>
</aside>

<main id="app" class="diary-scroll-region">
  <section class="diary-feed">
    <div class="load-control">...</div>

    <section class="diary-year" data-open="true">
      <button class="diary-group-summary" aria-expanded="true">2026</button>
      <div class="diary-group-content">
        <section class="diary-month" data-open="true">
          <button class="diary-group-summary" aria-expanded="true">06</button>
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
        </section>
      </div>
    </section>
  </section>
</main>
```

几点需要记住：

- 侧边栏相关节点直接挂在 `<body>` 下，是浮动界面层，不放入 `.diary-scroll-region`，
  因此不会参与日记流宽度、时间轴列宽或滚动加载计算。
- 侧边栏目前只有三个占位页面：日期、统计、设置。导航按钮使用内联 SVG 图标，不依赖
  外部图片素材；当前页面使用类似浏览器标签页的圆角上边框，与下方内容区顶线融合。
- 日期页已包含静态月历控件：年份控制和月份控制分成两行，年份和月份文字可点击打开
  浮动的可滚动选择卡片，点击卡片外部会关闭，且不能跳转到未来月份；使用 mock 日记
  日期区分深浅日期；有日记的日期可点击，当前只调用跳转占位函数。
- 年份、月份使用普通 `<section>`、`<button>` 和内容 `<div>` 组成；折叠状态由
  `data-open`、`aria-expanded` 和 `hidden` 控制。这样布局由普通 grid 元素承担，
  避免 `<details>` / `<summary>` 的特殊渲染模型影响列定位。
- 年/月折叠状态保存在前端内存 Map 中，重新渲染日记流时保留；刷新页面后恢复默认展开。
- 折叠年/月后，页面高度可能突然变短。静态阶段会在布局稳定后重新判断页面是否
  仍不足以形成可滚动内容；如果 `scrollHeight - clientHeight` 小于等于
  `--load-layout-fill-tolerance`，会继续模拟加载更早内容。这个折叠后的补拉判断
  与普通向上滚动的“接近顶部条目”判断分开，避免折叠状态下一路拉取过多内容。
  未来接入后端时，这一步应以服务端分页响应和结束信号为准。
- 当前布局是三层嵌套网格：年份盒子包住月份盒子，月份盒子包住日记条目盒子，
  日记条目盒子再包住日期和正文。年、月、日因此处在同一条真实布局链上，而
  不是靠 padding 临时偏移。
- 新建日记也放在当前年/月分组里；它没有持久化 `created_at`，但前端用打开页面时的临时时间归组。
- 窄屏下 `.diary-year`、`.diary-month`、`.diary-entry`、`.new-entry` 会退回普通块布局。
- 窄屏下年、月、日信息按行显示并靠右对齐；年/月按钮会占满行宽，并把“箭头 + label”小组推到右侧。
  桌面端为了列式排版，年/月控件内部默认左对齐。

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
这块右侧空间在 `base.css` 中由 `--timeline-right-width` 表示，默认等于
`--timeline-left-width`；调试模式下的橙色框就是这块占位列。
主体宽度在 `base.css` 中由 `--reading-width + --timeline-left-width +
--timeline-right-width` 自动计算。日记条目自身宽度使用“日期列、日期正文间距、
正文和右侧占位”的显式总和，避免 `inline-size: 100%` 在嵌套 grid 中留下额外
剩余空间。

## 横向对齐参数

优先修改 `tokens.css` 的“阅读布局”分组：

```css
--reading-width: 35rem;
--year-control-width: 4.5rem;
--month-control-width: 3rem;
--date-control-width: 3rem;
--year-month-inline-gap: var(--space-3);
--month-date-inline-gap: var(--space-3);
--date-content-gap: clamp(0.75rem, 2vw, 1.5rem);
--page-gutter: clamp(1rem, 4vw, 3rem);
```

- `--reading-width`：正文列宽度，只影响正文；主体总宽会由正文宽度和左右等宽占位自动计算。
- `--year-control-width`：年份左侧控件列宽度。
- `--month-control-width`：月份左侧控件列宽度。
- `--date-control-width`：日期/“现在”左侧控件列宽度。
- `--year-month-inline-gap`：年份列与月份列之间的横向距离。
- `--month-date-inline-gap`：月份列与日期列之间的横向距离。
- `--date-content-gap`：日期列与正文列之间的横向距离。
- `--page-gutter`：整个滚动区左右边距，主要防止窄屏贴边。

如果要让正文更宽或更窄，改 `--reading-width`。主体总宽会自动随正文宽度和
左侧列宽计算得到。如果要让年、月、日彼此靠近或远离，分别改
`--year-month-inline-gap` 和 `--month-date-inline-gap`。如果要让日期靠近或远离
正文，改 `--date-content-gap`；右侧占位会自动跟随左侧总宽变化。如果某一类
控件的数字太挤或太松，分别改对应的 `--*-control-width`。

年/月控件内部是“箭头 + label”的小网格，并且默认左对齐。因此：

- `--year-control-width` / `--month-control-width` 控制整个年/月控件列宽。
- `--group-summary-chevron-gap` 控制箭头与年/月数字之间的距离。
- `--year-month-inline-gap` / `--month-date-inline-gap` 控制控件列与下一层列之间的距离。

这条左对齐规则只用于桌面列式布局；窄屏下年/月按钮和日期会在 media query 中
恢复右对齐。

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
--sticky-group-label-top: 0;
--sticky-group-label-z-index: 8;
--sticky-group-label-background: var(--color-page);
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
- `--sticky-group-label-top`：桌面端年/月标签吸附到滚动容器顶部时的顶部偏移。
- `--sticky-group-label-z-index`：吸附标签的层级。
- `--sticky-group-label-background`：吸附标签背景色，用于避免滚动内容透出。
- `--sticky-year-label-top-compact`：窄屏下年份标签吸附到顶部时的偏移。
- `--sticky-year-label-height-compact`：窄屏下年份吸附区高度，用于决定月份标签的吸附触发线。
- `--sticky-month-label-top-compact`：窄屏下月份标签吸附到顶部时的偏移，默认等于年份顶部偏移加年份吸附区高度。
- `--title-gap`：标题与日期/正文之间的距离。
- `--paragraph-gap`：正文段落之间的距离。

如果目标是“年、月、日顶部严格对齐”，优先让 `--group-summary-padding-block`
接近 `0`，再用 `--year-control-padding-block-start`、
`--month-control-padding-block-start` 和 `--date-control-padding-block-start`
做细微补偿，并确认年、月、日字号和 line-height 接近。

桌面端年/月标签使用 `position: sticky` 吸附在滚动容器顶部；窄屏布局中也启用
sticky。月份标签的 sticky 触发线默认位于“页面顶端 + 年份吸附区高度”，避免
月份与年份重叠。

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

页面右下角有一个 `Debug` 按钮，用于即时开关布局调试边框。开启后，年、月、
日、正文和右侧占位列的真实边界会显示出来；状态会保存在当前浏览器的
`localStorage` 中，刷新页面后仍会保留。

也可以在 F12 Console 中运行：

```js
SereinDebugLayout.toggleDebugMode()
```

或明确设置：

```js
SereinDebugLayout.setDebugMode(true)
SereinDebugLayout.setDebugMode(false)
```

边框宽度、透明度和右侧占位列的调试高度仍在 `tokens.css` 中配置，通常不需要改。

颜色约定：

- 灰色：年份容器和年份文字。
- 蓝色：月份容器和月份文字。
- 绿色：分组内容、日记条目和日期列。
- 紫色：正文列。
- 橙色：右侧隐形占位列。

## 浏览器 Console 布局检查

除了肉眼查看边框，还可以在浏览器 F12 Console 中运行：

```js
SereinDebugLayout.inspect()
```

它会输出三张表：

- `boxes`：页面、主体、年、月、条目、日期、正文以及预测占位列的实际
  `left` / `right` / `width` / `center`。
- `columns`：当前日记条目 grid 四列的实际像素宽度，即日期列、日期正文间距、
  正文列、右侧占位列。
- `centers`：正文中心相对页面中心和年份主体中心的偏移。

如果要检查第 N 个条目，可以传入索引：

```js
SereinDebugLayout.inspect({ entryIndex: 2 })
```

如果要把结果复制给 AI 或保存，可以运行：

```js
copy(JSON.stringify(SereinDebugLayout.inspect(), null, 2))
```

排查横向居中问题时，优先看：

- `centers.bodyMinusViewportCenter`：正文中心相对页面中心的偏移。
- `centers.bodyMinusYearCenter`：正文中心相对年份主体中心的偏移。
- `columns.rightPlaceholder` 是否等于左侧时间轴总宽。
- `boxes.entry.width` 是否等于 `columns.entryColumnSum`。

## 年/月折叠箭头

年份和月份前面的折叠箭头不是字体字符，而是使用静态图片
`frontend/assets/pull-arrow.png`。图片默认为展开状态的下拉箭头；折叠状态通过
旋转同一张图片实现。折叠状态由 `.diary-year[data-open="false"]` 和
`.diary-month[data-open="false"]` 触发。

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
