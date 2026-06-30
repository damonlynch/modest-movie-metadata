#  SPDX-FileCopyrightText: 2022-2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime, timedelta
from typing import cast

import arrow
from qtpy.QtCore import (
    QSettings,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from qtpy.QtGui import QCloseEvent, QFont, QGuiApplication, QIcon, QPixmap
from qtpy.QtStateMachine import QState, QStateMachine
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
    create_table_index,
    database_exists,
    dataset_downward_size,
    download_and_convert,
    table_index_exists,
)
from modestmoviemetadata.tools.filetools import imdb_db_path, program_appdata_directory
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
from modestmoviemetadata.ui.state import (
    FinalState,
    HistoryState,
    State,
    StateMachineSignals,
)

logger = get_logger()


IMDB_YEAR_MIN = 1894


class MainWindow(QMainWindow):
    inputFieldEdited = Signal()
    inputFieldsCleared = Signal()
    inputFieldsEntered = Signal()
    imdbIdDifferenceDetected = Signal()
    folderLabelCleared = Signal()
    folderLabelGenerated = Signal()
    validSearchTermsEntered = Signal()
    validSearchTermsNotEntered = Signal()

    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.setWindowTitle(application_name)
        self.setWindowIcon(QIcon(program_icon_path()))

        self.settings = QSettings()
        # Three date time settings:
        # Last_Modified: When IMDb last modified their dataset (UTC)
        # Last_Updated: When the dataset was last converted into a database by this
        # program
        # Last_Prompted: When this program last prompted the user to update the
        # dataset after an unsuccessful search.

        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(1)
        self.controller = StateMachineSignals()

        self.clipboard = QGuiApplication.clipboard()

        # Record which IMDb ID is associated with generated Movie/TV show information
        self.generated_imdb_id = ""

        self.setupWidgets()
        self.setupStateMachine()
        self.layoutWidgets()

        self.centralWidget().setEnabled(False)
        self.show()
        # The state machine is not started until the initialization process for this
        # class is finished. Must emit a signal to move to the next state in the state
        # machine.
        QTimer.singleShot(0, self.controller.machineInitialized.emit)
        self.validateConfigDirectory()

    def validateConfigDirectory(self) -> None:
        if program_appdata_directory() is None:
            QMessageBox.critical(
                self,
                "Modest Movie Metadata Critical Error",
                "The program's Application Data directory cannot be created. "
                "The program will now exit.",
            )
            QTimer.singleShot(0, self.close)

    def closeEvent(self, event: QCloseEvent):
        self.controller.machineCloseRequested.emit()
        event.accept()

    def setupWidgets(self) -> None:

        self.mainWidget = QWidget()

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

        self.lastUpdatedTimer = QTimer()
        # Update last updated every 60 minutes
        self.lastUpdatedTimer.setInterval(60 * 60 * 1000)
        self.lastUpdatedTimer.timeout.connect(self.showLastUpdated)
        self.lastUpdatedTimer.start()

        self.titleEdit.textEdited.connect(self.inputFieldEdited)
        self.yearSpinbox.valueChanged.connect(self.inputFieldEdited)
        self.imdbEdit.textEdited.connect(self.inputFieldEdited)
        self.imdbEdit.pasted.connect(self.filterImdbEdit)

        self.inputFieldEdited.connect(self.evaluateInputFields)
        self.inputFieldEdited.connect(self.evaluateDatasetSearchPossible)

        self.setupButtonBox()

    def setupButtonBox(self) -> None:
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButtons.Apply
            | QDialogButtonBox.StandardButtons.Open
            | QDialogButtonBox.StandardButtons.Reset
            | QDialogButtonBox.StandardButtons.Help
        )

        self.aboutButton = self.buttonBox.button(QDialogButtonBox.StandardButton.Help)
        self.aboutButton.setText("About")
        self.aboutButton.setToolTip("Information about the program")

        self.resetButton = self.buttonBox.button(QDialogButtonBox.StandardButton.Reset)
        self.resetButton.setToolTip("Reset")
        self.resetButton.setToolTip("Clear the IMDb, Title and Year values")
        self.resetButton.clicked.connect(self.controller.resetRequested)

        self.copyButton = self.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
        self.copyButton.clicked.connect(self.controller.copyToClipboardRequested)
        self.copyButton.setText("&Copy")
        self.copyButton.setToolTip("Copy the Jellyfin folder name to the clipboard")

        self.getButton = self.buttonBox.button(QDialogButtonBox.StandardButton.Open)
        self.getButton.setText("&Get")
        self.getButton.clicked.connect(self.controller.searchRequested)
        self.getButton.setToolTip("Get the Jellyfin folder name")

        self.updateButton = self.buttonBox.addButton(
            QDialogButtonBox.StandardButton.Reset
        )
        self.updateButton.clicked.connect(self.controller.updateRequested)
        self.updateButton.setText("&Update Dataset")
        self.updateButton.setToolTip("Get the latest online IMDb dataset")

    def layoutWidgets(self) -> None:
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
        self.mainWidget.setLayout(layout)

        self.setCentralWidget(self.mainWidget)

        self.resize(QSize(600, 10))

    def setupStateMachine(self) -> None:

        self.createStates()
        self.configureStateMachine()
        self.configureStateTransitions()

        self.machine.start()

    def createStates(self) -> None:
        self.initializingState = State(name="initializingState")
        self.checkDatabaseState = State(name="checkDatabaseState")
        self.newDatabaseState = State(name="newDatabaseState")
        self.operationalState = State(name="operationalState")
        self.operationalHistoryState = HistoryState(
            name="operationalHistoryState", parent=self.operationalState
        )
        self.resetState = State(name="resetState", parent=self.operationalState)
        self.readyState = State(
            name="readyState",
            childMode=QState.ChildMode.ParallelStates,
            parent=self.operationalState,
        )
        self.updateState = State(name="updateState", parent=self.operationalState)
        self.searchDatasetState = State(
            name="searchDatasetState", parent=self.operationalState
        )
        # searchPendingState is a Transient Evaluation State whose only purpose is to
        # evaluate whether an index is needed and transition to either
        # addTitleIndexState or searchingState.
        self.searchPendingState = State(
            name="searchPendingState", parent=self.searchDatasetState
        )
        self.searchingState = State(
            name="searchingState", parent=self.searchDatasetState
        )
        self.addTitleIndexState = State(
            name="addTitleIndexState", parent=self.searchDatasetState
        )

        # Track whether any input fields contain data, which is used for
        # determining whether the reset button should be enabled
        self.inputFieldsRegionState = State(
            name="inputFieldsRegionState", parent=self.readyState
        )
        # inputFieldsEvaluationState is a Transient Evaluation State whose only purpose
        # is to determine whether the window's fields are empty or not empty.
        self.inputFieldsEvaluationState = State(
            name="inputFieldsEvaluationState", parent=self.inputFieldsRegionState
        )
        self.emptyState = State(name="emptyState", parent=self.inputFieldsRegionState)
        self.notEmptyState = State(
            name="notEmptyState", parent=self.inputFieldsRegionState
        )

        # Track whether the window's folder label is empty or populated
        self.generationRegionState = State(
            name="generationRegionState", parent=self.readyState
        )
        # folderLabelEvaluationState is a Transient Evaluation State whose only purpose
        # is to determine whether the window's folder label is empty or populated.
        self.generationEvaluationState = State(
            name="generationEvaluationState", parent=self.generationRegionState
        )
        self.generatedState = State(
            name="generatedState", parent=self.generationRegionState
        )
        self.notGeneratedState = State(
            name="notGeneratedState", parent=self.generationRegionState
        )

        self.searchDatasetPossibleRegionState = State(
            name="searchDatasetPossibleRegionState", parent=self.readyState
        )
        self.searchDatasetPossibleEvaluationState = State(
            name="searchDatasetPossibleEvaluationState",
            parent=self.searchDatasetPossibleRegionState,
        )
        self.searchDatasetPossibleState = State(
            name="searchDatasetPossibleState",
            parent=self.searchDatasetPossibleRegionState,
        )
        self.searchDatasetImpossibleState = State(
            name="searchDatasetImpossibleState",
            parent=self.searchDatasetPossibleRegionState,
        )

        self.generateFolderLabelState = State(name="generateFolderLabelState")

        self.clipboardChangedState = State(
            name="clipboardChangedState", parent=self.operationalState
        )

        self.copyState = State(name="copyState")
        self.aboutState = State(name="aboutState")
        self.finalState = FinalState(name="finalState")

    def configureStateMachine(self) -> None:
        self.machine = QStateMachine()
        self.machine.addState(self.initializingState)
        self.machine.addState(self.checkDatabaseState)
        self.machine.addState(self.newDatabaseState)
        self.machine.addState(self.operationalState)
        self.machine.addState(self.generateFolderLabelState)
        self.machine.addState(self.copyState)
        self.machine.addState(self.aboutState)
        self.machine.addState(self.finalState)

        self.machine.setInitialState(self.initializingState)
        self.machine.finished.connect(self.close)

    def configureStateTransitions(self) -> None:

        # Check database state at start-up
        self.initializingState.addTransition(
            self.controller.machineInitialized, self.checkDatabaseState
        )
        self.checkDatabaseState.entered.connect(self.checkDatabase)
        self.checkDatabaseState.addTransition(
            self.controller.databaseVerified, self.operationalState
        )
        self.checkDatabaseState.addTransition(
            self.controller.databaseVerificationFailed, self.newDatabaseState
        )
        self.newDatabaseState.entered.connect(self.newDatabase)
        self.newDatabaseState.addTransition(
            self.controller.updateRequested, self.updateState
        )
        self.newDatabaseState.addTransition(
            self.controller.datasetCreationRejected, self.finalState
        )

        self.operationalState.setInitialState(self.readyState)
        self.operationalHistoryState.setDefaultState(self.readyState)

        self.readyState.assignProperty(self.mainWidget, "enabled", True)
        self.readyState.addTransition(
            self.controller.machineCloseRequested, self.finalState
        )
        self.readyState.addTransition(self.controller.updateRequested, self.updateState)
        self.readyState.addTransition(
            self.controller.searchRequested, self.searchDatasetState
        )
        self.inputFieldsRegionState.setInitialState(self.inputFieldsEvaluationState)
        self.generationRegionState.setInitialState(self.generationEvaluationState)
        self.searchDatasetPossibleRegionState.setInitialState(
            self.searchDatasetPossibleEvaluationState
        )

        self.inputFieldsEvaluationState.entered.connect(self.evaluateInputFields)
        self.inputFieldsEvaluationState.addTransition(
            self.inputFieldsCleared, self.emptyState
        )
        self.inputFieldsEvaluationState.addTransition(
            self.inputFieldsEntered, self.notEmptyState
        )
        self.emptyState.assignProperty(self.resetButton, "enabled", False)
        self.notEmptyState.assignProperty(self.resetButton, "enabled", True)
        self.emptyState.addTransition(self.inputFieldsEntered, self.notEmptyState)
        self.notEmptyState.addTransition(self.inputFieldsCleared, self.emptyState)

        self.generationEvaluationState.entered.connect(self.evaluateFolderLabel)
        self.generationEvaluationState.addTransition(
            self.folderLabelCleared, self.notGeneratedState
        )
        self.generationEvaluationState.addTransition(
            self.folderLabelGenerated, self.generatedState
        )

        self.notGeneratedState.assignProperty(self.copyButton, "enabled", False)
        self.generatedState.assignProperty(self.copyButton, "enabled", True)
        self.generatedState.addTransition(
            self.imdbIdDifferenceDetected, self.notGeneratedState
        )

        self.searchDatasetPossibleEvaluationState.entered.connect(
            self.evaluateDatasetSearchPossible
        )
        self.searchDatasetPossibleEvaluationState.addTransition(
            self.validSearchTermsEntered, self.searchDatasetPossibleState
        )
        self.searchDatasetPossibleEvaluationState.addTransition(
            self.validSearchTermsNotEntered, self.searchDatasetImpossibleState
        )
        self.searchDatasetPossibleState.assignProperty(self.getButton, "enabled", True)
        self.searchDatasetImpossibleState.assignProperty(
            self.getButton, "enabled", False
        )
        self.searchDatasetPossibleState.addTransition(
            self.validSearchTermsNotEntered, self.searchDatasetImpossibleState
        )
        self.searchDatasetImpossibleState.addTransition(
            self.validSearchTermsEntered, self.searchDatasetPossibleState
        )

        self.readyState.addTransition(self.controller.resetRequested, self.resetState)
        self.resetState.entered.connect(self.resetFields)
        self.resetState.addTransition(self.operationalState)

        self.updateState.entered.connect(self.updateDataset)

        self.updateState.addTransition(
            self.controller.updateFinished, self.operationalHistoryState
        )
        self.updateState.addTransition(
            self.controller.updateFailed, self.checkDatabaseState
        )

        self.searchDatasetState.setInitialState(self.searchPendingState)
        self.searchPendingState.entered.connect(self.evaluateSearch)
        self.searchPendingState.addTransition(
            self.controller.addIndexRequested, self.addTitleIndexState
        )
        self.searchPendingState.addTransition(
            self.controller.searchEvaluationSucceeded, self.searchingState
        )

        self.searchingState.entered.connect(self.searchingDataset)
        self.searchingState.addTransition(
            self.controller.updateRequested, self.updateState
        )
        self.searchingState.addTransition(
            self.controller.searchTitleNotFound, self.readyState
        )
        self.searchingState.addTransition(
            self.controller.searchTitleFound, self.generateFolderLabelState
        )
        self.searchingState.addTransition(
            self.controller.searchDatasetFailed, self.checkDatabaseState
        )

        self.addTitleIndexState.entered.connect(self.addTitleIndex)
        self.addTitleIndexState.addTransition(
            self.controller.addIndexCancelled, self.readyState
        )
        self.addTitleIndexState.addTransition(
            self.controller.addIndexFinished, self.searchingState
        )
        self.addTitleIndexState.addTransition(
            self.controller.addIndexFailed, self.checkDatabaseState
        )

        self.generateFolderLabelState.entered.connect(self.generateFolderName)
        # Transient state: generates folder label, then immediately transitions to copy
        self.generateFolderLabelState.addTransition(self.copyState)

        self.copyState.entered.connect(self.copyToClipboard)
        self.copyState.addTransition(self.readyState)
        self.readyState.addTransition(
            self.controller.copyToClipboardRequested, self.copyState
        )

        self.aboutState.entered.connect(self.showAboutDialog)
        # Transient state: once About window is closed, immediately transitions to
        # ready state
        self.aboutState.addTransition(self.readyState)
        self.readyState.addTransition(self.aboutButton.clicked, self.aboutState)

        self.readyState.addTransition(
            self.clipboard.changed, self.clipboardChangedState
        )
        self.clipboardChangedState.entered.connect(self.clipboardDataChanged)
        self.clipboardChangedState.addTransition(
            self.controller.searchRequested, self.searchDatasetState
        )
        self.clipboardChangedState.addTransition(
            self.controller.clipboardIrrelevantDataInput, self.readyState
        )

    @Slot()
    def evaluateInputFields(self) -> None:
        empty = (
            self.yearSpinbox.isEmpty()
            and not self.titleEdit.text()
            and not self.imdbEdit.text()
        )
        self.inputFieldsCleared.emit() if empty else self.inputFieldsEntered.emit()

        if self.generated_imdb_id != self.imdbEdit.text():
            self.folderLabel.clear()
            self.generated_imdb_id = ""
            self.imdbIdDifferenceDetected.emit()

    @Slot()
    def evaluateFolderLabel(self) -> None:
        if self.folderLabel.text():
            self.folderLabelGenerated.emit()
        else:
            self.folderLabelCleared.emit()

    @Slot()
    def evaluateDatasetSearchPossible(self) -> None:
        imdb = self.imdbEdit.text()
        title = self.titleEdit.text()

        valid_imdb = len(imdb) > 2 and imdb[:2] == "tt" and imdb[2:].isdigit()
        have_valid_text = (
            bool(valid_imdb) or (title and valid_imdb) or (title and not imdb)
        )
        imdb_matches = imdb and imdb == self.generated_imdb_id

        if have_valid_text and not imdb_matches:
            self.validSearchTermsEntered.emit()
        else:
            self.validSearchTermsNotEntered.emit()

    @Slot()
    def filterImdbEdit(self) -> None:
        imdb_id = get_imdb(self.imdbEdit.text())
        if imdb_id:
            self.imdbEdit.setText(imdb_id)
            self.controller.searchRequested.emit()

    @Slot()
    def updateDataset(self) -> None:
        logger.debug("showing progress dialog")
        self.progressDialog = QProgressDialog(
            "Checking IMDb dataset...", None, 0, 0, self
        )
        self.progressDialog.setMinimumDuration(0)
        self.progressDialog.setValue(0)
        self.progressDialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progressDialog.setAutoReset(False)

        worker = Worker(download_and_convert, self.settings.value("Last_Modified", ""))
        worker.signals.result.connect(self.updateResult)
        worker.signals.finished.connect(self.updateComplete)
        worker.signals.progress.connect(self.updateProgress)
        worker.signals.error.connect(self.updateError)
        self.threadpool.start(worker)

    @Slot(tuple)
    def updateProgress(self, data: tuple) -> None:
        text, progress, maximum = data
        if text and text != self.progressDialog.labelText():
            self.progressDialog.setLabelText(text)
        if maximum >= 0:
            self.progressDialog.setMaximum(maximum)
        self.progressDialog.setValue(progress)

    @Slot(object)
    def updateResult(self, data: str) -> None:
        if data == "ALREADY_DOWNLOADED":
            QMessageBox.information(
                self,
                "IMDb Dataset",
                "The most recent dataset has already been downloaded.",
            )
        elif data:
            self.settings.setValue("Last_Modified", data)
            self.settings.setValue("Last_Updated", datetime.now().isoformat())

    @Slot()
    def updateComplete(self) -> None:
        logger.debug("closing progress dialog")
        self.progressDialog.reset()
        self.showLastUpdated()
        self.controller.updateFinished.emit()

    @Slot()
    def updateError(self, exception: Exception) -> None:
        logger.error("Error updating dataset")
        logger.error("%s", exception)
        QMessageBox.critical(self, "Error updating dataset", str(exception))
        if hasattr(self, "progressDialog"):
            self.progressDialog.reset()
        self.controller.updateFailed.emit()

    @Slot()
    def evaluateSearch(self) -> None:
        # TODO error checking
        if not self.imdbEdit.text() and not table_index_exists():
            # Need a title index to search
            self.controller.addIndexRequested.emit()
            return
        self.controller.searchEvaluationSucceeded.emit()

    @Slot()
    def searchingDataset(self):
        title = self.titleEdit.text()
        year = self.yearSpinbox.value()
        if year == IMDB_YEAR_MIN - 1:
            year = None
        imdb_id = self.imdbEdit.text()

        y = f"({year}) " if year else ""

        logger.debug("Fetching movie info for %s %s%s", title, y, imdb_id)
        worker = Worker(fetch_movie_info, title, year, imdb_id)
        worker.signals.result.connect(self.movieInfoExtracted)
        worker.signals.error.connect(self.movieInfoException)
        self.threadpool.start(worker)

    @Slot()
    def addTitleIndex(self) -> None:
        key = "Title_Index_Message"
        if not self.settings.value(key, ""):
            logger.debug("Prompting whether to add primary title index")
            current_size = imdb_db_path().lstat().st_size
            current = format_bytes(current_size)
            projected = format_bytes(current_size * 2)

            msgBox = QMessageBox(parent=self)
            msgBox.setWindowTitle("Database Optimization")
            msgBox.setText(
                "Searching without the IMDb ID requires additional database "
                "optimization to improve search speed. This process may take a few "
                "minutes.\n\n"
                f"The database will double in size from {current} to "
                f"about {projected}.\n\n"
                "Without this optimization, searching without the IMDb ID is not "
                "possible.\n\n"
                "Do you want to proceed?\n"
            )
            msgBox.setIcon(QMessageBox.Icon.Question)
            msgBox.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
            )
            msgBox.button(QMessageBox.StandardButton.Yes).setText("Optimize")
            cb = QCheckBox("Don't ask again")
            msgBox.setCheckBox(cb)
            ret = msgBox.exec()
            if cb.isChecked():
                # This value can be set to anything; the value merely has to exist
                self.settings.setValue(key, "do not show")
            if ret == QMessageBox.StandardButton.Cancel:
                logger.debug("User cancelled index creation")
                self.controller.addIndexCancelled.emit()
                return

        # The user has agreed to creating the index, either previously or just now
        self.progressDialog = QProgressDialog(
            "Optimizing Database...", None, 0, 0, self
        )
        self.progressDialog.setMinimumDuration(0)
        self.progressDialog.setValue(0)
        self.progressDialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progressDialog.setAutoReset(False)

        worker = Worker(create_table_index)
        worker.signals.finished.connect(self.addTitleIndexFinished)
        worker.signals.error.connect(self.addTitleIndexException)
        self.threadpool.start(worker)

    @Slot()
    def addTitleIndexFinished(self) -> None:
        self.controller.addIndexFinished.emit()
        self.progressDialog.reset()

    @Slot(Exception)
    def addTitleIndexException(self, exception: Exception) -> None:
        logger.error(str(exception))
        QMessageBox.critical(self, "Error optimizing dataset", str(exception))
        self.controller.addIndexFailed.emit()
        self.progressDialog.reset()

    @Slot()
    def showAboutDialog(self) -> None:
        aboutDialog = AboutDialog(parent=self)
        aboutDialog.exec()

    @Slot()
    def copyToClipboard(self) -> None:
        text = self.folderLabel.text()
        if text:
            self.clipboard.setText(text)

    @Slot()
    def clipboardDataChanged(self) -> None:
        text = get_imdb(self.clipboard.text())
        if text and text != self.imdbEdit.text():
            logger.debug("IMDb id %s detected in clipboard", text)
            self.resetFields()
            self.imdbEdit.setText(text)
            self.controller.searchRequested.emit()
        else:
            self.controller.clipboardIrrelevantDataInput.emit()

    @Slot()
    def resetFields(self) -> None:
        logger.debug("Resetting fields")
        self.titleEdit.clear()
        self.yearSpinbox.setValue(self.yearSpinbox.minimum())
        self.imdbEdit.clear()
        self.folderLabel.clear()
        self.generated_imdb_id = ""

    @Slot()
    def checkDatabase(self) -> None:
        if database_exists():
            self.showLastUpdated()
            self.controller.databaseVerified.emit()
        else:
            self.controller.databaseVerificationFailed.emit()

    def newDatabase(self) -> None:
        worker = Worker(dataset_downward_size)
        worker.signals.result.connect(self.newDatabaseSizeResult)
        worker.signals.error.connect(self.newDatabaseException)
        self.threadpool.start(worker)

    @Slot(object)
    def newDatabaseSizeResult(self, data: object) -> None:
        size = int(data)
        if size:
            download_size = f"{format_bytes(size)} " if size > 0 else ""
            projected_size = format_bytes(size * 4.7)
            projected_msg = (
                "The dataset will then be converted into a database roughly "
                f"{projected_size} in size, which may take a few minutes."
            )
        else:
            download_size = ""
            projected_msg = (
                "The dataset will then be converted into a database, "
                "which may take a few minutes."
            )

        msgBox = QMessageBox(parent=self)
        msgBox.setWindowTitle("Database Required")
        msgBox.setText(
            "To continue this program will download from IMDb a publicly "
            f"available {download_size}dataset.\n\n"
            f"{projected_msg} "
            "Without this database, the program is unable to function.\n\n"
            "Do you want this program to proceed with the download and conversion?",
        )
        msgBox.setIcon(QMessageBox.Icon.Question)
        msgBox.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        msgBox.button(QMessageBox.StandardButton.Yes).setText("Download")
        ret = msgBox.exec()
        if ret == QMessageBox.StandardButton.Cancel:
            self.controller.datasetCreationRejected.emit()
        else:
            self.controller.updateRequested.emit()

    @Slot(Exception)
    def newDatabaseException(self, exception: Exception) -> None:
        logger.debug("Error getting dataset size")
        logger.error("%s: %s", exception.__class__.__name__, str(exception))
        if not database_exists():
            # Allow for Internet connection problems: prompt again
            self.newDatabaseSizeResult(0)

    def generateFolderName(self) -> None:
        title = self.titleEdit.text()
        # Get the spinbox text, not the value, because minimum value == ""
        year = self.yearSpinbox.text()

        text = f"{sanitise_title(title)} ({year})" if year else sanitise_title(title)
        text = f"{text} [imdbid-{self.imdbEdit.text()}]"
        self.folderLabel.setText(text)

    @Slot()
    def showLastUpdated(self) -> None:
        last_modified = self.convertTimeFromIsoFormat(setting="Last_Modified")
        if last_modified is None:
            self.lastUpdatedLabel.setText("")
        else:
            self.lastUpdatedLabel.setText(
                f"Using IMDb's dataset released {arrow.get(last_modified).humanize()}"
            )

    @Slot(object)
    def movieInfoExtracted(self, movie_infos: list[MovieInfo | None]) -> None:
        logger.info("Located %s titles", len(movie_infos))
        movie_info = None

        if movie_infos is None:
            if self.promptForDatasetUpdate():
                ret = QMessageBox.question(
                    self,
                    "Update local dataset?",
                    "The IMDb id is not found in the dataset.\n\n"
                    "Do you want to update to the latest IMDb dataset?",
                )
                self.settings.setValue("Last_Prompted", datetime.now().isoformat())
                if ret == QMessageBox.StandardButton.Yes:
                    self.controller.updateRequested.emit()
                    return
            self.controller.searchTitleNotFound.emit()
            return

        if len(movie_infos) == 1:
            movie_info = movie_infos[0]
            self.playSound("brrr.mp3")

        elif len(movie_infos) > 1:
            self.playSound("click.mp3")
            selectRecord = SelectRecord(movie_infos=movie_infos, parent=self)
            if selectRecord.exec():
                movie_info = movie_infos[selectRecord.row]

        if movie_info is not None:
            logger.debug("%s (%s)", movie_info.title, movie_info.year)
            self.setMovieInfo(movie_info)
            self.controller.searchTitleFound.emit()
        else:
            self.controller.searchTitleNotFound.emit()

    def setMovieInfo(self, movieInfo: MovieInfo) -> None:
        self.titleEdit.setText(movieInfo.title)

        if movieInfo.year:
            self.yearSpinbox.setValue(movieInfo.year)
        else:
            self.yearSpinbox.setValue(self.yearSpinbox.minimum())

        self.imdbEdit.setText(movieInfo.imdb_id)
        self.generated_imdb_id = movieInfo.imdb_id

    @Slot(Exception)
    def movieInfoException(self, exception: Exception) -> None:
        logger.error("Error getting movie information")
        logger.error("%s: %s", exception.__class__.__name__, str(exception))
        if hasattr(self, "progressDialog"):
            self.progressDialog.reset()
        QMessageBox.critical(self, "Error searching dataset", str(exception))
        self.playSound("error.mp3")
        self.controller.searchDatasetFailed.emit()

    @Slot(str)
    def playSound(self, sound: str) -> None:
        if not self.isActiveWindow():
            logger.debug("Using Qt to play audio")
            play_sound(soundfile=sound)

    def convertTimeFromIsoFormat(self, setting: str) -> datetime | None:
        iso_format = cast(str, self.settings.value(setting, ""))
        if iso_format:
            try:
                return datetime.fromisoformat(iso_format)
            except ValueError:
                logger.error("Invalid %s ISO date time value %s", setting, iso_format)
        return None

    def promptForDatasetUpdate(self) -> bool:
        """
        Determine whether it makes sense to prompt the user whether they want to update
        the IMDb dataset
        :return: True if the user has not been prompted within the last 24 hours and
        the local database was not updated within the last 24 hours
        """

        now = datetime.now()
        delta = timedelta(hours=24)

        last_prompted = self.convertTimeFromIsoFormat(setting="Last_Prompted")
        if last_prompted is not None and now - last_prompted < delta:
            return False

        last_update = self.convertTimeFromIsoFormat(setting="Last_Updated")
        return last_update is not None and now - last_update > delta
