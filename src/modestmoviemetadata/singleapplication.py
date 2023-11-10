# Copyright (c) 2016-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

from qtpy.QtCore import Signal, QTextStream, QStringConverter, Qt
from qtpy.QtNetwork import QLocalSocket, QLocalServer
from qtpy.QtWidgets import QApplication

from .ui.mainwindow import MainWindow


class QtSingleApplication(QApplication):
    """
    Taken from
    http://stackoverflow.com/questions/12712360/qtsingleapplication-for-pyside-or-pyqt
    """

    messageReceived = Signal(str)

    def __init__(self, programId: str, *argv) -> None:
        super().__init__(*argv)
        self._id = programId
        self._activationWindow = None  # type: MainWindow | None
        self._activateOnMessage = False  # type: bool

        # Is there another instance running?
        self._outSocket = QLocalSocket()  # type: QLocalSocket
        self._outSocket.connectToServer(self._id)
        self._isRunning = self._outSocket.waitForConnected()  # type: bool

        self._outStream = None  # type: QTextStream | None
        self._inSocket = None
        self._inStream = None  # type: QTextStream | None
        self._server = None

        if self._isRunning:
            # Yes, there is.
            self._outStream = QTextStream(self._outSocket)
            self._outStream.setEncoding(QStringConverter.Encoding.Utf8)
        else:
            # No, there isn't, at least not properly.
            # Cleanup any past, crashed server.
            error = self._outSocket.error()
            if error == QLocalSocket.LocalSocketError.ConnectionRefusedError:
                self.close()
                QLocalServer.removeServer(self._id)
            self._outSocket = None
            self._server = QLocalServer()
            self._server.listen(self._id)
            self._server.newConnection.connect(self._onNewConnection)

    def close(self) -> None:
        if self._inSocket:
            self._inSocket.disconnectFromServer()
        if self._outSocket:
            self._outSocket.disconnectFromServer()
        if self._server:
            self._server.close()

    def isRunning(self) -> bool:
        return self._isRunning

    def id(self) -> str:
        return self._id

    def activationWindow(self) -> MainWindow:
        return self._activationWindow

    def setActivationWindow(
        self, activationWindow: MainWindow, activateOnMessage: bool = True
    ) -> None:
        self._activationWindow = activationWindow
        self._activateOnMessage = activateOnMessage

    def activateWindow(self) -> None:
        if not self._activationWindow:
            return
        self._activationWindow.setWindowState(
            self._activationWindow.windowState() & ~Qt.WindowState.WindowMinimized
        )
        self._activationWindow.raise_()
        self._activationWindow.activateWindowFromOtherInstance()

    def sendMessage(self, msg) -> bool:
        if not self._outStream:
            return False
        self._outStream << msg << "\n"
        self._outStream.flush()
        return self._outSocket.waitForBytesWritten()

    def _onNewConnection(self) -> None:
        if self._inSocket:
            self._inSocket.readyRead.disconnect(self._onReadyRead)
        self._inSocket = self._server.nextPendingConnection()
        if not self._inSocket:
            return
        self._inStream = QTextStream(self._inSocket)
        self._inStream.setEncoding(QStringConverter.Encoding.Utf8)
        self._inSocket.readyRead.connect(self._onReadyRead)
        if self._activateOnMessage:
            self.activateWindow()

    def _onReadyRead(self) -> None:
        while True:
            msg = self._inStream.readLine()
            if not msg:
                break
            self.messageReceived.emit(msg)
