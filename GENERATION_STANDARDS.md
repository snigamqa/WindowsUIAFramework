# Test Generation Standards and Compliance

## Overview

This document defines the standards and best practices for the Windows UIAutomation Framework, ensuring consistency, maintainability, and reliability across all generated and manual tests.

**Key principles:**
1. Use stable, semantic locators
2. Proper synchronization without sleeps
3. Atomic, focused test cases
4. Clear traceability between manual and automated
5. Observable assertions only
6. Framework compatibility

## Locator Strategy

### Locator Priority (in order)

1. **AutomationId** (Most preferred)
   - Most stable across app versions
   - Guaranteed unique within window
   - What accessibility tools use
   
   ```python
   @property
   def save_button(self):
       return self.by_id('SaveButton')
   ```

2. **Accessible Name** (Preferred alternative)
   - User-visible text
   - More semantic than IDs
   - Can change with localization
   
   ```python
   @property
   def save_button(self):
       return self.by_name('Save')
   ```

3. **ClassName + Index** (Last resort)
   - Fragile - affected by control additions
   - Use only when ID/Name unavailable
   - Always comment why it's needed
   
   ```python
   @property
   def third_button(self):
       # Last resort: control lacks AutomationId
       return self.by_class('Button', index=2)
   ```

### Locator Examples

```python
# Good: Most specific
def by_id(self, auto_id, **kw):
    return self.window.child_window(auto_id=auto_id, **kw)

# Good: Readable
def by_name(self, name, **kw):
    return self.window.child_window(title=name, **kw)

# Good: Descendant search for nested controls
def by_descendant_id(self, auto_id, **kw):
    return self._unique_descendant(auto_id=auto_id, **kw)

# Avoid: Too generic
def by_class(self, cls, index=0, **kw):
    return self.window.child_window(class_name=cls, found_index=index, **kw)
```

### Anti-Patterns

```python
# ❌ Hardcoded coordinates (never use)
element = self.window.click((100, 200))

# ❌ Image matching as primary (fragile)
element = self.window.find_by_image('button.png')

# ❌ Time.sleep() for synchronization
time.sleep(2)  # Wrong! Use wait_* instead
element.click()

# ❌ Overly generic locators
buttons = self.window.descendants(control_type='Button')
buttons[0].click()  # Which button? Fragile!
```

## Synchronization

### Wait Methods (Always Preferred)

```python
# Wait for element to be visible
def wait_visible(self, spec, timeout=ACTION_TIMEOUT):
    spec.wait("visible", timeout=timeout)

# Wait for element to disappear
def wait_gone(self, spec, timeout=ACTION_TIMEOUT):
    spec.wait_not("visible", timeout=timeout)

# Wait for a dialog window
def wait_window(self, title, timeout=ACTION_TIMEOUT):
    dlg = Desktop(backend="uia").window(title=title)
    dlg.wait("visible", timeout=timeout)

# Wait for custom condition
def wait_until(self, fn, timeout=ACTION_TIMEOUT, interval=0.3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if fn():
                return True
        except Exception:
            pass
        time.sleep(interval)
    raise TimeoutError(f"Condition not met within {timeout}s")
```

### Good Synchronization Patterns

```python
# Good: Wait for visible, then click
def save_document(self):
    self.wait_visible(self.save_button)
    self.save_button.click_input()

# Good: Wait for condition
def close_dialog(self):
    close_btn = self.dialog.child_window(title="Close")
    self.wait_visible(close_btn)
    close_btn.click_input()
    self.wait_gone(close_btn)

# Good: Compose waits
def complete_workflow(self):
    self.click(self.step1_button)
    self.wait_visible(self.step2_dialog)
    # ... step 2 ...
    self.click(self.step2_next)
    self.wait_visible(self.step3_confirmation)
```

### Anti-Patterns

```python
# ❌ Sleep instead of wait
time.sleep(2)
element = self.window.child_window(title="Save")

# ❌ No synchronization at all
self.save_button.click()
content = self.editor.get_text()  # May not be ready!

# ❌ Arbitrary long sleep
time.sleep(10)  # Too long! Wastes test time
```

## Test Case Structure

### Case IDs

```python
# Format: APP-NNN or APPNAME-NNN
# APP-001, APP-002, ... APP-999
# NOTEPAD-001, NOTEPAD-002
# SQLDM-001, SQLDM-002

# Rules:
# - Unique within application
# - Sequential or logical grouping (optionally)
# - Uppercase for consistency
# - Linked between manual and automated

@pytest.mark.case(id='NOTEPAD-001', title='Opening a blank editor')
def test_open_blank_editor(app):
    ...
```

### Case Titles

```python
# Good: Clear, specific, starts with verb
"Opening a blank Notepad editor"
"Entering and reading editor text"
"Undoing and redoing an editor change"

# Avoid: Vague or generic
"Testing the app"           # Too vague
"UI Test 1"                # Not semantic
"Test that works correctly" # Not observable
```

### Manual Case Format (Markdown)

```markdown
## Test case: Opening a blank Notepad editor (id: NOTEPAD-001, tag: smoke)
- Oracle: inferred
1. Create a new blank Notepad tab without changing existing tabs.
2. Verify the Text editor control is visible.
3. Expected: the editor contains no text.
```

**Rules:**
- Heading format: `##` with exact structure
- Include: title, case ID, tag
- Oracle: "inferred", "documented", "automated", etc.
- Numbered steps: user-visible actions
- Expected: observable results (not implementation details)

## Automated Test Structure

### Test Markers

```python
import pytest

# Every E2E test must have @pytest.mark.case()
@pytest.mark.case(id='APP-001', title='Saving a connection profile')
def test_save_connection(app):
    """Test: Saving a connection profile"""
    # Test code

# Framework tests use @pytest.mark.framework
@pytest.mark.framework
def test_catalog_validation():
    """Test: Test case catalog validation"""
    # Framework test

# Optional: Smoke test marker
@pytest.mark.case(id='APP-001', title='...')
@pytest.mark.smoke
def test_smoke_scenario(app):
    ...
```

### Test Structure

```python
@pytest.mark.case(id='APP-001', title='Saving a document')
def test_save_document(app, tmp_path):
    """Test: Saving a document to disk.
    
    Covers:
    - Text entry in editor
    - Save-as dialog interaction
    - File persisted to correct location
    """
    page = MyAppPage(app)
    
    # Arrange
    test_file = tmp_path / "test.txt"
    test_text = "Hello, World"
    
    # Act
    page.type_text(page.editor, test_text)
    page.save_as(test_file)
    
    # Assert
    assert test_file.exists()
    assert test_file.read_text() == test_text
```

**Components:**
1. **Docstring** - What the test does
2. **Arrange** - Setup test data/state
3. **Act** - Perform user actions
4. **Assert** - Verify observable results

### Assertions

```python
# Good: Verify observable state
assert page.confirmation_dialog.is_visible()
assert page.get_text(page.status_label) == "Saved"
assert saved_file.read_text() == expected_content

# Avoid: Implementation details
assert mock_save_called == 1  # Not observable!
assert internal_flag == True  # Not user-visible

# Avoid: Coordinates or timings
assert element.rect.left == 100  # What if window moves?
assert execution_time < 2.0  # Flaky on slow systems
```

## Page Object Patterns

### Property-Based Locators

```python
class MyAppPage(UIElement):
    @property
    def save_button(self):
        """Save button locator."""
        return self.by_id('SaveButton')

    @property
    def editor(self):
        """Main text editor control."""
        return self.by_descendant_id('MainEditor', control_type='Document')

    @property
    def status_label(self):
        """Status bar label."""
        return self.by_descendant_name('Status Label')
```

### Helper Methods

```python
class MyAppPage(UIElement):
    def type_in_editor(self, text):
        """Type text into the editor and verify it's captured."""
        self.type_text(self.editor, text)
        assert self.get_text(self.editor) == text

    def save_as(self, path):
        """Save document to path using Save-As dialog."""
        path = Path(path).resolve()
        self.click(self.save_button)
        dialog = self.wait_window("Save As")
        # ... dialog interaction ...
        self.wait_until(path.is_file, timeout=15)

    def wait_ready(self):
        """Wait for app to be ready for user interaction."""
        self.wait_visible(self.editor)
        self.wait_visible(self.save_button)
```

## Documentation

### Code Comments

```python
# Good: Explains why (not what)
@property
def status_label(self):
    # Uses descendant search because control is nested in a container
    return self.by_descendant_name('Status')

# Good: Document complex logic
def close_unsaved_dialog(self):
    """Close unsaved-changes dialog, discarding changes.
    
    Why complex: pywinauto's wait_not() doesn't work reliably
    for dialogs, so we poll is_visible() instead.
    """
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            discard_btn = self._find_discard_button()
            discard_btn.click_input()
            if not self.dialog.is_visible():
                return
        except Exception:
            pass
        time.sleep(0.2)
    raise TimeoutError("Dialog did not close")
```

### Docstrings

```python
class MyAppPage(UIElement):
    """Page object for MyApp main window.
    
    Provides access to main window controls and workflows.
    Uses UIA backend exclusively.
    """

    @property
    def save_button(self):
        """Save button in the toolbar."""
        return self.by_id('SaveButton')

    def save_as(self, path: Path) -> Path:
        """Save document to specified path.
        
        Args:
            path: File path to save to.
        
        Returns:
            Resolved Path object.
        
        Raises:
            TimeoutError: If save dialog doesn't appear.
            RuntimeError: If path validation fails.
        """
        path = Path(path).resolve()
        # ... implementation ...
        return path
```

## Code Style

### Formatting

```python
# Imports
from pathlib import Path
import re

from core.ui_element import UIElement

# Class definition
class MyAppPage(UIElement):
    """Docstring."""

    # Blank line after class definition
    @property
    def control(self):
        """Control docstring."""
        return self.by_id('ControlId')

    # Blank line between methods
    def method(self):
        """Method docstring."""
        pass
```

### Naming

```python
# Functions/methods: snake_case
def save_document(self):
    pass

# Classes: PascalCase
class MyAppPage(UIElement):
    pass

# Constants: UPPER_CASE
ACTION_TIMEOUT = 10
MAX_RETRIES = 3

# Private: _leading_underscore
def _internal_helper(self):
    pass

# Properties: snake_case
@property
def save_button(self):
    pass
```

## Test Case Catalog

### JSON Format

```json
{
  "cases": [
    {
      "id": "APP-001",
      "title": "Saving a document",
      "steps": [
        "Enter text in the editor",
        "Click Save button",
        "Verify file is created"
      ],
      "expected": "File saved to disk with correct content",
      "oracle": "inferred",
      "automation": "done",
      "notes": "Covers file I/O"
    }
  ]
}
```

**Fields:**
- **id** - Unique case identifier
- **title** - User-friendly description
- **steps** - Numbered user actions
- **expected** - Observable results
- **oracle** - Source: inferred, documented, automated
- **automation** - Status: todo, in_progress, done, blocked
- **notes** - Additional context

## Validation Checklist

Before committing tests, verify:

```python
# ✓ Case IDs
- Unique across all test cases
- Format: APP-NNN or APPNAME-NNN
- Same ID in manual and automated

# ✓ Titles
- Descriptive and specific
- Match between manual and automated
- Start with verb (Save, Verify, Open)

# ✓ Locators
- Use AutomationId > Name > Class+Index
- Verified with live app inspection
- Not hardcoded coordinates

# ✓ Synchronization
- Use wait_* methods, not time.sleep()
- Proper timeouts from ACTION_TIMEOUT
- No arbitrary delays

# ✓ Assertions
- Verify observable state only
- Clear pass/fail criteria
- Not implementation details

# ✓ Documentation
- Docstrings for classes/methods
- Comments explain 'why', not 'what'
- Clear test purpose in docstring

# ✓ Markers
- @pytest.mark.case() on all E2E tests
- Correct ID and title
- Tags for grouping (smoke, slow, etc.)

# ✓ Standards
- Follow existing code style
- No hardcoded test data
- Proper fixture usage
- Cleanup in teardown
```

## Common Mistakes and Fixes

| Mistake | Problem | Fix |
|---------|---------|-----|
| `time.sleep(2)` | Wastes time, unreliable | Use `wait_visible()`, `wait_until()` |
| Hardcoded coordinates | Breaks on window move/resize | Use locators, not coordinates |
| Overly generic IDs | Conflicts and confusion | Make IDs specific to control/page |
| No docstrings | Unclear intent | Add docstrings to all methods |
| Mixed concerns in test | Hard to debug | Separate arrange/act/assert |
| Assertion on coordinates | Environment-dependent | Assert on UI state/text/visibility |
| `element[0].click()` | Fragile, wrong element risk | Use specific locators |
| No case marker | Uncatalogued test | Add `@pytest.mark.case()` |

## See Also

- **AUTOGEN_GUIDE.md** - Test generation system
- **SELF_HEALING_GUIDE.md** - Healing mechanism
- **windows-desktop-e2e SKILL** - Full E2E framework
- **core/ui_element.py** - Implementation source
- **pages/notepad_page.py** - Reference page object
- **tests/test_notepad.py** - Reference tests

