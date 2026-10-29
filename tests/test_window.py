"""Ayarlar penceresi: değişiklikler yalnızca "Uygula" ile, doğru sırayla yazılır."""

import unittest
from unittest import mock

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from scyrox_sapp import device as d
from scyrox_sapp import protocol as p
from scyrox_sapp.models import lookup, with_color
from scyrox_sapp import app as A
from scyrox_sapp.window import SettingsWindow


def config(**kw):
    values = dict(report_rate=2000, dpi_stages=5, current_dpi=1, dpis=[400, 800, 1600, 3200, 6400, None, None, None],
                  lod=5, debounce=8, motion_sync=1, sleep_time=6, angle_snap=0, ripple=0,
                  performance_state=0, fps_20k=0, angle_tune=0)
    values.update(kw)
    return d.MouseConfig(**values)


class FakeService(QObject):
    device_changed = pyqtSignal(object)
    config_changed = pyqtSignal(object)
    battery_changed = pyqtSignal(object)
    busy_changed = pyqtSignal(bool)
    message = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        self.identity = d.Identity(62, 17, 5, lookup(62, 17))
        self.dev = mock.Mock(ref=d.DeviceRef(b"x", 0xF517, "Scyrox Turbo 8k dongle"))
        self.config = config()
        self.battery = None
        self.applied = []

    def detected_color(self):
        return "white"

    def set_color(self, color):
        # Gerçek servis gibi: model rengini değiştir, iki sinyali de yay.
        self.identity.model = with_color(self.identity.model, color)
        self.device_changed.emit(self.identity)
        self.config_changed.emit(self.config)

    def refresh(self, quiet=False, on_done=None):
        self.refresh_done = on_done        # testte okuma sonucunu elle bildirmek için

    def query_battery(self):
        pass

    def apply(self, label, action, on_fail=None):
        self.applied.append((label, action))
        self.on_fail = on_fail


class Recorder:
    """Uygulanan eylemin fareye hangi sırayla ne yazacağını kaydeder."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return lambda *args: self.calls.append((name, *args))


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.svc = FakeService()
        self.w = SettingsWindow(self.svc)
        self.w._on_config(self.svc.config)

    def run_apply(self):
        self.w.apply_btn.click()
        self.assertEqual(len(self.svc.applied), 1)
        rec = Recorder()
        self.svc.applied[0][1](rec)
        return rec.calls

    def test_nothing_is_written_until_apply(self):
        self.assertFalse(self.w.apply_btn.isEnabled())
        self.w.rate_group.button(1000).setChecked(True)
        self.w.dpi_cards[2].spin.setValue(1750)
        self.assertEqual(self.svc.applied, [])
        self.assertTrue(self.w.apply_btn.isEnabled())
        self.assertEqual(self.run_apply(), [("set_report_rate", 1000), ("set_dpi_value", 2, 1750)])

    def test_discard_restores_mouse_values(self):
        self.w.dpi_cards[0].spin.setValue(500)
        self.w.discard_btn.click()
        self.assertEqual(self.w.dpi_cards[0].spin.value(), 400)
        self.assertFalse(self.w.apply_btn.isEnabled())

    def test_changing_back_clears_pending(self):
        self.w.dpi_cards[0].spin.setValue(500)
        self.w.dpi_cards[0].spin.setValue(400)
        self.assertFalse(self.w.apply_btn.isEnabled())

    def test_fewer_stages_moves_active_stage(self):
        self.w.dpi_cards[4].selected.emit(4)        # 5. kademe aktif
        self.w.stage_spin.setValue(3)
        self.assertEqual(self.w._active_stage, 2)
        self.assertEqual(self.run_apply(), [("set_dpi_stages", 3), ("set_current_dpi", 2, 3)])

    def test_pending_survives_refresh(self):
        self.w.dpi_cards[0].spin.setValue(500)
        self.svc.config = config(report_rate=1000)     # tepsi menüsünden değişti
        self.svc.config_changed.emit(self.svc.config)
        self.assertEqual(self.w.dpi_cards[0].spin.value(), 500)
        self.assertEqual(self.w.rate_group.checkedId(), 1000)
        self.assertEqual(self.run_apply(), [("set_dpi_value", 0, 500)])

    def test_competitive_before_20k_after_confirm(self):
        self.w.checks["perf"].setChecked(True)
        self.w.checks["fps"].setChecked(True)
        with mock.patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            calls = self.run_apply()
        self.assertEqual(calls, [("set_flag", p.Addr.PERFORMANCE_STATE, True),
                                 ("set_flag", p.Addr.FPS_20K, True)])

    def test_declined_warning_writes_nothing(self):
        self.w.debounce_spin.setValue(2)
        with mock.patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No):
            self.w.apply_btn.click()
        self.assertEqual(self.svc.applied, [])
        self.assertTrue(self.w.apply_btn.isEnabled())   # taslak duruyor

    def test_quit_closes_window_even_with_pending(self):
        self.w.show()
        self.w.dpi_cards[0].spin.setValue(500)
        self.w.quitting = True                      # tepsi "Çıkış" soruyu zaten sordu
        self.assertTrue(self.w.close())
        self.assertFalse(self.w.isVisible())

    def test_close_without_changes_just_hides(self):
        self.w.show()
        self.assertTrue(self.w.confirm_close())
        self.assertFalse(self.w.close())           # kapanmaz, tepside kalır
        self.assertFalse(self.w.isVisible())

    def test_status_does_not_move_the_layout(self):
        self.w.show()
        A.QApplication.processEvents()
        body_y = self.w.scroll.geometry().y()
        apply_y = self.w.apply_btn.geometry().y()
        for step in (lambda: self.w._on_busy(True),
                     lambda: self.w._on_busy(False),
                     lambda: self.w._on_message("Polling rate 1000 Hz", "ok", "apply"),
                     lambda: self.w._on_message("Doğrulama başarısız " * 20, "error", "apply")):
            step()
            A.QApplication.processEvents()
            self.assertEqual(self.w.scroll.geometry().y(), body_y)
            self.assertEqual(self.w.apply_btn.geometry().y(), apply_y)
        self.assertEqual(self.w.status_lbl.text(), "Uygulanamadı")   # kısa sonuç
        self.assertIn("Doğrulama başarısız", self.w.status_lbl.toolTip())   # ayrıntı ipucunda

    def test_header_and_polling_note(self):
        self.assertEqual(self.w.sub_lbl.text(), "Kablosuz  ·  Scyrox Turbo 8k dongle")
        self.assertEqual(self.w.rate_box.note.text(), "en fazla 8000 Hz")

    def test_app_settings_menu_has_language_and_color(self):
        titles = [a.text() for a in self.w.app_menu.actions()]
        self.assertEqual(titles, ["Dil", "Fare ikonu rengi", "Windows açılınca başlat", "Güncellemeleri otomatik denetle", "",
                                  "Güncellemeleri denetle", "Tanıtımı göster"])
        self.assertTrue(self.w.autostart_act.isCheckable())
        colors = [a.text() for a in self.w.color_menu.actions()]
        self.assertIn("Pembe", colors)

    def test_short_status_texts(self):
        self.w._start("Uygulanıyor…")
        self.w._on_busy(True)
        self.assertEqual(self.w.busy_lbl.text(), "Uygulanıyor…")
        self.w._on_busy(False)
        self.w._on_message("Polling rate 1000 Hz: Fare kapalı ya da uyku modunda.", "offline", "apply")
        self.assertEqual(self.w.status_lbl.text(), "Uygulanamadı")   # uykuda olduğundan emin değiliz
        self.w._on_message("Polling rate 1000 Hz", "ok", "apply")
        self.assertEqual(self.w.status_lbl.text(), "Uygulandı")
        self.w._on_message("Fare kapalı", "offline", "refresh")
        self.assertEqual(self.w.status_lbl.text(), "Yenilenemedi")
        self.w._on_busy(True)                    # pencere dışından başlayan iş
        self.assertEqual(self.w.busy_lbl.text(), "İşleniyor…")

    def test_factory_reset_has_its_own_texts(self):
        with mock.patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
            self.w.reset_btn.click()
        self.svc.message.emit("Fabrika ayarları", "ok", "apply")
        self.assertEqual(self.w.status_lbl.text(), "Sıfırlandı")
        self.svc.message.emit("Polling rate 1000 Hz", "ok", "apply")   # sonraki iş normal uygulama
        self.assertEqual(self.w.status_lbl.text(), "Uygulandı")

    def test_refresh_spins_only_while_busy(self):
        self.w._refresh()
        self.w._on_busy(True)
        self.assertEqual(self.w.busy_lbl.text(), "Yenileniyor…")
        self.assertTrue(self.w._spin_timer.isActive())
        self.w._on_busy(False)
        self.assertFalse(self.w._spin_timer.isActive())

    def test_failed_apply_refreshes_automatically(self):
        self.w.rate_group.button(1000).setChecked(True)
        self.w.apply_btn.click()
        with mock.patch.object(self.svc, "refresh") as refresh:
            self.svc.on_fail()                    # servis: yazma başarısız
        refresh.assert_called_once()
        self.assertTrue(self.w.apply_btn.isEnabled())   # taslak duruyor, tekrar denenebilir

    def test_sensor_labels_have_no_parentheses(self):
        for chk in self.w.checks.values():
            self.assertNotIn("(", chk.text())
        self.assertEqual(self.w.checks["fps"].toolTip(), "Yalnızca rekabet modu açıkken kullanılabilir.")

    def test_failed_status_does_not_stick_after_refresh(self):
        # Kullanıcının senaryosu: uykudaki fareye ayar uygula -> uygulanamadı,
        # otomatik (sessiz) yenileme de başarısız; fareyi uyandırıp Yenile ->
        # "Yenilendi" (ayarlar uygulanmış izlenimi vermesin).
        self.w.rate_group.button(1000).setChecked(True)
        self.w.apply_btn.click()
        self.svc.message.emit("Polling rate 1000 Hz: uyku", "offline", "apply")
        with mock.patch.object(self.svc, "refresh", wraps=self.svc.refresh) as refresh:
            self.svc.on_fail()                     # otomatik yenileme sessiz…
        self.assertTrue(refresh.call_args.kwargs["quiet"])
        self.svc.refresh_done(False)               # …ve başarısız
        self.assertEqual(self.w.status_lbl.text(), "Uygulanamadı")
        self.w.refresh_btn.click()                 # fare uyandı, Yenile
        self.svc.refresh_done(True)
        self.assertEqual(self.w.status_lbl.text(), "Yenilendi")
        self.assertTrue(self.w.apply_btn.isEnabled())   # değişiklik hâlâ uygulanmadı
        self.w.refresh_btn.click()                 # tekrar Yenile
        self.svc.refresh_done(True)
        self.assertEqual(self.w.status_lbl.text(), "Yenilendi")

    def test_successful_retry_keeps_failed_apply_visible(self):
        self.svc.message.emit("Polling rate 1000 Hz: bağlantı", "error", "apply")
        self.w._refresh("retry")
        self.svc.refresh_done(True)                # anlık sorunmuş, okuma başarılı
        self.assertEqual(self.w.status_lbl.text(), "Uygulanamadı")   # ama ayar yazılamadı

    def test_opening_window_clears_old_failure(self):
        self.svc.message.emit("eski hata", "error", "refresh")
        self.w._refresh("open")
        self.svc.refresh_done(True)
        self.assertEqual(self.w.status_lbl.text(), "")

    def test_icon_color_change_applies_without_apply_button(self):
        self.svc.set_color("black")
        self.assertEqual(self.w.title_lbl.text(), "Scyrox V6s Siyah")
        self.assertFalse(self.w.apply_btn.isEnabled())       # fare ayarı değişmedi
        self.assertEqual(self.w.rate_group.checkedId(), 2000)
        self.assertEqual(self.w.lod_combo.currentData(), 5)

    def test_icon_color_change_keeps_pending_mouse_changes(self):
        self.w.dpi_cards[0].spin.setValue(500)
        self.svc.set_color("blue")
        self.assertEqual(self.w.dpi_cards[0].spin.value(), 500)
        self.assertEqual(self.run_apply(), [("set_dpi_value", 0, 500)])   # yalnızca DPI

    def test_clicking_a_card_makes_it_active(self):
        from PyQt6.QtCore import QPoint
        from PyQt6.QtTest import QTest
        card = self.w.dpi_cards[3]
        QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=QPoint(card.width() // 2, card.height() - 4))
        self.assertEqual(self.w._active_stage, 3)
        self.assertTrue(card.active and not self.w.dpi_cards[1].active)
        self.assertEqual(self.run_apply(), [("set_current_dpi", 3, 5)])

    def press(self, button):
        from PyQt6.QtTest import QTest
        QTest.mousePress(button, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(button, Qt.MouseButton.LeftButton)

    def test_card_arrows_step_by_50(self):
        card = self.w.dpi_cards[0]
        self.press(card.up)
        self.assertEqual(card.spin.value(), 450)
        self.press(card.down)
        self.press(card.down)
        self.assertEqual(card.spin.value(), 350)
        self.assertFalse(card._hold_timer.isActive())          # bırakınca durdu

    def test_arrows_leave_no_highlighted_numbers(self):
        for card in self.w.dpi_cards[:3]:
            self.press(card.up)
        for card in self.w.dpi_cards:
            self.assertFalse(card.spin.lineEdit().hasSelectedText())

    def test_single_click_on_number_selects_card(self):
        from PyQt6.QtTest import QTest
        self.w.show()
        card = self.w.dpi_cards[4]
        QTest.mouseClick(card.spin.lineEdit(), Qt.MouseButton.LeftButton)
        self.assertEqual(self.w._active_stage, 4)
        self.assertFalse(card.spin.editing())          # yazma moduna geçmedi
        self.assertFalse(card.spin.hasFocus())

    def test_double_click_edits_number(self):
        from PyQt6.QtTest import QTest
        self.w.show()
        self.w.activateWindow()
        card = self.w.dpi_cards[0]
        QTest.mouseDClick(card.spin.lineEdit(), Qt.MouseButton.LeftButton)
        self.assertTrue(card.spin.editing())
        QTest.keyClicks(card.spin.lineEdit(), "1250")
        QTest.keyClick(card.spin.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual(card.spin.value(), 1250)
        self.assertFalse(card.spin.editing())          # Enter düzenlemeyi kapattı

    def test_wheel_does_not_change_value_unless_editing(self):
        from PyQt6.QtCore import QPoint, QPointF
        from PyQt6.QtGui import QWheelEvent
        spin = self.w.dpi_cards[0].spin
        ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton,
                         Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        A.QApplication.sendEvent(spin, ev)
        self.assertEqual(spin.value(), 400)
        self.assertFalse(ev.isAccepted())               # pencere kaydırmaya devam eder

    def hold(self, card, start, ticks):
        """Basılı tutmayı canlandır: basış, 0.75 sn'deki adım, ardından `ticks` tik."""
        card.spin.setValue(start)
        with mock.patch.object(card, "_still_held", return_value=True):
            card.hold_begin(1)
            values = [card.spin.value()]
            card._hold_next()                       # 0.75 sn
            values.append(card.spin.value())
            for _ in range(ticks):                  # 1 sn'den itibaren her 0.25 sn
                card._hold_next()
                values.append(card.spin.value())
        card.hold_end()
        return values

    def test_holding_follows_the_timeline(self):
        v = self.hold(self.w.dpi_cards[0], 800, 8 + 8 + 2)
        self.assertEqual(v[:2], [850, 900])                       # basınca, 0.75 sn
        self.assertEqual(v[2:10], list(range(950, 1301, 50)))     # 2 sn boyunca +50 (toplam 10)
        self.assertEqual(v[10:18], list(range(1400, 2101, 100)))  # sonraki 2 sn +100 (+800)
        self.assertEqual(v[18:], [2200, 2400])                    # sonra +200

    def test_bigger_steps_land_on_round_numbers(self):
        v = self.hold(self.w.dpi_cards[0], 850, 8 + 1)
        self.assertEqual(v[9], 1350)
        self.assertEqual(v[10], 1400)                             # 100'lük adım "00" ile biter

    def test_hold_stops_when_button_released_elsewhere(self):
        card = self.w.dpi_cards[0]
        card.hold_begin(1)
        with mock.patch.object(card, "_still_held", return_value=False):
            card._hold_next()                       # ör. basılıyken Alt+Tab, bırakma olayı gelmedi
        self.assertFalse(card._hold_timer.isActive())
        self.assertEqual(card.spin.value(), 450)    # yalnızca ilk basış

    def test_stage_count_hides_cards(self):
        self.w.stage_spin.setValue(3)
        self.assertEqual([not c.isHidden() for c in self.w.dpi_cards], [True, True, True, False, False])

    def test_after_successful_apply_nothing_pending(self):
        self.w.rate_group.button(1000).setChecked(True)
        self.w.apply_btn.click()
        self.svc.config = config(report_rate=1000)      # servis yeniden okudu
        self.svc.config_changed.emit(self.svc.config)
        self.assertFalse(self.w.apply_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
