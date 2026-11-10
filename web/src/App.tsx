import { useEffect, useState } from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut,
} from "firebase/auth";
import type { User } from "firebase/auth";

import { auth, googleProvider } from "./firebase";

import AssistantChat from "./AssistantChat";
import HeadphoneTest from "./HeadphoneTest";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    return onAuthStateChanged(
      auth,
      (currentUser) => {
        setUser(currentUser);
        setReady(true);
      },
      () => {
        setError("Could not check your sign-in. Reload to retry.");
        setReady(true);
      },
    );
  }, []);

  async function handleAuth() {
    setBusy(true);
    setError("");

    try {
      if (user) {
        await signOut(auth);
      } else {
        await signInWithPopup(auth, googleProvider);
      }
    } catch {
      setError(
        "Sign-in or sign-out failed. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return <main>Checking sign-in…</main>;
  }

  return (
    <main>
      <h1>Your assistant</h1>

      <p>
        {user
          ? `Signed in as ${user.displayName ?? user.email ?? "you"}.`
          : "Sign in with the Google account you use for Planner."}
      </p>

      <button
        type="button"
        onClick={handleAuth}
        disabled={busy}
      >
        {busy
          ? "Please wait…"
          : user
            ? "Sign out"
            : "Continue with Google"}
      </button>

      {error && <p role="alert">{error}</p>}
      {user && <HeadphoneTest key={user.uid} user={user}/>}
      {user && <AssistantChat key={user.uid} user={user} />}
    </main>
  );
}