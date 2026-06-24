# 主题定制

Serein 的视觉参数集中在
[`frontend/styles/tokens.css`](../frontend/styles/tokens.css)。它使用原生 CSS
自定义属性，因此主题既不需要 Node.js，也不需要构建步骤，更不会把应用设置
写入日记数据。

## 从 token 开始

每次只调整一个分组，并在桌面与窄屏手机浏览器中刷新页面检查效果：

- **字体排版：** `--font-reading`、`--font-size-reading` 和
  `--line-height-reading` 控制正文；`--font-ui` 与 `--font-size-date` 控制
  安静的界面标签。
- **布局：** `--reading-width` 改变行长；`--page-gutter`、`--feed-gap` 与
  `--paragraph-gap` 调整留白。
- **颜色：** 应一起修改具有语义的 `--color-*` 变量。只要已有对应 token，
  组件就不应直接使用原始颜色值。

默认字体栈只使用本地/系统字体，不依赖网络服务。若未来发行版需要加入 Web
字体，应说明它的许可证、托管位置和隐私影响。

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
}
```

请不要把主题设置放入 `metadata.json`、`content.md` 或其他日记数据文件。主题
只影响呈现，必须能够在不迁移条目的前提下替换。

## 保持主题轻量

在出现明确产品需求前，不要加入设置界面、JSON 主题解析器或单篇日记的外观
控制。CSS 覆盖已经能以更少的代码提供首发版本所需的定制能力，同时不会增加
API 表面或与数据契约耦合。
