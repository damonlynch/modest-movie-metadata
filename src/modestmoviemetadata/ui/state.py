#  SPDX-FileCopyrightText: 2026 Damon Lynch <damonlynch@gmail.com>
#  SPDX-License-Identifier: GPL-3.0-or-later

from qtpy.QtStateMachine import QFinalState, QState

from modestmoviemetadata.tools.logtools import get_logger

logger = get_logger()


class State(QState):
    def __init__(self, name: str, parent: QState | None = None) -> None:
        super().__init__(parent)
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
