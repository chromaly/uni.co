import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { User } from "firebase/auth";

import RecordButton from "./RecordButton";
import { useSpeech } from "./useSpeech";

const API_URL =
  "https://assistant-api-efh5mnk57a-uc.a.run.app";

export default function AssistantChat({ user }: { user: User }) {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [presentedId, setPresentedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [audioBusy, setAudioBusy] = useState(false);

  const activeRequest = useRef<AbortController | null>(null);

  const [voiceEnabled, setVoiceEnabled] = useState(false);

    const {
    speak,
    stop,
    speaking,
    speechError,
    supported,
    } = useSpeech();

  useEffect(() => {
    return () => activeRequest.current?.abort();
  }, []);

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const text = message.trim();

    if (!text || activeRequest.current || audioBusy || speaking) return;

    const controller = new AbortController();
    activeRequest.current = controller;

    setBusy(true);
    setError("");

    const timeout = window.setTimeout(
      () => controller.abort(),
      180_000,
    );

    try {
      const token = await user.getIdToken();

      if (controller.signal.aborted) return;

      const response = await fetch(`${API_URL}/assistant/message`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: text,
          ...(presentedId
            ? { presented_proposal_id: presentedId }
            : {}),
        }),
        signal: controller.signal,
      });

      if (response.status === 401) {
        throw new Error("Please sign out and sign in again.");
      }

      if (response.status === 409) {
        setPresentedId(null);
        throw new Error(
          "The conversation is busy or the draft changed. " +
          "Wait briefly, then ask to review the current draft.",
        );
      }

      if (!response.ok) {
        throw new Error(
          `Assistant returned HTTP ${response.status}. ` +
          "If you were saving something, check Planner before retrying.",
        );
      }

      const result = await response.json();

      if (
        typeof result.answer !== "string" ||
        !result.answer.trim() ||
        (
          result.proposal_to_present != null &&
          typeof result.proposal_to_present !== "string"
        )
      ) {
        throw new Error("The assistant returned an invalid response.");
      }

      if (controller.signal.aborted) return;

      setAnswer(result.answer);
      setPresentedId(result.proposal_to_present ?? null);
      setMessage("");
      if (voiceEnabled) {
        speak(result.answer);
    }
    } catch (cause) {
      if (controller.signal.aborted) {
        setError(
          "The request was interrupted or timed out. " +
          "If you were saving something, check Planner before retrying.",
        );
      } else {
        setError(
          cause instanceof Error
            ? cause.message
            : "Could not contact the assistant.",
        );
      }
    } finally {
      window.clearTimeout(timeout);
      activeRequest.current = null;
      setBusy(false);
    }
  }

  return (
    <section className="assistant-chat">
      <h2>Talk to your assistant</h2>

                {supported && (
        <div>
            <button
            type="button"
            disabled={busy || audioBusy}
            onClick={() => {
                if (voiceEnabled) {
                stop();
                setVoiceEnabled(false);
                } else {
                setVoiceEnabled(true);
                speak("Spoken replies enabled.");
                }
            }}
            >
            {voiceEnabled ? "Disable spoken replies" : "Enable spoken replies"}
            </button>

            {speaking && (
            <button type="button" onClick={stop}>
                Stop speaking
            </button>
            )}

            {answer && !speaking && (
            <button
                type="button"
                disabled={busy || audioBusy}
                onClick={() => speak(answer)}
            >
                Read reply aloud
            </button>
            )}
        </div>
        )}

        {speechError && <p role="alert">{speechError}</p>}
    {answer && (
        <div className="assistant-answer" aria-live="polite">
        {answer}
        </div>
    )}

      {presentedId && (
        <p>
          Review the proposal above. Reply to confirm, change,
          or cancel it.
        </p>
      )}

        <RecordButton
        user={user}
        disabled={busy || speaking}
        onTranscript={setMessage}
        onBusyChange={setAudioBusy}
        />
      <form onSubmit={send}>
        <label htmlFor="message">Your message</label>

        <textarea
          id="message"
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="What events do I have tomorrow?"
          maxLength={4000}
          rows={3}
          disabled={busy || audioBusy || speaking}
          required
        />

        <button
          type="submit"
          disabled={busy || audioBusy || speaking || !message.trim()}
        >
          {busy ? "Thinking…" : "Send"}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}
    </section>
  );
}