import { useEffect, useRef, useState } from "react";
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

  async function sendMessage(
    rawText: string,
    fromRecording = false,
    ) {
    const text = rawText.trim();

    if (
        !text ||
        activeRequest.current ||
        speaking ||
        (audioBusy && !fromRecording)
    ) {
        return;
    }

    // Keep the transcribed request visible if sending fails.
    setMessage(text);

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
    <section className="assistant-chat" aria-label="Voice assistant">
      <RecordButton
        user={user}
        disabled={busy || speaking}
        onTranscript={(text) => {
          void sendMessage(text, true);
        }}
        onBusyChange={setAudioBusy}
        activity={speaking ? "speaking" : busy ? "thinking" : "idle"}
      />

      {supported && (
        <div className="voice-toolbar">
          <button
            type="button"
            aria-pressed={voiceEnabled}
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
            Voice {voiceEnabled ? "on" : "off"}
          </button>

          {speaking ? (
            <button type="button" onClick={stop}>
              Stop speaking
            </button>
          ) : answer ? (
            <button
              type="button"
              disabled={busy || audioBusy}
              onClick={() => speak(answer)}
            >
              Replay reply
            </button>
          ) : null}
        </div>
      )}

      {speechError && <p role="alert">{speechError}</p>}
      {error && <p role="alert">{error}</p>}

      {answer ? (
        <article className="reply-panel">
          <span className="section-label">Latest reply</span>

          <div className="assistant-answer" aria-live="polite">
            {answer}
          </div>

          {presentedId && (
            <p className="proposal-notice">
              Not saved yet. Review the details, then reply to
              confirm, change, or cancel.
            </p>
          )}
        </article>
      ) : (
        <p className="assistant-intro">
          Never forget another meeting again.
        </p>
      )}

      <details className="text-composer">
        <summary>Prefer to type?</summary>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void sendMessage(message);
          }}
        >
          <label htmlFor="message">Your message</label>

          <textarea
            id="message"
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="What’s on your mind?"
            maxLength={4000}
            rows={3}
            disabled={busy || audioBusy || speaking}
            required
          />

          <button
            type="submit"
            disabled={
              busy || audioBusy || speaking || !message.trim()
            }
          >
            {busy ? "Thinking…" : "Send message"}
          </button>
        </form>
      </details>
    </section>
  );
}