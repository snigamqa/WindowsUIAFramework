"""Base page/element wrapper: locators, waits, actions, artifacts.

Locator priority: AutomationId > Name (text) > ClassName+index (fragile).
Never use time.sleep() as primary synchronization — use the wait_* methods.
"""

import os
import sys
import time

from pywinauto import Desktop

from config import ACTION_TIMEOUT, ARTIFACT_DIR


class UIElement:
    def __init__(self, window):
        self.window = window

    # --- Locators ---

    def by_id(self, auto_id, **kw):
        """AutomationId — most stable. First choice."""
        return self.window.child_window(auto_id=auto_id, **kw)

    def by_name(self, name, **kw):
        """Visible text / accessible name."""
        return self.window.child_window(title=name, **kw)

    def by_descendant_id(self, auto_id, **kw):
        """AutomationId lookup for controls nested below the main window."""
        return self._unique_descendant(auto_id=auto_id, **kw)

    def by_descendant_name(self, name, **kw):
        """Accessible-name lookup for controls nested below the main window."""
        return self._unique_descendant(title=name, **kw)

    def _unique_descendant(self, auto_id=None, **criteria):
        matches = self.window.descendants(**criteria)
        if auto_id is not None:
            matches = [
                match
                for match in matches
                if match.element_info.automation_id == auto_id
            ]
        if len(matches) != 1:
            raise LookupError(
                "Expected one UIA descendant for "
                f"{criteria}, AutomationId={auto_id!r}; found {len(matches)}"
            )
        return matches[0]

    def by_class(self, cls, index=0, **kw):
        """Control class + index — fragile, avoid as primary strategy."""
        return self.window.child_window(class_name=cls, found_index=index, **kw)

    # --- Waits ---

    def wait_visible(self, spec, timeout=ACTION_TIMEOUT):
        wait = getattr(spec, "wait", None)
        if callable(wait):
            wait("visible", timeout=timeout)
        else:
            self.wait_until(spec.is_visible, timeout=timeout)
        return spec

    def wait_gone(self, spec, timeout=ACTION_TIMEOUT):
        wait_not = getattr(spec, "wait_not", None)
        if callable(wait_not):
            wait_not("visible", timeout=timeout)
        else:
            self.wait_until(lambda: not spec.is_visible(), timeout=timeout)
        return spec

    def wait_window(self, title, timeout=ACTION_TIMEOUT):
        """Wait for a new top-level window (dialogs, popups)."""
        dlg = Desktop(backend="uia").window(title=title)
        dlg.wait("visible", timeout=timeout)
        return dlg

    def wait_until(self, fn, timeout=ACTION_TIMEOUT, interval=0.3):
        """Poll an arbitrary condition — use when UIA events are unreliable."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if fn():
                    return True
            except Exception:
                pass
            time.sleep(interval)
        raise TimeoutError(f"Condition not met within {timeout}s")

    # --- Actions ---

    def click(self, spec):
        self.wait_visible(spec)
        spec.click_input()

    def type_text(self, spec, text):
        self.wait_visible(spec)
        wrapper_object = getattr(spec, "wrapper_object", None)
        ctrl = wrapper_object() if callable(wrapper_object) else spec
        try:
            set_edit_text = getattr(ctrl, "set_edit_text")
            set_edit_text(text)
        except Exception as e:
            # Qt 5.x / some RichEdit controls: UIA Value Pattern incomplete
            import pywinauto.keyboard as kb
            print(f"[windows-uia] set_edit_text failed ({e}), using keyboard fallback",
                  file=sys.stderr)
            ctrl.click_input()
            kb.send_keys("^a")
            kb.send_keys(text, with_spaces=True)

    def get_text(self, spec):
        wrapper_object = getattr(spec, "wrapper_object", None)
        ctrl = wrapper_object() if callable(wrapper_object) else spec
        for attr in ("window_text", "get_value"):
            try:
                v = getattr(ctrl, attr)()
                if v:
                    return v
            except Exception:
                pass
        return ""

    # --- Artifacts ---

    def screenshot(self, name):
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        path = os.path.join(ARTIFACT_DIR, f"{name}.png")
        self.window.capture_as_image().save(path)
        return path
