"""Stable ASGI test client helpers for the backend test suite."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import Any, Iterator

import anyio.to_thread
import httpx


async def _run_sync_inline(
    func,
    *args,
    abandon_on_cancel: bool = False,
    cancellable: bool | None = None,
    limiter: object | None = None,
):
    """Run sync FastAPI endpoints inline during ASGITransport tests."""
    return func(*args)


class ApiTestClient:
    """Small synchronous wrapper around httpx ASGITransport.

    The installed Starlette TestClient can hang in this environment. This helper
    keeps tests close to the existing client.get/post/delete shape while using
    httpx's ASGI transport directly.
    """

    def __init__(self, app) -> None:
        self._app = app

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        original_run_sync = anyio.to_thread.run_sync
        anyio.to_thread.run_sync = _run_sync_inline
        try:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.request(method, url, **kwargs)
                await response.aread()
                return response
        finally:
            anyio.to_thread.run_sync = original_run_sync

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return asyncio.run(self._request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("OPTIONS", url, **kwargs)

    @contextmanager
    def stream(self, method: str, url: str, **kwargs: Any) -> Iterator[httpx.Response]:
        yield self.request(method, url, **kwargs)
