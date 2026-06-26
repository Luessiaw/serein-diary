# Tiptap 静态实验

P2-T07 使用一个可切换的前端 demo 验证 Tiptap 是否适合 Serein 的“打开即写”
体验。它只影响新建日记区，不接入后端、认证、真实保存或已保存条目的编辑能力。

## 使用方式

页面右下角新增编辑器切换按钮：

- `Textarea`：默认稳定模式，使用原生 `<textarea>`。
- `Tiptap demo`：实验模式，使用 Tiptap 渲染新建正文区域。

切换状态会保存到当前浏览器的 `localStorage`，刷新后保留。切换时页面会重新渲染并
定位到新建日记区。

`Tiptap demo` 模式下会显示一排临时工具栏，用于测试段落、二/三级标题、粗体、斜体、
删除线、行内代码、列表、引用、代码块、撤销和重做。工具栏按钮暂不进入 Tab 顺序，
以免从标题输入框跳转到正文前被按钮打断；正式键盘可达性需要另行设计。

## 依赖与回退

当前实验为了避免引入 Node/Vite 构建，使用浏览器动态 `import()` 从 `esm.sh`
加载 Tiptap：

- `@tiptap/core`
- `@tiptap/starter-kit`
- `@tiptap/extension-placeholder`

因此第一次启用 `Tiptap demo` 需要浏览器能够访问外网 CDN。加载失败时，新建正文
区域会回退为浏览器原生 `contenteditable`，页面会显示“加载失败”的提示；这不会影响
原有 `Textarea` 模式。

## Console 检查

在浏览器 F12 Console 中可以运行：

```js
SereinEditorExperiment.getMode()
```

查看当前模式。

```js
SereinEditorExperiment.setTiptapEnabled(true)
SereinEditorExperiment.setTiptapEnabled(false)
```

切换实验模式。

```js
SereinEditorExperiment.dumpMarkdown()
```

导出当前新建正文区的 Markdown。这个导出器只覆盖当前实验所需的常见结构：段落、
二/三级标题、粗体、斜体、删除线、行内代码、链接、引用、列表、代码块和分割线。
正式接入前仍需确定最终 Markdown 适配策略。

## 当前不覆盖

- 图片导入、粘贴上传和媒体引用。正式功能需要 `media:<uuid>`、上传接口、预览生成和
  `media-manifest.json` 协同设计。
- 字体、字号、颜色等强表现样式。这类内容若直接进入正文，会削弱 `content.md` 的
  可迁移性；若需要支持，建议先映射为受控 Markdown/自定义字段，而不是保存任意
  HTML/CSS。
- 保存后的 Markdown 渲染。当前静态阅读区仍主要按段落展示文本，尚未接入完整
  Markdown renderer。

## 验收重点

- 长文输入是否随内容自然增高，而不是在编辑器内部滚动。
- 聚焦时是否仍保持无边框、沉浸式视觉。
- 桌面和手机上的输入法、选区、换行、撤销/重做是否舒服。
- `dumpMarkdown()` 输出是否接近 `content.md` 需要的语义 Markdown。
- 保存后生成的静态阅读条目是否仍保持已保存正文不可编辑。
