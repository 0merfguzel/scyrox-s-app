"""HID katmanı: cihaz bulma, okuma, doğrulamalı yazma.

Bütün yazmalar şu sırayla yapılır:
  1. Model tanınıyor mu (bilinmeyen modelde yazma kapalı)?
  2. Değer, sitenin sunduğu seçenekler / aralık içinde mi?
  3. Fare açık ve dongle'a bağlı mı (DEVICE_ONLINE)?
  4. Yaz, sonra aynı adresi geri okuyup birebir aynı mı diye kontrol et.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import hid

from . import protocol as p
from .i18n import tr
from .models import (LOD_OPTIONS, PRODUCT_IDS, SLEEP_OPTIONS, USAGE_PAGE, VENDOR_ID,
                     ModelInfo, lookup)

READ_TIMEOUT_S = 0.6
RETRIES = 3


def offline_msg() -> str:
    return tr("The mouse is off or asleep. Move it and try again.")


class DeviceError(Exception):
    pass


class MouseOffline(DeviceError):
    pass


@dataclass(frozen=True)
class DeviceRef:
    path: bytes
    pid: int
    product: str


def discover() -> list[DeviceRef]:
    """Takılı Scyrox dongle / kablolu fareleri listele. Cihaza paket
    göndermez, sadece işletim sisteminin HID listesine bakar."""
    found = []
    for d in hid.enumerate(VENDOR_ID):
        if d.get("usage_page") == USAGE_PAGE and d["product_id"] in PRODUCT_IDS:
            found.append(DeviceRef(d["path"], d["product_id"], d.get("product_string") or ""))
    return found


@dataclass
class Battery:
    percent: int            # farenin bildirdiği değer (%5'lik adımlar)
    charging: bool
    millivolts: int


@dataclass
class MouseConfig:
    report_rate: Optional[int]
    dpi_stages: Optional[int]
    current_dpi: Optional[int]
    dpis: list[Optional[int]]
    lod: Optional[int]
    debounce: Optional[int]
    motion_sync: Optional[int]
    sleep_time: Optional[int]
    angle_snap: Optional[int]
    ripple: Optional[int]
    performance_state: Optional[int]
    fps_20k: Optional[int]
    angle_tune: Optional[int]          # None => bu fare desteklemiyor
    flash: bytes = field(repr=False, default=b"")
    dpi_flash: bytes = field(repr=False, default=b"")

    @classmethod
    def parse(cls, flash: bytes, dpi_flash: bytes, layout: p.SensorLayout) -> "MouseConfig":
        rp = p.read_pair
        raw_rate = rp(flash, p.Addr.REPORT_RATE)
        dpis = []
        for i in range(p.DPI_SLOTS):
            off = i * layout.slot_size
            dpis.append(layout.decode(dpi_flash[off:off + layout.slot_size]))
        tune = rp(flash, p.Addr.ANGLE_TUNE)
        if tune is not None and rp(flash, p.Addr.ANGLE_TUNE_STATE) is not None:
            tune = tune - 256 if tune >= 128 else tune
        else:
            tune = None
        return cls(
            report_rate=p.RAW_TO_RATE.get(raw_rate) if raw_rate is not None else None,
            dpi_stages=rp(flash, p.Addr.DPI_STAGES),
            current_dpi=rp(flash, p.Addr.CURRENT_DPI),
            dpis=dpis,
            lod=rp(flash, p.Addr.LOD),
            debounce=rp(flash, p.Addr.DEBOUNCE),
            motion_sync=rp(flash, p.Addr.MOTION_SYNC),
            sleep_time=rp(flash, p.Addr.SLEEP_TIME),
            angle_snap=rp(flash, p.Addr.ANGLE_SNAP),
            ripple=rp(flash, p.Addr.RIPPLE),
            performance_state=rp(flash, p.Addr.PERFORMANCE_STATE),
            fps_20k=rp(flash, p.Addr.FPS_20K),
            angle_tune=tune,
            flash=flash,
            dpi_flash=dpi_flash,
        )


@dataclass
class Identity:
    cid: int
    mid: int
    dongle_type: int
    model: ModelInfo

    @property
    def wired(self) -> bool:
        return p.DONGLE_TYPES.get(self.dongle_type, (False, 1000))[0]

    @property
    def max_rate(self) -> int:
        return p.DONGLE_TYPES.get(self.dongle_type, (False, 1000))[1]

    @property
    def rate_options(self) -> list[int]:
        return [r for r in sorted(p.RATE_TO_RAW) if r <= self.max_rate]


class ScyroxDevice:
    def __init__(self, ref: DeviceRef) -> None:
        self.ref = ref
        self._h: Optional[hid.device] = None
        self._lock = threading.RLock()
        self.identity: Optional[Identity] = None
        self.lost = False        # G/Ç hatası oldu: dongle çıkarılmış ya da Windows uykudan dönmüş

    # ---- bağlantı -------------------------------------------------------

    def open(self) -> None:
        with self._lock:
            if self._h is not None:
                return
            h = hid.device()
            try:
                h.open_path(self.ref.path)
            except Exception as e:
                raise DeviceError(tr("Could not open the device: {e}", e=e)) from e
            h.set_nonblocking(True)
            self._h = h

    def close(self) -> None:
        with self._lock:
            if self._h is not None:
                try:
                    self._h.close()
                except Exception:
                    pass
                self._h = None

    def _drain(self) -> None:
        """Bekleyen eski raporları at (örn. açık bir scyrox.net sekmesinin
        cevapları da bize gelir). Beklemez: kuyruk boşsa hemen döner."""
        for _ in range(32):
            if not self._h.read(64, timeout_ms=0):
                break

    def _xfer(self, packet: bytes, match: int = 0) -> p.Response:
        """Paketi gönder; komutu ve [3..3+match) baytları (adres, uzunluk)
        eşleşen, checksum'ı doğru cevabı bekle. Site okumada adres+uzunluk
        (3), yazmada sadece adresin üst baytını (1) karşılaştırıyor; aynısını
        yapıyoruz. Araya giren başka raporlar atlanır."""
        with self._lock:
            self.open()
            last_err: Optional[Exception] = None
            for _ in range(RETRIES):
                try:
                    self._drain()
                    # hidapi yazma hatasında istisna atmaz, -1 döner (örn. dongle çıkarıldı).
                    if self._h.write(packet) < 0:
                        raise OSError("write failed")
                    deadline = time.monotonic() + READ_TIMEOUT_S
                    while time.monotonic() < deadline:
                        data = self._h.read(64, timeout_ms=50)
                        if not data:
                            continue
                        r = p.parse(data)
                        if r is None or not r.valid or r.cmd != packet[1]:
                            continue
                        if r.raw[3:3 + match] != packet[3:3 + match]:
                            continue
                        return r
                    last_err = DeviceError(tr("No response (timed out)"))
                except OSError as e:
                    self.close()
                    self.lost = True
                    raise DeviceError(tr("Connection lost: {e}", e=e)) from e
            raise last_err or DeviceError(tr("Unknown error"))

    # ---- okuma ----------------------------------------------------------

    def handshake(self) -> Identity:
        nonce = bytes(random.randrange(256) for _ in range(4)) + bytes(4)
        r = self._xfer(p.build(p.Cmd.HANDSHAKE, data=nonce))
        cid, mid, typ = r.data[4], r.data[5], r.data[6]
        self.identity = Identity(cid, mid, typ, lookup(cid, mid))
        return self.identity

    def is_online(self) -> bool:
        return self._xfer(p.build(p.Cmd.DEVICE_ONLINE)).data[0] == 1

    def battery(self) -> Battery:
        if not self.is_online():
            raise MouseOffline(offline_msg())
        r = self._xfer(p.build(p.Cmd.BATTERY))
        pct = r.data[0]
        if pct > 100:
            raise DeviceError(tr("Invalid battery response"))
        return Battery(pct, r.data[1] == 1, (r.data[2] << 8) | r.data[3])

    def read_flash(self, start: int, end: int) -> bytes:
        out = bytearray()
        addr = start
        while addr < end:
            n = min(p.MAX_CHUNK, end - addr)
            r = self._xfer(p.build(p.Cmd.READ_FLASH, addr, length=n), match=3)
            out += r.data[:n]
            addr += n
        return bytes(out)

    def read_config(self) -> MouseConfig:
        ident = self.identity or self.handshake()
        if not self.is_online():
            raise MouseOffline(offline_msg())
        layout = ident.model.layout
        flash = self.read_flash(0, p.MAIN_FLASH_SIZE)
        if layout.base < p.MAIN_FLASH_SIZE:
            dpi_flash = flash[layout.base:layout.base + layout.slot_size * p.DPI_SLOTS]
        else:
            dpi_flash = self.read_flash(layout.base, layout.base + layout.slot_size * p.DPI_SLOTS)
        return MouseConfig.parse(flash, dpi_flash, layout)

    # ---- yazma ----------------------------------------------------------

    def _check_writable(self) -> Identity:
        ident = self.identity or self.handshake()
        if not ident.model.known:
            raise DeviceError(tr("Unknown model; writing settings is disabled for safety."))
        if not self.is_online():
            raise MouseOffline(offline_msg())
        return ident

    def write_flash(self, addr: int, data: bytes) -> None:
        """Yaz ve geri okuyarak doğrula."""
        with self._lock:
            self._check_writable()
            for off in range(0, len(data), p.MAX_CHUNK):
                chunk = data[off:off + p.MAX_CHUNK]
                self._xfer(p.build(p.Cmd.WRITE_FLASH, addr + off, chunk), match=1)
            back = self.read_flash(addr, addr + len(data))
            if back != data:
                raise DeviceError(tr("Verification failed (address {addr}): wrote {w}, read {r}",
                                     addr=addr, w=data.hex(" "), r=back.hex(" ")))

    def _write_option(self, addr: int, value: int, allowed) -> None:
        if value not in allowed:
            raise ValueError(tr("Invalid value: {v}", v=value))
        self.write_flash(addr, p.pair(value))

    def set_report_rate(self, rate: int) -> None:
        ident = self.identity or self.handshake()
        self._write_option(p.Addr.REPORT_RATE, p.RATE_TO_RAW.get(rate, -1),
                           [p.RATE_TO_RAW[r] for r in ident.rate_options])

    def set_dpi_stages(self, count: int) -> None:
        ident = self.identity or self.handshake()
        self._write_option(p.Addr.DPI_STAGES, count, range(1, ident.model.max_stages + 1))

    def set_current_dpi(self, index: int, stages: int) -> None:
        self._write_option(p.Addr.CURRENT_DPI, index, range(0, stages))

    def set_dpi_value(self, index: int, dpi: int) -> int:
        """Kademe DPI'ını yaz; gerçekte yazılan (yuvarlanmış) değeri döner."""
        ident = self.identity or self.handshake()
        model = ident.model
        if not 0 <= index < model.max_stages:
            raise ValueError(tr("Invalid DPI stage"))
        dpi = model.layout.snap(min(dpi, model.max_dpi))
        self.write_flash(model.layout.slot_addr(index), model.layout.encode(dpi))
        return dpi

    def set_lod(self, value: int) -> None:
        ident = self.identity or self.handshake()
        self._write_option(p.Addr.LOD, value, [v for v, _ in LOD_OPTIONS[ident.model.layout.name]])

    def set_debounce(self, ms: int) -> None:
        ident = self.identity or self.handshake()
        self._write_option(p.Addr.DEBOUNCE, ms, range(0, ident.model.max_debounce + 1))

    def set_sleep_time(self, value: int) -> None:
        allowed = [v for v, _secs in SLEEP_OPTIONS]
        # Site uyku süresini iki adrese birden yazıyor.
        self._write_option(p.Addr.SLEEP_TIME, value, allowed)
        self._write_option(p.Addr.PERFORMANCE, value, allowed)

    def set_flag(self, addr: p.Addr, on: bool) -> None:
        if addr not in (p.Addr.MOTION_SYNC, p.Addr.ANGLE_SNAP, p.Addr.RIPPLE,
                        p.Addr.PERFORMANCE_STATE, p.Addr.FPS_20K):
            raise ValueError("not an on/off setting")
        self.write_flash(addr, p.pair(1 if on else 0))

    def set_angle_tune(self, degrees: int) -> None:
        if not -30 <= degrees <= 30:
            raise ValueError(tr("Angle must be between -30 and 30"))
        self.write_flash(p.Addr.ANGLE_TUNE_STATE, p.pair(1))
        self.write_flash(p.Addr.ANGLE_TUNE, p.pair(degrees & 0xFF))

    def factory_reset(self) -> None:
        """Tüm ayarları fabrika değerlerine döndürür (sitedeki 'Restore')."""
        with self._lock:
            self._check_writable()
            self._xfer(p.build(p.Cmd.CLEAR_SETTING))
            time.sleep(1.5)
