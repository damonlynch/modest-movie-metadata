# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

from functools import cache
from importlib.resources import files
from pathlib import Path

import qtpy

from .. import data


@cache
def pyqt_api() -> bool:
    return qtpy.API_NAME.startswith("PyQt")


def program_icon_path() -> str:
    # Icon created by Smashicons - Flaticon
    # https://www.flaticon.com/free-icon/letter-m_6431117
    return str(files(data).joinpath("letter-m.png"))


def video_folder_path() -> str:
    # Icon created by Smashicons - Flaticon
    # https://www.flaticon.com/free-icon/video_6302563
    return str(files(data).joinpath("video.png"))


def data_file_path(data_file: str) -> Path:
    return files(data).joinpath(data_file)
