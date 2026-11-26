# SQL Diagnostic Manager smoke test

## App
- Product: Idera SQL Diagnostic Manager 14.3
- EXE path: installed SQLdm client executable (set `APP_PATH`; do not use the installation kit)
- Window title: set `APP_TITLE` after inspecting the installed client
- Backend: UIA by default; set `APP_BACKEND=win32` only if UIA cannot expose required controls
- Precondition: SQLdm is installed and any required server/database configuration is complete

## Test case: Opening the SQLdm main window (id: SQLDM-001, tag: smoke)
- Oracle: inferred
1. Verify SQLdm is installed on the system
2. Launch the installed SQLdm client executable
3. Wait for the main window to appear
4. Expected: main window is visible and its title matches `APP_TITLE` when configured

## Test case: SQLdm main window is enabled and responsive (id: SQLDM-002, tag: smoke)
- Oracle: inferred
1. Launch the installed SQLdm client executable
2. Wait for the main window to appear
3. Verify the window is enabled and not in a disabled state
4. Expected: the main window is visible, enabled, and responsive to user input

## Test case: SQLdm displays status information (id: SQLDM-003, tag: smoke)
- Oracle: inferred
1. Launch the installed SQLdm client executable
2. Wait for the main window to appear
3. Check the status bar for status or connection information
4. Expected: status bar is visible and contains readable information

