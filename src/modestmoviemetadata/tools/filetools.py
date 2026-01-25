# Copyright (c) 2022-2024 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

from pathlib import Path

from qtpy.QtCore import (
    QStandardPaths,
)

from ..config import application_name
from .logtools import get_logger

logger = get_logger()


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
