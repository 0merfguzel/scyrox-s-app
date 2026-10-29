"""Tanıtımdaki kısa animasyonlar: imleç tepsi ikonuna gider, tıklar, sonucu görünür.

Sahneler elle çizilir (görev çubuğu, ikon, imleç, tıklama halkası); menü ve
ayarlar penceresi örnek fareyle o an alınmış gerçek görüntülerdir. Animasyon
yalnızca sahne görünürken çalışır.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QElapsedTimer, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QWidget

from .i18n import tr
from .icons import battery_icon, model_icon
from .models import ModelInfo

SCENE_W, SCENE_H = 500, 380
BAR_H = 44                 # görev çubuğu
ICON = 22                  # tepsi ikonu (mantıksal px)
FRAME_MS = 16


def ease(a: float) -> float:
    a = min(1.0, max(0.0, a))
    return a * a * (3 - 2 * a)


def phase(t: float, start: float, end: float) -> float:
    """t, [start, end] aralığının neresinde (0..1, kolaylaştırılmış)."""
    return ease((t - start) / (end - start)) if end > start else float(t >= start)


def lerp(p: QPointF, q: QPointF, a: float) -> QPointF:
    return QPointF(p.x() + (q.x() - p.x()) * a, p.y() + (q.y() - p.y()) * a)


class TutorialScene(QWidget):
    """kind: "battery" (sol tık -> pil), "menu" (sağ tık -> hızlı ayarlar),
    "settings" (sağ tık -> Tüm ayarlar -> pencere), "app" (ayarlar penceresinde
    Uygulama ayarları düğmesi -> menü; `button` düğmenin pencere içindeki yeri)."""

    LENGTH = {"battery": 5600, "menu": 6500, "settings": 7800, "app": 6500}

    def __init__(self, kind: str, model: ModelInfo, menu_pm: Optional[QPixmap] = None,
                 menu_rows: Optional[dict[str, QRect]] = None, window_pm: Optional[QPixmap] = None,
                 button: Optional[QRect] = None) -> None:
        super().__init__()
        self.kind = kind
        self.setFixedSize(SCENE_W, SCENE_H)
        self.model = model
        self.menu_pm, self.menu_rows, self.window_pm = menu_pm, menu_rows or {}, window_pm
        self._clock = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(FRAME_MS)
        self._timer.timeout.connect(self.update)
        self.time_override: Optional[float] = None       # testler ve önizleme için

        bar_top = SCENE_H - BAR_H
        self.icon_c = QPointF(SCENE_W - 150, bar_top + BAR_H / 2)
        self.start = QPointF(SCENE_W * 0.32, SCENE_H * 0.42)
        self.rest = self.icon_c + QPointF(5, 5)            # imleç ikonu kapatmasın

        # Menü: Windows'taki gibi görev çubuğunun üstünde, ikona yakın
        self.menu_rect = QRectF()
        self.menu_scale = 1.0
        if menu_pm is not None:
            dpr = menu_pm.devicePixelRatio() or 1.0
            w, h = menu_pm.width() / dpr, menu_pm.height() / dpr
            s = min(1.0, (bar_top - 12) / h)
            self.menu_scale = s
            x = min(self.icon_c.x() - 20, SCENE_W - w * s - 8)
            self.menu_rect = QRectF(x, bar_top - 6 - h * s, w * s, h * s)
        # Ayarlar penceresi: tepsinin köşesinde
        self.window_rect = QRectF()
        if window_pm is not None:
            dpr = window_pm.devicePixelRatio() or 1.0
            w, h = window_pm.width() / dpr, window_pm.height() / dpr
            s = min(1.0, (bar_top - 14) / h, (SCENE_W - 16) / w)
            self.window_rect = QRectF(SCENE_W - w * s - 8, bar_top - 6 - h * s, w * s, h * s)
        if kind == "app" and window_pm is not None and menu_pm is not None and button is not None:
            self._layout_app(window_pm, menu_pm, button)

    def _layout_app(self, window_pm: QPixmap, menu_pm: QPixmap, button: QRect) -> None:
        """Uygulama ayarları sahnesi: pencerenin sol alt köşesi yakından (gerçek
        boyutta, yazılar okunsun); menü düğmenin üstünde açılır."""
        pad = 16
        dpr = window_pm.devicePixelRatio() or 1.0
        w, h = window_pm.width() / dpr, window_pm.height() / dpr
        cw, ch = min(w, SCENE_W - pad), min(h, SCENE_H - pad)
        self.crop = QRectF(0, h - ch, cw, ch)                          # pencerenin görünen kısmı
        self.window_rect = QRectF(pad, SCENE_H - pad - ch, cw, ch)     # sahnedeki yeri
        off = self.window_rect.topLeft() - self.crop.topLeft()
        btn = QRectF(button).translated(off)
        self.btn_rect, self.btn_c = btn, btn.center()
        self.start = QPointF(SCENE_W * 0.62, SCENE_H * 0.30)
        mdpr = menu_pm.devicePixelRatio() or 1.0
        mw, mh = menu_pm.width() / mdpr, menu_pm.height() / mdpr
        self.menu_scale = 1.0
        self.menu_rect = QRectF(btn.left(), max(4.0, btn.top() - mh - 2), mw, mh)

    def row_center(self, name: str) -> QPointF:
        r = self.menu_rows.get(name)
        if r is None or self.menu_rect.isNull():
            return self.menu_rect.center()
        s = self.menu_scale
        return QPointF(self.menu_rect.x() + (r.x() + min(r.width(), 120) * 0.6) * s,
                       self.menu_rect.y() + (r.y() + r.height() / 2) * s)

    def row_rect(self, name: str) -> QRectF:
        r = self.menu_rows.get(name, QRect())
        s = self.menu_scale
        return QRectF(self.menu_rect.x() + r.x() * s, self.menu_rect.y() + r.y() * s, r.width() * s, r.height() * s)

    # ---- yaşam döngüsü: yalnızca görünürken çalış ------------------------

    def showEvent(self, e) -> None:  # noqa: N802 - Qt adı
        self._clock.start()
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e) -> None:  # noqa: N802 - Qt adı
        self._timer.stop()
        super().hideEvent(e)

    def now(self) -> float:
        if self.time_override is not None:
            return self.time_override
        return self._clock.elapsed() % self.LENGTH[self.kind] if self._clock.isValid() else 0.0

    # ---- zaman çizelgeleri ----------------------------------------------

    def state(self, t: float) -> dict:
        """Belirli bir andaki sahne: imleç, tıklama, ikon, menü, pencere."""
        st = {"cursor": self.start, "click": None, "battery": False, "menu": 0.0, "window": 0.0,
              "hover": None}
        to_icon = phase(t, 400, 1500)
        st["cursor"] = lerp(self.start, self.rest, to_icon)
        if self.kind == "app":
            st["window"] = 1.0
            st["click"] = ("left", 1600)
            st["cursor"] = lerp(self.start, self.btn_c, to_icon)
            st["menu"] = phase(t, 1700, 1900) * (1 - phase(t, 5600, 5800))
            st["cursor"] = lerp(st["cursor"], self.row_center("autostart"), phase(t, 2300, 3100))
            if t >= 3100 and st["menu"] > 0.5:
                st["hover"] = "autostart"
        elif self.kind == "battery":
            st["click"] = ("left", 1600)
            st["battery"] = 1700 <= t < 4700
        elif self.kind == "menu":
            st["click"] = ("right", 1600)
            st["menu"] = phase(t, 1700, 1900) * (1 - phase(t, 5600, 5800))
            target = self.row_center("rate")
            st["cursor"] = lerp(st["cursor"], target, phase(t, 2300, 3200))
            if t >= 3200 and st["menu"] > 0.5:
                st["hover"] = "rate"
        else:   # settings
            if t < 2700:
                st["click"] = ("right", 1500)
            else:
                st["click"] = ("left", 2700)
            st["menu"] = phase(t, 1600, 1800) * (0.0 if t >= 2750 else 1.0)
            target = self.row_center("settings")
            st["cursor"] = lerp(st["cursor"], target, phase(t, 1900, 2600))
            if 2600 <= t < 2750:
                st["hover"] = "settings"
            st["window"] = phase(t, 2850, 3150) * (1 - phase(t, 7100, 7400))
        return st

    # ---- çizim ----------------------------------------------------------

    def paintEvent(self, _e) -> None:  # noqa: N802 - Qt adı
        t = self.now()
        st = self.state(t)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        desk = QColor(44, 48, 58) if dark else QColor(214, 224, 238)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(desk)
        p.drawRoundedRect(QRectF(self.rect()), 10, 10)
        if self.kind == "app":
            self._window_corner(p)
        else:
            self._taskbar(p, st, dark)
        if st["window"] > 0 and self.window_pm is not None and self.kind != "app":
            self._pixmap(p, self.window_pm, self.window_rect, st["window"])
        if st["menu"] > 0 and self.menu_pm is not None:
            self._pixmap(p, self.menu_pm, self.menu_rect, st["menu"])
            if st["hover"]:
                hl = self.palette().color(QPalette.ColorRole.Highlight)
                hl.setAlpha(70)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(hl)
                p.drawRoundedRect(self.row_rect(st["hover"]).adjusted(2, 1, -2, -1), 3, 3)
        if st["click"]:
            self._click(p, st["cursor"], t, *st["click"])
        self._cursor(p, st["cursor"])
        p.end()

    def _taskbar(self, p: QPainter, st: dict, dark: bool) -> None:
        top = SCENE_H - BAR_H
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(28, 28, 32) if dark else QColor(240, 240, 244))
        # Alt köşeler sahneyle birlikte yuvarlak, üst kenar düz. (İki şekli tek yolda
        # birleştirmek, varsayılan tek-çift dolgu kuralında çakışan yarıyı boş bırakıyordu.)
        p.drawRoundedRect(QRectF(0, top, SCENE_W, BAR_H), 10, 10)
        p.drawRect(QRectF(0, top, SCENE_W, BAR_H / 2))
        ink = QColor(225, 225, 225) if dark else QColor(40, 40, 40)
        p.setPen(ink)
        p.drawText(QRectF(self.icon_c.x() - 50, top, 20, BAR_H), Qt.AlignmentFlag.AlignCenter, "^")
        icon = battery_icon(85) if st["battery"] else model_icon(self.model)
        r = QRectF(self.icon_c.x() - ICON / 2, self.icon_c.y() - ICON / 2, ICON, ICON)
        p.drawPixmap(r.toRect(), icon.pixmap(QSize(ICON, ICON)))
        f = QFont(p.font())
        f.setPointSizeF(f.pointSizeF() * 0.9)
        p.setFont(f)
        p.drawText(QRectF(SCENE_W - 100, top, 90, BAR_H), Qt.AlignmentFlag.AlignCenter, "12:34\n29.10.2026")

    def _window_corner(self, p: QPainter) -> None:
        """Ayarlar penceresinin sol alt köşesi; üst ve sağ kenar sahnenin dışına taşar."""
        if self.window_rect.isNull():
            return
        dpr = self.window_pm.devicePixelRatio() or 1.0
        src = QRectF(self.crop.x() * dpr, self.crop.y() * dpr, self.crop.width() * dpr, self.crop.height() * dpr)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawRoundedRect(self.window_rect.adjusted(-2, 2, 2, 6), 8, 8)
        p.setClipRect(QRectF(self.rect()))
        p.drawPixmap(self.window_rect, self.window_pm, src)
        p.restore()

    def _pixmap(self, p: QPainter, pm: QPixmap, rect: QRectF, a: float) -> None:
        p.save()
        p.setOpacity(a)
        grow = 0.94 + 0.06 * a                       # açılırken hafifçe büyür
        c = rect.center()
        r = QRectF(0, 0, rect.width() * grow, rect.height() * grow)
        r.moveCenter(QPointF(c.x(), rect.bottom() - r.height() / 2))
        shadow = QColor(0, 0, 0, int(60 * a))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shadow)
        p.drawRoundedRect(r.adjusted(2, 4, 4, 6), 8, 8)
        p.drawPixmap(r, pm, QRectF(pm.rect()))
        p.restore()

    def _click(self, p: QPainter, at: QPointF, t: float, button: str, when: float) -> None:
        dt = t - when
        if 0 <= dt < 450:                            # genişleyip sönen halka
            a = dt / 450
            ring = QColor(255, 255, 255) if button == "left" else QColor(120, 190, 255)
            ring.setAlphaF(1 - a)
            p.setPen(QPen(ring, 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(at, 5 + 16 * a, 5 + 16 * a)
        if -150 <= dt < 900:                         # "Sol tık" / "Sağ tık" etiketi
            text = tr("Left click") if button == "left" else tr("Right click")
            fm = p.fontMetrics()
            w, h = fm.horizontalAdvance(text) + 16, fm.height() + 8
            if self.kind == "app":                   # düğmenin sağındaki boşlukta
                box = QRectF(self.btn_rect.right() + 10, self.btn_rect.center().y() - h / 2, w, h)
            elif self.menu_rect.contains(at):        # menü yazısının üstüne binmesin
                box = QRectF(self.menu_rect.left() - w - 10, at.y() - h / 2, w, h)
            else:
                box = QRectF(at.x() - w - 10, at.y() - h - 18, w, h)
            box.moveLeft(max(6.0, box.left()))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 170))
            p.drawRoundedRect(box, h / 2, h / 2)
            p.setPen(QColor("white"))
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)

    def _cursor(self, p: QPainter, at: QPointF) -> None:
        arrow = QPolygonF([QPointF(x, y) for x, y in
                           ((0, 0), (0, 17), (4, 13), (7, 20), (10, 19), (7, 12), (12, 12))])
        arrow.translate(at)
        p.setPen(QPen(QColor("black"), 1.2))
        p.setBrush(QColor("white"))
        p.drawPolygon(arrow)
