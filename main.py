"""
Christmas Radio - strakke vaste layout versie
Deze versie houdt de afbeelding 1-op-1 aan zodat alles netjes uitgelijnd blijft.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QDateTime, QSettings, QTimer, QPoint
from PySide6.QtGui import QPainter, QPixmap, QColor, QFont, QPen
from PySide6.QtWidgets import QApplication, QWidget, QInputDialog, QMessageBox


class ChristmasRadio(QWidget):
    WIDTH = 1672
    HEIGHT = 941

    SERVERS = [
        "TG-103 Voorburg",
        "TG-108 Heerlen",
    ]

    HIT = {
        "min": (1421, 0, 1504, 48),
        "max": (1504, 0, 1575, 48),
        "close": (1575, 0, 1672, 48),

        "down": (35, 498, 172, 564),
        "scan": (180, 498, 268, 564),
        "up": (277, 498, 418, 564),

        "talk": (437, 571, 892, 726),

        "volume": (54, 560, 197, 742),
        "vox": (249, 560, 392, 742),

        "ptt_vox": (882, 498, 1031, 547),
        "mute": (1038, 498, 1187, 547),
        "webcam": (882, 554, 1031, 604),
        "roger": (1038, 554, 1187, 604),

        "leden": (1207, 332, 1332, 393),
        "chat": (1338, 332, 1459, 393),
        "nieuws": (1464, 332, 1568, 393),
        "instellingen": (1572, 332, 1664, 393),

        "server": (8, 858, 432, 938),
        "naam": (433, 858, 746, 938),
    }

    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        self.setWindowTitle("Christmas Radio")
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        image_path = Path(__file__).resolve().parent / "christmas_radio.png"
        self.background = QPixmap(str(image_path))

        if self.background.isNull():
            raise FileNotFoundError(
                "Bestand 'christmas_radio.png' ontbreekt. Zet dit bestand naast main.py."
            )

        self.settings = QSettings("ChristmasRadio", "ChristmasRadio")

        self.nickname = str(self.settings.value("nickname", "Gast"))
        self.group = str(self.settings.value("group", self.SERVERS[0]))
        self.channel = int(self.settings.value("channel", 14))

        if self.channel < 1:
            self.channel = 1
        if self.channel > 40:
            self.channel = 40

        self.muted = self.settings.value("muted", False, type=bool)
        self.roger_on = self.settings.value("roger", False, type=bool)
        self.vox_on = self.settings.value("vox", False, type=bool)

        self.tx_active = False
        self.drag_pos = None
        self.active_tab = "leden"

        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update)
        self.clock.start(1000)

        self.center_on_screen()

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def save_state(self):
        self.settings.setValue("nickname", self.nickname)
        self.settings.setValue("group", self.group)
        self.settings.setValue("channel", self.channel)
        self.settings.setValue("muted", self.muted)
        self.settings.setValue("roger", self.roger_on)
        self.settings.setValue("vox", self.vox_on)

    def hit(self, x, y, name):
        x1, y1, x2, y2 = self.HIT[name]
        return x1 <= x <= x2 and y1 <= y <= y2

    def draw_text(self, painter, x, y, w, h, text, size, color="#ffffff", bold=True):
        font = QFont("Segoe UI", size)
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(QRectF(x, y, w, h), Qt.AlignmentFlag.AlignCenter, text)

    def draw_round_box(
        self,
        painter,
        x,
        y,
        w,
        h,
        fill="#03110b",
        border="#1f6b47",
        radius=8,
        border_width=2,
    ):
        pen = QPen(QColor(border), border_width)
        painter.setPen(pen)
        painter.setBrush(QColor(fill))
        painter.drawRoundedRect(QRectF(x, y, w, h), radius, radius)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(0, 0, self.background)

        # CHANNEL
        self.draw_round_box(painter, 70, 398, 98, 74, fill="#020907", border="#020907", radius=4, border_width=1)
        self.draw_text(painter, 70, 402, 98, 66, str(self.channel), 36, "#9dffb0")

        # TIME
        current_time = QDateTime.currentDateTime().toString("HH:mm")
        self.draw_round_box(painter, 269, 398, 140, 74, fill="#020907", border="#020907", radius=4, border_width=1)
        self.draw_text(painter, 269, 402, 140, 66, current_time, 34, "#9dffb0")

        # CH rechtsboven
        self.draw_round_box(painter, 1490, 278, 105, 36, fill="#07120b", border="#07120b", radius=3, border_width=1)
        self.draw_text(painter, 1490, 279, 105, 32, f"CH {self.channel}", 20, "#f7fff8")

        # OFFLINE / ONLINE indicator onder talk
        status_color = "#ff9da5"
        status_text = "● OFFLINE"
        if self.tx_active:
            status_color = "#8cff96"
            status_text = "● TX ACTIEF"

        self.draw_round_box(painter, 577, 772, 171, 51, fill="#07130c", border="#2f8b57", radius=8, border_width=2)
        self.draw_text(painter, 580, 775, 165, 43, status_text, 20, status_color)

        # Bottom TG group
        self.draw_round_box(painter, 10, 860, 418, 63, fill="#02100a", border="#1d6844", radius=6, border_width=2)
        self.draw_text(painter, 18, 867, 402, 48, f"Gekozen: {self.group}", 18, "#95f1ff")

        # Bottom nickname
        self.draw_round_box(painter, 436, 860, 309, 63, fill="#02100a", border="#1d6844", radius=6, border_width=2)
        self.draw_text(painter, 442, 867, 297, 48, f"Gebruiker: {self.nickname}", 18, "#ffffff")

        # Bottom ping
        self.draw_text(painter, 1212, 876, 72, 28, "-- ms", 16, "#7cff89")

        # Date/time right
        self.draw_text(painter, 1515, 874, 116, 22, QDateTime.currentDateTime().toString("HH:mm"), 16, "#ffffff")
        self.draw_text(painter, 1515, 899, 116, 22, QDateTime.currentDateTime().toString("dd-MM-yyyy"), 12, "#ffffff")

        # Small indicators only, no huge overlay anymore
        if self.muted:
            self.draw_text(painter, 1046, 506, 126, 24, "MUTE AAN", 12, "#ff5d5d")

        if self.vox_on:
            self.draw_text(painter, 892, 506, 126, 24, "VOX AAN", 12, "#8dff95")

        if self.roger_on:
            self.draw_text(painter, 1046, 561, 126, 24, "ROGER AAN", 11, "#8dff95")

        # Tiny TX marker on TALK button
        if self.tx_active:
            self.draw_round_box(
                painter,
                520,
                610,
                289,
                76,
                fill="#a82424aa",
                border="#ffd67a",
                radius=14,
                border_width=3,
            )
            self.draw_text(painter, 520, 615, 289, 62, "TX", 34, "#ffffff")

        painter.end()

    def change_channel(self, step):
        self.channel += step
        if self.channel < 1:
            self.channel = 40
        elif self.channel > 40:
            self.channel = 1
        self.save_state()
        self.update()

    def choose_name(self):
        value, ok = QInputDialog.getText(
            self,
            "Gebruikersnaam",
            "Voer je naam in:",
            text=self.nickname,
        )
        if ok and value.strip():
            self.nickname = value.strip()[:32]
            self.save_state()
            self.update()

    def choose_group(self):
        current_index = 0
        if self.group in self.SERVERS:
            current_index = self.SERVERS.index(self.group)

        value, ok = QInputDialog.getItem(
            self,
            "TG-groep",
            "Kies een groep:",
            self.SERVERS,
            current_index,
            False,
        )
        if ok and value:
            self.group = value
            self.save_state()
            self.update()

    def show_tab_message(self, tab_name):
        if tab_name == "leden":
            QMessageBox.information(
                self,
                "Leden",
                "De live ledenlijst koppelen we in de volgende bouwstap.",
            )
        elif tab_name == "chat":
            QMessageBox.information(
                self,
                "Chat",
                "Kanaalchat is nog niet gekoppeld.",
            )
        elif tab_name == "nieuws":
            QMessageBox.information(
                self,
                "Nieuws",
                "Nieuwsfunctie komt later.",
            )
        elif tab_name == "instellingen":
            choice, ok = QInputDialog.getItem(
                self,
                "Instellingen",
                "Wat wil je aanpassen?",
                ["Gebruikersnaam", "TG-groep"],
                0,
                False,
            )
            if ok:
                if choice == "Gebruikersnaam":
                    self.choose_name()
                else:
                    self.choose_group()

    def adjust_value_dialog(self, title):
        value, ok = QInputDialog.getInt(
            self,
            title,
            f"{title} (0 t/m 100):",
            50,
            0,
            100,
            1,
        )
        if ok:
            QMessageBox.information(
                self,
                title,
                f"{title} ingesteld op {value}.\nDe echte audiokoppeling bouwen we hierna in.",
            )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        x = int(event.position().x())
        y = int(event.position().y())

        if self.hit(x, y, "close"):
            self.close()
            return

        if self.hit(x, y, "min"):
            self.showMinimized()
            return

        if self.hit(x, y, "max"):
            QMessageBox.information(
                self,
                "Venster",
                "Deze versie gebruikt een vaste layout zodat alles netjes uitgelijnd blijft.",
            )
            return

        if self.hit(x, y, "down"):
            self.change_channel(-1)
            return

        if self.hit(x, y, "up"):
            self.change_channel(1)
            return

        if self.hit(x, y, "scan"):
            QMessageBox.information(
                self,
                "Scan",
                "Kanaalscan bouwen we later in.",
            )
            return

        if self.hit(x, y, "talk"):
            self.tx_active = True
            self.update()
            return

        if self.hit(x, y, "mute"):
            self.muted = not self.muted
            self.save_state()
            self.update()
            return

        if self.hit(x, y, "roger"):
            self.roger_on = not self.roger_on
            self.save_state()
            self.update()
            return

        if self.hit(x, y, "ptt_vox"):
            self.vox_on = not self.vox_on
            self.save_state()
            self.update()
            return

        if self.hit(x, y, "webcam"):
            QMessageBox.information(
                self,
                "Webcam",
                "Webcamfunctie komt later.",
            )
            return

        if self.hit(x, y, "volume"):
            self.adjust_value_dialog("Volume")
            return

        if self.hit(x, y, "vox"):
            self.adjust_value_dialog("VOX-gevoeligheid")
            return

        if self.hit(x, y, "server"):
            self.choose_group()
            return

        if self.hit(x, y, "naam"):
            self.choose_name()
            return

        if self.hit(x, y, "leden"):
            self.active_tab = "leden"
            self.show_tab_message("leden")
            return

        if self.hit(x, y, "chat"):
            self.active_tab = "chat"
            self.show_tab_message("chat")
            return

        if self.hit(x, y, "nieuws"):
            self.active_tab = "nieuws"
            self.show_tab_message("nieuws")
            return

        if self.hit(x, y, "instellingen"):
            self.active_tab = "instellingen"
            self.show_tab_message("instellingen")
            return

        # window slepen via bovenste balk
        if y <= 48:
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            return

        x = int(event.position().x())
        y = int(event.position().y())

        clickable = any(self.hit(x, y, key) for key in self.HIT)

        if clickable or y <= 48:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = None
            if self.tx_active:
                self.tx_active = False
                self.update()

    def closeEvent(self, event):
        self.save_state()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Christmas Radio")

    try:
        window = ChristmasRadio()
    except FileNotFoundError as exc:
        QMessageBox.critical(None, "Christmas Radio", str(exc))
        sys.exit(1)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
