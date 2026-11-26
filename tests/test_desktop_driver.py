import pytest

from core.desktop_driver import DesktopDriver

pytestmark = pytest.mark.framework


def test_desktop_driver_rejects_unsupported_backend():
    with pytest.raises(ValueError, match="backend must be 'uia' or 'win32'"):
        DesktopDriver().launch("application.exe", backend="unsupported")
