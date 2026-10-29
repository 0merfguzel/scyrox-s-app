"""Cihaz işlemlerini arayüzü dondurmadan arka planda yürüten katman.

Tüm HID işlemleri tek bir iş parçacığında sırayla çalışır (paralel paket
yok); sonuçlar Qt sinyaliyle arayüz iş parçacığına geri döner.

Boştayken hiçbir şey yapılmaz: zamanlayıcı yok, fareye paket gitmez. Fareyle
yalnızca kullanıcı bir şey yaptığında konuşulur (pil için tıklama, menü veya
pencere açma, ayar değiştirme) ve bir dongle takıldığında modelini öğrenmek
için bir kez el sıkışılır. Takma / çıkarma Windows bildirimiyle gelir.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from . import device as d
from . import prefs
from .i18n import tr
from .models import lookup, with_color

FALLBACK_SCAN_MS = 2000   # yalnızca Windows bildirimi kullanılamıyorsa

UNCHANGED = object()


def error_kind(e: Exception) -> str:
    """Arayüzde kısa mesaj seçmek için: fare uykuda mı, başka bir hata mı."""
    return "offline" if isinstance(e, d.MouseOffline) else "error"


class DeviceService(QObject):
    _deliver = pyqtSignal(object)

    device_changed = pyqtSignal(object)    # Optional[Identity]
    config_changed = pyqtSignal(object)    # Optional[MouseConfig]
    battery_changed = pyqtSignal(object)   # Battery | str (hata)
    busy_changed = pyqtSignal(bool)
    # ayrıntı metni, tür ("ok" | "offline" | "error"), işlem ("apply" | "refresh")
    message = pyqtSignal(str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hid")
        self._deliver.connect(lambda fn: fn())
        self.dev: Optional[d.ScyroxDevice] = None
        self.identity: Optional[d.Identity] = None
        self.config: Optional[d.MouseConfig] = None
        self._stopped = False
        self._pending = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.scan)
        self._scanning = False
        self._rescan = False      # tarama sürerken yeni bildirim geldi
        self._known_paths: frozenset = frozenset()
        self._fallback_scan = False

        self.battery: Optional[d.Battery] = None
        self._battery_busy = False

    # ---- iş kuyruğu -----------------------------------------------------

    def _run(self, job: Callable, ok: Callable = lambda _r: None,
             fail: Optional[Callable[[Exception], None]] = None, busy: bool = True) -> None:
        if self._stopped:
            return  # kapanıyor: kuyruk kapalı
        if busy:
            self._pending += 1
            self.busy_changed.emit(True)

        def done(result=None, error=None):
            if self._stopped:
                return
            if busy:
                self._pending -= 1
                if self._pending == 0:
                    self.busy_changed.emit(False)
            if error is None:
                ok(result)
            elif fail is not None:
                fail(error)
            else:
                self.message.emit(str(error), error_kind(error), "refresh")
            if self.dev is not None and self.dev.lost:
                self.scan()   # bağlantı koptu: dongle çıkarılmış olabilir, hemen bak

        def task():
            try:
                r = job()
            except Exception as e:  # noqa: BLE001 - hatayı arayüze taşıyoruz
                # `e` except bloğundan çıkınca silinir; değeri lambda'ya bağla.
                self._deliver.emit(lambda e=e: done(error=e))
            else:
                self._deliver.emit(lambda: done(result=r))

        self._pool.submit(task)

    # ---- cihaz bulma ----------------------------------------------------

    def start(self, fallback_scan: bool = False) -> None:
        """fallback_scan: Windows takma/çıkarma bildirimi yoksa 2 sn'de bir tara."""
        self._fallback_scan = fallback_scan
        self.scan()

    def stop(self) -> None:
        self._stopped = True
        self._timer.stop()
        if self.dev is not None:
            self._pool.submit(self.dev.close)
        # Kuyruktaki işler iptal edilmez: çıkarken "Uygula" denmişse yazma tamamlansın.
        self._pool.shutdown(wait=True)

    def scan(self) -> None:
        """Takılı cihazları kontrol et. Açılışta, Windows'un USB takıldı /
        çıkarıldı bildirimiyle (hotplug.py) ve bir G/Ç hatasında çağrılır.
        Cihaz listesi değişmediyse fareye hiç paket gönderilmez.

        Birden fazla cihaz varsa (örn. dongle takılıyken fareye kablo da
        takıldıysa) faresi açık olan seçilir; eşitlikte mevcut cihaz kalır."""
        if self._scanning:
            # Bildirimi kaybetme: süren tarama bu takmayı görmemiş olabilir.
            self._rescan = True
            return
        self._scanning = True
        self._rescan = False
        cur, known = self.dev, self._known_paths

        def job():
            refs = d.discover()
            paths = frozenset(r.path for r in refs)
            if cur is not None and not cur.lost and paths == known:
                return paths, UNCHANGED
            best, best_key = None, None
            for ref in refs:
                reuse = cur is not None and not cur.lost and ref.path == cur.ref.path
                dev = cur if reuse else d.ScyroxDevice(ref)
                try:
                    if not reuse:
                        dev.handshake()
                    # Tek cihaz varsa seçim yok; fareye boşuna soru sorma.
                    key = (dev.is_online() if len(refs) > 1 else True, reuse)
                except d.DeviceError:
                    dev.close()
                    continue
                if best_key is None or key > best_key:
                    if best is not None and best is not cur:
                        best.close()
                    best, best_key = dev, key
                elif dev is not cur:
                    dev.close()
            if cur is not None and best is not cur:
                cur.close()
            return paths, best

        def ok(result):
            self._scanning = False
            paths, picked = result
            self._known_paths = paths
            if picked is not UNCHANGED and picked is not self.dev:
                self._set_device(picked)
            self._after_scan()

        def fail(_e):
            self._scanning = False
            self._after_scan()

        self._run(job, ok, fail, busy=False)

    def _after_scan(self) -> None:
        if self._rescan:
            self.scan()
        elif self._fallback_scan:
            self._timer.start(FALLBACK_SCAN_MS)

    def _set_device(self, dev: Optional[d.ScyroxDevice]) -> None:
        self.dev = dev
        self.identity = dev.identity if dev else None
        if self.identity is not None:
            color = prefs.color_override(self.identity.cid, self.identity.mid)
            if color:
                self.identity.model = with_color(self.identity.model, color)
        self.config = None
        self.battery = None
        self.device_changed.emit(self.identity)
        self.config_changed.emit(None)

    def detected_color(self) -> Optional[str]:
        """Farenin kendi bildirdiği renk (elle seçimden bağımsız)."""
        if self.identity is None:
            return None
        return lookup(self.identity.cid, self.identity.mid).color

    def set_color(self, color: Optional[str]) -> None:
        """Rengi elle düzelt; None: farenin bildirdiğine dön. Sadece ikon ve
        adı etkiler, fareye hiçbir şey yazılmaz."""
        ident = self.identity
        if ident is None:
            return
        detected = lookup(ident.cid, ident.mid)
        if color == detected.color:
            color = None
        prefs.set_color_override(ident.cid, ident.mid, color)
        ident.model = with_color(ident.model, color or detected.color)
        self.device_changed.emit(ident)
        self.config_changed.emit(self.config)

    # ---- okuma ----------------------------------------------------------

    def refresh(self, quiet: bool = False, on_done: Optional[Callable[[bool], None]] = None) -> None:
        """Ayarları fareden oku. on_done(başarılı_mı): okuma bitince çağrılır."""
        if self.dev is None:
            self.scan()   # kullanıcı bakıyor: açılışta el sıkışma cevapsız kalmış olabilir
            return
        dev = self.dev

        def ok(cfg):
            if dev is not self.dev:
                return  # okuma sürerken cihaz değişti
            self.config = cfg
            self.config_changed.emit(cfg)
            if on_done is not None:
                on_done(True)

        def fail(e):
            if dev is not self.dev:
                return
            self.config = None
            self.config_changed.emit(None)
            if not quiet:
                self.message.emit(str(e), error_kind(e), "refresh")
            if on_done is not None:
                on_done(False)

        self._run(dev.read_config, ok, fail, busy=not quiet)

    def query_battery(self) -> None:
        """Pili bir kez ölç (kullanıcı istediğinde). Site gibi: önce fare
        açık mı (DEVICE_ONLINE), açıksa BATTERY."""
        if self.dev is None:
            self.battery_changed.emit(tr("No device found (is the dongle plugged in?)"))
            self.scan()
            return
        if self._battery_busy:
            return  # süren ölçümün sonucu bu isteğin de cevabı olur
        self._battery_busy = True
        dev = self.dev

        def ok(b):
            self._battery_busy = False
            if dev is not self.dev:
                return  # bu arada cihaz değişti
            self.battery = b
            self.battery_changed.emit(b)

        def fail(e):
            self._battery_busy = False
            self.battery_changed.emit(str(e))

        self._run(dev.battery, ok, fail, busy=False)

    # ---- yazma ----------------------------------------------------------

    def apply(self, label: str, action: Callable[[d.ScyroxDevice], object],
              on_fail: Optional[Callable[[], None]] = None) -> None:
        """Bir ayarı yaz; ardından tüm ayarlar fareden tekrar okunur.
        on_fail: yazma başarısız olunca çağrılır (pencere fareyi yeniden okur)."""
        if self.dev is None:
            return
        dev = self.dev

        def job():
            action(dev)
            return dev.read_config()

        def ok(cfg):
            if dev is not self.dev:
                return
            self.config = cfg
            self.config_changed.emit(cfg)
            self.message.emit(label, "ok", "apply")

        def fail(e):
            self.message.emit(f"{label}: {e}", error_kind(e), "apply")
            if dev is self.dev:
                self.config_changed.emit(self.config)  # arayüzü eski değere döndür
                if on_fail is not None:
                    on_fail()

        self._run(job, ok, fail)
