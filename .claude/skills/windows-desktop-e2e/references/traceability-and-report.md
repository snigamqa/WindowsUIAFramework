# Traceability schema and report contents

## ID scheme

| Artifact | Pattern | Example |
|---|---|---|
| Screen | `SCR-###` | `SCR-003` |
| Control | `CTL-<screen>-##` | `CTL-003-07` |
| Test case | `TC-<SCRnnn>-###` for explored cases | `TC-SCR003-004` |
| Imported case | Markdown keeps its stable ID; CSV/Excel/TestRail use a generated `TC-IMP-` ID and keep source id in `source_id` | `TC-IMP-0012`, source `C1234` |
| Script | pytest node id, recorded from results | `tests/test_login.py::test_empty_password` |

IDs are stable: never renumber after a case is created. If a screen changes, add new IDs and mark old cases `retired: true`.

## app-model.json

```json
{
  "app": {"name": "App", "exe": "C:\\...\\App.exe", "explored_at": "2026-11-26T10:00:00", "backend": "uia"},
  "screens": [
    {"id": "SCR-001", "title": "Main", "kind": "window", "path": ["Main"],
     "screenshot": "shots/SCR-001.png", "fingerprint": "ab12...",
     "controls": [
       {"id": "CTL-001-01", "control_type": "Button", "name": "Login",
        "automation_id": "btnLogin", "class_name": "Button", "enabled": true,
        "rect": [10, 20, 90, 50], "interactive": true}
     ]}
  ],
  "transitions": [{"from": "SCR-001", "via": "CTL-001-05", "to": "SCR-002"}],
  "skipped": [{"screen": "SCR-001", "control": "CTL-001-09", "name": "Delete all", "reason": "risky name"}]
}
```

## test-cases.json

```json
{
  "cases": [
    {
      "id": "TC-SCR001-001",
      "title": "Login rejects empty password",
      "category": "validation",
      "priority": "high",
      "screen_id": "SCR-001",
      "control_ids": ["CTL-001-02", "CTL-001-01"],
      "preconditions": "App launched, logged out",
      "steps": ["Leave password empty", "Click Login"],
      "expected": "An error message is shown and the user stays on the login screen",
      "oracle": "observed",
      "automation": "now",
      "source": "explored",
      "source_id": null,
      "notes": ""
    }
  ]
}
```

Allowed values:
- `category`: smoke, functional, validation, boundary, negative, navigation, state, persistence, keyboard, accessibility, ui-integrity, flow
- `priority`: high, medium, low
- `oracle`: `spec` (from a requirement or an approved manual case), `observed` (what the app did during exploration), `inferred` (derived by Claude from conventions)
- `automation`: now, later, manual

Markdown, CSV, Excel, and TestRail imports default to `inferred` unless an
`oracle` column or `- Oracle: spec|observed|inferred` case metadata explicitly
sets the value. Treat `observed` and `inferred` expectations as unconfirmed
until a responsible owner approves them.

## How results are linked

The project `conftest.py` records `@pytest.mark.case(id="...", title="...")`
as a JUnit `<property name="tc_id">`. `build_report.py` reads that property
(falling back to a `TC-...` pattern in the test name). Several JUnit files
from repeated runs are merged: all passes means `passed`, all failures
`failed`, a pass/fail mix means `flaky`, and a case absent from any run is
`incomplete`.

Evidence is any file in the evidence folder whose name starts with the case ID
(for example, `SQLDM-001_20261201_101500.png`).

## Report sections (traceability.html)

1. **Summary**: totals by status (passed, failed, flaky, not run, manual), coverage of controls, and a banner if any cases are unconfirmed.
2. **Traceability matrix**: Screen -> Control -> Test case -> Script -> Result -> Evidence.
3. **Coverage gaps**: interactive controls with no case; cases with no control link; screens with no cases.
4. **Failures and flaky tests**: with evidence links and run-by-run results.
5. **Oracle review list**: cases whose expectations are `observed` or `inferred` and need human confirmation.
6. **Skipped controls**: controls the explorer refused to touch, with the reason.

The CSV has one row per case-control pair, so it can be filtered in Excel and imported into other tools.
