
"""Christmas Radio - interactieve Windows-app.
Deze eerste versie bevat nog geen live radioverbinding.
"""

import sys
from pathlib import Path

from PySide6.QtCore import (
    QDateTime,
    QRectF,
    QSettings,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QMessageBox,
    QWidget,
)


class ChristmasRadio(QWidget):
    BASE_W = 1672
    BASE_H = 941

    SERVERS = [
        "TG-103 Voorburg",
        "TG-108 Heerlen",
    ]

    AREAS = {
        "min": (1420, 0, 1502, 48),
        "max": (1503, 0, 1573, 48),
        "close": (1574, 0, 1672, 48),

        "down": (49, 501, 191, 563),
        "scan": (198, 500, 264, 563),
        "up": (275, 501, 419, 564),

        "talk": (482, 608, 816, 713),

        "volume": (69, 620, 201, 727),
        "vox_knob": (259, 619, 384, 731),

        "ptt_vox": (881, 497, 1024, 543),
        "mute": (1028, 497, 1167, 544),
        "webcam": (881, 550, 1025, 599),
        "roger": (1028, 550, 1170, 599),

        "leden": (1215, 331, 1326, 391),
        "chat": (1327, 331, 1423, 391),
        "nieuws": (1424, 331, 1516, 391),
        "instellingen": (1517, 331, 1644, 391),

        "server": (8, 859, 430, 938),
        "naam": (432, 860, 711, 938),
    }

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint,
        )

        self.setWindowTitle("Christmas Radio")

        image_path = (
            Path(__file__).resolve().parent /
            "christmas_radio.png"
        )

        self.background = QPixmap(str(image_path))

        if self.background.isNull():
            raise FileNotFoundError(
                "De afbeelding christmas_radio.png "
                "moet naast main.py staan."
            )

        self.preferences = QSettings(
            "ChristmasRadio",
            "ChristmasRadio",
        )

        self.nickname = str(
            self.preferences.value("nickname", "Gast")
        )

        self.group = str(
            self.preferences.value(
                "group",
                self.SERVERS[0],
            )
        )

        self.channel = max(
            1,
            min(
                40,
                int(
                    self.preferences.value(
                        "channel",
                        14,
                    )
                ),
            ),
        )

        self.muted = False
        self.roger = False
        self.vox = False
        self.test_ptt = False

        self.tab = "leden"

        self.volume = 65
        self.vox_sensitivity = 40

        self.drag_point = None

        self.setMinimumSize(1000, 563)
        self.resize(1440, 811)
        self.setMouseTracking(True)

        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update)
        self.clock.start(1000)

    def scale_and_offset(self):
        scale = min(
            self.width() / self.BASE_W,
            self.height() / self.BASE_H,
        )

        dx = (
            self.width() -
            self.BASE_W * scale
        ) / 2

        dy = (
            self.height() -
            self.BASE_H * scale
        ) / 2

        return scale, dx, dy

    def image_position(self, point):
        scale, dx, dy = self.scale_and_offset()

        return (
            (point.x() - dx) / scale,
            (point.y() - dy) / scale,
        )

    def hit(self, x, y, name):
        a, b, c, d = self.AREAS[name]

        return (
            a <= x <= c and
            b <= y <= d
        )

    @staticmethod
    def plate(
        painter,
        coords,
        fill,
        border="#136f3c",
        radius=10,
    ):
        painter.setPen(
            QPen(QColor(border), 2)
        )

        painter.setBrush(
            QColor(fill)
        )

        painter.drawRoundedRect(
            QRectF(*coords),
            radius,
            radius,
        )

    @staticmethod
    def text(
        painter,
        coords,
        value,
        size,
        color="#ffffff",
        bold=True,
    ):
        font = QFont("Segoe UI", size)
        font.setBold(bold)

        painter.setFont(font)
        painter.setPen(QColor(color))

        painter.drawText(
            QRectF(*coords),
            Qt.AlignmentFlag.AlignCenter,
            value,
        )

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.fillRect(
            self.rect(),
            QColor("#010b08"),
        )

        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        scale, dx, dy = self.scale_and_offset()

        painter.drawPixmap(
            QRectF(
                dx,
                dy,
                self.BASE_W * scale,
                self.BASE_H * scale,
            ),
            self.background,
            QRectF(
                0,
                0,
                self.background.width(),
                self.background.height(),
            ),
        )

        painter.translate(dx, dy)
        painter.scale(scale, scale)

        # Kanaalnummer

        self.plate(
            painter,
            (83, 405, 115, 64),
            "#030e08",
            "#030e08",
            3,
        )

        self.text(
            painter,
            (83, 405, 115, 64),
            str(self.channel),
            40,
            "#6eff73",
        )

        # Actuele klok

        self.plate(
            painter,
            (276, 408, 119, 60),
            "#030e08",
            "#030e08",
            3,
        )

        self.text(
            painter,
            (276, 408, 119, 60),
            QDateTime.currentDateTime().toString(
                "HH:mm"
            ),
            29,
            "#77ff9c",
        )

        # Kanaalchat nummer

        self.plate(
            painter,
            (1505, 277, 89, 39),
            "#03120a",
            "#03120a",
            3,
        )

        self.text(
            painter,
            (1505, 277, 89, 39),
            f"CH {self.channel}",
            24,
        )

        # Geen fictieve live weergegevens tonen

        self.plate(
            painter,
            (1016, 392, 138, 80),
            "#030e08",
            "#030e08",
            4,
        )

        self.text(
            painter,
            (1016, 398, 138, 38),
            "-- °C",
            27,
            "#a3ffc0",
        )

        self.text(
            painter,
            (1016, 443, 138, 24),
            "GEEN LIVE WEER",
            12,
        )

        # Verbindingsstatus

        self.plate(
            painter,
            (572, 772, 173, 52),
            "#04140b",
            "#2b6c3e",
            8,
        )

        self.text(
            painter,
            (575, 776, 167, 45),
            "● OFFLINE",
            22,
            "#ff7777",
        )

        # Geselecteerde TG-groep

        self.plate(
            painter,
            (11, 864, 416, 59),
            "#02110c",
            "#21633d",
            5,
        )

        self.text(
            painter,
            (17, 866, 406, 54),
            f"Gekozen: {self.group}",
            19,
            "#97eed6",
        )

        # Gebruikersnaam

        self.plate(
            painter,
            (438, 866, 275, 53),
            "#02110c",
            "#21633d",
            5,
        )

        self.text(
            painter,
            (445, 868, 260, 49),
            f"Gebruiker: {self.nickname}",
            18,
        )

        # Ping nog niet beschikbaar

        self.plate(
            painter,
            (1206, 870, 76, 48),
            "#05120b",
            "#05120b",
            3,
        )

        self.text(
            painter,
            (1206, 870, 76, 48),
            "-- ms",
            17,
            "#aaffaa",
        )

        # Datum en tijd

        self.plate(
            painter,
            (1519, 861, 112, 65),
            "#06130d",
            "#06130d",
            3,
        )

        self.text(
            painter,
            (1519, 864, 112, 28),
            QDateTime.currentDateTime().toString(
                "HH:mm"
            ),
            19,
        )

        self.text(
            painter,
            (1519, 896, 112, 27),
            QDateTime.currentDateTime().toString(
                "dd-MM-yyyy"
            ),
            13,
        )

        # Ledenpaneel
        # Voorbeeldpersonen uit de afbeelding verbergen
        # totdat er echte ledeninformatie beschikbaar is.

        self.plate(
            painter,
            (1217, 401, 415, 332),
            "#F503150F",
            "#1a6547",
            12,
        )

        self.plate(
            painter,
            (1221, 339, 102, 43),
            "#94071b",
            "#d6b45e",
            7,
        )

        self.text(
            painter,
            (1221, 340, 102, 41),
            "LEDEN (0)",
            17,
        )

        if self.tab == "leden":
            heading = "Nog geen live leden"
            description = (
                "Radioverbinding wordt later gekoppeld"
            )

        elif self.tab == "chat":
            heading = "Kanaalchat"
            description = (
                "Chat is nog niet gekoppeld"
            )

        elif self.tab == "nieuws":
            heading = "Prettige Kerstdagen!"
            description = (
                "Welkom bij Christmas Radio"
            )

        else:
            heading = "Instellingen"
            description = (
                "Klik hier voor je naam of serverkeuze"
            )

        self.text(
            painter,
            (1230, 460, 388, 55),
            heading,
            22,
            "#f8dd8c",
        )

        self.text(
            painter,
            (1232, 519, 386, 70),
            description,
            13,
            "#e9fff1",
        )

        # PTT-knop ingedrukt (visuele test)

        if self.test_ptt:
            self.plate(
                painter,
                (498, 617, 314, 94),
                "#a20c24",
                "#ffdc71",
                15,
            )

            self.text(
                painter,
                (502, 624, 306, 80),
                "PTT-TEST",
                32,
            )

        # Mute-indicator

        if self.muted:
            self.text(
                painter,
                (1045, 492, 110, 53),
                "MUTE AAN",
                14,
                "#ff3535",
            )

        # Rogerpiep-indicator

        if self.roger:
            self.text(
                painter,
                (1050, 545, 101, 48),
                "ROGER AAN",
                12,
                "#6dff74",
            )

        # VOX-indicator

        if self.vox:
            self.text(
                painter,
                (890, 492, 132, 53),
                "VOX AAN",
                14,
                "#6dff74",
            )

        painter.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        x, y = self.image_position(
            event.position()
        )

        # Vensterbediening

        if self.hit(x, y, "min"):
            self.showMinimized()

        elif self.hit(x, y, "max"):
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

        elif self.hit(x, y, "close"):
            self.close()

        # TALK-knop

        elif self.hit(x, y, "talk"):
            self.test_ptt = True
            self.update()

        # Kanaal omhoog

        elif self.hit(x, y, "up"):
            self.change_channel(1)

        # Kanaal omlaag

        elif self.hit(x, y, "down"):
            self.change_channel(-1)

        # Scan

        elif self.hit(x, y, "scan"):
            QMessageBox.information(
                self,
                "Kanaalscan",
                "Kanaalscan volgt bij de radioverbinding.",
            )

        # Microfoon mute

        elif self.hit(x, y, "mute"):
            self.muted = not self.muted
            self.update()

        # Rogerpiep

        elif self.hit(x, y, "roger"):
            self.roger = not self.roger
            self.update()

        # VOX

        elif self.hit(x, y, "ptt_vox"):
            self.vox = not self.vox
            self.update()

        # Webcam

        elif self.hit(x, y, "webcam"):
            QMessageBox.information(
                self,
                "Webcam",
                "De webcamfunctie is nog niet gekoppeld.",
            )

        # Volume-instelling

        elif self.hit(x, y, "volume"):
            self.adjust_knob("volume")

        # VOX-gevoeligheid

        elif self.hit(x, y, "vox_knob"):
            self.adjust_knob("vox_sensitivity")

        # TG-groep

        elif self.hit(x, y, "server"):
            self.choose_group()

        # Gebruikersnaam

        elif self.hit(x, y, "naam"):
            self.choose_name()

        # Tabbladen

        elif any(
            self.hit(x, y, name)
            for name in (
                "leden",
                "chat",
                "nieuws",
                "instellingen",
            )
        ):
            for name in (
                "leden",
                "chat",
                "nieuws",
                "instellingen",
            ):
                if self.hit(x, y, name):
                    self.tab = name

                    if name == "instellingen":
                        self.open_settings()

                    self.update()
                    break

        # Venster slepen

        elif 0 <= y <= 46 and x < 1415:
            self.drag_point = (
                event.globalPosition().toPoint() -
                self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if (
            self.drag_point is not None and
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            if not self.isMaximized():
                self.move(
                    event.globalPosition().toPoint() -
                    self.drag_point
                )
            return

        x, y = self.image_position(
            event.position()
        )

        clickable = any(
            self.hit(x, y, name)
            for name in self.AREAS
        )

        if clickable:
            self.setCursor(
                Qt.CursorShape.PointingHandCursor
            )
        else:
            self.setCursor(
                Qt.CursorShape.ArrowCursor
            )

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_point = None

            if self.test_ptt:
                self.test_ptt = False
                self.update()

    def mouseDoubleClickEvent(self, event):
        _, y = self.image_position(
            event.position()
        )

        if y < 48:
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

    def change_channel(self, delta):
        self.channel = (
            (self.channel - 1 + delta) % 40
        ) + 1

        self.preferences.setValue(
            "channel",
            self.channel,
        )

        self.update()

    def adjust_knob(self, name):
        current = getattr(self, name)

        if name == "volume":
            label = "Volume"
        else:
            label = "VOX-gevoeligheid"

        value, ok = QInputDialog.getInt(
            self,
            label,
            f"{label} (0 t/m 100):",
            current,
            0,
            100,
            1,
        )

        if ok:
            setattr(self, name, value)

            QMessageBox.information(
                self,
                label,
                "Waarde bewaard voor deze sessie. "
                "Audio volgt later.",
            )

    def choose_group(self):
        if self.group in self.SERVERS:
            index = self.SERVERS.index(self.group)
        else:
            index = 0

        group, ok = QInputDialog.getItem(
            self,
            "Gespreksgroep",
            "Kies een TG-groep:",
            self.SERVERS,
            index,
            False,
        )

        if ok:
            self.group = group

            self.preferences.setValue(
                "group",
                group,
            )

            self.update()

    def choose_name(self):
        name, ok = QInputDialog.getText(
            self,
            "Gebruikersnaam",
            "Jouw naam:",
            text=self.nickname,
        )

        if ok and name.strip():
            self.nickname = name.strip()[:32]

            self.preferences.setValue(
                "nickname",
                self.nickname,
            )

            self.update()

    def open_settings(self):
        choice, ok = QInputDialog.getItem(
            self,
            "Instellingen",
            "Wat wil je aanpassen?",
            [
                "Gebruikersnaam",
                "TG-groep",
            ],
            0,
            False,
        )

        if ok:
            if choice == "Gebruikersnaam":
                self.choose_name()
            else:
                self.choose_group()


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(
        "Christmas Radio"
    )

    try:
        window = ChristmasRadio()

    except FileNotFoundError as error:
        QMessageBox.critical(
            None,
            "Christmas Radio",
            str(error),
        )
        sys.exit(1)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
