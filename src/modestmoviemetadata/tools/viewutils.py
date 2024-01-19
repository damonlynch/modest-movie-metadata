# Copyright (c) 2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later


from qtpy.QtCore import (
    Qt,
)
from qtpy.QtGui import (
    QColor,
    QImage,
)
from qtpy.QtWidgets import QGroupBox, QWidget


def boxBorderColor(widget: QWidget | None = None) -> QColor:
    frame = widget if widget else QGroupBox()
    image = QImage(10, 10, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(Qt.GlobalColor.white))
    frame.render(image)
    return QColor(image.pixel(0, 2))


def close_color(color1: QColor, color2: QColor) -> bool:
    return (
        abs(color1.red() - color2.red())
        + abs(color1.green() - color2.green())
        + abs(color1.blue() - color2.blue())
        < 30
    )
