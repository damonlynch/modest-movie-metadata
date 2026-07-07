#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

import doctest

from modestmoviemetadata.tools.utilities import format_bytes, format_bytes_fraction_gb

if __name__ == "__main__":
    doctest.run_docstring_examples(format_bytes, globals())
    doctest.run_docstring_examples(format_bytes_fraction_gb, globals())
