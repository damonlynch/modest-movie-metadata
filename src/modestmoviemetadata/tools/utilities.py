#  SPDX-FileCopyrightText: 2022-2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

import math
from functools import cache
from importlib.resources import files
from pathlib import Path

import qtpy

from modestmoviemetadata import data


@cache
def pyqt_api() -> bool:
    return qtpy.API_NAME.startswith("PyQt")


def program_icon_path() -> str:
    # Icon created by Smashicons - Flaticon
    # https://www.flaticon.com/free-icon/letter-m_6431117
    return str(files(data).joinpath("logo.png"))


def video_folder_path() -> str:
    # Icon created by Smashicons - Flaticon
    # https://www.flaticon.com/free-icon/video_6302563
    return str(files(data).joinpath("video.png"))


def data_file_path(data_file: str) -> Path:
    return files(data).joinpath(data_file)


def format_bytes(bytes_value: int) -> str:
    """
    Convert bytes to a human-readable format.

    >>> format_bytes(1049866240)
    '1001 MB'
    >>> format_bytes(1024)
    '1 KB'
    """
    if bytes_value == 0:
        return "0 B"

    # Standard labels for binary storage units
    units = ("B", "KB", "MB", "GB", "TB", "PB", "EB")

    # Calculate the base 1024 exponent index
    # e.g., 1024 -> index 1 (KB), 1048576 -> index 2 (MB)
    i = int(math.floor(math.log(bytes_value, 1024)))

    # Scale the bytes to the correct unit value
    p = math.pow(1024, i)
    scaled_value = bytes_value / p

    return f"{scaled_value:.0f} {units[i]}"


def format_bytes_fraction_gb(byte_value: int) -> str:
    """
    Convert bytes to quarter fractions of a gigabyte, rounding up or down

    >>> format_bytes_fraction_gb(1049866240)
    '1.0 GB'

    """
    # Convert bytes to binary gigabytes (GiB)
    gib_value = byte_value / (1024**3)
    # Round to the nearest 0.25
    return f"{round(gib_value / 0.25) * 0.25} GB"
