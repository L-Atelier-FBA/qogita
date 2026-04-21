from typing import Optional
import os
import asyncio
from curl_cffi.requests import AsyncSession
from .logger import get_logger

logger = get_logger("Requester")


class Requester:
    def __init__(
        self,
        url: str,
        referrer: Optional[str] = None,
        cookie: Optional[str] = None,
        api: Optional[bool] = False,
        timeout: int = 10,
    ):
        self.url = url
        self.session: Optional[AsyncSession] = None

        self.headers = {
            "Accept": "application/json" if api else "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9"
        }

        if cookie:
            self.headers["Cookie"] = cookie
        if referrer:
            self.headers["Referer"] = referrer

        self.proxy = os.getenv("PROXY")
        self.timeout = timeout

    async def __aenter__(self):
        params = {"timeout": self.timeout, "allow_redirects": True, "http_version": "v2"}
        self.session = AsyncSession(
            impersonate="chrome142",
            **params
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    async def fetch_get(self, retries: int = 3, delay: float = 1.0):
        session = self.session
        if session is None:
            raise RuntimeError("Requester session not initialized.")
        for attempt in range(retries):
            try:
                response = await session.get(
                    self.url,
                    proxy=self.proxy,
                    headers=self.headers,
                )
                if response:
                    return response
            except Exception as e:
                logger.warning(str(e))

            await asyncio.sleep(delay * (attempt + 1))

        return None

    async def fetch_post(self, data: dict, retries: int = 3, delay: float = 1.0):
        session = self.session
        if session is None:
            raise RuntimeError("Requester session not initialized.")
        for attempt in range(retries):
            try:
                response = await session.post(
                    self.url,
                    json=data,
                    proxy=self.proxy,
                    headers=self.headers,
                )
                if response:
                    return response
            except Exception as e:
                logger.warning(str(e))

            await asyncio.sleep(delay * (attempt + 1))

        return None