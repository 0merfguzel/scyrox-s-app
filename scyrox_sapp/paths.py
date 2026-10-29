"""Uygulama veri klasörü: %APPDATA%\\ScyroxSApp (ayarlar, hata kaydı).

Programın kurulduğu yer (C:\\Program Files\\Scyrox S-App) burada değil, kurulum
tarifinde belirlenir: packaging/ScyroxSApp.iss. Ayarlar her kullanıcının kendi
klasöründe durur; Program Files'a normal kullanıcı yazamaz.
"""

from __future__ import annotations

import os

DIR_NAME = "ScyroxSApp"


def data_dir(*parts: str) -> str:
    # APPDATA her Windows oturumunda tanımlıdır; yoksa (örn. alışılmadık bir ortam) ev klasörü
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, DIR_NAME, *parts)
    os.makedirs(path, exist_ok=True)
    return path
