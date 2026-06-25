#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

from qtpy.QtCore import QObject, Signal
from qtpy.QtStateMachine import QFinalState, QHistoryState, QState

from modestmoviemetadata.tools.logtools import get_logger

logger = get_logger()


class State(QState):
    def __init__(
        self,
        name: str,
        childMode: QState.ChildMode = QState.ChildMode.ExclusiveStates,
        parent: QState | None = None,
    ) -> None:
        super().__init__(childMode=childMode, parent=parent)
        self.setObjectName(name)

    def onEntry(self, event):
        logger.debug(f"ENTER: {self.objectName()}")

    def onExit(self, event):
        logger.debug(f"EXIT: {self.objectName()}")


class HistoryState(QHistoryState):
    def __init__(self, name: str, parent: QState) -> None:
        super().__init__(parent)
        assert parent is not None
        self.setObjectName(name)

    def onEntry(self, event):
        logger.debug(f"ENTER: {self.objectName()}")

    def onExit(self, event):
        logger.debug(f"EXIT: {self.objectName()}")


class FinalState(QFinalState):
    def __init__(self, name: str, parent: QState | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(name)

    def onEntry(self, event):
        logger.debug(f"ENTER: {self.objectName()}")

    def onExit(self, event):
        logger.debug(f"EXIT: {self.objectName()}")


class StateMachineSignals(QObject):
    machineClosing = Signal()
    machineInitialized = Signal()
    databaseValid = Signal()
    databaseInvalid = Signal()
    update = Signal()
    updateFinished = Signal()
    updateError = Signal()
    searchDataset = Signal()
    searchDatasetTitleFound = Signal()
    searchDatasetTitleNotFound = Signal()
    searchDatasetInsufficientData = Signal()
    searchDatasetError = Signal()
    addTitleIndex = Signal()
    addTitleIndexCancelled = Signal()
    addTitleIndexFinished = Signal()
    addTitleIndexRefused = Signal()
    addTitleIndexError = Signal()
    doNotCreateDataset = Signal()
    copyToClipboard = Signal()
