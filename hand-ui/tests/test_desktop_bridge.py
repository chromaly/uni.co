"""No browser or network is opened by these trust-boundary checks."""
import sys
import unittest
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QObject, QUrl, Signal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desktop_bridge import DesktopBridge


class Browser(QObject):
    urlChanged = Signal(QUrl)

    def __init__(self, url):
        super().__init__()
        self.current = QUrl(url)

    def url(self):
        return self.current

    def navigate(self, url):
        self.current = QUrl(url)
        self.urlChanged.emit(self.current)


class DesktopBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QCoreApplication.instance() or QCoreApplication([])

    def test_internal_notes_navigation_keeps_initialized_desktop_session(self):
        browser = Browser('https://chromaly.github.io/planner.io/?embed=uni')
        bridge = DesktopBridge(browser)
        self.assertTrue(bridge.trusted_page())
        for route in ('notes', 'reminders', 'settings', ''):
            browser.navigate('https://chromaly.github.io/planner.io/' + route)
            self.assertTrue(bridge.trusted_page())

    def test_plain_website_does_not_start_a_desktop_session(self):
        browser = Browser('https://chromaly.github.io/planner.io/notes')
        bridge = DesktopBridge(browser)
        self.assertFalse(bridge.trusted_page())

    def test_leaving_scope_revokes_session_even_when_returning_without_marker(self):
        for destination in (
            'https://example.com/planner.io/?embed=uni',
            'https://chromaly.github.io/another-project/?embed=uni',
            'http://chromaly.github.io/planner.io/?embed=uni',
            'https://chromaly.github.io:8443/planner.io/?embed=uni',
        ):
            with self.subTest(destination=destination):
                browser = Browser('https://chromaly.github.io/planner.io/?embed=uni')
                bridge = DesktopBridge(browser)
                browser.navigate(destination)
                self.assertFalse(bridge.trusted_page())
                browser.navigate('https://chromaly.github.io/planner.io/notes')
                self.assertFalse(bridge.trusted_page())
                browser.navigate('https://chromaly.github.io/planner.io/?embed=uni')
                self.assertTrue(bridge.trusted_page())


if __name__ == '__main__':
    unittest.main()
