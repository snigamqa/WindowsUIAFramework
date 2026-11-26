import datetime
import os
from pathlib import Path
import re
import subprocess
import time

import psutil
import pytest
from pywinauto import Desktop

from config import APP_BACKEND, APP_PATH, ARTIFACT_DIR, LAUNCH_TIMEOUT
from pages.notepad_page import NotepadPage

pytestmark = pytest.mark.smoke


def _notepad_windows():
    windows = []
    for window in Desktop(backend="uia").windows():
        try:
            if (
                window.is_visible()
                and psutil.Process(window.process_id()).name().casefold()
                == "notepad.exe"
                and window.element_info.class_name == "Notepad"
            ):
                windows.append(window)
        except (psutil.Error, OSError):
            continue
    return windows


def _wait_for_notepad_window(timeout):
    deadline = time.monotonic() + timeout
    windows = []
    while time.monotonic() < deadline:
        windows = _notepad_windows()
        if windows:
            return windows
        time.sleep(0.2)
    raise TimeoutError("Notepad did not expose a visible UI Automation window")


def _open_isolated_window():
    if APP_BACKEND != "uia":
        pytest.fail("The Notepad suite requires APP_BACKEND=uia")
    if not APP_PATH or Path(APP_PATH).name.casefold() != "notepad.exe":
        pytest.fail("Set APP_PATH to the installed notepad.exe executable")

    host_windows = _notepad_windows()
    if not host_windows:
        if not Path(APP_PATH).is_file():
            pytest.fail(f"Notepad executable not found: {APP_PATH}")
        subprocess.Popen([APP_PATH])
        host_windows = _wait_for_notepad_window(LAUNCH_TIMEOUT)

    host_windows = [window for window in host_windows if window.is_enabled()]
    if not host_windows:
        pytest.fail(
            "No enabled Notepad window is available; dismiss any modal dialog first"
        )

    page = NotepadPage(host_windows[0])
    original_tab_count = page.tab_count
    page.add_tab()
    try:
        page.wait_until(
            lambda: page.tab_count == original_tab_count + 1,
            timeout=LAUNCH_TIMEOUT,
        )
        page.wait_visible(page.editor)
        if page.text:
            raise RuntimeError(
                "The new Notepad test tab was not blank; refusing to use its contents"
            )
    except Exception:
        if page.tab_count > original_tab_count:
            page.close_test_tabs(original_tab_count)
        raise
    return page, original_tab_count


def _capture_case_evidence(page, case_id):
    evidence = Path(ARTIFACT_DIR) / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", case_id)
    page.window.capture_as_image().save(evidence / f"{safe_id}_{stamp}.png")


@pytest.fixture
def notepad_page():
    page, original_tab_count = _open_isolated_window()
    try:
        yield page
    finally:
        page.close_test_tabs(original_tab_count)


@pytest.mark.case(
    id="NOTEPAD-001",
    title="Opening a blank Notepad editor",
)
def test_notepad_opens_with_blank_editor(notepad_page):
    assert notepad_page.editor.is_visible()
    assert notepad_page.text == ""
    _capture_case_evidence(notepad_page, "NOTEPAD-001")


@pytest.mark.case(
    id="NOTEPAD-002",
    title="Entering and reading editor text",
)
def test_editor_accepts_and_reads_text(notepad_page, tmp_path):
    expected = "Notepad automation sample"

    notepad_page.enter_text(expected)

    assert notepad_page.text == expected
    notepad_page.save_as(tmp_path / "editor-text.txt")
    _capture_case_evidence(notepad_page, "NOTEPAD-002")


@pytest.mark.case(
    id="NOTEPAD-003",
    title="Undoing and redoing an editor change",
)
def test_undo_and_redo_update_document(notepad_page, tmp_path):
    expected = "Undo and redo sample"
    notepad_page.enter_text(expected)

    notepad_page.window.type_keys("^z")
    assert notepad_page.text == ""

    notepad_page.window.type_keys("^y")
    assert notepad_page.text == expected
    notepad_page.save_as(tmp_path / "undo-redo.txt")
    _capture_case_evidence(notepad_page, "NOTEPAD-003")


@pytest.mark.case(
    id="NOTEPAD-004",
    title="Keeping text independent across tabs",
)
def test_tabs_keep_document_text_independent(notepad_page, tmp_path):
    first_text = "First tab text"
    second_text = "Second tab text"
    first_path = tmp_path / "first-tab.txt"
    second_path = tmp_path / "second-tab.txt"

    notepad_page.enter_text(first_text)
    notepad_page.save_as(first_path)
    notepad_page.add_tab()
    assert notepad_page.tab_count == 2
    assert notepad_page.text == ""

    notepad_page.enter_text(second_text)
    notepad_page.save_as(second_path)
    notepad_page.select_tab_containing(first_path.name)
    assert notepad_page.text == first_text
    notepad_page.select_tab_containing(second_path.name)
    assert notepad_page.text == second_text
    _capture_case_evidence(notepad_page, "NOTEPAD-004")


@pytest.mark.case(
    id="NOTEPAD-005",
    title="Saving a document to a temporary file",
)
def test_save_as_persists_text_to_temporary_file(notepad_page, tmp_path):
    expected = "Temporary Notepad save"
    target = tmp_path / "saved-note.txt"
    notepad_page.enter_text(expected)

    notepad_page.save_as(target)

    assert target.read_text(encoding="utf-8-sig") == expected
    _capture_case_evidence(notepad_page, "NOTEPAD-005")


@pytest.mark.case(
    id="NOTEPAD-006",
    title="Opening a temporary text file",
)
def test_open_displays_temporary_file_contents(notepad_page, tmp_path):
    expected = "Temporary Notepad open"
    source = tmp_path / "source-note.txt"
    source.write_text(expected, encoding="utf-8")

    notepad_page.open_file(source, expected)

    assert notepad_page.text == expected
    _capture_case_evidence(notepad_page, "NOTEPAD-006")
