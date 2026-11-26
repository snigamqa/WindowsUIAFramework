import atexit
import contextlib
import datetime
import logging
import os
import re

import psutil
import pytest

from config import APP_ARGS, APP_BACKEND, APP_PATH, APP_TITLE, ARTIFACT_DIR
from core.desktop_driver import DesktopDriver
from core.test_case_catalog import load_case_catalog, validate_automated_cases

LOGGER = logging.getLogger(__name__)


def _case_id(node):
    marker = node.get_closest_marker("case")
    return marker.kwargs.get("id") if marker else None


def _reap_orphan_apps():
    # pytest-timeout's thread method cannot kill GUI subprocesses — reap on exit
    try:
        for child in psutil.Process().children(recursive=True):
            child.kill()
    except Exception:
        pass


atexit.register(_reap_orphan_apps)


@pytest.fixture(scope="function")
def driver(request, tmp_path):
    """Fresh app process per test with isolated user-data dirs (Tier 1)."""
    if not APP_PATH:
        pytest.exit("APP_PATH environment variable is not set", returncode=1)
    handle = DesktopDriver().launch(
        APP_PATH, args=APP_ARGS, title=APP_TITLE, work_dir=tmp_path,
        backend=APP_BACKEND,
    )
    yield handle

    if getattr(getattr(request.node, "rep_call", None), "failed", False):
        evidence_dir = os.path.join(ARTIFACT_DIR, "evidence")
        os.makedirs(evidence_dir, exist_ok=True)
        case_id = _case_id(request.node)
        stem = re.sub(
            r"[^A-Za-z0-9._-]+", "_", case_id or f"FAIL_{request.node.name}"
        )
        stem = f"{stem}_{datetime.datetime.now():%Y%m%d_%H%M%S_%f}"
        try:
            handle.window.capture_as_image().save(
                os.path.join(evidence_dir, f"{stem}.png")
            )
        except Exception as exc:
            LOGGER.warning("Could not save failure screenshot for %s: %s", request.node.nodeid, exc)
        try:
            with open(
                os.path.join(evidence_dir, f"{stem}_tree.txt"),
                "w",
                encoding="utf-8",
            ) as output:
                with contextlib.redirect_stdout(output):
                    handle.window.print_control_identifiers()
        except Exception as exc:
            LOGGER.warning("Could not save UI tree for %s: %s", request.node.nodeid, exc)
    handle.close()


@pytest.fixture(scope="function")
def app(driver):
    """Main window of the app under test (pywinauto window spec)."""
    return driver.window


@pytest.fixture(autouse=True)
def trace_case_id(request, record_property):
    case_id = _case_id(request.node)
    if case_id:
        record_property("tc_id", case_id)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    rep = yield
    setattr(item, f"rep_{rep.when}", rep)
    return rep


def pytest_collection_modifyitems(config, items):
    try:
        manual_cases = load_case_catalog(
            config.rootpath / "testcases",
            config.rootpath / "cases" / "test-cases.json",
        )
        validate_automated_cases(items, manual_cases)
    except ValueError as exc:
        raise pytest.UsageError(str(exc)) from exc
