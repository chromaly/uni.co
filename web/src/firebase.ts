import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const app = initializeApp({
  apiKey: "AIzaSyBLN3fK1oadrrtPy7HLrTFGRGLdyZPVpOw",
  authDomain: "planner-io-f4953.firebaseapp.com",
  projectId: "planner-io-f4953",
  appId: "1:494647055361:web:367fd5a6a3bb144c1f1c00",
});

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();