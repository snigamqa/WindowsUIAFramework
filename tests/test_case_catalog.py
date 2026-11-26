from types import SimpleNamespace
import json

import pytest

from core.test_case_catalog import (
    load_case_catalog,
    load_manual_cases,
    validate_automated_cases,
)

pytestmark = pytest.mark.framework


def _write_cases(directory, *headings):
    directory.mkdir()
    (directory / "cases.md").write_text(
        "\n".join(headings), encoding="utf-8"
    )


def _automated_item(nodeid, case_id, title):
    marker = SimpleNamespace(kwargs={"id": case_id, "title": title})
    return SimpleNamespace(
        nodeid=nodeid,
        get_closest_marker=lambda name: marker if name == "case" else None,
    )


@pytest.mark.parametrize(
    ("headings", "message"),
    [
        (
            (
                "## Test case: First flow (id: APP-001, tag: smoke)",
                "## Test case: Second flow (id: app-001, tag: smoke)",
            ),
            "Duplicate manual test-case id",
        ),
        (
            (
                "## Test case: Save connection (id: APP-001, tag: smoke)",
                "## Test case: Save-connection! (id: APP-002, tag: smoke)",
            ),
            "Duplicate manual test-case title",
        ),
        (
            (
                "## Test case: Save the profile (id: APP-001, tag: smoke)\n"
                "1. Open settings\n2. Save the profile",
                "## Test case: Store the profile (id: APP-002, tag: smoke)\n"
                "1. Open settings!\n2. Save the profile.",
            ),
            "Duplicate manual test-case steps",
        ),
    ],
)
def test_manual_case_catalog_rejects_duplicates(tmp_path, headings, message):
    _write_cases(tmp_path / "testcases", *headings)

    with pytest.raises(ValueError, match=message):
        load_manual_cases(tmp_path / "testcases")


def test_automated_cases_must_uniquely_match_manual_case(tmp_path):
    testcases = tmp_path / "testcases"
    _write_cases(
        testcases,
        "## Test case: Opening the main window (id: APP-001, tag: smoke)",
    )
    manual_cases = load_manual_cases(testcases)
    items = [
        _automated_item("tests/test_app.py::test_open", "APP-001", "Opening the main window"),
        _automated_item("tests/test_other.py::test_open", "APP-001", "Opening the main window"),
    ]

    with pytest.raises(ValueError, match="Duplicate automated test-case id"):
        validate_automated_cases(items, manual_cases)


def test_automated_case_title_must_match_manual_case(tmp_path):
    testcases = tmp_path / "testcases"
    _write_cases(
        testcases,
        "## Test case: Opening the main window (id: APP-001, tag: smoke)",
    )
    manual_cases = load_manual_cases(testcases)

    with pytest.raises(ValueError, match="does not match manual title"):
        validate_automated_cases(
            [_automated_item("tests/test_app.py::test_open", "APP-001", "Opening app")],
            manual_cases,
        )


def test_automated_test_requires_manual_case_metadata(tmp_path):
    testcases = tmp_path / "testcases"
    _write_cases(
        testcases,
        "## Test case: Opening the main window (id: APP-001, tag: smoke)",
    )
    manual_cases = load_manual_cases(testcases)
    item = SimpleNamespace(
        nodeid="tests/test_app.py::test_open",
        get_closest_marker=lambda name: None,
    )

    with pytest.raises(ValueError, match="add @pytest.mark.case"):
        validate_automated_cases([item], manual_cases)


def test_normalized_json_case_links_to_same_manual_case(tmp_path):
    testcases = tmp_path / "testcases"
    _write_cases(
        testcases,
        "## Test case: Opening the main window (id: APP-001, tag: smoke)\n"
        "1. Launch the application\n2. Confirm its main window is visible",
    )
    normalized_path = tmp_path / "cases" / "test-cases.json"
    normalized_path.parent.mkdir()
    normalized_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "id": "APP-001",
                        "title": "Opening the main window",
                        "steps": [
                            "Launch the application",
                            "Confirm its main window is visible",
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    cases = load_case_catalog(testcases, normalized_path)

    assert len(cases) == 1
    validate_automated_cases(
        [_automated_item("tests/test_app.py::test_open", "APP-001", "Opening the main window")],
        cases,
    )


def test_normalized_json_conflict_with_manual_case_is_rejected(tmp_path):
    testcases = tmp_path / "testcases"
    _write_cases(
        testcases,
        "## Test case: Opening the main window (id: APP-001, tag: smoke)",
    )
    normalized_path = tmp_path / "test-cases.json"
    normalized_path.write_text(
        json.dumps(
            {"cases": [{"id": "APP-001", "title": "Closing the main window", "steps": []}]}
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Conflicting title"):
        load_case_catalog(testcases, normalized_path)
