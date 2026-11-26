# Deriving test cases from an app model

Work screen by screen. For each control type, apply the rules below, then add flow cases across screens. Give every case an ID, control links, and an `oracle` level. Prefer fewer, sharper cases over exhaustive combinations, and put anything needing human judgment in `automation: manual`.

## By control type

| Control | Cases to derive |
|---|---|
| Edit / text box | accepts valid text; empty value (if it looks required); max length (try length+1); leading/trailing spaces; special characters and unicode; very long paste; value persists after tab-away; read-only fields reject typing |
| Password | masked display; empty rejected; wrong value rejected; no value in logs or screenshots |
| Button | enabled/disabled state matches preconditions; click produces the expected visible change; double-click does not duplicate the action; keyboard activation (Enter or Space) |
| Check box / radio | default state; toggle on and off; radio group is mutually exclusive; state persists after reopening the screen |
| Combo box / list | options present and in expected order; selecting an option updates dependent controls; no selection handled; keyboard selection |
| Tab / menu / tree | each item opens its content; the selected item is indicated; returning to a tab keeps its state |
| Data grid / table | headers present; sorting (if offered); row selection; empty state; long text truncation; scroll to end |
| Dialog | opens from its trigger; cancel and close discard changes; OK commits; Escape closes; focus returns to the caller |
| Slider / spinner / date | min and max bounds; step; out-of-range typed values; invalid date formats |
| Menu / shortcut | every shortcut shown in a menu works; disabled items are not actionable |

## Cross-cutting categories

- **Smoke**: app launches within a time limit, main window title correct, every top-level tab or menu opens, app exits cleanly. Keep to 5 to 10 cases.
- **Validation and boundary**: for each input, valid, empty, at limit, past limit, wrong type.
- **Negative and error handling**: server unreachable (only if the test environment can simulate it), invalid file, missing permission. Mark `manual` if it needs environment manipulation that has not been provided.
- **Navigation and state**: back/forward behavior, unsaved-change prompts, state after switching screens.
- **Persistence**: change a setting, close and reopen the app, confirm it persisted. Restore the original value in teardown.
- **Keyboard and accessibility**: Tab order visits controls in a sensible order, every interactive control reachable by keyboard, controls expose a Name to UI Automation (a missing name is itself a finding).
- **UI integrity**: labels not truncated, expected default focus, disabled controls actually disabled.
- **Flow**: the 3 to 5 business-critical end-to-end journeys the user named in the review checkpoint. These get the highest priority.

## Priorities

- High: smoke, business-critical flows, anything that blocks the main journey.
- Medium: validation, persistence, navigation on main screens.
- Low: cosmetic checks, rare dialogs, deep keyboard paths.

## Writing expected results

State something the test can check: a control's text, enabled state, a window appearing or closing, a value read back. Avoid "works correctly". When exploration observed the result, write exactly what was observed and set `oracle: observed`. When writing from a manual case, use its expected text and set `oracle: spec`.

## Things not to automate by default

Visual layout judgment, printing, hardware devices, installers on a machine you cannot reset, anything requiring real payments or messages, captchas and MFA.
