#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
from pathlib import Path

version = subprocess.check_output(
    ["hatch", "version"],
    text=True,
).strip()

template = Path("modestmoviemetadata.iss.in").read_text(encoding="utf-8")

output = template.replace("@APPVERSION@", version)

Path("modestmoviemetadata.iss").write_text(
    output,
    encoding="utf-8",
)
