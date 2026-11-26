import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Set APP_PATH to the installed application executable, not its installer kit.
# APP_TITLE is an optional regular expression for the main window title.
APP_PATH  = os.environ.get("APP_PATH", "")
APP_ARGS  = os.environ.get("APP_ARGS", "")
APP_TITLE = os.environ.get("APP_TITLE", "")
APP_BACKEND = os.environ.get("APP_BACKEND", "uia").casefold()

LAUNCH_TIMEOUT = int(os.environ.get("LAUNCH_TIMEOUT", "30"))
ACTION_TIMEOUT = int(os.environ.get("ACTION_TIMEOUT", "10"))
ARTIFACT_DIR   = os.path.join(BASE_DIR, "artifacts")
