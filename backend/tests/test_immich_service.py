"""Tests for the secret-safe Immich v3 adapter."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from PIL import Image

from serein.config import Settings
from serein.services.immich import (
    ImmichClient,
    ImmichDownloadTooLarge,
    ImmichError,
    ImmichHttpResponse,
)


ASSET_ID = UUID("77777777-7777-4777-8777-777777777777")


class ImmichClientTests(IsolatedAsyncioTestCase):
    def make_settings(self, data_dir: Path) -> Settings:
        return Settings(
            data_dir=data_dir,
            timezone="Asia/Shanghai",
            admin_password="private password",
            session_secret="x" * 32,
            immich_enabled=True,
            immich_base_url="http://immich.test/api",
            immich_api_key="secret-key",
        )

    async def test_search_normalizes_results_and_keeps_key_in_header(self) -> None:
        with TemporaryDirectory() as data_dir:
            def requester(method, url, headers, json_body, limit):
                self.assertEqual(method, "POST")
                self.assertEqual(urlparse(url).path, "/api/search/metadata")
                self.assertEqual(headers["x-api-key"], "secret-key")
                self.assertNotIn("secret-key", url)
                self.assertLessEqual(limit, 2 * 1024 * 1024)
                self.assertEqual(json_body["type"], "IMAGE")
                return json_response({"assets": {"items": [{
                    "id": str(ASSET_ID), "type": "IMAGE",
                    "localDateTime": "2026-08-25T10:00:00",
                    "width": 100, "height": 80, "originalFileName": "rain.jpg",
                }], "nextPage": "2"}})

            client = ImmichClient(self.make_settings(Path(data_dir)), requester)
            result = await client.search(
                query=None, taken_after=None, taken_before=None,
                album_id=None, cursor=None, limit=60,
            )

        self.assertEqual(result["items"][0]["alt"], "rain")
        self.assertIsNotNone(result["next_cursor"])

    async def test_import_keeps_compatible_original(self) -> None:
        image = create_png_bytes()
        with TemporaryDirectory() as data_dir:
            def requester(method, url, headers, json_body, limit):
                path = urlparse(url).path
                if path.endswith(str(ASSET_ID)):
                    return json_response({
                        "id": str(ASSET_ID), "type": "IMAGE", "isTrashed": False,
                        "isOffline": False, "originalMimeType": "image/png",
                        "width": 6, "height": 4, "originalFileName": "original.png",
                    })
                if path.endswith("/original"):
                    return image_response(image, "image/png")
                return ImmichHttpResponse(500, {}, b"")

            client = ImmichClient(self.make_settings(Path(data_dir)), requester)
            imported = await client.import_image(ASSET_ID, None)

        self.assertEqual(imported.content, image)
        self.assertEqual(imported.alt, "original")

    async def test_import_falls_back_to_fullsize_for_heic(self) -> None:
        image = create_png_bytes()
        with TemporaryDirectory() as data_dir:
            def requester(method, url, headers, json_body, limit):
                parsed = urlparse(url)
                if parsed.path.endswith(str(ASSET_ID)):
                    return json_response({
                        "id": str(ASSET_ID), "type": "IMAGE", "isTrashed": False,
                        "isOffline": False, "originalMimeType": "image/heic",
                        "width": 100, "height": 80, "originalFileName": "phone.heic",
                    })
                self.assertEqual(parse_qs(parsed.query)["size"], ["fullsize"])
                return image_response(image, "image/png")

            client = ImmichClient(self.make_settings(Path(data_dir)), requester)
            imported = await client.import_image(ASSET_ID, None)

        self.assertEqual(imported.content, image)

    async def test_oversize_original_falls_back_to_fullsize(self) -> None:
        image = create_png_bytes()
        with TemporaryDirectory() as data_dir:
            def requester(method, url, headers, json_body, limit):
                parsed = urlparse(url)
                if parsed.path.endswith(str(ASSET_ID)):
                    return json_response({
                        "id": str(ASSET_ID), "type": "IMAGE", "isTrashed": False,
                        "isOffline": False, "originalMimeType": "image/jpeg",
                        "originalFileName": "huge.jpg",
                    })
                if parsed.path.endswith("/original"):
                    raise ImmichDownloadTooLarge()
                self.assertEqual(parse_qs(parsed.query)["size"], ["fullsize"])
                return image_response(image, "image/jpeg")

            client = ImmichClient(self.make_settings(Path(data_dir)), requester)
            imported = await client.import_image(ASSET_ID, None)

        self.assertEqual(imported.content, image)

    async def test_permission_failure_uses_safe_error(self) -> None:
        with TemporaryDirectory() as data_dir:
            client = ImmichClient(
                self.make_settings(Path(data_dir)),
                lambda method, url, headers, json_body, limit: ImmichHttpResponse(
                    403, {}, b"private upstream detail"
                ),
            )
            with self.assertRaises(ImmichError) as context:
                await client.albums()

        self.assertEqual(context.exception.code, "immich_forbidden")
        self.assertNotIn("private upstream detail", str(context.exception))


def json_response(value) -> ImmichHttpResponse:
    return ImmichHttpResponse(
        200, {"content-type": "application/json"}, json.dumps(value).encode()
    )


def image_response(content: bytes, media_type: str) -> ImmichHttpResponse:
    return ImmichHttpResponse(200, {"content-type": media_type}, content)


def create_png_bytes() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (6, 4), "#789abc").save(stream, format="PNG")
    return stream.getvalue()
