import asyncio
from typing import Optional

import aiohttp

from VampireMusic import logger


def mask_key(key: str | None) -> str:
    """Mask a secret API key for safe logging (first 6 + last 4 chars)."""
    if not key:
        return "<unset>"
    if len(key) <= 10:
        return key[:2] + "***"
    return f"{key[:6]}…{key[-4:]}"


class LilyApi:
    """Client for the lily-style ``/search/all`` music API.

    The endpoint searches one or more platforms (e.g. JioSaavn) for a text
    query and returns results that already include a ready-to-stream
    ``stream_url``. That URL is a direct CDN link, so it can be handed
    straight to PyTgCalls/ffmpeg as a media path (no local download).

    Example:
        GET {base}/search/all?api_key=...&platforms=jiosaavn&q=kesariya
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        *,
        name: str = "lily",
        platform: str = "jiosaavn",
        retries: int = 1,
        timeout: int = 15,
    ):
        self.name = name
        self.base = api_url.rstrip("/")
        self.api_key = api_key
        # Comma-separated list of platforms, tried in the given order.
        self.platforms = [p.strip() for p in platform.split(",") if p.strip()]
        self.retries = max(1, retries)
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _first_playable(self, data: dict) -> Optional[dict]:
        """Return the first result (across platforms) that has a stream URL."""
        results = data.get("results") or {}
        for platform in self.platforms:
            block = results.get(platform) or {}
            for item in block.get("results") or []:
                if item.get("stream_url") and not item.get("preview_only"):
                    return item
        return None

    async def search(self, query: str) -> Optional[dict]:
        """Return the first playable result dict for ``query`` or ``None``.

        The returned dict contains at least: ``id``, ``title``, ``artists``,
        ``duration`` (seconds), ``thumbnail``, ``url`` and ``stream_url``.
        """
        if not self.api_key or not self.base or not self.platforms:
            return None

        params = {
            "api_key": self.api_key,
            "platforms": ",".join(self.platforms),
            "q": query,
        }
        endpoint = f"{self.base}/search/all"

        for attempt in range(1, self.retries + 1):
            try:
                session = await self._get_session()
                async with session.get(endpoint, params=params) as resp:
                    data = await resp.json(content_type=None)
                if (
                    resp.status == 200
                    and isinstance(data, dict)
                    and data.get("success")
                ):
                    item = self._first_playable(data)
                    if item is not None:
                        logger.info(
                            f"[{self.name}] PLAY resolved via provider="
                            f"{self.name} url={self.base} "
                            f"platform={','.join(self.platforms)} "
                            f"key={mask_key(self.api_key)} query={query!r} "
                            f"-> title={item.get('title')!r}"
                        )
                    return item
                logger.warning(
                    f"[{self.name}] search({query!r}) HTTP {resp.status} -> "
                    f"{data if isinstance(data, dict) else 'invalid response'}"
                )
                return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning(
                    f"[{self.name}] search({query!r}) attempt "
                    f"{attempt}/{self.retries}: {exc}"
                )
                if attempt < self.retries:
                    await asyncio.sleep(1)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[{self.name}] search({query!r}) error: {exc}")
                return None
        return None
