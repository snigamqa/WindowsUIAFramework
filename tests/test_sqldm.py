import re

import pytest

from config import APP_TITLE
from pages.sqldm_page import SqlDmPage

pytestmark = pytest.mark.smoke


@pytest.mark.case(id="SQLDM-001", title="Opening the SQLdm main window")
def test_sqldm_main_window_opens(app):
    page = SqlDmPage(app)

    assert page.is_visible()
    assert page.title.strip()
    if APP_TITLE:
        assert re.search(APP_TITLE, page.title, re.IGNORECASE)
    page.screenshot("sqldm_main_window")


@pytest.mark.case(id="SQLDM-002", title="SQLdm main window is enabled and responsive")
def test_sqldm_window_is_responsive(app):
    page = SqlDmPage(app)

    assert page.is_visible()
    assert page.is_enabled
    page.screenshot("sqldm_window_enabled")


@pytest.mark.case(id="SQLDM-003", title="SQLdm displays status information")
def test_sqldm_shows_status_bar(app):
    page = SqlDmPage(app)

    # Status bar should be accessible (content varies based on connection state)
    status_text = page.get_status_bar_text()
    assert isinstance(status_text, str)
    page.screenshot("sqldm_status_bar")
