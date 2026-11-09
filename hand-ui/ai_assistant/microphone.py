from collections import deque
import time
import wave

import numpy as np
import sounddevice as sd


def record_to(
    path,
    duration=30,
    *,
    silence_duration=1.2,
    start_timeout=8,
    interrupted=None,
):
    interrupted = interrupted or (lambda: False)

    device = sd.query_devices(kind="input")
    sample_rate = int(device["default_samplerate"])
    block_size = round(sample_rate * 0.02)

    # Lower this for a quiet voice; raise it for background noise.
    speech_threshold = 0.006

    # Keep the beginning of words before speech is confirmed.
    pre_roll = deque(maxlen=10)
    chunks = []
    speech_frames = 0
    speech_started = None
    last_speech = None
    waiting_started = time.monotonic()


    with sd.InputStream(
        samplerate=sample_rate,
        blocksize=block_size,
        channels=1,
        dtype="int16",
    ) as stream:
        while not interrupted():
            audio, overflowed = stream.read(block_size)
            now = time.monotonic()

            if overflowed:
                raise RuntimeError(
                    "Microphone recording fell behind. Please try again."
                )

            chunk = audio.copy()
            samples = chunk.astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(samples * samples)))
            is_speech = rms >= speech_threshold

            if speech_started is None:
                pre_roll.append(chunk)
                speech_frames = (
                    speech_frames + 1 if is_speech else 0
                )

                # Require two consecutive blocks above the threshold.
                if speech_frames >= 2:
                    speech_started = now
                    last_speech = now
                    chunks.extend(pre_roll)
                    pre_roll.clear()
                elif now - waiting_started >= start_timeout:
                    return False

                continue

            chunks.append(chunk)

            if is_speech:
                last_speech = now

            if now - speech_started >= duration:
                break

            if now - last_speech >= silence_duration:
                break

    if interrupted() or not chunks:
        return False

    with wave.open(str(path), "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(sample_rate)
        recording.writeframes(
            b"".join(chunk.tobytes() for chunk in chunks)
        )

    return True