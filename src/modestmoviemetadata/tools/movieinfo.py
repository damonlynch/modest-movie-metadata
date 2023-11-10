# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

from collections.abc import Callable
from dataclasses import dataclass
import re


from imdb import Cinemagoer, IMDbError, Movie


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


def get_year(movie: Movie.Movie) -> int:
    try:
        year = int(movie.get("year"))
    except (ValueError, TypeError):
        ic("Incorrect value for movie year", movie.get("title"))
        year = 0
    return year


def fetch_movie_info(
    title: str,
    year: int | None,
    imdb_id: str,
    progress_callback: Callable[[int], None],
) -> list[MovieInfo]:

    ia = Cinemagoer()

    if imdb_id:
        try:
            movie = ia.get_movie(imdb_id)
        except IMDbError as inst:
            ic(inst)
        else:
            title = movie.get("title")
            year = get_year(movie)

            return [MovieInfo(title=title, year=year, imdb_id=imdb_id)]

    else:
        try:
            movies = ia.search_movie(title)
        except IMDbError as inst:
            ic(inst)
        else:
            if not year:
                return [
                    MovieInfo(
                        title=movie.get("title"),
                        year=get_year(movie),
                        imdb_id=movie.getID(),
                    )
                    for movie in movies
                ]
            else:
                return [
                    MovieInfo(
                        title=movie.get("title"),
                        year=get_year(movie),
                        imdb_id=movie.getID(),
                    )
                    for movie in movies
                    if year - 1 <= get_year(movie) <= year + 1
                ]


def make_imdb_url(imdb_id: str) -> str:
    return f"https://www.imdb.com/title/tt{imdb_id}/"


def sanitise_title(title: str) -> str:
    for c in r'\:*?"<>|./!':
        title = title.replace(c, "")
    return title
