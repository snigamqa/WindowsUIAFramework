#  Automated Test Generation Guide

> Historical guide: generation produces drafts requiring review and may not
> produce runnable tests. Use [README.md](README.md) for the current workflow.

## Overview

The Windows UIAutomation Framework now includes **automated test generation** that can analyze an application's UI structure and generate complete test suites with minimal manual effort.

**Key capabilities:**
- Analyzes UI via `app-model.json` from exploration
- Generates Markdown manual test cases
- Creates page objects with locators
- Produces pytest test code
- Builds normalized test case catalogs
- Integrates seamlessly with existing framework

## Quick Start

### Step 1: Explore the Application

First, analyze your application's UI structure:

```powershell
# Windows PowerShell
$skill = ".claude\skills\windows-desktop-e2e\scripts"
& .\venv\Scripts\python.exe "$skill\explore_windows.py" `
  --exe "C:\Windows\System32\notepad.exe" `
  --out artifacts/model `
  --backend uia
```

This creates `artifacts/model/app-model.json` with all discovered controls, structure, and navigation patterns.

**Options:**
- `--traverse` - Click navigation controls to discover more screens
- `--click-buttons` - Also click non-risky buttons
- `--max-screens 40` - Maximum screens to explore (default: 40)

### Step 2: Generate Tests

Run the automated test generator:

```powershell
# From project root
& .\venv\Scripts\python.exe scripts/autogen_testcases.py `
  --app-path "C:\Windows\System32\notepad.exe" `
  --app-name notepad `
  --app-title "Notepad" `
  --out artifacts/generated
```

**Parameters:**
- `--app-path` - Full path to application executable (required)
- `--app-name` - Short name for files/classes, e.g., 'myapp', 'sqldm' (required)
- `--app-title` - Window title regex pattern (optional)
- `--app-model` - Path to app-model.json (auto-found if omitted)
- `--out` - Output directory (default: `artifacts/generated`)
- `--verbose` - Enable debug logging

### Step 3: Review Generated Files

The generator creates:

```
artifacts/generated/
├── testcases/
│   └── notepad.md              # Manual test cases
├── pages/
│   └── notepad_page.py         # Page object with locators
├── tests/
│   └── test_notepad.py         # Pytest test code
├── cases/
│   └── notepad_test-cases.json # Test case catalog
└── notepad_generation_report.md # Summary report
```

### Step 4: Integrate into Framework

Copy generated files to their framework locations:

```powershell
# Manual test cases
Copy-Item artifacts/generated/testcases/notepad.md testcases/

# Page object
Copy-Item artifacts/generated/pages/notepad_page.py pages/

# Tests
Copy-Item artifacts/generated/tests/test_notepad.py tests/

# Case catalog - merge with cases/test-cases.json
```

### Step 5: Customize and Run

Edit the generated files to:
1. Update locator AutomationIds with real values
2. Add meaningful test assertions
3. Implement specific test workflows
4. Verify case IDs and titles match your standards

Then validate:

```powershell
# Check for catalog errors
& .\venv\Scripts\pytest.exe --collect-only -q

# Run the generated tests
& .\venv\Scripts\pytest.exe tests/test_notepad.py -v
```

## Generated Artifacts

### Manual Test Cases (Markdown)

Format matches existing framework patterns with one test per `##` heading:

```markdown
## Test case: Verify control is visible (id: APP-001, tag: auto-gen)
- Oracle: inferred
1. Locate the control
2. Verify it is visible
3. Expected: control is visible and enabled
```

**Key fields:**
- **id** - Unique case identifier (e.g., `APP-001`, `NOTEPAD-001`)
- **tag** - Test marker (auto-gen for generated, smoke for smoke tests)
- **Steps** - Numbered user-visible actions
- **Expected** - Observable results

### Page Object (Python)

Extends `UIElement` with app-specific locators and helper methods:

```python
class NotepadPage(UIElement):
    @property
    def editor(self):
        """Locator for Text editor."""
        return self.by_descendant_id('TextEditor')

    def verify_ui_ready(self):
        """Verify app UI is ready for testing."""
        self.wait_visible(self.editor)
```

**Best practices:**
- Properties for each major control
- Helper methods for workflows
- Use preferred locator priorities: AutomationId > Name > Class+Index

### Pytest Tests (Python)

Generated tests include pytest markers and fixtures:

```python
@pytest.mark.case(id='APP-001', title='Verify control is visible')
def test_control_visible(app):
    """Test: Verify control is visible"""
    page = NotepadPage(app)
    page.verify_ui_ready()
    # TODO: implement test logic
```

**Features:**
- `@pytest.mark.case()` marker linking to manual case
- Uses `app` fixture for process isolation
- Docstrings for all tests
- TODO placeholders for implementation

### Test Case Catalog (JSON)

Normalized cases for traceability and reporting:

```json
{
  "cases": [
    {
      "id": "APP-001",
      "title": "Verify control is visible",
      "steps": ["Locate control", "Verify visible"],
      "expected": "Control is visible and enabled",
      "oracle": "inferred",
      "automation": "todo",
      "pattern": "ui_state",
      "notes": "Auto-generated from UI exploration"
    }
  ]
}
```

## Test Design Patterns

The generator recognizes and creates several test pattern types:

### 1. UI State Tests (`ui_state`)

Verify controls are present, visible, and enabled.

```python
def test_button_visible(app):
    page = MyAppPage(app)
    assert page.my_button.is_visible()
    assert page.my_button.is_enabled()
```

**Use for:**
- Control availability verification
- UI initialization tests
- Dialog presence checks

### 2. Text Input Tests (`text_input`)

Type text and verify it's captured correctly.

```python
def test_text_input(app):
    page = MyAppPage(app)
    test_text = "Hello, World"
    page.type_text(page.text_field, test_text)
    assert page.get_text(page.text_field) == test_text
```

**Use for:**
- Form input validation
- Text field functionality
- Editor content tests

### 3. Button Click Tests (`button_click`)

Click buttons and verify resulting state changes.

```python
def test_save_button(app):
    page = MyAppPage(app)
    page.click(page.save_button)
    page.wait_until(lambda: page.confirmation_visible())
```

**Use for:**
- Button functionality
- Dialog triggering
- State transitions

### 4. Dialog Tests (`dialog`)

Open, interact with, and close dialogs.

```python
def test_save_dialog(app):
    page = MyAppPage(app)
    page.click(page.save_button)
    dialog = page.wait_window("Save As")
    # ... interact with dialog
```

### 5. Error Handling Tests (`error_handling`)

Send invalid input and verify error responses.

```python
def test_invalid_input_error(app):
    page = MyAppPage(app)
    page.type_text(page.amount_field, "invalid")
    assert page.error_message.is_visible()
```

### 6. Navigation Tests (`navigation`)

Navigate workflows and verify state transitions.

```python
def test_workflow_navigation(app):
    page = MyAppPage(app)
    page.click(page.next_button)
    page.wait_until(lambda: page.step_2_visible())
```

## Standards Compliance

All generated tests follow framework standards:

✓ **Locator Priority:**
- AutomationId (most reliable)
- Accessible Name (friendly)
- ClassName + Index (fragile, last resort)

✓ **Synchronization:**
- Use `wait_visible()`, `wait_gone()`, `wait_until()`
- Never use `time.sleep()` as primary sync
- Proper timeouts from `config.ACTION_TIMEOUT`

✓ **Case IDs:**
- Format: `APP-NNN` or `APPNAME-NNN`
- Unique across all test cases
- Linked between manual and automated tests

✓ **Markers & Tags:**
- All tests have `@pytest.mark.case(id=..., title=...)`
- Tags: `smoke`, `auto-gen`, or test-specific
- Framework tests use `@pytest.mark.framework`

✓ **Code Style:**
- Docstrings for all public methods
- Type hints where practical
- 4-space indentation
- Follows existing framework patterns

✓ **Dependencies:**
- Uses only existing UIElement methods
- No new packages without justification
- Compatible with pywinauto + UIA backend

## Customization

### Updating Locators

After generation, verify and update locator AutomationIds:

```python
# Generated (placeholder)
@property
def save_button(self):
    return self.by_descendant_id('GEN-001')

# After inspection - use real AutomationId
@property
def save_button(self):
    return self.by_id('SaveButton')
```

Use Accessibility Insights to verify AutomationIds:
1. Open target app
2. Launch Accessibility Insights
3. Enable UIA inspection
4. Record confirmed AutomationIds
5. Update page object

### Adding Test Logic

Replace TODO placeholders with actual test logic:

```python
# Generated
@pytest.mark.case(id='APP-001', title='Saving a document')
def test_save_document(app):
    """Test: Saving a document"""
    page = MyAppPage(app)
    page.verify_ui_ready()
    # TODO: implement test logic from scenario

# After implementation
@pytest.mark.case(id='APP-001', title='Saving a document')
def test_save_document(app, tmp_path):
    """Test: Saving a document"""
    page = MyAppPage(app)
    page.verify_ui_ready()
    
    # Arrange
    test_file = tmp_path / "test.txt"
    
    # Act
    page.type_text(page.editor, "Hello, World")
    page.save_as(test_file)
    
    # Assert
    assert test_file.exists()
    assert test_file.read_text() == "Hello, World"
```

### Merging Catalogs

To merge generated catalog with existing cases:

```python
import json
from pathlib import Path

# Load existing
existing = json.loads(Path("cases/test-cases.json").read_text())
existing_ids = {c["id"] for c in existing["cases"]}

# Load generated
generated = json.loads(Path("artifacts/generated/cases/app_test-cases.json").read_text())

# Merge (skip duplicates)
for case in generated["cases"]:
    if case["id"] not in existing_ids:
        existing["cases"].append(case)

# Save merged
Path("cases/test-cases.json").write_text(
    json.dumps(existing, indent=2),
    encoding="utf-8"
)
```

## Self-Healing Integration

If using `SelfHealingUIElement`, mark page methods to enable healing:

```python
from core.self_healing_element import SelfHealingUIElement

class MyAppPage(SelfHealingUIElement):
    @property
    def save_button(self):
        """Locator with self-healing for save button."""
        # Try AutomationId first, fallback to Name and Descendant
        return self.by_id_with_fallback('SaveButton')

    def save_document(self, path):
        self.click(self.save_button)
        # ... rest of method
        # Healing attempts are logged automatically
```

After tests, check healing reports:

```powershell
# View healing logs
Get-ChildItem artifacts/healing/*.json
Get-Content artifacts/healing/test_save_*.json
```

## Troubleshooting

### "app-model.json not found"

**Solution:** Run exploration first:
```powershell
python .claude/skills/windows-desktop-e2e/scripts/explore_windows.py `
  --exe "C:\app.exe" --out artifacts/model
```

### Generated tests have empty steps

**Cause:** UI controls in model lack names/AutomationIds

**Solution:** 
1. Re-run exploration with `--traverse` and `--click-buttons`
2. Inspect live app with Accessibility Insights
3. Manually add AutomationIds to controls in test markup

### Case ID conflicts

**Cause:** Generated ID already exists

**Solution:** Rename in generated files or manual catalog:
```bash
# Update markdown
sed -i 's/APP-001/APP-010/g' testcases/app.md

# Update JSON catalog
sed -i 's/"id": "APP-001"/"id": "APP-010"/g' cases/app_test-cases.json
```

### Pytest collection errors

**Check:**
```powershell
# Validate catalog without launching app
pytest --collect-only -q

# Check for duplicate IDs
pytest --collect-only -q 2>&1 | Select-String "duplicate"
```

## Examples

### Complete Example: Notepad

```powershell
# 1. Explore
python .claude/skills/windows-desktop-e2e/scripts/explore_windows.py `
  --exe "C:\Windows\System32\notepad.exe" --out artifacts/model

# 2. Generate
python scripts/autogen_testcases.py `
  --app-path "C:\Windows\System32\notepad.exe" `
  --app-name notepad `
  --out artifacts/generated

# 3. Review generated files
Get-ChildItem artifacts/generated/

# 4. Integrate
Copy-Item artifacts/generated/testcases/notepad.md testcases/
Copy-Item artifacts/generated/pages/notepad_page.py pages/
Copy-Item artifacts/generated/tests/test_notepad.py tests/

# 5. Run tests
pytest tests/test_notepad.py -v
```

### Custom Pattern: Multi-step Workflow

For workflows spanning multiple screens:

```python
# In page object
def complete_workflow(self):
    """Complete a multi-step workflow."""
    # Step 1
    self.click(self.step1_button)
    self.wait_visible(self.step2_dialog)
    
    # Step 2
    self.type_text(self.step2_input, "value")
    self.click(self.step2_next)
    
    # Step 3
    self.wait_visible(self.step3_confirmation)
    return self.get_text(self.confirmation_message)

# In test
@pytest.mark.case(id='APP-050', title='Complete workflow')
def test_complete_workflow(app):
    page = MyAppPage(app)
    result = page.complete_workflow()
    assert "success" in result.lower()
```

## Best Practices

1. **Always Review Generated Code**
   - Verify locator AutomationIds against live app
   - Confirm test logic makes sense
   - Check for placeholder values

2. **Keep Markdown Manual Cases Readable**
   - Avoid jargon or internal implementation details
   - Use observable behaviors ("click button", not "invoke()")
   - Include expected results for each step

3. **Use Page Objects for Reusability**
   - Define high-level page methods (e.g., `save_document()`)
   - Keep locators in properties
   - Share common workflows across tests

4. **Maintain Case Traceability**
   - Every automated test links to a manual case
   - IDs are unique and stable
   - Titles match between manual and automated

5. **Document Healing Decisions**
   - Review healing logs after test runs
   - Decide: update locator or add fallback permanently
   - Keep healing history for audit trail

## See Also

- **SELF_HEALING_GUIDE.md** - Detailed healing mechanism
- **GENERATION_STANDARDS.md** - Technical standards reference
- **framework SKILL.md** - Full Windows E2E patterns
- **explore_windows.py** - UI exploration tool

