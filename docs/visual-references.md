# Serein 视觉与交互参考调研

本文件记录一次纯视觉/交互层面的外部调研，用于回答“界面如何同时更优雅、更简洁”。
不涉及技术路线：所有建议都能落在 `frontend/styles/tokens.css` 与现有 CSS 上。

- 参考册（可在浏览器打开）：[`reference-gallery.html`](reference-gallery.html)
- 截图与原始大图：[`reference-shots/`](reference-shots/)
- 截取日期：2026-10-28（外部产品会改版，观感以截图为准）

## 0. 结论先行

Serein 的骨架是对的：连续长文、单列纸带、折叠年/月、极简锁屏、“此刻”新建。
不够优雅和简洁的地方几乎都集中在**围绕正文的外围**，按收益排序：

1. **工作区底色太重。** `--color-workspace: #3f4141` 让两侧深灰成为画面主体，
   白纸带反而像“被夹住的一条”。Craft、iA Writer、Simplenote 都是浅底 + 白纸。
2. **时间信息占了四层。** 年、月、日三列常驻，加上条目时间，视觉重量超过正文。
   参考对象普遍把时间压成页边小刻度或每月一条分隔线。
3. **中文字体实际回退到黑体。** `--font-reading` 首位是 Times New Roman，
   中文回退到 STFangsong/KaiTi（多数环境没有）再到系统黑体；“优雅”的第一来源因此丢失。
4. **行高与字号的比例偏空。** 20px 字配 48px 行高（2.4 倍），汉字之间像被拉开；
   参考对象普遍在 1.6–1.9 倍。
5. **状态符号喧闹。** 新建条目右侧 ○ × ✓ 带红绿两色，是全页唯一的高饱和色。
6. **菜单面板空。** 36rem × 34rem 的面板里只有一张小日历，留白没有承担任何功能。

## 1. 调研范围与方法

| 类别 | 调研对象 | 图 |
|---|---|---|
| 日记 App | Day One、Journey、Diarium、Moleskine Journal、DailyBean、Diaro、Minimal · Notes | `reference-shots/01-diary-apps/` |
| 笔记 / 书写工具 | iA Writer、Obsidian、Craft、Heptabase、Logseq、Reflect、Simplenote、Standard Notes、Ulysses、Capacities、Dillinger | `reference-shots/02-note-web-tools/` |
| 排版 / 界面细节 | Apple Newsroom、iA、以及本机实测的字体/字号/留白/状态样张 | `reference-shots/03-typography-ui/` |
| Serein 现实验证 | 把上述做法以 CSS 注入真实 Serein（mock 数据）后截图 | `reference-shots/04-serein-experiments/` |

素材来源与可信度：

- **App Store 官方商店页**（iOS/iPad/macOS 版本截图）：真实产品界面，最可信。
- **厂商官网**：多为营销图，偏“海报”，参考价值在配色与排版气质，不在交互。
- **实测样张**：本轮新做，渲染环境只安装了 Droid Sans Fallback 一种中文字体，
  因此“F1 字体配对”中除 Noto/LXGW 两组外，中文形态一致、只有拉丁部分有差异；
  该局限已写入样张说明。
- **Serein 实验**：在现有前端注入 CSS 截图，**不是已实现的代码**。

未能取得的部分：GitHub README 截图（`raw.githubusercontent.com` 在本机网络下不可达），
以及部分返回 Cloudflare 403 的站点（AppFlowy 等）未纳入。

## 2. 逐项借鉴点

参考册里每个条目都标了“看点 / 对 Serein 的启发 / 迁移度”，这里只汇总最值得的三类。

### 2.1 纸面与层次（决定“第一眼优雅”）

- **Craft**：纯白文档区浮在浅暖灰底上，大圆角 + 极淡阴影；界面本身几乎无色，颜色交给
  用户内容。→ 与 Serein 的“白纸带”同构，只需把底色提亮。
- **Heptabase**：分区用 `#e5e7eb` 级浅灰，卡片只有 1px 边框、没有阴影。→ 更省事、
  在中文正文周围更干净。
- **Obsidian（夜间）**：同色不同明度分区，强调色只出现一次。→ 给未来暗色主题一个直接模板。
- **Apple Newsroom**：12 / 17 / 34 / 60px 的分级 + 每级独立字距 + 只用灰阶与一个强调色。
  中文不适合负字距，但“字号层级 + 灰阶层级”可以完整照搬。

### 2.2 时间如何在场（决定“简洁”）

- **Day One 的日历热力**：每天一张缩略图拼成月历，密度本身承担导航。
- **Notion Calendar**：网格线极淡、今天只用一个实心小标记，不用底色填充。
- **Reflect**：整页只有日期一个标题；左侧当前页用一抹紫色细条标记。
- **Diarium / Diaro**：时间竖排在左侧、正文在右，无需卡片边框。

→ 对应实测样张 `03-typography-ui/time-axis-specimen.png` 的三种方案：
无刻度纸页 / 细刻度+月份分隔 / 时间缩进页边。

### 2.3 状态与微交互（决定“流畅但不喧闹”）

- **iA Writer 聚焦模式**：当前句全黑、其余降到约 20% 灰；打字机模式光标固定在中线。
  → Serein 有天然的“新建 / 已封存”二态，正好对应“聚焦 / 退后”。
- **Bear**：选中文字后浮现的格式气泡，不占常驻工具栏。
- **Notion 系**：条目操作只在悬停/聚焦时出现。
- 保存反馈：点阵指示、2px 顶部进度条——不占位，也不打断阅读。

对应样张 `03-typography-ui/states-specimen.png`。

## 3. 对 Serein 的具体建议（按成本排序）

### 第 0 档：只改 token，不碰结构

```css
/* frontend/styles/tokens.css */
--color-workspace: #f4f2ec;   /* 原 #3f4141：深灰吸走注意力 */
--color-page: #fdfcfa;        /* 原 #fcfcfa：纸带略亮，与底色拉开一档 */
--color-muted: #6B7169;       /* 在纸带与工作区上都 ≥4.2:1 */
--font-reading: Georgia, "Noto Serif SC", "Songti SC", STSong, serif;
--line-height-reading: 2.1rem;  /* 原 3rem */
--font-size-reading: 1.15rem;   /* 原 1.25rem */
--font-size-entry-time: 0.7rem;
```

效果见 `04-serein-experiments/exp-a-paper-page.png` 与 `exp-lean-direction.png`。

注意：桌面端深色工作区来自 `base.css` 的 `color-mix` 渐变和分组摘要背景，
单改 token 即可全部跟随，无需改结构。

### 第 1 档：时间轴降噪

- 年标签：字号降到 0.8rem、`letter-spacing: .4em`、颜色 `#b8b3a6`。
- 月标签：改为每月一条 1px 横线 + 12px 小字（`exp-e-month-rule.png`）。
- 日：保留在纸带内，字号降一档并用 `font-variant-numeric: tabular-nums` 对齐。
- 可选：同一天有多条时，条目之间加 `1px #eeeae0` 细分隔线，跨天不加
  （`exp-d-entry-rules.png`）。

### 第 2 档：中文字体（改变最大，也最有争议）

| 方案 | 样张 | 代价 |
|---|---|---|
| Noto Serif SC（思源宋体）正文 | `exp-f-serif-webfont.png` | 中文 webfont 首屏约 1–3MB（Google Fonts 按 unicode-range 切片，可只加载用到的字集）；需接受网络依赖或自托管 |
| LXGW WenKai（霞鹜文楷） | `exp-g-kai-webfont.png` | 最有手写温度，但小字号笔画细、读数慢；适合标题/引文 |
| Noto Sans SC（思源黑体） | `exp-h-sans-webfont.png` | 最中性耐读，但失去文学感 |
| 宋体标题 + 黑体正文 | `exp-i-dynamic-type.png` | 层级最清楚，适合想提高密度时 |

保持现有“只用本地字体”原则也可以，但建议把首位换成 Georgia（拉丁字形明显优于
Times New Roman），并在字体栈里显式写出中文衬线候选（`Songti SC`、`STSong`、
`Noto Serif CJK SC`）。

### 第 3 档：交互

- 新建条目时，让其余条目降到 55% 灰（iA 聚焦）；保存后恢复（`exp-*` 系列之外，见 2.3）。
- 把 ○ × ✓ 换成灰度文字按钮（保存 / 取消），删除放进悬停菜单或二次确认。
- 选中正文文字后浮现格式气泡，替代常驻工具栏。
- 日历：日期格缩小，有日记的日期仅加 3px 圆点；今天用描边圈而非底色
  （`exp-lean-calendar.png`）。

## 4. 与 Serein 三条原则的对应

| 原则 | 本轮调研中与之冲突的做法（不建议采用） | 与之契合、建议采用的做法 |
|---|---|---|
| 简约 | 卡片化（Day One、Craft 的卡片入口）、双列瀑布、分屏编辑（Dillinger） | 空白即入口、浅底白纸、页边时间、悬停操作、聚焦模式 |
| 流畅 | 一次性展开全部历史、常驻加载骨架 | 顶部细进度条、点阵保存指示、滚动边缘渐隐（Minimal） |
| 模块化 | 把主题写进组件 CSS | 继续只动 token；暗色主题可直接平移 Obsidian 的同色不同明度关系 |

## 5. 复现方式

- 参考册是纯静态页面，图片以相对路径引用 `reference-shots/`；直接双击打开或在
  `docs/` 下起任意静态服务器都能看。
- 实验截图是在真实 Serein 上注入一段临时 CSS 得到的，参数写在参考册每个条目的说明里；
  CSS 未提交到仓库，避免把探索性样式混进 `tokens.css`。
