"""Tepsi: menü düzeni ve çalışırken dil değiştirme."""

import types
import unittest
from unittest import mock

from scyrox_sapp import app as A
from scyrox_sapp import i18n
from tests.test_window import FakeService


class TrayTests(unittest.TestCase):
    def setUp(self):
        self.svc = FakeService()
        self.svc.scan = lambda: None
        self.svc.stop = lambda: None
        self.svc.start = lambda fallback_scan=False: None
        with mock.patch.object(A, "DeviceService", lambda: self.svc), \
                mock.patch.object(A, "HotplugWatcher", lambda cb: types.SimpleNamespace(active=True)):
            self.tray = A.Tray(A.QApplication.instance())
        self.tray._on_device(self.svc.identity)
        self.old_lang = i18n.LANG

    def tearDown(self):
        i18n.use(self.old_lang)
        if self.tray.window is not None:
            self.tray.window.quitting = True
            self.tray.window.close()
        self.tray.tray.hide()

    def texts(self):
        return [a.text() for a in self.tray.menu.actions() if a.isVisible() and not a.isSeparator()]

    def test_menu_order(self):
        t = self.texts()
        self.assertEqual(t[:3], ["Scyrox V6s Beyaz", "Pil: -", "Pili ölç"])
        self.assertEqual(t[-2:], ["Tüm ayarlar", "Çıkış"])

    def test_language_change_keeps_pending_changes(self):
        self.tray.open_settings()
        self.tray.window.dpi_cards[0].spin.setValue(500)
        with mock.patch.object(i18n.prefs, "set_language") as saved:
            self.tray._change_language("de")
        saved.assert_called_once_with("de")
        self.assertIn("Akku prüfen", self.texts())
        w = self.tray.window
        self.assertEqual(w.apply_btn.text(), "Übernehmen")
        self.assertEqual(w.dpi_cards[0].spin.value(), 500)
        self.assertTrue(w.apply_btn.isEnabled())

    def test_automatic_language_follows_system(self):
        with mock.patch.object(i18n.prefs, "set_language"), \
                mock.patch.object(i18n, "system_language", return_value="ja"):
            i18n.choose(None)
        self.assertEqual(i18n.LANG, "ja")


if __name__ == "__main__":
    unittest.main()
