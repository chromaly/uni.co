import base64
import os
from pathlib import Path
import subprocess
import tempfile

from google import genai
from google.genai import types
import time
import sounddevice as sd

VOICE = "Algieba"
#VOICE = "Capella"

STYLE = (
    "A refined British English accent. "
    "Calm, quietly confident, and conversational. "
    "Natural variation in pitch and emphasis, with crisp diction. "
    "Measured pacing with short, natural pauses. "
    "Warm and understated rather than theatrical or announcer-like."
)


class SpeechOutput:
    def __init__(self):
        key = os.environ.get("GEMINI_API_KEY")

        if not key:
            raise RuntimeError("Set GEMINI_API_KEY first.")

        self.client = genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=30_000,
                retry_options=types.HttpRetryOptions(attempts=0),
            ),
        )

    def speak(self, text):
        if not text or not text.strip():
            return
        started = time.monotonic()
        print("Sending TTS request...", flush=True)

        stream = self.client.interactions.create(
            model="gemini-3.8-flash-lite-tts",
            input=[
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": text,
                            "annotations": [
                                {
                                    "type": "speech_metadata",
                                    "style": STYLE,
                                }
                            ],
                        }
                    ],
                }
            ],
            response_format={
                "type": "audio",
                "mime_type": "audio/l16",
                "sample_rate": 24000,
            },
            generation_config={
                "speech_config": [{"voice": VOICE}]
            },
            stream=True,
            timeout=20.0,
        )
        print("Stream created; waiting for events...", flush=True)
        received_audio = False
        pending = b""

        try:
            with sd.RawOutputStream(
                samplerate=24000,
                channels=1,
                dtype="int16",
            ) as output:
                for event in stream:
                    for event in stream:
                        print(
                            f"Event: {event.event_type}",
                            flush=True,
                        )

                    if event.event_type != "step.delta":
                        continue

                    delta = event.delta

                    print(
                        f"Delta type: {getattr(delta, 'type', None)}",
                        flush=True,
                    )
                    if getattr(delta, "type", None) != "audio":
                        continue

                    if not delta.data:
                        continue

                    chunk = base64.b64decode(delta.data)

                    if not chunk:
                        continue

                    if not received_audio:
                        received_audio = True
                        print(
                            "First audio received after "
                            f"{time.monotonic() - started:.1f}s",
                            flush=True,
                        )

                    # Each 16-bit sample occupies two bytes.
                    pending += chunk
                    complete_bytes = len(pending) // 2 * 2

                    if complete_bytes:
                        output.write(pending[:complete_bytes])
                        pending = pending[complete_bytes:]
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                close()

        if not received_audio:
            raise RuntimeError("Gemini returned no audio.")


if __name__ == "__main__":
    SpeechOutput().speak(
        "Welcome back. Shall we clear your afternoon, "
        "or tackle that study session first?"
    )