import os
import time

import requests


started = time.monotonic()

try:
    with requests.post(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        headers={
            "x-goog-api-key": os.environ["GEMINI_API_KEY"],
            "Content-Type": "application/json",
        },
        json={
            "model": "gemini-3.8-flash-lite-tts",
            "input": [
                {
                    "type": "user_input",
                    "content": [
                        {"type": "text", "text": "Hello."}
                    ],
                }
            ],
            "response_format": {"type": "audio"},
            "generation_config": {
                "speech_config": [{"voice": "Algieba"}]
            },
            "stream": True,
        },
        stream=True,
        timeout=(5, 20),
    ) as response:
        print(
            f"HTTP {response.status_code}, "
            f"after {time.monotonic() - started:.1f}s",
            flush=True,
        )

        if not response.ok:
            print(response.text)
        else:
            for chunk in response.iter_content(chunk_size=64):
                if chunk:
                    print("Stream data received.", flush=True)
                    break

except requests.RequestException as error:
    print(type(error).__name__, str(error))