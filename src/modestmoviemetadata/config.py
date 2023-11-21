# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

import importlib.metadata
from . import __version__

application_name = "Modest Movie Metadata"
application_identifier = "modest-movie-metadata"
application_summary = "Create Jellyfin compatible folder and file names"
logfile_name = "modest-movie-metadata.log"

copyright_message = "Copyright &copy; 2023 Damon Lynch."

try:
    version = importlib.metadata.version("modestmoviemetadata")
except importlib.metadata.PackageNotFoundError:
    version = __version__

app_guid = "17ea3af5-1edc-478b-b0fc-00384af8b188" # arbitrary UUID
