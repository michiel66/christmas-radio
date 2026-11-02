
"""Interne radiomotor van Christmas Radio.

Gebaseerd op de WebSpeak3-connector.
Zie de meegeleverde licentiebestanden.
"""

import audioop
import base64
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal


SERVERS = {
    "TG-103 Voorburg": "ptt.mijnts3.nl",
    "TG-108 Heerlen": "heerlen.mijnts3.nl",
}

SAMPLES = 960


class RadioEngine(QObject):
    event = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.connected = False
        self.connecting = False
        self.transmitting = False
        self.rx_active = False

        self._generation = 0
        self._process = None
        self._stop = None
        self._commands = None

        self._audio = queue.Queue(maxsize=12)

        self._input = None
        self._output = None

        self._ptt = False
        self._muted = False
        self._vox = False

        self._sensitivity = 40
        self._volume = 65
        self._speech_until = 0.0

        self._channel_id = None
        self._channels = []
        self._clients = []
        self._talkers = set()

        self._own_id = 0
        self._desired_channel = 14
        self._last_channel_request = None

    def _emit(self, kind, **data):
        self.event.emit({
            "type": kind,
            "generation": self._generation,
            **data,
        })

    def _command(self, text):
        if self._commands is not None:
            try:
                self._commands.put_nowait(text)
            except queue.Full:
                pass

    def start(self, group, nickname, identity=""):
        self.stop(notify=False)

        if group not in SERVERS:
            self._emit(
                "error",
                message="Onbekende radiogroep.",
            )
            return

        folder = Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(__file__).resolve().parent,
            )
        )

        binary = folder / "ts-connector.exe"

        if not binary.is_file():
            self._emit(
                "error",
                message="Radiomotor ontbreekt in deze installatie.",
            )
            return

        self._generation += 1
        generation = self._generation

        self._stop = threading.Event()
        self._commands = queue.Queue(maxsize=24)
        self._audio = queue.Queue(maxsize=12)

        self._channel_id = None
        self._channels = []
        self._clients = []
        self._talkers = set()
        self._own_id = 0
        self._last_channel_request = None

        self.connected = False
        self.connecting = True
        self.transmitting = False
        self._ptt = False

        env = os.environ.copy()

        if identity:
            env["TS_IDENTITY"] = identity

        flags = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )

        try:
            self._process = subprocess.Popen(
                [
                    str(binary),
                    "--address",
                    SERVERS[group],
                    "--nickname",
                    nickname,
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=flags,
                env=env,
            )

        except OSError:
            self.connecting = False
            self._emit(
                "error",
                message="De radiomotor kon niet starten.",
            )
            return

        process = self._process
        stopped = self._stop
        commands = self._commands

        self._emit("connecting")

        threading.Thread(
            target=self._read_loop,
            args=(process, stopped, generation),
            daemon=True,
        ).start()

        threading.Thread(
            target=self._write_loop,
            args=(process, stopped, commands),
            daemon=True,
        ).start()

        threading.Thread(
            target=self._drain_errors,
            args=(process,),
            daemon=True,
        ).start()

    def _read_loop(self, process, stopped, generation):
        try:
            for line in process.stdout:
                if stopped.is_set():
                    break

                if generation != self._generation:
                    break

                try:
                    data = json.loads(line)
                except ValueError:
                    continue

                kind = data.get("type")

                if kind == "audioOut":
                    if self._output:
                        try:
                            sample = base64.b64decode(
                                data.get("pcm", ""),
                                validate=True,
                            )

                            if self._volume != 100:
                                sample = audioop.mul(
                                    sample,
                                    2,
                                    self._volume / 100.0,
                                )

                            if len(sample) != SAMPLES * 4:
                                continue

                            if self._audio.full():
                                self._audio.get_nowait()

                            self._audio.put_nowait(sample)

                        except (
                            ValueError,
                            queue.Empty,
                            queue.Full,
                        ):
                            pass

                    continue

                if kind == "connected":
                    self.connected = True
                    self.connecting = False

                    self._emit(
                        "connected",
                        identity=data.get("identity", ""),
                    )

                    self._command("muteinput 1")

                elif kind == "channels":
                    self._channels = data.get(
                        "channels", []
                    )

                    self._clients = data.get(
                        "clients", []
                    )

                    self._own_id = data.get(
                        "own_client_id", 0
                    )

                    own = next(
                        (
                            c for c in self._clients
                            if c.get("id") == self._own_id
                        ),
                        None,
                    )

                    self._channel_id = (
                        own.get("channel")
                        if own else None
                    )

                    self._emit(
                        "members",
                        members=self.members(),
                    )

                    self.request_channel(
                        self._desired_channel
                    )

                elif kind == "talkers":
                    self._talkers = set(
                        data.get("clients", [])
                    )

                    self.rx_active = bool(
                        self._talkers - {self._own_id}
                    )

                    self._emit(
                        "talkers",
                        members=self.members(),
                        rx=self.rx_active,
                    )

                elif kind == "reconnecting":
                    self.connected = False
                    self.connecting = True
                    self._emit("connecting")

                elif kind == "reconnected":
                    self.connected = True
                    self.connecting = False

                    self._emit(
                        "connected",
                        identity="",
                    )

                elif kind == "disconnected":
                    self.connected = False
                    self.connecting = False
                    self._emit("disconnected")

                elif kind == "chatMessage":
                    self._emit(
                        "chat",
                        from_user=data.get("from", ""),
                        message=data.get("message", ""),
                    )

                elif kind == "error":
                    self._emit(
                        "error",
                        message=(
                            "De radioverbinding of "
                            "actie is mislukt."
                        ),
                    )

        finally:
            if (
                generation == self._generation
                and not stopped.is_set()
            ):
                self.connected = False
                self.connecting = False
                self._emit("disconnected")

    @staticmethod
    def _write_loop(process, stopped, commands):
        while not stopped.is_set():
            try:
                command = commands.get(timeout=0.2)

            except queue.Empty:
                continue

            try:
                process.stdin.write(
                    command + "\n"
                )
                process.stdin.flush()

            except (
                BrokenPipeError,
                OSError,
                ValueError,
            ):
                break

    @staticmethod
    def _drain_errors(process):
        try:
            for _ in process.stderr:
                pass

        except (OSError, ValueError):
            pass

    def members(self):
        return [
            {
                "name": str(
                    c.get("name", "")
                )[:30],
                "talking": (
                    c.get("id") in self._talkers
                ),
            }
            for c in self._clients
            if (
                c.get("channel") == self._channel_id
                and not c.get("is_query", False)
            )
        ][:25]

    def request_channel(self, number):
        self._desired_channel = number

        if not self.connected or not self._channels:
            return

        pattern = re.compile(
            r"^(?:ch|cb|kanaal)\s*[-:# ]*\s*0*"
            + str(number)
            + r"(?:\b|$)",
            re.I,
        )

        match = next(
            (
                c for c in self._channels
                if pattern.search(
                    str(c.get("name", ""))
                )
            ),
            None,
        )

        if match:
            target = int(
                match.get("id", 0)
            )

            if (
                target
                and self._channel_id != target
                and self._last_channel_request != target
            ):
                self._last_channel_request = target

                self._command(
                    "switch " + str(target)
                )
        else:
            self._emit(
                "channel_unavailable",
                number=number,
            )

    def start_audio(self):
        if not self.connected:
            return

        try:
            import sounddevice as sd

        except ImportError:
            self._emit(
                "audio_error",
                message="Audio-ondersteuning ontbreekt.",
            )
            return

        def playback(outdata, frames, timing, status):
            try:
                chunk = self._audio.get_nowait()

            except queue.Empty:
                chunk = bytes(frames * 4)

            expected = frames * 4

            outdata[:] = (
                chunk[:expected]
                .ljust(expected, b"\0")
            )

        def capture(indata, frames, timing, status):
            if (
                frames != SAMPLES
                or not self.connected
                or self._stop is None
                or self._stop.is_set()
            ):
                return

            frame = bytes(indata)

            if len(frame) != SAMPLES * 2:
                return

            now = time.monotonic()

            if self._vox and not self._muted:
                level = audioop.rms(
                    frame, 2
                )

                threshold = (
                    300
                    + (100 - self._sensitivity) * 75
                )

                if level > threshold:
                    self._speech_until = (
                        now + 0.7
                    )

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

                self._emit(
                    "tx",
                    active=active,
                )

            if active:
                self._command(
                    "audio "
                    + base64.b64encode(frame).decode(
                        "ascii"
                    )
                )

        try:
            self._output = sd.RawOutputStream(
                samplerate=48000,
                blocksize=SAMPLES,
                channels=2,
                dtype="int16",
                callback=playback,
            )

            self._output.start()

        except Exception:
            self._output = None

            self._emit(
                "audio_error",
                message=(
                    "De luidspreker kon "
                    "niet worden geopend."
                ),
            )

        try:
            self._input = sd.RawInputStream(
                samplerate=48000,
                blocksize=SAMPLES,
                channels=1,
                dtype="int16",
                callback=capture,
            )

            self._input.start()

        except Exception:
            self._input = None

            self._emit(
                "audio_error",
                message=(
                    "De microfoon kon "
                    "niet worden geopend."
                ),
            )

    def set_ptt(self, enabled):
        self._ptt = (
            bool(enabled)
            and self.connected
            and self._input is not None
        )

        if (
            not self._ptt
            and self.transmitting
            and not self._vox
        ):
            self.transmitting = False

            self._drop_pending_audio()

            self._command("muteinput 1")

            self._emit(
                "tx",
                active=False,
            )

    def _drop_pending_audio(self):
        if self._commands is None:
            return

        retained = []

        while True:
            try:
                item = (
                    self._commands.get_nowait()
                )

            except queue.Empty:
                break

            if not item.startswith("audio "):
                retained.append(item)

        for item in retained:
            self._command(item)

    def set_options(
        self,
        muted,
        vox,
        sensitivity,
    ):
        self._muted = bool(muted)
        self._vox = bool(vox)
        self._sensitivity = int(sensitivity)

        if muted:
            self.set_ptt(False)
            self.transmitting = False

            self._drop_pending_audio()

            self._command("muteinput 1")

            self._emit(
                "tx",
                active=False,
            )

    def set_volume(self, volume):
        self._volume = max(
            0,
            min(100, int(volume)),
        )

    def send_chat(self, message):
        message = (
            str(message)
            .replace("\r", " ")
            .replace("\n", " ")[:500]
        )

        if self.connected and message.strip():
            self._command(
                "chat " + message
            )

    def stop(self, notify=True):
        self._generation += 1

        self.connected = False
        self.connecting = False
        self.transmitting = False
        self._ptt = False

        if self._stop:
            self._stop.set()

        for name in (
            "_input",
            "_output",
        ):
            stream = getattr(self, name)

            setattr(
                self,
                name,
                None,
            )

            if stream:
                try:
                    stream.stop()
                    stream.close()

                except Exception:
                    pass

        process = self._process
        self._process = None

        if (
            process
            and process.poll() is None
        ):
            try:
                process.terminate()
                process.wait(timeout=0.8)

            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

        self._commands = None
        self._talkers = set()
        self._clients = []
        self._channels = []
        self.rx_active = False

        if notify:
            self._emit("disconnected")
