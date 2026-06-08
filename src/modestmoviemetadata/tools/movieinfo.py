#  SPDX-FileCopyrightText: 2022-2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

import re
from collections.abc import Callable
from dataclasses import dataclass

from modestmoviemetadata.tools.database import query_by_imdb_id, query_by_title


@dataclass
class MovieInfo:
    title: str
    year: int | None
    imdb_id: str


def get_imdb(text: str) -> str:
    match = re.search(r"(?P<id>tt\d+)", text)
    if match is not None:
        return match.group("id")
    return ""


def fetch_movie_info(
    title: str,
    year: int | None,
    imdb_id: str,
    progress_callback: Callable[[int], None],
) -> list[MovieInfo] | None:

    if imdb_id:
        data = query_by_imdb_id(imdb_id)
        if data is not None:
            title, year = data
            return [MovieInfo(title=title, year=year, imdb_id=imdb_id)]
        else:
            # imdb_id with non-existent values for title and year represents a failed
            # lookup
            return [MovieInfo(title="", year=None, imdb_id=imdb_id)]

    else:
        try:
            movies = query_by_title(title)
        except Exception as inst:
            ic(inst)
        else:
            if not year:
                return [MovieInfo(*movie) for movie in movies]
            else:
                return [
                    MovieInfo(*movie)
                    for movie in movies
                    if year - 1 <= movie[1] <= year + 1
                ]


def make_imdb_url(imdb_id: str) -> str:
    return f"https://www.imdb.com/title/{imdb_id}/"


def sanitise_title(title: str) -> str:
    for c in r'\:*?"<>|./!':
        title = title.replace(c, "")
    return title
