# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later


import webbrowser
from typing import Any

from qtpy.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
    Signal,
    Slot,
)
from qtpy.QtGui import (
    QColor,
)
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMainWindow,
    QStyle,
    QTableView,
    QVBoxLayout,
)

from ..tools.movieinfo import MovieInfo, make_imdb_url


class SelectRecord(QDialog):
    def __init__(self, movie_infos: list[MovieInfo], parent: QMainWindow) -> None:
        super().__init__(parent)
        self.model = MoviesModel(movie_infos=movie_infos, parent=self)
        self.table = MoviesTable(parent=self)
        self.table.setModel(self.model)
        self.table.resizeColumnsToContents()
        self.table.movieSelected.connect(self.tableMovieSelected)

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)
        self.row = None

        self.table.setFixedWidth(
            min(
                self.table.horizontalHeader().length()
                + self.table.verticalHeader().width()
                + self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
                + self.style().pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth) * 2,
                self.screen().size().width() - 10,
            )
        )
        self.setMinimumHeight(min(500, self.screen().size().height() - 10))

    @Slot(int)
    def tableMovieSelected(self, row: int) -> None:
        self.row = row
        self.accept()


class MoviesModel(QAbstractTableModel):
    def __init__(self, movie_infos: list[MovieInfo], parent: SelectRecord) -> None:
        super().__init__(parent)
        self.movie_infos = movie_infos

        self.header_labels = ("Title", "Year", "IMDb")
        assert len(self.header_labels) == self.columnCount()

        for i, value in enumerate(self.header_labels):
            self.setHeaderData(i, Qt.Orientation.Horizontal, value)

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        return len(self.movie_infos)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        return 3

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.header_labels[section]
        elif (
            orientation == Qt.Orientation.Vertical
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return section + 1

    def data(self, index: QModelIndex, role: Qt.ItemDataRole) -> Any:
        if not index.isValid():
            return
        row = index.row()
        column = index.column()
        if role == Qt.ItemDataRole.ForegroundRole and column == 2:
            return QColor("blue")

        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.UserRole):
            return

        info = self.movie_infos[row]
        match column:
            case 0:
                return info.title
            case 1:
                return info.year
            case 2:
                match role:
                    case Qt.ItemDataRole.DisplayRole:
                        return make_imdb_url(info.imdb_id)
                    case Qt.ItemDataRole.UserRole:
                        return info.imdb_id


class MoviesTable(QTableView):
    movieSelected = Signal(int)

    def __init__(self, parent: SelectRecord) -> None:
        super().__init__(parent)
        self.clicked.connect(self.cellClicked)
        self.doubleClicked.connect(self.cellDoubleClicked)

    def cellClicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        if index.column() == 2:
            webbrowser.open(index.data())

    def cellDoubleClicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        if index.column() in (0, 1):
            self.movieSelected.emit(index.row())
