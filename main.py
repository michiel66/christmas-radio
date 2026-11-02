
"""Christmas Radio V4 - gecentreerde OFFLINE-indicator en TALK-knop.

Vereist: PySide6 en christmas_radio.png (1672 x 941).
Dit is een visueel prototype: nog geen echte spraakverbinding.
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

    W, H = 1672, 941

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

        "talk": (483, 585, 871, 731),

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
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint,
        )

        self.setWindowTitle("Christmas Radio")
        self.setMouseTracking(True)
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )
        self.setMinimumSize(780, 440)

        # Afbeelding laden, ook binnen de Windows EXE.
        base = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(__file__).resolve().parent,
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

        # Instellingen onthouden.
        self.cfg = QSettings(
            "ChristmasRadio",
            "ChristmasRadio",
        )

        self.nickname = str(
            self.cfg.value("nickname", "Gast")
        )[:28]

        self.group = str(
            self.cfg.value(
                "group",
                self.GROUPS[0],
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
            "muted", False, type=bool
        )

        self.vox = self.cfg.value(
            "vox", False, type=bool
        )

        self.roger = self.cfg.value(
            "roger", False, type=bool
        )

        self.tab = "leden"
        self.ptt_down = False
        self.drag_offset = None

        # Klok automatisch bijwerken.
        self.clock = QTimer(self)
        self.clock.timeout.connect(
            self.update
        )
        self.clock.start(1000)

        # Venster automatisch passend op scherm.
        screen = QApplication.primaryScreen()

        if screen:
            area = screen.availableGeometry()

            factor = min(
                1.0,
                (area.width() - 20) / self.W,
                (area.height() - 20) / self.H,
            )

            self.resize(
                round(self.W * factor),
                round(self.H * factor),
            )

            self.move(
                area.center()
                - self.rect().center()
            )
        else:
            self.resize(1254, 706)

    def _number(
        self,
        name,
        default,
        smallest,
        largest,
    ):
        try:
            value = int(
                self.cfg.value(name, default)
            )

            return max(
                smallest,
                min(largest, value),
            )

        except (TypeError, ValueError):
            return default

    def save(self):
        for key in (
            "nickname",
            "group",
            "channel",
            "volume",
            "sensitivity",
            "muted",
            "vox",
            "roger",
        ):
            self.cfg.setValue(
                key,
                getattr(self, key),
            )

    def transform_info(self):
        scale = min(
            self.width() / self.W,
            self.height() / self.H,
        )

        offset_x = (
            self.width() - self.W * scale
        ) / 2

        offset_y = (
            self.height() - self.H * scale
        ) / 2

        return (
            scale,
            offset_x,
            offset_y,
        )

    def artwork_pos(self, pos):
        scale, ox, oy = self.transform_info()

        return (
            (pos.x() - ox) / scale,
            (pos.y() - oy) / scale,
        )

    @staticmethod
    def in_box(x, y, box):
        x1, y1, x2, y2 = box

        return (
            x1 <= x <= x2
            and y1 <= y <= y2
        )

    @staticmethod
    def fill(
        painter,
        x,
        y,
        w,
        h,
        color="#06120d",
    ):
        painter.fillRect(
            QRectF(x, y, w, h),
            QColor(color),
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
        radius=8,
    ):
        gradient = QLinearGradient(
            x,
            y,
            x,
            y + h,
        )

        gradient.setColorAt(
            0,
            QColor(top),
        )

        gradient.setColorAt(
            1,
            QColor(bottom),
        )

        painter.setBrush(gradient)

        if edge:
            painter.setPen(
                QPen(
                    QColor(edge),
                    2,
                )
            )
        else:
            painter.setPen(
                Qt.PenStyle.NoPen
            )

        painter.drawRoundedRect(
            QRectF(x, y, w, h),
            radius,
            radius,
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
        align=Qt.AlignmentFlag.AlignCenter,
    ):
        font = QFont(
            "Segoe UI",
            size,
        )

        font.setBold(weight)

        painter.setFont(font)
        painter.setPen(
            QColor(color)
        )

        painter.drawText(
            QRectF(x, y, w, h),
            align,
            str(value),
        )

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform
        )

        painter.fillRect(
            self.rect(),
            QColor("#030b08"),
        )

        scale, ox, oy = self.transform_info()

        painter.translate(ox, oy)
        painter.scale(scale, scale)

        # Originele kerstafbeelding.
        painter.drawPixmap(
            QRectF(0, 0, self.W, self.H),
            self.art,
            QRectF(self.art.rect()),
        )

        # Volledige dynamische panelen.
        self.draw_display(painter)
        self.draw_sidebar(painter)
        self.draw_footer(painter)

        # OFFLINE correct in statusvak.
        self.draw_status(painter)

        # TALK alleen binnenin rood bij indrukken.
        if self.ptt_down:
            self.draw_pressed_talk(painter)

        # Kleine knoppen markeren bij inschakelen.
        for enabled, key in (
            (self.vox, "vox"),
            (self.muted, "mute"),
            (self.roger, "roger"),
        ):
            if enabled:
                x1, y1, x2, y2 = self.HOTSPOTS[key]

                painter.setBrush(
                    Qt.BrushStyle.NoBrush
                )

                painter.setPen(
                    QPen(
                        QColor("#ffdf75"),
                        3,
                    )
                )

                painter.drawRoundedRect(
                    QRectF(
                        x1,
                        y1,
                        x2 - x1,
                        y2 - y1,
                    ),
                    8,
                    8,
                )

        painter.end()

    def draw_status(self, painter):
        # OFFLINE binnen het bestaande statusvak.
        self.gradient(
            painter,
            582, 782, 171, 53,
            "#35191f",
            "#100d11",
            "#eb6671",
            13,
        )

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.setBrush(
            QColor("#fa5662")
        )

        painter.drawEllipse(
            QPointF(612, 808),
            8,
            8,
        )

        self.label(
            painter,
            "OFFLINE",
            630, 789, 113, 39,
            20,
            "#fff4f3",
        )

    def draw_pressed_talk(self, painter):
        # Alleen binnenkant van de TALK-knop.
        # Groene omlijsting blijft zichtbaar.
        self.gradient(
            painter,
            539, 631, 285, 76,
            "#e7525b",
            "#720e20",
            "#ffcc91",
            12,
        )

        self.label(
            painter,
            "TALK",
            546, 636, 271, 65,
            38,
            "#fff6df",
        )

    def draw_display(self, painter):
        # Compleet radiodisplay opnieuw tekenen.
        self.gradient(
            painter,
            39, 357, 1137, 121,
            "#07130f",
            "#020907",
            "#d5a94a",
            12,
        )

        # Scheidingslijnen.
        for x in (
            223,
            433,
            791,
            989,
        ):
            painter.setPen(
                QPen(
                    QColor("#9e8b4f"),
                    2,
                )
            )

            painter.drawLine(
                x, 362,
                x, 473,
            )

        # Kanaal.
        self.label(
            painter,
            "CHANNEL",
            46, 368, 173, 26,
            18,
            "#f5f7f1",
        )

        self.label(
            painter,
            str(self.channel),
            48, 396, 170, 74,
            43,
            "#75ff92",
        )

        # Tijd.
        self.label(
            painter,
            "TIME",
            228, 368, 200, 26,
            18,
        )

        self.label(
            painter,
            QDateTime.currentDateTime().toString(
                "HH:mm"
            ),
            229, 396, 199, 74,
            36,
            "#80ffaf",
        )

        # Signaalmeter.
        self.label(
            painter,
            "SIGNAL / MODULATION",
            440, 368, 341, 26,
            18,
        )

        for i in range(11):
            self.gradient(
                painter,
                463 + i * 27,
                409,
                23,
                18,
                "#214634",
                "#183227",
                "#395847",
                3,
            )

        self.label(
            painter,
            "S   1   3   5   7   9   +30",
            459, 440, 313, 27,
            16,
        )

        # RX / TX / BUSY.
        indicators = (
            (838, False, "#3dff69"),
            (891, self.ptt_down, "#ff4b54"),
            (942, False, "#ffc358"),
        )

        for cx, enabled, color in indicators:
            painter.setPen(
                QPen(
                    QColor("#536e5e"),
                    1,
                )
            )

            painter.setBrush(
                QColor(
                    color if enabled
                    else "#30463c"
                )
            )

            painter.drawEllipse(
                QPointF(cx, 416),
                10,
                10,
            )

        self.label(
            painter,
            "RX",
            814, 440, 48, 27,
            17,
        )

        self.label(
            painter,
            "TX",
            867, 440, 48, 27,
            17,
        )

        self.label(
            painter,
            "BUSY",
            913, 440, 65, 27,
            16,
        )

        # Weergegevens nog niet aangesloten.
        self.label(
            painter,
            "NEDERLAND",
            996, 368, 172, 26,
            18,
        )

        self.label(
            painter,
            "-- °C",
            1000, 393, 169, 48,
            30,
            "#90ffc2",
        )

        self.label(
            painter,
            "GEEN WEERDATA",
            1000, 439, 169, 27,
            12,
            "#e3ece8",
        )

    def draw_sidebar(self, painter):
        # Rechterpaneel opnieuw tekenen.
        self.gradient(
            painter,
            1207, 332, 459, 505,
            "#103627",
            "#07150f",
            "#c59c4d",
            13,
        )

        titles = {
            "leden": "LEDEN (0)",
            "chat": "CHAT",
            "nieuws": "NIEUWS",
            "instellingen": "INSTELLINGEN",
        }

        # Tabbladen.
        for key in (
            "leden",
            "chat",
            "nieuws",
            "instellingen",
        ):
            x1, y1, x2, y2 = self.HOTSPOTS[key]

            active = self.tab == key

            self.gradient(
                painter,
                x1 + 2,
                y1 + 5,
                x2 - x1 - 5,
                y2 - y1 - 10,
                "#bf2130" if active else "#1c503c",
                "#770b19" if active else "#09271c",
                "#ffe19a" if active else "#538566",
                8,
            )

            self.label(
                painter,
                titles[key],
                x1 + 3,
                y1 + 6,
                x2 - x1 - 6,
                y2 - y1 - 12,
                13 if key == "instellingen" else 15,
            )

        self.gradient(
            painter,
            1217, 404, 440, 344,
            "#0a251d",
            "#04100c",
            "#21513b",
            9,
        )

        if self.tab == "leden":
            self.label(
                painter,
                "● OFFLINE",
                1230, 454, 391, 45,
                23,
                "#f6aeaa",
            )

            self.label(
                painter,
                "Nog geen leden verbonden",
                1228, 513, 395, 45,
                21,
                "#f4e6be",
            )

            self.label(
                painter,
                "De echte ledenlijst verschijnt wanneer",
                1230, 563, 390, 33,
                15,
                "#bde5cd",
            )

            self.label(
                painter,
                "we de spraakverbinding koppelen.",
                1230, 592, 390, 33,
                15,
                "#bde5cd",
            )

            self.label(
                painter,
                f"Gekozen: {self.group}",
                1230, 670, 390, 42,
                17,
                "#8bf2af",
            )

        elif self.tab == "chat":
            self.label(
                painter,
                "KANAALCHAT",
                1230, 457, 390, 55,
                24,
                "#f5e3b2",
            )

            self.label(
                painter,
                "De chat is nog niet aangesloten.",
                1230, 535, 390, 43,
                18,
            )

        elif self.tab == "nieuws":
            self.label(
                painter,
                "PRETTIGE KERSTDAGEN!",
                1230, 457, 390, 55,
                24,
                "#f4d17d",
            )

            self.label(
                painter,
                "Welkom bij Christmas Radio",
                1230, 535, 390, 43,
                18,
            )

        else:
            self.label(
                painter,
                "Klik op een regel om te wijzigen",
                1228, 420, 390, 44,
                17,
                "#f8e5af",
            )

            values = [
                (
                    "setting_name",
                    f"Gebruiker: {self.nickname[:19]}",
                ),
                (
                    "setting_group",
                    self.group,
                ),
                (
                    "setting_volume",
                    f"Volume: {self.volume}% (nog geen audio)",
                ),
                (
                    "setting_vox",
                    f"VOX-gevoeligheid: {self.sensitivity}%",
                ),
            ]

            for key, value in values:
                x1, y1, x2, y2 = self.HOTSPOTS[key]

                self.gradient(
                    painter,
                    x1,
                    y1,
                    x2 - x1,
                    y2 - y1,
                    "#245440",
                    "#0b291e",
                    "#5c956f",
                    7,
                )

                self.label(
                    painter,
                    value,
                    x1 + 5,
                    y1 + 2,
                    x2 - x1 - 10,
                    y2 - y1 - 4,
                    16,
                )

        # Onderkant rechterpaneel.
        painter.setPen(
            QPen(
                QColor("#ba934d"),
                2,
            )
        )

        painter.drawLine(
            1225, 768,
            1650, 768,
        )

        self.label(
            painter,
            "❄  CHRISTMAS RADIO  ❄",
            1225, 779, 428, 40,
            19,
            "#efd18b",
        )

        # Kanaalchat titel.
        self.fill(
            painter,
            1263, 277, 342, 44,
            "#07140e",
        )

        self.label(
            painter,
            f"KANAALCHAT  •  CH {self.channel}",
            1263, 278, 342, 43,
            22,
        )

    def draw_footer(self, painter):
        # Complete onderbalk.
        self.gradient(
            painter,
            5, 859, 1662, 73,
            "#0b2c1e",
            "#04100e",
            "#af8440",
            10,
        )

        for x in (
            435,
            730,
            1190,
            1300,
            1516,
        ):
            painter.setPen(
                QPen(
                    QColor("#7c9669"),
                    1,
                )
            )

            painter.drawLine(
                x, 876,
                x, 916,
            )

        # Geselecteerde groep.
        self.label(
            painter,
            f"Gekozen: {self.group}",
            20, 871, 405, 49,
            20,
            "#b9fff2",
        )

        # Gebruiker.
        nick = (
            self.nickname
            if len(self.nickname) < 19
            else self.nickname[:18] + "…"
        )

        self.label(
            painter,
            f"Gebruiker: {nick}",
            441, 872, 281, 48,
            18,
        )

        # Kerstgroet.
        self.label(
            painter,
            "❄  Prettige Kerstdagen  ❄",
            735, 870, 447, 51,
            24,
            "#f5d48f",
        )

        # Ping nog niet beschikbaar.
        self.label(
            painter,
            "-- ms",
            1192, 871, 105, 49,
            18,
            "#cdd9d1",
        )

        # Volumeweergave.
        self.label(
            painter,
            "VOLUME",
            1302, 872, 211, 22,
            13,
            "#d3e8d6",
        )

        count = round(
            self.volume / 10
        )

        for i in range(10):
            painter.setPen(
                Qt.PenStyle.NoPen
            )

            painter.setBrush(
                QColor(
                    "#43c3e0"
                    if i < count
                    else "#34453f"
                )
            )

            painter.drawRect(
                QRectF(
                    1331 + i * 16,
                    900,
                    12,
                    10,
                )
            )

        # Tijd en datum.
        now = QDateTime.currentDateTime()

        self.label(
            painter,
            now.toString("HH:mm"),
            1521, 863, 135, 32,
            19,
        )

        self.label(
            painter,
            now.toString("dd-MM-yyyy"),
            1521, 894, 135, 30,
            13,
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
            text=self.nickname,
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
            False,
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
            100,
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

        # Vensterknoppen.
        for key in (
            "close",
            "min",
            "max",
        ):
            if self.in_box(
                x,
                y,
                self.HOTSPOTS[key],
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

        # TALK.
        if self.in_box(
            x,
            y,
            self.HOTSPOTS["talk"],
        ):
            self.setFocus()
            self.ptt_down = True
            self.update()
            return

        # Kanaal omlaag.
        if self.in_box(
            x, y,
            self.HOTSPOTS["down"],
        ):
            self.change_channel(-1)
            return

        # Kanaal omhoog.
        if self.in_box(
            x, y,
            self.HOTSPOTS["up"],
        ):
            self.change_channel(1)
            return

        # Scan.
        if self.in_box(
            x, y,
            self.HOTSPOTS["scan"],
        ):
            self.tab = "nieuws"
            self.update()
            return

        # MUTE / VOX / ROGER.
        for key in (
            "mute",
            "vox",
            "roger",
        ):
            if self.in_box(
                x, y,
                self.HOTSPOTS[key],
            ):
                attr = (
                    "muted"
                    if key == "mute"
                    else key
                )

                setattr(
                    self,
                    attr,
                    not getattr(self, attr),
                )

                self.save()
                self.update()
                return

        # Webcam.
        if self.in_box(
            x, y,
            self.HOTSPOTS["webcam"],
        ):
            self.tab = "nieuws"
            self.update()
            return

        # Groep kiezen.
        if self.in_box(
            x, y,
            self.HOTSPOTS["group"],
        ):
            self.change_group()
            return

        # Naam wijzigen.
        if self.in_box(
            x, y,
            self.HOTSPOTS["nickname"],
        ):
            self.change_name()
            return

        # Volume.
        if self.in_box(
            x, y,
            self.HOTSPOTS["volume"],
        ):
            self.change_number(
                "volume",
                "Volume",
            )
            return

        # VOX-gevoeligheid.
        if self.in_box(
            x, y,
            self.HOTSPOTS["sensitivity"],
        ):
            self.change_number(
                "sensitivity",
                "VOX-gevoeligheid",
            )
            return

        # Tabbladen.
        for key in (
            "leden",
            "chat",
            "nieuws",
            "instellingen",
        ):
            if self.in_box(
                x, y,
                self.HOTSPOTS[key],
            ):
                self.tab = key
                self.update()
                return

        # Instellingen rechts.
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
                    self.HOTSPOTS[key],
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
                            title,
                        )

                    return

        # Venster slepen via bovenste balk.
        if 0 <= x < 1420 and 0 <= y < 48:
            self.drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if (
            self.drag_offset is not None
            and event.buttons()
            & Qt.MouseButton.LeftButton
        ):
            if not self.isMaximized():
                self.move(
                    event.globalPosition().toPoint()
                    - self.drag_offset
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
                x,
                y,
                self.HOTSPOTS[key],
            )
            for key in keys
        )

        if active:
            self.setCursor(
                Qt.CursorShape.PointingHandCursor
            )
        else:
            self.setCursor(
                Qt.CursorShape.ArrowCursor
            )

    def mouseReleaseEvent(self, event):
        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
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
            str(exc),
        )

        return 1

    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
