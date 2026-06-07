#  SPDX-FileCopyrightText: 2022-2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

from qtpy.QtCore import QObject, QSettings, QSize, Qt, QThreadPool, QTimer, Slot
from qtpy.QtGui import QGuiApplication, QIcon, QPixmap
from qtpy.QtWidgets import (
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
    database_exists,
    dataset_downward_size,
    download_and_convert,
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

        self.lookup_after_dataset_refresh_needed = False
        self.inform_dataset_downloaded = False

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
        self.getButton.setText("&Generate")
        self.getButton.clicked.connect(self.getButtonClicked)
        self.getButton.setToolTip("Generate the Jellyfin folder name")

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
            self.inform_dataset_downloaded = True
            self.settings.setValue("Last_Modified", data)

    @Slot()
    def downloadComplete(self) -> None:
        if self.inform_dataset_downloaded:
            self.playSound("choh.mp3")
            self.inform_dataset_downloaded = False

        self.progressDialog.reset()
        if self.lookup_after_dataset_refresh_needed:
            QTimer.singleShot(0, self.getButton.clicked.emit)

    @Slot()
    def downloadException(self, exception: Exception) -> None:
        logger.error("Error updating dataset")
        logger.error("%s", exception)
        QMessageBox.critical(self, "Error updating dataset", str(exception))

    @Slot(bool)
    def getButtonClicked(self, checked: bool) -> None:
        title = self.titleEdit.text().strip()
        year = self.yearSpinbox.value() or None
        imdb_id = self.imdbEdit.text().strip()

        if not (title or year or imdb_id):
            return

        if len(imdb_id) < 2:
            return

        if not imdb_id[2:].isdigit():
            return

        worker = Worker(fetch_movie_info, title, year, imdb_id)
        worker.signals.result.connect(self.movieInfoExtracted)
        worker.signals.error.connect(self.movieInfoException)
        self.threadpool.start(worker)

    @Slot(object)
    def movieInfoExtracted(self, movie_infos: list[MovieInfo | None]) -> None:
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
                if not self.lookup_after_dataset_refresh_needed:
                    ret = QMessageBox.question(
                        self,
                        "Update local database?",
                        "The IMDb id is not found in the local database.\n\n"
                        "Do you want to update the local database using the latest "
                        "IMDb dataset?",
                    )
                    if ret == QMessageBox.StandardButton.Yes:
                        self.lookup_after_dataset_refresh_needed = True
                        QTimer.singleShot(0, self.downloadButton.clicked.emit)
                else:
                    # The dataset was already refreshed — don't prompt again
                    self.lookup_after_dataset_refresh_needed = False

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
        logger.debug("Error getting movie information")
        logger.error("%s: %s", exception.__class__.__name__, str(exception))
        self.playSound("error.mp3")

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
        if size:
            ret = QMessageBox.question(
                self,
                "Database Required",
                "To continue this program will download from IMDb a publicly "
                f"available {format_bytes(size)} dataset.\n\n"
                "The dataset will then be converted into a database about 1 GB in "
                "size, which may take a few minutes. "
                "Without this database, the program is unable to function.\n\n"
                "Do you want this program to proceed with the download and conversion?",
            )
            if ret == QMessageBox.StandardButton.No:
                self.close()
