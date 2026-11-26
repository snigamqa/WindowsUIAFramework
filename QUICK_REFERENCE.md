# Framework Quick Reference

> Historical reference: use [README.md](README.md) for current setup and run
> each application's tests separately with its own `APP_PATH`.

## Setup (One-time)

```powershell
cd C:\Automation\WindowsUIAFramework
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run Tests

```powershell
# All smoke tests
pytest tests/ -m smoke -v

# Single file
pytest tests/test_notepad.py -v

# Single test
pytest tests/test_notepad.py::test_notepad_opens_with_blank_editor -v

# Collect only (validate catalog)
pytest --collect-only -q

# With HTML report
pytest tests/ -v --html=artifacts/report.html --self-contained-html
```

## Configure App

```powershell
# Notepad (built-in)
$env:APP_PATH = "C:\Windows\System32\notepad.exe"
$env:APP_TITLE = "Notepad"
$env:APP_BACKEND = "uia"

# Any app
$env:APP_PATH = "path\to\app.exe"
$env:APP_TITLE = "Window Title"
$env:APP_ARGS = "--arg1 value1"
$env:LAUNCH_TIMEOUT = "30"
$env:ACTION_TIMEOUT = "10"
```

## Write a Test

```python
from pages.notepad_page import NotepadPage

@pytest.mark.case(id="APP-001", title="My test case")
def test_my_case(app):
    page = NotepadPage(app)
    
    page.click(page.button)
    page.type_text(page.text_box, "Hello")
    
    assert page.text == "Hello"
    page.screenshot("my_evidence")
```

## Write a Page Object

```python
from core.ui_element import UIElement

class MyAppPage(UIElement):
    @property
    def button(self):
        return self.by_id("MyButton")
    
    @property
    def text_box(self):
        return self.by_id("TextInput")
    
    def click_button(self):
        self.click(self.button)
        self.wait_window("Dialog Title", timeout=10)
```

## Common Locators

```python
# AutomationId (best)
element = page.by_id("TextBox1")

# UI text
element = page.by_name("OK")

# Nested element
element = page.by_descendant_id("SaveButton")

# Class + index (avoid)
element = page.by_class("Edit", index=0)
```

## Common Waits

```python
# Wait for visible
page.wait_visible(element, timeout=10)

# Wait for gone
page.wait_gone(element, timeout=10)

# Wait for new window
dlg = page.wait_window("Dialog Title", timeout=10)

# Wait for condition
page.wait_until(lambda: page.text == "Done", timeout=10)
```

## Common Actions

```python
# Click
page.click(element)

# Type text
page.type_text(text_box, "Hello World")

# Get text
text = page.get_text(text_box)

# Screenshot
page.screenshot("my_screenshot")
```

## Troubleshooting

### App doesn't launch
- Check `APP_PATH` exists: `Test-Path $env:APP_PATH`
- Verify executable: `Get-Item $env:APP_PATH`
- Check window title: remove `APP_TITLE` temporarily

### Element not found
- Print UI tree: `app.print_control_identifiers()`
- Find AutomationId in output
- Use `by_id()` instead of `by_name()` or `by_class()`

### Test times out
- Increase `ACTION_TIMEOUT`: `$env:ACTION_TIMEOUT = "20"`
- Use `page.wait_until()` with explicit condition
- Avoid `time.sleep()`

### Flaky test
- Use stable locators (AutomationId)
- Increase timeout for slow systems
- Mark with `@pytest.mark.flaky`

## Files

| File | Purpose |
|------|---------|
| `README.md` | Full documentation |
| `config.py` | App configuration |
| `conftest.py` | pytest fixtures |
| `core/` | Framework modules |
| `pages/` | Page object models |
| `tests/` | Automated tests |
| `testcases/` | Manual test cases |
| `cases/test-cases.json` | Test catalog |
| `artifacts/report.html` | Test results |

## Resources

- Full docs: `README.md`
- Skill guide: `.claude/skills/windows-desktop-e2e/SKILL.md`
- Manual cases: `testcases/README.md`
- Completion: `COMPLETION_REPORT.md`

---

## Automated Test Generation (NEW)

### Generate Tests Automatically

```powershell
# 1. Explore app UI
python .claude/skills/windows-desktop-e2e/scripts/explore_windows.py `
  --exe "C:\app.exe" --out artifacts/model

# 2. Generate test suite
python scripts/autogen_testcases.py `
  --app-path "C:\app.exe" `
  --app-name myapp `
  --out artifacts/generated
```

### Generated Artifacts
- `artifacts/generated/testcases/myapp.md` - Manual test cases
- `artifacts/generated/pages/myapp_page.py` - Page object
- `artifacts/generated/tests/test_myapp.py` - Pytest tests
- `artifacts/generated/cases/myapp_test-cases.json` - Test catalog

### Self-Healing Tests

```python
from core.self_healing_element import SelfHealingUIElement

class MyAppPage(SelfHealingUIElement):
    @property
    def save_button(self):
        # Auto-fallback: by_id → by_name → by_descendant_id
        return self.by_id_with_fallback('SaveButton')
```

### Documentation
- `AUTOGEN_GUIDE.md` - Complete generation guide
- `SELF_HEALING_GUIDE.md` - Healing mechanism
- `GENERATION_STANDARDS.md` - Standards and patterns
- `IMPLEMENTATION_SUMMARY.md` - System overview
