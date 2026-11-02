
"""Christmas Radio V5.

Voegt de radioverbinding toe aan de bestaande V4-app.
De goedgekeurde layout en hotspot-posities blijven staan.
"""

import re
from pathlib import Path


file = Path("main.py")
s = file.read_text(encoding="utf-8")

if "Christmas Radio V4" not in s:
    raise SystemExit(
        "V5 verwacht de werkende Christmas Radio V4."
    )


def once(old, new, label):
    global s

    count = s.count(old)

    if count != 1:
        raise SystemExit(
            f"Patch-afwijking bij {label}: "
            f"{count} overeenkomsten"
        )

    s = s.replace(
        old,
        new,
        1,
    )


def method(name, replacement):
    global s

    pattern = (
        rf"(?ms)^    def {name}\("
        r".*?(?=^    def |^def main\(|\Z)"
    )

    s, count = re.subn(
        pattern,
        replacement.rstrip() + "\n\n",
        s,
        count=1,
    )

    if count != 1:
        raise SystemExit(
            "Methode ontbreekt: " + name
        )


# Radiomotor importeren.
once(
    "from pathlib import Path",
    "from pathlib import Path\n"
    "from radio_engine import RadioEngine",
    "import",
)

# Klikvlak voor ONLINE/OFFLINE.
once(
    '        "talk": (483, 585, 871, 731),',
    '        "talk": (483, 585, 871, 731),\n'
    '        "status": (582, 782, 753, 836),',
    "status-hotspot",
)

# Statusvariabelen en radio starten.
once(
    "        self.drag_offset = None\n\n"
    "        # Klok",
    """        self.drag_offset = None
        self.status = "OFFLINE"
        self.members = []
        self.radio_message = "Klik op OFFLINE om te verbinden"
        self.chat_messages = []

        self.radio = RadioEngine(self)
        self.radio.event.connect(self.on_radio_event)

        # Klok""",
    "radio-start",
)


# Nieuwe verbindingsfuncties.
backend_methods = '''    def connect_radio(self):
        if self.radio.connected or self.radio.connecting:
            self.radio.stop()
            self.status = "OFFLINE"
            self.members = []
            self.update()
            return

        if self.nickname.strip().lower() in ("", "gast"):
            value, ok = QInputDialog.getText(
                self,
                "Christmas Radio",
                "Welke naam gebruik je op de radio?",
                text=""
            )

            if not ok or not value.strip():
                return

            self.nickname = str(value.strip())[:28]
            self.save()

        self.radio.set_options(
            self.muted,
            self.vox,
            self.sensitivity
        )

        self.radio.set_volume(self.volume)
        self.radio.request_channel(self.channel)

        identity = str(
            self.cfg.value(
                "radio_identity_" + self.group,
                ""
            )
        )

        self.radio.start(
            self.group,
            self.nickname,
            identity
        )

    def on_radio_event(self, data):
        if data.get("generation") != self.radio._generation:
            return

        kind = data.get("type")

        if kind == "connecting":
            self.status = "VERBINDEN"
            self.radio_message = "Verbinding maken..."

        elif kind == "connected":
            self.status = "ONLINE"

            identity = data.get("identity", "")

            if identity:
                self.cfg.setValue(
                    "radio_identity_" + self.group,
                    identity
                )

            if (
                self.radio._input is None
                and self.radio._output is None
            ):
                self.radio.start_audio()

            self.radio_message = (
                "Verbonden met " + self.group
            )

        elif kind == "disconnected":
            self.status = "OFFLINE"
            self.members = []
            self.ptt_down = False

            self.radio_message = (
                "Verbinding verbroken. Klik op OFFLINE."
            )

        elif kind in ("members", "talkers"):
            self.members = data.get(
                "members", []
            )

        elif kind == "tx":
            pass

        elif kind == "channel_unavailable":
            self.radio_message = (
                "Kanaal CH "
                + str(
                    data.get("number", self.channel)
                )
                + " niet op deze server gevonden"
            )

        elif kind == "chat":
            name = str(
                data.get("from_user", "")
            )[:20]

            message = str(
                data.get("message", "")
            )[:110]

            self.chat_messages.append(
                name + ": " + message
            )

            self.chat_messages = (
                self.chat_messages[-6:]
            )

        elif kind in ("audio_error", "error"):
            self.radio_message = str(
                data.get(
                    "message",
                    "Radioprobleem"
                )
            )

        self.update()

    def update_audio_options(self):
        self.radio.set_options(
            self.muted,
            self.vox,
            self.sensitivity
        )

        self.radio.set_volume(
            self.volume
        )

'''

once(
    "    def draw_status(self, painter):",
    backend_methods
    + "    def draw_status(self, painter):",
    "connection-methods",
)


# Echte statusindicator.
method(
    "draw_status",
    '''    def draw_status(self, painter):
        live = self.status == "ONLINE"
        waiting = self.status == "VERBINDEN"

        self.gradient(
            painter,
            582, 782, 171, 53,
            "#0f4b23" if live else "#514016" if waiting else "#35191f",
            "#061f0e" if live else "#241e0e" if waiting else "#100d11",
            "#55ec7e" if live else "#e6c969" if waiting else "#eb6671",
            13,
        )

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.setBrush(
            QColor(
                "#4dff78" if live
                else "#f1c04c" if waiting
                else "#fa5662"
            )
        )

        painter.drawEllipse(
            QPointF(603, 808),
            7,
            7,
        )

        self.label(
            painter,
            self.status,
            615, 790, 134, 38,
            17 if waiting else 20,
            "#f4fff4",
        )''',
)


# RX / TX echte signalen.
once(
    '(838, False, "#3dff69"),',
    '(838, self.radio.rx_active, "#3dff69"),',
    "rx",
)

once(
    '(891, self.ptt_down, "#ff4b54"),',
    '(891, self.radio.transmitting, "#ff4b54"),',
    "tx",
)

# Leden-teller.
once(
    '"leden": "LEDEN (0)",',
    '"leden": f"LEDEN ({len(self.members)})",',
    "leden-teller",
)


# Ledenlijst opnieuw vullen met live gegevens.
pattern = (
    r'(?ms)^        if self.tab == "leden":\n'
    r'.*?(?=^        elif self.tab == "chat":)'
)

leden = '''        if self.tab == "leden":
            if self.status != "ONLINE":
                self.label(
                    painter,
                    "● " + self.status,
                    1230, 451, 391, 44,
                    22,
                    "#f6aeaa"
                )

                self.label(
                    painter,
                    self.radio_message[:46],
                    1228, 514, 395, 48,
                    16,
                    "#f4e6be"
                )

                self.label(
                    painter,
                    "Klik onder de TALK-knop om te verbinden",
                    1230, 578, 390, 34,
                    15,
                    "#bde5cd"
                )

            elif not self.members:
                self.label(
                    painter,
                    "Nog geen leden in dit kanaal",
                    1229, 480, 394, 45,
                    18,
                    "#f4e6be"
                )

                self.label(
                    painter,
                    self.radio_message[:48],
                    1230, 552, 390, 31,
                    14,
                    "#bde5cd"
                )

            else:
                for i, client in enumerate(self.members[:7]):
                    y = 419 + 41 * i

                    if client.get("talking"):
                        color = "#75ff8c"
                        sign = "●"
                    else:
                        color = "#dbebdb"
                        sign = "○"

                    self.label(
                        painter,
                        sign,
                        1228, y, 35, 34,
                        19,
                        color
                    )

                    self.label(
                        painter,
                        client.get("name", "")[:27],
                        1263, y, 350, 34,
                        17,
                        color,
                        align=(
                            Qt.AlignmentFlag.AlignVCenter
                            | Qt.AlignmentFlag.AlignLeft
                        ),
                    )

                self.label(
                    painter,
                    self.radio_message[:48],
                    1231, 716, 388, 30,
                    12,
                    "#95c8ad"
                )
'''

s, count = re.subn(
    pattern,
    lambda match: leden,
    s,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Ledenpaneel niet gevonden"
    )


# Chatvenster met echte ontvangen berichten.
pattern = (
    r'(?ms)^        elif self.tab == "chat":\n'
    r'.*?(?=^        elif self.tab == "nieuws":)'
)

chat = '''        elif self.tab == "chat":
            self.label(
                painter,
                "KANAALCHAT",
                1230, 418, 390, 38,
                19,
                "#f5e3b2"
            )

            for index, message in enumerate(
                self.chat_messages[-6:]
            ):
                self.label(
                    painter,
                    message[:51],
                    1230,
                    462 + 40 * index,
                    392,
                    37,
                    13,
                    "#d8f7e0",
                    align=(
                        Qt.AlignmentFlag.AlignVCenter
                        | Qt.AlignmentFlag.AlignLeft
                    ),
                )

            self.label(
                painter,
                "Klik hier om een bericht te sturen",
                1228, 717, 392, 30,
                13,
                "#d8f7e0"
            )
'''

s, count = re.subn(
    pattern,
    lambda match: chat,
    s,
    count=1,
)

if count != 1:
    raise SystemExit(
        "Chatpaneel niet gevonden"
    )


# Volumetekst aanpassen.
once(
    'f"Volume: {self.volume}% (nog geen audio)"',
    'f"Volume: {self.volume}%"',
    "volume-status",
)


# Kanaalwisseling doorgeven.
once(
    "        self.save()\n"
    "        self.update()\n\n"
    "    def change_name",
    "        self.radio.request_channel(self.channel)\n"
    "        self.save()\n"
    "        self.update()\n\n"
    "    def change_name",
    "kanaal-actie",
)


# Gebruikersnaam wijzigen.
once(
    "            self.nickname = value.strip()[:28]\n"
    "            self.save()",
    "            self.nickname = value.strip()[:28]\n"
    "            was_connected = (\n"
    "                self.radio.connected or self.radio.connecting\n"
    "            )\n"
    "            if was_connected:\n"
    "                self.radio.stop()\n"
    "            self.save()",
    "naam-actie",
)


# TG-groep veranderen.
once(
    "            self.group = value\n"
    "            self.save()",
    "            self.group = value\n"
    "            self.radio.stop()\n"
    '            self.status = "OFFLINE"\n'
    "            self.members = []\n"
    "            self.save()",
    "groep-actie",
)


# Volume en gevoeligheid doorgeven.
once(
    "            setattr(self, key, value)\n"
    "            self.save()",
    "            setattr(self, key, value)\n"
    "            self.update_audio_options()\n"
    "            self.save()",
    "volume-actie",
)


# ONLINE/OFFLINE gebruiken als verbindingsknop.
once(
    "        # TALK.\n",
    '''        if self.in_box(
            x, y,
            self.HOTSPOTS["status"]
        ):
            self.connect_radio()
            return

        if (
            self.tab == "chat"
            and 1218 <= x <= 1650
            and 404 <= y <= 748
        ):
            if self.radio.connected:
                text, ok = QInputDialog.getText(
                    self,
                    "Kanaalchat",
                    "Bericht:"
                )

                if ok and text.strip():
                    self.radio.send_chat(text)

            return

        # TALK.
''',
    "status-actie",
)


# PTT via de muis en de spatiebalk.
# Deze code komt tweemaal voor in V4.
press = (
    "            self.ptt_down = True\n"
    "            self.update()"
)

if s.count(press) != 2:
    raise SystemExit(
        "TALK-anker gewijzigd: "
        + str(s.count(press))
    )

s = s.replace(
    press,
    "            self.ptt_down = (\n"
    "                self.radio.connected\n"
    "                and not self.muted\n"
    "                and self.radio._input is not None\n"
    "            )\n"
    "            self.radio.set_ptt(self.ptt_down)\n"
    "            self.update()",
)


# TALK loslaten met muis of spatiebalk.
release = (
    "            self.ptt_down = False\n"
    "            self.update()"
)

if s.count(release) != 2:
    raise SystemExit(
        "PTT-stop ankers gewijzigd: "
        + str(s.count(release))
    )

s = s.replace(
    release,
    "            self.ptt_down = False\n"
    "            self.radio.set_ptt(False)\n"
    "            self.update()",
)


# Bij focusverlies zenden stoppen.
once(
    "        self.ptt_down = False\n"
    "        self.update()\n\n"
    "        super().focusOutEvent",
    "        self.ptt_down = False\n"
    "        self.radio.set_ptt(False)\n"
    "        self.update()\n\n"
    "        super().focusOutEvent",
    "focus-stop",
)


# Bij afsluiten verbinding beëindigen.
once(
    "        self.ptt_down = False\n"
    "        self.save()\n"
    "        super().closeEvent",
    "        self.ptt_down = False\n"
    "        self.radio.stop()\n"
    "        self.save()\n"
    "        super().closeEvent",
    "close-stop",
)


# MUTE en VOX naar de radiomotor sturen.
once(
    "                self.save()\n"
    "                self.update()\n"
    "                return\n\n"
    "        # Webcam.",
    "                self.update_audio_options()\n"
    "                self.save()\n"
    "                self.update()\n"
    "                return\n\n"
    "        # Webcam.",
    "mute-vox-actie",
)


file.write_text(
    s,
    encoding="utf-8",
)

print(
    "Christmas Radio V5 gekoppeld. "
    "De V4-kerstlayout is behouden."
)
