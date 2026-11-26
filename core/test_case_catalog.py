"""Manual and automated test-case identity and duplicate validation."""

import json
import re
from dataclasses import dataclass
from pathlib import Path


_CASE_PREFIX = re.compile(r"^##\s+Test case:", re.IGNORECASE)
_HEADING = re.compile(r"^\s*#{1,6}\s+")
_CASE_HEADING = re.compile(
    r"^##\s+Test case:\s*(?P<title>.+?)\s+"
    r"\(id:\s*(?P<case_id>[A-Za-z0-9][A-Za-z0-9._-]*),\s*"
    r"tag:\s*[A-Za-z0-9_-]+\)\s*$",
    re.IGNORECASE,
)
_STEP_LINE = re.compile(r"^\s*\d+[.)]\s*(?P<step>.+?)\s*$")


@dataclass(frozen=True)
class ManualTestCase:
    case_id: str
    title: str
    steps: tuple
    source: Path
    line: int


def normalize_title(title):
    """Normalize titles for duplicate detection without relying on punctuation."""
    return " ".join(re.sub(r"[^\w]+", " ", title.casefold()).split())


def load_manual_cases(directory):
    """Parse and validate test-case headings from Markdown files."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"Manual test-case directory not found: {directory}")

    cases = []
    for path in sorted(directory.rglob("*.md")):
        if path.name.casefold() == "readme.md":
            continue
        active_case = None
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines, start=1):
            if not _CASE_PREFIX.match(line):
                if _HEADING.match(line):
                    active_case = None
                    continue
                if active_case is not None:
                    step_match = _STEP_LINE.match(line)
                    if step_match is not None:
                        if re.match(
                            r"^expected(?: result)?:", step_match.group("step"), re.I
                        ):
                            continue
                        active_case["steps"].append(
                            normalize_title(step_match.group("step"))
                        )
                continue
            match = _CASE_HEADING.fullmatch(line)
            if match is None:
                raise ValueError(
                    f"{path}:{line_number}: test-case heading must include "
                    "(id: UNIQUE-ID, tag: smoke)"
                )
            title = match.group("title").strip()
            case_id = match.group("case_id")
            if not title:
                raise ValueError(f"{path}:{line_number}: test-case title is empty")
            active_case = {
                "case_id": case_id,
                "title": title,
                "steps": [],
                "source": path,
                "line": line_number,
            }
            cases.append(active_case)

    parsed_cases = tuple(
        ManualTestCase(
            case["case_id"],
            case["title"],
            tuple(case["steps"]),
            case["source"],
            case["line"],
        )
        for case in cases
    )
    _reject_duplicate_cases(parsed_cases)
    return parsed_cases


def load_normalized_cases(path):
    """Load cases normalized from Markdown, CSV, Excel, or a test management tool."""
    path = Path(path)
    if not path.exists():
        return ()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError(f"{path}: expected a JSON object with a 'cases' list")

    cases = []
    for index, value in enumerate(data["cases"], start=1):
        if not isinstance(value, dict):
            raise ValueError(f"{path}: case entry {index} must be an object")
        if value.get("retired"):
            continue
        case_id = value.get("id")
        title = value.get("title")
        steps = value.get("steps", [])
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{path}: case entry {index} has no valid id")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{path}: case entry {index} has no valid title")
        if not isinstance(steps, list) or not all(
            isinstance(step, str) for step in steps
        ):
            raise ValueError(f"{path}: case entry {index} steps must be strings")
        cases.append(
            ManualTestCase(
                case_id.strip(),
                title.strip(),
                tuple(normalize_title(step) for step in steps if step.strip()),
                path,
                None,
            )
        )

    _reject_duplicate_cases(cases)
    return tuple(cases)


def load_case_catalog(manual_directory, normalized_path):
    """Merge matching Markdown and normalized cases, rejecting conflicting records."""
    manual_cases = list(load_manual_cases(manual_directory))
    normalized_cases = load_normalized_cases(normalized_path)
    by_id = {case.case_id.casefold(): index for index, case in enumerate(manual_cases)}

    for normalized_case in normalized_cases:
        key = normalized_case.case_id.casefold()
        existing_index = by_id.get(key)
        if existing_index is None:
            by_id[key] = len(manual_cases)
            manual_cases.append(normalized_case)
            continue

        existing = manual_cases[existing_index]
        if normalize_title(existing.title) != normalize_title(normalized_case.title):
            raise ValueError(
                f"Conflicting title for case id '{existing.case_id}' in "
                f"{existing.source} and {normalized_case.source}"
            )
        if (
            existing.steps
            and normalized_case.steps
            and existing.steps != normalized_case.steps
        ):
            raise ValueError(
                f"Conflicting steps for case id '{existing.case_id}' in "
                f"{existing.source} and {normalized_case.source}"
            )
        if not existing.steps and normalized_case.steps:
            manual_cases[existing_index] = normalized_case

    _reject_duplicate_cases(manual_cases)
    return tuple(manual_cases)


def _reject_duplicate_cases(cases):
    seen_ids = {}
    seen_titles = {}
    seen_steps = {}
    for case in cases:
        id_key = case.case_id.casefold()
        title_key = normalize_title(case.title)
        if id_key in seen_ids:
            previous = seen_ids[id_key]
            raise ValueError(
                f"Duplicate manual test-case id '{case.case_id}': "
                f"{_location(previous)} and {_location(case)}"
            )
        if title_key in seen_titles:
            previous = seen_titles[title_key]
            raise ValueError(
                f"Duplicate manual test-case title '{case.title}': "
                f"{_location(previous)} and {_location(case)}"
            )
        if case.steps and case.steps in seen_steps:
            previous = seen_steps[case.steps]
            raise ValueError(
                f"Duplicate manual test-case steps for '{case.title}': "
                f"{_location(previous)} and {_location(case)}"
            )
        seen_ids[id_key] = case
        seen_titles[title_key] = case
        if case.steps:
            seen_steps[case.steps] = case


def _location(case):
    return f"{case.source}:{case.line}" if case.line is not None else str(case.source)


def validate_automated_cases(items, manual_cases):
    """Require marked tests to map one-to-one to unique manual cases."""
    manual_by_id = {case.case_id.casefold(): case for case in manual_cases}
    seen_ids = {}
    seen_titles = {}

    for item in items:
        marker = item.get_closest_marker("case")
        if marker is None:
            if item.get_closest_marker("framework") is None:
                raise ValueError(
                    f"{item.nodeid}: add @pytest.mark.case(id=..., title=...) "
                    "or mark infrastructure-only tests with @pytest.mark.framework"
                )
            continue
        case_id = marker.kwargs.get("id")
        title = marker.kwargs.get("title")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{item.nodeid}: @pytest.mark.case requires a non-empty id")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(
                f"{item.nodeid}: @pytest.mark.case requires a non-empty title"
            )

        id_key = case_id.casefold()
        title_key = normalize_title(title)
        manual_case = manual_by_id.get(id_key)
        if manual_case is None:
            raise ValueError(
                f"{item.nodeid}: case id '{case_id}' has no matching manual test case"
            )
        if normalize_title(manual_case.title) != title_key:
            raise ValueError(
                f"{item.nodeid}: automated title '{title}' does not match "
                f"manual title '{manual_case.title}' for id '{case_id}'"
            )
        if id_key in seen_ids:
            raise ValueError(
                f"Duplicate automated test-case id '{case_id}': "
                f"{seen_ids[id_key]} and {item.nodeid}"
            )
        if title_key in seen_titles:
            raise ValueError(
                f"Duplicate automated test-case title '{title}': "
                f"{seen_titles[title_key]} and {item.nodeid}"
            )
        seen_ids[id_key] = item.nodeid
        seen_titles[title_key] = item.nodeid
