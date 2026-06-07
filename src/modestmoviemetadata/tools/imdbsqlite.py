#  SPDX-FileCopyrightText: 2018 Jonas Tingeborn
#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

import gzip
import os
import sqlite3
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path

from qtpy.QtCore import QLocale, SignalInstance

from modestmoviemetadata.tools.logtools import get_logger

logger = get_logger()


class Column:
    """Table column configuration"""

    def __init__(
        self, name, type="VARCHAR", pk=None, index=None, unique=None, null=True
    ):
        self.name = name
        self.type = type
        self.pk = pk
        self.index = index
        self.unique = unique
        self.null = null


# Files and their corresponding mapping functions used to import into the
# database. The files are imported in order listed, and are obtained from:
# https://www.imdb.com/interfaces/

# <filename>: ( <table-name>, {<tsv-header>: column} )
TSV_TABLE_MAP = OrderedDict(
    [
        (
            "title.basics.tsv.gz",
            (
                "titles",
                OrderedDict(
                    [
                        (
                            "tconst",
                            Column(
                                name="title_id", type="VARCHAR PRIMARY KEY", index=True
                            ),
                        ),
                        ("primaryTitle", Column(name="primary_title")),
                        ("startYear", Column(name="premiered", type="INTEGER")),
                    ]
                ),
            ),
        ),
    ]
)


class Database:
    """Shallow DB abstraction"""

    def __init__(self, table_map, uri=":memory:"):
        self.table_map = table_map
        exists = os.path.exists(uri)
        self.connection = sqlite3.connect(uri, isolation_level=None)
        self.connection.executescript("""
            PRAGMA encoding="UTF-8";
            PRAGMA foreign_keys=TRUE;
            PRAGMA synchronous=OFF;
        """)

        if not exists:
            logger.info("Applying schema")
            self.create_tables()

        # using a cursor is a smidgen faster, due to fewer function calls
        self.cursor = self.connection.cursor()
        self.debug_enabled = False

    def create_tables(self):
        sqls = [
            self._create_table_sql(table, mapping.values())
            for table, mapping in self.table_map.values()
        ]
        sql = "\n".join(sqls)
        logger.debug(sql)
        self.connection.executescript(sql)

    def create_indices(self):
        sqls = [
            self._create_index_sql(table, mapping.values())
            for table, mapping in self.table_map.values()
        ]
        sql = "\n".join([s for s in sqls if s])
        logger.debug(sql)
        for stmt in sql.split("\n"):
            self.connection.executescript(stmt)
        self.commit()

    def analyze(self):
        self.connection.executescript("ANALYZE;")

    def begin(self):
        logger.debug("TX BEGIN")
        return self.cursor.execute("BEGIN")

    def commit(self):
        logger.debug("TX COMMIT")
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def execute(self, sql, values=None):
        if self.debug_enabled:
            logger.debug(f"{sql} = {values}")

        return self.cursor.execute(sql, values)

    def close(self):
        logger.debug("DB CLOSE")
        self.cursor.close()
        self.connection.close()

    @staticmethod
    def _create_table_sql(table_name, columns):
        lines = [f"CREATE TABLE {table_name} ("]

        # Declare columns
        cols = (
            "  {name} {type}{pk}{unique}{null}".format(
                name=c.name,
                type=c.type,
                pk=(" PRIMARY KEY" if c.pk else ""),
                unique=(" UNIQUE" if c.unique and not c.pk else ""),
                null=(" NOT NULL" if c.pk or not c.null else ""),
            )
            for c in columns
        )
        lines.append(",\n".join(cols))
        lines.append(");")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _create_index_sql(table_name, columns):
        lines = [
            f"CREATE INDEX ix_{table_name}_{c.name} ON {table_name} ({c.name});"
            for c in columns
            if c.index
        ]
        return "\n".join(lines)


def tsv(f, null="\\N"):
    """
    Read a Tab separated file and yield a dict for each "record".
    Similar to python's csv.DictReader but faster and handles imdb nulls.
    """
    headers = [x.strip() for x in next(f).split("\t")]
    for s in f:
        values = [
            (x.strip() if x and x != null else None) for x in s.rstrip().split("\t")
        ]
        yield dict(zip(headers, values))


def count_lines(f):
    """Count lines in a byte iterable"""
    lf = b"\n"
    chunk_size = 1 << 20
    lines = 0
    chunk = f.read(chunk_size)
    while chunk:
        lines += chunk.count(lf)
        chunk = f.read(chunk_size)
    return lines


def import_file(db, filename, table, column_mapping, progress_callback: SignalInstance):
    """
    Import an imdb file into a given table, using a specific tsv value to column mapping
    """

    @contextmanager
    def text_open(fn, encoding="utf-8"):
        """Yields utf-8 decoded strings, one per line, from a [gzipped] text file"""
        # Fast python3 text decoding
        with gzip.open(fn, "rt", encoding=encoding) as tf:
            yield tf

    logger.debug("Importing file: %s", filename)

    headers = column_mapping.keys()
    columns = [c.name for c in column_mapping.values()]
    placeholders = ["?" for _ in columns]
    sql = "INSERT INTO {table} ({columns}) VALUES({values})".format(
        table=table, columns=", ".join(columns), values=",".join(placeholders)
    )

    logger.debug("Reading number of rows ...")
    with gzip.open(filename, "rb") as f:
        total_rows = count_lines(f) - 1  # first line is header

    locale = QLocale.system()

    progress_callback.emit(
        (
            f"Creating database ({locale.toString(total_rows)} records)...",
            0,
            total_rows,
        )
    )

    logger.debug("Inserting %s rows into table: %s", total_rows, table)
    db.begin()
    try:
        with text_open(filename) as tf:
            for count, row in enumerate(tsv(tf)):
                values = [row[h] for h in headers if h in row]
                db.execute(sql, list(values))
                if count % 1000 == 0:
                    progress_callback.emit(("", count, -1))
        db.commit()
    except Exception:
        db.rollback()
        raise


def create_db(dataset: Path, progress_callback: SignalInstance):
    progress_callback.emit(("Examining dataset...", 0, 0))
    uri = dataset.parent / "imdb.db"
    if uri.exists():
        uri.unlink()
    logger.debug("Creating database: %s", uri)
    table_map = TSV_TABLE_MAP
    db = Database(table_map=table_map, uri=str(uri))
    for filename, table_mapping in table_map.items():
        table, column_mapping = table_mapping
        logger.debug("Table: %s", table)
        import_file(
            db=db,
            filename=str(dataset),
            table=table,
            column_mapping=column_mapping,
            progress_callback=progress_callback,
        )
    logger.debug("Creating database index ...")
    progress_callback.emit(("Optimizing database...", 0, 0))
    db.create_indices()
