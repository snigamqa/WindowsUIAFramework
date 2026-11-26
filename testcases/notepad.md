# Notepad smoke and document workflows

## App
- Product: Windows Notepad
- EXE path: `C:\Windows\System32\notepad.exe` (set `APP_PATH`)
- Backend: UIA (`APP_BACKEND=uia`)
- Isolation: each test creates a blank Notepad tab and closes only that test tab, leaving pre-existing tabs open
- Test data: temporary strings and files under pytest's `tmp_path`

## Test case: Opening a blank Notepad editor (id: NOTEPAD-001, tag: smoke)
- Oracle: inferred
1. Create a new blank Notepad tab without changing existing tabs.
2. Verify the Text editor control is visible.
3. Expected: the editor contains no text.

## Test case: Entering and reading editor text (id: NOTEPAD-002, tag: smoke)
- Oracle: inferred
1. Enter a known string in the Text editor.
2. Read the editor text.
3. Expected: the editor text equals the entered string.

## Test case: Undoing and redoing an editor change (id: NOTEPAD-003, tag: smoke)
- Oracle: inferred
1. Enter a known string in the Text editor.
2. Undo the edit.
3. Redo the edit.
4. Save the document under pytest's temporary directory.
5. Expected: the entered string is restored.

## Test case: Keeping text independent across tabs (id: NOTEPAD-004, tag: smoke)
- Oracle: inferred
1. Enter and save text in the first tab.
2. Add a new tab.
3. Enter and save different text in the new tab.
4. Select each tab in turn.
5. Expected: each tab retains its own saved text.

## Test case: Saving a document to a temporary file (id: NOTEPAD-005, tag: smoke)
- Oracle: inferred
1. Enter a known string in the Text editor.
2. Save the document to a path under pytest's temporary directory.
3. Expected: the saved file contains exactly the entered string.

## Test case: Opening a temporary text file (id: NOTEPAD-006, tag: smoke)
- Oracle: inferred
1. Create a text file under pytest's temporary directory.
2. Open the file in Notepad.
3. Expected: the editor displays the file contents.
