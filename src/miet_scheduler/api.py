"""Клиент открытого API расписания miet.ru."""

import difflib
from typing import Any

import httpx

BASE_URL = "https://www.miet.ru/schedule"
TIMEOUT = 15.0


class MietApiError(Exception):
    pass


class UnknownGroupError(MietApiError):
    def __init__(self, group: str, suggestions: list[str]) -> None:
        message = f"Группа {group!r} не найдена"
        if suggestions:
            message += f". Возможно, имелось в виду: {', '.join(suggestions)}"
        super().__init__(message)
        self.suggestions = suggestions


class MietClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def groups(self) -> list[str]:
        """Список всех групп."""
        data = await self._request("POST", "/groups")
        if not isinstance(data, list):
            raise MietApiError("Неожиданный формат списка групп")
        return [str(g) for g in data]

    async def schedule(self, group: str) -> dict[str, Any]:
        """Сырое расписание группы: {"Times": [...], "Data": [...], "Semestr": "..."}."""
        data = await self._request("GET", "/data", params={"group": group})
        if not isinstance(data, dict) or "Data" not in data or "Semestr" not in data:
            raise MietApiError("Неожиданный формат расписания")
        return data

    async def resolve_group(self, group: str) -> str:
        """Возвращает название группы так, как оно записано на сайте.

        Сайт на несуществующую группу отвечает пустым расписанием, поэтому группу
        проверяем по списку заранее.
        """
        by_folded = {name.casefold(): name for name in await self.groups()}
        normalized = group.strip().casefold()
        if normalized in by_folded:
            return by_folded[normalized]
        matches = difflib.get_close_matches(
            normalized, list(by_folded), n=5, cutoff=0.6
        )
        raise UnknownGroupError(group, [by_folded[m] for m in matches])

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, BASE_URL + path, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise MietApiError(
                f"Сайт МИЭТ ответил ошибкой {e.response.status_code} на {path}"
            ) from e
        except httpx.HTTPError as e:
            raise MietApiError(f"Не удалось подключиться к сайту МИЭТ: {e}") from e
        except ValueError as e:
            raise MietApiError(f"Сайт МИЭТ вернул некорректный JSON на {path}") from e


def create_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True)
