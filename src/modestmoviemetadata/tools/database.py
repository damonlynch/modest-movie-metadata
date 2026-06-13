#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

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


def convert_last_modified_header(web_mtime: str) -> datetime:
    """
    Convert web timestamp to a timezone-aware datetime object
    :param web_mtime:  web header timestamp, e.g. 'Sat, 06 Jun 2026 12:43:17 GMT'
    :return:  datetime object, e.g. datetime(2026, 6, 6, 12, 43, 17, tzinfo=datetime.timezone.utc)
    """
    web_dt = parsedate_to_datetime(web_mtime)
    # Strip microseconds
    return web_dt.replace(microsecond=0)


def download_needed(last_modified: str, url: str) -> bool:
    if not last_modified:
        return True

    try:
        last_modified_dt = datetime.fromisoformat(last_modified)
    except ValueError:
        logger.error("Invalid Last Modified ISO date time value %s", last_modified)
        return True

    response = requests.head(url, timeout=5)
    web_mtime = response.headers.get("Last-Modified")

    if not web_mtime:
        logger.warning(
            "Server did not provide a Last-Modified header for %s. "
            "Cannot compare file date and time.",
            url,
        )
        return True

    web_dt = convert_last_modified_header(web_mtime)

    logger.debug("Local File Time (UTC): %s", last_modified_dt)
    logger.debug("Web Server Time (UTC): %s", web_dt)

    return web_dt > last_modified_dt


def do_download(
    url: str, name: str, path: Path, progress_callback: SignalInstance
) -> str:
    logger.debug("Downloading %s", name)

    with requests.get(url, stream=True, timeout=15) as response:
        response.raise_for_status()

        # Fetch total file size and file modification time from response header
        total_size = int(response.headers.get("content-length", 0))
        downloaded_size = 0
        web_mtime = response.headers.get("Last-Modified")

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

        if web_mtime:
            return convert_last_modified_header(web_mtime).isoformat()
        return ""


def download_and_convert(last_modified: str, progress_callback: SignalInstance):
    appdata = program_appdata_directory()
    assert appdata is not None

    url = imdb_dataset_url
    name = QUrl(url).path().lstrip("/")
    path = appdata / name

    db_create = download_needed(last_modified, url) or not imdb_db_path().exists()
    if db_create:
        last_modified_iso = do_download(url, name, path, progress_callback)
        create_db(dataset=path, progress_callback=progress_callback)
        return last_modified_iso
    else:
        logger.debug("Most recent IMDb dataset already downloaded")
        return "ALREADY_DOWNLOADED"


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


def query_by_title(title: str) -> list[tuple[str, int, str]]:
    with closing(sqlite3.connect(imdb_db_path())) as conn:
        c = conn.cursor()
        formatted_search = f"%{title}%"
        # Convert NULL years to 0, which is important when comparing years via
        # integer comparison
        c.execute(
            """
            SELECT primary_title, IFNULL(premiered, 0), title_id FROM titles 
            WHERE primary_title LIKE ?
            """,
            (formatted_search,),
        )
        rows = c.fetchall()
        return rows


def title_index_exists() -> bool:
    with closing(sqlite3.connect(imdb_db_path())) as conn:
        c = conn.cursor()
        c.execute(
            """
            SELECT 1 FROM sqlite_master WHERE type = 'index' AND 
            name = 'ix_titles_primary_title';
            """,
        )
        row = c.fetchone()
        return row is not None


def create_title_index(progress_callback: SignalInstance):
    logger.debug("Creating title_index")
    with closing(sqlite3.connect(imdb_db_path())) as conn:
        c = conn.cursor()
        c.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_titles_primary_title 
            ON titles(primary_title);
            """,
        )
    logger.debug("title_index created")
