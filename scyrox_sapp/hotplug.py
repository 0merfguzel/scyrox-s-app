"""Windows'un "HID cihazı takıldı / çıkarıldı" bildirimini dinler.

Sürekli tarama yerine Windows bize haber verir (WM_DEVICECHANGE). Bunun
için görünmez bir pencere, HID cihaz sınıfına RegisterDeviceNotification
ile kaydedilir. Bildirim gelince kısa bir gecikmeyle `on_change` çağrılır
(tek takma işleminde birkaç bildirim art arda gelir).

Windows dışında ya da kayıt başarısız olursa hiçbir şey yapmaz; servis
o durumda zamanlayıcıyla taramaya devam eder.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from .models import VENDOR_ID

WM_DEVICECHANGE = 0x0219
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVTYP_DEVICEINTERFACE = 5
DEVICE_NOTIFY_WINDOW_HANDLE = 0
DEBOUNCE_MS = 300


class _GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


# GUID_DEVINTERFACE_HID {4D1E55B2-F16F-11CF-88CB-001111000030}
_HID_GUID = _GUID(0x4D1E55B2, 0xF16F, 0x11CF, (ctypes.c_ubyte * 8)(0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30))


class _DEV_BROADCAST_DEVICEINTERFACE(ctypes.Structure):
    _fields_ = [("dbcc_size", wintypes.DWORD), ("dbcc_devicetype", wintypes.DWORD),
                ("dbcc_reserved", wintypes.DWORD), ("dbcc_classguid", _GUID),
                ("dbcc_name", wintypes.WCHAR * 1)]


class HotplugWatcher(QAbstractNativeEventFilter):
    def __init__(self, on_change: Callable[[], None]) -> None:
        super().__init__()
        self.active = False
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(on_change)
        if sys.platform != "win32":
            return
        self._window = QWidget()          # hiç gösterilmez; sadece pencere tanıtıcısı için
        hwnd = int(self._window.winId())
        flt = _DEV_BROADCAST_DEVICEINTERFACE()
        flt.dbcc_size = ctypes.sizeof(flt)
        flt.dbcc_devicetype = DBT_DEVTYP_DEVICEINTERFACE
        flt.dbcc_classguid = _HID_GUID
        register = ctypes.windll.user32.RegisterDeviceNotificationW
        register.restype = wintypes.HANDLE
        register.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        self._hwnd = hwnd
        self._handle = register(hwnd, ctypes.byref(flt), DEVICE_NOTIFY_WINDOW_HANDLE)
        if self._handle:
            QApplication.instance().installNativeEventFilter(self)
            self.active = True

    def nativeEventFilter(self, event_type, message):  # noqa: N802 - Qt adı
        if event_type == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if (msg.message == WM_DEVICECHANGE and msg.hWnd == self._hwnd
                    and msg.wParam in (DBT_DEVICEARRIVAL, DBT_DEVICEREMOVECOMPLETE)
                    and self._is_ours(msg.lParam)):
                self._timer.start(DEBOUNCE_MS)
        return False, 0

    @staticmethod
    def _is_ours(lparam) -> bool:
        """Klavye, kulaklık gibi başka HID cihazlarında tarama yapma. Cihaz
        yolunda "HID#VID_3554&PID_F517…" geçer."""
        if not lparam:
            return True
        offset = _DEV_BROADCAST_DEVICEINTERFACE.dbcc_name.offset
        name = ctypes.wstring_at(lparam + offset)
        return f"vid_{VENDOR_ID:04x}" in name.lower()
