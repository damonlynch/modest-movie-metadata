#  SPDX-FileCopyrightText: 2023-2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

from qtpy.QtCore import QSize
from qtpy.QtWidgets import QSpinBox, QStyle, QStyleOptionSpinBox


class NarrowSpinbox(QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lowest_text = ""  # The text to display at the lowest value

    def textFromValue(self, value: int) -> str:
        # If the value is at the absolute minimum, show clear text
        if value == self.minimum():
            return self.lowest_text
        return super().textFromValue(value)

    def valueFromText(self, text: str) -> int:
        # Re-map the clear text back to the minimum integer value
        if text == self.lowest_text:
            return self.minimum()
        return super().valueFromText(text)

    def sizeHint(self):
        self.ensurePolished()

        width = self.fontMetrics().horizontalAdvance(str(self.maximum()))
        height = super().sizeHint().height()

        opt = QStyleOptionSpinBox()
        self.initStyleOption(opt)
        valueSize = QSize(width, height)
        spinboxSize = self.style().sizeFromContents(
            QStyle.ContentsType.CT_SpinBox, opt, valueSize, self
        )
        return spinboxSize
