# Self-Healing Test Mechanism Guide

> Historical guide: fallback is experimental and not automatically enabled for
> all page objects. Lazy locators may not fail until later, so fallback is not
> guaranteed. Review recovered controls and use [README.md](README.md) for setup.

## Overview

The Windows UIAutomation Framework includes **self-healing capabilities** that automatically detect broken locators, try alternative strategies, and adapt without manual intervention.

**Key features:**
- Detects when locators fail (element not found)
- Tries fallback strategies automatically (by_name, by_descendant_id, by_class)
- Logs what changed and why for diagnosis
- Learns from failures across test runs
- Zero test failure due to UI structure changes (in many cases)

## How It Works

### Detection

When a primary locator fails:

```python
# Primary strategy fails
try:
    element = page.by_id('SaveButton')  # → Element not found
except Exception as e:
    # Trigger healing
```

### Recovery

Automatically tries fallbacks in order:

```python
1. Try primary:    by_id('SaveButton')      # Failed
2. Try fallback 1: by_name('Save')          # Success ✓
3. Use fallback, log healing event
4. Continue test
```

### Adaptation

Healing events are logged for review:

```json
{
  "original": {"strategy": "by_id", "params": {"auto_id": "SaveButton"}},
  "fallback": {"strategy": "by_name", "params": {"name": "Save"}},
  "success": true,
  "error": null
}
```

## Using Self-Healing

### Basic Setup

Replace `UIElement` with `SelfHealingUIElement`:

```python
from core.self_healing_element import SelfHealingUIElement

class MyAppPage(SelfHealingUIElement):
    """Page object with self-healing capabilities."""

    def __init__(self, window):
        super().__init__(window)
        # Optional: specify custom healing log directory
        # self.healing_log_dir = Path("custom/path")

    @property
    def save_button(self):
        """Locator with fallback strategies."""
        return self.by_id_with_fallback('SaveButton')
```

### Available Fallback Methods

#### `by_id_with_fallback(auto_id, **kw)`

Primary: AutomationId → Fallback: by_name → by_descendant_id

```python
@property
def save_button(self):
    # Try: by_id('SaveButton')
    # Fallback: by_name('SaveButton'), by_descendant_id('SaveButton')
    return self.by_id_with_fallback('SaveButton')
```

#### `by_name_with_fallback(name, **kw)`

Primary: Name → Fallback: by_id → by_descendant_name

```python
@property
def status_label(self):
    # Try: by_name('Status')
    # Fallback: by_id('Status'), by_descendant_name('Status')
    return self.by_name_with_fallback('Status')
```

#### `by_class_with_fallback(cls, index=0, **kw)`

Primary: Class+Index → Fallback: by_name → by_id

```python
@property
def text_field(self):
    # Try: by_class('Edit', index=0)
    # Fallback: by_name('Edit'), by_id('Edit')
    return self.by_class_with_fallback('Edit', index=0)
```

### Generic Fallback Strategy

For custom locator sequences:

```python
def custom_locator(self):
    """Try multiple locator strategies in order."""
    strategies = [
        ('by_id', {'auto_id': 'MyButtonID'}),
        ('by_name', {'name': 'My Button'}),
        ('by_descendant_id', {'auto_id': 'MyButtonID'}),
        ('by_class', {'cls': 'Button', 'index': 0}),
    ]
    return self._try_strategies(
        'by_id',  # Primary strategy name
        {'auto_id': 'MyButtonID'},  # Primary params
        strategies[1:]  # Fallbacks
    )[0]  # Return element (also returns strategy name, params)
```

## Healing Reports

### Automatic Report Generation

After each test, optionally save healing report:

```python
@pytest.fixture(autouse=True)
def healing_report(app):
    page = MyAppPage(app)
    yield page
    if page.healed_count > 0:
        page.save_healing_report(test_name="test_save_document")
```

### Report Format

JSON file with all healing attempts:

```json
{
  "test": "test_save_document",
  "total_heals": 2,
  "healing_attempts": [
    {
      "original": {
        "strategy": "by_id",
        "params": {"auto_id": "SaveButton"}
      },
      "fallback": {
        "strategy": "by_name",
        "params": {"name": "Save"}
      },
      "success": true,
      "error": null
    },
    {
      "original": {
        "strategy": "by_id",
        "params": {"auto_id": "TextEditor"}
      },
      "fallback": {
        "strategy": "by_descendant_id",
        "params": {"auto_id": "TextEditor"}
      },
      "success": true,
      "error": null
    }
  ]
}
```

### Accessing Healing Statistics

```python
def test_save_document(app):
    page = MyAppPage(app)
    
    # ... test code ...
    
    # Check healing statistics
    print(f"Successful heals: {page.healed_count}")
    print(f"Total attempts: {page.total_healing_attempts}")
    print(f"Healing history: {page.healing_history}")
```

## Healing Strategy Fallback Chains

### Strategy 1: ID-First (Recommended)

```python
by_id_with_fallback('SaveButton')
↓ (if fails)
by_name('SaveButton')
↓ (if fails)
by_descendant_id('SaveButton')
↓ (if fails)
LookupError
```

**Best for:** Stable controls with guaranteed AutomationIds

### Strategy 2: Name-First

```python
by_name_with_fallback('Save')
↓ (if fails)
by_id('Save')
↓ (if fails)
by_descendant_name('Save')
↓ (if fails)
LookupError
```

**Best for:** User-facing controls where Name is more stable

### Strategy 3: Class+Index (Last Resort)

```python
by_class_with_fallback('Edit', index=0)
↓ (if fails)
by_name('Edit')
↓ (if fails)
by_id('Edit')
↓ (if fails)
LookupError
```

**Best for:** Generic controls without unique IDs/Names

## Understanding Healing Events

### Success Event

```python
{
  "original": {"strategy": "by_id", "params": {"auto_id": "OldID"}},
  "fallback": {"strategy": "by_name", "params": {"name": "Button"}},
  "success": true,
  "error": null
}
```

**Action:** Test continues with fallback strategy. Review and decide:
- **Update locator** in page object to use `by_name_with_fallback`
- **Add permanent fallback** if UI structure is unstable
- **Monitor** in next runs

### Failure Event

```python
{
  "original": {"strategy": "by_id", "params": {"auto_id": "MissingButton"}},
  "fallback": {"strategy": "by_name", "params": {"name": "MissingButton"}},
  "success": false,
  "error": "LookupError: Expected one..."
}
```

**Action:** Control truly missing or moved. Options:
- **Inspect live app** with Accessibility Insights
- **Update AutomationId** in app or test
- **Report to dev team** if UI changed
- **Re-run exploration** to get fresh model

## Best Practices

### 1. Start with Most Specific Locator

```python
# Good: Most specific first
return self.by_id_with_fallback('UniqueButtonID')

# Less good: Generic first
return self.by_class_with_fallback('Button', index=0)
```

### 2. Keep Fallback Chains Short

```python
# Good: 2-3 fallbacks
by_id_with_fallback('SaveButton')

# Avoid: Too many fallbacks (slower recovery)
def overly_complex():
    return self._try_strategies('by_id', {...}, [
        ('by_name', {...}),
        ('by_descendant_id', {...}),
        ('by_class', {...}),
        ('by_ancestor', {...}),  # Too many
    ])[0]
```

### 3. Document Why Healing Is Needed

```python
@property
def status_label(self):
    """Status label - uses Name fallback.
    
    Why healing: AutomationId can change with app version.
    Name 'Status' is more stable. Healing captures changes
    for analysis.
    """
    return self.by_name_with_fallback('Status')
```

### 4. Review Healing Reports After Changes

When app updates, check healing reports:

```powershell
# List all recent healing attempts
Get-ChildItem artifacts/healing/*.json | 
  ForEach-Object { Write-Host ""; Get-Content $_ }

# Count healed controls
Get-ChildItem artifacts/healing/*.json | 
  ForEach-Object { Select-String '"success": true' $_ } | 
  Measure-Object
```

### 5. Update Locators Based on Patterns

After reviewing healing reports, update stable patterns:

```python
# If healing shows by_name always succeeds:
# Change this:
return self.by_id_with_fallback('OldID')

# To this:
return self.by_name_with_fallback('Status Label')
```

## Healing Workflow

### Step 1: Enable Healing in Page Object

```python
from core.self_healing_element import SelfHealingUIElement

class MyAppPage(SelfHealingUIElement):
    @property
    def save_button(self):
        return self.by_id_with_fallback('SaveButton')
```

### Step 2: Run Tests Normally

```powershell
pytest tests/test_myapp.py -v
```

### Step 3: Check Healing Reports

```powershell
# After test run
Get-ChildItem artifacts/healing/test_*.json | 
  ForEach-Object { Get-Content $_ | ConvertFrom-Json }
```

### Step 4: Analyze and Decide

For each healing event, decide:

| Event | Decision | Action |
|-------|----------|--------|
| Success | Add permanent fallback | Update page object to `by_name_with_fallback` |
| Success | Inspect and confirm | No action if one-time glitch |
| Failure | Control missing | Inspect live app, update locator |
| Failure | UI changed | Re-run exploration, regenerate tests |

### Step 5: Update Page Object

```python
# Before (ID-based, fails occasionally)
@property
def status_label(self):
    return self.by_id_with_fallback('Status')

# After (Name-based, more stable)
@property
def status_label(self):
    return self.by_name_with_fallback('Status Label')
```

### Step 6: Re-run and Verify

```powershell
# Remove old healing logs
Remove-Item artifacts/healing/*.json

# Re-run tests
pytest tests/test_myapp.py -v

# Verify no healing occurred (if changes were effective)
Get-ChildItem artifacts/healing/*.json
```

## Troubleshooting

### "LookupError: All locator strategies failed"

**Cause:** Control not found by any strategy

**Solutions:**
1. Verify control exists in live app
2. Check AutomationId/Name spelling (case-sensitive)
3. Inspect with Accessibility Insights to get correct values
4. Control may be in a dialog or sub-window

### Healing logs not created

**Cause:** No healing occurred or logging disabled

**Solutions:**
1. Verify test has healing events (page.healed_count > 0)
2. Check healing_log_dir exists and is writable
3. Call save_healing_report() explicitly

### Too many healing events (performance impact)

**Cause:** Overly generic locators or unstable UI

**Solutions:**
1. Use more specific locators (by_id before by_class)
2. Inspect UI for unique AutomationIds
3. Report stability issues to dev team
4. Add waits before locating (UI might not be ready)

### Healing changes correct behavior (false positives)

**Cause:** Fallback strategy finds wrong control

**Solutions:**
1. Make primary locator more specific
2. Add additional criteria (control_type, class_name)
3. Use more restricted scoping (search within window, not descendants)

```python
# Too generic - might find wrong button
self.by_name_with_fallback('OK')

# Better - add specificity
def ok_button(self):
    dialog = self._foreground_owned_dialog()
    return dialog.child_window(title='OK', control_type='Button')
```

## Monitoring and Metrics

### Generate Healing Summary

```python
def analyze_healing_reports():
    """Summarize healing attempts across all tests."""
    from pathlib import Path
    import json
    
    healing_dir = Path('artifacts/healing')
    total_attempts = 0
    successful_heals = 0
    failed_heals = 0
    strategies_used = {}
    
    for report_file in healing_dir.glob('*.json'):
        report = json.loads(report_file.read_text())
        for attempt in report['healing_attempts']:
            total_attempts += 1
            strategy = attempt['fallback']['strategy']
            strategies_used[strategy] = strategies_used.get(strategy, 0) + 1
            
            if attempt['success']:
                successful_heals += 1
            else:
                failed_heals += 1
    
    print(f"Total healing attempts: {total_attempts}")
    print(f"Successful: {successful_heals}")
    print(f"Failed: {failed_heals}")
    print(f"Strategies used: {strategies_used}")
```

## Advanced: Custom Healing Strategies

For specialized apps, implement custom healing:

```python
class CustomPage(SelfHealingUIElement):
    def by_property_path(self, path):
        """Custom strategy: find by object property path."""
        # Implementation for custom locator
        pass

    def custom_control(self):
        """Custom control with multi-step healing."""
        strategies = [
            ('by_id', {'auto_id': 'UniqueName'}),
            ('by_property_path', {'path': 'App.MainWindow.SaveButton'}),
            ('by_name', {'name': 'Save'}),
        ]
        return self._try_strategies('by_id', {...}, strategies[1:])[0]
```

## See Also

- **AUTOGEN_GUIDE.md** - Test generation system
- **GENERATION_STANDARDS.md** - Framework standards
- **core/self_healing_element.py** - Implementation source
- **UI Exploration** - `explore_windows.py` reference

