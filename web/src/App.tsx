import { useEffect, useState } from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut,
} from "firebase/auth";
import type { User } from "firebase/auth";

import { auth, googleProvider } from "./firebase";

import AssistantChat from "./AssistantChat";

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
      <header className="app-header">
       <div className="header-content">
          <h1>uni.co</h1>
          <p>Your very own personal assistant. So cute.</p>

          <div className="account-row">
            <p>
              {user
                ? user.displayName ?? user.email
                : "Your day, a little more connected."}
            </p>

            {user && (
              <button
                className="quiet-button"
                type="button"
                onClick={handleAuth}
                disabled={busy}
              >
                {busy ? "Please wait…" : "Sign out"}
              </button>
            )}
          </div>
        </div>
      </header>

      {!user && (
        <section className="sign-in">
          <h2>A little help, whenever you need it.</h2>
          <p>Sign in to connect to your assistant.</p>

          <button
            type="button"
            onClick={handleAuth}
            disabled={busy}
          >
            {busy ? "Signing in…" : "Continue with Google"}
          </button>
        </section>
      )}

      {error && <p role="alert">{error}</p>}

      {user && <AssistantChat key={user.uid} user={user} />}
    </main>
  );
}