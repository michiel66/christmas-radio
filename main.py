
"""Christmas Radio V3 - verbeterde uitlijning.

Vereist:
- PySide6
- christmas_radio.png (1672 x 941)

Dit is een visueel prototype.
De echte radioverbinding volgt later.
"""

import sys
from pathlib import Path

from PySide6.QtCore import (
    QDateTime,
    QPointF,
    QRectF,
    QSettings,
    Qt,
    QTimer,
)

from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
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

    W = 1672
    H = 941

    GROUPS = [
        "TG-103 Voorburg",
        "TG-108 Heerlen",
    ]

    HOTSPOTS = {
        "min": (1425, 0, 1498, 48),
        "max": (1499, 0, 1574, 48),
        "close": (1575, 0, 1672, 48),

        "down": (50, 499, 190, 564),
        "scan": (198, 499, 264, 564),
        "up": (275, 499, 415, 564),

        "volume": (75, 622, 195, 729),
        "sensitivity": (267, 622, 386, 729),

        "talk": (497, 606, 823, 715),

        "vox": (889, 498, 1020, 541),
        "mute": (1036, 498, 1163, 541),
        "webcam": (889, 553, 1020, 596),
        "roger": (1036, 553, 1163, 596),

        "group": (68, 867, 421, 924),
        "nickname": (494, 866, 727, 923),

        "leden": (1217, 332, 1321, 394),
        "chat": (1325, 332, 1417, 394),
        "nieuws": (1421, 332, 1513, 394),
        "instellingen": (1518, 332, 1661, 394),

        "setting_name": (1234, 483, 1618, 531),
        "setting_group": (1234, 545, 1618, 593),
        "setting_volume": (1234, 607, 1618, 655),
        "setting_vox": (1234, 669, 1618, 717),
    }

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint
        )

        self.setWindowTitle("Christmas Radio")
        self.setMouseTracking(True)
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self.setMinimumSize(780, 440)

        # Afbeelding zoeken, ook binnen Windows EXE
        base = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(__file__).resolve().parent
            )
        )

        self.art = QPixmap(
            str(base / "christmas_radio.png")
        )

        if self.art.isNull():
            raise FileNotFoundError(
                "christmas_radio.png staat niet "
                "bij main.py of in de EXE."
            )

        # Instellingen onthouden
        self.cfg = QSettings(
            "ChristmasRadio",
            "ChristmasRadio"
        )

        self.nickname = str(
            self.cfg.value("nickname", "Gast")
        )[:28]

        self.group = str(
            self.cfg.value(
                "group",
                self.GROUPS[0]
            )
        )

        if self.group not in self.GROUPS:
            self.group = self.GROUPS[0]

        self.channel = self._number(
            "channel", 14, 1, 40
        )

        self.volume = self._number(
            "volume", 65, 0, 100
        )

        self.sensitivity = self._number(
            "sensitivity", 40, 0, 100
        )

        self.muted = self.cfg.value(
            "muted",
            False,
            type=bool
        )

        self.vox = self.cfg.value(
            "vox",
            False,
            type=bool
        )

        self.roger = self.cfg.value(
            "roger",
            False,
            type=bool
        )

        self.tab = "leden"
        self.ptt_down = False
        self.drag_offset = None

        # Klok bijwerken
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update)
        self.clock.start(1000)

        # Venster passend maken
        screen = QApplication.primaryScreen()

        if screen:
            area = screen.availableGeometry()

            factor = min(
                1.0,
                (area.width() - 20) / self.W,
                (area.height() - 20) / self.H
            )

            self.resize(
                round(self.W * factor),
                round(self.H * factor)
            )

            self.move(
                area.center() -
                self.rect().center()
            )

        else:
            self.resize(1254, 706)

    def _number(
        self,
        name,
        default,
        smallest,
        largest
    ):
        try:
            value = int(
                self.cfg.value(name, default)
            )

            return max(
                smallest,
                min(largest, value)
            )

        except (TypeError, ValueError):
            return default

    def save(self):
        fields = (
            "nickname",
            "group",
            "channel",
            "volume",
            "sensitivity",
            "muted",
            "vox",
            "roger",
        )

        for key in fields:
            self.cfg.setValue(
                key,
                getattr(self, key)
            )

    def transform_info(self):
        scale = min(
            self.width() / self.W,
            self.height() / self.H
        )

        offset_x = (
            self.width() - self.W * scale
        ) / 2

        offset_y = (
            self.height() - self.H * scale
        ) / 2

        return scale, offset_x, offset_y

    def artwork_pos(self, pos):
        scale, ox, oy = self.transform_info()

        return (
            (pos.x() - ox) / scale,
            (pos.y() - oy) / scale
        )

    @staticmethod
    def in_box(x, y, box):
        x1, y1, x2, y2 = box

        return (
            x1 <= x <= x2 and
            y1 <= y <= y2
        )

    @staticmethod
    def fill(
        painter,
        x,
        y,
        w,
        h,
        color="#06120d"
    ):
        painter.fillRect(
            QRectF(x, y, w, h),
            QColor(color)
        )

    @staticmethod
    def gradient(
        painter,
        x,
        y,
        w,
        h,
        top,
        bottom,
        edge=None,
        radius=8
    ):
        grad = QLinearGradient(
            x,
            y,
            x,
            y + h
        )

        grad.setColorAt(
            0,
            QColor(top)
        )

        grad.setColorAt(
            1,
            QColor(bottom)
        )

        painter.setBrush(grad)

        if edge:
            painter.setPen(
                QPen(QColor(edge), 2)
            )
        else:
            painter.setPen(
                Qt.PenStyle.NoPen
            )

        painter.drawRoundedRect(
            QRectF(x, y, w, h),
            radius,
            radius
        )

    @staticmethod
    def label(
        painter,
        value,
        x,
        y,
        w,
        h,
        size=19,
        color="#ffffff",
        weight=True,
        align=Qt.AlignmentFlag.AlignCenter
    ):
        font = QFont(
            "Segoe UI",
            size
        )

        font.setBold(weight)

        painter.setFont(font)
        painter.setPen(
            QColor(color)
        )

        painter.drawText(
            QRectF(x, y, w, h),
            align,
            str(value)
        )

    def paintEvent(self, event):
        p = QPainter(self)

        p.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        p.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )

        p.fillRect(
            self.rect(),
            QColor("#030b08")
        )

        scale, ox, oy = self.transform_info()

        p.translate(ox, oy)
        p.scale(scale, scale)

        # Kerstafbeelding
        p.drawPixmap(
            QRectF(0, 0, self.W, self.H),
            self.art,
            QRectF(self.art.rect())
        )

        # Dynamische radiopanelen
        self.draw_display(p)
        self.draw_sidebar(p)
        self.draw_footer(p)

        # Statusindicator
        self.gradient(
            p,
            575, 770, 171, 58,
            "#302025",
            "#111518",
            "#db897e",
            10
        )

        self.label(
            p,
            "● OFFLINE",
            579, 777, 162, 42,
            21,
            "#ffb0ad"
        )

        # TALK knop visuele test
        if self.ptt_down:
            p.setBrush(
                Qt.BrushStyle.NoBrush
            )

            p.setPen(
                QPen(
                    QColor("#ff4545"),
                    6
                )
            )

            p.drawRoundedRect(
                QRectF(
                    493, 603, 330, 116
                ),
                15,
                15
            )

        # Knopindicaties
        states = (
            (self.vox, "vox"),
            (self.muted, "mute"),
            (self.roger, "roger"),
        )

        for enabled, key in states:
            if enabled:
                x1, y1, x2, y2 = self.HOTSPOTS[key]

                p.setBrush(
                    Qt.BrushStyle.NoBrush
                )

                p.setPen(
                    QPen(
                        QColor("#ffdf75"),
                        3
                    )
                )

                p.drawRoundedRect(
                    QRectF(
                        x1,
                        y1,
                        x2 - x1,
                        y2 - y1
                    ),
                    8,
                    8
                )

        p.end()

    def draw_display(self, p):
        # Compleet display opnieuw tekenen
        self.gradient(
            p,
            39, 357, 1137, 121,
            "#07130f",
            "#020907",
            "#d5a94a",
            12
        )

        # Scheidingslijnen
        for x in (223, 433, 791, 989):
            p.setPen(
                QPen(
                    QColor("#9e8b4f"),
                    2
                )
            )

            p.drawLine(
                x, 362,
                x, 473
            )

        # Kanaal
        self.label(
            p,
            "CHANNEL",
            46, 368, 173, 26,
            18,
            "#f5f7f1"
        )

        self.label(
            p,
            str(self.channel),
            48, 396, 170, 74,
            43,
            "#75ff92"
        )

        # Tijd
        self.label(
            p,
            "TIME",
            228, 368, 200, 26,
            18
        )

        current_time = (
            QDateTime.currentDateTime()
            .toString("HH:mm")
        )

        self.label(
            p,
            current_time,
            229, 396, 199, 74,
            36,
            "#80ffaf"
        )

        # Signaalmeter
        self.label(
            p,
            "SIGNAL / MODULATION",
            440, 368, 341, 26,
            18
        )

        for i in range(11):
            self.gradient(
                p,
                463 + i * 27,
                409,
                23,
                18,
                "#214634",
                "#183227",
                "#395847",
                3
            )

        self.label(
            p,
            "S   1   3   5   7   9   +30",
            459, 440, 313, 27,
            16
        )

        # RX / TX / BUSY
        indicators = (
            (838, False, "#3dff69"),
            (891, self.ptt_down, "#ff4b54"),
            (942, False, "#ffc358"),
        )

        for cx, active, color in indicators:
            p.setPen(
                QPen(
                    QColor("#536e5e"),
                    1
                )
            )

            p.setBrush(
                QColor(
                    color if active else "#30463c"
                )
            )

            p.drawEllipse(
                QPointF(cx, 416),
                10,
                10
            )

        self.label(
            p,
            "RX",
            814, 440, 48, 27,
            17
        )

        self.label(
            p,
            "TX",
            867, 440, 48, 27,
            17
        )

        self.label(
            p,
            "BUSY",
            913, 440, 65, 27,
            16
        )

        # Weer
        self.label(
            p,
            "NEDERLAND",
            996, 368, 172, 26,
            18
        )

        self.label(
            p,
            "-- °C",
            1000, 393, 169, 48,
            30,
            "#90ffc2"
        )

        self.label(
            p,
            "GEEN WEERDATA",
            1000, 439, 169, 27,
            12,
            "#e3ece8"
        )

    def draw_sidebar(self, p):
        # Compleet rechterpaneel
        self.gradient(
            p,
            1207, 332, 459, 505,
            "#103627",
            "#07150f",
            "#c59c4d",
            13
        )

        titles = {
            "leden": "LEDEN (0)",
            "chat": "CHAT",
            "nieuws": "NIEUWS",
            "instellingen": "INSTELLINGEN",
        }

        # Tabbladen
        for key in (
            "leden",
            "chat",
            "nieuws",
            "instellingen"
        ):
            x1, y1, x2, y2 = self.HOTSPOTS[key]

            active = self.tab == key

            self.gradient(
                p,
                x1 + 2,
                y1 + 5,
                x2 - x1 - 5,
                y2 - y1 - 10,
                "#bf2130" if active else "#1c503c",
                "#770b19" if active else "#09271c",
                "#ffe19a" if active else "#538566",
                8
            )

            self.label(
                p,
                titles[key],
                x1 + 3,
                y1 + 6,
                x2 - x1 - 6,
                y2 - y1 - 12,
                13 if key == "instellingen" else 15
            )

        self.gradient(
            p,
            1217, 404, 440, 344,
            "#0a251d",
            "#04100c",
            "#21513b",
            9
        )

        if self.tab == "leden":
            self.label(
                p,
                "● OFFLINE",
                1230, 454, 391, 45,
                23,
                "#f6aeaa"
            )

            self.label(
                p,
                "Nog geen leden verbonden",
                1228, 513, 395, 45,
                21,
                "#f4e6be"
            )

            self.label(
                p,
                "De echte ledenlijst verschijnt wanneer",
                1230, 563, 390, 33,
                15,
                "#bde5cd"
            )

            self.label(
                p,
                "we de spraakverbinding koppelen.",
                1230, 592, 390, 33,
                15,
                "#bde5cd"
            )

            self.label(
                p,
                f"Gekozen: {self.group}",
                1230, 670, 390, 42,
                17,
                "#8bf2af"
            )

        elif self.tab == "chat":
            self.label(
                p,
                "KANAALCHAT",
                1230, 457, 390, 55,
                24,
                "#f5e3b2"
            )

            self.label(
                p,
                "De chat is nog niet aangesloten.",
                1230, 535, 390, 43,
                18
            )

        elif self.tab == "nieuws":
            self.label(
                p,
                "PRETTIGE KERSTDAGEN!",
                1230, 457, 390, 55,
                24,
                "#f4d17d"
            )

            self.label(
                p,
                "Welkom bij Christmas Radio",
                1230, 535, 390, 43,
                18
            )

        else:
            self.label(
                p,
                "Klik op een regel om te wijzigen",
                1228, 420, 390, 44,
                17,
                "#f8e5af"
            )

            values = [
                (
                    "setting_name",
                    f"Gebruiker: {self.nickname[:19]}"
                ),
                (
                    "setting_group",
                    self.group
                ),
                (
                    "setting_volume",
                    f"Volume: {self.volume}% (nog geen audio)"
                ),
                (
                    "setting_vox",
                    f"VOX-gevoeligheid: {self.sensitivity}%"
                ),
            ]

            for key, value in values:
                x1, y1, x2, y2 = self.HOTSPOTS[key]

                self.gradient(
                    p,
                    x1, y1,
                    x2 - x1,
                    y2 - y1,
                    "#245440",
                    "#0b291e",
                    "#5c956f",
                    7
                )

                self.label(
                    p,
                    value,
                    x1 + 5,
                    y1 + 2,
                    x2 - x1 - 10,
                    y2 - y1 - 4,
                    16
                )

        # Kersttekst onderaan
        p.setPen(
            QPen(
                QColor("#ba934d"),
                2
            )
        )

        p.drawLine(
            1225, 768,
            1650, 768
        )

        self.label(
            p,
            "❄  CHRISTMAS RADIO  ❄",
            1225, 779, 428, 40,
            19,
            "#efd18b"
        )

        # Kanaalchat titel
        self.fill(
            p,
            1263, 277, 342, 44,
            "#07140e"
        )

        self.label(
            p,
            f"KANAALCHAT  •  CH {self.channel}",
            1263, 278, 342, 43,
            22
        )

    def draw_footer(self, p):
        # Complete onderbalk
        self.gradient(
            p,
            5, 859, 1662, 73,
            "#0b2c1e",
            "#04100e",
            "#af8440",
            10
        )

        # Scheidingslijnen
        for x in (
            435,
            730,
            1190,
            1300,
            1516
        ):
            p.setPen(
                QPen(
                    QColor("#7c9669"),
                    1
                )
            )

            p.drawLine(
                x, 876,
                x, 916
            )

        # TG
        self.label(
            p,
            f"Gekozen: {self.group}",
            20, 871, 405, 49,
            20,
            "#b9fff2"
        )

        # Gebruikersnaam
        nick = self.nickname

        if len(nick) >= 19:
            nick = nick[:18] + "…"

        self.label(
            p,
            f"Gebruiker: {nick}",
            441, 872, 281, 48,
            18
        )

        # Kerstgroet
        self.label(
            p,
            "❄  Prettige Kerstdagen  ❄",
            735, 870, 447, 51,
            24,
            "#f5d48f"
        )

        # Ping nog niet beschikbaar
        self.label(
            p,
            "-- ms",
            1192, 871, 105, 49,
            18,
            "#cdd9d1"
        )

        # Volume
        self.label(
            p,
            "VOLUME",
            1302, 872, 211, 22,
            13,
            "#d3e8d6"
        )

        count = round(
            self.volume / 10
        )

        for i in range(10):
            p.setPen(
                Qt.PenStyle.NoPen
            )

            p.setBrush(
                QColor(
                    "#43c3e0" if i < count
                    else "#34453f"
                )
            )

            p.drawRect(
                QRectF(
                    1331 + i * 16,
                    900,
                    12,
                    10
                )
            )

        # Tijd en datum
        now = QDateTime.currentDateTime()

        self.label(
            p,
            now.toString("HH:mm"),
            1521, 863, 135, 32,
            19
        )

        self.label(
            p,
            now.toString("dd-MM-yyyy"),
            1521, 894, 135, 30,
            13
        )

    def change_channel(self, delta):
        self.channel = (
            self.channel - 1 + delta
        ) % 40 + 1

        self.save()
        self.update()

    def change_name(self):
        value, ok = QInputDialog.getText(
            self,
            "Christmas Radio",
            "Gebruikersnaam:",
            text=self.nickname
        )

        if ok and value.strip():
            self.nickname = value.strip()[:28]

            self.save()
            self.update()

    def change_group(self):
        value, ok = QInputDialog.getItem(
            self,
            "Christmas Radio",
            "Kies je TG-groep:",
            self.GROUPS,
            self.GROUPS.index(self.group),
            False
        )

        if ok:
            self.group = value

            self.save()
            self.update()

    def change_number(self, key, name):
        value, ok = QInputDialog.getInt(
            self,
            "Christmas Radio",
            name + " (0-100):",
            getattr(self, key),
            0,
            100
        )

        if ok:
            setattr(self, key, value)

            self.save()
            self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        x, y = self.artwork_pos(
            event.position()
        )

        # Vensterknoppen
        for key in (
            "close",
            "min",
            "max"
        ):
            if self.in_box(
                x, y,
                self.HOTSPOTS[key]
            ):
                if key == "close":
                    self.close()

                elif key == "min":
                    self.showMinimized()

                elif self.isMaximized():
                    self.showNormal()

                else:
                    self.showMaximized()

                return

        # TALK
        if self.in_box(
            x, y,
            self.HOTSPOTS["talk"]
        ):
            self.setFocus()
            self.ptt_down = True
            self.update()
            return

        # Kanaal omlaag
        if self.in_box(
            x, y,
            self.HOTSPOTS["down"]
        ):
            self.change_channel(-1)
            return

        # Kanaal omhoog
        if self.in_box(
            x, y,
            self.HOTSPOTS["up"]
        ):
            self.change_channel(1)
            return

        # Scan
        if self.in_box(
            x, y,
            self.HOTSPOTS["scan"]
        ):
            self.tab = "nieuws"
            self.update()
            return

        # MUTE, VOX en ROGER
        for key in (
            "mute",
            "vox",
            "roger"
        ):
            if self.in_box(
                x, y,
                self.HOTSPOTS[key]
            ):
                attr = (
                    "muted"
                    if key == "mute"
                    else key
                )

                setattr(
                    self,
                    attr,
                    not getattr(self, attr)
                )

                self.save()
                self.update()
                return

        # Webcam
        if self.in_box(
            x, y,
            self.HOTSPOTS["webcam"]
        ):
            self.tab = "nieuws"
            self.update()
            return

        # TG-groep
        if self.in_box(
            x, y,
            self.HOTSPOTS["group"]
        ):
            self.change_group()
            return

        # Naam
        if self.in_box(
            x, y,
            self.HOTSPOTS["nickname"]
        ):
            self.change_name()
            return

        # Volume
        if self.in_box(
            x, y,
            self.HOTSPOTS["volume"]
        ):
            self.change_number(
                "volume",
                "Volume"
            )
            return

        # VOX-gevoeligheid
        if self.in_box(
            x, y,
            self.HOTSPOTS["sensitivity"]
        ):
            self.change_number(
                "sensitivity",
                "VOX-gevoeligheid"
            )
            return

        # Tabbladen
        for key in (
            "leden",
            "chat",
            "nieuws",
            "instellingen"
        ):
            if self.in_box(
                x, y,
                self.HOTSPOTS[key]
            ):
                self.tab = key
                self.update()
                return

        # Instellingen
        if self.tab == "instellingen":
            mapping = (
                ("setting_name", "name"),
                ("setting_group", "group"),
                ("setting_volume", "volume"),
                ("setting_vox", "sensitivity"),
            )

            for key, attr in mapping:
                if self.in_box(
                    x, y,
                    self.HOTSPOTS[key]
                ):
                    if attr == "name":
                        self.change_name()

                    elif attr == "group":
                        self.change_group()

                    else:
                        title = (
                            "Volume"
                            if attr == "volume"
                            else "VOX-gevoeligheid"
                        )

                        self.change_number(
                            attr,
                            title
                        )

                    return

        # Venster verslepen
        if 0 <= x < 1420 and 0 <= y < 48:
            self.drag_offset = (
                event.globalPosition().toPoint() -
                self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if (
            self.drag_offset is not None
            and event.buttons()
            & Qt.MouseButton.LeftButton
        ):
            if not self.isMaximized():
                self.move(
                    event.globalPosition().toPoint() -
                    self.drag_offset
                )

            return

        x, y = self.artwork_pos(
            event.position()
        )

        keys = [
            key
            for key in self.HOTSPOTS
            if not key.startswith("setting_")
        ]

        if self.tab == "instellingen":
            keys.extend(
                key
                for key in self.HOTSPOTS
                if key.startswith("setting_")
            )

        active = any(
            self.in_box(
                x, y,
                self.HOTSPOTS[key]
            )
            for key in keys
        )

        if active:
            cursor = Qt.CursorShape.PointingHandCursor
        else:
            cursor = Qt.CursorShape.ArrowCursor

        self.setCursor(cursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = None
            self.ptt_down = False
            self.update()

    def keyPressEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
        ):
            self.ptt_down = True
            self.update()

        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if (
            event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
        ):
            self.ptt_down = False
            self.update()

        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self.ptt_down = False
        self.update()

        super().focusOutEvent(event)

    def closeEvent(self, event):
        self.ptt_down = False
        self.save()

        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(
        "Christmas Radio"
    )

    try:
        window = ChristmasRadio()

    except FileNotFoundError as exc:
        QMessageBox.critical(
            None,
            "Christmas Radio",
            str(exc)
        )

        return 1

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
