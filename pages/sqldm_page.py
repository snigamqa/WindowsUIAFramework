from core.ui_element import UIElement


class SqlDmPage(UIElement):
    """Page object for the SQL Diagnostic Manager main window.

    SQL Diagnostic Manager (SQLdm) is an Idera database monitoring tool.
    Control locators are populated after inspecting the installed application's UIA tree.
    
    Typical main window contains:
    - Navigation pane (left sidebar with servers/databases)
    - Main content area (dashboard or detail view)
    - Toolbar (refresh, settings, etc.)
    - Status bar (connection status, notifications)
    """

    @property
    def title(self):
        """Get the main window title."""
        return self.window.wrapper_object().window_text()

    def is_visible(self):
        """Check if the main window is visible and responsive."""
        return self.window.exists(timeout=1)

    @property
    def is_enabled(self):
        """Check if the application is enabled and responsive."""
        try:
            return self.window.is_enabled()
        except Exception:
            return False

    def get_status_bar_text(self):
        """Get the status bar message (if available).
        
        Returns:
            str: Status bar text, or empty string if not found
        """
        try:
            status_bar = self.by_descendant_id("StatusBar", control_type="StatusBar")
            return self.get_text(status_bar)
        except LookupError:
            return ""

    def wait_for_connection(self, timeout=15):
        """Wait for SQLdm to establish a connection (not in error/busy state).
        
        Args:
            timeout: Maximum seconds to wait
            
        Raises:
            TimeoutError: If connection is not established within timeout
        """
        def is_ready():
            status = self.get_status_bar_text().lower()
            return "connected" in status or ("error" not in status and "busy" not in status)
        
        self.wait_until(is_ready, timeout=timeout)
