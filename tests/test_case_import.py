import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.test_case_catalog import load_case_catalog, validate_automated_cases

pytestmark = pytest.mark.framework

_SCRIPT = (
    Path(__file__).parents[1]
    / ".claude"
    / "skills"
    / "windows-desktop-e2e"
    / "scripts"
    / "normalize_cases.py"
)
_SPEC = importlib.util.spec_from_file_location("normalize_cases", _SCRIPT)
normalize_cases = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(normalize_cases)

_REPORT_SCRIPT = _SCRIPT.with_name("build_report.py")
_REPORT_SPEC = importlib.util.spec_from_file_location("build_report", _REPORT_SCRIPT)
build_report = importlib.util.module_from_spec(_REPORT_SPEC)
_REPORT_SPEC.loader.exec_module(build_report)


def test_case_import_rejects_duplicate_source_ids():
    rows = [
        {
            "source_id": "C123",
            "title": "Open settings",
            "steps": ["Open settings"],
            "expected": "Settings open",
        },
        {
            "source_id": "c123",
            "title": "Close settings",
            "steps": ["Close settings"],
            "expected": "Settings close",
        },
    ]

    with pytest.raises(ValueError, match="Duplicate source case ID"):
        normalize_cases.build_cases(rows)


def test_case_import_rejects_normalized_duplicate_steps():
    rows = [
        {
            "source_id": "C123",
            "title": "Open profile settings",
            "steps": ["Open settings", "Select profile"],
            "expected": "Profile settings are shown",
        },
        {
            "source_id": "C124",
            "title": "Open account settings",
            "steps": ["Open settings!", "Select profile."],
            "expected": "Account settings are shown",
        },
    ]

    with pytest.raises(ValueError, match="Duplicate normalized test steps"):
        normalize_cases.build_cases(rows)


def test_testrail_import_rejects_non_https_before_network_access():
    with pytest.raises(SystemExit, match="absolute HTTPS URL"):
        normalize_cases.fetch_testrail("http://testrail.invalid", 1, 1)


def test_markdown_import_preserves_manual_case_identity(tmp_path):
    markdown_path = tmp_path / "cases.md"
    markdown_path.write_text(
        "## Test case: Opening the app (id: APP-001, tag: smoke)\n"
        "1. Launch the application\n"
        "2. Expected: main window is visible\n",
        encoding="utf-8",
    )
    rows = list(normalize_cases.rows_from_markdown(markdown_path))
    cases, _ = normalize_cases.build_cases(rows)
    testcases_dir = tmp_path / "testcases"
    testcases_dir.mkdir()
    (testcases_dir / "cases.md").write_text(
        markdown_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    normalized_path = tmp_path / "test-cases.json"
    normalized_path.write_text(json.dumps({"cases": cases}), encoding="utf-8")

    catalog = load_case_catalog(testcases_dir, normalized_path)

    assert len(catalog) == 1
    assert cases[0]["oracle"] == "inferred"
    assert cases[0]["notes"] == ""
    item = SimpleNamespace(
        nodeid="tests/test_app.py::test_open",
        get_closest_marker=lambda name: SimpleNamespace(
            kwargs={"id": "APP-001", "title": "Opening the app"}
        )
        if name == "case"
        else None,
    )
    validate_automated_cases([item], catalog)


def test_case_import_rejects_unknown_oracle():
    with pytest.raises(ValueError, match="invalid oracle"):
        normalize_cases.build_cases(
            [
                {
                    "title": "Open settings",
                    "steps": ["Open settings"],
                    "expected": "Settings open",
                    "oracle": "guess",
                }
            ]
        )


def test_case_import_handles_missing_steps_column():
    cases, _ = normalize_cases.build_cases(
        [{"title": "Open settings", "expected": "Settings are visible"}]
    )

    assert cases[0]["steps"] == []
    assert cases[0]["automation"] == "later"


def test_markdown_import_preserves_explicit_oracle(tmp_path):
    markdown_path = tmp_path / "cases.md"
    markdown_path.write_text(
        "## Test case: Opening the app (id: APP-001, tag: smoke)\n"
        "- Oracle: spec\n"
        "1. Launch the application\n"
        "2. Expected: main window is visible\n",
        encoding="utf-8",
    )

    cases, _ = normalize_cases.build_cases(
        normalize_cases.rows_from_markdown(markdown_path)
    )

    assert cases[0]["oracle"] == "spec"


def test_report_marks_case_missing_from_repeat_as_incomplete():
    results = build_report.merge_runs(
        [
            {"APP-001": ("passed", "tests/test_app.py::test_open", "")},
            {},
        ]
    )

    assert results["APP-001"]["status"] == "incomplete"
    assert results["APP-001"]["runs"] == ["passed", "not run"]
