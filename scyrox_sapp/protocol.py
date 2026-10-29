r"""
Scyrox / Compx HID protokolü
============================

scyrox.net (S-center) web sürücüsünün JS kodundan çıkarıldı ve gerçek bir
V6s + Turbo 8K dongle üzerinde okunarak doğrulandı.

Paket yapısı (17 bayt, report id dahil)::

    [0]      0x08   HID report ID
    [1]      cmd    Komut (Cmd)
    [2]      0x00   Cevapta durum baytı
    [3..4]   addr   Flash adresi, big-endian
    [5]      len    Veri uzunluğu
    [6..15]  data   En fazla 10 bayt veri
    [16]     chk    (0x55 - sum(bytes[0..15])) & 0xFF

Fare ayarları, dongle üzerinden fareye ait bir "flash" bellek tablosuna
yazılır (WRITE_FLASH) ve okunur (READ_FLASH). Tek baytlık ayarlar
[değer, 0x55 - değer] çifti olarak saklanır; toplamı 0x55 olmayan çift
geçersiz / hiç yazılmamış kabul edilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

REPORT_ID = 0x08
PACKET_LEN = 17
MAX_CHUNK = 10


class Cmd(IntEnum):
    HANDSHAKE = 0x01        # site: EncryptionData. cid / mid / dongle tipi döner
    DEVICE_ONLINE = 0x03    # fare açık ve dongle'a bağlı mı
    BATTERY = 0x04
    WRITE_FLASH = 0x07
    READ_FLASH = 0x08
    CLEAR_SETTING = 0x09    # fabrika ayarlarına dönüş


class Addr(IntEnum):
    """Fare flash adres haritası (site: Se tablosu)."""

    REPORT_RATE = 0
    DPI_STAGES = 2
    CURRENT_DPI = 4
    FPS_20K = 8             # site: Scyrox20K
    LOD = 10
    DPI_VALUE = 12          # 3950 düzeni: 8 x 4 bayt
    DEBOUNCE = 169
    MOTION_SYNC = 171
    SLEEP_TIME = 173
    ANGLE_SNAP = 175
    RIPPLE = 177
    PERFORMANCE_STATE = 181
    PERFORMANCE = 183
    ANGLE_TUNE = 189
    ANGLE_TUNE_STATE = 191
    DPI_VALUE_3955 = 6912   # 3955 düzeni: 8 x 6 bayt


MAIN_FLASH_SIZE = 256
DPI_SLOTS = 8


def checksum(first16: bytes | list[int]) -> int:
    return (0x55 - sum(first16)) & 0xFF


def build(cmd: int, addr: int = 0, data: bytes = b"", length: Optional[int] = None) -> bytes:
    """Gönderilecek 17 baytlık paketi üret."""
    if len(data) > MAX_CHUNK:
        raise ValueError("bir pakette en fazla 10 bayt veri olabilir")
    body = [0] * 16
    body[0] = REPORT_ID
    body[1] = cmd
    body[3] = (addr >> 8) & 0xFF
    body[4] = addr & 0xFF
    body[5] = len(data) if length is None else length
    body[6:6 + len(data)] = data
    return bytes(body + [checksum(body)])


@dataclass
class Response:
    cmd: int
    status: int
    addr: int
    length: int
    data: bytes  # 10 bayt
    raw: bytes

    @property
    def valid(self) -> bool:
        return checksum(self.raw[:16]) == self.raw[16]


def parse(report: bytes | list[int]) -> Optional[Response]:
    raw = bytes(report)
    if len(raw) < PACKET_LEN or raw[0] != REPORT_ID:
        return None
    raw = raw[:PACKET_LEN]
    return Response(cmd=raw[1], status=raw[2], addr=(raw[3] << 8) | raw[4],
                    length=raw[5], data=raw[6:16], raw=raw)


# -------------------------------------------------------------------------
# Değer çiftleri
# -------------------------------------------------------------------------

def pair(value: int) -> bytes:
    value &= 0xFF
    return bytes([value, (0x55 - value) & 0xFF])


def read_pair(mem: bytes, addr: int) -> Optional[int]:
    """[değer, 0x55-değer] çiftini oku; geçersizse None."""
    if addr + 1 >= len(mem):
        return None
    v, c = mem[addr], mem[addr + 1]
    return v if (v + c) & 0xFF == 0x55 else None


# -------------------------------------------------------------------------
# Polling rate
# -------------------------------------------------------------------------

RATE_TO_RAW = {125: 8, 250: 4, 500: 2, 1000: 1, 2000: 16, 4000: 32, 8000: 64}
RAW_TO_RATE = {v: k for k, v in RATE_TO_RAW.items()}

# Handshake'teki "type" alanı -> (kablolu mu, en yüksek polling)
DONGLE_TYPES = {
    0: (False, 1000),
    1: (False, 4000),
    2: (True, 1000),
    3: (True, 8000),
    4: (False, 2000),
    5: (False, 8000),
}


# -------------------------------------------------------------------------
# DPI kodlaması
# -------------------------------------------------------------------------

@dataclass(frozen=True)
class DpiRange:
    min: int
    max: int
    step: int
    ex: int  # site: DPIex. 17 => "x2" bayrağı hem X hem Y için


@dataclass(frozen=True)
class SensorLayout:
    """DPI'nın flash'ta nasıl saklandığı. İsim, sitenin sensor.json
    anahtarıdır; farenin içindeki sensörün ticari adıyla aynı olmayabilir
    (örn. V6s'te PAW Next-1 var ama site onu "3955" düzeniyle yazıyor)."""

    name: str
    base: int
    slot_size: int
    ranges: tuple[DpiRange, ...]

    def slot_addr(self, index: int) -> int:
        return self.base + index * self.slot_size

    def snap(self, dpi: int) -> int:
        """DPI'yı sensörün kabul ettiği en yakın değere yuvarla."""
        lo, hi = self.ranges[0].min, self.ranges[-1].max
        dpi = max(lo, min(hi, int(dpi)))
        for r in reversed(self.ranges):
            if dpi >= r.min:
                return max(r.min, min(r.max, round(dpi / r.step) * r.step))
        return lo

    def encode(self, dpi: int) -> bytes:
        dpi = self.snap(dpi)
        idx = max(i for i, r in enumerate(self.ranges) if dpi >= r.min)
        ex = self.ranges[idx].ex
        # Üst aralıkta (ex=17) değer yarıya bölünüp "x2" bayrağıyla saklanır.
        t = (dpi // (2 if ex else 1)) // self.ranges[0].step - 1
        if self.slot_size == 6:
            hi = (t >> 16) & 3
            flags = (hi << 2 | hi << 6 | ex | ex << 4) & 0xFF
            body = [t & 0xFF, (t >> 8) & 0xFF, t & 0xFF, (t >> 8) & 0xFF, flags]
        else:
            hi = (t >> 8) & 3
            flags = (hi << 2 | hi << 6 | ex | ex << 4) & 0xFF
            body = [t & 0xFF, t & 0xFF, flags]
        return bytes(body + [checksum(body)])

    def decode(self, slot: bytes) -> Optional[int]:
        """Slot baytlarını DPI'ya çevir (X ekseni). Geçersizse None."""
        if len(slot) < self.slot_size or sum(slot[:self.slot_size]) & 0xFF != 0x55:
            return None
        flags = slot[self.slot_size - 2]
        ex, hi = flags & 3, (flags >> 2) & 3
        if self.slot_size == 6:
            t = slot[0] | slot[1] << 8 | hi << 16
        else:
            t = slot[0] | hi << 8
        value = (t + 1) * self.ranges[0].step
        if ex & 1:
            value *= 2
        if ex & 2:
            value *= 2
        return value


LAYOUT_3950 = SensorLayout("3950", Addr.DPI_VALUE, 4, (
    DpiRange(50, 30000, 50, 0),
    DpiRange(30100, 60000, 100, 17),
))

LAYOUT_3955 = SensorLayout("3955", Addr.DPI_VALUE_3955, 6, (
    DpiRange(1, 42000, 1, 0),
    DpiRange(42002, 84000, 2, 17),
))
