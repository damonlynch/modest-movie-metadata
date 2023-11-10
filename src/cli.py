# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later


try:
    from icecream import install
    install()

except ImportError:  # Graceful fallback if IceCream isn't installed.
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa
    builtins = __import__('builtins')
    setattr(builtins, 'ic', ic)

from modestmoviemetadata.modestmoviemetadata import main

if __name__ == "__main__":
    main()
