import { useEffect, useRef, useState } from "react";

import type { User } from "firebase/auth";
import { recordAudio } from "./recordAudio";

export default function HeadphoneTest({ user }: { user: User }) {

  const audio = useRef<HTMLAudioElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("Select an audio file to begin.");

  useEffect(() => {
    const player = audio.current;

    if (!file || !player) return;

    if (!("mediaSession" in navigator)) {
      setStatus("Media Session is unavailable in this browser.");
      return;
    }

    const url = URL.createObjectURL(file);
    player.src = url;

    const session = navigator.mediaSession;
    let active: AbortController | null = null;
    let completedRecordings = 0;

    async function captureQuestion() {
    if (active || !player || document.hidden) return;

    const controller = new AbortController();
    active = controller;

    let timeout: number | undefined;

    try {
        player.pause();
        session.playbackState = "paused";

        setStatus("Opening microphone from headphone button…");

        const clip = await recordAudio(
        controller.signal,
        () => setStatus("Listening—speak, then pause."),
        );

        controller.signal.throwIfAborted();
        setStatus("Transcribing headphone-triggered recording…");

        timeout = window.setTimeout(
        () => controller.abort(),
        60_000,
        );

        const token = await user.getIdToken();
        controller.signal.throwIfAborted();

        const response = await fetch(
        "https://assistant-api-efh5mnk57a-uc.a.run.app/assistant/transcribe",
        {
            method: "POST",
            headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": clip.type,
            },
            body: clip,
            signal: controller.signal,
        },
        );

        if (!response.ok) {
        throw new Error(`Transcription returned HTTP ${response.status}.`);
        }

        const result = await response.json();

        if (
        typeof result.text !== "string" ||
        !result.text.trim()
        ) {
        throw new Error("No intelligible speech detected.");
        }

        controller.signal.throwIfAborted();
        completedRecordings += 1;

        setStatus(
        `Recording ${completedRecordings}: ${result.text} ` +
        "Press your headphone button again without replaying the clip.",
        );
    } catch (error) {
        if (!controller.signal.aborted) {
        setStatus(
            error instanceof Error
            ? error.message
            : "Headphone recording failed.",
        );
        } else if (!document.hidden) {
        setStatus("Recording or transcription was interrupted.");
        }
    } finally {
        window.clearTimeout(timeout);
        active = null;
    }
    }
    try {
      session.metadata = new MediaMetadata({
        title: "Assistant headphone test",
        artist: "Button detection",
      });

      session.setActionHandler("play", () => {
        setStatus(`PLAY received at ${new Date().toLocaleTimeString()}`);

        void player.play().catch(() => {
          setStatus("PLAY received, but playback was blocked.");
        });
      });

      session.setActionHandler("pause", () => {
        setStatus(`PAUSE received at ${new Date().toLocaleTimeString()}`);
        player.pause();
      });

      setStatus("Press Play below, then use your headphone button.");
    } catch {
      setStatus("This browser could not register media controls.");
    }

    return () => {
      active?.abort();
      player.pause();
      player.removeAttribute("src");
      player.load();

      session.setActionHandler("play", null);
      session.setActionHandler("pause", null);
      session.metadata = null;

      URL.revokeObjectURL(url);
    };
  }, [file, user]);

  return (
    <section>
      <h2>Headphone button test</h2>

      <input
        type="file"
        aria-label="Choose a test audio file"
        onChange={(event) => {
          setFile(event.target.files?.[0] ?? null);
        }}
      />

      <audio
        ref={audio}
        controls
        onError={() => setStatus("Could not play this audio file.")}
      />

      <p role="status">{status}</p>
    </section>
  );
}