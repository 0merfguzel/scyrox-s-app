"""Hoş geldin ekranındaki görüntüler için örnek fare (gerçek cihaza dokunmaz).

Menü ve ayarlar penceresi bu servisle o an çizilir; böylece görüntüler seçili
dil ve Windows teması neyse onunla aynıdır.
"""

from __future__ import annotations

from types import SimpleNamespace

from PyQt6.QtCore import QObject, pyqtSignal

from . import device as d
from .models import lookup


class DemoService(QObject):
    device_changed = pyqtSignal(object)
    config_changed = pyqtSignal(object)
    battery_changed = pyqtSignal(object)
    busy_changed = pyqtSignal(bool)
    message = pyqtSignal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self.identity = d.Identity(62, 17, 5, lookup(62, 17))          # V6s Beyaz, 8K dongle
        self.dev = SimpleNamespace(ref=d.DeviceRef(b"demo", 0xF517, "Scyrox Turbo 8K Dongle"))
        self.config = d.MouseConfig(
            report_rate=2000, dpi_stages=5, current_dpi=1,
            dpis=[400, 800, 1600, 3200, 6400, None, None, None], lod=2, debounce=8,
            motion_sync=1, sleep_time=6, angle_snap=0, ripple=0, performance_state=0,
            fps_20k=0, angle_tune=0)
        self.battery = d.Battery(85, False, 4046)

    # SettingsWindow / Tray'in kullandığı arayüz; hepsi etkisiz.
    def detected_color(self):
        return self.identity.model.color

    def set_color(self, _color) -> None:
        pass

    def refresh(self, quiet: bool = False, on_done=None) -> None:
        pass

    def query_battery(self) -> None:
        pass

    def apply(self, _label, _action, on_fail=None) -> None:
        pass

    def scan(self) -> None:
        pass
