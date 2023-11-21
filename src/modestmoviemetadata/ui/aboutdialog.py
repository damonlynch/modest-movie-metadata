# Copyright (c) 2016-2022 Damon Lynch
# SPDX - License - Identifier: GPL-3.0-or-later

from qtpy.QtCore import Qt, Slot, QObject, QPointF
import qtpy.QtCore as QtCore
import qtpy
from qtpy.QtGui import (
    QFont,
    QImage,
    QPainter,
    QFontMetricsF,
    QPaintEvent,
    QPixmap,
    QPen,
    QColor,
)


from qtpy.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QDialogButtonBox,
    QSizePolicy,
    QHBoxLayout,
    QStackedWidget,
    QWidget,
    QScrollArea,
    QPushButton,
)

from ..tools.utilities import data_file_path, pyqt_api
from ..config import version, application_name, copyright_message


class AboutDialog(QDialog):
    """
    Display an About window
    """

    def __init__(self, parent: QObject = None) -> None:
        super().__init__(parent)

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)

        path = data_file_path("splashscreen600.jpg")
        url = path.as_posix()

        self.setObjectName("AboutDialog")
        self.setStyleSheet(
            "QDialog#AboutDialog {background-image: url(%(url)s);}" % dict(url=url)
        )
        self.setFixedSize(QImage(str(path)).size())

        self.margin = 16
        self.padding = 6
        self.setupTitleVersion()

        transparency = "rgba(240, 240, 242, 200)"

        # Standard About view

        personal_website = "https://damonlynch.net"
        link_style = 'style="color: black;"'

        gpl3link = "https://www.gnu.org/licenses/gpl-3.0.html"
        lgpl3link = "https://www.gnu.org/licenses/lgpl-3.0.html"

        msg = f"""{copyright_message}<br><br>
        <a href="{personal_website}" {link_style}>
        damonlynch.net</a><br><br>
        This program comes with absolutely no warranty.<br>
        See the <a href="{gpl3link}" {link_style}>GNU 
        General Public License, version 3 or later</a> for details.
        """

        details = QLabel(msg)

        details_style_sheet = """QLabel {
        color: black;
        background-color: %(transparency)s;
        margin-left: 0px;
        padding-left: %(left_margin)dpx;
        padding-top: 6px;
        padding-right: 6px;
        padding-bottom: 6px;
        }""" % dict(
            left_margin=self.margin, transparency=transparency
        )

        details.setStyleSheet(details_style_sheet)
        details.setOpenExternalLinks(True)
        details.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        font = self.font()  # type: QFont
        details.setFont(font)

        aboutLayout = QVBoxLayout()
        aboutLayout.setContentsMargins(0, 0, 0, 0)
        aboutLayout.addSpacing(150)
        detailsLayout = QHBoxLayout()
        detailsLayout.setContentsMargins(0, 0, 0, 0)
        detailsLayout.addWidget(details)
        detailsLayout.addStretch(10)
        aboutLayout.addLayout(detailsLayout)
        aboutLayout.addStretch(10)

        about = QWidget()
        about.setLayout(aboutLayout)

        # Credits view

        photolink = f"""<a href="https://www.flickr.com/photos/damonlynch/53347185963/" {link_style}>High-altitude power poles in Tajikistan</a>"""
        program_icon = f'<a href="https://www.flaticon.com/free-icon/letter-m_6431117" {link_style}>Smashicons - Flaticon</a>'
        video_folder = f'<a href="https://www.flaticon.com/free-icon/video_6302563" {link_style}>Freepik - Flaticon</a>'
        sound_pixabay = f"""<a href="https://pixabay.com/sound-effects/game-ui-sounds-14857/" {link_style}>Pixabay</a>"""

        gpl3desc = f', licensed under the <a href="{gpl3link}" {link_style}>GNU General Public License, version 3</a>'
        lgpl3desc = f', licensed under the <a href="{lgpl3link}" {link_style}>GNU Lesser General Public License, version 3</a>'

        if pyqt_api():
            api_version = qtpy.PYQT_VERSION
            api_name = "PyQt"
            qt_licence = gpl3desc
        else:
            api_version = qtpy.PYSIDE_VERSION
            api_name = "PySide"
            qt_licence = lgpl3desc

        credits_text = f"""
        {copyright_message}

        Photo {photolink} copyright © 2023 Damon Lynch, all rights reserved.
        
        Program icon courtesy of {program_icon}.
        Video folder courtesy of {video_folder}.
        Sound effect courtesy of {sound_pixabay}.
        
        Uses {api_name} {api_version}{qt_licence}.
        Uses Qt {QtCore.__version__}{lgpl3desc}.
        """

        credits_text = credits_text.replace("\n", "<br>\n")

        label_style_sheet = """QLabel {
        background-color: rgba(0, 0, 0, 0);
        color: black;
        padding-left: %(left_margin)dpx;
        padding-top: 6px;
        padding-right: 6px;
        padding-bottom: 6px;
        }""" % dict(
            left_margin=self.margin
        )

        creditsLabel = QLabel(credits_text)
        creditsLabel.setFont(font)
        creditsLabel.setStyleSheet(label_style_sheet)
        creditsLabel.setOpenExternalLinks(True)

        credits = QScrollArea()
        credits.setWidget(creditsLabel)
        scroll_area_style_sheet = """QScrollArea {
        background-color: %(transparency)s;
        border: 0px;
        }
        """ % dict(
            transparency=transparency
        )
        credits.setStyleSheet(scroll_area_style_sheet)

        mainLayout = QVBoxLayout()

        self.stack = QStackedWidget()
        self.stack.addWidget(about)
        self.stack.addWidget(credits)
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        buttonBox = QDialogButtonBox()
        closeButton = buttonBox.addButton(
            QDialogButtonBox.StandardButton.Close
        )  # type: QPushButton
        self.creditsButton = buttonBox.addButton(
            "Credits", QDialogButtonBox.ButtonRole.HelpRole
        )  # type: QPushButton
        self.creditsButton.setDefault(False)
        self.creditsButton.setCheckable(True)
        closeButton.setDefault(True)

        buttonLayout = QVBoxLayout()
        buttonLayout.addWidget(buttonBox)
        buttonLayout.setContentsMargins(
            self.margin, self.margin, self.margin, self.margin
        )

        mainLayout.setContentsMargins(0, 0, 0, 0)

        mainLayout.addSpacing(self.title_version_height)
        mainLayout.addWidget(self.stack)
        mainLayout.addLayout(buttonLayout)

        self.setLayout(mainLayout)

        buttonBox.rejected.connect(self.reject)
        self.creditsButton.clicked.connect(self.creditsButtonClicked)

        closeButton.setFocus()

    @Slot()
    def creditsButtonClicked(self) -> None:
        self.showStackItem()

    @Slot()
    def showStackItem(self) -> None:
        if self.creditsButton.isChecked():
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)

    def setupTitleVersion(self) -> None:
        self.title = application_name
        self.titleFont = QFont()
        self.titleFont.setPointSize(self.titleFont.pointSize() + 12)
        self.titleFont.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 95.0)
        fm = QFontMetricsF(self.titleFont)
        title_height = fm.height()
        title_width = fm.horizontalAdvance(self.title)

        self.versionFont = QFont()
        fm = QFontMetricsF(self.versionFont)
        version_height = fm.height()
        version_width = fm.horizontalAdvance(version)

        self.margin_top = self.margin / (self.width() / self.height())

        self.title_y = self.margin_top + title_height
        self.version_y = self.title_y + version_height * 2

        self.title_version_width = int(
            max(title_width, version_width) + self.margin * 2 + self.padding * 2
        )
        self.title_version_height = int(self.version_y + self.margin)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        image = QPixmap(self.title_version_width, self.title_version_height)
        image.fill(QColor("#6B87BF"))
        painter.drawPixmap(0, 0, image)
        painter.setPen(QPen(Qt.GlobalColor.white))
        painter.setFont(self.titleFont)
        painter.drawText(
            QPointF(self.margin - 1 + self.padding, self.title_y), self.title
        )
        painter.setFont(self.versionFont)
        painter.drawText(QPointF(self.margin + self.padding, self.version_y), version)
        painter.end()
