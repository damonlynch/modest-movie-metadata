# Copyright (c) 2022-2023 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

from importlib.resources import files

from qtpy.QtCore import QUrl
from qtpy.QtMultimedia import QAudioOutput, QMediaPlayer

from ..data import audio

player = QMediaPlayer()
audioOutput = QAudioOutput()
player.setAudioOutput(audioOutput)


def play_sound(soundfile: str) -> None:
    player.setSource(QUrl())
    player.setSource(QUrl.fromLocalFile(str(files(audio).joinpath(soundfile))))
    player.play()
