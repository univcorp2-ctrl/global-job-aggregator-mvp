from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import Settings
from app.models import NormalizedJob


class Connector(ABC):
    name: str

    @abstractmethod
    async def collect(self, client: httpx.AsyncClient, settings: Settings) -> list[NormalizedJob]:
        raise NotImplementedError


async def request_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 2,
) -> dict[str, Any]:
    for attempt in range(retries + 1):
        response = await client.get(url, params=params, headers=headers)
        if response.status_code in {429, 500, 502, 503, 504} and attempt < retries:
            await asyncio.sleep(2**attempt)
            continue
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"items": data}
    return {}


def default_headers(settings: Settings) -> dict[str, str]:
    return {
        "User-Agent": settings.user_agent,
        "Accept": "application/json",
    }


async def polite_sleep(settings: Settings) -> None:
    if settings.request_delay_seconds > 0:
        await asyncio.sleep(settings.request_delay_seconds)
