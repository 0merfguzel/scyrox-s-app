"""Windows açılınca başlatma: kullanıcının "Run" kaydı
(HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run). Yönetici izni gerekmez,
yalnızca bu kullanıcıyı etkiler; Windows'un Başlangıç uygulamaları listesinde görünür.
"""

from __future__ import annotations

import os
import sys

try:
    import winreg
except ImportError:   # Windows dışı: özellik kapalı
    winreg = None

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ScyroxSApp"


def command() -> str:
    """Başlangıçta çalıştırılacak komut: exe ise kendisi, geliştirirken pythonw + başlatıcı."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    launcher = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ScyroxSApp.pyw")
    return f'"{pythonw}" "{launcher}"'


def _read() -> str | None:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
            return value
    except OSError:
        return None


def is_enabled() -> bool:
    return _read() is not None


def set_enabled(on: bool) -> bool:
    """Kaydı aç/kapat; başarılıysa True."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def refresh() -> None:
    """Kayıt açıksa yolu güncel tut: exe başka klasöre taşınsa da başlangıç çalışsın."""
    current = _read()
    if current is not None and current != command():
        set_enabled(True)
