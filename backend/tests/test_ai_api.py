"""Tests for the write-only AI entry API.

These cover the properties that make the interface safe to hand to an agent:
it can create, it cannot read or modify, and a wrong token never writes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase

from fastapi import HTTPException, Response

from serein.api.ai import (
    AiEntryRequest,
    ai_health,
    create_ai_entry,
    require_ai_writer,
)
from serein.config import Settings
from serein.storage.entry import read_entry
from serein.storage.repository import scan_entry_summaries

from test_entry_contract import create_entry_fixture

TOKEN = "test-ai-writer-token"


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AiApiTests(TestCase):
    def make_request(
        self,
        data_dir: Path,
        *,
        enabled: bool = True,
        token_sha256: str | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    settings=Settings(
                        data_dir=data_dir,
                        timezone="Asia/Shanghai",
                        admin_password="a private lock-screen password",
                        session_secret="x" * 32,
                        ai_writer_enabled=enabled,
                        ai_token_sha256=token_sha256 if token_sha256 is not None else digest(TOKEN),
                    )
                )
            ),
            cookies={},
        )

    def bearer(self, token: str = TOKEN) -> str:
        return f"Bearer {token}"

    # ---------------------------------------------------------------- 正向
    def test_creates_an_ai_dialogue_entry(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            request = self.make_request(root)

            created = create_ai_entry(
                AiEntryRequest(
                    title="十月二十八日",
                    content="今天把仿真跑完了，晚上散步一小时。\n",
                    source_material="2026-10-28T09:00:00+08:00/2026-10-28T23:30:00+08:00",
                    source_session_ids=["session-1"],
                ),
                request,
                Response(),
            )

            entry = read_entry(next((root / "entries").iterdir()))
            metadata = json.loads((entry.path / "metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(created.source_kind, "ai-dialogue")
        self.assertEqual(metadata["source_kind"], "ai-dialogue")
        self.assertEqual(metadata["source_review"], "unreviewed")
        self.assertEqual(metadata["source_session_ids"], ["session-1"])
        # 素材只记时间范围，不存对话原文。
        self.assertIn("2026-10-28", metadata["source_material"])
        self.assertNotIn("仿真", json.dumps(metadata, ensure_ascii=False))

    def test_created_entry_is_listed_for_the_owner(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            create_ai_entry(
                AiEntryRequest(content="今天还好。\n"),
                self.make_request(root),
                Response(),
            )

            summaries = scan_entry_summaries(root)

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].source_kind, "ai-dialogue")

    def test_response_does_not_echo_the_body_back(self) -> None:
        """A write endpoint must not become a read surface."""

        response = create_ai_entry(
            AiEntryRequest(content="只有我知道的内容。\n"),
            self.make_request(Path(self.enterContext(TemporaryDirectory()))),
            Response(),
        )

        self.assertEqual(
            set(response.model_dump()),
            {"id", "created_at", "source_kind"},
        )

    # ---------------------------------------------------------------- 认证
    def test_rejects_missing_and_wrong_tokens(self) -> None:
        with TemporaryDirectory() as data_dir:
            request = self.make_request(Path(data_dir))

            for header in (None, "", "Bearer ", "Bearer wrong-token", "Basic abc"):
                with self.assertRaises(HTTPException) as context:
                    require_ai_writer(request, authorization=header)
                self.assertEqual(context.exception.status_code, 401)

            require_ai_writer(request, authorization=self.bearer())

    def test_disabled_feature_rejects_every_token(self) -> None:
        with TemporaryDirectory() as data_dir:
            request = self.make_request(Path(data_dir), enabled=False, token_sha256="")
            with self.assertRaises(HTTPException) as context:
                require_ai_writer(request, authorization=self.bearer())
        self.assertEqual(context.exception.status_code, 401)

    def test_health_reports_writability_without_content(self) -> None:
        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            on = ai_health(self.make_request(root), Response())
            off = ai_health(self.make_request(root, enabled=False, token_sha256=""), Response())

        self.assertTrue(on.write_enabled)
        self.assertFalse(off.write_enabled)
        self.assertEqual(set(on.model_dump()), {"status", "write_enabled"})

    # ---------------------------------------------------------------- 隔离
    def test_does_not_touch_existing_entries(self) -> None:
        """Existing hand-written entries must stay byte-identical.

        The real deployment already holds hundreds of them; an AI write must be
        purely additive.
        """

        with TemporaryDirectory() as data_dir:
            root = Path(data_dir)
            entries = root / "entries"
            create_entry_fixture(
                entries,
                name="202606230930-11111111-1111-4111-8111-111111111111",
                entry_id="11111111-1111-4111-8111-111111111111",
                created_at="2026-06-23T09:30:00+08:00",
                content="我自己写的一段。\n",
            )
            human_dir = entries / "202606230930-11111111-1111-4111-8111-111111111111"
            before = snapshot(human_dir)

            create_ai_entry(
                AiEntryRequest(content="AI 写的一段。\n"),
                self.make_request(root),
                Response(),
            )

            self.assertEqual(snapshot(human_dir), before, "既有条目被改动了")
            self.assertEqual(len(list(entries.iterdir())), 2)

    def test_rejects_invalid_payloads(self) -> None:
        from pydantic import ValidationError

        for bad in (
            {"content": "   \n"},
            {"content": ""},
            {"content": "ok", "source_review": "maybe"},
            {"content": "ok", "source_material": "x" * 300},
        ):
            with self.assertRaises(ValidationError):
                AiEntryRequest(**bad)

def snapshot(directory: Path) -> dict[str, bytes]:
    """Every file under one entry directory, keyed by relative path."""

    return {
        str(path.relative_to(directory)): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


class AiWriterCannotReachOwnerEndpointsTests(TestCase):
    """An ai-writer token must never unlock a read or mutate endpoint.

    This is the property the whole design rests on: the agent can see only what
    it just wrote, and cannot rewrite history.
    """

    def make_request(self, data_dir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    settings=Settings(
                        data_dir=data_dir,
                        timezone="Asia/Shanghai",
                        admin_password="a private lock-screen password",
                        session_secret="x" * 32,
                        ai_writer_enabled=True,
                        ai_token_sha256=digest(TOKEN),
                    )
                )
            ),
            cookies={},
        )

    def test_ai_token_as_cookie_is_rejected(self) -> None:
        from serein.api.auth import read_current_session
        from serein.security import create_ai_writer_token

        with TemporaryDirectory() as data_dir:
            request = self.make_request(Path(data_dir))
            settings = request.app.state.settings
            # 即使 token 本身是签名过的合法串，塞进 cookie 也不该被当成管理员。
            request.cookies = {"serein_session": create_ai_writer_token(settings)}

            self.assertIsNone(read_current_session(request))

    def test_ai_token_as_cookie_from_env_secret_is_rejected(self) -> None:
        from serein.api.auth import read_current_session
        from serein.security import AI_WRITER_TOKEN_SALT
        from itsdangerous import URLSafeTimedSerializer
        from time import time

        with TemporaryDirectory() as data_dir:
            request = self.make_request(Path(data_dir))
            settings = request.app.state.settings
            forged = URLSafeTimedSerializer(
                secret_key=settings.session_secret, salt=AI_WRITER_TOKEN_SALT
            ).dumps({"sub": "ai-writer", "iat": int(time())})
            request.cookies = {"serein_session": forged}

            self.assertIsNone(read_current_session(request))
