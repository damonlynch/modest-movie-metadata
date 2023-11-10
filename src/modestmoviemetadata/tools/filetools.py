# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

import sys
from pathlib import Path
from tempfile import gettempdir

try:
    import win32api
except ImportError:
    pass

from qtpy.QtCore import (
    QFileSystemWatcher,
    Slot,
    Signal,
    QObject,
    QStandardPaths,
    QTimer,
)

from ..config import application_name
from .logtools import get_logger

logger = get_logger()


def documents_directory(as_str=True) -> str | Path:
    path = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
    )
    if as_str:
        return str(path)
    else:
        return path


def downloads_directory() -> str:
    return str(
        Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.DownloadLocation
            )
        )
    )


def windows_appdata_directory() -> str:
    return str(
        Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.GenericConfigLocation
            )
        )
    )


def windows_user_profile_directory() -> str:
    return str(
        Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.HomeLocation
            )
        )
    )


def program_appdata_directory() -> Path | None:
    appdata_dir = Path(windows_appdata_directory()) / application_name
    if not appdata_dir.is_dir():
        try:
            appdata_dir.mkdir()
        except Exception as e:
            logger.exception(e)
            return None
    return appdata_dir


def edge_temp_download_directory() -> str:
    return str(Path(win32api.GetLongPathName(gettempdir())) / "MicrosoftEdgeDownloads")


def file_opened_by_another_process(check: Path) -> bool:
    if sys.platform.startswith("win"):
        if check.exists():
            try:
                check.rename(str(check))
            except OSError:
                return True
        return False
    raise "file_opened_by_another_process() not implemented on this platform"


def remove_temp_files(temp_files: list[Path, ...], description: str) -> None:
    logger.debug("Removing %s temporary %s files", len(temp_files), description)
    for temp_file in temp_files:
        if temp_file.is_file():
            try:
                temp_file.unlink()
                logger.debug("Removed %s", temp_file)
            except:
                logger.warning("Could not remove temp file %s", temp_file)
        else:
            logger.debug("Temp file was already removed: %s", temp_file)
