#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from qtpy.QtCore import QUrl, SignalInstance

from modestmoviemetadata.config import imdb_dataset_url
from modestmoviemetadata.tools.filetools import (
    imdb_db_path,
    program_appdata_directory,
    standard_temp_directory,
)
from modestmoviemetadata.tools.imdbsqlite import create_db
from modestmoviemetadata.tools.logtools import get_logger
from modestmoviemetadata.tools.utilities import format_bytes

logger = get_logger()


def download_needed(path: Path, url: str) -> bool:
    # Does the file already exist?
    if not path.is_file():
        return True

    # Get file modification time in UTC
    local_mtime_timestamp = path.stat().st_mtime
    local_dt = datetime.fromtimestamp(local_mtime_timestamp, tz=UTC)

    response = requests.head(url, timeout=5)
    web_mtime_str = response.headers.get("Last-Modified")

    if not web_mtime_str:
        logger.warning(
            "Server did not provide a Last-Modified header for %s. "
            "Cannot compare file date and time.",
            url,
        )
        return True

    # Convert web timestamp to a timezone-aware datetime object
    web_dt = parsedate_to_datetime(web_mtime_str)

    # Compare timestamps (Stripping microseconds for a perfectly clean comparison)
    local_dt_clean = local_dt.replace(microsecond=0)
    web_dt_clean = web_dt.replace(microsecond=0)

    logger.debug("Local File Time (UTC): %s", local_dt_clean)
    logger.debug("Web Server Time (UTC): %s", web_dt_clean)

    return web_dt_clean > local_dt_clean


def do_download(
    url: str, name: str, path: Path, progress_callback: SignalInstance
) -> None:
    logger.debug("Downloading %s", name)

    with requests.get(url, stream=True, timeout=15) as response:
        response.raise_for_status()

        # Fetch total file size and file modification time from response header
        total_size = int(response.headers.get("content-length", 0))
        downloaded_size = 0
        web_mtime_str = response.headers.get("Last-Modified")

        progress_callback.emit(
            (
                f"Downloading IMDb dataset ({format_bytes(total_size)})...",
                0,
                total_size,
            )
        )
        with tempfile.TemporaryDirectory(dir=standard_temp_directory()) as temp_dir:
            temp_path = Path(temp_dir) / name
            with open(temp_path, "wb") as f:
                logger.debug("Saving temporary download to %s", temp_path)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress_callback.emit(("", downloaded_size, -1))

            logger.debug("Download completed successfully")

            logger.debug("Moving temporary download to %s", path)
            if path.is_file():
                path.unlink()
            shutil.move(temp_path, path)

        if web_mtime_str:
            logger.debug("Setting local file timestamp to match web file")
            # Convert RFC 7231 string to a timezone-aware datetime object
            web_dt = parsedate_to_datetime(web_mtime_str)
            # Convert datetime object to a Unix timestamp (float) required by
            # os.utime
            web_unix_timestamp = web_dt.timestamp()

            # Apply timestamp: (atime, mtime). We apply the web time to both access
            # and modification
            os.utime(path, (web_unix_timestamp, web_unix_timestamp))


def download_and_convert(progress_callback: SignalInstance):
    appdata = program_appdata_directory()
    assert appdata is not None

    url = imdb_dataset_url
    name = QUrl(url).path().lstrip("/")
    path = appdata / name

    if download_needed(path, url):
        do_download(url, name, path, progress_callback)
        db_create = True
    else:
        logger.debug("Most recent IMDb dataset already downloaded")
        db_create = not imdb_db_path().exists()

    if db_create:
        create_db(dataset=path, progress_callback=progress_callback)


def dataset_downward_size(progress_callback: SignalInstance) -> int:
    response = requests.head(imdb_dataset_url, timeout=5)
    return int(response.headers.get("content-length", 0))


def database_exists() -> bool:
    try:
        path = imdb_db_path()
    except AssertionError:
        return False
    return path.exists()


def query_by_imdb_id(imdb_id: str) -> tuple[str, int] | None:
    with closing(sqlite3.connect(imdb_db_path())) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT primary_title, premiered FROM titles WHERE title_id = ?
            """,
            (imdb_id,),
        )
        row = c.fetchone()
        return row
