#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

from qtpy.QtCore import Qt
from qtpy.QtGui import QCloseEvent, QKeyEvent, QKeySequence
from qtpy.QtWidgets import QProgressDialog, QWidget


class UnclosableProgressDialog(QProgressDialog):
    def __init__(self, labelText: str, parent: QWidget) -> None:
        super().__init__(labelText, None, 0, 0, parent)
        self.setMinimumDuration(0)
        self.setValue(0)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAutoReset(False)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowFlags.WindowCloseButtonHint)

    def closeEvent(self, event: QCloseEvent) -> None:
        # Ignore the close event to prevent closing
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
        else:
            super().keyPressEvent(event)
