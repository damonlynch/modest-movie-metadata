# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later


from qtpy.QtCore import Signal
from qtpy.QtGui import QFocusEvent, QKeyEvent, QKeySequence, QMouseEvent
from qtpy.QtWidgets import QLineEdit


class FancyLineEdit(QLineEdit):
    pasted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        super().keyPressEvent(event)

        if event.matches(QKeySequence.StandardKey.Paste):
            self.pasted.emit()

    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self.selectAll()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        self.selectAll()
