#!/usr/bin/env bash
# 手动提交一篇「由对话整理」的日记，用于在真实数据上评估生成质量。
#
# 用法（在宿主机，普通用户即可）：
#   cd ~/storage/srv/projects/serein-diary
#   bash scripts/post-ai-entry.sh --title "十月二十八日" --file /tmp/day.md \
#       --material "2026-10-28T09:00:00+08:00/2026-10-28T23:30:00+08:00"
#
#   echo "今天……" | bash scripts/post-ai-entry.sh --title "今天"
#
# token 从文件读取，不接受命令行参数：参数会进入 shell history 和进程列表。
# 默认读取 ~/.config/serein/ai-token，可用 --token-file 指定别处。
#
# 这个脚本只做一次写入。它不会读回任何日记，也不会改动既有条目。
set -uo pipefail

API_BASE="${SEREIN_API_BASE:-http://127.0.0.1:8088}"

# token 查找顺序：显式覆盖 → $HOME 下的位置 → 运维侧的绝对路径。
#
# 为什么不只认 $HOME：这个脚本会被两个身份调用。运维自己跑时 HOME 是
# /home/luessiaw；DSH 会话以服务身份运行，HOME 是 /var/lib/dsh/home，而且
# 通常看不到 /home/luessiaw。依次尝试可以让两种身份都直接工作，而不是让
# 调用者自己去猜该传哪个 --token-file。
default_token_file() {
  local candidate
  for candidate in "$HOME/.config/serein/ai-token" "/home/luessiaw/.config/serein/ai-token"; do
    if [[ -r "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  # 都不可读时，返回第一个候选，让后面的报错信息指向最常见的那个位置。
  printf '%s' "$HOME/.config/serein/ai-token"
}
TOKEN_FILE="${SEREIN_AI_TOKEN_FILE:-$(default_token_file)}"
TITLE=""
MATERIAL=""
REVIEW="unreviewed"
SESSION_IDS=""
CONTENT_FILE=""
DRY_RUN=0

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  cat <<'EOF'

  --title <text>        条目标题（可选，最长 120 字）
  --file <path>         从文件读正文；省略则从 stdin 读
  --material <range>    素材时间范围，例如 2026-10-28T09:00/2026-10-28T23:30
  --session-id <id>     来源会话 ID，可重复
  --review <state>      unreviewed（默认）/ confirmed / rejected
  --token-file <path>   存放 AI token 的文件
  --base <url>          API 地址（默认 http://127.0.0.1:8088）
  --dry-run             只打印将要提交的内容，不发送
  -h, --help            显示本帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="${2:?--title 需要参数}"; shift 2 ;;
    --file) CONTENT_FILE="${2:?--file 需要参数}"; shift 2 ;;
    --material) MATERIAL="${2:?--material 需要参数}"; shift 2 ;;
    --session-id) SESSION_IDS="${SESSION_IDS}${SESSION_IDS:+,}\"${2:?}\""; shift 2 ;;
    --review) REVIEW="${2:?--review 需要参数}"; shift 2 ;;
    --token-file) TOKEN_FILE="${2:?--token-file 需要参数}"; shift 2 ;;
    --base) API_BASE="${2:?--base 需要参数}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $1（用 --help 查看用法）" >&2; exit 2 ;;
  esac
done

stage() { printf '\n==> %s\n' "$1"; }
die()   { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1; }
need curl || die "找不到 curl"
need python3 || die "找不到 python3（用于安全地拼装 JSON）"

# ---------------------------------------------------------------- 读正文
stage "读取正文"
if [[ -n "$CONTENT_FILE" ]]; then
  [[ -r "$CONTENT_FILE" ]] || die "读不到正文文件: $CONTENT_FILE"
  CONTENT=$(cat "$CONTENT_FILE")
  printf '  来源: %s\n' "$CONTENT_FILE"
else
  CONTENT=$(cat)
  printf '  来源: stdin\n'
fi

if [[ -z "${CONTENT//[[:space:]]/}" ]]; then
  die "正文为空。空日记比勉强生成的日记更有害，这里拒绝提交。"
fi
printf '  字数: %s\n' "$(printf '%s' "$CONTENT" | wc -m | tr -d ' ')"

# 服务端要求 LF；Windows 上编辑过的文件常带 CRLF。
if printf '%s' "$CONTENT" | grep -q $'\r'; then
  CONTENT=$(printf '%s' "$CONTENT" | tr -d '\r')
  printf '  已移除 CRLF 换行\n'
fi

# ---------------------------------------------------------------- 拼 JSON
stage "拼装请求"
PAYLOAD=$(CONTENT="$CONTENT" TITLE="$TITLE" MATERIAL="$MATERIAL" \
  REVIEW="$REVIEW" SESSION_IDS="$SESSION_IDS" python3 - <<'PY'
import json, os
body = {
    "content": os.environ["CONTENT"],
    "title": os.environ["TITLE"] or None,
    "source_material": os.environ["MATERIAL"] or None,
    "source_review": os.environ["REVIEW"] or "unreviewed",
}
ids = os.environ["SESSION_IDS"].strip()
if ids:
    body["source_session_ids"] = json.loads("[" + ids + "]")
print(json.dumps({k: v for k, v in body.items() if v is not None}, ensure_ascii=False))
PY
) || die "拼装 JSON 失败"

if [[ $DRY_RUN -eq 1 ]]; then
  printf '  %s\n' "$PAYLOAD"
  stage "dry-run：未发送"
  exit 0
fi

# ---------------------------------------------------------------- 读 token
stage "读取 AI token"
if [[ ! -r "$TOKEN_FILE" ]]; then
  die "读不到 token 文件: $TOKEN_FILE
  已尝试：\$HOME/.config/serein/ai-token 与 /home/luessiaw/.config/serein/ai-token
  推荐用一键脚本生成并同步到两处：
    python3 /home/luessiaw/storage/srv/scripts/serein_ai_writer/enable.py
  或用 --token-file 显式指定。"
fi
TOKEN=$(tr -d '[:space:]' < "$TOKEN_FILE")
[[ -n "$TOKEN" ]] || die "token 文件是空的: $TOKEN_FILE"
printf '  %s（%s 字符）\n' "$TOKEN_FILE" "${#TOKEN}"

# ---------------------------------------------------------------- 预检
stage "预检：接口是否可写"
health=$(curl -s -m 10 "$API_BASE/api/v1/ai/health")
if ! printf '%s' "$health" | grep -q '"write_enabled": *true'; then
  printf '  响应: %s\n' "${health:-<空>}"
  die "AI 写入未启用。检查 .env 里的 DIARY_AI_WRITER_ENABLED 与 DIARY_AI_TOKEN_SHA256。"
fi
printf '  write_enabled=true\n'

# ---------------------------------------------------------------- 提交
stage "提交"
# token 通过 600 权限的临时文件交给 curl：写成命令行参数会让它出现在
# 进程列表（ps）里，写成 curl 的 -H @- 又不受支持。
header_file=$(mktemp "${TMPDIR:-/tmp}/serein-ai-header.XXXXXX") || die "无法创建临时文件"
chmod 600 "$header_file"
trap 'rm -f "$header_file"' EXIT
printf 'Authorization: Bearer %s\n' "$TOKEN" > "$header_file"

response=$(curl -sS -m 30 -X POST "$API_BASE/api/v1/ai/entries" \
  -H @"$header_file" \
  -H 'Content-Type: application/json' \
  --data-binary "$PAYLOAD" \
  -w '\n%{http_code}')

status_code=$(printf '%s' "$response" | tail -n1)
body=$(printf '%s' "$response" | sed '$d')

case "$status_code" in
  201)
    printf '  已创建: %s\n' "$body"
    stage "完成"
    printf '  在日记页面刷新即可看到（带 AI 角标的卡片）。\n'
    printf '  不满意可以直接在前端删除，或把 source_review 改成 rejected。\n'
    exit 0
    ;;
  401)
    printf '  响应: %s\n' "$body"
    die "认证失败：token 与服务器上的 DIARY_AI_TOKEN_SHA256 不匹配。"
    ;;
  400|422)
    printf '  响应: %s\n' "$body"
    die "请求被拒（内容不合服务端契约）。"
    ;;
  *)
    printf '  响应: %s\n' "$body"
    die "提交失败，HTTP $status_code"
    ;;
esac
