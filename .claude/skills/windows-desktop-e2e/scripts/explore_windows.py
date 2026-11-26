#!/usr/bin/env python3
"""Explore a Windows desktop application through UI Automation and write app-model.json.

Run on Windows (test VM recommended):
    pip install pywinauto pillow
    python explore_windows.py --exe "C:\\Path\\App.exe" --out model --traverse --max-screens 40

Safety:
  * Without --traverse only a passive snapshot of the main window is taken.
  * With --traverse it clicks navigation controls (tabs, menu items, tree items, hyperlinks).
  * --click-buttons also clicks buttons, except those whose names look risky (see DENY).
  * Controls skipped for safety are listed under "skipped" in the output.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import time

DENY = re.compile(
    r"(delete|remove|uninstall|format|reset|erase|wipe|log ?out|sign ?out|exit|quit|close|"
    r"pay|purchase|buy|send|submit|publish|overwrite|clear all|factory|shutdown|restart)",
    re.I,
)
NAV_TYPES = {"TabItem", "MenuItem", "TreeItem", "Hyperlink"}
BUTTON_TYPES = {"Button", "SplitButton"}
INTERACTIVE = {
    "Button", "SplitButton", "Edit", "ComboBox", "CheckBox", "RadioButton", "Slider",
    "Spinner", "TabItem", "MenuItem", "TreeItem", "ListItem", "DataItem", "Hyperlink",
    "Document", "ScrollBar", "Thumb", "ToggleButton",
}
MAX_CONTROLS_PER_SCREEN = 1500


def safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def describe(el):
    info = el.element_info
    rect = safe(lambda: info.rectangle)
    return {
        "control_type": safe(lambda: info.control_type, "") or "",
        "name": safe(lambda: info.name, "") or "",
        "automation_id": safe(lambda: info.automation_id, "") or "",
        "class_name": safe(lambda: info.class_name, "") or "",
        "enabled": bool(safe(el.is_enabled, True)),
        "visible": bool(safe(el.is_visible, True)),
        "rect": [rect.left, rect.top, rect.right, rect.bottom] if rect else None,
    }


def fingerprint(controls):
    key = sorted(
        (c["control_type"], c["name"], c["automation_id"])
        for c in controls if c["control_type"] in INTERACTIVE
    )
    return hashlib.sha1(json.dumps(key).encode("utf-8")).hexdigest()[:12]


def snapshot(window, screen_id, title, path, kind, shots_dir, wrappers_out=None):
    controls = []
    for i, el in enumerate(safe(window.descendants, []) or [], start=1):
        if i > MAX_CONTROLS_PER_SCREEN:
            break
        d = describe(el)
        if not d["visible"]:
            continue
        d["id"] = "CTL-%s-%02d" % (screen_id.split("-")[1], len(controls) + 1)
        d["interactive"] = d["control_type"] in INTERACTIVE
        controls.append(d)
        if wrappers_out is not None:
            wrappers_out[d["id"]] = el
    shot_rel = None
    try:
        os.makedirs(shots_dir, exist_ok=True)
        shot_rel = os.path.join("shots", screen_id + ".png")
        window.capture_as_image().save(os.path.join(os.path.dirname(shots_dir), shot_rel))
    except Exception:
        shot_rel = None
    return {
        "id": screen_id, "title": title, "kind": kind, "path": path,
        "screenshot": shot_rel, "fingerprint": fingerprint(controls), "controls": controls,
    }


def main_window(app, timeout):
    win = app.top_window()
    win.wait("exists visible", timeout=timeout)
    return win


def process_windows(desktop, pid):
    return safe(lambda: desktop.windows(process=pid), []) or []


def close_dialog(dlg):
    safe(lambda: dlg.type_keys("{ESC}"))
    time.sleep(0.5)
    if safe(dlg.exists, False):
        for label in ("Cancel", "Close", "No", "OK"):
            btn = safe(lambda: dlg.child_window(title=label, control_type="Button"))
            if btn is not None and safe(btn.exists, False):
                safe(btn.click_input)
                time.sleep(0.5)
                break


def candidates(controls, click_buttons):
    out, skipped = [], []
    for c in controls:
        if not c["enabled"] or not c["name"]:
            continue
        ctype = c["control_type"]
        wanted = ctype in NAV_TYPES or (click_buttons and ctype in BUTTON_TYPES)
        if not wanted:
            continue
        if DENY.search(c["name"]):
            skipped.append({"control": c["id"], "name": c["name"], "reason": "risky name"})
            continue
        out.append(c)
    return out, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--exe", help="Path to the application executable to launch")
    src.add_argument("--title-re", help="Regex of an already running window title to attach to")
    ap.add_argument("--out", default="model", help="Output folder")
    ap.add_argument("--traverse", action="store_true", help="Click navigation controls to discover more screens")
    ap.add_argument("--click-buttons", action="store_true", help="Also click non-risky buttons (use with care)")
    ap.add_argument("--max-screens", type=int, default=40)
    ap.add_argument("--wait", type=float, default=1.0, help="Seconds to wait after each click")
    ap.add_argument("--launch-timeout", type=int, default=30)
    ap.add_argument("--backend", choices=("uia", "win32"), default="uia")
    args = ap.parse_args()

    if sys.platform != "win32":
        sys.exit("This explorer must run on Windows (pywinauto UI Automation).")
    try:
        from pywinauto import Application, Desktop
    except ImportError:
        sys.exit("Install dependencies first: pip install pywinauto pillow")

    os.makedirs(args.out, exist_ok=True)
    shots_dir = os.path.join(args.out, "shots")

    if args.exe:
        app = Application(backend=args.backend).start(args.exe)
    else:
        app = Application(backend=args.backend).connect(title_re=args.title_re)
    desktop = Desktop(backend=args.backend)
    win = main_window(app, args.launch_timeout)
    pid = app.process

    model = {
        "app": {
            "name": os.path.basename(args.exe) if args.exe else args.title_re,
            "exe": args.exe or "",
            "explored_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "backend": args.backend,
            "traversed": bool(args.traverse),
        },
        "screens": [], "transitions": [], "skipped": [],
    }
    seen = {}
    wrappers = {}

    def add_screen(window, title, path, kind):
        sid = "SCR-%03d" % (len(model["screens"]) + 1)
        w = {}
        scr = snapshot(window, sid, title, path, kind, shots_dir, w)
        if scr["fingerprint"] in seen:
            return seen[scr["fingerprint"]], False
        seen[scr["fingerprint"]] = scr["id"]
        wrappers[scr["id"]] = w
        model["screens"].append(scr)
        return scr["id"], True

    main_title = safe(win.window_text, "Main") or "Main"
    root_id, _ = add_screen(win, main_title, [main_title], "window")
    print("Snapshot of main window: %s (%d controls)" % (
        root_id, len(model["screens"][0]["controls"])))

    if args.traverse:
        queue = [root_id]
        clicked = set()
        while queue and len(model["screens"]) < args.max_screens:
            sid = queue.pop(0)
            screen = next(s for s in model["screens"] if s["id"] == sid)
            cands, skipped = candidates(screen["controls"], args.click_buttons)
            for s in skipped:
                s["screen"] = sid
                model["skipped"].append(s)
            for c in cands:
                key = (c["control_type"], c["name"])
                if key in clicked or len(model["screens"]) >= args.max_screens:
                    continue
                clicked.add(key)
                el = wrappers.get(sid, {}).get(c["id"])
                if el is None:
                    continue
                before = {w.handle for w in process_windows(desktop, pid)}
                try:
                    el.click_input()
                except Exception as exc:
                    print("  could not click %s '%s': %s" % (c["control_type"], c["name"], exc))
                    continue
                time.sleep(args.wait)
                after = process_windows(desktop, pid)
                new = [w for w in after if w.handle not in before]
                if new:
                    dlg = new[0]
                    title = safe(dlg.window_text, "Dialog") or "Dialog"
                    new_id, is_new = add_screen(dlg, title, screen["path"] + [title], "dialog")
                    model["transitions"].append({"from": sid, "via": c["id"], "to": new_id})
                    close_dialog(dlg)
                else:
                    cur = main_window(app, 5)
                    title = "%s > %s" % (screen["title"], c["name"])
                    new_id, is_new = add_screen(cur, title, screen["path"] + [c["name"]], "view")
                    if new_id != sid:
                        model["transitions"].append({"from": sid, "via": c["id"], "to": new_id})
                if is_new:
                    queue.append(new_id)
                    print("  discovered %s via %s '%s'" % (new_id, c["control_type"], c["name"]))

    out_path = os.path.join(args.out, "app-model.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2, ensure_ascii=False)
    total = sum(len(s["controls"]) for s in model["screens"])
    missing = sum(1 for s in model["screens"] for c in s["controls"]
                  if c["interactive"] and not c["automation_id"])
    print("Wrote %s: %d screens, %d controls, %d interactive controls without AutomationId, %d skipped"
          % (out_path, len(model["screens"]), total, missing, len(model["skipped"])))


if __name__ == "__main__":
    main()
