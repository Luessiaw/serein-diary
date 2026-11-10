"""Tests for extracting a day of conversation from DSH session logs.

The important properties: only the user's own words count (system-injected
messages must never be mistaken for them), the local date filter is right, and
an empty day is reported as empty rather than padded out.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from zoneinfo import ZoneInfo

from serein.services.session_digest import (
    DEFAULT_SESSIONS_ROOT,
    build_digest,
    decoded_workspace,
    escape_workspace,
    extract_utterances,
    render_digest,
)

TZ = ZoneInfo("Asia/Shanghai")
WORKSPACE = Path("/home/luessiaw/storage/data/01_生活/00_我的记录/05_心理健康")


def ms(year: int, month: int, day: int, hour: int, minute: int) -> int:
    from datetime import datetime

    return int(datetime(year, month, day, hour, minute, tzinfo=TZ).timestamp() * 1000)


def window(start: date, days: int = 1) -> tuple[datetime, datetime]:
    """Half-open local window starting at `start` 00:00."""

    since = datetime.combine(start, time.min, tzinfo=TZ)
    return since, since + timedelta(days=days)


DAY_28 = date(2026, 10, 28)
WINDOW_28 = window(DAY_28)


def user_event(text: str, when: int, kind: str = "user") -> dict:
    return {
        "type": "user/message",
        "time": when,
        "data": {
            "id": "x",
            "role": "user",
            "source": {"kind": kind},
            "content": [{"type": "text", "text": text}],
        },
    }


class WorkspaceEncodingTests(TestCase):
    def test_escape_matches_the_observed_directory_name(self) -> None:
        # 这是 DSH 实际生成的目录名，比对不上就读不到任何日志。
        self.assertEqual(
            escape_workspace(WORKSPACE),
            "--home-luessiaw-storage-data-01_~751F~6D3B-00_~6211~7684~8BB0~5F55"
            "-05_~5FC3~7406~5065~5EB7--",
        )

    def test_decode_is_the_inverse_of_escape(self) -> None:
        self.assertEqual(decoded_workspace(escape_workspace(WORKSPACE)), WORKSPACE)

    def test_decode_rejects_foreign_names(self) -> None:
        self.assertIsNone(decoded_workspace("not-a-session-dir"))


class ExtractTests(TestCase):
    def test_keeps_only_real_user_messages(self) -> None:
        events = [
            user_event("今天把仿真跑完了。", ms(2026, 10, 28, 10, 0)),
            user_event("你是温和的伙伴。", ms(2026, 10, 28, 10, 1), kind="agent-instructions"),
            user_event("当前时间……", ms(2026, 10, 28, 10, 2), kind="runtime-context"),
        ]

        found = extract_utterances(events, session_id="s1", since=WINDOW_28[0], until=WINDOW_28[1], tz=TZ)

        self.assertEqual([item.text for item in found], ["今天把仿真跑完了。"])

    def test_filters_by_local_date(self) -> None:
        events = [
            user_event("昨天的话", ms(2026, 10, 27, 23, 59)),
            user_event("凌晨的话", ms(2026, 10, 28, 0, 1)),
        ]

        found = extract_utterances(events, session_id="s1", since=WINDOW_28[0], until=WINDOW_28[1], tz=TZ)

        self.assertEqual([item.text for item in found], ["凌晨的话"])

    def test_ignores_empty_text_and_non_text_parts(self) -> None:
        events = [
            user_event("   ", ms(2026, 10, 28, 10, 0)),
            {
                "type": "user/message",
                "time": ms(2026, 10, 28, 10, 1),
                "data": {"source": {"kind": "user"}, "content": [{"type": "image"}]},
            },
            user_event("真的话", ms(2026, 10, 28, 10, 2)),
        ]

        found = extract_utterances(events, session_id="s1", since=WINDOW_28[0], until=WINDOW_28[1], tz=TZ)

        self.assertEqual([item.text for item in found], ["真的话"])

    def test_truncates_a_very_long_message(self) -> None:
        events = [user_event("字" * 5000, ms(2026, 10, 28, 10, 0))]

        found = extract_utterances(events, session_id="s1", since=WINDOW_28[0], until=WINDOW_28[1], tz=TZ)

        self.assertLessEqual(len(found[0].text), 2001)
        self.assertTrue(found[0].text.endswith("…"))


class DigestTests(TestCase):
    def write_session(self, root: Path, session_id: str, events: list[dict]) -> None:
        session_dir = root / escape_workspace(WORKSPACE) / f"session-{session_id}"
        session_dir.mkdir(parents=True)
        lines = "\n".join(json.dumps(event, ensure_ascii=False) for event in events)
        (session_dir / "session.v4.jsonl").write_text(lines + "\n", encoding="utf-8")

    def test_merges_sessions_and_sorts_by_time(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_session(root, "aaaa", [user_event("下午", ms(2026, 10, 28, 15, 0))])
            self.write_session(root, "bbbb", [user_event("上午", ms(2026, 10, 28, 9, 0))])

            digest = build_digest(
                sessions_root=root, workspace=WORKSPACE, since=WINDOW_28[0], until=WINDOW_28[1], timezone="Asia/Shanghai"
            )

        self.assertEqual([item.text for item in digest.utterances], ["上午", "下午"])
        self.assertEqual(sorted(digest.session_ids), ["aaaa", "bbbb"])

    def test_empty_day_is_reported_as_empty(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_session(root, "aaaa", [user_event("别的话", ms(2026, 10, 27, 9, 0))])

            digest = build_digest(
                sessions_root=root, workspace=WORKSPACE, since=WINDOW_28[0], until=WINDOW_28[1], timezone="Asia/Shanghai"
            )
            rendered = render_digest(digest)

        self.assertTrue(digest.empty)
        self.assertIn("没有可用的用户发言", rendered)
        self.assertIn("建议不生成", rendered)

    def test_missing_sessions_root_yields_empty_digest(self) -> None:
        digest = build_digest(
            sessions_root=Path("/nonexistent-sessions-root"),
            workspace=WORKSPACE,
            since=WINDOW_28[0],
            until=WINDOW_28[1],
            timezone="Asia/Shanghai",
        )

        self.assertTrue(digest.empty)

    def test_rendered_digest_records_provenance(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_session(root, "aaaa", [user_event("一句话", ms(2026, 10, 28, 9, 0))])
            digest = build_digest(
                sessions_root=root, workspace=WORKSPACE, since=WINDOW_28[0], until=WINDOW_28[1], timezone="Asia/Shanghai"
            )
            rendered = render_digest(digest)

        self.assertIn("2026-10-28", rendered)
        self.assertIn("09:00", rendered)
        self.assertIn("会话：1", rendered)
        self.assertIn("用户发言：1 条", rendered)
        self.assertIn("时区：Asia/Shanghai", rendered)

    def test_default_sessions_root_is_the_home_sessions_dir(self) -> None:
        # DSH 服务的 HOME 是 /var/lib/dsh/home，日志就在 $HOME/sessions 下面。
        self.assertEqual(DEFAULT_SESSIONS_ROOT, Path.home() / "sessions")


class SessionGroupingTests(TestCase):
    """A conversation can span days; one conversation is one diary unit."""

    def write_session(self, root: Path, session_id: str, events: list[dict]) -> None:
        session_dir = root / escape_workspace(WORKSPACE) / f"session-{session_id}"
        session_dir.mkdir(parents=True)
        lines = "\n".join(json.dumps(event, ensure_ascii=False) for event in events)
        (session_dir / "session.v4.jsonl").write_text(lines + "\n", encoding="utf-8")

    def test_cross_day_session_reports_last_message_time(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_session(root, "long", [
                user_event("第一天", ms(2026, 11, 10, 21, 0)),
                user_event("第二天", ms(2026, 11, 11, 22, 15)),
                user_event("第三天收尾", ms(2026, 11, 12, 23, 40)),
            ])
            digest = build_digest(
                sessions_root=root, workspace=WORKSPACE,
                since=window(date(2026, 11, 10), 3)[0],
                until=window(date(2026, 11, 10), 3)[1],
                timezone="Asia/Shanghai",
            )
            rendered = render_digest(digest)

        grouped = digest.by_session()
        self.assertEqual(list(grouped), ["long"])
        last = grouped["long"][-1].at
        # 日记时间取最后一条发言，而不是整理时刻。
        self.assertEqual(last.hour, 23)
        self.assertIn("建议日记时间：`2026-11-12T23:40:00+08:00`", rendered)

    def test_skip_session_excludes_already_digested_conversation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_session(root, "done", [user_event("已整理", ms(2026, 11, 12, 20, 0))])
            self.write_session(root, "todo", [user_event("待整理", ms(2026, 11, 12, 21, 0))])
            day = window(date(2026, 11, 12))
            digest = build_digest(
                sessions_root=root, workspace=WORKSPACE,
                since=day[0], until=day[1],
                timezone="Asia/Shanghai",
                skip_sessions={"done"},
            )

        self.assertEqual(list(digest.by_session()), ["todo"])
        self.assertEqual([u.text for u in digest.utterances], ["待整理"])

    def test_window_is_half_open_at_midnight(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_session(root, "s", [
                user_event("23:59 前一天", ms(2026, 11, 11, 23, 59)),
                user_event("00:00 当天", ms(2026, 11, 12, 0, 0)),
            ])
            digest = build_digest(
                sessions_root=root, workspace=WORKSPACE,
                since=window(date(2026, 11, 12))[0],
                until=window(date(2026, 11, 12))[1],
                timezone="Asia/Shanghai",
            )

        self.assertEqual([u.text for u in digest.utterances], ["00:00 当天"])
