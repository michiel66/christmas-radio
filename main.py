
"""Christmas Radio v2 - Windows kerstinterface.

Vereist: PySide6 en christmas_radio.png naast main.py.
Deze versie heeft nog geen echte spraakverbinding.
"""

import sys
from pathlib import Path

from PySide6.QtCore import (
    QDateTime, QPointF, QRectF, QSettings, Qt, QTimer
)
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap
)
from PySide6.QtWidgets import (
    QApplication, QInputDialog, QMessageBox, QWidget
)


class ChristmasRadio(QWidget):
    ART_W, ART_H = 1672, 941

    GROUPS = (
        "TG-103 Voorburg",
        "TG-108 Heerlen",
    )

    # Klikvlakken in de originele afbeelding
    BUTTONS = {
        "min": (1436, 0, 1499, 48),
        "max": (1501, 0, 1578, 48),
        "close": (1579, 0, 1672, 48),

        "channel_down": (48, 498, 193, 564),
        "scan": (201, 498, 266, 564),
        "channel_up": (273, 498, 422, 564),

        "volume": (74, 623, 199, 734),
        "sensitivity": (265, 622, 392, 733),

        "talk": (482, 603, 823, 715),

        "vox": (882, 498, 1024, 543),
        "mute": (1028, 498, 1169, 543),
        "webcam": (882, 551, 1024, 598),
        "roger": (1028, 551, 1169, 598),

        "group": (50, 868, 425, 928),
        "nickname": (475, 869, 722, 927),
    }

    TAB_RECTS = {
        "leden": (1219, 338, 1321, 389),
        "chat": (1328, 338, 1417, 389),
        "nieuws": (1425, 338, 1509, 389),
        "instellingen": (1515, 338, 1638, 389),
    }

    SETTINGS_RECTS = {
        "naam": (1240, 490, 1610, 542),
        "groep": (1240, 553, 1610, 605),
        "volume": (1240, 616, 1610, 668),
        "vox": (1240, 679, 1610, 731),
    }

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )

        self.setWindowTitle("Christmas Radio")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(835, 471)

        folder = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(__file__).resolve().parent
            )
        )

        self.art = QPixmap(
            str(folder / "christmas_radio.png")
        )

        if self.art.isNull():
            raise FileNotFoundError(
                "christmas_radio.png ontbreekt naast main.py."
            )

        self.settings = QSettings(
            "ChristmasRadio",
            "ChristmasRadio"
        )

        self.nickname = str(
            self.settings.value("nickname", "Gast")
        )[:32]

        self.group = str(
            self.settings.value(
                "group",
                self.GROUPS[0]
            )
        )

        if self.group not in self.GROUPS:
            self.group = self.GROUPS[0]

        try:
            self.channel = max(
                1,
                min(
                    40,
                    int(self.settings.value("channel", 14))
                )
            )

            self.volume = max(
                0,
                min(
                    100,
                    int(self.settings.value("volume", 65))
                )
            )

            self.sensitivity = max(
                0,
                min(
                    100,
                    int(self.settings.value("sensitivity", 40))
                )
            )

        except (TypeError, ValueError):
            self.channel = 14
            self.volume = 65
            self.sensitivity = 40

        self.muted = self.settings.value(
            "muted",
            False,
            type=bool
        )

        self.vox = self.settings.value(
            "vox",
            False,
            type=bool
        )

        self.roger = self.settings.value(
            "roger",
            False,
            type=bool
        )

        self.active_tab = "leden"

        self.news_notice = (
            "De Windows-radio is klaar voor de"
        )

        self.news_detail = (
            "volgende stap: live communicatie."
        )

        self.ptt_pressed = False
        self.drag_offset = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)

        # Schalen naar beschikbare schermruimte
        screen = QApplication.primaryScreen()

        if screen:
            available = screen.availableGeometry()

            ratio = min(
                1.0,
                (available.width() - 18) / self.ART_W,
                (available.height() - 18) / self.ART_H
            )

            self.resize(
                round(self.ART_W * ratio),
                round(self.ART_H * ratio)
            )

            self.move(
                available.center() -
                self.rect().center()
            )
        else:
            self.resize(1254, 706)

    def save(self):
        names = (
            "nickname",
            "group",
            "channel",
            "volume",
            "sensitivity",
            "muted",
            "vox",
            "roger",
        )

        for name in names:
            self.settings.setValue(
                name,
                getattr(self, name)
            )

    def image_coords(self, point):
        scale = min(
            self.width() / self.ART_W,
            self.height() / self.ART_H
        )

        left = (
            self.width() - self.ART_W * scale
        ) / 2

        top = (
            self.height() - self.ART_H * scale
        ) / 2

        return (
            (point.x() - left) / scale,
            (point.y() - top) / scale
        )

    @staticmethod
    def contains(rect, x, y):
        x1, y1, x2, y2 = rect

        return (
            x1 <= x <= x2 and
            y1 <= y <= y2
        )

    @staticmethod
    def text(
        painter,
        text,
        box,
        size=19,
        color="#ffffff",
        bold=True,
        align=Qt.AlignmentFlag.AlignCenter,
    ):
        font = QFont("Segoe UI", size)
        font.setBold(bold)

        painter.setFont(font)
        painter.setPen(QColor(color))

        painter.drawText(
            QRectF(*box),
            align,
            str(text)
        )

    @staticmethod
    def plate(
        painter,
        box,
        top="#062219",
        bottom="#03110e",
        stroke="#377858",
        radius=9,
    ):
        x, y, w, h = box

        gradient = QLinearGradient(
            x, y, x, y + h
        )

        gradient.setColorAt(
            0,
            QColor(top)
        )

        gradient.setColorAt(
            1,
            QColor(bottom)
        )

        painter.setBrush(gradient)

        painter.setPen(
            QPen(QColor(stroke), 1.4)
        )

        painter.drawRoundedRect(
            QRectF(x, y, w, h),
            radius,
            radius
        )

    @staticmethod
    def value_background(
        painter,
        box,
        color="#051409"
    ):
        painter.fillRect(
            QRectF(*box),
            QColor(color)
        )

    def paintEvent(self, event):
        p = QPainter(self)

        p.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )

        p.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        p.fillRect(
            self.rect(),
            QColor("#020b0b")
        )

        scale = min(
            self.width() / self.ART_W,
            self.height() / self.ART_H
        )

        left = (
            self.width() - self.ART_W * scale
        ) / 2

        top = (
            self.height() - self.ART_H * scale
        ) / 2

        p.translate(left, top)
        p.scale(scale, scale)

        # Originele kerstafbeelding
        p.drawPixmap(0, 0, self.art)

        # Kanaaldisplay
        self.value_background(
            p,
            (82, 402, 120, 70),
            "#021107"
        )

        self.text(
            p,
            self.channel,
            (82, 402, 120, 66),
            43,
            "#6fff70"
        )

        # Actuele klok
        self.value_background(
            p,
            (275, 400, 137, 70),
            "#011006"
        )

        self.text(
            p,
            QDateTime.currentDateTime().toString(
                "HH:mm"
            ),
            (275, 401, 137, 67),
            37,
            "#86ff9c"
        )

        # Kanaalchat-nummer
        self.value_background(
            p,
            (1539, 281, 54, 38),
            "#03140b"
        )

        self.text(
            p,
            str(self.channel),
            (1539, 280, 54, 39),
            25
        )

        # Geen fictieve live weersinformatie
        self.value_background(
            p,
            (1015, 399, 147, 72),
            "#011007"
        )

        self.text(
            p,
            "-- °C",
            (1015, 398, 147, 45),
            31,
            "#86ff9c"
        )

        self.text(
            p,
            "GEEN LIVE WEER",
            (1016, 442, 145, 26),
            12
        )

        # Signaalmeter (offline)
        self.value_background(
            p,
            (464, 397, 303, 70),
            "#010e06"
        )

        for i in range(11):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#45594e"))

            p.drawRoundedRect(
                QRectF(
                    468 + i * 27,
                    419,
                    23,
                    17
                ),
                3,
                3
            )

        self.text(
            p,
            "S   1   3   5   7   9   +30",
            (479, 440, 279, 27),
            17,
            "#c9ded0"
        )

        # RX / TX / BUSY
        self.value_background(
            p,
            (801, 398, 162, 69),
            "#010f08"
        )

        for x in (838, 889, 941):
            p.setPen(
                QPen(QColor("#45584e"), 1)
            )

            p.setBrush(
                QColor("#384c44")
            )

            p.drawEllipse(
                QPointF(x, 414),
                10,
                10
            )

        self.text(
            p,
            "RX",
            (810, 439, 55, 27),
            18,
            "#d7e4da"
        )

        self.text(
            p,
            "TX",
            (864, 439, 55, 27),
            18,
            "#d7e4da"
        )

        self.text(
            p,
            "BUSY",
            (917, 439, 64, 27),
            16,
            "#d7e4da"
        )

        # Offline indicator
        self.plate(
            p,
            (574, 775, 171, 49),
            "#1c1619",
            "#170e11",
            "#cf6969",
            10
        )

        self.text(
            p,
            "● OFFLINE",
            (580, 777, 160, 45),
            22,
            "#ffb2b6"
        )

        # TALK-knop visuele test
        if self.ptt_pressed:
            p.setPen(
                QPen(QColor("#ff4149"), 5)
            )

            p.setBrush(
                Qt.BrushStyle.NoBrush
            )

            p.drawRoundedRect(
                QRectF(
                    500, 613, 316, 97
                ),
                13,
                13
            )

            self.plate(
                p,
                (705, 589, 114, 27),
                "#9b1322",
                "#63111d",
                "#ffbda8",
                5
            )

            self.text(
                p,
                "PTT-TEST",
                (708, 590, 109, 25),
                14
            )

        # Actieve kleine knoppen
        for active, rect in (
            (self.muted, (1033, 498, 132, 43)),
            (self.vox, (886, 498, 133, 43)),
            (self.roger, (1033, 550, 132, 46)),
        ):
            if active:
                p.setPen(
                    QPen(
                        QColor("#e8bd44"),
                        3.5
                    )
                )

                p.setBrush(
                    Qt.BrushStyle.NoBrush
                )

                p.drawRoundedRect(
                    QRectF(*rect),
                    8,
                    8
                )

                p.setPen(
                    Qt.PenStyle.NoPen
                )

                p.setBrush(
                    QColor("#35fc7c")
                )

                p.drawEllipse(
                    QPointF(
                        rect[0] + rect[2] - 8,
                        rect[1] + 6
                    ),
                    4,
                    4
                )

        # Onderbalk TG-groep
        self.plate(
            p,
            (55, 869, 365, 52),
            "#04231a",
            "#051710",
            "#2d795c",
            5
        )

        self.text(
            p,
            f"Gekozen: {self.group}",
            (64, 875, 346, 37),
            18,
            "#a7faff"
        )

        # Gebruikersnaam
        self.plate(
            p,
            (495, 869, 230, 52),
            "#052018",
            "#051510",
            "#2d795c",
            5
        )

        nick = self.nickname

        if len(nick) > 16:
            nick = nick[:15] + "…"

        self.text(
            p,
            f"Gebruiker: {nick}",
            (501, 875, 218, 37),
            18
        )

        # Ping niet beschikbaar
        self.value_background(
            p,
            (1190, 879, 87, 30),
            "#041a13"
        )

        self.text(
            p,
            "-- ms",
            (1190, 876, 87, 35),
            19,
            "#a0b5ab"
        )

        # Datum en tijd
        self.value_background(
            p,
            (1527, 868, 110, 57),
            "#051612"
        )

        now = QDateTime.currentDateTime()

        self.text(
            p,
            now.toString("HH:mm"),
            (1527, 870, 110, 25),
            17
        )

        self.text(
            p,
            now.toString("dd-MM-yyyy"),
            (1527, 896, 110, 25),
            13
        )

        # Rechterpaneel
        self.draw_side_panel(p)

        p.end()

    def draw_side_panel(self, p):
        self.plate(
            p,
            (1219, 403, 410, 347),
            "#092a20",
            "#03130f",
            "#286a4c",
            12
        )

        # Tabbladen
        for key, rect in self.TAB_RECTS.items():
            x1, y1, x2, y2 = rect

            active = (
                key == self.active_tab
            )

            self.plate(
                p,
                (
                    x1,
                    y1,
                    x2 - x1,
                    y2 - y1
                ),
                "#b51c26" if active else "#174735",
                "#5b0c18" if active else "#06251b",
                "#efcb77" if active else "#378861",
                9
            )

            labels = {
                "leden": "LEDEN (0)",
                "chat": "CHAT",
                "nieuws": "NIEUWS",
                "instellingen": "INSTELLINGEN",
            }

            self.text(
                p,
                labels[key],
                (
                    x1 + 3,
                    y1 + 4,
                    x2 - x1 - 6,
                    y2 - y1 - 8
                ),
                14 if key == "instellingen" else 16
            )

        # LEDEN
        if self.active_tab == "leden":
            self.text(
                p,
                "●  OFFLINE",
                (1240, 436, 370, 51),
                24,
                "#ffb8bf"
            )

            self.text(
                p,
                "Nog geen verbonden leden",
                (1241, 499, 367, 49),
                21,
                "#fff0c0"
            )

            self.text(
                p,
                "De ledenlijst wordt zichtbaar zodra",
                (1240, 552, 369, 31),
                15,
                "#cfedda"
            )

            self.text(
                p,
                "de echte radioverbinding is gekoppeld.",
                (1240, 582, 369, 32),
                15,
                "#cfedda"
            )

            self.text(
                p,
                f"Geselecteerde groep: {self.group}",
                (1239, 652, 371, 38),
                16,
                "#96ffc4"
            )

        # CHAT
        elif self.active_tab == "chat":
            self.text(
                p,
                "KANAALCHAT",
                (1240, 445, 365, 49),
                25,
                "#fff0c0"
            )

            self.text(
                p,
                "Chat is nog niet verbonden.",
                (1240, 508, 365, 36),
                18,
                "#d6f5e1"
            )

            self.text(
                p,
                "Hier verschijnen later echte berichten.",
                (1240, 555, 365, 42),
                15,
                "#b8dccc"
            )

        # NIEUWS
        elif self.active_tab == "nieuws":
            self.text(
                p,
                "PRETTIGE KERSTDAGEN!",
                (1240, 450, 365, 55),
                23,
                "#f9d177"
            )

            self.text(
                p,
                "Welkom bij Christmas Radio",
                (1240, 510, 365, 40),
                17,
                "#d4f5dc"
            )

            self.text(
                p,
                self.news_notice,
                (1240, 554, 365, 30),
                15,
                "#c2e8d0"
            )

            self.text(
                p,
                self.news_detail,
                (1240, 584, 365, 30),
                15,
                "#c2e8d0"
            )

        # INSTELLINGEN
        elif self.active_tab == "instellingen":
            self.text(
                p,
                "Klik op een regel om die te wijzigen.",
                (1238, 425, 376, 43),
                17,
                "#e4d98c"
            )

            values = {
                "naam": f"Gebruiker: {self.nickname[:20]}",
                "groep": f"Groep: {self.group}",
                "volume": (
                    f"Volume: {self.volume}%  (nog geen audio)"
                ),
                "vox": (
                    f"VOX-gevoeligheid: {self.sensitivity}%"
                ),
            }

            for key, rect in self.SETTINGS_RECTS.items():
                x1, y1, x2, y2 = rect

                self.plate(
                    p,
                    (
                        x1,
                        y1,
                        x2 - x1,
                        y2 - y1
                    ),
                    "#174532",
                    "#092b21",
                    "#4d9670",
                    8
                )

                self.text(
                    p,
                    values[key],
                    (
                        x1 + 12,
                        y1 + 5,
                        x2 - x1 - 24,
                        y2 - y1 - 10
                    ),
                    16,
                    "#f3fff8"
                )

    def change_channel(self, delta):
        self.channel = (
            self.channel - 1 + delta
        ) % 40 + 1

        self.save()
        self.update()

    def choose_name(self):
        value, ok = QInputDialog.getText(
            self,
            "Christmas Radio",
            "Gebruikersnaam:",
            text=self.nickname
        )

        if ok and value.strip():
            self.nickname = value.strip()[:32]
            self.save()
            self.update()

    def choose_group(self):
        value, ok = QInputDialog.getItem(
            self,
            "Christmas Radio",
            "Kies een TG-groep:",
            list(self.GROUPS),
            self.GROUPS.index(self.group),
            False
        )

        if ok and value:
            self.group = value
            self.save()
            self.update()

    def choose_number(self, key, title):
        value, ok = QInputDialog.getInt(
            self,
            title,
            f"{title} (0-100):",
            getattr(self, key),
            0,
            100,
            1
        )

        if ok:
            setattr(self, key, value)
            self.save()
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        x, y = self.image_coords(
            event.position()
        )

        if not (
            0 <= x < self.ART_W and
            0 <= y < self.ART_H
        ):
            return

        # Vensterknoppen
        for key in ("close", "min", "max"):
            if self.contains(self.BUTTONS[key], x, y):
                if key == "close":
                    self.close()

                elif key == "min":
                    self.showMinimized()

                else:
                    if self.isMaximized():
                        self.showNormal()
                    else:
                        self.showMaximized()

                return

        # TALK
        if self.contains(self.BUTTONS["talk"], x, y):
            self.setFocus()
            self.ptt_pressed = True
            self.update()
            return

        # Kanaal omlaag
        if self.contains(
            self.BUTTONS["channel_down"],
            x,
            y
        ):
            self.change_channel(-1)
            return

        # Kanaal omhoog
        if self.contains(
            self.BUTTONS["channel_up"],
            x,
            y
        ):
            self.change_channel(1)
            return

        # Scan
        if self.contains(self.BUTTONS["scan"], x, y):
            self.news_notice = (
                "Kanaalscan is nog niet beschikbaar."
            )

            self.news_detail = (
                "Eerst koppelen we de echte kanalen."
            )

            self.active_tab = "nieuws"
            self.update()
            return

        # MUTE / VOX / ROGER
        for key in ("mute", "vox", "roger"):
            if self.contains(self.BUTTONS[key], x, y):
                if key == "mute":
                    self.muted = not self.muted

                elif key == "vox":
                    self.vox = not self.vox

                else:
                    self.roger = not self.roger

                self.save()
                self.update()
                return

        # Webcam
        if self.contains(self.BUTTONS["webcam"], x, y):
            self.news_notice = (
                "De webcam is nog niet aangesloten."
            )

            self.news_detail = (
                "Deze functie bouwen we later."
            )

            self.active_tab = "nieuws"
            self.update()
            return

        # TG-groep
        if self.contains(self.BUTTONS["group"], x, y):
            self.choose_group()
            return

        # Gebruikersnaam
        if self.contains(
            self.BUTTONS["nickname"],
            x,
            y
        ):
            self.choose_name()
            return

        # Volume
        if self.contains(
            self.BUTTONS["volume"],
            x,
            y
        ):
            self.choose_number(
                "volume",
                "Volume"
            )
            return

        # VOX-gevoeligheid
        if self.contains(
            self.BUTTONS["sensitivity"],
            x,
            y
        ):
            self.choose_number(
                "sensitivity",
                "VOX-gevoeligheid"
            )
            return

        # Tabbladen
        for key, rect in self.TAB_RECTS.items():
            if self.contains(rect, x, y):
                self.active_tab = key
                self.update()
                return

        # Instellingen in rechterpaneel
        if self.active_tab == "instellingen":
            for key, rect in self.SETTINGS_RECTS.items():
                if self.contains(rect, x, y):
                    if key == "naam":
                        self.choose_name()

                    elif key == "groep":
                        self.choose_group()

                    elif key == "volume":
                        self.choose_number(
                            "volume",
                            "Volume"
                        )

                    else:
                        self.choose_number(
                            "sensitivity",
                            "VOX-gevoeligheid"
                        )

                    return

        # Venster verslepen
        if y < 46 and x < 1430:
            self.drag_offset = (
                event.globalPosition().toPoint() -
                self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if (
            self.drag_offset is not None and
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            if not self.isMaximized():
                self.move(
                    event.globalPosition().toPoint() -
                    self.drag_offset
                )
            return

        x, y = self.image_coords(
            event.position()
        )

        clickable = any(
            self.contains(rect, x, y)
            for rect in self.BUTTONS.values()
        )

        clickable = clickable or any(
            self.contains(rect, x, y)
            for rect in self.TAB_RECTS.values()
        )

        if self.active_tab == "instellingen":
            clickable = clickable or any(
                self.contains(rect, x, y)
                for rect in self.SETTINGS_RECTS.values()
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
            self.drag_offset = None

            if self.ptt_pressed:
                self.ptt_pressed = False
                self.update()

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Space and
            not event.isAutoRepeat()
        ):
            self.ptt_pressed = True
            self.update()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Space and
            not event.isAutoRepeat()
        ):
            self.ptt_pressed = False
            self.update()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self.ptt_pressed = False
        self.update()
        super().focusOutEvent(event)

    def closeEvent(self, event):
        self.ptt_pressed = False
        self.save()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Christmas Radio")

    try:
        radio = ChristmasRadio()

    except FileNotFoundError as exc:
        QMessageBox.critical(
            None,
            "Christmas Radio",
            str(exc)
        )
        return 1

    radio.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
