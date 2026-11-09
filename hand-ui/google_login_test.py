import argparse
import secrets

from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import InstalledAppFlow
from urllib.parse import urlencode

import requests

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "client_file",
        help="Path to your downloaded Desktop OAuth client JSON"
    )
    args = parser.parse_args()

    nonce = secrets.token_urlsafe(32)

    flow = InstalledAppFlow.from_client_secrets_file(
        args.client_file,
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ],
        autogenerate_code_verifier=True,
    )

    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        timeout_seconds=180,
        authorization_prompt_message=(
            "Opening Google sign-in in your browser..."
        ),
        success_message=(
            "Google sign-in completed. "
            "You can return to the terminal."
        ),
        nonce=nonce,
        prompt="select_account",
    )

    if not credentials.id_token:
        raise RuntimeError("Google did not return an ID token.")

    # Verify Google's signature, expiry, and intended client.
    identity = id_token.verify_oauth2_token(
        credentials.id_token,
        Request(),
        audience=flow.client_config["client_id"],
    )

    if identity.get("nonce") != nonce:
        raise RuntimeError("Sign-in response did not match this request.")
        # Use the same Firebase project as planner.io.
    
    firebase_api_key = "AIzaSyBLN3fK1oadrrtPy7HLrTFGRGLdyZPVpOw"

    response = requests.post(
        "https://identitytoolkit.googleapis.com/v1/"
        "accounts:signInWithIdp",
        params={"key": firebase_api_key},
        json={
            "requestUri": "http://localhost",
            "postBody": urlencode({
                "id_token": credentials.id_token,
                "providerId": "google.com",
            }),
            "returnSecureToken": True,
        },
        timeout=20,
    )

    firebase_session = response.json()

    if not response.ok:
        message = firebase_session.get("error", {}).get(
            "message", "UNKNOWN_ERROR"
        )

        # Print only the error code, not credentials.
        error_code = message.split()[0].rstrip(":")
        raise RuntimeError(
            f"Firebase sign-in failed: {error_code}"
        )

    if not firebase_session.get("idToken"):
        raise RuntimeError(
            "Firebase did not return a session token."
        )

    print("Firebase sign-in succeeded.")
    print("Firebase user ID:", firebase_session["localId"])
    print("New account:", firebase_session.get("isNewUser", False))
    print("Google sign-in verified successfully.")
    print("Account:", identity.get("email", "Email not provided"))
    print("No tokens were printed or saved.")

if __name__ == "__main__":
    main()