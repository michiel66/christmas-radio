
"""Christmas Radio V6: spraakverbetering en extra rechtertabbladen.

De bestaande V4-tekeningen blijven ongemoeid. V5 blijft de basis.
Onderliggende communicatie gebruikt de WebSpeak3-connector (MIT).
"""

import audioop
import base64
import queue
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QInputDialog, QMessageBox

from radio_engine import RadioEngine as BaseRadioEngine


class RadioEngine(BaseRadioEngine):
    """V5-motor met microfoonkeuze en rechtstreekse kanaalselectie."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.input_device = None
        self.mic_level = 0
        self.mic_rate = 48000
        self._last_meter = 0.0
        self._convert_state = None
        self._last_unmute = 0.0

    def request_channel(self, number):
        # V5 probeerde automatisch 'CH 14' te vinden.
        # V6 gebruikt de echte serverkanalen.
        self._desired_channel = number

        if self._channels:
            self._emit(
                "channels_list",
                channels=list(self._channels),
                current_id=self._channel_id,
            )

    def select_channel(self, channel_id):
        if not self.connected:
            return

        try:
            cid = int(channel_id)
        except (TypeError, ValueError):
            return

        if cid == self._channel_id:
            return

        if not any(
            int(c.get("id", -1)) == cid
            for c in self._channels
        ):
            return

        self.set_ptt(False)
        self._command(f"switch {cid}")
        self._emit("switching", channel_id=cid)

    def set_ptt(self, enabled):
        active = (
            bool(enabled)
            and self.connected
            and self._input is not None
            and not self._muted
        )

        self._ptt = active

        if active:
            # Zendkant direct vrijgeven.
            self._command("muteinput 0")
            self._last_unmute = time.monotonic()

        elif not self._vox:
            self.transmitting = False
            self._drop_pending_audio()
            self._command("muteinput 1")
            self._emit("tx", active=False)

    def start_audio(self):
        if not self.connected:
            return

        try:
            import sounddevice as sd
        except ImportError:
            self._emit(
                "audio_error",
                message="Audio-ondersteuning is niet geïnstalleerd.",
            )
            return

        # Ontvangst: 48 kHz stereo.
        if self._output is None:

            def playback(outdata, frames, timing, status):
                try:
                    chunk = self._audio.get_nowait()
                except queue.Empty:
                    chunk = b""

                expected = frames * 4

                if len(chunk) < expected:
                    chunk += bytes(expected - len(chunk))

                outdata[:] = chunk[:expected]

            try:
                self._output = sd.RawOutputStream(
                    samplerate=48000,
                    blocksize=960,
                    channels=2,
                    dtype="int16",
                    callback=playback,
                )

                self._output.start()

            except Exception:
                self._output = None
                self._emit(
                    "audio_error",
                    message="Luidspreker kon niet worden geopend.",
                )

        # Probeer 48 kHz en 44,1 kHz microfoons.
        self._input = None

        for rate in (48000, 44100):
            self.mic_rate = rate
            self._convert_state = None
            block = round(rate * 0.02)

            def capture(indata, frames, timing, status):
                if (
                    not self.connected
                    or self._stop is None
                    or self._stop.is_set()
                ):
                    return

                pcm = bytes(indata)

                if self.mic_rate != 48000:
                    pcm, self._convert_state = audioop.ratecv(
                        pcm,
                        2,
                        1,
                        self.mic_rate,
                        48000,
                        self._convert_state,
                    )

                pcm = pcm[:1920].ljust(1920, b"\0")

                level = audioop.rms(pcm, 2)
                now = time.monotonic()

                # Microfoonmeter bijwerken.
                if now - self._last_meter >= 0.35:
                    self._last_meter = now

                    self.mic_level = min(
                        100,
                        round(level / 120),
                    )

                    self._emit(
                        "mic_level",
                        value=self.mic_level,
                    )

                # Optionele spraakactivatie.
                if self._vox and not self._muted:
                    threshold = (
                        300
                        + (100 - self._sensitivity) * 75
                    )

                    if level > threshold:
                        self._speech_until = now + 0.7

                active = (
                    (
                        self._ptt
                        or (
                            self._vox
                            and now < self._speech_until
                        )
                    )
                    and not self._muted
                )

                if active != self.transmitting:
                    self.transmitting = active

                    if not active:
                        self._drop_pending_audio()

                    self._command(
                        "muteinput 0"
                        if active
                        else "muteinput 1"
                    )

                    self._emit("tx", active=active)

                if active:
                    # Microfoon licht versterken.
                    pcm = audioop.mul(pcm, 2, 1.65)

                    self._command(
                        "audio "
                        + base64.b64encode(pcm).decode("ascii")
                    )

            try:
                self._input = sd.RawInputStream(
                    device=self.input_device,
                    samplerate=rate,
                    blocksize=block,
                    channels=1,
                    dtype="int16",
                    callback=capture,
                )

                self._input.start()

                self._emit(
                    "mic_ready",
                    rate=rate,
                )

                break

            except Exception:
                if self._input is not None:
                    try:
                        self._input.close()
                    except Exception:
                        pass

                self._input = None

        if self._input is None:
            self._emit(
                "audio_error",
                message=(
                    "Geen werkende microfoon. "
                    "Kies een andere microfoon bij TG-GROEPEN."
                ),
            )


# De zes tabbladen passen binnen het bestaande rechterpaneel.
TABS = (
    ("leden", "LEDEN"),
    ("kanalen", "KANALEN"),
    ("groepen", "TG-GROEPEN"),
    ("chat", "CHAT"),
    ("nieuws", "NIEUWS"),
    ("instellingen", "INSTELLINGEN"),
)

TAB_AREAS = {}

for i, (key, title) in enumerate(TABS):
    col = i % 3
    row = i // 3

    x = 1217 + col * 148
    y = 336 + row * 34

    TAB_AREAS[key] = (
        x,
        y,
        x + 144,
        y + 31,
    )


def install_interface(cls):
    """Voegt V6 toe aan de bestaande kerstinterface."""

    old_init = cls.__init__
    old_draw = cls.draw_sidebar
    old_press = cls.mousePressEvent
    old_event = cls.on_radio_event
    old_channel = cls.change_channel
    old_connect = cls.connect_radio
    old_group = cls.change_group

    def __init__(self):
        old_init(self)

        self.v6_scroll = 0
        self.v6_mic_level = 0
        self.v6_mic_ok = False
        self.v6_channels = []
        self.v6_mic_message = ""

        try:
            device = self.cfg.value("microfoon", "")

            self.radio.input_device = (
                int(device)
                if str(device).strip()
                else None
            )

        except (TypeError, ValueError):
            self.radio.input_device = None

    def visible_channels(self):
        return [
            c for c in self.v6_channels
            if isinstance(c, dict)
            and c.get("id") is not None
        ]

    def draw_sidebar(self, p):
        # Bestaande kerstlay-out behouden.
        old_draw(self, p)

        # Twee rijen met tabbladen.
        for key, title in TABS:
            x1, y1, x2, y2 = TAB_AREAS[key]

            selected = self.tab == key

            self.gradient(
                p,
                x1,
                y1,
                x2 - x1,
                y2 - y1,
                "#b92533" if selected else "#23523d",
                "#700e1a" if selected else "#08291c",
                "#f8d28c" if selected else "#567d63",
                6,
            )

            self.label(
                p,
                title,
                x1 + 2,
                y1 + 2,
                x2 - x1 - 4,
                y2 - y1 - 4,
                13 if key in (
                    "groepen",
                    "instellingen",
                ) else 15,
            )

        if self.tab not in ("kanalen", "groepen"):
            return

        self.gradient(
            p,
            1217,
            407,
            440,
            341,
            "#0b281f",
            "#04110d",
            "#275d45",
            9,
        )

        # KANALENLIJST
        if self.tab == "kanalen":
            channels = visible_channels(self)
            total = len(channels)

            self.v6_scroll = min(
                self.v6_scroll,
                max(0, total - 7),
            )

            self.label(
                p,
                f"KANALEN ({total})",
                1230,
                413,
                390,
                35,
                20,
                "#f5dda7",
            )

            if not self.radio.connected:
                self.label(
                    p,
                    "Verbind eerst met een TG-groep",
                    1232,
                    480,
                    390,
                    44,
                    18,
                    "#d9f7df",
                )

            elif not channels:
                self.label(
                    p,
                    "Kanaallijst wordt opgehaald...",
                    1232,
                    480,
                    390,
                    44,
                    17,
                    "#d9f7df",
                )

            else:
                shown = channels[
                    self.v6_scroll:self.v6_scroll + 7
                ]

                for i, channel in enumerate(shown):
                    y = 451 + 37 * i

                    current = (
                        channel.get("id")
                        == self.radio._channel_id
                    )

                    self.gradient(
                        p,
                        1232,
                        y,
                        406,
                        33,
                        "#2d6442" if current else "#133c2d",
                        "#16452c" if current else "#09251b",
                        "#9edca4" if current else "#2e654b",
                        5,
                    )

                    title = str(
                        channel.get("name", "Kanaal")
                    )[:39]

                    self.label(
                        p,
                        ("● " if current else "○ ") + title,
                        1241,
                        y + 1,
                        385,
                        30,
                        15,
                        "#baffbd" if current else "#e5eee4",
                        align=(
                            Qt.AlignmentFlag.AlignVCenter
                            | Qt.AlignmentFlag.AlignLeft
                        ),
                    )

                self.label(
                    p,
                    (
                        f"{self.v6_scroll + 1}-"
                        f"{min(total, self.v6_scroll + 7)} "
                        f"van {total}  •  Scroll voor meer"
                    ),
                    1235,
                    713,
                    397,
                    30,
                    13,
                    "#a8cfb6",
                )

        # TG-GROEPEN
        else:
            self.label(
                p,
                "TALK-GROEPEN",
                1227,
                416,
                400,
                41,
                23,
                "#f5dda7",
            )

            groups = (
                ("TG-103 Voorburg", 480),
                ("TG-108 Heerlen", 543),
            )

            for name, y in groups:
                active = (
                    self.group == name
                    and self.radio.connected
                )

                self.gradient(
                    p,
                    1231,
                    y,
                    407,
                    53,
                    "#286044" if active else "#1b4735",
                    "#0d3626" if active else "#09261c",
                    "#ecc878" if active else "#4b8969",
                    8,
                )

                self.label(
                    p,
                    name + (
                        "  ● ONLINE"
                        if active
                        else ""
                    ),
                    1240,
                    y + 5,
                    390,
                    43,
                    18,
                    "#d3ffdd" if active else "#f2eeee",
                )

            # Microfoon kiezen.
            self.gradient(
                p,
                1232,
                626,
                405,
                50,
                "#174a37",
                "#08291e",
                "#478564",
                7,
            )

            self.label(
                p,
                "MICROFOON KIEZEN",
                1238,
                631,
                392,
                40,
                17,
                "#fff4d5",
            )

            mic = (
                "MIC OK"
                if self.v6_mic_ok
                else "MIC NIET BESCHIKBAAR"
            )

            self.label(
                p,
                f"{mic}   •   Niveau: {self.v6_mic_level}%",
                1238,
                689,
                392,
                40,
                16,
                "#91ffa3" if self.v6_mic_ok else "#ffb3b3",
            )

    def on_radio_event(self, data):
        old_event(self, data)

        if (
            data.get("generation")
            != self.radio._generation
        ):
            return

        kind = data.get("type")

        if kind == "channels_list":
            self.v6_channels = data.get(
                "channels", []
            )

            channels = visible_channels(self)
            current = self.radio._channel_id

            for index, item in enumerate(channels):
                if item.get("id") == current:
                    self.channel = (index % 40) + 1
                    break

            self.v6_scroll = min(
                self.v6_scroll,
                max(0, len(channels) - 7),
            )

        elif kind == "mic_ready":
            self.v6_mic_ok = True
            self.v6_mic_message = (
                "Microfoon beschikbaar"
            )

        elif kind == "mic_level":
            self.v6_mic_level = int(
                data.get("value", 0)
            )

        elif kind == "audio_error":
            message = str(
                data.get("message", "")
            )

            if "microfoon" in message.lower():
                self.v6_mic_ok = False
                self.v6_mic_message = message

        elif kind == "disconnected":
            self.v6_channels = []
            self.v6_mic_ok = False

        self.update()

    def connect_radio(self):
        self.v6_mic_level = 0
        self.v6_mic_ok = False
        old_connect(self)

    def change_channel(self, delta):
        channels = visible_channels(self)

        if self.radio.connected and channels:
            current = self.radio._channel_id

            idx = next(
                (
                    i for i, c in enumerate(channels)
                    if c.get("id") == current
                ),
                0,
            )

            nxt = (
                idx + delta
            ) % len(channels)

            self.radio.select_channel(
                channels[nxt]["id"]
            )

            self.v6_scroll = max(
                0,
                nxt - 3,
            )

            self.tab = "kanalen"
            self.update()

        else:
            old_channel(self, delta)

    def change_group(self):
        before = self.group
        old_group(self)

        if self.group != before:
            self.connect_radio()

    def choose_microphone(self):
        try:
            import sounddevice as sd

            available = [
                (i, str(device["name"]))
                for i, device in enumerate(
                    sd.query_devices()
                )
                if device["max_input_channels"] > 0
            ]

        except Exception:
            QMessageBox.warning(
                self,
                "Christmas Radio",
                "Microfoonapparaten konden niet worden gevonden.",
            )
            return

        if not available:
            QMessageBox.warning(
                self,
                "Christmas Radio",
                "Geen microfoon gevonden in Windows.",
            )
            return

        items = [
            f"{i}: {name}"
            for i, name in available
        ]

        current = next(
            (
                index
                for index, (device, _) in enumerate(available)
                if device == self.radio.input_device
            ),
            0,
        )

        choice, ok = QInputDialog.getItem(
            self,
            "Christmas Radio",
            "Kies de microfoon:",
            items,
            current,
            False,
        )

        if not ok:
            return

        selected = available[
            items.index(choice)
        ][0]

        self.cfg.setValue(
            "microfoon",
            selected,
        )

        self.radio.input_device = selected

        if self.radio.connected:
            # Microfoon opnieuw openen
            # zonder radiogroep te verlaten.
            stream = self.radio._input
            self.radio._input = None

            self.radio.set_ptt(False)

            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass

            self.radio.start_audio()

    def mousePressEvent(self, event):
        if (
            event.button()
            != Qt.MouseButton.LeftButton
        ):
            return old_press(self, event)

        x, y = self.artwork_pos(
            event.position()
        )

        # Extra tabbladen.
        for key, _ in TABS:
            x1, y1, x2, y2 = TAB_AREAS[key]

            if (
                x1 <= x <= x2
                and y1 <= y <= y2
            ):
                self.tab = key
                self.update()
                return

        # Kanaal aanklikken.
        if (
            self.tab == "kanalen"
            and 1232 <= x <= 1638
            and 451 <= y < 710
        ):
            row = int(
                (y - 451) // 37
            )

            index = (
                self.v6_scroll + row
            )

            channels = visible_channels(self)

            if (
                0 <= row < 7
                and 0 <= index < len(channels)
            ):
                self.radio.select_channel(
                    channels[index]["id"]
                )

                self.update()

            return

        # TG-groep aanklikken.
        if (
            self.tab == "groepen"
            and 1231 <= x <= 1638
        ):
            target = None

            if 480 <= y <= 533:
                target = "TG-103 Voorburg"

            elif 543 <= y <= 596:
                target = "TG-108 Heerlen"

            elif 626 <= y <= 676:
                return self.choose_microphone()

            if target is not None:
                if (
                    target != self.group
                    or not self.radio.connected
                ):
                    self.radio.stop()
                    self.group = target
                    self.status = "OFFLINE"
                    self.members = []
                    self.v6_channels = []

                    self.save()
                    self.connect_radio()

                return

        return old_press(self, event)

    def wheelEvent(self, event):
        x, y = self.artwork_pos(
            event.position()
        )

        if (
            self.tab == "kanalen"
            and 1215 <= x <= 1660
            and 404 <= y <= 750
        ):
            max_offset = max(
                0,
                len(visible_channels(self)) - 7,
            )

            direction = event.angleDelta().y()

            self.v6_scroll = max(
                0,
                min(
                    max_offset,
                    self.v6_scroll + (
                        -3 if direction > 0 else 3
                    ),
                ),
            )

            self.update()
            event.accept()

        else:
            super(cls, self).wheelEvent(event)

    cls.__init__ = __init__
    cls.draw_sidebar = draw_sidebar
    cls.on_radio_event = on_radio_event
    cls.connect_radio = connect_radio
    cls.change_channel = change_channel
    cls.change_group = change_group
    cls.mousePressEvent = mousePressEvent
    cls.wheelEvent = wheelEvent
