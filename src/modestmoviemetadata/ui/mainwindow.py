#  SPDX-FileCopyrightText: 2022-2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime
from enum import Flag, auto
from typing import cast

import arrow
from qtpy.QtCore import QObject, QSettings, QSize, Qt, QThreadPool, QTimer, Slot
from qtpy.QtGui import QFont, QGuiApplication, QIcon, QPixmap
from qtpy.QtWidgets import (
    QCheckBox,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QVBoxLayout,
    QWidget,
)

from modestmoviemetadata.config import application_name
from modestmoviemetadata.tools.audiotools import play_sound
from modestmoviemetadata.tools.database import (
    create_title_index,
    database_exists,
    dataset_downward_size,
    download_and_convert,
    title_index_exists,
)
from modestmoviemetadata.tools.filetools import program_appdata_directory
from modestmoviemetadata.tools.logtools import get_logger
from modestmoviemetadata.tools.movieinfo import (
    MovieInfo,
    fetch_movie_info,
    get_imdb,
    sanitise_title,
)
from modestmoviemetadata.tools.utilities import (
    format_bytes,
    program_icon_path,
    video_folder_path,
)
from modestmoviemetadata.tools.viewutils import boxBorderColor
from modestmoviemetadata.ui.aboutdialog import AboutDialog
from modestmoviemetadata.ui.appthreading import Worker
from modestmoviemetadata.ui.fancylineedit import FancyLineEdit
from modestmoviemetadata.ui.narrowspinbox import NarrowSpinbox
from modestmoviemetadata.ui.selectrecord import SelectRecord

logger = get_logger()


class PendingOperation(Flag):
    TITLE_SEARCH = auto()
    IMDB_ID_SEARCH = auto()
    INFORM_DATASET_CONVERTED = auto()


IMDB_YEAR_MIN = 1894


class MainWindow(QMainWindow):
    def __init__(
        self,
        parent: QObject = None,
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle(application_name)
        self.setWindowIcon(QIcon(program_icon_path()))

        self.settings = QSettings()

        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(1)

        self.clipboard = QGuiApplication.clipboard()
        self.clipboard.changed.connect(self.clipboardDataChanged)

        self.folderIconLabel = QLabel()

        # Initialize pending operation flag to no flag
        self.pending_operation = PendingOperation(0)

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
        self.yearSpinbox.setRange(IMDB_YEAR_MIN - 1, 2100)
        self.yearSpinbox.setSpecialValueText("")
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

        self.lastUpdatedLabel = QLabel()
        self.lastUpdatedLabel.setContentsMargins(4, 18, 0, 0)
        font = QFont()
        font.setItalic(True)
        self.lastUpdatedLabel.setFont(font)
        self.showLastUpdated()

        self.lastUpdatedTimer = QTimer()
        # Update last updated every 60 minutes
        self.lastUpdatedTimer.setInterval(60 * 60 * 1000)
        self.lastUpdatedTimer.timeout.connect(self.showLastUpdated)
        self.lastUpdatedTimer.start()

        self.titleEdit.textEdited.connect(self.titleEditTextEdited)
        self.titleEdit.pasted.connect(self.titleEditPasted)
        self.yearSpinbox.valueChanged.connect(self.yearSpinboxValueChanged)
        self.imdbEdit.textEdited.connect(self.imdbEditTextEdited)
        self.imdbEdit.pasted.connect(self.imdbEditPasted)

        self.setupButtonBox()

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
        gridLayout.addWidget(self.lastUpdatedLabel, 4, 0, 1, 2)
        gridLayout.setSpacing(6)

        layout = QVBoxLayout()
        layout.setSpacing(18)
        layout.addWidget(folderWidget, stretch=100)
        layout.addLayout(gridLayout)
        layout.addWidget(self.buttonBox)

        mainWidget = QWidget()
        mainWidget.setLayout(layout)

        self.setCentralWidget(mainWidget)

        self.resize(QSize(600, 10))
        self.show()
        if program_appdata_directory() is None:
            QMessageBox.critical(
                self,
                "Modest Movie Metadata Critical Error",
                "The program's Application Data directory cannot be created. "
                "The program will now exit.",
            )
            QTimer.singleShot(0, self.close)
        elif not database_exists():
            QTimer.singleShot(0, self.datasetRequired)

    def setupButtonBox(self) -> None:
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButtons.Apply
            | QDialogButtonBox.StandardButtons.Open
            | QDialogButtonBox.StandardButtons.Reset
            | QDialogButtonBox.StandardButtons.Help
        )

        self.aboutButton = self.buttonBox.button(QDialogButtonBox.StandardButton.Help)
        self.aboutButton.clicked.connect(self.aboutButtonClicked)
        self.aboutButton.setText("About")
        self.aboutButton.setToolTip("Information about the program")

        self.resetButton = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
        self.resetButton.clicked.connect(self.resetButtonClicked)
        self.resetButton.setToolTip("Reset")
        self.resetButton.setToolTip("Clear the IMDb, Title and Year values")

        self.copyButton = self.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
        self.copyButton.setText("&Copy")
        self.copyButton.clicked.connect(self.copyButtonClicked)
        self.copyButton.setToolTip("Copy the Jellyfin folder name to the clipboard")

        self.getButton = self.buttonBox.button(QDialogButtonBox.StandardButton.Open)
        self.getButton.setText("&Get")
        self.getButton.clicked.connect(self.getButtonClicked)
        self.getButton.setToolTip("Get the Jellyfin folder name")

        self.downloadButton = self.buttonBox.addButton(
            QDialogButtonBox.StandardButton.Reset
        )
        self.downloadButton.setText("&Update Database")
        self.downloadButton.clicked.connect(self.downloadButtonClicked)
        self.downloadButton.setToolTip(
            "Update local database using the latest IMDb  dataset"
        )

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

    @Slot()
    def aboutButtonClicked(self, checked: bool) -> None:
        about = AboutDialog(parent=self)
        about.exec()

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

    def resetContentsExceptIMDbId(self) -> None:
        self.titleEdit.clear()
        self.yearSpinbox.setValue(0)
        self.yearSpinbox.clear()
        self.folderLabel.clear()

    @Slot(bool)
    def downloadButtonClicked(self, checked: bool) -> None:

        self.progressDialog = QProgressDialog(
            "Checking IMDb dataset...", None, 0, 0, self
        )
        self.progressDialog.setMinimumDuration(0)
        self.progressDialog.setValue(0)
        self.progressDialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progressDialog.setAutoReset(False)

        worker = Worker(download_and_convert, self.settings.value("Last_Modified", ""))
        worker.signals.result.connect(self.downloadResult)
        worker.signals.finished.connect(self.downloadComplete)
        worker.signals.progress.connect(self.downloadProgress)
        worker.signals.error.connect(self.downloadException)
        self.threadpool.start(worker)

    @Slot(tuple)
    def downloadProgress(self, data: tuple) -> None:
        text, progress, maximum = data
        if text and text != self.progressDialog.labelText():
            self.progressDialog.setLabelText(text)
        if maximum >= 0:
            self.progressDialog.setMaximum(maximum)
        self.progressDialog.setValue(progress)

    @Slot(object)
    def downloadResult(self, data: str) -> None:
        if data == "ALREADY_DOWNLOADED":
            QMessageBox.information(
                self, "IMDb Database", "You already have the most recent database."
            )
        elif data:
            # Set flag to indicate the dataset has been converted
            self.pending_operation |= PendingOperation.INFORM_DATASET_CONVERTED
            self.settings.setValue("Last_Modified", data)

    @Slot()
    def downloadComplete(self) -> None:
        if PendingOperation.INFORM_DATASET_CONVERTED in self.pending_operation:
            self.playSound("choh.mp3")
            # Remove the flag
            self.pending_operation &= ~PendingOperation.INFORM_DATASET_CONVERTED

        self.progressDialog.reset()
        self.showLastUpdated()
        if PendingOperation.IMDB_ID_SEARCH in self.pending_operation:
            QTimer.singleShot(0, self.getButton.clicked.emit)

    @Slot()
    def downloadException(self, exception: Exception) -> None:
        logger.error("Error updating dataset")
        logger.error("%s", exception)
        QMessageBox.critical(self, "Error updating dataset", str(exception))
        if not database_exists():
            QTimer.singleShot(0, self.datasetRequired)

    @Slot()
    def showLastUpdated(self) -> None:
        last_modified = cast(str, self.settings.value("Last_Modified", ""))
        if not last_modified:
            self.lastUpdatedLabel.setText("")
        else:
            try:
                last_modified_dt = datetime.fromisoformat(last_modified)
            except ValueError:
                logger.error(
                    "Invalid Last Modified ISO date time value %s", last_modified
                )
                self.lastUpdatedLabel.setText("")
            else:
                last_modified = arrow.get(last_modified_dt).humanize()
                self.lastUpdatedLabel.setText(
                    f"Using IMDb dataset from {last_modified}"
                )

    def searchByTitle(self) -> bool:
        if PendingOperation.TITLE_SEARCH in self.pending_operation:
            logger.debug(
                "Searching by title because Title Search pending operation set"
            )
            return True

        if not title_index_exists():
            key = "Title_Index_Message"
            if not self.settings.value(key, ""):
                logger.debug("Prompting whether to add primary title index")
                msgBox = QMessageBox(parent=self)
                msgBox.setWindowTitle("Database Optimization")
                msgBox.setText(
                    "Searching by title requires this program's database to be "
                    "optimized to make that search more efficient. Optimizing it may "
                    "take a few minutes.\n\n"
                    "Do you agree?\n"
                )
                msgBox.setIcon(QMessageBox.Icon.Question)
                msgBox.setStandardButtons(
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel
                )
                cb = QCheckBox("Don't show this again")
                msgBox.setCheckBox(cb)
                ret = msgBox.exec()
                if cb.isChecked():
                    # This value can be set to anything; the value merely has to exist
                    self.settings.setValue(key, "do not show")
                if ret == QMessageBox.StandardButton.Cancel:
                    logger.debug("User cancelled index creation")
                    return False
                if ret == QMessageBox.StandardButton.Yes:
                    self.progressDialog = QProgressDialog(
                        "Optimizing Database...", None, 0, 0, self
                    )
                    self.progressDialog.setMinimumDuration(0)
                    self.progressDialog.setValue(0)
                    self.progressDialog.setWindowModality(Qt.WindowModality.WindowModal)
                    self.progressDialog.setAutoReset(False)

                    worker = Worker(create_title_index)
                    worker.signals.finished.connect(self.titleIndexCreationFinished)
                    worker.signals.error.connect(self.titleIndexCreationException)
                    # Set the flag to indicate a title search needs to be done
                    # after the index is created
                    self.pending_operation |= PendingOperation.TITLE_SEARCH
                    self.threadpool.start(worker)
                    return False

        self.pending_operation |= PendingOperation.TITLE_SEARCH
        return True

    @Slot()
    def titleIndexCreationFinished(self) -> None:
        QTimer.singleShot(0, self.getButton.clicked.emit)
        self.progressDialog.reset()

    @Slot(Exception)
    def titleIndexCreationException(self, exception: Exception) -> None:
        logger.error(str(exception))
        if PendingOperation.TITLE_SEARCH in self.pending_operation:
            self.pending_operation &= ~PendingOperation.TITLE_SEARCH
        self.progressDialog.reset()

    @Slot(bool)
    def getButtonClicked(self, checked: bool) -> None:
        title = self.titleEdit.text().strip()
        year = self.yearSpinbox.value()
        if year == IMDB_YEAR_MIN - 1:
            year = None
        imdb_id = self.imdbEdit.text().strip()

        if not (title or year or imdb_id):
            return

        if not imdb_id and title:
            if not self.searchByTitle():
                if PendingOperation.TITLE_SEARCH in self.pending_operation:
                    logger.debug("Deferring searching by title until index created")
                else:
                    logger.debug("Not searching by title")
                return

            searching_for = f"{title} ({year})" if year is not None else title
            self.progressDialog = QProgressDialog(
                f"Searching for {searching_for}...", None, 0, 0, self
            )
            self.progressDialog.setMinimumDuration(0)
            self.progressDialog.setValue(0)
            self.progressDialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progressDialog.setAutoReset(False)

        if not title:
            if len(imdb_id) < 2:
                return

            if not imdb_id[2:].isdigit():
                return

        logger.debug("Fetching movie info %s (%s) %s", title, year, imdb_id)
        worker = Worker(fetch_movie_info, title, year, imdb_id)
        worker.signals.result.connect(self.movieInfoExtracted)
        worker.signals.error.connect(self.movieInfoException)
        self.threadpool.start(worker)

    @Slot(object)
    def movieInfoExtracted(self, movie_infos: list[MovieInfo | None]) -> None:

        if PendingOperation.TITLE_SEARCH in self.pending_operation:
            self.progressDialog.reset()
            # Unset the Title Search flag
            self.pending_operation &= ~PendingOperation.TITLE_SEARCH

        movie_info = None

        if movie_infos is None:
            return

        if len(movie_infos) == 1:
            movie_info = movie_infos[0]
            # Was the information found in the local database using the IMDb id?
            if (
                movie_info.title == ""
                and movie_info.year is None
                and movie_info.imdb_id
            ):
                # It wasn't
                self.resetContentsExceptIMDbId()
                # if there is no pending search operation
                if (PendingOperation.IMDB_ID_SEARCH & self.pending_operation) == 0:
                    ret = QMessageBox.question(
                        self,
                        "Update local database?",
                        "The IMDb id is not found in the local database.\n\n"
                        "Do you want to update the local database using the latest "
                        "IMDb dataset?",
                    )
                    if ret == QMessageBox.StandardButton.Yes:
                        self.pending_operation |= PendingOperation.IMDB_ID_SEARCH
                        QTimer.singleShot(0, self.downloadButton.clicked.emit)
                else:
                    # The dataset was already refreshed. Don't prompt again.
                    # Clear the flag
                    self.pending_operation &= ~PendingOperation.IMDB_ID_SEARCH

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

    @Slot(Exception)
    def movieInfoException(self, exception: Exception) -> None:
        logger.debug("Error getting movie information")
        logger.error("%s: %s", exception.__class__.__name__, str(exception))
        self.playSound("error.mp3")
        if PendingOperation.TITLE_SEARCH in self.pending_operation:
            self.progressDialog.reset()
            # Unset the Title Search flag
            self.pending_operation &= ~PendingOperation.TITLE_SEARCH

    @Slot(str)
    def playSound(self, sound: str) -> None:
        logger.debug("Using Qt to play audio")
        play_sound(soundfile=sound)

    def datasetRequired(self) -> None:
        worker = Worker(dataset_downward_size)
        worker.signals.result.connect(self.datasetRequiredSize)
        self.threadpool.start(worker)

    @Slot(object)
    def datasetRequiredSize(self, data: object) -> None:
        size = int(data)
        s = f"{format_bytes(size)} " if size > 0 else ""

        ret = QMessageBox.question(
            self,
            "Database Required",
            "To continue this program will download from IMDb a publicly "
            f"available {s}dataset.\n\n"
            "The dataset will then be converted into a database about 1 GB in "
            "size, which may take a few minutes. "
            "Without this database, the program is unable to function.\n\n"
            "Do you want this program to proceed with the download and conversion?",
        )
        if ret == QMessageBox.StandardButton.No:
            self.close()
        QTimer.singleShot(0, self.downloadButton.clicked.emit)

    @Slot(Exception)
    def datasetRequiredException(self, exception: Exception) -> None:
        logger.debug("Error getting dataset size")
        logger.error("%s: %s", exception.__class__.__name__, str(exception))
        if not database_exists():
            # Allow for Internet connection problems: prompt again
            self.datasetRequiredSize(0)
