"""Tüm ayarlar penceresi.

Kontroller değiştirilince fareye hemen yazılmaz: pencere bir taslak tutar.
Fareden okunan değerlerden farklı bir şey varsa "Uygula" vurgulanır; basınca
tüm farklar tek seferde (sonda tek okuma) yazılır. "Vazgeç"
taslağı atar. Pencere açıkken ayarlar başka yerden (tepsi menüsü) değişirse
taslaktaki değişiklikler korunur.
"""

from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup, QColor, QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QMenu, QMessageBox, QProgressBar, QPushButton,
                             QScrollArea, QSizePolicy, QSlider, QSpacerItem, QSpinBox, QStackedWidget,
                             QStyle, QStyleOptionButton, QStyleOptionGroupBox, QToolButton,
                             QVBoxLayout, QWidget)

from . import autostart
from . import device as d
from . import i18n
from . import prefs
from . import protocol as p
from . import style
from .i18n import tr
from .icons import battery_glyph, chevron_icon, menu_icon, model_icon, refresh_icon
from .models import LOD_OPTIONS, SLEEP_OPTIONS, color_label, colors_for, sleep_label
from .service import DeviceService

DPI_ROWS = 5
CARD_W, CARD_H, CARD_PAD = 90, 64, 4
ARROW_W = 16                # ok düğmesi genişliği (12 px simge + 2'şer px pay)
# DPI okuna basılı tutma: basınca hemen bir adım, HOLD_SECOND_MS sonra bir adım
# daha; HOLD_TICKS_START_MS'den itibaren her HOLD_TICK_MS'de bir adım (sabit hız).
# Adım DPI_STEP ile başlar, her HOLD_DOUBLE_EVERY tikte (2 sn) ikiye katlanır.
DPI_STEP = 50
HOLD_SECOND_MS = 750
HOLD_TICKS_START_MS = 1000
HOLD_TICK_MS = 250
HOLD_DOUBLE_EVERY = 8
MESSAGE_MS = 6000   # "kaydedildi" mesajı bu kadar görünür (hatalar kalır)
# Fabrika ayarları: sakin dursun (yalnızca kırmızı çerçeve), üstüne gelince kırmızıyla dolsun.
RESET_CSS = ("QPushButton { background: transparent; color: #e0574c; border: 1px solid #c0392b;"
             " font-weight: 600; padding: 7px 18px; border-radius: 4px; }"
             " QPushButton:hover { background: #c0392b; color: white; }"
             " QPushButton:pressed { background: #a93226; color: white; }"
             " QPushButton:disabled { color: gray; border-color: gray; }")
FLAGS = (("motion", p.Addr.MOTION_SYNC, "Motion Sync"),
         ("angle", p.Addr.ANGLE_SNAP, "Angle snapping"),
         ("ripple", p.Addr.RIPPLE, "Ripple control"),
         ("perf", p.Addr.PERFORMANCE_STATE, None),   # 20K FPS'ten önce yazılmalı
         ("fps", p.Addr.FPS_20K, "20K FPS"))


def battery_text(b: d.Battery) -> str:
    text = tr("Battery {p}%  ({v} V)", p=b.percent, v=f"{b.millivolts / 1000:.2f}")
    return text + (tr("  · charging") if b.charging else "")


class NoteGroupBox(QGroupBox):
    """Başlığın hemen yanında soluk bir not gösteren grup kutusu
    (örn. "Polling rate  en fazla 8000 Hz")."""

    def __init__(self, title: str) -> None:
        super().__init__(title)
        self.note = QLabel(self)
        self.note.setStyleSheet("color: gray; padding: 0 4px;")
        self.note.setAutoFillBackground(True)   # çerçeve çizgisi notun altından geçmesin

    def set_note(self, text: str) -> None:
        self.note.setText(text)
        self.note.adjustSize()
        self.note.setVisible(bool(text))
        self._place()

    def resizeEvent(self, e) -> None:  # noqa: N802 - Qt adı
        super().resizeEvent(e)
        self._place()

    def _place(self) -> None:
        opt = QStyleOptionGroupBox()
        self.initStyleOption(opt)
        r = self.style().subControlRect(QStyle.ComplexControl.CC_GroupBox, opt,
                                        QStyle.SubControl.SC_GroupBoxLabel, self)
        self.note.move(r.right() + 2, r.top() + (r.height() - self.note.height()) // 2)


class DpiSpin(QSpinBox):
    """Kartın değer kutusu. Tek tık kartı seçer (kutuya odaklanmaz); çift tık
    klavyeyle düzenlemeyi açar, Enter ya da başka yere tıklamak kapatır.
    Düzenlemede değilken fare tekerleği değeri değiştirmez, pencereyi kaydırır."""

    clicked = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.lineEdit().installEventFilter(self)
        self.editingFinished.connect(self._stop_editing)
        self._stop_editing()

    def editing(self) -> bool:
        return not self.isReadOnly()

    def _start_editing(self) -> None:
        self.setReadOnly(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lineEdit().setCursor(Qt.CursorShape.IBeamCursor)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.selectAll()

    def _stop_editing(self) -> None:
        self.setReadOnly(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lineEdit().setCursor(Qt.CursorShape.PointingHandCursor)
        self.lineEdit().deselect()
        self.clearFocus()

    def eventFilter(self, obj, ev) -> bool:  # noqa: N802 - Qt adı
        if obj is self.lineEdit() and not self.editing():
            kind = ev.type()
            if kind == QEvent.Type.MouseButtonPress:
                if ev.button() == Qt.MouseButton.LeftButton:
                    self.clicked.emit()
                return True                    # imleç konmasın, odak alınmasın
            if kind == QEvent.Type.MouseButtonDblClick:
                if ev.button() == Qt.MouseButton.LeftButton:
                    self._start_editing()
                return True
            if kind in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseMove):
                return True                    # sürükleyerek metin seçilmesin
        return super().eventFilter(obj, ev)

    def wheelEvent(self, e) -> None:  # noqa: N802 - Qt adı
        if self.editing():
            super().wheelEvent(e)
        else:
            e.ignore()                         # pencereye geçsin: kaydırma


class DpiCard(QFrame):
    """Bir DPI kademesi: üstte yazılabilen değer, altında "⌄ DPI ⌃". Karta
    tıklanınca o kademe aktif olur; aktif kart vurgu renginde dolu çizilir.
    Kart elle çizilir (stil sayfası yok), içteki kutular stilden etkilenmesin."""

    selected = pyqtSignal(int)

    def __init__(self, index: int) -> None:
        super().__init__()
        self.index = index
        self.active = False
        self._hover = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(CARD_W, CARD_H)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(CARD_PAD, 6, CARD_PAD, 4)
        lay.setSpacing(0)
        self.spin = DpiSpin()
        self.spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.spin.setFrame(False)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setSingleStep(50)
        self.spin.clicked.connect(lambda: self.selected.emit(self.index))
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.down = QToolButton()
        self.up = QToolButton()
        for b in (self.down, self.up):
            b.setAutoRaise(True)
            b.setFixedSize(ARROW_W, 20)
            b.setIconSize(QSize(12, 12))
            b.setCursor(Qt.CursorShape.ArrowCursor)
            b.installEventFilter(self)            # basma / bırakma: bkz. eventFilter
        # Basılı tutma zamanlayıcısı (yalnızca ok basılıyken çalışır)
        self._hold_sign = 0
        self._hold_ticks = 0
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._hold_next)
        self.unit = QLabel("DPI")
        self.unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Eşit boşluk: kenar | ⌄ | DPI | ⌃ | kenar arasındaki dört boşluk aynı.
        text_w = self.unit.fontMetrics().horizontalAdvance("DPI")
        self.unit.setFixedWidth(text_w)
        free = CARD_W - 2 * ARROW_W - text_w
        gap, extra = divmod(free, 4)
        left = gap - CARD_PAD + extra // 2        # kartın kendi iç payı zaten var;
        right = gap - CARD_PAD + extra - extra // 2   # bölünmeyen pikseller iki kenara
        row.setContentsMargins(left, 0, right, 0)
        row.setSpacing(gap)
        row.addWidget(self.down)
        row.addWidget(self.unit)
        row.addWidget(self.up)
        lay.addWidget(self.spin)
        lay.addLayout(row)
        self._recolor()

    def eventFilter(self, obj, ev) -> bool:  # noqa: N802 - Qt adı
        if obj in (self.down, self.up) and obj.isEnabled():
            if ev.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick) \
                    and ev.button() == Qt.MouseButton.LeftButton:
                self.hold_begin(-1 if obj is self.down else 1)
            elif ev.type() == QEvent.Type.MouseButtonRelease:
                self.hold_end()
        return super().eventFilter(obj, ev)

    # ---- basılı tutma: 0 sn adım, 0.75 sn adım, 1 sn'den itibaren 4 tik/sn
    def hold_begin(self, sign: int) -> None:
        self._hold_sign = sign
        self._hold_ticks = -1                       # -1: henüz ikinci adım atılmadı
        self.bump(sign, DPI_STEP)
        self._hold_timer.start(HOLD_SECOND_MS)

    @staticmethod
    def _still_held() -> bool:
        # Bırakma olayı kaçabilir (ör. basılıyken Alt+Tab): sayaç sonsuza kadar sürmesin.
        return bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)

    def _hold_next(self) -> None:
        if not self._still_held():
            self.hold_end()
            return
        if self._hold_ticks < 0:                    # 0.75 sn: ikinci adım
            self.bump(self._hold_sign, DPI_STEP)
            self._hold_ticks = 0
            self._hold_timer.start(HOLD_TICKS_START_MS - HOLD_SECOND_MS)
            return
        size = DPI_STEP * 2 ** (self._hold_ticks // HOLD_DOUBLE_EVERY)
        self.bump(self._hold_sign, size)
        self._hold_ticks += 1
        self._hold_timer.start(HOLD_TICK_MS)

    def hold_end(self) -> None:
        self._hold_timer.stop()
        self._hold_sign = 0

    def bump(self, sign: int, size: int) -> None:
        """Değeri `size`'ın bir sonraki katına taşı: adım 100 olunca değer
        "00" ile biter (850'den başlansa bile). setValue metni seçmez (stepBy
        seçiyordu: artırılan kutuların sayısı vurgulu kalıyordu)."""
        v = self.spin.value()
        if sign > 0:
            target = (v // size + 1) * size
        else:
            target = (-(-v // size) - 1) * size
        self.spin.setValue(target)
        self.spin.lineEdit().deselect()

    def _accent(self) -> QColor:
        return self.palette().color(getattr(QPalette.ColorRole, "Accent", QPalette.ColorRole.Highlight))

    def set_active(self, on: bool) -> None:
        if on != self.active:
            self.active = on
            self._recolor()
            self.update()

    def _recolor(self) -> None:
        """Yazı ve okların rengi: aktif kartta vurgu renginin üstünde okunur olsun."""
        if self.active:
            ink = QColor("black") if self._accent().lightness() > 150 else QColor("white")
        else:
            ink = self.palette().color(QPalette.ColorRole.Text)
        self.spin.setStyleSheet(f"QSpinBox {{ background: transparent; border: none; color: {ink.name()};"
                                " font-size: 15px; font-weight: 600; }")
        self.unit.setStyleSheet(f"color: {ink.name()};")
        self.down.setIcon(chevron_icon(ink.rgb(), False))
        self.up.setIcon(chevron_icon(ink.rgb(), True))

    def mousePressEvent(self, e) -> None:  # noqa: N802 - Qt adı
        if e.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.index)
        super().mousePressEvent(e)

    def enterEvent(self, e) -> None:  # noqa: N802 - Qt adı
        self._hover = True
        self.update()

    def leaveEvent(self, e) -> None:  # noqa: N802 - Qt adı
        self._hover = False
        self.update()

    def paintEvent(self, e) -> None:  # noqa: N802 - Qt adı
        accent = self._accent()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.active:
            fill = QColor(accent)
            if not self.isEnabled():
                fill.setAlpha(90)
            p.setPen(fill)
            p.setBrush(fill)
        else:
            edge = QColor(accent) if self._hover and self.isEnabled() else QColor(128, 128, 128, 140)
            p.setPen(edge)
            p.setBrush(QColor(128, 128, 128, 25))
        p.drawRoundedRect(rect, 6, 6)
        p.end()


class ElidedLabel(QLabel):
    """Tek satır; sığmayan metin "…" ile kısalır, tamamı ipucunda görünür.
    Uzun bir hata mesajı pencere yerleşimini oynatmasın."""

    def __init__(self) -> None:
        super().__init__()
        self._full = ""
        self.setMinimumWidth(10)

    def set_full_text(self, text: str) -> None:
        self._full = text
        self.setToolTip(text if len(text) > 40 else "")
        self._elide()

    def resizeEvent(self, e) -> None:  # noqa: N802 - Qt adı
        super().resizeEvent(e)
        self._elide()

    def _elide(self) -> None:
        self.setText(self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight, self.width()))


class SettingsWindow(QWidget):
    language_changed = pyqtSignal(object)   # dil kodu ya da None (Windows diline göre)
    welcome_requested = pyqtSignal()        # Uygulama ayarları > Tanıtımı göster
    update_requested = pyqtSignal()         # Uygulama ayarları > Güncellemeleri denetle

    def __init__(self, service: DeviceService) -> None:
        super().__init__()
        style.install()                # sayı kutusu düğmeleri ve açılır liste işareti
        self.svc = service
        self._loading = False
        self._base: dict = {}          # fareden okunan değerler (kontrollerdeki karşılığı)
        self._shown_dev = None
        self.quitting = False
        self.setWindowTitle("Scyrox S-App")
        self._build()
        service.device_changed.connect(self._on_device)
        service.config_changed.connect(self._on_config)
        service.battery_changed.connect(self._on_battery)
        service.busy_changed.connect(self._on_busy)
        service.message.connect(self._on_message)
        self._on_device(service.identity)
        if service.battery is not None:
            self._on_battery(service.battery)

    # ---- yerleşim -------------------------------------------------------

    def _build(self) -> None:
        root = QVBoxLayout(self)

        head = QHBoxLayout()
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(48, 48)
        info = QVBoxLayout()
        title_row = QHBoxLayout()
        self.title_lbl = QLabel()
        self.title_lbl.setStyleSheet("font-size: 16px; font-weight: 600;")
        title_row.addWidget(self.title_lbl)
        title_row.addStretch(1)
        self.sub_lbl = QLabel()
        self.sub_lbl.setStyleSheet("color: gray;")
        batt_row = QHBoxLayout()
        self.batt_icon = QLabel()
        self.batt_lbl = QLabel()
        batt_row.addWidget(self.batt_icon)
        batt_row.addWidget(self.batt_lbl)
        batt_row.addStretch(1)
        info.addLayout(title_row)
        info.addWidget(self.sub_lbl)
        info.addLayout(batt_row)
        self.refresh_btn = QPushButton(tr("Refresh"))
        self.refresh_btn.setObjectName("refreshBtn")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(lambda: self._refresh("manual"))
        self._spin_angle = 0
        self._spin_timer = QTimer(self)            # yalnızca yenileme sürerken çalışır
        self._spin_timer.setInterval(40)
        self._spin_timer.timeout.connect(self._spin)
        head.addWidget(self.icon_lbl)
        head.addLayout(info, 1)
        head.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(head)

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.setStyleSheet("background:#fff4d6; color:#5a4500; padding:6px; border-radius:4px;")
        root.addWidget(self.banner)

        # Ayarlar kaydırılabilir: küçük ekranlarda (örn. 1366x768) pencere ekrana sığsın,
        # başlık ve Uygula / Vazgeç her zaman görünsün.
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)
        self._root = root

        # Polling rate
        box = self.rate_box = NoteGroupBox("Polling rate")
        self.rate_layout = QHBoxLayout(box)
        self.rate_group = QButtonGroup(self)
        self.rate_group.idToggled.connect(lambda *_: self._changed())
        body.addWidget(box)

        # DPI: kademeler polling rate düğmeleri gibi yan yana kartlar; aktif kart
        # dolu. Altında ortada kademe sayısı.
        box = QGroupBox("DPI")
        dl = QVBoxLayout(box)
        cards = QHBoxLayout()
        cards.addStretch(1)
        self._active_stage = 0
        self.dpi_cards: list[DpiCard] = []
        for i in range(DPI_ROWS):
            card = DpiCard(i)
            card.setToolTip(tr("Stage {n}", n=i + 1))
            card.spin.valueChanged.connect(lambda *_: self._changed())
            card.selected.connect(self._select_stage)
            cards.addWidget(card)
            self.dpi_cards.append(card)
        cards.addStretch(1)
        dl.addLayout(cards)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(QLabel(tr("Number of stages")))
        self.stage_spin = QSpinBox()
        self.stage_spin.setRange(1, DPI_ROWS)
        self.stage_spin.valueChanged.connect(self._stages_changed)
        row.addWidget(self.stage_spin)
        row.addStretch(1)
        dl.addSpacing(4)
        dl.addLayout(row)
        body.addWidget(box)

        # Sensör
        # Sensör: üstte tam genişlikte sensör açısı; altında iki sütunda üçer
        # seçenek. Rekabet modu, ona bağlı 20K FPS ve LOD sağda. Satırlar eşit
        # yükseklikte: iki sütun hizalı dursun.
        box = QGroupBox(tr("Sensor"))
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(24)
        lod = QHBoxLayout()
        lod_lbl = QLabel("LOD")
        lod_lbl.setToolTip(tr("Lift-off distance"))
        self.lod_combo = QComboBox()
        self.lod_combo.setToolTip(tr("Lift-off distance"))
        self.lod_combo.currentIndexChanged.connect(lambda *_: self._changed())
        lod.addWidget(lod_lbl)
        self._lod_gap = QSpacerItem(0, 0)   # genişliği aşağıda, sağ boşluğa eşitlenir
        lod.addSpacerItem(self._lod_gap)
        lod.addWidget(self.lod_combo, 1)
        grid.addLayout(lod, 3, 1)
        tune = QHBoxLayout()
        tune.setContentsMargins(0, 0, 0, 0)
        self.tune_slider = QSlider(Qt.Orientation.Horizontal)
        self.tune_slider.setRange(-30, 30)
        self.tune_lbl = QLabel("0°")
        self.tune_lbl.setMinimumWidth(self.tune_lbl.fontMetrics().horizontalAdvance("-30°"))
        self.tune_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tune_slider.valueChanged.connect(self._tune_changed)
        tune.addWidget(QLabel(tr("Sensor angle")))
        tune.addWidget(self.tune_slider, 1)
        tune.addWidget(self.tune_lbl)
        self.tune_row = QWidget()
        self.tune_row.setLayout(tune)
        grid.addWidget(self.tune_row, 0, 0, 1, 2)
        self.checks: dict[str, QCheckBox] = {}
        labels = {"perf": tr("Competitive mode"), "angle": tr("Angle snapping")}
        tips = {"perf": tr("Runs the sensor at full performance."),
                "fps": tr("Only available in competitive mode."),
                "angle": tr("Straightens slightly crooked mouse movements.")}
        cells = {"motion": (1, 0), "angle": (2, 0), "ripple": (3, 0), "perf": (1, 1), "fps": (2, 1)}
        for key, _addr, label in FLAGS:
            chk = QCheckBox(labels.get(key, label))
            chk.setToolTip(tips.get(key, ""))
            chk.toggled.connect(lambda *_: self._changed())
            grid.addWidget(chk, *cells[key])
            self.checks[key] = chk
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        # "LOD" yazısı üstteki kutucuklarla aynı yerden başlasın (stil kutucuğu biraz içeriden çizer).
        chk = self.checks["motion"]
        opt = QStyleOptionButton()
        chk.initStyleOption(opt)
        indent = chk.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, opt, chk).x()
        # LOD kutusu: "LOD" yazısına uzaklığı, panelin sağ kenarına uzaklığıyla eşit.
        # Sağ boşluk = üstteki sürgünün sağındaki açı değeri kadar + panelin iç kenar payı.
        spacing = tune.spacing()
        if spacing < 0:
            spacing = self.style().layoutSpacing(QSizePolicy.ControlType.Slider, QSizePolicy.ControlType.Label,
                                                 Qt.Orientation.Horizontal)
        right = self.tune_lbl.minimumWidth() + max(0, spacing)
        edge = grid.contentsMargins().right()
        if edge < 0:
            edge = self.style().pixelMetric(QStyle.PixelMetric.PM_LayoutRightMargin)
        lod.setContentsMargins(max(0, indent), 0, right, 0)
        self._lod_gap.changeSize(right + edge - 1, 0)   # -1: panel çerçeve çizgisinin kalınlığı
        lod.invalidate()
        row_h = max(self.lod_combo.sizeHint().height(), self.checks["motion"].sizeHint().height())
        for r in (1, 2, 3):
            grid.setRowMinimumHeight(r, row_h)
        body.addWidget(box)

        # Tuşlar / güç
        # Tuşlar ve güç: iki ayar yan yana, sensör panelindeki gibi iki sütun.
        box = QGroupBox(tr("Buttons and power"))
        grid = QGridLayout(box)
        grid.setHorizontalSpacing(24)
        self.debounce_spin = QSpinBox()
        self.debounce_spin.setSuffix(" ms")
        self.debounce_spin.valueChanged.connect(lambda *_: self._changed())
        self.sleep_combo = QComboBox()
        for v, secs in SLEEP_OPTIONS:
            self.sleep_combo.addItem(sleep_label(secs), v)
        self.sleep_combo.currentIndexChanged.connect(lambda *_: self._changed())
        for col, (label, widget) in enumerate(((tr("Button debounce"), self.debounce_spin),
                                               (tr("Sleep time"), self.sleep_combo))):
            cell = QHBoxLayout()
            cell.addWidget(QLabel(label))
            cell.addSpacing(8)
            cell.addWidget(widget, 1)
            grid.addLayout(cell, 0, col)
            grid.setColumnStretch(col, 1)
        body.addWidget(box)

        box = QGroupBox(tr("Factory reset"))
        fl = QVBoxLayout(box)
        self.reset_btn = QPushButton(tr("Reset the mouse to factory settings"))
        self.reset_btn.setStyleSheet(RESET_CSS)
        self.reset_btn.clicked.connect(self._factory_reset)
        fl.addWidget(self.reset_btn)
        body.addWidget(box)

        # Alt satır: uygulama ayarları | durum (sabit yükseklik) | Vazgeç, Uygula.
        # Durum alanı hep yer kaplar; mesaj ya da "işleniyor" gelince pencere oynamaz.
        foot = QHBoxLayout()
        self.app_btn = QPushButton(tr("App settings"))
        self.app_menu = QMenu(self)
        self.app_btn.setMenu(self.app_menu)
        self._build_app_menu()
        self.discard_btn = QPushButton(tr("Discard"))
        self.discard_btn.clicked.connect(self._discard)
        self.apply_btn = QPushButton(tr("Apply"))
        self.apply_btn.clicked.connect(self._apply)
        self.status = QStackedWidget()
        self.status_lbl = ElidedLabel()
        busy = QWidget()
        bl = QHBoxLayout(busy)
        bl.setContentsMargins(0, 0, 0, 0)
        bar = QProgressBar()
        bar.setRange(0, 0)              # belirsiz: kayan çubuk
        bar.setTextVisible(False)
        bar.setFixedSize(70, 6)
        self.busy_lbl = QLabel(tr("Working…"))
        self.busy_lbl.setStyleSheet("color: gray;")
        bl.addWidget(bar)
        bl.addWidget(self.busy_lbl)
        bl.addStretch(1)
        self.status.addWidget(self.status_lbl)
        self.status.addWidget(busy)
        self.status.setFixedHeight(self.apply_btn.sizeHint().height())
        self._msg_timer = QTimer(self)
        self._msg_timer.setSingleShot(True)
        self._msg_timer.timeout.connect(lambda: self.status_lbl.set_full_text(""))
        self._busy_text: Optional[str] = None     # sıradaki işin adı (Yenileniyor…, Uygulanıyor…)
        self._resetting = False                   # sıradaki "apply" sonucu fabrika ayarlarına ait
        foot.addWidget(self.app_btn)
        foot.addSpacing(8)
        foot.addWidget(self.status, 1)
        foot.addWidget(self.discard_btn)
        foot.addWidget(self.apply_btn)
        root.addLayout(foot)

        # Uygula: Windows vurgu rengi (Qt 6.6+), yazı rengi zemine göre.
        accent = self.palette().color(getattr(QPalette.ColorRole, "Accent", QPalette.ColorRole.Highlight))
        ink = "black" if accent.lightness() > 150 else "white"
        self._apply_css = (f"QPushButton {{ background: {accent.name()}; color: {ink};"
                           f" font-weight: 600; padding: 5px 18px; border-radius: 4px; }}")
        a = f"{accent.red()},{accent.green()},{accent.blue()}"
        self.refresh_btn.setStyleSheet(
            "QPushButton#refreshBtn { border: 1px solid rgba(128,128,128,0.55); border-radius: 15px;"
            " padding: 6px 16px 6px 12px; background: rgba(128,128,128,0.12); }"
            f" QPushButton#refreshBtn:hover {{ border-color: rgb({a}); background: rgba({a},0.18); }}"
            f" QPushButton#refreshBtn:pressed {{ background: rgba({a},0.32); }}"
            " QPushButton#refreshBtn:disabled { color: gray; }")
        self._text_rgb = self.palette().color(QPalette.ColorRole.ButtonText).rgb()
        self.refresh_btn.setIcon(refresh_icon(self._text_rgb))
        # Uygulama ayarları: ok yerine üç çizgi, yazıdan sonra (açılır listelerdeki gibi).
        # Simge yalnızca sağdan-sola düzende sağa geçer; menünün kendisi pencereye bağlı, etkilenmez.
        self.app_btn.setIcon(menu_icon(self._text_rgb, lead=24))
        self.app_btn.setIconSize(QSize(22, 16))   # 24/64 pay ≈ 6 px boşluk
        self.app_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.app_btn.setStyleSheet("QPushButton::menu-indicator { image: none; width: 0px; }")
        self._update_buttons()
        self._fit_width()
        self.resize(self.sizeHint())

    def _build_app_menu(self) -> None:
        """Uygulamaya ait ayarlar (fareye yazılmaz, Uygula beklemez): dil,
        ikonda gösterilen fare rengi, Windows açılınca başlatma, tanıtım."""
        lang_menu = self.app_menu.addMenu(tr("Language"))
        group = QActionGroup(lang_menu)
        system = i18n.LANGUAGES[i18n.system_language()]
        current = i18n.chosen()
        for code, name in [(None, tr("Automatic ({name})", name=system))] + list(i18n.LANGUAGES.items()):
            act = QAction(name, lang_menu, checkable=True)
            act.setChecked(code == current)
            act.triggered.connect(lambda _c, code=code: self.language_changed.emit(code))
            group.addAction(act)
            lang_menu.addAction(act)
        self.color_menu = self.app_menu.addMenu(tr("Mouse icon color"))
        self.autostart_act = QAction(tr("Start with Windows"), self.app_menu, checkable=True)
        self.autostart_act.setChecked(autostart.is_enabled())
        self.autostart_act.toggled.connect(self._set_autostart)
        self.app_menu.addAction(self.autostart_act)
        self.auto_update_act = QAction(tr("Check for updates automatically"), self.app_menu, checkable=True)
        self.auto_update_act.setChecked(prefs.auto_update())
        self.auto_update_act.toggled.connect(prefs.set_auto_update)
        self.app_menu.addAction(self.auto_update_act)
        self.app_menu.addSeparator()
        self.app_menu.addAction(tr("Check for updates"), self.update_requested.emit)
        self.app_menu.addAction(tr("Show introduction"), self.welcome_requested.emit)
        # Kayıt başka yerden (örn. Görev Yöneticisi > Başlangıç) değişmiş olabilir.
        self.app_menu.aboutToShow.connect(
            lambda: self.autostart_act.setChecked(autostart.is_enabled()))

    def _set_autostart(self, on: bool) -> None:
        if not autostart.set_enabled(on):
            self.autostart_act.blockSignals(True)
            self.autostart_act.setChecked(autostart.is_enabled())
            self.autostart_act.blockSignals(False)

    def _fit_width(self) -> None:
        """Kaydırma alanı içeriğin genişliğinden dar olmasın (yatay kaydırma yok).
        Polling rate düğmeleri cihaza göre eklendiği için cihaz değişince de çağrılır."""
        self.ensurePolished()   # stil (düğme en küçük boyutları) uygulanmadan ölçüler yanlış çıkar
        bar = self.style().pixelMetric(self.style().PixelMetric.PM_ScrollBarExtent)
        self.scroll.setMinimumWidth(self.body.minimumSizeHint().width() + bar + 4)

    def sizeHint(self):  # noqa: N802 - Qt adı
        """Tam boy: kaydırma alanı yerine içeriğin kendi yüksekliği sayılır.
        Ekrana sığmazsa tepsi tarafı pencereyi kısaltır, içerik kayar."""
        hint = super().sizeHint()
        # Satır kıran yazılar (fabrika ayarları açıklaması) gerçek genişlikte ölçülsün.
        width = max(self.scroll.viewport().width(), self.body.minimumSizeHint().width())
        body_h = self.body.heightForWidth(width)
        if body_h < 0:
            body_h = self.body.sizeHint().height()
        extra = body_h - self.scroll.sizeHint().height()
        hint.setHeight(hint.height() + max(0, extra) + 4)
        hint.setWidth(max(hint.width(), self.minimumSizeHint().width(), 520))
        return hint

    # ---- kontrol değerleri ----------------------------------------------

    def _read(self) -> dict:
        v = {"rate": self.rate_group.checkedId(), "stages": self.stage_spin.value(),
             "current": self._active_stage, "lod": self.lod_combo.currentData(),
             "tune": self.tune_slider.value(), "debounce": self.debounce_spin.value(),
             "sleep": self.sleep_combo.currentData()}
        for key, chk in self.checks.items():
            v[key] = chk.isChecked()
        for i, card in enumerate(self.dpi_cards):
            v[f"dpi{i}"] = card.spin.value()
        return v

    def _write(self, values: dict) -> None:
        self._loading = True
        try:
            for key, val in values.items():
                if key == "rate":
                    btn = self.rate_group.button(val)
                    if btn is not None:
                        btn.setChecked(True)
                elif key == "stages":
                    self.stage_spin.setValue(val)
                elif key == "current":
                    if 0 <= val < DPI_ROWS:
                        self._active_stage = val
                elif key == "lod":
                    self.lod_combo.setCurrentIndex(self.lod_combo.findData(val))
                elif key == "tune":
                    self.tune_slider.setValue(val)
                elif key == "debounce":
                    self.debounce_spin.setValue(val)
                elif key == "sleep":
                    self.sleep_combo.setCurrentIndex(self.sleep_combo.findData(val))
                elif key in self.checks:
                    self.checks[key].setChecked(val)
                elif key.startswith("dpi"):
                    self.dpi_cards[int(key[3:])].spin.setValue(val)
        finally:
            self._loading = False
        self._refresh_rows()

    def _load(self, cfg: d.MouseConfig) -> None:
        """Fareden okunan ayarları kontrollere koy ve bunları 'değişmemiş' kabul et."""
        values = {"stages": cfg.dpi_stages or 1, "motion": bool(cfg.motion_sync),
                  "angle": bool(cfg.angle_snap), "ripple": bool(cfg.ripple),
                  "perf": bool(cfg.performance_state), "fps": bool(cfg.fps_20k),
                  "tune": cfg.angle_tune or 0}
        for key, val in (("rate", cfg.report_rate), ("current", cfg.current_dpi), ("lod", cfg.lod),
                         ("debounce", cfg.debounce), ("sleep", cfg.sleep_time)):
            if val is not None:
                values[key] = val
        for i in range(DPI_ROWS):
            if cfg.dpis[i] is not None:
                values[f"dpi{i}"] = cfg.dpis[i]
        self._write(values)
        self.tune_row.setEnabled(cfg.angle_tune is not None)
        self._base = self._read()
        self._update_buttons()

    def pending(self) -> dict:
        """Uygulanmamış değişiklikler (kontrol anahtarı -> değer)."""
        return self._diff()

    def restore_pending(self, values: dict) -> None:
        if values and self._base:
            self._write(values)
            self._update_buttons()

    def _diff(self) -> dict:
        if not self._base:
            return {}
        now = self._read()
        diff = {k: v for k, v in now.items() if v != self._base.get(k)}
        # Gizli kademelerin değerleri yazılmaz.
        for i in range(now["stages"], DPI_ROWS):
            diff.pop(f"dpi{i}", None)
        return diff

    # ---- kontrol olayları -----------------------------------------------

    def _changed(self) -> None:
        if not self._loading:
            self._refresh_rows()
            self._update_buttons()

    def _select_stage(self, i: int) -> None:
        """Karta tıklandı: o kademe aktif olsun (Uygula ile fareye yazılır)."""
        if i != self._active_stage:
            self._active_stage = i
            self._changed()

    def _stages_changed(self, n: int) -> None:
        # Seçili kademe gizlenecekse son görünen kademeyi seç.
        if self._active_stage >= n:
            self._active_stage = n - 1
        self._changed()

    def _tune_changed(self, v: int) -> None:
        self.tune_lbl.setText(f"{v}°")
        self._changed()

    def _refresh_rows(self) -> None:
        stages = self.stage_spin.value()
        for i, card in enumerate(self.dpi_cards):
            card.setVisible(i < stages)
            card.set_active(i == self._active_stage)
        self.checks["fps"].setEnabled(self.checks["perf"].isChecked())

    def _update_buttons(self) -> None:
        dirty = bool(self._diff())
        self.apply_btn.setEnabled(dirty)
        self.discard_btn.setEnabled(dirty)
        self.apply_btn.setStyleSheet(self._apply_css if dirty else "")

    # ---- servis olayları ------------------------------------------------

    def _on_device(self, ident: Optional[d.Identity]) -> None:
        """Başlık ve ikon her zaman güncellenir. Kontroller (polling rate
        düğmeleri, LOD listesi, sınırlar) yalnızca başka bir cihaz takıldıysa
        yeniden kurulur: renk değişimi de bu sinyali yayar ve kontrolleri
        yeniden kurmak taslakta sahte bir değişiklik (Uygula vurgusu) bırakırdı."""
        new_dev = self.svc.dev is not self._shown_dev
        self._shown_dev = self.svc.dev
        self.color_menu.menuAction().setEnabled(ident is not None and ident.model.known)
        self.rate_box.set_note(tr("up to {hz} Hz", hz=ident.max_rate) if ident else "")
        if ident is None:
            self.title_lbl.setText(tr("No device found"))
            self.sub_lbl.setText(tr("Plug in the Scyrox dongle or the wired mouse."))
            self.icon_lbl.setPixmap(model_icon(None).pixmap(48, 48))
            self.setWindowIcon(model_icon(None))
        else:
            m = ident.model
            self.title_lbl.setText(m.display_name)
            conn = tr("Wired") if ident.wired else tr("Wireless")
            self.sub_lbl.setText(f"{conn}  ·  {self.svc.dev.ref.product}")
            self.icon_lbl.setPixmap(model_icon(m).pixmap(48, 48))
            self.setWindowIcon(model_icon(m))
            self._fill_colors(ident)
        if ident is not None and new_dev:
            m = ident.model
            self._loading = True
            for b in self.rate_group.buttons():
                self.rate_group.removeButton(b)
                b.deleteLater()
            # Seçili düğme vurgu renginde; yazısı DPI kartlarındaki gibi zemine göre koyu/açık
            accent = self.palette().color(getattr(QPalette.ColorRole, "Accent", QPalette.ColorRole.Highlight))
            checked_css = f"QPushButton:checked {{ color: {'black' if accent.lightness() > 150 else 'white'}; }}"
            for rate in ident.rate_options:
                btn = QPushButton(f"{rate}")
                btn.setCheckable(True)
                btn.setStyleSheet(checked_css)
                btn.setMinimumWidth(52)   # Windows stili düğmeyi 80 px'e zorlar; 8 düğme sığsın
                self.rate_group.addButton(btn, rate)
                self.rate_layout.addWidget(btn)
            self.lod_combo.clear()
            for v, label in LOD_OPTIONS[m.layout.name]:
                self.lod_combo.addItem(label, v)
            self.stage_spin.setMaximum(m.max_stages)
            self.debounce_spin.setRange(0, m.max_debounce)
            for card in self.dpi_cards:
                card.spin.setRange(50, m.max_dpi)
            self._loading = False
            self._fit_width()
        if new_dev:
            self._base = {}           # başka cihaz: önceki taslak geçersiz
            self._on_config(self.svc.config)
            if ident is not None and self.isVisible():
                self.svc.refresh()

    def _fill_colors(self, ident: d.Identity) -> None:
        self.color_menu.clear()
        group = QActionGroup(self.color_menu)
        detected = self.svc.detected_color()
        for c in colors_for(ident.model):
            text = color_label(c) + (tr("  (reported by the mouse)") if c == detected else "")
            act = QAction(text, self.color_menu, checkable=True)
            act.setChecked(c == ident.model.color)
            act.triggered.connect(lambda _c, c=c: self.svc.set_color(c))
            group.addAction(act)
            self.color_menu.addAction(act)

    def _on_config(self, cfg: Optional[d.MouseConfig]) -> None:
        ident = self.svc.identity
        enabled = cfg is not None and ident is not None and ident.model.known
        self.body.setEnabled(enabled)
        self.reset_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(ident is not None)
        if ident is None:
            self.banner.hide()
        elif not ident.model.known:
            self.banner.setText(tr("This model is not recognised. Settings cannot be changed for safety."))
            self.banner.show()
        elif cfg is None:
            self.banner.setText(tr("Could not read the settings. The mouse may be asleep: "
                                   "move it and press \"Refresh\"."))
            self.banner.show()
        else:
            self.banner.hide()
        if cfg is None:
            self._update_buttons()
            return
        # Taslakta bekleyen değişiklikleri koru: yeni değerleri yükle, taslağı üstüne koy.
        pending = {k: v for k, v in self._read().items() if self._base and v != self._base.get(k)}
        self._load(cfg)
        if pending:
            self._write(pending)
            self._update_buttons()

    def _on_battery(self, b) -> None:
        if isinstance(b, d.Battery):
            self.batt_lbl.setText(battery_text(b))
            self._set_battery_icon(b.percent)
        else:
            self.batt_lbl.setText(tr("Battery: -"))
            self.batt_icon.clear()

    def _set_battery_icon(self, percent: Optional[int]) -> None:
        dpr = self.devicePixelRatioF()
        height = round(self.batt_lbl.fontMetrics().height() * 0.8 * dpr)
        pm = QPixmap.fromImage(battery_glyph(percent, height))
        pm.setDevicePixelRatio(dpr)
        self.batt_icon.setPixmap(pm)

    def _start(self, busy_text: str) -> None:
        """Pencereden başlatılan işin kısa adı; meşgul satırında görünür."""
        self._busy_text = busy_text

    def _on_busy(self, busy: bool) -> None:
        self.setCursor(Qt.CursorShape.BusyCursor if busy else Qt.CursorShape.ArrowCursor)
        if busy:
            self.busy_lbl.setText(self._busy_text or tr("Working…"))
            if self._busy_text == tr("Refreshing…"):
                self._spin_timer.start()
        else:
            self._busy_text = None
            self._spin_timer.stop()
            self._spin_angle = 0
            self.refresh_btn.setIcon(refresh_icon(self._text_rgb))
        self.status.setCurrentIndex(1 if busy else 0)

    def _spin(self) -> None:
        self._spin_angle = (self._spin_angle + 30) % 360
        self.refresh_btn.setIcon(refresh_icon(self._text_rgb, self._spin_angle))

    def _on_message(self, text: str, kind: str, op: str) -> None:
        """Kısa sonuç, işleme göre ayrı: Uygulandı / Uygulanamadı, Yenilendi /
        Yenilenemedi, Sıfırlandı / Sıfırlanamadı (karışmasınlar: başarılı bir
        yenileme, ayarlar uygulanmış izlenimi vermesin). Ayrıntı ipucunda."""
        if op == "apply" and self._resetting:
            op, self._resetting = "reset", False
        ok = kind == "ok"
        short = {"apply": tr("Settings applied") if ok else tr("Could not apply"),
                 "reset": tr("Mouse reset") if ok else tr("Could not reset"),
                 "refresh": tr("Refreshed") if ok else tr("Could not refresh")}[op]
        self.status_lbl.setStyleSheet("color: #3fae5a;" if kind == "ok" else "color: #e05a4f;")
        self.status_lbl.set_full_text(short)
        self.status_lbl.setToolTip("" if kind == "ok" else text)
        if kind == "ok":
            self._msg_timer.start(MESSAGE_MS)
        else:
            self._msg_timer.stop()      # hata, bir sonraki işleme kadar görünür kalır

    def showEvent(self, e) -> None:  # noqa: N802 - Qt adı
        super().showEvent(e)
        self._fit_width()
        self._refresh()

    def _refresh(self, reason: str = "open") -> None:
        """Fareden yeniden oku. reason: "manual" (Yenile düğmesi), "open"
        (pencere açıldı), "retry" (uygulama başarısız oldu, otomatik)."""
        retry = reason == "retry"
        if self.svc.dev is not None and not retry:   # cihaz yoksa yalnızca tarama yapılır
            self._start(tr("Refreshing…"))
        # Otomatik yenileme sessizdir: alt satırda "Uygulanamadı" kalır, fare
        # uykudaysa bunu sarı uyarı satırı söyler.
        self.svc.refresh(quiet=retry, on_done=lambda ok: self._refresh_done(ok, reason))
        self.svc.query_battery()

    def _refresh_done(self, ok: bool, reason: str) -> None:
        """Başarısızlıkta servis zaten "Başarısız" mesajı gönderir. Başarıda:
        Yenile'ye basıldıysa "Başarılı" göster; pencere açılışında eski mesajı
        temizle; başarısız uygulamanın ardından gelen otomatik yenilemede
        "Başarısız" kalsın (değişiklik yazılamadı), sonraki Yenile onu değiştirir."""
        if not ok or reason == "retry":
            return
        if reason == "manual":
            self._on_message("", "ok", "refresh")
        else:
            self._msg_timer.stop()
            self.status_lbl.set_full_text("")
            self.status_lbl.setToolTip("")

    # ---- uygulama -------------------------------------------------------

    def _steps(self, diff: dict) -> list[tuple[str, Callable[[d.ScyroxDevice], object]]]:
        """Farkları yazma adımlarına çevir. Sıra önemli: kademe sayısı aktif
        kademeden, rekabet modu 20K FPS'ten önce."""
        v = self._read()
        stages = v["stages"]
        steps = []
        if "rate" in diff:
            steps.append((f"Polling rate {v['rate']} Hz", lambda dev, r=v["rate"]: dev.set_report_rate(r)))
        if "stages" in diff:
            steps.append((tr("DPI stages: {n}", n=stages), lambda dev: dev.set_dpi_stages(stages)))
        for i in range(stages):
            if f"dpi{i}" in diff:
                steps.append((tr("Stage {n} DPI", n=i + 1),
                              lambda dev, i=i, x=v[f"dpi{i}"]: dev.set_dpi_value(i, x)))
        if "current" in diff:
            steps.append((tr("Active DPI stage {n}", n=v["current"] + 1),
                          lambda dev, c=v["current"]: dev.set_current_dpi(c, stages)))
        if "lod" in diff:
            steps.append((f"LOD {self.lod_combo.currentText()}", lambda dev, x=v["lod"]: dev.set_lod(x)))
        for key, addr, _label in FLAGS:
            if key in diff:
                text = self.checks[key].text()
                steps.append((f"{text}: {tr('on') if v[key] else tr('off')}",
                              lambda dev, a=addr, on=v[key]: dev.set_flag(a, on)))
        if "tune" in diff:
            steps.append((tr("Sensor angle {n}°", n=v["tune"]), lambda dev, x=v["tune"]: dev.set_angle_tune(x)))
        if "debounce" in diff:
            steps.append((f"Debounce {v['debounce']} ms", lambda dev, x=v["debounce"]: dev.set_debounce(x)))
        if "sleep" in diff:
            steps.append((tr("Sleep time: {t}", t=self.sleep_combo.currentText()),
                          lambda dev, x=v["sleep"]: dev.set_sleep_time(x)))
        return steps

    def _confirm(self, diff: dict) -> bool:
        ident = self.svc.identity
        if diff.get("perf") is True:
            ok = QMessageBox.question(
                self, tr("Competitive mode"),
                tr("In competitive mode the sensor always runs at full performance and the battery "
                   "drains faster.\nTurn it on?"))
            if ok != QMessageBox.StandardButton.Yes:
                return False
        if ident and "debounce" in diff and diff["debounce"] < ident.model.tips_debounce:
            ok = QMessageBox.warning(
                self, "Debounce",
                tr("Below {n} ms the buttons may double-click by themselves.\n"
                   "If that happens, raise the value again. Continue?", n=ident.model.tips_debounce),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ok != QMessageBox.StandardButton.Yes:
                return False
        return True

    def _apply(self) -> bool:
        diff = self._diff()
        if not diff:
            return True
        if not self._confirm(diff):
            return False
        steps = self._steps(diff)

        def run(dev: d.ScyroxDevice) -> None:
            for label, fn in steps:
                try:
                    fn(dev)
                except d.MouseOffline as e:
                    raise d.MouseOffline(f"{label}: {e}") from e
                except Exception as e:  # noqa: BLE001 - hangi adımda kaldığını söyle
                    raise d.DeviceError(f"{label}: {e}") from e

        label = steps[0][0] if len(steps) == 1 else tr("{n} settings", n=len(steps))
        self._start(tr("Applying…"))
        self.svc.apply(label, run, on_fail=lambda: self._refresh("retry"))
        return True

    def _discard(self) -> None:
        if self.svc.config is not None:
            self._load(self.svc.config)

    def _factory_reset(self) -> None:
        ok = QMessageBox.warning(
            self, tr("Factory reset"),
            tr("ALL settings on the mouse (DPI, polling rate, button bindings, macros…) go back to "
               "factory values.\nThis cannot be undone. Continue?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ok == QMessageBox.StandardButton.Yes:
            self._discard()
            self._start(tr("Resetting…"))
            self._resetting = True
            self.svc.apply(tr("Factory reset"), lambda dev: dev.factory_reset(),
                           on_fail=lambda: self._refresh("retry"))

    def confirm_close(self) -> bool:
        """Uygulanmamış değişiklik varsa sor. Kapatılabilirse True."""
        if not self.isVisible() or not self._diff():
            return True
        box = QMessageBox(QMessageBox.Icon.Question, "Scyrox S-App",
                          tr("There are changes that have not been applied."), parent=self)
        apply_b = box.addButton(tr("Apply"), QMessageBox.ButtonRole.AcceptRole)
        discard_b = box.addButton(tr("Discard"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is apply_b:
            return self._apply()
        if box.clickedButton() is discard_b:
            self._discard()
            return True
        return False

    def closeEvent(self, e) -> None:  # noqa: N802 - pencere kapanınca uygulama tepside kalır
        if self.quitting:
            e.accept()   # uygulama kapanıyor; soru tepsideki "Çıkış"ta soruldu
            return
        e.ignore()
        if self.confirm_close():
            self.hide()
