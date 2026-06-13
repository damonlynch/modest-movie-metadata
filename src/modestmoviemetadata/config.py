#  SPDX-FileCopyrightText: 2022-2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

import importlib.metadata

from modestmoviemetadata import __version__

application_name = "Modest Movie Metadata"
application_identifier = "modest-movie-metadata"
application_summary = "Create Jellyfin compatible folder and file names"
logfile_name = "modest-movie-metadata.log"

copyright_message = "Copyright &copy; 2024-2026 Damon Lynch."

try:
    version = importlib.metadata.version("modestmoviemetadata")
    if version == "0.0.0":
        version = __version__
except importlib.metadata.PackageNotFoundError:
    version = __version__

app_guid = "17ea3af5-1edc-478b-b0fc-00384af8b188"  # arbitrary UUID

imdb_dataset_url = "https://datasets.imdbws.com/title.basics.tsv.gz"
imdb_dataset_description_url = "https://developer.imdb.com/non-commercial-datasets/"
