"""Desteklenen cihazlar ve model / renk tablosu.

Kaynak: scyrox.net/cfg.json ve sitenin model başına gösterdiği ürün
görselleri (img/devices/mouse/<CID><MID>.png). Aynı modelin her rengi
ayrı bir "mid" ile geliyor, böylece renk dongle'dan okunabiliyor.

İstisna: eski V6'lar renginden bağımsız mid 2 ("V6 siyah") bildiriyor;
mavi bir V6 da mid 2 diyebiliyor (site de onu siyah gösteriyor). Bu yüzden
renk, ayarlar penceresinden elle düzeltilebilir (bkz. prefs.py).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .i18n import tr
from .protocol import LAYOUT_3950, LAYOUT_3955, SensorLayout

VENDOR_ID = 0x3554
USAGE_PAGE = 0xFF02

PRODUCT_IDS = {
    0xF5F4: "Kablosuz dongle",
    0xF5F7: "Kablosuz dongle (V6)",
    0xF517: "Turbo 8K dongle",
    0xF5F6: "Kablolu",
    0xF515: "Kablolu",
}

# Renk anahtarı -> (ad, ikon çizim rengi). Ad, color_label() ile çevrilir.
COLORS = {
    "black": ("Black", "#2b2b2e"),
    "white": ("White", "#ececec"),
    "blue": ("Blue", "#9fd3e6"),
    "yellow": ("Yellow", "#f2e14a"),
    "pink": ("Pink", "#f4b6c8"),
    "red": ("Red", "#b3262c"),
    "white_pattern": ("White (patterned)", "#dcdcdc"),
    "black_pattern": ("Black (patterned)", "#3a3a3a"),
    "unknown": ("Unknown", "#8a8f98"),
}


def color_label(color: str) -> str:
    return tr(COLORS.get(color, COLORS["unknown"])[0])

LOD_OPTIONS = {
    "3950": [(3, "0.7 mm"), (1, "1 mm"), (2, "2 mm")],
    "3955": [(1, "0.7 mm"), (2, "0.9 mm"), (3, "1.2 mm"), (4, "1.4 mm"), (5, "1.6 mm")],
}

# Uyku süresi: flash değeri -> saniye (site seçenekleri)
SLEEP_OPTIONS = [(1, 10), (3, 30), (6, 60), (30, 300), (60, 600), (180, 1800)]


def sleep_label(seconds: int) -> str:
    if seconds < 60:
        return tr("{n} s", n=seconds)
    return tr("{n} min", n=seconds // 60)


@dataclass(frozen=True)
class ModelInfo:
    name: str
    color: str
    layout: SensorLayout
    max_dpi: int
    max_stages: int = 5
    max_debounce: int = 30
    tips_debounce: int = 8   # bunun altı çift tıklamaya yol açabilir (site uyarısı)
    known: bool = True

    @property
    def color_name(self) -> str:
        return color_label(self.color)

    @property
    def display_name(self) -> str:
        return f"Scyrox {tr(self.name)} {self.color_name}"


def _v3950(name, color):
    return ModelInfo(name, color, LAYOUT_3950, 30000)


def _v3955(name, color, **kw):
    return ModelInfo(name, color, LAYOUT_3955, 50000, **kw)


# (cid, mid) -> model
MODELS: dict[tuple[int, int], ModelInfo] = {
    (62, 1): _v3950("V8", "black"),
    (62, 10): _v3950("V8", "white"),
    (62, 11): _v3950("V8", "yellow"),
    (62, 2): _v3950("V6", "black"),
    (62, 12): _v3950("V6", "white"),
    (62, 13): _v3950("V6", "blue"),
    (62, 14): _v3955("V8s", "white"),
    (62, 15): _v3955("V8s", "yellow"),
    (62, 16): _v3955("V8s", "black"),
    (62, 17): _v3955("V6s", "white"),
    (62, 18): _v3955("V6s", "blue"),
    (62, 19): _v3955("V6s", "black"),
    # Pembe: sitedeki görselde V6 kasası, DPI düzeni V6s'inki (3955).
    (62, 5): _v3955("V6s", "pink", max_debounce=15),
    (62, 6): _v3955("V6s", "pink", max_debounce=15),
    # Farklı kasalı, desenli bir seri (sitede adı yok); üç renk aynı model.
    (62, 7): _v3955("(patterned series)", "black_pattern"),
    (62, 8): _v3955("(patterned series)", "red"),
    (62, 9): _v3955("(patterned series)", "white_pattern"),
}

# Renk menüsünde gösterim sırası
COLOR_ORDER = ("black", "white", "blue", "yellow", "pink", "red", "black_pattern", "white_pattern")


def colors_for(model: ModelInfo) -> list[str]:
    """Bu modelin bilinen renkleri (elle renk seçimi için)."""
    colors = {m.color for m in MODELS.values() if m.name == model.name} or {model.color}
    return sorted(colors, key=lambda c: COLOR_ORDER.index(c) if c in COLOR_ORDER else len(COLOR_ORDER))


def with_color(model: ModelInfo, color: str) -> ModelInfo:
    return replace(model, color=color)


def lookup(cid: int, mid: int) -> ModelInfo:
    """Bilinmeyen modelde salt-okunur bir yer tutucu döner."""
    m = MODELS.get((cid, mid))
    if m is not None:
        return m
    return ModelInfo(tr("unknown (cid {cid}, mid {mid})", cid=cid, mid=mid), "unknown",
                     LAYOUT_3950, 30000, known=False)
