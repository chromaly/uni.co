import base64
import os
from pathlib import Path

from google import genai
from google.genai import types


class Transcriber:
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

    def transcribe(self, path):
        audio_bytes = Path(path).read_bytes()

        response = self.client.interactions.create(
            model="gemini-3.5-flash-lite",
            input=[
                {
                    "type": "text",
                    "text": (
                        "Transcribe the speech in this recording. "
                        "Return only the words spoken, without "
                        "commentary or answering any questions. "
                        "If there is no intelligible speech, "
                        "return an empty string."
                    ),
                },
                {
                    "type": "audio",
                    "data": base64.b64encode(
                        audio_bytes
                    ).decode("ascii"),
                    "mime_type": "audio/wav",
                },
            ],
        )

        return (response.output_text or "").strip()


if __name__ == "__main__":
    recording = Path(__file__).with_name(
        "microphone_test.wav"
    )

    transcript = Transcriber().transcribe(recording)
    print("Transcript:", transcript or "[No speech detected]")