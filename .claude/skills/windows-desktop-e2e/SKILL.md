---
name: windows-desktop-e2e
description: Create and maintain page-object-based tests for Windows desktop applications, and convert structured manual test cases into automation.
---

# Windows Desktop E2E with POM

Use this workflow for native Windows desktop applications, including WPF,
WinForms, Win32/MFC, Qt, UWP, and WinUI. The project uses pywinauto with UI
Automation (`uia`) by default and supports the `win32` backend as a fallback.

This is not a promise that every Windows UI is automatable. Electron, WebView2,
and other browser-hosted interfaces may need browser automation for their web
content. Custom-drawn controls may expose no usable accessibility tree; use
image/coordinate automation only as an explicitly documented last resort.

## Required workflow

### 1. Identify the real application target

- Distinguish an installer/bootstrapper from the installed application EXE.
- Do not install or modify an application unless the user asks for it.
- Read `APP_PATH`, `APP_ARGS`, `APP_TITLE`, and `APP_BACKEND` in `config.py`.
- Record the installed app path, title pattern, framework/backend, launch
  arguments, test prerequisites, and cleanup expectations.
- Do not guess paths, titles, AutomationIds, control names, or app behavior.

### 2. Review existing POM methods and dependencies first

Before adding a page helper, action, or package:

1. Read `core/ui_element.py` and the target page objects.
2. Search `core/`, `pages/`, and tests for an existing locator, wait, action,
   or assertion helper that already solves the need.
3. Check `requirements.txt` and installed project patterns before proposing a
   dependency.
4. Reuse an existing helper. Add a new shared method only when no existing
   method fits; keep app intent in the app-specific page object.

Current shared methods in `UIElement`:

| Purpose | Existing methods |
| --- | --- |
| Locators | `by_id`, `by_name`, `by_class` |
| Synchronization | `wait_visible`, `wait_gone`, `wait_window`, `wait_until` |
| Interaction/read | `click`, `type_text`, `get_text` |
| Artifacts | `screenshot` |

Prefer AutomationId, then accessible name, then class/index as a last resort.
Scope locators to the relevant window/container.

### 3. Check for duplicate cases before writing tests

- Search all `testcases/**/*.md`, `tests/`, and page objects for the scenario.
- Give each manual case a stable, unique ID and title:

  ```markdown
  ## Test case: Saving a connection profile (id: APP-001, tag: smoke)
  ```

- Do not create another case with an existing ID or equivalent title.
- The pytest collection hook rejects duplicate manual IDs/titles, duplicate
  automated IDs/titles, missing manual-case links, and title mismatches.
- Every application E2E test must have a `case` marker; use the `framework`
  marker only for tests that exercise test-framework infrastructure rather
  than an application scenario.
- Link one automated test to its manual case:

  ```python
  @pytest.mark.case(id="APP-001", title="Saving a connection profile")
  def test_saving_connection_profile(app):
      ...
  ```

- Run `pytest --collect-only -q` to validate the catalog and mappings without
  launching the target application.

### 4. Write or update the manual test first

Use `testcases/<app_or_feature>.md`. Keep each case focused and specify:

- Preconditions, test data, and cleanup requirements.
- User-visible steps in order.
- Observable expected results (text, state, dialog, persisted data).
- A unique ID and pytest marker/tag.

Avoid vague expectations such as “works correctly.” Never include real
credentials in test data or fixtures.

### 5. Inspect the live UI and implement the page object

- Inspect the live UIA tree with Accessibility Insights or pywinauto before
  writing locators. Record verified AutomationIds, names, and control types.
- Create `pages/<app>_page.py`; inherit from/reuse the existing shared POM
  helpers. Page methods should express user intent, not duplicate low-level
  click/type/wait code.
- Use `APP_BACKEND=uia` by default. Try `APP_BACKEND=win32` only when UIA
  inspection confirms that the target controls are better exposed there.
- Do not add a locator for a control that is not present in observed evidence.
- Do not put assertions, test data, or test flow in shared locator helpers.

### 6. Implement and validate automation

- Add focused pytest cases in `tests/test_<app_or_feature>.py`, each linked to
  its manual case using `pytest.mark.case`.
- Use the function-scoped `app` fixture for a fresh process and isolated
  per-user data directories.
- Synchronize with existing waits; never use fixed sleeps as test
  synchronization.
- Assert observable UI state, not coordinates or screenshots.
- Capture screenshots for useful evidence and let fixture teardown close the
  app.
- Run duplicate/catalog collection checks, then the targeted app test when the
  application is installed and configured. Report clearly when runtime
  validation is blocked by installation, permissions, services, or a backend.

## Supported scope and limits

The same POM structure can be used for Idera products and other Windows
applications; app-specific locators and workflows belong in separate page
objects. UIA accessibility quality depends on the application. Browser-hosted
content and custom-drawn controls may require a different automation approach.
Never claim universal support without verifying the target application's
accessibility surface.

## Explore an application and model its UI

The helper scripts and references are stored beside this skill:

- `scripts/explore_windows.py` creates `app-model.json` with screen, control,
  AutomationId, transition, screenshot, and skipped-control information.
- `references/windows-uia-patterns.md` documents locator and synchronization
  patterns.
- `references/test-design-techniques.md` lists practical test categories.
- `references/traceability-and-report.md` defines the case/model format and
  report relationships.

The explorer's default behavior is a passive snapshot. It starts the supplied
application when passed `--exe`; it does not install an application. Run it
only against an authorized test environment:

```powershell
$skill = ".claude\skills\windows-desktop-e2e\scripts"
& .\venv\Scripts\python.exe "$skill\explore_windows.py" `
  --exe "$env:APP_PATH" --backend "$env:APP_BACKEND" --out "artifacts\model"
```

`--traverse` clicks navigation controls, and `--click-buttons` clicks
non-risky-looking buttons. Names are not a guarantee of safety: use traversal
only in a disposable/test environment after confirming the scope. Do not
explore installers or production systems. Review the generated model for
missing AutomationIds, skipped controls, inaccessible regions, and screens
before designing tests. Exploration observations are not product requirements;
label expectations as `spec`, `observed`, or `inferred` and seek approval for
observed/inferred behavior before treating it as a regression requirement.

## Import manual cases and preserve traceability

`scripts/normalize_cases.py` accepts the project's structured Markdown cases,
CSV, Excel, or an explicitly requested TestRail API import. It writes the
normalized JSON format in the traceability reference, checks duplicate IDs,
titles, and step sequences, and can link cases to an app model.

```powershell
$skill = ".claude\skills\windows-desktop-e2e\scripts"
& .\venv\Scripts\python.exe "$skill\normalize_cases.py" `
  --markdown testcases --out cases\test-cases.json
```

For Excel, install `openpyxl` in the active environment. TestRail import makes
a network request: only do it when explicitly requested, use an HTTPS instance
URL, and provide `TESTRAIL_USER` and `TESTRAIL_API_KEY` through the environment.
Never put credentials in files or command history. The normalized JSON catalog
is checked against Markdown and pytest case markers during collection.

Each pytest `case` marker is emitted to JUnit XML as `tc_id`. On failures, the
fixture stores a case-ID-prefixed screenshot and UI tree under
`artifacts/evidence/`, allowing the traceability report to associate results
and evidence.

```powershell
New-Item -ItemType Directory -Force artifacts\results | Out-Null
& .\venv\Scripts\python.exe -m pytest tests\test_sqldm.py `
  --junitxml=artifacts\results\run1.xml
& .\venv\Scripts\python.exe "$skill\build_report.py" `
  --model artifacts\model\app-model.json `
  --cases cases\test-cases.json `
  --junit artifacts\results\run1.xml `
  --evidence artifacts\evidence --out artifacts\report
```

For a stability check, run the targeted batch five times with separate JUnit
files and pass all files to `build_report.py`. Mixed pass/fail results count as
flaky; a case missing from any repeat is incomplete, not green. Use 20
consecutive passing runs for a regression gate; do not hide a failure by
changing expected results or counting a retry as a pass.
