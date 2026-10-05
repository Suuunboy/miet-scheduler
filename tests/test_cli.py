from pathlib import Path
from typing import Any

import httpx
import pytest
from ical.calendar_stream import IcsCalendarStream

from miet_scheduler import cli

from .sample import ENTRIES, GROUP, OPTIONAL_ENTRIES

GROUPS = [GROUP, "ТСТ-12", "П-11"]


@pytest.fixture
def site(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> dict[str, Any]:
    """Подменяет сайт МИЭТ: отдаёт список групп и синтетическое расписание."""
    state: dict[str, Any] = {"payload": payload, "requests": []}

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        if request.url.path == "/schedule/groups":
            return httpx.Response(200, json=GROUPS)
        if request.url.path == "/schedule/data":
            return httpx.Response(200, json=state["payload"])
        return httpx.Response(404)

    monkeypatch.setattr(
        cli,
        "create_http_client",
        lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    return state


def _read_events(path: Path) -> list:
    return IcsCalendarStream.calendar_from_ics(path.read_text(encoding="utf-8")).events


def _generate(tmp_path: Path, *args: str) -> list:
    """Запускает CLI для тестовой группы и возвращает события из файла."""
    output = tmp_path / "out.ics"
    assert cli.main(["-g", GROUP, "-o", str(output), *args]) == 0
    return _read_events(output)


def _dates(events: list) -> set[str]:
    return {e.dtstart.date().isoformat() for e in events}


def test_writes_calendar(
    site: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "out.ics"

    assert cli.main(["-g", "тст-11", "-o", str(output)]) == 0

    events = _read_events(output)
    assert events
    assert all(e.color == "gray" for e in events)
    # 04.11.2026 — праздник, занятий в этот день нет.
    assert not any(e.dtstart.date().isoformat() == "2026-11-04" for e in events)

    out = capsys.readouterr().out
    assert f"{GROUP}, Осенний семестр 2026/2027 (01.09.2026–31.12.2026)" in out
    assert f"{len(events)} занятий сохранено в {output}" in out
    assert "Без занятий: 04.11.2026" in out
    assert site["requests"][-1].url.params["group"] == GROUP


def test_default_output_name(
    site: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["-g", GROUP]) == 0
    assert (tmp_path / f"{GROUP}.ics").exists()


def test_no_holidays(site: dict[str, Any], tmp_path: Path) -> None:
    assert "2026-11-04" in _dates(_generate(tmp_path, "--no-holidays"))


def test_skip_dates_and_file(
    site: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skip_file = tmp_path / "skip.txt"
    skip_file.write_text("# каникулы\n2026-12-28..2026-12-31\n", encoding="utf-8")

    days = _dates(
        _generate(
            tmp_path,
            *("--skip-dates", "2026-09-01,2026-09-02"),
            *("--skip-dates", "2026-09-07"),
            *("--skip-file", str(skip_file)),
        )
    )

    skipped = {"2026-09-01", "2026-09-02", "2026-09-07", "2026-12-28", "2026-12-29"}
    assert not days & skipped
    assert "01.09.2026, 02.09.2026, 07.09.2026, 04.11.2026" in capsys.readouterr().out


def test_color_options(site: dict[str, Any], tmp_path: Path) -> None:
    events = _generate(tmp_path, "--color", "Navy", "--color-map", "Лаб=green")

    colors = {e.summary: e.color for e in events}
    assert colors["Физика [Лаб]"] == "green"
    assert colors["Программирование [Лек]"] == "navy"


def test_start_and_end(site: dict[str, Any], tmp_path: Path) -> None:
    dates = _dates(_generate(tmp_path, "--start", "2026-09-07", "--end", "2026-10-31"))

    assert min(dates) >= "2026-09-07"
    assert max(dates) <= "2026-10-31"


PRACTICE = "Практическая подготовка"
MILITARY = "Военная подготовка [Пр]"
MILITARY_BASICS = "[ФТД] Основы военной подготовки [Лек]"


@pytest.fixture
def site_with_optional(site: dict[str, Any]) -> dict[str, Any]:
    site["payload"] = {**site["payload"], "Data": ENTRIES + OPTIONAL_ENTRIES}
    return site


def test_optional_subjects_skipped_by_default(
    site_with_optional: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    summaries = {e.summary for e in _generate(tmp_path)}

    assert PRACTICE not in summaries
    assert MILITARY not in summaries
    assert MILITARY_BASICS in summaries
    out = capsys.readouterr().out
    assert "Не выгружено: Практическая подготовка (добавьте --include-practice)" in out
    assert "Не выгружено: Военная подготовка (добавьте --include-military)" in out


@pytest.mark.parametrize(
    ("flags", "included", "excluded"),
    [
        (["--include-practice"], {PRACTICE}, {MILITARY}),
        (["--include-military"], {MILITARY}, {PRACTICE}),
        (["--include-practice", "--include-military"], {PRACTICE, MILITARY}, set()),
    ],
)
def test_optional_subjects_included_by_flags(
    site_with_optional: dict[str, Any],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    flags: list[str],
    included: set[str],
    excluded: set[str],
) -> None:
    summaries = {e.summary for e in _generate(tmp_path, *flags)}

    assert included <= summaries
    assert not excluded & summaries
    assert capsys.readouterr().out.count("Не выгружено:") == len(excluded)


def test_no_message_when_group_has_no_optional_subjects(
    site: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _generate(tmp_path)
    assert "Не выгружено" not in capsys.readouterr().out


def test_only_optional_subjects(
    site: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    site["payload"] = {**site["payload"], "Data": OPTIONAL_ENTRIES[:2]}

    assert cli.main(["-g", GROUP]) == 1

    err = capsys.readouterr().err
    assert "--include-practice --include-military" in err


def test_list_groups(site: dict[str, Any], capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--list-groups"]) == 0
    assert capsys.readouterr().out.splitlines() == GROUPS


def test_unknown_group(
    site: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["-g", "ТСТ-1"]) == 1
    err = capsys.readouterr().err
    assert "не найдена" in err
    assert GROUP in err


def test_empty_schedule(
    site: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    site["payload"] = {**site["payload"], "Data": []}
    assert cli.main(["-g", GROUP]) == 1
    assert "нет занятий" in capsys.readouterr().err


def test_bad_skip_file_fails_before_network(
    site: dict[str, Any], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    skip_file = tmp_path / "skip.txt"
    skip_file.write_text("не дата\n", encoding="utf-8")

    assert cli.main(["-g", GROUP, "--skip-file", str(skip_file)]) == 1
    assert "строка 1" in capsys.readouterr().err
    assert site["requests"] == []


def test_start_after_end(
    site: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["-g", GROUP, "--start", "2026-12-01", "--end", "2026-11-01"]) == 1
    assert "позже" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["-g", GROUP, "--list-groups"],
        ["-g", GROUP, "--color", "#ff0000"],
        ["-g", GROUP, "--color-map", "Лаб"],
        ["-g", GROUP, "--start", "01.09.2026"],
        ["-g", GROUP, "--skip-dates", "2026-12-31..2026-12-01"],
    ],
)
def test_invalid_arguments(args: list[str]) -> None:
    with pytest.raises(SystemExit) as info:
        cli.main(args)
    assert info.value.code == 2
