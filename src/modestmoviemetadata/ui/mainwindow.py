# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later


from qtpy.QtCore import Slot, QObject, QThreadPool, QTimer, QSize
from qtpy.QtGui import QGuiApplication, QIcon, QPixmap

from qtpy.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QWidget,
    QDialogButtonBox,
    QPushButton,
    QProgressBar,
    QLabel,
)

from .appthreading import Worker
from .selectrecord import SelectRecord
from .fancylineedit import FancyLineEdit
from .narrowspinbox import NarrowSpinbox
from ..config import application_name
from ..tools.audiotools import play_sound
from ..tools.logtools import get_logger
from ..tools.movieinfo import fetch_movie_info, MovieInfo, sanitise_title, get_imdb
from ..tools.utilities import program_icon_path, video_folder_path
from ..tools.viewutils import boxBorderColor

logger = get_logger()


class MainWindow(QMainWindow):
    def __init__(
        self,
        parent: QObject = None,
    ) -> None:

        super().__init__(parent)

        self.setWindowTitle(application_name)
        self.setWindowIcon(QIcon(program_icon_path()))

        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(1)

        self.clipboard = QGuiApplication.clipboard()
        self.clipboard.changed.connect(self.clipboardDataChanged)

        self.folderIconLabel = QLabel()

        pixmap = QPixmap(video_folder_path())
        self.folderIconLabel.setPixmap(pixmap)
        self.folderIconLabel.setScaledContents(True)
        self.folderIconLabel.setFixedSize(pixmap.size())
        self.folderLabel = QLabel()
        self.folderLabel.setWordWrap(True)

        self.titleEdit = FancyLineEdit()
        self.titleLabel = QLabel("&Title")
        self.titleLabel.setBuddy(self.titleEdit)

        self.yearSpinbox = NarrowSpinbox()
        self.yearSpinbox.setRange(1894, 2080)
        self.yearSpinbox.clear()
        self.yearLabel = QLabel("&Year")
        self.yearLabel.setBuddy(self.yearSpinbox)

        self.imdbEdit = FancyLineEdit()
        self.imdbLabel = QLabel("&IMDb")
        self.imdbLabel.setBuddy(self.imdbEdit)

        for label in (self.titleLabel, self.yearLabel, self.imdbLabel):
            label.setStyleSheet(
                f"""
                font-weight: bold;
                font-size: {self.font().pointSize() - 1}pt;
                margin-top: 10px;
                """
            )

        self.titleEdit.textEdited.connect(self.titleEditTextEdited)
        self.titleEdit.pasted.connect(self.titleEditPasted)
        self.yearSpinbox.valueChanged.connect(self.yearSpinboxValueChanged)
        self.imdbEdit.textEdited.connect(self.imdbEditTextEdited)
        self.imdbEdit.pasted.connect(self.imdbEditPasted)

        self.setupButtonBox()

        self.progressBar = QProgressBar()
        self.progressBar.setTextVisible(False)
        self.progressBar.setMaximumWidth(100)

        folderLayout = QHBoxLayout()
        folderLayout.addWidget(self.folderIconLabel)
        folderLayout.addWidget(self.folderLabel)
        folderWidget = QWidget()
        folderWidget.setLayout(folderLayout)

        folderWidget.setObjectName("folderWidget")
        borderColor = boxBorderColor(self.imdbEdit)

        folderWidget.setStyleSheet(
            f"""
            #folderWidget 
            {{
                background-color: palette(base);
                border: 1px solid {borderColor.name()};
            }}
            """
        )

        gridLayout = QGridLayout()
        gridLayout.addWidget(self.titleLabel, 0, 0)
        gridLayout.addWidget(self.yearLabel, 0, 1)
        gridLayout.addWidget(self.titleEdit, 1, 0)
        gridLayout.addWidget(self.yearSpinbox, 1, 1)
        gridLayout.addWidget(self.imdbLabel, 2, 0)
        gridLayout.addWidget(self.imdbEdit, 3, 0, 1, 2)
        gridLayout.setSpacing(6)

        layout = QVBoxLayout()
        layout.setSpacing(18)
        layout.addWidget(folderWidget, stretch=100)
        layout.addLayout(gridLayout)
        layout.addWidget(self.buttonBox)

        mainWidget = QWidget()
        mainWidget.setLayout(layout)

        self.setCentralWidget(mainWidget)

        # Activate the status bar
        self.statusBar()
        self.statusBar().addPermanentWidget(self.progressBar)

        self.resize(QSize(600, 10))
        self.show()

    def setupButtonBox(self) -> None:
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButtons.Apply
            | QDialogButtonBox.StandardButtons.Open
            | QDialogButtonBox.StandardButtons.Reset
        )

        self.resetButton = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Reset
        )  # type: QPushButton
        self.resetButton.clicked.connect(self.resetButtonClicked)

        self.copyButton = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Apply
        )  # type: QPushButton
        self.copyButton.setText("&Copy")
        self.copyButton.clicked.connect(self.copyButtonClicked)

        self.getButton = self.buttonBox.button(
            QDialogButtonBox.StandardButton.Open
        )  # type: QPushButton
        self.getButton.setText("&Get")
        self.getButton.clicked.connect(self.getButtonClicked)

    @Slot()
    def clipboardDataChanged(self) -> None:
        text = get_imdb(self.clipboard.text())
        if text and text != self.imdbEdit.text():
            logger.debug("IMDb id %s detected in clipboard", text)
            self.resetButtonClicked(False)
            self.imdbEdit.setText(text)
            self.getButtonClicked(False)

    @Slot(str)
    def titleEditTextEdited(self, text: str) -> None:
        self.generateOutput()

    @Slot()
    def titleEditPasted(self) -> None:
        text = self.titleEdit.text()
        self.resetButtonClicked(False)
        self.titleEdit.setText(text)

    @Slot()
    def imdbEditPasted(self) -> None:
        text = self.imdbEdit.text()  # type:str
        self.resetButtonClicked(False)
        self.imdbEdit.setText(text)
        if text.startswith("tt") and len(text) > 2 and text[2:].isdigit():
            self.getButtonClicked(False)

    @Slot(int)
    def yearSpinboxValueChanged(self, value: int) -> None:
        self.generateOutput()

    @Slot(str)
    def imdbEditTextEdited(self, text: str) -> None:
        ic(text)
        if not text.startswith("tt"):
            text = get_imdb(text)
            if text:
                self.imdbEdit.setText(text)
        self.generateOutput()

    def generateOutput(self) -> None:
        title = self.titleEdit.text()
        year = self.yearSpinbox.text()
        if not (title and year):
            self.folderLabel.clear()
            return

        text = f"{sanitise_title(title)} ({year})"
        if self.imdbEdit.text():
            text = f"{text} [imdbid-{self.imdbEdit.text()}]"
        self.folderLabel.setText(text)

    @Slot(bool)
    def copyButtonClicked(self, checked: bool) -> None:
        text = self.folderLabel.text()
        if text:
            self.clipboard.setText(text)

    @Slot(bool)
    def resetButtonClicked(self, checked: bool) -> None:
        self.titleEdit.clear()
        self.yearSpinbox.setValue(0)
        self.yearSpinbox.clear()
        self.imdbEdit.clear()
        self.folderLabel.clear()

    @Slot(bool)
    def getButtonClicked(self, checked: bool) -> None:
        title = self.titleEdit.text().strip()
        year = self.yearSpinbox.value() or None
        imdb_id = self.imdbEdit.text().strip()

        if not (title or year or imdb_id):
            return

        if imdb_id:
            imdb_id = imdb_id[2:]
            if not imdb_id.isdigit():
                return

        self.progressBar.setRange(0, 0)
        worker = Worker(fetch_movie_info, title, year, imdb_id)
        worker.signals.result.connect(self.movieInfoExtracted)
        worker.signals.error.connect(self.movieInfoException)
        self.threadpool.start(worker)

    @Slot(object)
    def movieInfoExtracted(self, movie_infos: list[MovieInfo]) -> None:
        self.progressBar.setRange(0, 1)
        movie_info = None

        if movie_infos is None:
            return

        if len(movie_infos) == 1:
            movie_info = movie_infos[0]
            self.playSound("choh.mp3")

        elif len(movie_infos) > 1:
            self.playSound("brrr.mp3")
            selectRecord = SelectRecord(movie_infos=movie_infos, parent=self)
            if selectRecord.exec():
                movie_info = movie_infos[selectRecord.row]

        if movie_info is not None:
            logger.debug("%s (%s)", movie_info.title, movie_info.year)
            self.setMovieInfo(movie_info)
            self.generateOutput()
            QTimer.singleShot(0, self.copyButton.clicked.emit)

    def setMovieInfo(self, movieInfo: MovieInfo) -> None:
        if movieInfo.title:
            state = self.titleEdit.blockSignals(True)
            self.titleEdit.setText(movieInfo.title)
            self.titleEdit.blockSignals(state)

        if movieInfo.year:
            state = self.yearSpinbox.blockSignals(True)
            self.yearSpinbox.setValue(movieInfo.year)
            self.yearSpinbox.blockSignals(state)

        if not self.imdbEdit.text():
            text = f"tt{movieInfo.imdb_id}"
            state = self.imdbEdit.blockSignals(True)
            self.imdbEdit.setText(text)
            self.imdbEdit.blockSignals(state)

    @Slot()
    def movieInfoException(self, exception: Exception) -> None:
        self.progressBar.setRange(0, 1)
        logger.debug("Error getting movie information")
        logger.error("%s: %s", exception.__class__.__name__, str(exception))
        self.playSound("error.mp3")

    @Slot(str)
    def playSound(self, sound: str) -> None:
        logger.debug("Using Qt to play audio")
        play_sound(soundfile=sound)
