#!/usr/bin/env python3
"""Normalize manual test cases from Excel, CSV or TestRail into cases/test-cases.json.

Examples:
    python normalize_cases.py --excel cases.xlsx --out cases/test-cases.json
    python normalize_cases.py --csv cases.csv --out cases/test-cases.json
    python normalize_cases.py --testrail-url https://x.testrail.io --project 1 --suite 2 \
        --out cases/test-cases.json        # needs TESTRAIL_USER and TESTRAIL_API_KEY env vars

Optionally link cases to an app model (--model model/app-model.json): step text is matched
to control names to fill screen_id and control_ids. Unmatched cases stay unlinked.
"""
import argparse
import base64
import csv
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
import urllib.request

ALIASES = {
    "source_id": ["id", "case id", "test case id", "tc id", "testcase id", "case_id", "#"],
    "title": ["title", "test case", "test case name", "name", "summary", "scenario", "test scenario"],
    "preconditions": ["preconditions", "precondition", "pre-conditions", "prerequisites", "setup"],
    "steps": ["steps", "test steps", "step", "procedure", "actions", "description"],
    "expected": ["expected", "expected result", "expected results", "expected outcome", "result"],
    "priority": ["priority", "severity"],
    "platform": ["platform", "type of app", "application", "app type", "module", "area"],
    "oracle": ["oracle", "oracle type", "expectation source"],
}
ORACLES = {"spec", "observed", "inferred"}
MARKDOWN_CASE = re.compile(
    r"^##\s+Test case:\s*(?P<title>.+?)\s+"
    r"\(id:\s*(?P<id>[A-Za-z0-9][A-Za-z0-9._-]*),\s*"
    r"tag:\s*(?P<tag>[A-Za-z0-9_-]+)\)\s*$",
    re.IGNORECASE,
)
MARKDOWN_STEP = re.compile(r"^\s*\d+[.)]\s*(?P<step>.+?)\s*$")


def norm_header(h):
    return re.sub(r"\s+", " ", str(h or "").strip().lower())


def map_headers(headers):
    mapping = {}
    for field, names in ALIASES.items():
        for i, h in enumerate(headers):
            if norm_header(h) in names and i not in mapping.values():
                mapping[field] = i
                break
    return mapping


def split_steps(text):
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"\r?\n+|(?<=\.)\s+(?=\d+[.)]\s)", text) if p.strip()]
    return [re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", p) for p in parts]


def prio(value):
    v = str(value or "").strip().lower()
    if any(k in v for k in ("high", "critical", "p1", "1", "blocker")):
        return "high"
    if any(k in v for k in ("low", "p3", "3", "minor", "trivial")):
        return "low"
    return "medium"


def normalized_text(value):
    return " ".join(re.sub(r"[^\w]+", " ", str(value or "").casefold()).split())


def validate_case_duplicates(cases):
    seen_sources, seen_titles, seen_steps = {}, {}, {}
    for index, case in enumerate(cases, start=1):
        source_id = str(case.get("source_id") or "").strip().casefold()
        title = normalized_text(case.get("title"))
        steps = tuple(
            normalized_text(step)
            for step in case.get("steps", [])
            if normalized_text(step)
        )
        if source_id and source_id in seen_sources:
            raise ValueError(
                "Duplicate source case ID '%s' in imported cases %d and %d"
                % (case["source_id"], seen_sources[source_id], index)
            )
        if title and title in seen_titles:
            raise ValueError(
                "Duplicate normalized test title '%s' in imported cases %d and %d"
                % (case["title"], seen_titles[title], index)
            )
        if steps and steps in seen_steps:
            raise ValueError(
                "Duplicate normalized test steps in imported cases %d and %d"
                % (seen_steps[steps], index)
            )
        if source_id:
            seen_sources[source_id] = index
        if title:
            seen_titles[title] = index
        if steps:
            seen_steps[steps] = index


def rows_from_excel(path):
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError(
            "Excel import requires openpyxl; install it with "
            "'python -m pip install openpyxl'"
        ) from exc
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if rows:
            yield ws.title, rows[0], rows[1:]


def rows_from_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if rows:
        yield os.path.basename(path), rows[0], rows[1:]


def rows_from_markdown(path):
    """Read the project's structured manual-case headings and numbered steps."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Manual case path not found: {path}")
    files = [path] if path.is_file() else sorted(path.rglob("*.md"))
    for file_path in files:
        if file_path.name.casefold() == "readme.md":
            continue
        active = None
        for line_number, line in enumerate(
            file_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = MARKDOWN_CASE.fullmatch(line)
            if match:
                if active is not None:
                    yield active
                active = {
                    "id": match.group("id"),
                    "source_id": match.group("id"),
                    "title": match.group("title").strip(),
                    "steps": [],
                    "expected": "",
                    "oracle": "inferred",
                    "_source": "manual",
                    "_file": str(file_path),
                    "_line": line_number,
                }
                continue
            if line.lstrip().startswith("#"):
                if active is not None:
                    yield active
                    active = None
                if line.lstrip().lower().startswith("## test case:"):
                    raise ValueError(
                        f"{file_path}:{line_number}: malformed test-case heading"
                    )
                continue
            if active is None:
                continue
            oracle_match = re.match(
                r"^\s*[-*]\s*Oracle:\s*(?P<oracle>\w+)\s*$", line, re.I
            )
            if oracle_match:
                active["oracle"] = oracle_match.group("oracle").casefold()
                continue
            step_match = MARKDOWN_STEP.match(line)
            if step_match is None:
                continue
            step = step_match.group("step").strip()
            expected_match = re.match(r"^expected(?: result)?:\s*(.+)$", step, re.I)
            if expected_match:
                active["expected"] = expected_match.group(1).strip()
            else:
                active["steps"].append(step)
        if active is not None:
            yield active


def fetch_testrail(url, project, suite):
    parsed_url = urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        sys.exit("TestRail URL must be an absolute HTTPS URL.")
    user, key = os.environ.get("TESTRAIL_USER"), os.environ.get("TESTRAIL_API_KEY")
    if not user or not key:
        sys.exit("Set TESTRAIL_USER and TESTRAIL_API_KEY environment variables.")
    token = base64.b64encode(("%s:%s" % (user, key)).encode()).decode()
    cases, offset = [], 0
    while True:
        endpoint = "%s/index.php?/api/v2/get_cases/%s&suite_id=%s&limit=250&offset=%d" % (
            url.rstrip("/"), project, suite, offset)
        req = urllib.request.Request(endpoint, headers={
            "Authorization": "Basic " + token, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        batch = data["cases"] if isinstance(data, dict) else data
        cases.extend(batch)
        if len(batch) < 250:
            break
        offset += 250
    out = []
    for c in cases:
        steps, expected = [], []
        for s in c.get("custom_steps_separated") or []:
            steps.append(s.get("content", ""))
            if s.get("expected"):
                expected.append(s["expected"])
        if not steps:
            steps = split_steps(c.get("custom_steps") or "")
        out.append({
            "source_id": "C%s" % c["id"], "title": c.get("title", ""),
            "preconditions": c.get("custom_preconds") or "",
            "steps": steps,
            "expected": "\n".join(expected) or (c.get("custom_expected") or ""),
            "priority": prio(c.get("priority_id") and {1: "low", 2: "medium", 3: "high", 4: "high"}.get(c["priority_id"], "medium")),
            "platform": "",
        })
    return out


def build_cases(raw_rows):
    cases, skipped = [], []
    for n, r in enumerate(raw_rows, start=1):
        if not r.get("title") and not r.get("steps"):
            skipped.append({"row": n, "reason": "no title or steps"})
            continue
        oracle = str(r.get("oracle") or "inferred").strip().casefold()
        if oracle not in ORACLES:
            raise ValueError(
                "Case %d has invalid oracle '%s'; expected one of %s"
                % (n, oracle, ", ".join(sorted(ORACLES)))
            )
        raw_steps = r.get("steps") or ""
        steps = (
            raw_steps
            if isinstance(raw_steps, list)
            else split_steps(str(raw_steps))
        )
        cases.append({
            "id": str(r.get("id") or "TC-IMP-%04d" % n).strip(),
            "title": str(r.get("title") or (steps[0] if steps else "")).strip(),
            "category": "functional",
            "priority": prio(r.get("priority")),
            "screen_id": None, "control_ids": [],
            "preconditions": str(r.get("preconditions") or "").strip(),
            "steps": steps,
            "expected": str(r.get("expected") or "").strip(),
            "oracle": oracle,
            "automation": "later" if (not steps or not r.get("expected")) else "now",
            "source": str(r.get("_source") or "imported"),
            "source_id": str(r.get("source_id") or "").strip() or None,
            "platform": str(r.get("platform") or "").strip(),
            "notes": (
                ""
                if steps and r.get("expected")
                else "missing steps or expected result; needs rewrite before automation"
            ),
        })
    validate_case_duplicates(cases)
    return cases, skipped


def link_to_model(cases, model):
    index = []
    for s in model.get("screens", []):
        for c in s.get("controls", []):
            if c.get("interactive") and c.get("name") and len(c["name"]) > 2:
                index.append((c["name"].lower(), s["id"], c["id"]))
    for case in cases:
        text = " ".join(case["steps"] + [case["title"], case["expected"]]).lower()
        hits = [(sid, cid) for name, sid, cid in index if name in text]
        if hits:
            case["control_ids"] = sorted({cid for _, cid in hits})
            screens = [sid for sid, _ in hits]
            case["screen_id"] = max(set(screens), key=screens.count)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument("--excel")
    source.add_argument("--csv")
    source.add_argument("--markdown")
    source.add_argument("--testrail-url")
    ap.add_argument("--project")
    ap.add_argument("--suite")
    ap.add_argument("--model", help="app-model.json to link cases to controls")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    raw = []
    if args.testrail_url:
        if not (args.project and args.suite):
            sys.exit("--project and --suite are required with --testrail-url")
        raw = fetch_testrail(args.testrail_url, args.project, args.suite)
    elif args.markdown:
        raw = list(rows_from_markdown(args.markdown))
    else:
        sources = rows_from_excel(args.excel) if args.excel else rows_from_csv(args.csv)
        for sheet, headers, rows in sources:
            mapping = map_headers(headers)
            if "title" not in mapping and "steps" not in mapping:
                print("Skipping sheet '%s': no recognizable title or steps column. Headers: %s" % (sheet, headers))
                continue
            for row in rows:
                if not any(row):
                    continue
                item = {f: (row[i] if i < len(row) else None) for f, i in mapping.items()}
                item["_sheet"] = sheet
                raw.append(item)

    cases, skipped = build_cases(raw)
    if args.model:
        if not os.path.isfile(args.model):
            ap.error("app model not found: %s" % args.model)
        with open(args.model, encoding="utf-8") as f:
            link_to_model(cases, json.load(f))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"cases": cases, "skipped_rows": skipped}, f, indent=2, ensure_ascii=False)
    unlinked = sum(1 for c in cases if not c["control_ids"])
    needs_rewrite = sum(1 for c in cases if c["notes"])
    print("Wrote %s: %d cases (%d skipped rows, %d unlinked to controls, %d need rewrite)"
          % (args.out, len(cases), len(skipped), unlinked, needs_rewrite))


if __name__ == "__main__":
    main()
