from datetime import date

import pytest

from screening.periods import duration_months, find_periods

TODAY = date(2026, 6, 15)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("2019–2024 Senior Engineer", [("2019–2024", "2019", "2024", False)]),
        ("2016-2019  Developer, Grupo Andino", [("2016-2019", "2016", "2019", False)]),
        ("2018 - present", [("2018 - present", "2018", None, True)]),
        ("Backend Engineer (Jan 2020 - Present)", [("Jan 2020 - Present", "2020-01", None, True)]),
        ("ene 2020 – actual", [("ene 2020 – actual", "2020-01", None, True)]),
        ("Sept. 2019 – Feb 2021", [("Sept. 2019 – Feb 2021", "2019-09", "2021-02", False)]),
        (
            "Agosto 2016 – Diciembre 2019",
            [("Agosto 2016 – Diciembre 2019", "2016-08", "2019-12", False)],
        ),
        ("marzo de 2018 a la fecha", [("marzo de 2018 a la fecha", "2018-03", None, True)]),
        ("01/2020 - 12/2023 Analista", [("01/2020 - 12/2023", "2020-01", "2023-12", False)]),
        ("de 2015 a 2017, en Monterrey", [("de 2015 a 2017", "2015", "2017", False)]),
        ("from 2012 to 2014", [("from 2012 to 2014", "2012", "2014", False)]),
        ("Opero los clústeres desde 2022.", [("desde 2022", "2022", None, True)]),
        ("Since March 2021 leading the team", [("Since March 2021", "2021-03", None, True)]),
        (
            "2014 - 2016 y 2018 - 2020",
            [("2014 - 2016", "2014", "2016", False), ("2018 - 2020", "2018", "2020", False)],
        ),
    ],
)  # fmt: skip
def test_date_ranges_in_spanish_and_english(line, expected):
    found = [(p.text, p.start, p.end, p.ongoing) for p in find_periods(line, TODAY)]

    assert found == expected


@pytest.mark.parametrize(
    "line",
    [
        "Python 3.12 and PostgreSQL 15",
        "Tel. 81-1234-5678",
        "3,000 orders a minute",
        "Speaker at PyCon US 2025",  # one year is a date, not a range
        "2024 – 2019",  # ends before it starts
        "1850 - 1860",
        "2019 - 2031",  # the future
    ],
)
def test_what_is_not_a_date_range(line):
    assert find_periods(line, TODAY) == []


@pytest.mark.parametrize(
    ("period", "months"),
    [
        ({"start": "2019", "end": "2024", "ongoing": False}, 60),
        ({"start": "2020-01", "end": "2023-12", "ongoing": False}, 48),
        ({"start": "2025-01", "end": None, "ongoing": True}, 18),
        ({"start": "2024", "end": None, "ongoing": True}, 24),
        ({"start": "2026", "end": "2026", "ongoing": False}, 1),
    ],
)
def test_how_long_a_period_lasted(period, months):
    assert duration_months(period, TODAY) == months
