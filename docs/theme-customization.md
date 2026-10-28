# 主题定制

Serein 的视觉参数集中在
[`frontend/styles/tokens.css`](../frontend/styles/tokens.css)。它使用原生 CSS
自定义属性，因此主题既不需要 Node.js，也不需要构建步骤，更不会把应用设置
写入日记数据。

## 从 token 开始

每次只调整一个分组，并在桌面与窄屏手机浏览器中刷新页面检查效果：

- **字体排版：** `--font-title`、`--font-size-title` 与 `--font-weight-title` 控制
  可选标题（默认楷体）；`--font-reading`、`--font-size-reading` 和
  `--line-height-reading` 控制正文（默认衬线）；`--font-date`、
  `--font-size-date` 与 `--font-size-entry-time` 控制日期和同日多篇时的时间标签。
- **布局：** `--reading-width` 只改变正文行长；`--year-control-width`、
  `--month-control-width` 和 `--date-control-width` 分别调整年、月、日左侧控件
  宽度；`--year-month-inline-gap`、`--month-date-inline-gap`、`--date-content-gap`、
  `--page-gutter`、`--feed-gap` 与
  `--paragraph-gap` 调整留白。
- **日历分组：** `--font-year`、`--font-size-year`、`--letter-spacing-year`、
  `--font-month`、`--font-size-month` 与 `--letter-spacing-month` 控制可折叠的
  年份、月份刻度（默认很小，月份另有一条分隔线）；`--color-year`、
  `--color-month` 和 `--color-date` 控制其层级色彩；`--year-gap`、
  `--year-month-block-gap` 和 `--month-date-block-gap` 调整它们与正文的距离。
- **颜色：** 应一起修改具有语义的 `--color-*` 变量。只要已有对应 token，
  组件就不应直接使用原始颜色值。

## 字体与 webfont

标题默认楷体、正文默认衬线。两组字体栈都遵循同一个顺序：先本地系统字体，
最后才落到 [`frontend/styles/fonts.css`](../frontend/styles/fonts.css) 提供的
webfont 兜底。

- **许可证：** Noto Serif SC 与 LXGW WenKai TC 均为 SIL Open Font License 1.1，
  可自由使用与再分发。
- **托管位置：** `fonts.css` 通过 Google Fonts 的 CSS 引入 `fonts.gstatic.com`
  上的字体切片。应用不向第三方发送日记内容，只暴露“本页使用了某字体”这一事实。
- **隐私与离线：** 若希望完全离线或屏蔽第三方请求，删除 `fonts.css` 的全部内容
  （或在 `index.html` 去掉它的 `<link>`）即可；此时自动退回系统楷体/衬线，
  版式、间距和断行宽度都不变。切换后建议在桌面与窄屏各刷新一次确认。

`--font-title` 与 `--font-reading` 的值是覆盖点：把自定义主题里的字体放在本地
字体之前，即可替换默认观感，而不必改动 `fonts.css`。

## 分享自定义主题

如需分发主题，可新建单独的 CSS 文件，只覆盖需要改变的变量；然后在
`frontend/index.html` 中将它置于 `tokens.css` 之后、`base.css` 之前加载。

```css
/* themes/warm-paper.css：暖色纸张主题 */
:root {
  --color-page: #fffaf0;
  --color-ink: #352f2a;
  --color-muted: #75695d;
  --font-reading: "Noto Serif SC", Georgia, serif;
  --reading-width: 44rem;
  --date-control-width: 4rem;
  --date-content-gap: 1rem;
}
```

请不要把主题设置放入 `metadata.json`、`content.md` 或其他日记数据文件。主题
只影响呈现，必须能够在不迁移条目的前提下替换。

## 保持主题轻量

在出现明确产品需求前，不要加入设置界面、JSON 主题解析器或单篇日记的外观
控制。CSS 覆盖已经能以更少的代码提供首发版本所需的定制能力，同时不会增加
API 表面或与数据契约耦合。
