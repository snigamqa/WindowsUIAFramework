from pathlib import Path
import re

from core.ui_element import UIElement
from pywinauto import Desktop
import win32con
import win32gui
import win32process


class NotepadPage(UIElement):
    """Page object for a single, isolated Notepad window."""

    @property
    def editor(self):
        return self.by_descendant_name("Text editor", control_type="Document")

    @property
    def text(self):
        return self.get_text(self.editor)

    @property
    def tab_names(self):
        return [
            tab.element_info.name
            for tab in self.window.descendants(control_type="TabItem")
            if tab.is_visible()
        ]

    @property
    def tab_count(self):
        return len(self.tab_names)

    def enter_text(self, value):
        self.type_text(self.editor, value)

    def add_tab(self):
        self.by_descendant_id(
            "AddButton", control_type="Button"
        ).invoke()

    def select_tab_containing(self, text):
        matches = [
            tab for tab in self.window.descendants(control_type="TabItem")
            if text.casefold() in tab.element_info.name.casefold()
        ]
        if len(matches) != 1:
            raise LookupError(
                f"Expected one Notepad tab containing {text!r}, found {len(matches)}"
            )
        matches[0].select()

    def _foreground_owned_dialog(self):
        test_handle = self.window.handle
        if not win32gui.IsWindow(test_handle):
            return None

        dialog_handle = win32gui.GetForegroundWindow()
        if (
            not win32gui.IsWindow(dialog_handle)
            or dialog_handle == test_handle
            or win32gui.GetClassName(dialog_handle) != "#32770"
        ):
            return None

        _, dialog_pid = win32process.GetWindowThreadProcessId(dialog_handle)
        if dialog_pid != self.window.process_id():
            return None

        owner = dialog_handle
        while owner and owner != test_handle:
            owner = win32gui.GetWindow(owner, win32con.GW_OWNER)
        if owner != test_handle:
            return None

        return Desktop(backend="uia").window(handle=dialog_handle)

    def _wait_for_owned_dialog(self):
        self.wait_until(
            lambda: self._foreground_owned_dialog() is not None,
            timeout=15,
        )
        dialog = self._foreground_owned_dialog()
        if dialog is None:
            raise RuntimeError("The expected Notepad file dialog is not active")
        return dialog

    @staticmethod
    def _dialog_control(dialog, auto_id, control_type):
        matches = [
            item
            for item in dialog.descendants(control_type=control_type)
            if item.element_info.automation_id == auto_id
        ]
        if len(matches) != 1:
            raise LookupError(
                f"Expected one dialog control with AutomationId {auto_id!r}; "
                f"found {len(matches)}"
            )
        return matches[0]

    def _set_dialog_path(self, dialog, path):
        filename = self._dialog_control(dialog, "1001", "Edit")
        self.type_text(filename, str(path))
        entered_path = filename.get_value().strip('"')
        if Path(entered_path) != path:
            basename_matches = bool(entered_path) and Path(entered_path).name == path.name
            raise RuntimeError(
                "Notepad did not accept the requested file path "
                f"(value_present={bool(entered_path)}, "
                f"basename_matches={basename_matches}, "
                f"focused={filename.has_keyboard_focus()})"
            )

    def save_as(self, path):
        path = Path(path).resolve()
        self.window.set_focus()
        self.window.type_keys("^s")
        dialog = self._wait_for_owned_dialog()
        self._set_dialog_path(dialog, path)
        save = self._dialog_control(dialog, "1", "Button")
        self.wait_visible(save)
        save.invoke()
        self.wait_until(path.is_file, timeout=15)

    def open_file(self, path, expected_text):
        path = Path(path).resolve()
        self.window.set_focus()
        self.window.type_keys("^o")
        dialog = self._wait_for_owned_dialog()
        self._set_dialog_path(dialog, path)
        open_button = self._dialog_control(dialog, "1", "Button")
        self.wait_visible(open_button)
        open_button.invoke()
        self.wait_until(lambda: self.text == expected_text, timeout=15)

    def close_test_tabs(self, original_tab_count):
        dialog = self._foreground_owned_dialog()
        if dialog is not None:
            safe_buttons = [
                button
                for button in dialog.descendants(control_type="Button")
                if re.fullmatch(
                    r"(cancel|no|don't save|do not save|discard)",
                    button.element_info.name,
                    re.IGNORECASE,
                )
            ]
            if len(safe_buttons) != 1:
                raise RuntimeError(
                    "The isolated Notepad modal did not expose one unambiguous "
                    "cancel or discard action."
                )
            safe_buttons[0].click_input()
            self.wait_until(
                lambda: self._foreground_owned_dialog() is None,
                timeout=5,
            )

        while self.tab_count > original_tab_count:
            previous_count = self.tab_count
            selected_tabs = [
                tab
                for tab in self.window.descendants(control_type="TabItem")
                if tab.is_visible() and tab.is_selected()
            ]
            if len(selected_tabs) != 1:
                raise RuntimeError(
                    "Could not uniquely identify the active test tab for cleanup."
                )
            close_buttons = [
                button
                for button in selected_tabs[0].descendants(control_type="Button")
                if button.element_info.automation_id == "CloseButton"
            ]
            if len(close_buttons) != 1:
                raise RuntimeError(
                    "The active Notepad tab did not expose one close button."
                )

            close_buttons[0].invoke()
            self.wait_until(
                lambda: self.tab_count < previous_count
                or self._foreground_owned_dialog() is not None,
                timeout=5,
            )
            dialog = self._foreground_owned_dialog()
            if dialog is not None:
                discard_buttons = [
                    button
                    for button in dialog.descendants(control_type="Button")
                    if re.fullmatch(
                        r"(don't save|do not save|discard)",
                        button.element_info.name,
                        re.IGNORECASE,
                    )
                ]
                if len(discard_buttons) != 1:
                    raise RuntimeError(
                        "The isolated Notepad tab did not expose one unambiguous "
                        "discard action."
                    )
                discard_buttons[0].click_input()

            self.wait_until(
                lambda: self.tab_count == previous_count - 1,
                timeout=10,
            )

        if self.tab_count != original_tab_count:
            raise RuntimeError(
                "Notepad tab cleanup would require closing a pre-existing tab."
            )
