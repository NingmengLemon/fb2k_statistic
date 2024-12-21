from collections.abc import Mapping
import logging
from typing import Unpack

from yarl import URL
import aiohttp
from .asyncsse import parse_sse_message

from .models import (
    GetPlayerResponse,
    GetPlaylistItemsResponse,
    GetPlaylistsResponse,
    QueryParams,
    QueryResponse,
)

logger = logging.getLogger(__name__)


class BeefwebClientBase:
    def __init__(
        self,
        root: str | URL = "http://127.0.0.1:8880/api",
        *,
        username: str | None = None,
        password: str | None = None,
        total_timeout: float | None = None,
    ):
        self._root = URL(root)
        self._auth = (
            aiohttp.BasicAuth(login=username, password=password, encoding="utf-8")
            if username and password
            else None
        )
        self._timeout = aiohttp.ClientTimeout(total=total_timeout)
        self._session = aiohttp.ClientSession(auth=self._auth, timeout=self._timeout)
        self._sse_ok_codes = [200, 301, 307]

    async def close(self):
        await self._session.close()

    async def _sse(self, path: str, **kwargs: Unpack[aiohttp.client._RequestOptions]):
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "Connection": "keep-alive",
                "Cache-Control": "no-cache",
                "Accept": "text/event-stream",
            }
        )
        kwargs["headers"] = headers
        # handle boolean
        params = kwargs.get("params", None)
        if params and isinstance(params, Mapping):
            params = {
                k: (str(v).lower() if isinstance(v, bool) else v)
                for k, v in params.items()
            }
            kwargs["params"] = params
        try:
            async with self._session.get(self._root / path, **kwargs) as resp:
                if resp.status not in self._sse_ok_codes:
                    raise aiohttp.ClientError(
                        f"Unexpected status code in SSE request: {resp.status}"
                    )
                async for line in resp.content:
                    yield parse_sse_message(line.decode("utf-8"))
        except aiohttp.ClientError:
            pass

    async def __request(
        self, method: str, path: str, **kwargs: Unpack[aiohttp.client._RequestOptions]
    ):
        async with self._session.request(method, self._root / path, **kwargs) as resp:
            resp.raise_for_status()
            return await resp.read()

    async def _get(self, path: str, **kwargs: Unpack[aiohttp.client._RequestOptions]):
        return await self.__request("get", path, **kwargs)

    async def _post(self, path: str, **kwargs: Unpack[aiohttp.client._RequestOptions]):
        return await self.__request("post", path, **kwargs)


class BeefwebClient(BeefwebClientBase):
    async def get_player(self, columns: str):
        return GetPlayerResponse.model_validate_json(
            await self._get("player", params={"columns": columns})
        )

    async def query(self, **params: Unpack[QueryParams]):
        return QueryResponse.model_validate_json(
            await self._get("query", params=params),
        )

    async def query_updates(self, **params: Unpack[QueryParams]):
        async for event in self._sse("query/updates", params=params):
            if event.event == "message" and event.data:
                yield QueryResponse.model_validate_json(event.data)

    async def toggle_pause_state(self):
        await self._post("player/pause/toggle")

    async def get_playlists(self):
        return GetPlaylistsResponse.model_validate_json(
            await self._get("playlists"),
        )

    async def get_playlist_items(self, playlist_id: str, range: str, columns: str):
        return GetPlaylistItemsResponse.model_validate_json(
            await self._get(
                (URL("playlists") / playlist_id / "items" / range).path,
                params={"columns": columns},
            )
        )
