from pathlib import Path
import tempfile
import subprocess

from .assistant_core import AssistantCore
from .microphone import record_to
from .transcription import Transcriber

INSTRUCTIONS = """
You are uni.co, a conversational productivity assistant.
Respond naturally in one to three sentences suitable for speech.
Avoid Markdown formatting.

You currently have no access to calendars, Spotify, study sets,
the screen, or other applications. Never claim you performed
an action or retrieved information from those applications.
"""


def main():
    assistant = AssistantCore()
    transcriber = Transcriber()
    # speaker = SpeechOutput()

    with tempfile.TemporaryDirectory() as directory:
        recording = Path(directory) / "question.wav"

        while True:
            command = input(
                "\nEnter to speak for five seconds, or q to quit: "
            )

            if command.strip().lower() == "q":
                break

            stage = "recording"

            try:
                record_to(recording)

                stage = "transcription"
                print("Transcribing...")
                transcript = transcriber.transcribe(recording)

                if not transcript:
                    print("No speech detected. Try again.")
                    continue

                print(f"You: {transcript}")

                stage = "answer generation"
                print("Thinking...")
                answer = assistant.reply(
                    f"{INSTRUCTIONS}\n\nUser: {transcript}"
                )

                if not answer or not answer.strip():
                    print("No answer returned. Try again.")
                    continue

                print(f"uni.co: {answer}")

                stage = "speech generation/playback"
                print("Generating speech...")
                # speaker.speak(answer)
                subprocess.run(
                    ["/usr/bin/say", "-f", "-"],
                    input=answer,
                    text=True,
                    check=True,
                )

            except Exception as error:
                print(str(error))
                print(
                    f"Failed during {stage}: "
                    f"{type(error).__name__}"
                )
                print("You can retry, or quit with q.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nAssistant stopped.")