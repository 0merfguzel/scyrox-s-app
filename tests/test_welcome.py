"""Tanıtım ekranı: sayfalar, başlangıç seçimi, bir daha kendiliğinden açılmama."""

import unittest
from unittest import mock

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog

from scyrox_sapp import welcome as W
from scyrox_sapp.demo import DemoService
from scyrox_sapp.tutorial import TutorialScene


class WelcomeTests(unittest.TestCase):
    def setUp(self):
        patches = [mock.patch.object(W.autostart, "is_enabled", return_value=False),
                   mock.patch.object(W.autostart, "set_enabled", return_value=True),
                   mock.patch.object(W.prefs, "welcome_shown", return_value=False),
                   mock.patch.object(W.prefs, "set_welcome_shown")]
        self.mocks = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        self.dlg = W.WelcomeDialog(QPixmap(10, 10), {})

    def test_five_pages_and_buttons(self):
        self.assertEqual(self.dlg.stack.count(), 5)
        self.assertFalse(self.dlg.back_btn.isEnabled())
        for _ in range(4):
            self.dlg.next_btn.click()
        self.assertEqual(self.dlg.next_btn.text(), "Başla")
        self.assertTrue(self.dlg.autostart_chk.isChecked())   # ilk açılışta önerilen

    def test_get_started_applies_choice(self):
        self.dlg.autostart_chk.setChecked(False)
        for _ in range(5):
            self.dlg.next_btn.click()
        self.assertEqual(self.dlg.result(), QDialog.DialogCode.Accepted)
        self.mocks[1].assert_called_once_with(False)
        self.mocks[3].assert_called_once()

    def test_closing_early_does_not_touch_startup(self):
        self.dlg.reject()                                      # pencere kapatıldı
        self.mocks[1].assert_not_called()                      # başlangıca habersiz eklenmez
        self.mocks[3].assert_called_once()                     # ama bir daha kendiliğinden açılmaz


class TutorialTests(unittest.TestCase):
    def setUp(self):
        self.model = DemoService().identity.model
        rows = {"rate": QRect(0, 100, 200, 24), "settings": QRect(0, 220, 200, 24)}
        self.menu = QPixmap(220, 280)
        self.scenes = {k: TutorialScene(k, self.model, self.menu, rows, QPixmap(400, 300))
                       for k in ("battery", "menu", "settings")}

    def test_battery_shows_after_left_click(self):
        s = self.scenes["battery"]
        self.assertFalse(s.state(1000)["battery"])
        self.assertEqual(s.state(1000)["click"], ("left", 1600))
        self.assertTrue(s.state(2500)["battery"])
        self.assertFalse(s.state(5000)["battery"])          # döngü başına dönmeden ikon geri gelir

    def test_menu_opens_on_right_click_and_cursor_reaches_row(self):
        s = self.scenes["menu"]
        self.assertEqual(s.state(0)["menu"], 0)
        self.assertEqual(s.state(1600)["click"][0], "right")
        self.assertEqual(s.state(3000)["menu"], 1)
        self.assertEqual(s.state(4000)["hover"], "rate")
        self.assertEqual(s.state(4000)["cursor"], s.row_center("rate"))

    def test_settings_window_follows_menu_click(self):
        s = self.scenes["settings"]
        self.assertEqual(s.state(2200)["menu"], 1)
        self.assertEqual(s.state(2700)["hover"], "settings")
        self.assertEqual(s.state(5000)["menu"], 0)
        self.assertEqual(s.state(5000)["window"], 1)
        self.assertLess(s.state(7700)["window"], 0.1)
        self.assertTrue(s.menu_rect.contains(s.row_center("settings")))

    def test_app_settings_menu_opens_from_button(self):
        s = TutorialScene("app", self.model, QPixmap(200, 160), {"autostart": QRect(0, 50, 200, 24)},
                          QPixmap(480, 600), QRect(10, 560, 120, 26))
        self.assertTrue(s.window_rect.contains(s.btn_c))
        self.assertEqual(s.state(1500)["cursor"], s.btn_c)
        self.assertEqual(s.state(1500)["menu"], 0)
        self.assertEqual(s.state(3000)["menu"], 1)
        self.assertLess(s.menu_rect.bottom(), s.btn_rect.top())     # menü düğmenin üstünde
        self.assertEqual(s.state(4000)["hover"], "autostart")

    def test_timer_runs_only_while_visible(self):
        s = self.scenes["battery"]
        self.assertFalse(s._timer.isActive())
        s.show()
        self.assertTrue(s._timer.isActive())
        s.hide()
        self.assertFalse(s._timer.isActive())

    def test_frames_paint(self):
        s = self.scenes["settings"]
        for t in range(0, s.LENGTH["settings"], 250):
            s.time_override = t
            self.assertFalse(s.grab().isNull())


if __name__ == "__main__":
    unittest.main()
