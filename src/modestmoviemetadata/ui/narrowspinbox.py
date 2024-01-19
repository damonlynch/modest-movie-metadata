# Copyright (c) 2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

from qtpy.QtCore import QSize
from qtpy.QtWidgets import QSpinBox, QStyle, QStyleOptionSpinBox


class NarrowSpinbox(QSpinBox):
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
