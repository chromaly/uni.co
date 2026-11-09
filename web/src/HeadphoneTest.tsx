import { useEffect, useRef, useState } from "react";

export default function HeadphoneTest() {
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
      player.pause();
      player.removeAttribute("src");
      player.load();

      session.setActionHandler("play", null);
      session.setActionHandler("pause", null);
      session.metadata = null;

      URL.revokeObjectURL(url);
    };
  }, [file]);

  return (
    <section>
      <h2>Headphone button test</h2>

      <input
        type="file"
        accept="audio/*"
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