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

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QIcon, QIconEngine, QImage, QPainter, QPainterPath, QPen,
                         QPixmap)

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


# ---- piksel hizalı pil ikonu ---------------------------------------------
#
# Tepsi ikonu ekran ölçeğine göre 16, 20 (%125), 24 (%150), 32 (%200)…
# piksel olur. Büyük çizip küçültmek bulanıklaştırır; bu yüzden ikon, Qt
# hangi gerçek piksel boyutunu isterse tam o boyutta, yumuşatmasız ve tam
# sayı koordinatlarla çizilir. Tahoma Bold küçük boyutta yumuşatmasız
# gösterim için tasarlanmış bir yazı tipi.

BATTERY_FONTS = ("Tahoma", "Verdana", "Arial")
_BG = QColor(20, 20, 24)


def _ink_bbox(img: QImage) -> Optional[tuple[int, int, int, int]]:
    """Boyanmış piksellerin sınırı: (x, y, w, h)."""
    a = img.convertToFormat(QImage.Format.Format_Alpha8)
    w, h, bpl = a.width(), a.height(), a.bytesPerLine()
    data = a.constBits().asstring(bpl * h)
    top = left = None
    bottom, right = -1, -1
    for y in range(h):
        row = data[y * bpl:y * bpl + w]
        stripped = row.lstrip(b"\0")
        if not stripped:
            continue
        top = y if top is None else top
        bottom = y
        x0 = w - len(stripped)
        x1 = len(row.rstrip(b"\0")) - 1
        left = x0 if left is None else min(left, x0)
        right = max(right, x1)
    if top is None:
        return None
    return left, top, right - left + 1, bottom - top + 1


@lru_cache(maxsize=512)
def _glyph(ch: str, px: int) -> tuple[QImage, tuple[int, int, int, int]]:
    """Tek karakter, ortak taban çizgisinde: (resim, boyalı alan x, y, w, h)."""
    font = QFont()
    font.setFamilies(list(BATTERY_FONTS))
    font.setPixelSize(px)
    font.setBold(True)
    font.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    img = QImage(px * 2, px * 2, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setFont(font)
    p.setPen(QColor("white"))
    p.drawText(px // 2, px * 3 // 2, ch)
    p.end()
    return img, _ink_bbox(img) or (0, 0, 0, 0)


def _layout(text: str, px: int, gap: int) -> tuple[int, int, int]:
    """Karakterler arasında tam `gap` piksel boşlukla dizildiğinde
    (genişlik, üst, yükseklik)."""
    boxes = [_glyph(c, px)[1] for c in text]
    width = sum(b[2] for b in boxes) + gap * (len(text) - 1)
    top = min(b[1] for b in boxes)
    return width, top, max(b[1] + b[3] for b in boxes) - top


def _fit_px(sample: str, avail: int, gap: int) -> int:
    for px in range(avail * 2, 3, -1):
        w, _top, h = _layout(sample, px, gap)
        if w <= avail and h <= avail:
            return px
    return 4


@lru_cache(maxsize=256)
def _battery_image(text: str, rgb: int, size: int) -> QImage:
    border = max(1, size // 16)            # 16-31 px: 1, 32-47 px: 2 …
    gap = max(1, size // 24)               # rakamlar arası boşluk
    avail = size - 2 * border - 2          # çerçeveyle yazı arasında 1 px boşluk
    # Yazı boyutu sayıya göre değil ikon boyutuna göre seçilir: "5" de "49"
    # da aynı yükseklikte görünür. Yalnızca "100" sığması için küçülür.
    if len(text) > 2:
        # "100": 20 px'e kadar yer dar, okunur kalsın diye çerçeveye kadar uzanır;
        # daha büyük boyutlarda 1 px boşluk kalır.
        px = _fit_px("100", avail + 2 if size <= 20 else avail, gap)
    else:
        px = _fit_px("88", avail, gap)
    width, top, height = _layout(text, px, gap)

    out = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(QColor.fromRgb(rgb))
    p = QPainter(out)
    p.fillRect(border, border, size - 2 * border, size - 2 * border, _BG)
    x = (size - width) // 2
    y = (size - height) // 2
    for c in text:
        img, (gx, _gy, gw, _gh) = _glyph(c, px)
        p.drawImage(x, y, img.copy(gx, top, gw, height))
        x += gw + gap
    p.end()
    return out


class _PixelIconEngine(QIconEngine):
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
        return _PixelIconEngine(self.text, self.color)


def battery_icon(percent: Optional[int]) -> QIcon:
    """Kare, içinde pil yüzdesi yazan tepsi ikonu."""
    text = "!" if percent is None else str(percent)
    return QIcon(_PixelIconEngine(text, battery_color(percent)))
