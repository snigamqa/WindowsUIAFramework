# Manual Test Cases

Drop one Markdown file per app/feature in this folder (e.g. `myapp_login.md`), then ask:

> Convert `testcases/myapp_login.md` into automation for the app at `C:\build\MyApp.exe`.

## Template

```markdown
## App
- EXE path: C:\build\MyApp.exe          (set APP_PATH)
- Window title: "MyApp"                (set APP_TITLE)
- Launch args:                         (set APP_ARGS, optional)
- Backend: uia (default) or win32      (set APP_BACKEND)
- Framework: WPF / WinForms / Win32 / Qt

## Test case: <short name> (id: APP-001, tag: smoke)
- Oracle: inferred (use spec only for an approved requirement)
1. Open the window and enter <value> in the "..." field
2. Click "..."
3. Expected: <observable result — control text, enabled state, new window>

## Test case: <negative / error path> (id: APP-002, tag: smoke)
1. Open the window and enter <invalid value>
2. Click "..."
3. Expected: error label shows "<message>"
```

## How it becomes automation

The `windows-desktop-e2e` skill (`.claude/skills/windows-desktop-e2e/SKILL.md`) drives it:

1. Read `.claude/skills/windows-desktop-e2e/SKILL.md` and inspect existing helpers in `core/ui_element.py`, page objects, test cases, and dependencies before adding a method or package.
2. Check for duplicate manual and automated cases. Every automated case uses `@pytest.mark.case(id="...", title="...")` and must match exactly one manual case.
3. Inspect the live UIA tree — use AutomationId first, then accessible name, then class/index as a last resort.
4. Add a page object `pages/<app>_page.py` that reuses `UIElement` methods, plus tests using the function-scoped `app` fixture.
5. Synchronize with waits, never fixed sleeps. Assert observable state, not coordinates.
6. Run the targeted tests and review the skill's anti-pattern checklist.

Expected-result lines in the manual test case become assertions on control text/state — never pixel coordinates or sleeps.

The pytest collection hook checks duplicate IDs/titles and verifies that automated
case markers refer to matching manual cases. It also detects exact duplicate
normalized step sequences. Semantically similar cases with differently worded
steps still need a human review. Run `pytest --collect-only -q` to check the
catalog and test metadata without launching the desktop application.

## Import, explore, and report

The project skill includes scripts for building an observed UI model, importing
case catalogs, and producing traceability reports. Read
`.claude/skills/windows-desktop-e2e/SKILL.md` before using them.

The explorer takes a passive snapshot by default. It launches an installed app
specified by `APP_PATH`; it does not install applications. `--traverse` and
`--click-buttons` interact with the app and should be used only in an authorized
test environment after reviewing their scope.

```powershell
$env:APP_BACKEND = "uia"
python .claude\skills\windows-desktop-e2e\scripts\explore_windows.py `
  --exe "$env:APP_PATH" --backend "$env:APP_BACKEND" --out artifacts\model
```

Convert the structured Markdown catalog into normalized JSON. The importer
also accepts `--csv` and `--excel`; Excel requires the optional `openpyxl`
package. This generated catalog is cross-checked against the Markdown files and
pytest markers during collection.

```powershell
python .claude\skills\windows-desktop-e2e\scripts\normalize_cases.py `
  --markdown testcases --out cases\test-cases.json
pytest --collect-only -q
```

TestRail import requires explicit authorization, an HTTPS instance URL, and
`TESTRAIL_USER` / `TESTRAIL_API_KEY` environment variables. Never save tokens
in the repository or pass them in command arguments.

Save test outcomes as JUnit XML and build a report from the model, normalized
cases, results, and case-ID-prefixed failure evidence:

```powershell
New-Item -ItemType Directory -Force artifacts\results | Out-Null
python -m pytest tests\test_sqldm.py --junitxml=artifacts\results\run1.xml
python .claude\skills\windows-desktop-e2e\scripts\build_report.py `
  --model artifacts\model\app-model.json --cases cases\test-cases.json `
  --junit artifacts\results\run1.xml --evidence artifacts\evidence `
  --out artifacts\report
```

The model is optional when no UI exploration is appropriate. For an initial
stability check, use five separate runs; a regression gate should require 20
consecutive passes. Mixed pass/fail outcomes are reported as flaky, while a
case missing from any run is incomplete. Do not hide either condition with
retries.

## Idera SQL Diagnostic Manager

The supplied `IderaSQLdmInstallationKit-x64.exe` is the SQLdm 14.3 installation
kit. It contains a setup launcher and supporting installers; it is **not** the
installed client executable and should not be set as `APP_PATH`. The installer
requires administrator elevation in this environment, so the SQLdm client UI
has not yet been inspected and no product-specific control locators are assumed.

After SQLdm is installed, set `APP_PATH` to the installed client executable and
optionally `APP_TITLE` to a regular expression matching its main window title.
The SQLdm smoke POM and test are `pages/sqldm_page.py` and
`tests/test_sqldm.py`. Add feature locators only after inspecting the running
client's UIA tree. The tracked smoke case is `sqldm_smoke.md`.

```powershell
$env:APP_PATH = "C:\Program Files\Idera\...\<installed-client>.exe"
$env:APP_TITLE = "SQL Diagnostic Manager"
pytest tests\test_sqldm.py -m smoke -v
```

Replace the example executable path and title with the values from the actual
installation. Tests launch the installed application; they do not install or
modify SQLdm.
