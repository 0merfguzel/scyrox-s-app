"""GitHub Releases üzerinden güncelleme kontrolü.

Uygulamanın internete çıktığı tek yer burası. Otomatik kontrol açılışta
yapılır, en fazla günde bir kez (Uygulama ayarlarından kapatılabilir); ayrıca
elle "Güncellemeleri denetle". Yeni sürüm bulunursa kurulum dosyası
(…-Setup.exe) indirilir ve sessiz kurulumla çalıştırılır; kurulum uygulamayı
kapatır, günceller ve yeniden açar.
"""

from __future__ import annotations

import functools
import json
import os
import re
import ssl
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from . import __version__, prefs

REPO = "0merfguzel/scyrox-s-app"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_EVERY_S = 24 * 3600
TIMEOUT_S = 8
SETUP_SUFFIX = "-Setup.exe"


@dataclass
class Release:
    version: str
    page_url: str
    setup_url: Optional[str]      # kurulum dosyası yoksa yalnızca sayfa açılır


def parse_version(text: str) -> tuple[int, ...]:
    """"v2.1.0" -> (2, 1, 0). Sayı olmayan son ekler (ör. -beta) yok sayılır."""
    nums = re.findall(r"\d+", text.split("-")[0])
    return tuple(int(n) for n in nums) or (0,)


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


@functools.cache
def ssl_context() -> ssl.SSLContext:
    """Sertifikayı Windows doğrulasın (truststore; pip de bunu kullanır).

    Python'un kendi doğrulaması yalnızca Windows sertifika deposunda o an
    bulunanlara bakar. Windows kök sertifikaların çoğunu ilk gerektiğinde
    indirir; yeni kurulmuş bir bilgisayarda GitHub'ın kökü henüz yoksa Python
    "unable to get local issuer certificate" der, tarayıcı ise sorunsuz bağlanır.
    truststore doğrulamayı Windows'a yaptırır: eksik kök tarayıcıdaki gibi
    indirilir, iş yeri / antivirüs sertifikaları da tanınır."""
    try:
        import truststore
    except ImportError:                 # kaynaktan çalışırken kurulu değilse
        return ssl.create_default_context()
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"ScyroxSApp/{__version__}",
    })
    with urllib.request.urlopen(req, timeout=TIMEOUT_S, context=ssl_context()) as resp:
        return resp.read()


def latest_release() -> Optional[Release]:
    """En son yayın; henüz yayın yoksa None. Ağ hatası istisna olarak çıkar."""
    try:
        data = json.loads(_get(API_URL))
    except urllib.error.HTTPError as e:
        if e.code == 404:             # depoda henüz yayın yok
            return None
        raise
    tag = data.get("tag_name") or ""
    if not tag or data.get("draft") or data.get("prerelease"):
        return None
    setup = next((a.get("browser_download_url") for a in data.get("assets", [])
                  if str(a.get("name", "")).endswith(SETUP_SUFFIX)), None)
    return Release(tag.lstrip("vV"), data.get("html_url", f"https://github.com/{REPO}/releases"), setup)


def download(url: str) -> str:
    """Kurulum dosyasını geçici klasöre indir, yolunu döndür."""
    req = urllib.request.Request(url, headers={"User-Agent": f"ScyroxSApp/{__version__}"})
    path = os.path.join(tempfile.gettempdir(), os.path.basename(url.split("?")[0]) or "ScyroxSApp-Setup.exe")
    with urllib.request.urlopen(req, timeout=60, context=ssl_context()) as resp, open(path, "wb") as f:
        while chunk := resp.read(1 << 16):
            f.write(chunk)
    if os.path.getsize(path) < 1_000_000:          # yarım kalmış / hatalı indirme
        raise OSError("download too small")
    return path


def can_self_install() -> bool:
    """Kurulumla gelmiş exe kendini güncelleyebilir (yanında kaldırıcı vardır).
    Kurulumsuz (zip) sürümde ve geliştirirken yalnızca yayın sayfası açılır;
    yoksa kurulum ikinci bir kopyayı Program Files'a kurardı."""
    if not getattr(sys, "frozen", False):
        return False
    return os.path.isfile(os.path.join(os.path.dirname(sys.executable), "unins000.exe"))


class UpdateChecker(QObject):
    """Kontrol ve indirme ayrı iş parçacığında; sonuçlar sinyalle gelir.
    Otomatik kontrolün hataları sessizce geçilir, elle istenenler bildirilir."""

    found = pyqtSignal(object)        # Release
    up_to_date = pyqtSignal()
    failed = pyqtSignal(str, str)     # ("check" | "download", hata)
    downloaded = pyqtSignal(str)      # kurulum dosyasının yolu
    _result = pyqtSignal(str, object)

    def __init__(self) -> None:
        super().__init__()
        self._busy = ""               # sürmekte olan iş: "check" | "download" | ""
        self._manual = False
        self._result.connect(self._deliver)

    def auto_check_due(self) -> bool:
        return prefs.auto_update() and time.time() - prefs.last_update_check() >= CHECK_EVERY_S

    def check(self, manual: bool = False) -> None:
        if self._busy == "check":
            # Otomatik denetim sürerken elle istendi: yenisini başlatma, sonucu bildir.
            self._manual = self._manual or manual
            return
        if self._busy:
            return
        self._busy, self._manual = "check", manual
        self._run("check", latest_release)

    def fetch(self, release: Release) -> None:
        if self._busy or not release.setup_url:
            return
        self._busy = "download"
        self._run("download", lambda: download(release.setup_url))

    def _run(self, kind: str, job) -> None:
        def work():
            try:
                self._result.emit(kind, job())
            except Exception as e:  # noqa: BLE001 - ağ yok, zaman aşımı, bozuk cevap…
                self._result.emit(kind + "-error", str(e) or type(e).__name__)
        threading.Thread(target=work, daemon=True).start()

    def _deliver(self, kind: str, value) -> None:
        self._busy = ""
        if kind == "check":
            prefs.set_last_update_check(time.time())
            if value is not None and is_newer(value.version):
                self.found.emit(value)
            elif self._manual:
                self.up_to_date.emit()
        elif kind == "download":
            self.downloaded.emit(value)
        elif kind == "download-error" or self._manual:
            self.failed.emit(kind.split("-")[0], value)
