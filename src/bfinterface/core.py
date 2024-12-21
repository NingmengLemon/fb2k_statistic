import json
from typing import Unpack

from yarl import URL
import aiohttp
from .asyncsse import parse_sse_message

from .models import QueryBody


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

        params = kwargs.pop("params")
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
            data = await resp.read()
            try:
                return json.loads(data) if data else None
            except json.JSONDecodeError:
                return data.decode("utf-8")

    async def _get(self, path: str, **kwargs: Unpack[aiohttp.client._RequestOptions]):
        return await self.__request("get", path, **kwargs)

    async def _post(self, path: str, **kwargs: Unpack[aiohttp.client._RequestOptions]):
        return await self.__request("post", path, **kwargs)


class BeefwebClient(BeefwebClientBase):
    pass
