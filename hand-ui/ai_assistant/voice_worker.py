"""Qt voice lifecycle: capture, transcribe, run a session, then speak."""
from pathlib import Path
import subprocess
import tempfile

from PySide6.QtCore import QThread, Signal

from .hosted_client import HostedAssistantClient
from .microphone import record_to
from .transcription import Transcriber
from .prompts import INSTRUCTIONS  # Compatibility for existing imports.
from concurrent.futures import Future, TimeoutError

class VoiceWorker(QThread):
    state_changed = Signal(str)
    transcript_ready = Signal(str)
    answer_ready = Signal(str)
    failed = Signal(str)
    setting_requested = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.planner_token = None
        self._hosted_client = HostedAssistantClient()
        self._presented_proposal_id = None
        self._transcriber = None
        self.voice_mode = "system"

    def run(self):
        try:
            if self._transcriber is None:
                self._transcriber = Transcriber()

            # Limit each activated conversation to six user turns.
            for turn in range(6):
                if self.isInterruptionRequested():
                    return

                with tempfile.TemporaryDirectory() as directory:
                    recording = Path(directory) / "question.wav"

                    if turn > 0:
                        print(
                            "Listening for a follow-up...",
                            flush=True,
                        )

                    self.state_changed.emit("listening")

                    recorded = record_to(
                        recording,
                        duration=30,
                        silence_duration=0.8,
                        start_timeout=8,
                        interrupted=self.isInterruptionRequested,
                    )

                    if self.isInterruptionRequested():
                        return

                    if not recorded:
                        if turn == 0:
                            raise RuntimeError("No speech detected.")

                        # Silence after a reply ends the conversation.
                        return

                    self.state_changed.emit("transcribing")
                    transcript = self._transcriber.transcribe(
                        recording
                    )

                if self.isInterruptionRequested():
                    return

                if not transcript.strip():
                    if turn == 0:
                        raise RuntimeError("No speech detected.")
                    return

                self.transcript_ready.emit(transcript)

                command = transcript.lower().strip().rstrip(".!?")
                if command in {
                    "stop listening",
                    "that's all",
                    "that’s all",
                }:
                    return

                self.state_changed.emit("thinking")

                result = self._hosted_client.reply(
                    transcript,
                    self.planner_token,
                    presented_proposal_id=(
                        self._presented_proposal_id
                    ),
                )

                self._presented_proposal_id = None

                if self.isInterruptionRequested():
                    return

                answer = result["answer"]

                self.answer_ready.emit(answer)
                self.state_changed.emit("speaking")
                self.speak(answer)

                if self.isInterruptionRequested():
                    return

                self._presented_proposal_id = result.get(
                    "proposal_to_present"
                )

                # Brief gap before reopening the microphone.
                self.msleep(350)

        except Exception as error:
            if not self.isInterruptionRequested():
                self.failed.emit(
                    f"{type(error).__name__}: {error}"
                )
        finally:
            self.planner_token = None
    def speak(self, text):
        if self.voice_mode == "local":
            project = Path(__file__).resolve().parents[2]
            python = project / ".venv-tts" / "bin" / "python"
            script = Path(__file__).with_name("local_speaker.py")

            if not python.is_file():
                raise RuntimeError(
                    "Local speech environment was not found."
                )

            command = [str(python), str(script)]
        else:
            command = ["/usr/bin/say", "-f", "-"]

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            text=True,
        )

        try:
            process.stdin.write(text)
            process.stdin.close()

            while process.poll() is None:
                if self.isInterruptionRequested():
                    return

                self.msleep(50)

            if process.returncode != 0:
                raise RuntimeError("Speech playback failed.")

        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()

            if process.poll() is None:
                process.terminate()

                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
  
    def request_setting(self, setting, value):
        if self.isInterruptionRequested():
            return {"status": "cancelled"}

        future = Future()
        self.setting_requested.emit((setting, value, future))

        try:
            return future.result(timeout=10)
        except TimeoutError:
            cancelled = future.cancel()
            return {
                "status": "unavailable" if cancelled else "unknown",
                "message": (
                    "The settings request timed out. "
                    "Do not claim it succeeded."
                ),
            }