"""App lifecycle for Windows desktop E2E tests.

Launches the app under test as a subprocess with an isolated per-user data
directory (Tier 1: APPDATA/LOCALAPPDATA/TEMP redirect), optionally attached to
a Job Object (Tier 2: process-tree containment), and connects pywinauto over
UIA by PID.
"""

import ctypes
import ctypes.wintypes as wt
import os
import shlex
import subprocess
import time

import psutil
from pywinauto import Application, Desktop

from config import LAUNCH_TIMEOUT

# --- Tier 2: Windows Job Object (process-lifetime containment only) ---
# Job Objects do NOT virtualize filesystem access or block network traffic.

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
PROCESS_SET_QUOTA_AND_TERMINATE = 0x0101  # SET_QUOTA | TERMINATE


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", wt.LARGE_INTEGER),
        ("PerJobUserTimeLimit", wt.LARGE_INTEGER),
        ("LimitFlags", wt.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wt.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wt.DWORD),
        ("SchedulingClass", wt.DWORD),
    ]


def attach_job_object(pid):
    """Attach a process to a Job Object that kills it (and any children) when
    the job handle is closed. Returns the job handle — the caller must keep it
    alive for the process lifetime, then CloseHandle it."""
    kernel32 = ctypes.windll.kernel32
    job = kernel32.CreateJobObjectW(None, None)
    hproc = kernel32.OpenProcess(PROCESS_SET_QUOTA_AND_TERMINATE, False, pid)
    try:
        info = JOBOBJECT_BASIC_LIMIT_INFORMATION()
        info.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(job, 2, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError()
        if not kernel32.AssignProcessToJobObject(job, hproc):
            raise ctypes.WinError()
    finally:
        kernel32.CloseHandle(hproc)
    return job


def _close_handle(handle):
    try:
        ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass


def sandbox_env(work_dir):
    """Environment with per-user storage redirected into an isolated dir."""
    env = os.environ.copy()
    env["QT_ACCESSIBILITY"] = "1"  # required for Qt 5.x UIA support; harmless otherwise
    appdata = work_dir / "AppData" / "Roaming"
    localappdata = work_dir / "AppData" / "Local"
    temp = work_dir / "Temp"
    for p in (appdata, localappdata, temp):
        os.makedirs(p, exist_ok=True)
    env["APPDATA"] = str(appdata)
    env["LOCALAPPDATA"] = str(localappdata)
    env["TEMP"] = env["TMP"] = str(temp)
    return env


class AppHandle:
    """A launched app: raw process + pywinauto Application + main window spec."""

    def __init__(self, process, app, window, job=None):
        self.process = process
        self.app = app
        self.window = window
        self.job = job

    def close(self):
        # Graceful exit first, force-kill as fallback
        try:
            self.window.close()
            self.process.wait(timeout=5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        if self.job is not None:
            _close_handle(self.job)  # KILL_ON_JOB_CLOSE reaps any survivors


class DesktopDriver:
    """Launches apps and returns a connected pywinauto handle."""

    def launch(self, app_path, args="", title="", work_dir=None,
               timeout=LAUNCH_TIMEOUT, sandbox=True, use_job_object=True,
               backend="uia"):
        if backend not in {"uia", "win32"}:
            raise ValueError("backend must be 'uia' or 'win32'")
        if sandbox and work_dir is not None:
            env = sandbox_env(work_dir)
        else:
            env = os.environ.copy()
            env.setdefault("QT_ACCESSIBILITY", "1")
        arg_list = shlex.split(args, posix=False) if args else []
        arg_list = [arg.strip('"') for arg in arg_list]
        cmd = [app_path] + arg_list

        desktop = Desktop(backend=backend)
        existing_pids = {
            win.process_id()
            for win in desktop.windows()
            if win.is_visible()
        }
        proc = subprocess.Popen(cmd, env=env)

        job = None
        if use_job_object:
            try:
                job = attach_job_object(proc.pid)
            except Exception:
                job = None  # containment is best-effort; never block the launch

        deadline = time.monotonic() + timeout
        window = None
        while time.monotonic() < deadline:
            try:
                if title:
                    window = desktop.window(title_re=title)
                    window.wait("visible", timeout=1)
                    break

                candidates = [
                    win for win in desktop.windows()
                    if win.is_visible()
                    and win.process_id() not in existing_pids
                    and win.window_text()
                ]
                if candidates:
                    window = candidates[0]
                    break
            except Exception:
                pass
            time.sleep(0.2)

        if window is None:
            app_name = os.path.basename(app_path).casefold()
            for candidate in desktop.windows():
                try:
                    if not candidate.is_visible():
                        continue
                    candidate_pid = candidate.process_id()
                    candidate_exe = os.path.basename(
                        psutil.Process(candidate_pid).exe()
                    ).casefold()
                    if candidate_exe == app_name:
                        window = candidate
                        break
                except Exception:
                    pass

        if window is None:
            raise RuntimeError(
                f"No visible top-level UIA window appeared within {timeout}s"
            )

        if hasattr(window, "wrapper_object"):
            window_wrapper = window.wrapper_object()
        else:
            window_wrapper = window
        window_pid = window_wrapper.process_id()
        window_handle = window_wrapper.handle
        app = Application(backend=backend).connect(process=window_pid, timeout=timeout)
        window = app.window(handle=window_handle)
        return AppHandle(proc, app, window, job=job)
