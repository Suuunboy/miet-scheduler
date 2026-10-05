import asyncio
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from miet_scheduler.api import MietApiError, MietClient, UnknownGroupError

GROUPS = ["П-11", "П-12", "П-21", "ИВТ-11"]

Handler = Callable[[httpx.Request], httpx.Response]


def _call(handler: Handler, method: str, *args: Any) -> Any:
    async def run() -> Any:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http:
            return await getattr(MietClient(http), method)(*args)

    return asyncio.run(run())


def _groups_handler(request: httpx.Request) -> httpx.Response:
    assert request.method == "POST"
    assert request.url.path == "/schedule/groups"
    return httpx.Response(200, json=GROUPS)


def test_groups() -> None:
    assert _call(_groups_handler, "groups") == GROUPS


def test_schedule_passes_group_as_query_param(payload: dict[str, Any]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/schedule/data"
        assert request.url.params["group"] == "П-11"
        return httpx.Response(200, json=payload)

    assert _call(handler, "schedule", "П-11") == payload


@pytest.mark.parametrize("name", ["П-11", "п-11", "  п-11 "])
def test_resolve_group_is_case_insensitive(name: str) -> None:
    assert _call(_groups_handler, "resolve_group", name) == "П-11"


def test_resolve_unknown_group_suggests_similar() -> None:
    with pytest.raises(UnknownGroupError) as info:
        _call(_groups_handler, "resolve_group", "п-1")

    assert set(info.value.suggestions) <= set(GROUPS)
    assert "П-11" in info.value.suggestions
    assert "П-11" in str(info.value)


def test_resolve_unknown_group_without_suggestions() -> None:
    with pytest.raises(UnknownGroupError) as info:
        _call(_groups_handler, "resolve_group", "Совсем другое")
    assert info.value.suggestions == []


def test_http_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(MietApiError, match="503"):
        _call(handler, "groups")


def test_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(MietApiError, match="подключиться"):
        _call(handler, "groups")


def test_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>не JSON</html>")

    with pytest.raises(MietApiError, match="JSON"):
        _call(handler, "groups")


@pytest.mark.parametrize("body", [{"Data": []}, [], {"Semestr": "x"}])
def test_unexpected_schedule_format(body: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(MietApiError, match="формат"):
        _call(handler, "schedule", "П-11")
