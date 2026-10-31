"""Tepsi / pencere ikonları.

Önce `assets/icons/<model>_<renk>.ico|png` (örn. `V6s_white.ico`) aranır;
böylece her model + renk için istediğin ikonu klasöre koyman yeterli.
Bulunamazsa farenin rengine boyanmış basit bir fare silueti çizilir.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Optional

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QIconEngine, QImage, QPainter,
                         QPainterPath, QPen, QPixmap, QTransform)

from .models import COLORS, ModelInfo


def assets_dir() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, "assets", "icons")


def _custom_icon(model: ModelInfo) -> Optional[QIcon]:
    folder = assets_dir()
    if not os.path.isdir(folder):
        return None
    files = sorted(os.listdir(folder))
    # Önce tam model (V6s_white), sonra "s"siz gövde (V6_white: aynı kasa),
    # en son aynı renkteki herhangi bir ikon.
    for stem in (f"{model.name}_{model.color}", f"{model.name.rstrip('s')}_{model.color}"):
        for ext in (".ico", ".png"):
            for f in files:
                if f.lower() == (stem + ext).lower():
                    return QIcon(os.path.join(folder, f))
    for f in files:
        name, ext = os.path.splitext(f.lower())
        if ext in (".ico", ".png") and name.endswith("_" + model.color):
            return QIcon(os.path.join(folder, f))
    return None


def _mouse_pixmap(fill: str, size: int = 64) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    w, h = size * 0.56, size * 0.92
    body = QRectF((size - w) / 2, (size - h) / 2, w, h)
    path = QPainterPath()
    path.addRoundedRect(body, w * 0.48, w * 0.48)
    color = QColor(fill)
    outline = QColor("#111") if color.lightness() > 110 else QColor("#ddd")
    p.setPen(QPen(outline, size / 24))
    p.setBrush(color)
    p.drawPath(path)
    # tuş ayrımı ve tekerlek
    p.setPen(QPen(outline, size / 40))
    cx = body.center().x()
    p.drawLine(int(cx), int(body.top() + 2), int(cx), int(body.top() + h * 0.36))
    p.setBrush(outline)
    p.drawRoundedRect(QRectF(cx - size / 22, body.top() + h * 0.1, size / 11, h * 0.16), 3, 3)
    p.end()
    return pm


@lru_cache(maxsize=32)
def model_icon(model: Optional[ModelInfo]) -> QIcon:
    if model is not None:
        custom = _custom_icon(model)
        if custom is not None:
            return custom
        return QIcon(_mouse_pixmap(COLORS.get(model.color, COLORS["unknown"])[1]))
    return QIcon(_mouse_pixmap(COLORS["unknown"][1]))


def battery_color(percent: Optional[int]) -> QColor:
    """0-19 kırmızı, 20-39 turuncu, 40-59 sarı, 60-79 açık yeşil, 80-100 koyu yeşil."""
    if percent is None:
        return QColor(150, 150, 155)
    if percent >= 80:
        return QColor(30, 150, 60)
    if percent >= 60:
        return QColor(120, 210, 80)
    if percent >= 40:
        return QColor(240, 200, 40)
    if percent >= 20:
        return QColor(250, 140, 30)
    return QColor(225, 60, 60)


def battery_glyph(percent: Optional[int], height: int) -> QImage:
    """Yatay pil simgesi; doluluk ve renk yüzdeye göre. `height` gerçek
    piksel cinsinden; tam sayı koordinatlarla, yumuşatmasız çizilir."""
    h = max(8, height)
    line = max(1, h // 12)
    body_w = h * 2
    nub_w = max(2, h // 6)
    img = QImage(body_w + nub_w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    frame = QColor(160, 160, 165)
    p.fillRect(0, 0, body_w, h, frame)                                   # dış çerçeve
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)  # içini boşalt
    p.fillRect(line, line, body_w - 2 * line, h - 2 * line, Qt.GlobalColor.transparent)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    nub_h = max(2, h // 2)
    p.fillRect(body_w, (h - nub_h) // 2, nub_w, nub_h, frame)            # kutup başı
    if percent is not None:
        inner_w = body_w - 4 * line
        fill_w = max(1, round(inner_w * min(100, max(0, percent)) / 100))
        p.fillRect(2 * line, 2 * line, fill_w, h - 4 * line, battery_color(percent))
    p.end()
    return img


@lru_cache(maxsize=64)
def refresh_icon(rgb: int, angle: int = 0) -> QIcon:
    """Yenile düğmesi için dairesel ok; `angle` yenileme sürerken döndürmek için."""
    size, r, width = 64, 19, 7
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor.fromRgb(rgb)
    p.translate(size / 2, size / 2)
    p.rotate(angle)
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    start, span = 70, 280                      # derece, saat yönünün tersine
    p.drawArc(QRectF(-r, -r, 2 * r, 2 * r), start * 16, span * 16)
    # Ok başı yayın üstteki ucunda, saat yönünü gösterir
    import math
    end = math.radians(start)
    ex, ey = r * math.cos(end), -r * math.sin(end)
    tx, ty = math.sin(end), math.cos(end)       # teğet (saat yönünde)
    nx, ny = math.cos(end), -math.sin(end)      # dışa doğru
    head = 11
    path = QPainterPath()
    path.moveTo(ex + tx * head, ey + ty * head)
    path.lineTo(ex + nx * head, ey + ny * head)
    path.lineTo(ex - nx * head, ey - ny * head)
    path.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


@lru_cache(maxsize=8)
def chevron_icon(rgb: int, up: bool) -> QIcon:
    """İnce ok (⌃ / ⌄): DPI kartındaki artır / azalt düğmeleri."""
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor.fromRgb(rgb), 6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    path = QPainterPath()
    tip, base = (20, 44) if up else (44, 20)
    path.moveTo(14, base)
    path.lineTo(32, tip)
    path.lineTo(50, base)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


@lru_cache(maxsize=4)
def menu_icon(rgb: int, lead: int = 0) -> QIcon:
    """Üç yatay çizgi (açılan menü işareti). `lead`: solda şeffaf pay (64'lük
    ölçekte); simge yazıdan sonra durduğunda araya boşluk koyar."""
    size = 64
    pm = QPixmap(size + lead, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor.fromRgb(rgb), 6)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    for y in (18, 32, 46):
        p.drawLine(lead + 12, y, lead + 52, y)
    p.end()
    return QIcon(pm)


@lru_cache(maxsize=4)
def gear_icon(rgb: int) -> QIcon:
    """'Tüm ayarlar' için çark simgesi (menü metniyle aynı renkte)."""
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor.fromRgb(rgb))
    p.translate(size / 2, size / 2)
    for _ in range(8):                                   # dişler
        p.drawRoundedRect(QRectF(-6, -30, 12, 16), 2, 2)
        p.rotate(45)
    p.drawEllipse(QRectF(-21, -21, 42, 42))              # gövde
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    p.drawEllipse(QRectF(-9, -9, 18, 18))                # ortadaki delik
    p.end()
    return QIcon(pm)


# ---- pil ikonu -------------------------------------------------------------
#
# Kare çerçeve (rengi yüzdeye göre), koyu zemin, beyaz rakamlar. Rakamlar
# yazı tipinin gerçek çizgileriyle (QPainterPath), ikonun istendiği tam piksel
# boyutunda ve kenar yumuşatmasıyla çizilir; büyütüp küçültme yok.
#   - Yükseklik "88"e göre: 5 de 40 da aynı boyda; "100" kendine göre.
#   - Üstte / altta ve sağda / solda kalan boşluklar eşit: yükseklik ve genişlik
#     buna göre tam piksel seçilir; gerekirse rakamlar yatayda biraz sıkışır.
#   - Rakamlar arasında yazı tipinin boşluğu değil, tam 1 piksel (16-31 px) boşluk.
# Bahnschrift (Windows 10+) dar rakamlıdır, kutuyu iyi doldurur.

BATTERY_FONTS = [("Bahnschrift", "SemiBold SemiCondensed"), ("Segoe UI", "Semibold"), ("Arial", "Bold")]
_BG = QColor(20, 20, 24)
_MIN_SX, _MAX_SX = 0.88, 1.12          # yatay sıkıştırma / açma sınırı


@lru_cache(maxsize=64)
def _text_path(text: str) -> QPainterPath:
    """Yazının 200 px'lik çizgisi (ölçü için büyük; sonra ölçeklenir)."""
    font = QFont()
    for family, style in BATTERY_FONTS:
        if family in QFontDatabase.families():
            font = QFontDatabase.font(family, style, 12)
            break
    font.setPixelSize(200)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    path = QPainterPath()
    path.addText(0, 0, font, text)
    return path


def _ink_width(text: str, scale: float) -> float:
    return sum(_text_path(c).boundingRect().width() for c in text) * scale


@lru_cache(maxsize=256)
def _battery_image(text: str, rgb: int, size: int) -> QImage:
    border = max(1, size // 16)            # 16-31 px: 1, 32-47 px: 2 …
    inner = size - 2 * border
    gap = border                           # rakamlar arası
    avail = inner - 2 * border             # çerçeveyle rakamlar arasında da aynı pay
    gaps = gap * (len(text) - 1)
    eight = _text_path("8").boundingRect()
    ref, min_sx = (text, _MIN_SX) if len(text) > 2 else ("88", 1.0)
    h = avail
    for h in range(avail, 3, -1):          # boş satır sayısı çift: üst ve alt boşluk eşit
        if (inner - h) % 2 == 0 and _ink_width(ref, h / eight.height()) * min_sx + gap * (len(ref) - 1) <= avail:
            break
    scale = h / eight.height()
    baseline = border + (inner - h) // 2 - eight.top() * scale
    ink = _ink_width(text, scale)
    fits = [w for w in range(1, avail + 1)  # boş sütun sayısı çift: sağ ve sol boşluk eşit
            if (inner - w) % 2 == 0 and _MIN_SX <= (w - gaps) / ink <= _MAX_SX]
    width = min(fits, key=lambda w: abs(w - ink - gaps)) if fits else min(ink + gaps, avail)
    sx = (width - gaps) / ink

    out = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(QColor.fromRgb(rgb))
    p = QPainter(out)
    p.fillRect(border, border, inner, inner, _BG)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("white"))
    x = border + (inner - width) / 2
    for c in text:
        path = _text_path(c)
        box = path.boundingRect()
        t = QTransform()
        t.translate(x, baseline)
        t.scale(scale * sx, scale)
        t.translate(-box.left(), 0)
        p.drawPath(t.map(path))
        x += box.width() * scale * sx + gap
    p.end()
    return out


class _BatteryIconEngine(QIconEngine):
    """Her istenen boyut için tam o piksel sayısında çizen ikon motoru."""

    def __init__(self, text: str, color: QColor) -> None:
        super().__init__()
        self.text = text
        self.color = QColor(color)

    def _pixmap(self, px: int, scale: float = 1.0) -> QPixmap:
        pm = QPixmap.fromImage(_battery_image(self.text, self.color.rgb(), max(8, px)))
        pm.setDevicePixelRatio(scale)
        return pm

    def scaledPixmap(self, size, mode, state, scale):  # noqa: N802 - Qt adı
        return self._pixmap(round(size.width() * scale), scale)

    def pixmap(self, size, mode, state):
        return self._pixmap(size.width())

    def paint(self, painter, rect, mode, state):
        dpr = painter.device().devicePixelRatioF() if painter.device() else 1.0
        painter.drawPixmap(rect.topLeft(), self._pixmap(round(rect.width() * dpr), dpr))

    def clone(self):
        return _BatteryIconEngine(self.text, self.color)


def battery_icon(percent: Optional[int]) -> QIcon:
    """Kare, içinde pil yüzdesi yazan tepsi ikonu."""
    text = "!" if percent is None else str(percent)
    return QIcon(_BatteryIconEngine(text, battery_color(percent)))


# ---- tepsi ikonu boyutu ----------------------------------------------------
#
# Qt tepsi ikonunu tüm ekranların en yüksek ölçeğine göre ister (örn. %100
# monitör + %125 laptop: 20 px). Tepsi ise ana ekranın görev çubuğundadır ve
# orada 16 px gösterilir; Windows 20 px'lik ikonu 16'ya küçültürken rakamlar
# yarım piksel kayıp bulanıklaşıyordu. Bu yüzden tepsiye tam kullanılacak
# boyutta ikon verilir.

def tray_px() -> int:
    """Tepsinin gerçekten kullandığı küçük ikon boyutu (ana ekranın ölçeğinde)."""
    screen = QGuiApplication.primaryScreen()
    dpi = round(96 * (screen.devicePixelRatio() if screen else 1.0))
    if sys.platform == "win32":
        try:
            import ctypes
            return ctypes.windll.user32.GetSystemMetricsForDpi(49, dpi)    # SM_CXSMICON
        except (AttributeError, OSError):
            pass
    return round(16 * dpi / 96)


class _TrayIconEngine(QIconEngine):
    """Başka bir ikonu, Qt hangi boyutu isterse istesin tepsinin boyutunda verir."""

    def __init__(self, icon: QIcon) -> None:
        super().__init__()
        self.icon = QIcon(icon)

    def scaledPixmap(self, size, mode, state, scale):  # noqa: N802 - Qt adı
        px = tray_px()
        pm = self.icon.pixmap(QSize(px, px), 1.0, mode, state)
        pm.setDevicePixelRatio(px / max(1, size.width()))
        return pm

    def pixmap(self, size, mode, state):
        return self.icon.pixmap(size, 1.0, mode, state)

    def paint(self, painter, rect, mode, state):
        self.icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter, mode, state)

    def clone(self):
        return _TrayIconEngine(self.icon)


def tray_icon(icon: QIcon) -> QIcon:
    return QIcon(_TrayIconEngine(icon))
