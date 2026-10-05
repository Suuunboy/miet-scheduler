from dataclasses import dataclass, field
from fetcher_abc import Fetcher
from typing import Dict, Any
import httpx
import asyncio

@dataclass
class MietScheduleFetcher(Fetcher):
    group: str
    url: str = "https://www.miet.ru/schedule/data"
    schedule: dict[str, Any] = field(default_factory=dict)

    async def fetch(self) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.url, params={"group": self.group})
            response.raise_for_status()
            self.schedule = response.json()
            return {"schedule": self.schedule}