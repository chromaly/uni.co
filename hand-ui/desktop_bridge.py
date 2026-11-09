import json
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from uuid import uuid4

from PySide6.QtCore import (
    QObject, QFile, QIODevice, QTimer, QUrlQuery, Slot, Signal
)

from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineScript

from desktop_login import run_google_login

class DesktopBridge(QObject):
    planner_token_ready = Signal(str)
    planner_token_failed = Signal(str)

    def __init__(self, browser):
        super().__init__(browser)

        self._planner_token_request = None

        self.browser = browser
        self._desktop_session = False
        self.browser.urlChanged.connect(self._track_desktop_page)
        self._track_desktop_page(self.browser.url())
        self._busy = False
        self._client_file = str(
            Path(__file__).resolve().parent
            / "config"
            / "google-desktop-client.json"
        )
        self._results = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check_login_result)

    @staticmethod
    def _planner_url(url):
        return (
            url.scheme() == "https"
            and url.host() == "chromaly.github.io"
            and url.port(-1) in (-1, 443)
            and url.path().startswith("/planner.io/")
        )

    def _track_desktop_page(self, url):
        # React navigation can drop the query string without changing the
        # initialized desktop page. Leaving this site's scope revokes trust.
        if not self._planner_url(url):
            self._desktop_session = False
        elif QUrlQuery(url).queryItemValue("embed") == "uni":
            self._desktop_session = True

    def trusted_page(self):
        url = self.browser.url()
        self._track_desktop_page(url)
        return self._planner_url(url) and self._desktop_session

    @Slot()
    def startSignIn(self):
        if self._busy or not self.trusted_page():
            return

        # Prevent duplicate attempts, including during file selection.
        self._busy = True

        if not Path(self._client_file).is_file():
            self._busy = False
            print("Desktop OAuth configuration is missing.")
            return

        self._results = Queue(maxsize=1)

        Thread(
            target=run_google_login,
            args=(self._client_file, self._results),
            daemon=True
        ).start()

        self._timer.start(100)

    def check_login_result(self):
        try:
            status, value = self._results.get_nowait()
        except Empty:
            return

        self._timer.stop()

        if status == "error":
            self._busy = False
            print("Google sign-in failed:", value, flush=True)
            return

        if not self.trusted_page():
            self._busy = False
            print("Sign-in cancelled: planner page changed.")
            return

        # Check the destination again inside the executing page.
        script = """
        (() => {
          if (
            location.origin !== "https://chromaly.github.io" ||
            !location.pathname.startsWith("/planner.io/") ||
            (
              new URLSearchParams(location.search).get("embed") !== "uni" &&
              document.documentElement.dataset.unico !== "true"
            )
          ) {
            return false;
          }

          const signIn = window.uniDesktopSignIn;
          const bridge = window.uniDesktopBridge;

          if (typeof signIn !== "function" || !bridge) {
            return false;
          }

          Promise.resolve()
            .then(() => signIn(__GOOGLE_TOKEN__))
            .then(() => bridge.finishSignIn(true, ""))
            .catch(error => {
              bridge.finishSignIn(
                false,
                String(error.code || "FIREBASE_SIGN_IN_FAILED")
              );
            });

          return true;
        })();
        """

        script = script.replace(
            "__GOOGLE_TOKEN__",
            json.dumps(value)
        )

        self.browser.page().runJavaScript(
            script,
            self.on_sign_in_dispatched
        )

    @Slot(bool, str)
    def finishSignIn(self, success, error_code):
        self._busy = False

        if not self.trusted_page():
            return

        if success:
            print("Planner sign-in completed.", flush=True)
        else:
            print(
                "Planner sign-in failed:",
                error_code,
                flush=True
            )

    def on_sign_in_dispatched(self, accepted):
        if accepted is not True:
            self._busy = False
            print(
                "Sign-in could not reach the planner. "
                "Check that its desktop-auth code is loaded.",
                flush=True
            )

    def request_planner_token(self):
        if self._planner_token_request is not None:
            return

        if not self.trusted_page():
            self.planner_token_failed.emit(
                "Open the planner's trusted desktop page first."
            )
            return

        request_id = uuid4().hex
        self._planner_token_request = request_id

        script = """
        (() => {
        const requestId = __REQUEST_ID__;

        if (
            location.origin !== "https://chromaly.github.io" ||
            !location.pathname.startsWith("/planner.io/") ||
            (
              new URLSearchParams(location.search).get("embed") !== "uni" &&
              document.documentElement.dataset.unico !== "true"
            )
        ) {
            return;
        }

        const bridge = window.uniDesktopBridge;
        const getToken = window.uniDesktopGetPlannerToken;

        if (!bridge) return;

        if (typeof getToken !== "function") {
            bridge.finishPlannerToken(
            requestId, "", "PLANNER_UPDATE_REQUIRED"
            );
            return;
        }

        Promise.resolve()
            .then(() => getToken())
            .then(token => {
            bridge.finishPlannerToken(requestId, token, "");
            })
            .catch(() => {
            bridge.finishPlannerToken(
                requestId, "", "PLANNER_SESSION_UNAVAILABLE"
            );
            });
        })();
        """

        script = script.replace(
            "__REQUEST_ID__",
            json.dumps(request_id),
        )

        self.browser.page().runJavaScript(script)

        QTimer.singleShot(
            15000,
            lambda: self._fail_planner_token(
                request_id,
                "Planner session request timed out.",
            ),
        )

    def _fail_planner_token(self, request_id, message):
        if request_id != self._planner_token_request:
            return

        self._planner_token_request = None
        self.planner_token_failed.emit(message)

    @Slot(str, str, str)
    def finishPlannerToken(self, request_id, token, error):
        if (
            self._planner_token_request is None
            or request_id != self._planner_token_request
        ):
            return

        if not self.trusted_page():
            self._fail_planner_token(
                request_id,
                "Planner page changed during the request.",
            )
            return

        if error or not token:
            self._fail_planner_token(
                request_id,
                error or "Planner returned no session.",
            )
            return

        self._planner_token_request = None
        self.planner_token_ready.emit(token)

def install_desktop_bridge(browser):
    bridge = DesktopBridge(browser)

    channel = QWebChannel(browser.page())
    channel.registerObject("uniDesktop", bridge)
    browser.page().setWebChannel(channel)

    # Inject Qt's bridge library into the remote page.
    resource = QFile(":/qtwebchannel/qwebchannel.js")

    if not resource.open(QIODevice.OpenModeFlag.ReadOnly):
        raise RuntimeError("Could not load Qt WebChannel.")

    source = bytes(resource.readAll()).decode("utf-8")
    resource.close()

    source += """
    if (
      location.origin === "https://chromaly.github.io" &&
      location.pathname.startsWith("/planner.io/") &&
      new URLSearchParams(location.search).get("embed") === "uni" &&
      typeof qt !== "undefined"
    ) {
      new QWebChannel(qt.webChannelTransport, function(channel) {
        window.uniDesktopBridge = channel.objects.uniDesktop;
      });
    }
    """

    script = QWebEngineScript()
    script.setName("uni-desktop-bridge")
    script.setInjectionPoint(
        QWebEngineScript.InjectionPoint.DocumentCreation
    )
    script.setWorldId(
        QWebEngineScript.ScriptWorldId.MainWorld
    )
    script.setRunsOnSubFrames(False)
    script.setSourceCode(source)

    browser.page().scripts().insert(script)

    return channel, bridge
