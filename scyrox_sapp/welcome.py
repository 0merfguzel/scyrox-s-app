"""İlk açılışta gösterilen tanıtım (Uygulama ayarları > Tanıtımı göster ile de açılır).

Görüntüler sabit resim değil: tepsi menüsü ve ayarlar penceresi örnek bir
fareyle (demo.py) o an çizilir, böylece seçili dil ve tema neyse onunla aynıdır.
"""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import QPoint, QRect, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                             QVBoxLayout, QWidget)

from . import autostart, prefs
from .demo import DemoService
from .i18n import tr
from .icons import model_icon
from .tutorial import TutorialScene

IMAGE_W, IMAGE_H = 500, 420   # görüntü alanı (mantıksal piksel)


def _fit(pm: QPixmap, w: int = IMAGE_W, h: int = IMAGE_H) -> QPixmap:
    """Görüntüyü alana sığdır (büyütmeden), ekran ölçeğini koruyarak."""
    dpr = pm.devicePixelRatio() or 1.0
    lw, lh = pm.width() / dpr, pm.height() / dpr
    scale = min(1.0, w / lw, h / lh)
    if scale >= 1.0:
        return pm
    out = pm.scaled(QSize(round(pm.width() * scale), round(pm.height() * scale)),
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    out.setDevicePixelRatio(dpr)
    return out


def _canvas(w: int, h: int, dpr: float) -> QPixmap:
    pm = QPixmap(round(w * dpr), round(h * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    return pm


def tray_picture(dpr: float, palette: QPalette) -> QPixmap:
    """Görev çubuğunun sağ köşesi: gizli simgeler oku, fare ikonu, saat."""
    w, h, scale = 300, 64, 1.4
    pm = _canvas(round(w * scale), round(h * scale), dpr)
    p = QPainter(pm)
    p.scale(scale, scale)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    bar = QColor(32, 32, 36) if palette.color(QPalette.ColorRole.Window).lightness() < 128 else QColor(236, 236, 240)
    ink = QColor(230, 230, 230) if bar.lightness() < 128 else QColor(30, 30, 30)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bar)
    p.drawRoundedRect(QRectF(0, 8, w, h - 16), 8, 8)
    p.setPen(ink)
    f = QFont(p.font())
    f.setPointSizeF(f.pointSizeF() * 1.1)
    p.setFont(f)
    p.drawText(QRectF(14, 8, 24, h - 16), Qt.AlignmentFlag.AlignCenter, "^")
    # Bizim ikon, vurgulu çerçeveyle
    accent = palette.color(getattr(QPalette.ColorRole, "Accent", QPalette.ColorRole.Highlight))
    p.setPen(accent)
    p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 50))
    p.drawRoundedRect(QRectF(52, 14, 36, 36), 6, 6)
    p.drawPixmap(60, 22, model_icon(DemoService().identity.model).pixmap(20, 20))
    p.setPen(ink)
    for i, sym in enumerate(("📶", "🔊")):
        p.drawText(QRectF(104 + i * 30, 8, 26, h - 16), Qt.AlignmentFlag.AlignCenter, sym)
    p.drawText(QRectF(180, 8, 110, h - 16), Qt.AlignmentFlag.AlignCenter, "12:34\n29.10.2026")
    p.end()
    return pm


def settings_pictures() -> tuple[QPixmap, QPixmap, QRect, dict[str, QRect]]:
    """Örnek fareyle çizilmiş ayarlar penceresi ve Uygulama ayarları menüsü;
    animasyon için Uygulama ayarları düğmesinin pencere içindeki yeri ve
    menüde imlecin gideceği satır."""
    from .window import SettingsWindow   # döngüsel içe aktarmayı önlemek için burada

    svc = DemoService()
    w = SettingsWindow(svc)
    w._on_config(svc.config)
    w._on_battery(svc.battery)
    # Gösterilmeden ölçülen pencere eksik boyut verir; ekrana çıkmadan "göster".
    w.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    w.show()
    w.resize(w.sizeHint())
    w.layout().activate()
    window_pm = w.grab()
    button = QRect(w.app_btn.mapTo(w, QPoint(0, 0)), w.app_btn.size())
    w.hide()
    w.app_menu.adjustSize()
    rows = {"autostart": w.app_menu.actionGeometry(w.autostart_act)}
    menu_pm = w.app_menu.grab()
    w.quitting = True
    w.deleteLater()
    return window_pm, menu_pm, button, rows


class WelcomeDialog(QDialog):
    def __init__(self, menu_picture: QPixmap, menu_rows: dict[str, QRect],
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scyrox S-App")
        self.setMinimumWidth(IMAGE_W + 60)
        dpr = self.devicePixelRatioF()
        window_pm, app_menu_pm, app_button, app_rows = settings_pictures()
        model = DemoService().identity.model
        # Pil, hızlı ayarlar, tüm ayarlar ve uygulama ayarları kısa animasyonlarla gösterilir.
        scenes = {kind: TutorialScene(kind, model, menu_picture, menu_rows, window_pm)
                  for kind in ("battery", "menu", "settings")}
        scenes["app"] = TutorialScene("app", model, app_menu_pm, app_rows, window_pm, app_button)

        self.autostart_chk = QCheckBox(tr("Start with Windows"))
        # İlk açılışta önerilen: açık. Sonradan açılırsa mevcut durumu göster.
        self.autostart_chk.setChecked(autostart.is_enabled() or not prefs.welcome_shown())

        pages = [
            (tr("Welcome to Scyrox S-App"),
             tr("Scyrox S-App lives in the system tray, next to the clock. It automatically detects your "
                "Scyrox V6, V6s, V8 or V8s and uses no resources while idle.\n\nDon't see the icon? "
                "Windows may hide new icons: click the ^ arrow on the taskbar and drag the icon onto the "
                "taskbar."),
             tray_picture(dpr, self.palette()), None),
            (tr("Battery at a glance"),
             tr("Left-click the tray icon: the battery level appears on the icon for 10 seconds. "
                "Its color shows the charge, from red to green.\n\nThis is the level the mouse itself "
                "reports, in 5% steps."),
             scenes["battery"], None),
            (tr("Quick settings"),
             tr("Right-click the tray icon: change polling rate, the active DPI stage, LOD, sleep time "
                "and more with one click."),
             scenes["menu"], None),
            (tr("All settings"),
             tr("Double-click the tray icon, or choose All settings: every setting in one window. "
                "Changes are written to the mouse only when you press Apply."),
             scenes["settings"], None),
            (tr("App settings"),
             tr("At the bottom left of All settings: language, the color of the mouse icon, starting "
                "with Windows and updates."),
             scenes["app"], self.autostart_chk),
        ]

        root = QVBoxLayout(self)
        self.stack = QStackedWidget()
        for title, text, picture, extra in pages:
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(8, 4, 8, 4)
            head = QLabel(title)
            head.setStyleSheet("font-size: 18px; font-weight: 600;")
            body = QLabel(text)
            body.setWordWrap(True)
            if isinstance(picture, QPixmap):
                img = QLabel()
                img.setPixmap(_fit(picture))
                img.setAlignment(Qt.AlignmentFlag.AlignCenter)
                img.setMinimumHeight(IMAGE_H // 2)
            else:
                img = picture                           # animasyon
            lay.addWidget(head)
            lay.addWidget(body)
            lay.addSpacing(8)
            lay.addWidget(img, 1, Qt.AlignmentFlag.AlignCenter)
            if extra is not None:
                lay.addWidget(extra, 0, Qt.AlignmentFlag.AlignHCenter)
            self.stack.addWidget(page)
        root.addWidget(self.stack, 1)

        foot = QHBoxLayout()
        self.dots = QLabel()
        self.dots.setStyleSheet("color: gray;")
        self.back_btn = QPushButton(tr("Back"))
        self.next_btn = QPushButton(tr("Next"))
        self.next_btn.setDefault(True)
        self.back_btn.clicked.connect(lambda: self._go(-1))
        self.next_btn.clicked.connect(lambda: self._go(+1))
        foot.addWidget(self.dots)
        foot.addStretch(1)
        foot.addWidget(self.back_btn)
        foot.addWidget(self.next_btn)
        root.addLayout(foot)
        self._go(0)

    def _go(self, delta: int) -> None:
        i = self.stack.currentIndex() + delta
        if i >= self.stack.count():
            self.accept()
            return
        self.stack.setCurrentIndex(max(0, i))
        last = self.stack.currentIndex() == self.stack.count() - 1
        self.back_btn.setEnabled(self.stack.currentIndex() > 0)
        self.next_btn.setText(tr("Get started") if last else tr("Next"))
        self.dots.setText(" ".join("●" if n == self.stack.currentIndex() else "○"
                                   for n in range(self.stack.count())))

    def done(self, result: int) -> None:   # Başla ya da pencereyi kapatma
        """Kapanınca bir daha kendiliğinden açılmaz. Başlangıç seçimi yalnızca
        "Başla" ile uygulanır: son sayfayı (onay kutusunu) görmeden kapatan
        kullanıcı başlangıca habersizce eklenmesin."""
        if result == QDialog.DialogCode.Accepted:
            autostart.set_enabled(self.autostart_chk.isChecked())
        prefs.set_welcome_shown()
        super().done(result)
