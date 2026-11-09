import { useCallback, useEffect, useRef, useState } from "react";

export function useSpeech() {
  const [speaking, setSpeaking] = useState(false);
  const [speechError, setSpeechError] = useState("");

  const current = useRef<SpeechSynthesisUtterance | null>(null);
  const supported = "speechSynthesis" in window;

  const stop = useCallback(() => {
    if (current.current) {
      current.current.onend = null;
      current.current.onerror = null;
      current.current = null;
    }

    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    setSpeaking(false);
  }, []);

  const speak = useCallback(
    (text: string) => {
      stop();
      setSpeechError("");

      if (!supported) {
        setSpeechError("Spoken replies are unavailable in this browser.");
        return;
      }

      if (!text.trim()) return;

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = "en-GB";
      utterance.rate = 1;
      utterance.pitch = 1;

      const voices = window.speechSynthesis.getVoices();
      const voice = voices.find(
        (item) => item.lang.toLowerCase() === "en-gb",
      );

      if (voice) utterance.voice = voice;

      current.current = utterance;
      setSpeaking(true);

      utterance.onend = () => {
        if (current.current !== utterance) return;

        current.current = null;
        setSpeaking(false);
      };

      utterance.onerror = () => {
        if (current.current !== utterance) return;

        current.current = null;
        setSpeaking(false);
        setSpeechError(
          "Speech playback failed. You can read or replay the reply.",
        );
      };

      try {
        window.speechSynthesis.speak(utterance);
      } catch {
        current.current = null;
        setSpeaking(false);
        setSpeechError("Could not start speech playback.");
      }
    },
    [stop, supported],
  );

  useEffect(() => {
    const cancel = () => {
      if (current.current) {
        current.current.onend = null;
        current.current.onerror = null;
        current.current = null;
      }

      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) stop();
    };

    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      document.removeEventListener(
        "visibilitychange",
        onVisibilityChange,
      );
      cancel();
    };
  }, [stop]);

  return { speak, stop, speaking, speechError, supported };
}