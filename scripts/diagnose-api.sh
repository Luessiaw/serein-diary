#!/usr/bin/env bash
# 只读诊断：Serein API 容器起不来时，按从外到内的顺序收集事实。
#
# 用法（在宿主机，普通用户即可，不需要 sudo）：
#   cd ~/storage/srv/projects/serein-diary
#   bash scripts/diagnose-api.sh                          # 默认检查 127.0.0.1:8088
#   bash scripts/diagnose-api.sh --base https://diary.tail31ef0b.ts.net
#
# 这个脚本只读：不启动、不停止、不重建任何容器，不修改任何文件。
# 所有 `docker compose run` 都不会触发构建：优先带 --no-build，旧版 compose
# 不支持该参数时退回裸 run（此时镜像已确认存在，compose 不会重新构建）。
# 它不打印 .env 的值，也不打印配置里的密钥，只看键名、长度与路径。
set -uo pipefail

STAGE_URL="http://127.0.0.1:8088"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base) STAGE_URL="${2:?--base 需要一个 URL}"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

cd "$(dirname "$0")/.." || exit 1
REPO=$PWD

failures=0
warns=0
IMAGE_READY=1

stage() { printf '\n==> %s\n' "$1"; }
pass()  { printf '  PASS: %s\n' "$1"; }
warn()  { printf '  WARN: %s\n' "$1"; warns=$((warns + 1)); }
fail()  { printf '  FAIL: %s\n' "$1" >&2; failures=$((failures + 1)); }
info()  { printf '  INFO: %s\n' "$1"; }

need() { command -v "$1" >/dev/null 2>&1; }

# 在 api 镜像里跑一条只读命令。镜像不存在时直接失败，绝不触发构建。
#
# `run --no-build` 只有较新的 compose 才支持；旧版本会直接报
# `unknown flag: --no-build`，若把它当成探针结果就会得出完全相反的结论。
# 因此先探测一次支持情况，不支持时退回不带该 flag 的写法（镜像已确认存在，
# 所以 compose 不会因此重新构建）。
COMPOSE_RUN_FLAGS=()
detect_compose_run_flags() {
  local out
  out=$(docker compose run --help 2>&1 || true)
  if printf '%s' "$out" | grep -q -- '--no-build'; then
    COMPOSE_RUN_FLAGS=(--no-build)
  fi
}

in_api() {
  docker compose run --rm --no-deps "${COMPOSE_RUN_FLAGS[@]}" --entrypoint "$1" api "${@:2}" 2>&1
}

# 探针输出若是 compose 自身的报错（而不是容器命令的输出），必须判为
# “无法判断”，绝不能当成 NOT-WRITABLE / NOT-READABLE 这类否定结论。
probe_failed() {
  # 空输出同样是“没跑起来”，不是一个有意义的否定结果。
  [[ -z "${1//[[:space:]]/}" ]] && return 0
  printf '%s' "$1" | grep -qi 'unknown flag\|unknown shorthand\|no such service\|Error response from daemon\|pull access denied\|no configuration file provided'
}

read_env_key() {
  awk -F= -v key="$1" '$0 ~ "^"key"=" { print substr($0, index($0, "=")+1); exit }' .env
}

# ---------------------------------------------------------------- 前置
stage "前置检查"
if ! need docker; then
  fail "找不到 docker 命令"
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  fail "无法访问 docker daemon（当前用户没有权限？请在能跑 docker 的会话里执行）"
  exit 1
fi
pass "docker daemon 可用"

detect_compose_run_flags
if ((${#COMPOSE_RUN_FLAGS[@]})); then
  pass "compose 支持 run --no-build"
else
  warn "当前 compose 不支持 run --no-build，探针改为不带该参数（镜像已存在，不会触发构建）"
fi

if [[ ! -f .env ]]; then
  fail "当前目录没有 .env（$REPO）"
  exit 1
fi
pass "找到 $REPO/.env"

if tail -c 1 .env | od -An -c | grep -qv '\\n'; then
  fail ".env 末行没有换行符，最后一个键可能被吞掉"
else
  pass ".env 以换行结尾"
fi

image=$(docker compose config --images api 2>/dev/null | head -1)
if [[ -z "$image" ]] || ! docker image inspect "$image" >/dev/null 2>&1; then
  IMAGE_READY=0
  fail "api 镜像 ${image:-<unknown>} 不存在：构建还没成功过，容器内探针全部跳过"
else
  pass "api 镜像存在：$image"
fi

# ---------------------------------------------------------------- 1 容器状态
stage "1. 容器状态（-a 包含已退出的容器）"
docker compose ps -a 2>&1 | sed 's/^/  /'
api_line=$(docker compose ps -a --format '{{.Service}}|{{.State}}|{{.Status}}' 2>/dev/null | awk -F'|' '$1=="api"')
if [[ -z "$api_line" ]]; then
  fail "compose 里根本没有 api 容器：创建阶段就失败了，看第 2、3 段"
else
  IFS='|' read -r _ state status <<<"$api_line"
  info "api: state=$state status=$status"
  case "$state" in
    running) pass "api 容器在运行" ;;
    restarting) fail "api 容器在重启循环（启动后立刻退出），看第 2、3 段" ;;
    *) fail "api 容器未运行" ;;
  esac
fi

# ---------------------------------------------------------------- 2-3 日志
stage "2. api 日志：最前面 40 行（真正的报错常在这里，不在 traceback 底部）"
logs=$(docker compose logs api 2>&1)
if [[ -z "$logs" ]]; then
  warn "没有任何日志（容器可能从未创建成功）"
else
  printf '%s\n' "$logs" | head -40 | sed 's/^/  /'
fi

stage "3. api 日志：最后 25 行"
printf '%s\n' "$logs" | tail -25 | sed 's/^/  /'

# 直接从日志里读出结论，省得照着 traceback 翻
if printf '%s' "$logs" | grep -q 'ConfigError'; then
  fail "配置校验失败 → $(printf '%s' "$logs" | grep -o 'serein\.config\.ConfigError:.*' | head -1)"
fi
if printf '%s' "$logs" | grep -q 'PermissionError'; then
  fail "容器内读文件被拒 → $(printf '%s' "$logs" | grep -o 'PermissionError.*' | head -1)"
fi
if printf '%s' "$logs" | grep -q 'Address already in use'; then
  fail "端口被占用：宿主机上可能还有直接运行的 uvicorn"
fi

# ---------------------------------------------------------------- 4 配置
stage "4. 容器内实际生效的 DIARY_* 配置（键名与路径，密钥只显示长度）"
if [[ $IMAGE_READY -eq 0 ]]; then
  warn "跳过：api 镜像不存在"
else
  cfg=$(in_api sh -c 'env | grep "^DIARY_" | sort | while IFS="=" read -r k v; do
      case "$k" in
        *PASSWORD*|*SECRET*|*API_KEY) printf "%s=<redacted len=%s>\n" "$k" "${#v}" ;;
        *) printf "%s=%s\n" "$k" "$v" ;;
      esac
    done')
  if probe_failed "$cfg" || printf '%s' "$cfg" | grep -qi 'cannot connect\|permission denied'; then
    fail "进不去容器看配置（问题不在配置本身）：$(printf '%s' "$cfg" | tail -2 | tr '\n' ' ')"
  elif [[ -z "$cfg" ]]; then
    fail "容器内没有输出任何 DIARY_* 变量，说明环境变量没有传进容器"
  else
    printf '%s\n' "$cfg" | sed 's/^/  /'
  fi
fi

# ---------------------------------------------------------------- 5 数据目录
stage "5. 数据目录挂载与写权限"
host_data=$(read_env_key DIARY_HOST_DATA_DIR)
host_data=${host_data:-./data}
info "宿主路径: $host_data"
if [[ -e "$host_data" ]] || [[ -L "$host_data" ]]; then
  info "类型/权限: $(stat -c '%F %A %U:%G' "$host_data" 2>&1)"
  if [[ -d "$host_data" ]]; then
    pass "宿主路径是目录"
  else
    fail "宿主路径不是目录"
  fi
else
  warn "该路径在本次检查的视图里不可见（agent 看不到未授权子树）；"
  warn "这不等于它不存在，容器内写探针才是结论来源"
fi

if [[ $IMAGE_READY -eq 0 ]]; then
  warn "跳过容器内写探针：api 镜像不存在"
else
  write_probe=$(in_api sh -c 'touch /data/.diagnose-write-probe 2>/dev/null && rm -f /data/.diagnose-write-probe && echo WRITABLE || echo NOT-WRITABLE' | tail -1)
  if probe_failed "$write_probe"; then
    warn "写探针没能运行，无法判断 /data 是否可写：$(printf '%s' "$write_probe" | tail -1)"
  else
    case "$write_probe" in
      WRITABLE)
        container_uid=$(in_api id -u | tail -1)
        pass "容器内 /data 可写（容器 uid=${container_uid:-unknown}）"
        ;;
      NOT-WRITABLE)
        fail "容器内 /data 不可写 → 容器 uid 在宿主上不等于 luessiaw"
        fail "  修法：.env 里设 DIARY_API_UID / DIARY_API_GID，或让该目录对容器 uid 可写"
        ;;
      *)
        warn "写探针返回了预期外的结果，无法判断：${write_probe:-<empty>}"
        ;;
    esac
  fi
fi

# ---------------------------------------------------------------- 6 密钥
stage "6. Immich 密钥文件（只测可读，不读内容）"
immich_enabled=$(read_env_key DIARY_IMMICH_ENABLED)
if [[ "${immich_enabled,,}" != "true" ]]; then
  info "DIARY_IMMICH_ENABLED 未开启，跳过"
elif [[ $IMAGE_READY -eq 0 ]]; then
  warn "跳过：api 镜像不存在"
else
  probe=$(in_api sh -c 'test -r /run/secrets/immich-api-key && echo READABLE || echo NOT-READABLE' | tail -1)
  if probe_failed "$probe"; then
    warn "密钥探针没能运行，无法判断：$(printf '%s' "$probe" | tail -1)"
  else
    case "$probe" in
      READABLE) pass "容器内 /run/secrets/immich-api-key 可读" ;;
      NOT-READABLE) fail "DIARY_IMMICH_ENABLED=true 但容器内读不到密钥（检查 DIARY_IMMICH_API_KEY_HOST_FILE 指向的文件是否存在且可读）" ;;
      *) warn "密钥探针返回了预期外的结果，无法判断：${probe:-<empty>}" ;;
    esac
  fi
fi

# ---------------------------------------------------------------- 7 HTTP
stage "7. 端口与 HTTP 探针"
if ! need curl; then
  warn "没有 curl，跳过"
else
  code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$STAGE_URL/api/v1/health")
  body=$(curl -s -m 5 "$STAGE_URL/api/v1/health" | head -c 200)
  info "$STAGE_URL/api/v1/health → $code $body"
  case "$code" in
    200) pass "健康检查通过" ;;
    502|503|504) fail "反向代理可达，但上游 api 不可用（$code）" ;;
    000) fail "连不上 $STAGE_URL（web/Caddy 容器没起？）" ;;
    *) warn "意外状态码 $code" ;;
  esac
  root_code=$(curl -s -m 5 -o /dev/null -w '%{http_code}' "${STAGE_URL%/}/")
  info "前端 ${STAGE_URL%/}/ → $root_code"
fi

# ---------------------------------------------------------------- 8 构建上下文
stage "8. 构建上下文权限（容器以 uid 1000 运行，不等于你的用户名）"
# 只检查真正进入构建上下文的路径：backend/.dockerignore 排除了 __pycache__、
# .venv、tests 等，它们缺 other 权限也不会影响构建，报出来只是噪音。
#
# 容器读到源码需要两级都满足：父目录 other 可穿越（x），文件 other 可读（r）。
# 目录属主是 luessiaw，agent 本人改不动，必须由用户执行 chmod。
build_dirs=$(find backend/serein -type d \
  -not -path '*/__pycache__' -not -path '*/__pycache__/*' 2>/dev/null)
bad_dirs=$(printf '%s\n' "$build_dirs" | while read -r d; do
  [[ -n "$d" ]] && [[ ! -x "$d" ]] && printf '%s\n' "$d"
done)
bad_files=$(find backend/serein -type f -name '*.py' \
  -not -path '*/__pycache__/*' ! -perm -o+r 2>/dev/null)
top_bad=$(find backend -maxdepth 1 -type f \( -name 'Dockerfile' -o -name 'pyproject.toml' -o -name '.dockerignore' \) ! -perm -o+r 2>/dev/null)
bad_files=$(printf '%s\n%s\n' "$bad_files" "$top_bad")
bad_files=$(printf '%s\n' "$bad_files" | sed '/^$/d')

if [[ -z "$bad_dirs" && -z "$bad_files" ]]; then
  pass "构建上下文完整可读（父目录可穿越、源码与构建文件可读）"
  info "__pycache__ 已按 .dockerignore 排除，不参与判断"
else
  if [[ -n "$bad_dirs" ]]; then
    fail "这些目录缺 o+x（属主是 luessiaw，需要你本人执行 chmod o+x <这些目录>）:"
    printf '%s\n' "$bad_dirs" | sed 's/^/    /'
  fi
  if [[ -n "$bad_files" ]]; then
    fail "这些源码缺 o+r:"
    printf '%s\n' "$bad_files" | sed 's/^/    /'
  fi
fi

# ---------------------------------------------------------------- 汇总
stage "汇总"
if [[ $failures -eq 0 ]]; then
  printf '  RESULT: OK（%s 个提醒）\n' "$warns"
  exit 0
fi
printf '  RESULT: %s 个 FAIL，%s 个 WARN\n' "$failures" "$warns"
cat <<'EOF'

  按 FAIL 逐条处理。三类常见情况：
    - 配置校验失败（ConfigError） → 看它点名哪个环境变量；Immich 可先设
      DIARY_IMMICH_ENABLED=false 做二分
    - /data 不可写               → .env 里设 DIARY_API_UID / DIARY_API_GID 让容器用你的身份
    - 构建上下文缺 other 权限     → 由 luessiaw 本人 chmod o+x 相应目录
EOF
exit 1
