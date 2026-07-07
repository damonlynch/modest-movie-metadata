# Changelog for Modest Movie Metadata

## 2.0.0 (2026-07-07)

- Initiate search when Return or Enter key is pressed  within the Title or IMDb ID fields.
- Disable closing of Progress Dialog.
- Improve readability of message boxes.

## 2.0.0b2 (2026-06-30)

- Refactor user interface logic to use Qt's state machine.
- Disable user interface buttons when clicking them would have no effect.
- Significantly speed up searching by title by using SQLite FTS5 virtual table for high-speed text lookups.

## 2.0.0b1 (2026-06-13)

- Purge use of remote access to IMDb data using Cinemagoer in favor of downloading a freely available non-commercial dataset directly from IMDb.
- Use IMDb's Primary Title field when fetching the title.
- Update bundled Qt 6 to version 6.11 and Python to 3.14.
- Use Inno Setup instead of InstallForge.
- Use Hatch to build Windows executable using PyInstaller and the installer using Inno Setup.

## 1.0.0 (2023-11-22)

- Initial release
