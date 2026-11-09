import time

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QThread, Signal


class ClapListener(QThread):
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.detected = False

    def run(self):
        self.detected = False
        first_clap = None
        burst_start = None
        burst_peak = 0.0
        quiet_frames = 0

        try:
            device = sd.query_devices(kind="input")
            rate = int(device["default_samplerate"])

            with sd.InputStream(
                samplerate=rate,
                blocksize=round(rate * 0.02),
                channels=1,
                dtype="float32",
            ) as stream:
                while not self.isInterruptionRequested():
                    audio, overflowed = stream.read(
                        round(rate * 0.02)
                    )
                    if overflowed:
                        first_clap = None
                        burst_start = None
                        quiet_frames = 0
                        continue

                    now = time.monotonic()
                    peak = float(np.max(np.abs(audio)))
                    rms = float(np.sqrt(np.mean(audio * audio)))

                    if rms >= 0.025:
                        if burst_start is None:
                            burst_start = now
                            burst_peak = 0.0
                        burst_peak = max(burst_peak, peak)
                        quiet_frames = 0
                        continue

                    if burst_start is None:
                        continue

                    quiet_frames += 1
                    if quiet_frames < 2:
                        continue

                    duration = now - burst_start - 0.04
                    clap_time = burst_start
                    is_clap = (
                        duration <= 0.12
                        and burst_peak >= 0.25
                    )
                    burst_start = None
                    quiet_frames = 0

                    if not is_clap:
                        continue

                    if first_clap is not None:
                        gap = clap_time - first_clap

                        if 0.18 <= gap <= 0.65:
                            self.detected = True
                            return

                        if gap < 0.18:
                            continue

                    first_clap = clap_time

        except Exception as error:
            self.failed.emit(
                f"{type(error).__name__}: {error}"
            )