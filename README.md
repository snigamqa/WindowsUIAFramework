# Windows UI Automation Framework

Python, pytest and pywinauto framework for Windows desktop UI tests. It includes
page objects, manual-to-automated case traceability, UI exploration, a
test-generation prototype and locator-fallback helpers.

## Requirements

- Windows with Python 3.13 and pip. Windows dependencies do not install on Linux.
- For UI tests: an interactive, unlocked desktop and the installed application.
  The Notepad examples target the **tabbed Windows 11 Notepad**, not classic
  Windows Server Notepad. Run them on a dedicated test desktop.
- For SQL Diagnostic Manager tests: an installed, configured client and any
  necessary services. The installer is not the application executable.

## Setup

Open PowerShell in the project directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Commands below use the virtual environment directly; activation is optional.
If cloned, first `cd` into the cloned directory.

## Run and inspect tests

```powershell
# Verify all case IDs, titles and test collection without starting an app.
.\.venv\Scripts\python.exe -m pytest --collect-only -q -o addopts=

# Run framework tests; no desktop application is launched.
.\.venv\Scripts\python.exe -m pytest -m framework

# Run Notepad tests on a suitable interactive Windows 11 desktop.
$env:APP_PATH = "$env:WINDIR\System32\notepad.exe"
$env:APP_BACKEND = "uia"
.\.venv\Scripts\python.exe -m pytest tests\test_notepad.py

# Run SQLdm tests only after configuring the installed client.
$env:APP_PATH = "C:\path\to\installed\client.exe"
$env:APP_TITLE = "actual window title regex"
$env:APP_BACKEND = "uia"
.\.venv\Scripts\python.exe -m pytest tests\test_sqldm.py
```

Use the real installed path and title. Tests for different applications must be
run separately with the appropriate configuration; do not run the entire
application suite against a single `APP_PATH`. `APP_ARGS` is optional;
`LAUNCH_TIMEOUT` and `ACTION_TIMEOUT` are timeouts in seconds.

By default, pytest writes an HTML report to `artifacts\report.html`. Failed
tests using the `app` fixture attempt to capture screenshots and UI trees in
`artifacts\evidence`. Evidence and reports may contain application data:
inspect them before sharing.

## Create a test

1. Inspect the running application's accessibility tree with Accessibility
   Insights or the passive explorer below. Do not guess locators or expected
   behavior. Use a disposable, authorized environment.
2. Check `testcases\`, `tests\` and `pages\` for duplicate scenarios.
3. Add a unique case in `testcases\myapp.md`, including preconditions, test
   data, cleanup, steps and an observable expected result:

   ```markdown
   ## Test case: Opening the application (id: MYAPP-001, tag: smoke)
   - Oracle: spec
   - Preconditions: the installed client is configured.
   1. Launch the application.
   2. Expected: the main window is visible.
   ```

   Use `spec` only for an approved requirement; otherwise label it `observed`
   or `inferred` and obtain approval before making it a regression assertion.
4. Add a page object in `pages\myapp_page.py` using `core.ui_element.UIElement`.
   Prefer verified AutomationIds, then accessible names; use existing waits.
   Keep application actions in the page object.
5. Add `tests\test_myapp.py` with the identical case ID and title. For example,
   this first test needs only the configured application window:

   ```python
   import pytest

   @pytest.mark.case(id="MYAPP-001", title="Opening the application")
   @pytest.mark.smoke
   def test_application_opens(app):
       assert app.is_visible()
   ```

6. Normalize all Markdown cases, validate collection, then run the new test
   against the configured application:

   ```powershell
   .\.venv\Scripts\python.exe .\.claude\skills\windows-desktop-e2e\scripts\normalize_cases.py `
     --markdown testcases --out cases\test-cases.json
   .\.venv\Scripts\python.exe -m pytest --collect-only -q -o addopts=
   .\.venv\Scripts\python.exe -m pytest tests\test_myapp.py
   ```

Collection rejects duplicate cases and missing or mismatched `case` markers.
Mark infrastructure-only tests with `@pytest.mark.framework`. Avoid fixed sleeps
and assert observable UI state. See [the manual case guide](testcases/README.md)
and [desktop automation skill](.claude/skills/windows-desktop-e2e/SKILL.md).

## Explore and generate test drafts

The explorer starts the installed executable and takes a passive UI snapshot:

```powershell
$env:APP_PATH = "C:\path\to\installed\client.exe"
.\.venv\Scripts\python.exe .\.claude\skills\windows-desktop-e2e\scripts\explore_windows.py `
  --exe $env:APP_PATH --backend uia --out artifacts\model

.\.venv\Scripts\python.exe .\scripts\autogen_testcases.py `
  --app-path $env:APP_PATH --app-name myapp `
  --app-model artifacts\model\app-model.json --out artifacts\generated
```

Generated cases and code are **drafts**, not approved requirements or
guaranteed runnable tests. Review locators, safety, case IDs, expected results
and assertions; integrate them into the project, normalize the catalog, and
run collection and application tests. Traversal (`--traverse` and
`--click-buttons`) interacts with the application and should only be used
after reviewing the risks in a disposable test environment.

`SelfHealingUIElement` provides fallback helpers and healing reports, but is
not automatically enabled for all page objects. Review recovered locators;
fallbacks can match the wrong control and do not replace test maintenance.

## GitHub Actions

[The CI workflow](.github/workflows/ci-cd.yml) runs on pushes, pull requests
and manual dispatch. A GitHub-hosted Windows runner installs the dependencies,
validates collection and runs framework tests; JUnit XML and the HTML report
are uploaded as artifacts. The workflow does not deploy an application.

Desktop UI tests need a suitable interactive session and are **not** included
in the hosted job. To run the optional Notepad job:

1. Set up a dedicated Windows 11 self-hosted runner with the custom label
   `windows-uia`, Python support, tabbed Notepad and an unlocked interactive
   desktop. Run the runner in that desktop session rather than as a service.
2. In Actions, select **Windows framework CI**, choose **Run workflow** on the
   default branch and enable **run_notepad**.
3. Review the result and downloaded evidence. The job is not run for pull
   requests. Restrict runner access to trusted code and users; self-hosted
   runners can execute repository code on your machine.

SQLdm requires its own configured test environment and is not run by this
workflow. No GitHub Actions run or desktop compatibility is guaranteed until
verified in your environment. GitHub pricing depends on your plan and usage.

## Troubleshooting

- **Missing dependency or collection error:** reinstall from
  `requirements.txt`, then run collection above and read the first error.
- **App does not start:** verify `APP_PATH` points to the installed EXE and
  `APP_TITLE` matches the real window. Check permissions and prerequisites.
- **Control not found:** inspect the actual UI tree and backend; verify the
  app version, language and interactive session.
- **CI passes but UI fails:** framework CI does not execute application tests;
  inspect the interactive runner and its artifacts separately.

The skill's [traceability reference](.claude/skills/windows-desktop-e2e/references/traceability-and-report.md)
describes optional JUnit-based reporting.
