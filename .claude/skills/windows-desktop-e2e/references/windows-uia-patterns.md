# Windows UI Automation patterns (pywinauto, UIA backend)

## Choosing the tool

| App technology | Tool |
|---|---|
| WPF, WinForms, UWP, WinUI, Qt (with accessibility on) | pywinauto `backend="uia"` (default here), or FlaUI if the team prefers C# |
| Win32 / MFC with poor UIA exposure | pywinauto `backend="win32"` |
| Electron, WebView2, CEF | Playwright for the web layer, UIA only for the native shell |
| Custom-drawn or legacy controls with an empty UIA tree | Ranorex, image matching only as a last resort |

Qt 5 needs the environment variable `QT_ACCESSIBILITY=1` before launch.

## Locator priority

1. `auto_id` (AutomationId)
2. `title` (Name) plus `control_type`
3. A short relative path from a stable parent
4. Never absolute coordinates or index-only lookups

Keep every locator in a page object. If the model shows controls with no AutomationId, list them for the developers and use Name plus ControlType in the meantime.

## Page object shape

```python
from pywinauto.timings import wait_until

class LoginPage:
    def __init__(self, window):
        self.w = window

    @property
    def user(self):
        return self.w.child_window(auto_id="txtUser", control_type="Edit")

    @property
    def login_button(self):
        return self.w.child_window(auto_id="btnLogin", control_type="Button")

    def login(self, user, password):
        self.user.wait("enabled visible", timeout=10).set_edit_text(user)
        self.w.child_window(auto_id="txtPassword", control_type="Edit").set_edit_text(password)
        self.login_button.wait("enabled", timeout=10).click_input()

    def error_text(self):
        err = self.w.child_window(auto_id="lblError", control_type="Text")
        err.wait("visible", timeout=5)
        return err.window_text()
```

## Waiting rules

- No `time.sleep` for synchronization. Use `.wait("exists enabled visible", timeout=...)`, `wait_until`, or a helper that polls for a condition and raises with a clear message.
- After launch, wait for the main window to be ready (splash gone, busy indicator gone) before the test body.
- After an action that triggers background work, wait for a completion signal: a status label, a progress bar disappearing, a control becoming enabled, or a log line.

## Test isolation

- Start each test from a known state: fresh launch, clean profile or config, seeded data through an API or database script rather than the UI.
- Kill leftover processes in teardown and confirm the app closed.
- Do not depend on test order.

## Environment rules

- Dedicated VM or machine, fixed resolution, fixed DPI scaling, fixed language and theme.
- Interactive, unlocked desktop session. Disable screensaver, sleep, OS updates and notifications.
- One test session per machine; parallelism needs separate VMs.

## Diagnostics on failure

Capture a screenshot, a UI tree dump (`window.print_control_identifiers()` to a file), and the app log. The conftest template saves the screenshot and tree dump under `results/evidence/<TC-ID>*`.

## Flakiness policy

- New test: 5 consecutive passes before merge. Regression gate: 20.
- One retry in CI is acceptable as a safety net, but a pass after retry is reported as flaky.
- A test that fails 1 in 20 runs is a defect in the test or the app, tracked and fixed.
