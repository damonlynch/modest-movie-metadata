# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

import logging
import sys
from logging.handlers import RotatingFileHandler
import gzip
import os
from pathlib import Path

try:
    import colorlog
except ImportError:
    colorlog = None

from ..config import logfile_name, application_name

logging_format = "%(levelname)s: %(message)s"
colored_logging_format = "%(log_color)s%(levelname)-8s%(reset)s %(message)s"
log_colors = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
}

logging_date_format = "%Y-%m-%d %H:%M:%S"
file_logging_format = "%(asctime)s %(levelname)s %(filename)s %(lineno)d: %(message)s"


class RotatingGzipFileHandler(RotatingFileHandler):
    def rotation_filename(self, name):
        return name + ".gz"

    def rotate(self, source, dest):
        with open(source, "rb") as sf:
            with gzip.open(dest, "wb") as df:
                df.writelines(sf)
        os.remove(source)


def get_program_logging_directory(appdata_dir: Path) -> Path | None:
    """
    Get directory in which to store program log files.

    Log files are kept in the program's appdata directory.

    :return: the Path of the logging directory, or None on error
    """

    if appdata_dir is None:
        logging.error("Unable to create logging directory %s", appdata_dir)
        return None

    log_dir = appdata_dir / "log"
    if log_dir.is_dir():
        return log_dir
    try:
        if log_dir.is_file():
            log_dir.unlink(missing_ok=True)
        log_dir.mkdir(0o700, exist_ok=True)
        return log_dir
    except Exception as e:
        logging.error("An error occurred while creating the log directory: %s", str(e))
    return None


def full_log_file_path(appdata_path: Path, alternate_path: Path) -> Path:
    log_file_path = get_program_logging_directory(appdata_dir=appdata_path)
    if log_file_path is not None:
        log_file = log_file_path / logfile_name
    else:
        # Problem: for some reason cannot create log file in standard location,
        # so create it in the home directory
        log_file = alternate_path / logfile_name
    return log_file


def setup_main_process_logging(
    appdata_path: Path, alternate_path: Path, logging_level: int
) -> logging.Logger:
    """
    Setup logging at the module level.

    :param appdata_path: primary program configuration directory
    :param alternate_path: alternate program configuration directory if primary fails
    :param logging_level: logging module's logging level for console output
    :return: default logging object
    """

    log_file = full_log_file_path(appdata_path, alternate_path)
    logger = get_logger()
    max_bytes = 1024 * 1024  # 1 MB
    filehandler = RotatingGzipFileHandler(
        str(log_file), maxBytes=max_bytes, backupCount=10, encoding = 'utf-8'
    )
    filehandler.setLevel(logging.DEBUG)
    filehandler.setFormatter(
        logging.Formatter(file_logging_format, logging_date_format)
    )
    logger.addHandler(filehandler)
    logger.setLevel(logging.DEBUG)

    consolehandler = logging.StreamHandler()
    consolehandler.set_name("console")
    if 'colorlog' in sys.modules:
        consolehandler.setFormatter(
            colorlog.ColoredFormatter(fmt=colored_logging_format, log_colors=log_colors)
        )
    else:
        consolehandler.setFormatter(logging.Formatter(logging_format))
    consolehandler.setLevel(logging_level)
    logger.addHandler(consolehandler)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(application_name)
