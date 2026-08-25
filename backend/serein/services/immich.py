from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
import socket
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from uuid import UUID

from PIL import Image, UnidentifiedImageError

from serein.config import Settings
from serein.storage.repository import ImageAttachment

MAX_ORIGINAL_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_JSON_BYTES = 2 * 1024 * 1024
COMPATIBLE_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImmichError(Exception):
    def __init__(
        self, code: str, message: str | None = None, status_code: int = 502
    ) -> None:
        super().__init__(message or code)
        self.code = code
        self.status_code = status_code


class ImmichDownloadTooLarge(ImmichError):
    def __init__(self) -> None:
        super().__init__("immich_asset_too_large", status_code=413)


@dataclass(frozen=True)
class ImmichHttpResponse:
    status_code: int
    headers: dict[str, str]
    content: bytes


Requester = Callable[
    [str, str, dict[str, str], dict[str, Any] | None, int],
    ImmichHttpResponse,
]


class ImmichClient:
    def __init__(self, settings: Settings, requester: Requester | None = None) -> None:
        self.enabled = settings.immich_enabled
        self.base_url = settings.immich_base_url.rstrip("/") + "/"
        self.api_key = settings.immich_api_key
        self.requester = requester or self._stdlib_request

    def _ensure_configured(self) -> None:
        if not self.enabled:
            raise ImmichError("immich_disabled", status_code=503)
        if not self.api_key:
            raise ImmichError("immich_not_configured", status_code=503)

    async def status(self) -> dict[str, str]:
        if not self.enabled:
            return {"status": "disabled"}
        if not self.api_key:
            return {"status": "unavailable", "error": "immich_not_configured"}
        try:
            await self._json("GET", "server/ping")
            return {"status": "available"}
        except ImmichError as exc:
            return {"status": "unavailable", "error": exc.code}

    async def albums(self) -> list[dict[str, Any]]:
        payload = await self._json("GET", "albums")
        if not isinstance(payload, list):
            raise ImmichError("immich_invalid_response")
        return [
            {
                "id": str(album.get("id", "")),
                "name": str(album.get("albumName", "")),
                "asset_count": int(album.get("assetCount") or 0),
                "cover_asset_id": album.get("albumThumbnailAssetId"),
            }
            for album in payload
            if album.get("id") and album.get("albumName")
        ]

    async def search(
        self,
        *,
        query: str | None,
        taken_after: date | None,
        taken_before: date | None,
        album_id: UUID | None,
        cursor: str | None,
        limit: int,
    ) -> dict[str, Any]:
        page = _decode_cursor(cursor)
        body: dict[str, Any] = {
            "page": page,
            "size": min(max(limit, 1), 100),
            "type": "IMAGE",
            "isNotInAlbum": False,
            "withDeleted": False,
        }
        if taken_after:
            body["takenAfter"] = taken_after.isoformat()
        if taken_before:
            body["takenBefore"] = taken_before.isoformat()
        if album_id:
            body["albumIds"] = [str(album_id)]
        path = "search/smart" if query and query.strip() else "search/metadata"
        if query and query.strip():
            body["query"] = query.strip()

        payload = await self._json("POST", path, body)
        assets = payload.get("assets") if isinstance(payload, dict) else None
        if not isinstance(assets, dict) or not isinstance(assets.get("items"), list):
            raise ImmichError("immich_invalid_response")

        items = []
        for asset in assets["items"]:
            if not _is_importable_image(asset):
                continue
            asset_id = asset.get("id")
            if not asset_id:
                continue
            items.append(
                {
                    "id": str(asset_id),
                    "filename": str(asset.get("originalFileName") or "image"),
                    "alt": _filename_alt(asset.get("originalFileName")),
                    "taken_at": asset.get("fileCreatedAt") or asset.get("localDateTime"),
                    "width": asset.get("width")
                    or asset.get("exifInfo", {}).get("exifImageWidth"),
                    "height": asset.get("height")
                    or asset.get("exifInfo", {}).get("exifImageHeight"),
                }
            )

        next_page = assets.get("nextPage")
        if next_page is None:
            total = int(assets.get("total") or len(items))
            next_page = page + 1 if page * body["size"] < total else None
        next_cursor = _encode_cursor(int(next_page)) if next_page else None
        return {"items": items, "next_cursor": next_cursor}

    async def thumbnail(self, asset_id: UUID) -> tuple[bytes, str]:
        response = await self._request(
            "GET", f"assets/{asset_id}/thumbnail", query={"size": "thumbnail"}, limit=5 * 1024 * 1024
        )
        return response.content, response.headers.get("content-type", "image/jpeg").split(";")[0]

    async def import_image(self, asset_id: UUID, alt: str | None) -> ImageAttachment:
        asset = await self._json("GET", f"assets/{asset_id}")
        if not _is_importable_image(asset):
            raise ImmichError("immich_asset_not_importable", status_code=422)

        filename = str(asset.get("originalFileName") or f"{asset_id}.jpg")
        original_mime = str(asset.get("originalMimeType") or "").lower()
        try_original = original_mime in {"image/jpeg", "image/png", "image/webp"}

        data: bytes | None = None
        if try_original:
            try:
                response = await self._request(
                    "GET", f"assets/{asset_id}/original", limit=MAX_ORIGINAL_BYTES
                )
                if _compatible_image(response.content):
                    data = response.content
            except ImmichDownloadTooLarge:
                pass

        if data is None:
            response = await self._request(
                "GET",
                f"assets/{asset_id}/thumbnail",
                query={"size": "fullsize"},
                limit=MAX_ORIGINAL_BYTES,
            )
            data = response.content
            filename = f"{asset_id}.jpg"
            if not _valid_image(data):
                raise ImmichError("immich_invalid_image", status_code=422)

        return ImageAttachment(content=data, alt=alt or _filename_alt(filename))

    async def _json(
        self, method: str, path: str, json_body: dict[str, Any] | None = None
    ) -> Any:
        response = await self._request(method, path, json_body=json_body, limit=MAX_JSON_BYTES)
        try:
            return json.loads(response.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ImmichError("immich_invalid_response") from None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
        limit: int,
    ) -> ImmichHttpResponse:
        self._ensure_configured()
        url = urljoin(self.base_url, path.lstrip("/"))
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {"x-api-key": self.api_key or "", "accept": "application/json"}
        try:
            response = await asyncio.to_thread(
                self.requester, method, url, headers, json_body, limit
            )
        except ImmichError:
            raise
        except (TimeoutError, socket.timeout):
            raise ImmichError("immich_timeout", status_code=504) from None
        except (OSError, URLError):
            raise ImmichError("immich_unavailable", status_code=503) from None
        self._raise_for_status(response.status_code)
        return response

    @staticmethod
    def _stdlib_request(
        method: str,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any] | None,
        limit: int,
    ) -> ImmichHttpResponse:
        data = None
        request_headers = dict(headers)
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            request_headers["content-type"] = "application/json"
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=60) as response:
                content = bytearray()
                while chunk := response.read(64 * 1024):
                    content.extend(chunk)
                    if len(content) > limit:
                        raise ImmichDownloadTooLarge()
                return ImmichHttpResponse(
                    status_code=response.status,
                    headers={key.lower(): value for key, value in response.headers.items()},
                    content=bytes(content),
                )
        except HTTPError as exc:
            return ImmichHttpResponse(status_code=exc.code, headers={}, content=b"")

    @staticmethod
    def _raise_for_status(status_code: int) -> None:
        if status_code == 401:
            raise ImmichError("immich_key_invalid", status_code=503)
        if status_code == 403:
            raise ImmichError("immich_forbidden", status_code=503)
        if status_code == 404:
            raise ImmichError("immich_asset_not_found", status_code=404)
        if status_code >= 400:
            raise ImmichError("immich_request_failed", status_code=502)


def get_immich_client(request: Any) -> ImmichClient:
    return ImmichClient(request.app.state.settings)


def _is_importable_image(asset: Any) -> bool:
    if not isinstance(asset, dict):
        return False
    return (
        asset.get("type") == "IMAGE"
        and not asset.get("isTrashed", False)
        and not asset.get("isOffline", False)
    )


def _valid_image(data: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width * height > MAX_PIXELS:
                return False
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _compatible_image(data: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in COMPATIBLE_FORMATS:
                return False
            if image.width * image.height > MAX_PIXELS:
                return False
            image.verify()
        return True
    except (UnidentifiedImageError, OSError, ValueError):
        return False


def _encode_cursor(page: int) -> str:
    return base64.urlsafe_b64encode(str(page).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 1
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        page = int(base64.urlsafe_b64decode(padded).decode())
        if page < 1:
            raise ValueError
        return page
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise ImmichError("immich_invalid_cursor", status_code=422) from None


def default_alt(asset: dict[str, Any]) -> str:
    return str(asset.get("originalFileName") or "Immich photo")


def _filename_alt(filename: Any) -> str:
    value = str(filename or "Immich photo")
    return value.rsplit(".", maxsplit=1)[0] or "Immich photo"
