"""把 DSH 会话日志里当天的对话整理成一份候选日记。

这个工具**只负责取素材**，不负责判断哪段值得留下，也不直接提交——它输出
一份带出处的 Markdown，供人或 agent 进一步筛选后再用
`scripts/post-ai-entry.sh` 提交。

为什么需要它：DSH 的定时提醒绑定在单个 Session 上，醒来时看不到别的窗口
里聊了什么。素材必须从会话日志里取。

会话日志格式（DSH 0.2，实测）：

    ~/.dsh-home/sessions/<工作区转义名>/session-<uuid>/session.v4.jsonl.zstd

每行一个 JSON 事件。真正属于用户的输入是 `type == "user/message"` 且
`data.source.kind == "user"` 的事件；同一事件类型里还有 `agent-instructions`
和 `runtime-context` 两种系统注入，取素材时必须排除，否则会把规则文件
当成用户说过的话。

用法：

    python -m serein.services.session_digest --date 2026-11-02
    python -m serein.services.session_digest --date 2026-11-02 --out /tmp/day.md

隐私：默认只输出用户自己说的话，不输出助手回复（助手的话由模型重新生成，
没必要复制粘贴）。截断长度可调，但**不要**因为想保留更多细节而调得很大——
素材应留在会话日志里，日记只留提炼结果。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

DEFAULT_SESSIONS_ROOT = Path.home() / "sessions"
USER_SOURCE_KIND = "user"
MAX_PART_CHARS = 2000


@dataclass
class Utterance:
    """One thing the user said, with the session it came from."""

    session_id: str
    at: datetime
    text: str


@dataclass
class SessionDigest:
    """Everything the user said in one workspace on one local date."""

    workspace: Path
    day: date
    timezone: str
    utterances: list[Utterance] = field(default_factory=list)
    skipped_sessions: int = 0

    @property
    def session_ids(self) -> list[str]:
        seen: list[str] = []
        for item in self.utterances:
            if item.session_id not in seen:
                seen.append(item.session_id)
        return seen

    @property
    def empty(self) -> bool:
        return not self.utterances


def escape_workspace(path: Path) -> str:
    """Reproduce DSH's workspace directory naming.

    DSH encodes a workspace path as `--<path with / replaced by ->--`, with each
    non-ASCII character escaped as `~XXXX` (its UTF-16 code unit in hex). We try
    the escaped form first and fall back to matching any directory whose
    decoding yields this path, so a format change in DSH does not silently
    produce an empty digest.
    """

    # 实测样例：/home/... -> --home-luessiaw-...--
    # 开头的 "/" 只贡献分隔前缀里的那个 "-"，不额外再加一个。
    parts = []
    for index, char in enumerate(str(path)):
        if char == "/":
            parts.append("-" if index > 0 else "")
        elif char.isascii() and (char.isalnum() or char in "-_"):
            parts.append(char)
        else:
            parts.append("~" + format(ord(char), "X"))
    return "--" + "".join(parts) + "--"


def find_session_dirs(sessions_root: Path, workspace: Path) -> list[Path]:
    """Return session directories belonging to one workspace."""

    if not sessions_root.is_dir():
        return []

    escaped = escape_workspace(workspace)
    direct = sessions_root / escaped
    if direct.is_dir():
        dirs = sorted(direct.glob("session-*"))
        return [d for d in dirs if d.is_dir()]

    # 退路：直接比较目录名里解码回来的路径。
    matched: list[Path] = []
    for candidate in sessions_root.iterdir():
        if not candidate.is_dir() or not candidate.name.startswith("--"):
            continue
        if decoded_workspace(candidate.name) == workspace:
            matched.extend(d for d in sorted(candidate.glob("session-*")) if d.is_dir())
    return matched


def decoded_workspace(dirname: str) -> Path | None:
    """Best-effort inverse of `escape_workspace`, or None if it does not fit."""

    body = dirname[2:-2] if dirname.startswith("--") and dirname.endswith("--") else None
    if body is None:
        return None
    out: list[str] = ["/"]
    index = 0
    while index < len(body):
        char = body[index]
        if char == "~":
            hex_digits = body[index + 1 : index + 5]
            try:
                out.append(chr(int(hex_digits, 16)))
            except ValueError:
                return None
            index += 5
        elif char == "-":
            out.append("/")
            index += 1
        else:
            out.append(char)
            index += 1
    try:
        return Path("".join(out))
    except (OSError, ValueError):
        return None


def read_events(log_path: Path) -> list[dict]:
    """Yield decoded events from a zstd-compressed JSONL session log."""

    raw = decompress(log_path)
    events: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def decompress(path: Path) -> str:
    """Read a session log, which may be zstd-compressed or plain JSONL."""

    if path.suffix == ".zstd":
        # 不引入 python-zstandard 依赖：宿主机有 zstd 命令，且只在读日志时用。
        completed = subprocess.run(
            ["zstd", "-dc", str(path)],
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"zstd 解码失败（需要 zstd 命令）: {completed.stderr.decode()[:200]}"
            )
        return completed.stdout.decode("utf-8", errors="replace")
    return path.read_text(encoding="utf-8", errors="replace")


def extract_utterances(
    events: list[dict],
    *,
    session_id: str,
    day: date,
    tz: ZoneInfo,
) -> list[Utterance]:
    """Pull the user's own words for one local date."""

    found: list[Utterance] = []
    for event in events:
        if event.get("type") != "user/message":
            continue
        data = event.get("data") or {}
        source = data.get("source") or {}
        # 只有真正的用户输入算素材；agent-instructions 和 runtime-context 是
        # 系统注入的规则与上下文，把它们当对话会污染日记。
        if source.get("kind") != USER_SOURCE_KIND:
            continue

        timestamp = event.get("time")
        if not isinstance(timestamp, (int, float)):
            continue
        at = datetime.fromtimestamp(timestamp / 1000, tz=tz)
        if at.date() != day:
            continue

        text = join_parts(data.get("content"))
        if not text.strip():
            continue
        found.append(Utterance(session_id=session_id, at=at, text=text))
    return found


def join_parts(content: object) -> str:
    if not isinstance(content, list):
        return ""
    pieces: list[str] = []
    for part in content:
        if isinstance(part, dict) and part.get("type") == "text":
            value = part.get("text")
            if isinstance(value, str):
                pieces.append(value)
    text = "\n".join(pieces).strip()
    if len(text) > MAX_PART_CHARS:
        text = text[:MAX_PART_CHARS].rstrip() + "…"
    return text


def build_digest(
    *,
    sessions_root: Path,
    workspace: Path,
    day: date,
    timezone: str,
) -> SessionDigest:
    tz = ZoneInfo(timezone)
    digest = SessionDigest(workspace=workspace, day=day, timezone=timezone)

    for session_dir in find_session_dirs(sessions_root, workspace):
        log_files = sorted(
            [p for p in session_dir.iterdir() if p.name.endswith(".jsonl") or p.name.endswith(".jsonl.zstd")],
            reverse=True,
        )
        if not log_files:
            digest.skipped_sessions += 1
            continue
        try:
            events = read_events(log_files[0])
        except (OSError, RuntimeError):
            digest.skipped_sessions += 1
            continue
        digest.utterances.extend(
            extract_utterances(
                events,
                session_id=session_dir.name.removeprefix("session-"),
                day=day,
                tz=tz,
            )
        )

    digest.utterances.sort(key=lambda item: item.at)
    return digest


def render_digest(digest: SessionDigest) -> str:
    """Render the material as Markdown for a human or agent to curate."""

    lines = [
        f"# {digest.day.isoformat()} 对话素材",
        "",
        f"- 工作区：`{digest.workspace}`",
        f"- 时区：{digest.timezone}",
        f"- 会话：{len(digest.session_ids)} 个",
        f"- 用户发言：{len(digest.utterances)} 条",
    ]
    if digest.skipped_sessions:
        lines.append(f"- 跳过（读不到或已清理）：{digest.skipped_sessions} 个会话")
    lines.append("")
    if digest.empty:
        lines.append("这一天没有可用的用户发言。空日记比勉强生成的日记更有害，建议不生成。")
        return "\n".join(lines) + "\n"

    for item in digest.utterances:
        lines.append(f"## {item.at.strftime('%H:%M')}")
        lines.append("")
        lines.append(item.text)
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="本地日期 YYYY-MM-DD（默认昨天）")
    parser.add_argument("--workspace", required=True, help="会话所属工作区（绝对路径）")
    parser.add_argument("--sessions-root", default=str(DEFAULT_SESSIONS_ROOT))
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--out", help="写入文件；省略则打印到 stdout")
    args = parser.parse_args(argv)

    tz = ZoneInfo(args.timezone)
    if args.date:
        try:
            day = date.fromisoformat(args.date)
        except ValueError:
            print(f"ERROR: --date 需要 YYYY-MM-DD，收到 {args.date}", file=sys.stderr)
            return 2
    else:
        day = (datetime.now(tz) - timedelta(days=1)).date()

    digest = build_digest(
        sessions_root=Path(args.sessions_root),
        workspace=Path(args.workspace),
        day=day,
        timezone=args.timezone,
    )
    rendered = render_digest(digest)

    if args.out:
        out_path = Path(args.out)
        # 素材含用户原话，比最终日记更接近原文。别把它写进日记数据目录或
        # 任何会被同步/备份的地方，用完即删。
        out_path.write_text(rendered, encoding="utf-8")
        try:
            out_path.chmod(0o600)
        except OSError:
            pass
        print(
            f"已写入 {out_path}（{len(digest.utterances)} 条发言，{len(digest.session_ids)} 个会话）\n"
            "提醒：这份素材含原话，用完请删除；不要放进日记数据目录。"
        )
    else:
        sys.stdout.write(rendered)
    return 0 if not digest.empty else 3


if __name__ == "__main__":
    sys.exit(main())
