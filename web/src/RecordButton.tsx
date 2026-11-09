import { useEffect, useRef, useState } from "react";
import type { User } from "firebase/auth";
import { recordAudio } from "./recordAudio";

type Props = {
  user: User;
  disabled: boolean;
  onTranscript: (text: string) => void;
  onBusyChange: (busy: boolean) => void;
};

export default function RecordButton({
  user,
  disabled,
  onTranscript,
  onBusyChange,
}: Props) {
  const [phase, setPhase] = useState<
    "idle" | "starting" | "recording" | "transcribing"
  >("idle");
  const [error, setError] = useState("");

  const active = useRef<AbortController | null>(null);
  const stopRecording = useRef<(() => void) | null>(null);

  useEffect(() => {
    const cancelWhenHidden = () => {
      if (document.hidden) active.current?.abort();
    };

    document.addEventListener("visibilitychange", cancelWhenHidden);

    return () => {
      document.removeEventListener("visibilitychange", cancelWhenHidden);
      active.current?.abort();
    };
  }, []);

  async function record() {
    if (active.current || disabled) return;

    const controller = new AbortController();
    active.current = controller;

    setError("");
    setPhase("starting");
    onBusyChange(true);

    let timeout: number | undefined;

    try {
      const audio = await recordAudio(
        controller.signal,
        (stop) => {
          stopRecording.current = stop;
          setPhase("recording");
        },
      );

      stopRecording.current = null;
      setPhase("transcribing");

      if (audio.size > 5 * 1024 * 1024) {
        throw new Error("Recording is too large. Try a shorter message.");
      }

      timeout = window.setTimeout(() => controller.abort(), 60_000);

      const token = await user.getIdToken();
      controller.signal.throwIfAborted();

      const response = await fetch(
        "https://assistant-api-efh5mnk57a-uc.a.run.app/assistant/transcribe",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": audio.type,
          },
          body: audio,
          signal: controller.signal,
        },
      );

      if (!response.ok) {
        throw new Error(
          response.status === 401
            ? "Please sign out and sign in again."
            : `Transcription failed: HTTP ${response.status}.`,
        );
      }

      const result = await response.json();

      if (
        typeof result.text !== "string" ||
        !result.text.trim()
      ) {
        throw new Error("No intelligible speech detected. Please try again.");
      }

      if (result.text.length > 4000) {
        throw new Error("Please record a shorter message.");
      }

      if (!controller.signal.aborted) {
        onTranscript(result.text);
      }
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not record your message.",
        );
      } else if (!document.hidden) {
        setError("Recording or transcription was interrupted.");
      }
    } finally {
      window.clearTimeout(timeout);
      stopRecording.current = null;
      active.current = null;
      setPhase("idle");
      onBusyChange(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        disabled={
          disabled ||
          phase === "starting" ||
          phase === "transcribing"
        }
        onClick={() => {
          if (phase === "recording") {
            stopRecording.current?.();
          } else {
            void record();
          }
        }}
      >
        {phase === "starting"
          ? "Opening microphone…"
          : phase === "recording"
            ? "Stop recording"
            : phase === "transcribing"
              ? "Transcribing…"
              : "Record message"}
      </button>

      {phase === "recording" && (
        <p>Listening. Pause to finish, or press Stop recording.</p>
      )}

      {error && <p role="alert">{error}</p>}
    </div>
  );
}