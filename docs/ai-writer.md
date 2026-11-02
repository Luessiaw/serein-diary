# AI 写入接口

本文件说明「由对话整理生成的日记」如何进入 Serein：接口边界、token 机制、
以及它**看不到也改不动**什么。

设计决策的来龙去脉见父仓库的
`docs/11_mental-health-ai-diary-assessment.md`。

## 边界

`/api/v1/ai/*` 是唯一面向 AI 的入口，只有两个端点：

| 方法 | 路径 | 认证 | 作用 |
|---|---|---|---|
| `GET` | `/api/v1/ai/health` | 不需要 | 报告 `write_enabled`，让定时任务区分"功能关了"和"token 错了" |
| `POST` | `/api/v1/ai/entries` | Bearer token | 创建一条 `source_kind: "ai-dialogue"` 的条目 |

**没有** list / get / patch / delete。AI 拿不到任何既有条目内容，也改不掉历史，
包括它自己先前写的条目。

`POST` 的响应只有 `id`、`created_at`、`source_kind`，不回显正文——否则这个写接口
就变相成了读接口。

## 认证是第二种主体

Serein 原有 `single-admin` 一种身份，浏览器用签名 cookie。AI 用的是**独立 salt**
签名的 bearer token：

```python
AI_WRITER_SUBJECT = "ai-writer"
AI_WRITER_TOKEN_SALT = "serein-ai-writer"   # 与 cookie 的 salt 不同
```

两点必须成立，测试 `tests/test_ai_api.py` 覆盖了它们：

1. `read_session_token()`（cookie 路径）**显式拒绝** `ai-writer`。否则把 AI token
   塞进 `serein_session` cookie 就能拿到管理权限。
2. 因为 salt 不同，AI token 即使被塞进 cookie 也验签失败，反之亦然。

## 服务器只保存摘要

`.env` 里存的是 `DIARY_AI_TOKEN_SHA256`，不是明文 token。原因：明文一旦进了环境
变量，就会出现在 `docker inspect`、`systemctl show` 和崩溃转储里。

签发（在宿主机的 `backend/` 目录）：

```bash
cd ~/storage/srv/projects/serein-diary/backend
DIARY_DATA_DIR=/path/to/existing/dir \
DIARY_ADMIN_PASSWORD=... DIARY_SESSION_SECRET=... \
  python -m serein.issue_ai_token
```

输出一段 token 和一个 `DIARY_AI_TOKEN_SHA256=...`：

- **token** → 写进 AI 侧的文件（例如 `~/.config/serein/ai-token`，`chmod 600`）
- **摘要** → 写进服务器 `.env`

签发不经过 HTTP：没有任何接口能拿密码换写权限，只有能登宿主机的人才能发 token。

核对某个 token 是否与当前配置匹配：

```bash
python -m serein.issue_ai_token --verify < token文件
```

## 启用

`.env`：

```env
DIARY_AI_WRITER_ENABLED=true
DIARY_AI_TOKEN_SHA256=<64 位十六进制>
```

`DIARY_AI_WRITER_ENABLED=true` 而摘要缺失或格式不对时，服务**拒绝启动**
（`ConfigError`），不会以半开状态运行。

## 提交一篇

```bash
cd ~/storage/srv/projects/serein-diary

# 先看会提交什么，不发送
echo "今天把边界条件改完了……" | bash scripts/post-ai-entry.sh --title "十月二十八日" --dry-run

# 真正提交
echo "今天把边界条件改完了……" | bash scripts/post-ai-entry.sh \
  --title "十月二十八日" \
  --material "2026-10-28T09:00:00+08:00/2026-10-28T23:30:00+08:00"
```

脚本从 stdin 或 `--file` 读正文，token 从文件读（不经命令行，避免进入 shell
history 和进程列表）。

## 取素材：从会话日志整理当天对话

AI 写入的前一步是知道「今天聊了什么」。DSH 的定时提醒绑定在单个 Session
上，醒来时看不到别的窗口，所以素材必须从会话日志里取：

```text
$HOME/sessions/<工作区转义名>/session-<uuid>/session.v4.jsonl.zstd
```

用现成工具提取：

```bash
cd ~/storage/srv/projects/serein-diary/backend
.venv/bin/python -m serein.services.session_digest \
  --date 2026-10-28 \
  --workspace "/home/luessiaw/storage/data/01_生活/00_我的记录/05_心理健康" \
  --sessions-root /var/lib/dsh/home/sessions
```

输出是一份带时间戳的 Markdown 素材，交给 agent 筛选后再用
`scripts/post-ai-entry.sh` 提交。退出码 `3` 表示当天没有用户发言，此时**不应
生成日记**。

三个容易出错的地方：

1. **只取 `data.source.kind == "user"` 的事件。** 同一 `user/message` 类型下还有
   `agent-instructions` 和 `runtime-context`，它们是系统注入的规则与上下文。
   不排除的话，`AGENTS.md` 的规则会被当成「用户说过的话」写进日记。
2. **按本地日期过滤。** 事件 `time` 是毫秒时间戳，必须按 `DIARY_TIMEZONE`
   换算后再比较，否则跨零点的对话会落到错误的一天。
3. **素材是原话，比日记敏感。** `--out` 写出的文件权限会是 `600`，并且提醒
   用完即删；不要把它放进日记数据目录或会被同步的位置。

## 落盘结果

```json
{
  "schema_version": 1,
  "id": "…",
  "created_at": "2026-11-02T17:17:51+08:00",
  "title": "时区测试",
  "source_kind": "ai-dialogue",
  "source_review": "unreviewed",
  "source_material": "2026-10-28T09:00:00+08:00/2026-10-28T23:30:00+08:00"
}
```

- `source_material` **只存时间范围**，不存对话原文：素材留在会话日志里。
  契约见 `docs/data-contract-v1.md` §来源字段。
- `created_at` 用 `DIARY_TIMEZONE`（compose 默认 `Asia/Shanghai`）。
- 写入是**纯新增**：`create_entry` 在 `entries/` 下建新目录，从不读写既有条目。

## 与手写日记的区分

前端只认 `source_kind === "ai-dialogue"`：

- 卡片换极淡底色 `--color-entry-ai-surface`
- 右上角白字 "AI" 角标 + 半透明衬底（`--color-entry-ai-badge-scrim`）
- 正文排版、字号、行高与手写条目完全一致

改这两个颜色前先看 `frontend/tests/entry-origin.test.js`：它会计算 WCAG 对比度，
角标低于 4.5:1 或正文低于 4.5:1 会直接失败。

## 已知边界

- **接口隔离不等于物理隔离。** 它挡住的是"AI 通过 HTTP 读日记"。如果某个任务被
  明确授权读取数据目录，这层隔离就不起作用了。默认部署下 `04_日记` 不在 DSH 的
  可见范围内，前提是任务提示词里不出现该路径。
- **AI 不能修改自己写的条目。** 写错了只能由用户在前端删除。若将来需要自我修订，
  应当新增一条带 `source_kind` 的修订记录，而不是开放 `PATCH`。
