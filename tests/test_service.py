"""DeviceService: takma / çıkarma ve fare uyku senaryoları.

Gerçek HID yerine sahte bir "dünya" kullanılır: hangi dongle takılı, fare
açık mı, okuma sürerken cihaz çıkarılırsa ne olur. Servisin iş parçacığı ve
Qt sinyalleri gerçektir.
"""

import threading
import time
import unittest
from unittest import mock

from PyQt6.QtWidgets import QApplication

from scyrox_sapp import device as d
from scyrox_sapp import service as s
from scyrox_sapp.models import lookup

app = QApplication.instance()   # tests/__init__.py oluşturur


class Hardware:
    def __init__(self, path, mid=17, online=True, pid=0xF517):
        self.ref = d.DeviceRef(path, pid, "fake")
        self.mid = mid
        self.online = online
        self.present = True
        self.reads = 0
        self.packets = 0          # fareye/dongle'a giden paket sayısı
        self.gate = None          # threading.Event: okumayı bekletmek için


class FakeDevice:
    """ScyroxDevice ile aynı arayüz; donanım çıkarılınca G/Ç hatası verir."""
    world: dict = {}

    def __init__(self, ref):
        self.ref = ref
        self.hw = self.world[ref.path]
        self.identity = None
        self.lost = False

    def _io(self):
        self.hw.packets += 1
        if not self.hw.present:
            self.lost = True
            raise d.DeviceError("Bağlantı koptu")

    def handshake(self):
        self._io()
        self.identity = d.Identity(62, self.hw.mid, 5, lookup(62, self.hw.mid))
        return self.identity

    def is_online(self):
        self._io()
        return self.hw.online

    def battery(self):
        self._io()
        if not self.hw.online:
            raise d.MouseOffline(d.offline_msg())
        return d.Battery(85, False, 4046)

    def read_config(self):
        if self.hw.gate is not None:
            self.hw.gate.wait(2)
        self._io()
        if not self.hw.online:
            raise d.MouseOffline(d.offline_msg())
        self.hw.reads += 1
        return ("config", self.ref.path, self.hw.reads)

    def close(self):
        pass


def wait_until(pred, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if pred():
            return True
        time.sleep(0.005)
    return pred()


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.world = {}
        FakeDevice.world = self.world
        patches = [
            mock.patch.object(d, "discover",
                              lambda: [h.ref for h in self.world.values() if h.present]),
            mock.patch.object(d, "ScyroxDevice", FakeDevice),
            mock.patch.object(s.prefs, "color_override", lambda cid, mid: None),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.svc = s.DeviceService()
        self.devices, self.configs, self.batteries = [], [], []
        self.svc.device_changed.connect(lambda i: self.devices.append(i and i.model.display_name))
        self.svc.config_changed.connect(self.configs.append)
        self.svc.battery_changed.connect(self.batteries.append)

    def tearDown(self):
        self.svc.stop()

    def plug(self, path, **kw):
        self.world[path] = Hardware(path, **kw)
        return self.world[path]

    def scan(self):
        self.svc.scan()
        self.assertTrue(wait_until(lambda: not self.svc._scanning))

    def settle(self):
        """Kuyruktaki tüm işler bitsin."""
        done = threading.Event()
        self.svc._pool.submit(done.set)
        self.assertTrue(done.wait(3))
        wait_until(lambda: False, 0.05)

    # ---- senaryolar -----------------------------------------------------

    def test_plug_in_after_start(self):
        self.scan()
        self.assertEqual(self.devices, [])
        self.plug("v6s")
        self.scan()
        self.assertEqual(self.devices, ["Scyrox V6s Beyaz"])

    def test_rescan_without_change_emits_nothing(self):
        self.plug("v6s")
        self.scan()
        self.scan()
        self.scan()
        self.assertEqual(self.devices, ["Scyrox V6s Beyaz"])

    def test_unplug_detected_by_io_error_immediately(self):
        hw = self.plug("v6s")
        self.scan()
        self.settle()
        hw.present = False
        self.svc.query_battery()                # kullanıcı tıkladı
        self.assertTrue(wait_until(lambda: self.devices[-1] is None))
        self.assertIsNone(self.svc.dev)

    def test_idle_sends_nothing(self):
        hw = self.plug("v6s")
        self.scan()
        self.settle()
        self.assertEqual(hw.packets, 1)         # takılınca tek el sıkışma
        wait_until(lambda: False, 0.5)
        self.scan()                             # Windows bildirimi, liste aynı
        self.settle()
        self.assertEqual(hw.packets, 1)
        self.assertFalse(self.svc._timer.isActive())
        self.assertEqual(self.batteries, [])

    def test_plug_during_running_scan_is_not_lost(self):
        gate = threading.Event()
        real = d.discover

        def slow_discover():
            refs = real()                       # o anki liste (henüz boş)…
            gate.wait(2)                        # …tarama sürerken dongle takılır
            return refs

        with mock.patch.object(d, "discover", slow_discover):
            self.svc.scan()
            self.plug("v6s")
            self.svc.scan()                     # Windows bildirimi: tarama sürüyor
            gate.set()
            self.assertTrue(wait_until(lambda: self.devices == ["Scyrox V6s Beyaz"]))

    def test_user_action_retries_detection(self):
        hw = self.plug("v6s")
        hw.present = False                      # açılışta cevap vermedi
        self.scan()
        self.assertIsNone(self.svc.dev)
        hw.present = True
        self.svc.query_battery()                # kullanıcı ikona tıkladı
        self.assertTrue(wait_until(lambda: self.devices == ["Scyrox V6s Beyaz"]))

    def test_swap_dongles_between_scans(self):
        hw = self.plug("v6s")
        self.scan()
        hw.present = False
        self.plug("v6", mid=2, pid=0xF5F7)
        self.scan()
        self.assertEqual(self.devices, ["Scyrox V6s Beyaz", "Scyrox V6 Siyah"])

    def test_prefers_device_whose_mouse_is_on(self):
        dongle = self.plug("dongle", online=False)
        self.scan()
        self.assertIs(self.svc.dev.hw, dongle)
        wired = self.plug("wired", online=True, pid=0xF515)
        self.scan()                             # kablo takıldı: fare kablodan açık
        self.assertIs(self.svc.dev.hw, wired)
        wired.present = False
        self.scan()                             # kablo çıktı: dongle'a dön
        self.assertIs(self.svc.dev.hw, dongle)

    def test_result_from_removed_device_is_ignored(self):
        old = self.plug("v6s")
        self.scan()
        self.settle()
        old.gate = threading.Event()            # okuma sürerken…
        self.svc.refresh(quiet=True)            # menü açıldı
        old.present = False                     # …dongle çıkarılır, başkası takılır
        self.plug("v6", mid=2, pid=0xF5F7)
        old.gate.set()
        self.scan()
        self.settle()
        self.assertEqual(self.devices[-1], "Scyrox V6 Siyah")
        self.assertFalse(any(isinstance(c, tuple) and c[1] == "v6s" and c is self.svc.config
                             for c in self.configs))

    def test_apply_while_asleep_reports_offline_kind(self):
        self.plug("v6s", online=False)
        self.scan()
        self.settle()
        messages = []
        self.svc.message.connect(lambda text, kind, op: messages.append(kind))

        def write(dev):
            raise d.MouseOffline(d.offline_msg())
        refreshed = []
        self.svc.apply("Polling rate 1000 Hz", write, on_fail=lambda: refreshed.append(True))
        self.assertTrue(wait_until(lambda: messages == ["offline"] and refreshed == [True]))

    def test_refresh_reports_result(self):
        hw = self.plug("v6s", online=False)
        self.scan()
        self.settle()
        results = []
        self.svc.refresh(on_done=results.append)
        self.assertTrue(wait_until(lambda: results == [False]))
        hw.online = True                            # fare uyandı
        self.svc.refresh(on_done=results.append)
        self.assertTrue(wait_until(lambda: results == [False, True]))

    def test_click_while_asleep_reports_offline(self):
        self.plug("v6s", online=False)
        self.scan()
        self.settle()
        self.svc.query_battery()
        self.assertTrue(wait_until(lambda: self.batteries == [d.offline_msg()]))


if __name__ == "__main__":
    unittest.main()
