import logging
import sys
from pathlib import Path

from .config import app_guid, application_name
from .tools.filetools import program_appdata_directory, windows_user_profile_directory
from .tools.logtools import setup_main_process_logging
from .ui.mainwindow import MainWindow
from .ui.qtsingleapplication import QtSingleApplication

try:
    # Ensure the program's icon is displayed in the Windows taskbar
    from ctypes import windll

    myappid = "damonlynch.modest.movie.metadata.1"
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    myappid = None


def main():
    logging_level = logging.DEBUG
    logger = setup_main_process_logging(
        appdata_path=program_appdata_directory(),
        alternate_path=Path(windows_user_profile_directory()),
        logging_level=logging_level,
    )
    logger.debug("%s is starting", application_name)

    global app
    app = QtSingleApplication(app_guid, sys.argv)
    if app.isRunning():
        logger.warning(f"{application_name} is already running")
        sys.exit(0)

    app.setOrganizationName(application_name)
    app.setOrganizationDomain("damonlynch.net")
    app.setApplicationName(application_name)

    window = MainWindow()
    app.setActivationWindow(window)
    code = app.exec()
    logging.debug("Exiting")
    sys.exit(code)


if __name__ == "__main__":
    main()
