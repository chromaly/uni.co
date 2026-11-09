import sys

import numpy as np
import sounddevice as sd
from mlx_audio.tts.utils import load_model


def main():
    text = sys.stdin.read().strip()
    if not text:
        return

    model = load_model("mlx-community/Kokoro-82M-bf16")

    try:
        for result in model.generate(
            text=text,
            voice="bf_emma",
            speed=0.95,
            lang_code="b",
        ):
            audio = np.array(
                result.audio,
                dtype=np.float32,
                copy=True,
            ).reshape(-1)

            if audio.size:
                sd.play(audio, samplerate=model.sample_rate)
                sd.wait()
    finally:
        sd.stop()


if __name__ == "__main__":
    main()