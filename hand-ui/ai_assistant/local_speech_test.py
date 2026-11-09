import numpy as np
import sounddevice as sd

from mlx_audio.tts.utils import load_model


VOICE = "bf_emma"
PAUSE_SECONDS = 0.15

SENTENCES = [
    "Welcome back.",
    "Your chemistry session is ready.",
    "We can review the fundamentals first.",
    "Or, if you prefer, start with a few practice questions.",
]

def main():
    print("Loading local voice model...", flush=True)
    model = load_model("mlx-community/Kokoro-82M-bf16")

    sample_rate = model.sample_rate
    silence = np.zeros(
        round(sample_rate * PAUSE_SECONDS),
        dtype=np.float32,
    )

    pieces = []

    for index, sentence in enumerate(SENTENCES):
        print(f"Generating: {sentence}", flush=True)

        sentence_audio = []

        for result in model.generate(
            text=sentence,
            voice=VOICE,
            speed=0.95,
            lang_code="b",
        ):
            sentence_audio.append(
                np.asarray(
                    result.audio,
                    dtype=np.float32,
                ).reshape(-1)
            )

        if not sentence_audio:
            raise RuntimeError(
                f"No audio generated for: {sentence}"
            )

        if index > 0:
            pieces.append(silence)

        pieces.extend(sentence_audio)

    print("Playing with sentence pauses...", flush=True)

    try:
        sd.play(
            np.concatenate(pieces),
            samplerate=sample_rate,
        )
        sd.wait()
    finally:
        sd.stop()


if __name__ == "__main__":
    main()