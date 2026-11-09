import secrets

from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google_auth_oauthlib.flow import InstalledAppFlow


def run_google_login(client_file, results):
    try:
        nonce = secrets.token_urlsafe(32)

        flow = InstalledAppFlow.from_client_secrets_file(
            client_file,
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
                "Opening Google sign-in..."
            ),
            success_message="You can return to uni.co.",
            nonce=nonce,
            prompt="select_account",
        )

        if not credentials.id_token:
            raise RuntimeError("Missing Google ID token.")

        identity = id_token.verify_oauth2_token(
            credentials.id_token,
            Request(),
            audience=flow.client_config["client_id"],
        )

        if identity.get("nonce") != nonce:
            raise RuntimeError("Sign-in response mismatch.")

        results.put(("success", credentials.id_token))

    except Exception as error:
        # Never put credentials or full responses in logs.
        results.put(("error", type(error).__name__))