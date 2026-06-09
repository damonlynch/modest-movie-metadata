#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

# Generate version_info.txt containing Windows version info to be used by PyInstaller

import re
import subprocess

raw_version = subprocess.check_output(
    ["hatch", "version"],
    text=True,
).strip()

clean_version = re.match(r"^\d+(\.\d+){0,3}", raw_version).group(0)
parts = clean_version.split(".")
parts += ["0"] * (4 - len(parts))
win_version = ".".join(parts[:4])

subprocess.run(
    [
        "pyivf-make_version",
        "--source-format",
        "yaml",
        "--metadata-source",
        "metadata.yml",
        "--outfile",
        "version_info.txt",
        "--version",
        win_version,
    ],
    check=True,
)
