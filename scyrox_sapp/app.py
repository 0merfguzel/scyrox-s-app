"""Uygulama girişi: tepsi simgesi + ayarlar penceresi."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Optional

from PyQt6.QtCore import QDir, QLockFile, QPoint, QRect, QTimer, QUrl
from PyQt6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QPalette, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from . import __version__, autostart, prefs
from . import device as d
from . import i18n
from . import protocol as p
from . import style
from . import update
from .demo import DemoService
from .hotplug import HotplugWatcher
from .i18n import tr
from .icons import battery_icon, gear_icon, model_icon
from .models import LOD_OPTIONS, SLEEP_OPTIONS, sleep_label
from .paths import data_dir
from .service import DeviceService
from .welcome import WelcomeDialog
from .window import SettingsWindow, battery_text

SHOW_BATTERY_MS = 10_000
MARGIN = 12   # pencereyle ekran kenarı / görev çubuğu arası


def corner_position(icon: QRect, avail: QRect, width: int, height: int) -> QPoint:
    """Tepsi ikonuna en yakın köşe: görev çubuğu üstteyse sağ üst, alttaysa
    (Windows varsayılanı) sağ alt, soldaysa sol. İkonun yeri bilinmiyorsa sağ alt.
    `avail` görev çubuğu hariç ekran alanıdır."""
    ref = icon.center() if icon.isValid() else QPoint(avail.right(), avail.bottom())
    if ref.x() >= avail.center().x():
        x = avail.right() + 1 - width - MARGIN
    else:
        x = avail.left() + MARGIN
    if ref.y() < avail.center().y():
        y = avail.top() + MARGIN
    else:
        y = avail.bottom() + 1 - height - MARGIN
    return QPoint(max(avail.left(), x), max(avail.top(), y))


class Tray:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.svc = DeviceService()
        self.window: Optional[SettingsWindow] = None
        self.ident: Optional[d.Identity] = None
        self.last_battery: Optional[d.Battery] = None
        self.querying = False
        self._welcome: Optional[WelcomeDialog] = None
        self.release: Optional[update.Release] = None    # bulunan yeni sürüm
        self._balloon = ""                                # son bildirimin türü (tıklanınca)

        self.tray = QSystemTrayIcon(model_icon(None))
        self.tray.activated.connect(self._on_activated)
        self.tray.messageClicked.connect(self._on_balloon_clicked)
        self.updater = update.UpdateChecker()
        self.updater.found.connect(self._on_update_found)
        self.updater.up_to_date.connect(self._on_up_to_date)
        self.updater.failed.connect(self._on_update_failed)
        self.updater.downloaded.connect(self._run_installer)
        self.revert = QTimer()
        self.revert.setSingleShot(True)
        self.revert.timeout.connect(self._show_idle)

        self._build_menu()
        self.svc.device_changed.connect(self._on_device)
        self.svc.battery_changed.connect(self._on_battery)
        self.svc.config_changed.connect(self._fill_quick)
        self.svc.message.connect(self._on_message)
        self._on_device(None)
        self.tray.show()
        self.hotplug = HotplugWatcher(self.svc.scan)
        self.svc.start(fallback_scan=not self.hotplug.active)

    def _build_menu(self) -> None:
        """Tepsi menüsünü kur (dil değişince yeniden kurulur)."""
        menu = QMenu()
        # Bilgi satırları (gri) ve hemen altında ilk tıklanabilir seçenek: pil ölçümü
        self.model_act = QAction(tr("Searching for device…"))
        self.model_act.setEnabled(False)
        self.batt_act = QAction(tr("Battery: -"))
        self.batt_act.setEnabled(False)
        measure = QAction(tr("Check battery"), triggered=self.measure)
        for a in (self.model_act, self.batt_act, measure):
            menu.addAction(a)
        menu.addSeparator()

        # Hızlı ayarlar: alt menüler üzerine gelince açılır, tek tıkla yazar.
        self.state_act = QAction("")
        self.state_act.setEnabled(False)
        menu.addAction(self.state_act)
        self.rate_menu = menu.addMenu("Polling rate")
        self.dpi_menu = menu.addMenu("DPI")
        self.lod_menu = menu.addMenu("LOD")
        self.sleep_menu = menu.addMenu(tr("Sleep time"))
        self.flag_acts: list[tuple[QAction, p.Addr]] = []
        for addr, label in ((p.Addr.MOTION_SYNC, "Motion Sync"),
                            (p.Addr.ANGLE_SNAP, "Angle snapping"),
                            (p.Addr.RIPPLE, "Ripple control")):
            act = QAction(label, checkable=True)
            act.triggered.connect(lambda on, a=addr, t=label: self.svc.apply(
                f"{t} {tr('on') if on else tr('off')}", lambda dev: dev.set_flag(a, on)))
            menu.addAction(act)
            self.flag_acts.append((act, addr))
        menu.addSeparator()

        # Tüm ayarlar: çark simgesi ve kalın yazıyla diğerlerinden ayrışsın.
        settings = QAction(tr("All settings"), triggered=self.open_settings)
        settings.setIcon(gear_icon(self.app.palette().color(QPalette.ColorRole.WindowText).rgb()))
        font = settings.font()
        font.setBold(True)
        settings.setFont(font)
        # Yeni sürüm bulununca görünür
        self.update_act = QAction("", triggered=self.install_update)
        self.update_act.setFont(font)
        quit_ = QAction(tr("Quit"), triggered=self.quit)
        menu.addAction(settings)
        menu.addAction(self.update_act)
        menu.addSeparator()
        menu.addAction(quit_)
        self._show_update()
        self._actions = [measure, settings, quit_]   # QMenu sahiplenmez; referansı tut
        self._shown_cfg: object = ()
        menu.aboutToShow.connect(self._on_menu_open)
        self.menu = menu
        self.tray.setContextMenu(menu)

    # ---- olaylar --------------------------------------------------------

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.measure()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def _on_device(self, ident: Optional[d.Identity]) -> None:
        self.ident = ident
        self.last_battery = self.svc.battery
        if self.last_battery is None:
            self.batt_act.setText(tr("Battery: -"))
        self.model_act.setText(ident.model.display_name if ident else tr("No device found"))
        self._shown_cfg = ()
        self._fill_quick(self.svc.config)
        self._show_idle()

    # ---- hızlı ayarlar menüsü -------------------------------------------

    def _on_menu_open(self) -> None:
        if self.updater.auto_check_due():     # bilgisayar günlerce açık kalırsa
            self.check_updates()
        # Menü her açıldığında güncel ayarları fareden oku (ayar başka yerden,
        # örn. siteden değişmiş olabilir). Okuma bitince menü kendini günceller.
        if self.svc.identity is None:
            self.svc.scan()   # açılışta cevap vermemiş olabilir; kullanıcı bakarken tekrar dene
            return
        if self.svc.config is None and self.svc.identity.model.known:
            self.state_act.setText(tr("Reading settings…"))
            self.state_act.setVisible(True)
        self.svc.refresh(quiet=True)

    @staticmethod
    def _choice_menu(menu: QMenu, items, current, on_pick) -> None:
        menu.clear()
        group = QActionGroup(menu)
        for value, text in items:
            act = QAction(text, menu, checkable=True)
            act.setChecked(value == current)
            act.triggered.connect(lambda _c, v=value: on_pick(v))
            group.addAction(act)
            menu.addAction(act)

    def _fill_quick(self, cfg: Optional[d.MouseConfig]) -> None:
        ident = self.svc.identity
        usable = cfg is not None and ident is not None and ident.model.known
        for m in (self.rate_menu, self.dpi_menu, self.lod_menu, self.sleep_menu):
            m.menuAction().setVisible(usable)
        for act, _addr in self.flag_acts:
            act.setVisible(usable)
        if ident is None or usable:
            self.state_act.setVisible(False)
        else:
            self.state_act.setText(tr("Unknown model: settings disabled") if not ident.model.known
                                   else tr("Mouse is asleep: move it and reopen the menu"))
            self.state_act.setVisible(True)
        if not usable:
            return
        # Açık bir alt menüyü boş yere yeniden kurmamak için yalnızca değişince doldur.
        key = (ident.mid, cfg.report_rate, cfg.dpi_stages, cfg.current_dpi, tuple(cfg.dpis),
               cfg.lod, cfg.sleep_time, cfg.motion_sync, cfg.angle_snap, cfg.ripple)
        if key == self._shown_cfg:
            return
        self._shown_cfg = key
        apply = self.svc.apply

        rate = cfg.report_rate
        self.rate_menu.setTitle(f"Polling rate: {rate} Hz" if rate else "Polling rate")
        self._choice_menu(self.rate_menu, [(r, f"{r} Hz") for r in ident.rate_options], rate,
                          lambda r: apply(f"Polling rate {r} Hz", lambda dev: dev.set_report_rate(r)))

        stages = min(cfg.dpi_stages or 1, len(cfg.dpis))   # bozuk flash'a karşı
        cur = cfg.current_dpi
        cur_dpi = cfg.dpis[cur] if cur is not None and cur < stages else None
        self.dpi_menu.setTitle(f"DPI: {cur_dpi}" if cur_dpi else "DPI")
        self._choice_menu(self.dpi_menu,
                          [(i, tr("Stage {n}: {dpi} DPI", n=i + 1, dpi=cfg.dpis[i] or "?"))
                           for i in range(stages)], cur,
                          lambda i: apply(tr("Active DPI stage {n}", n=i + 1),
                                          lambda dev: dev.set_current_dpi(i, stages)))

        lods = dict(LOD_OPTIONS[ident.model.layout.name])
        self.lod_menu.setTitle(f"LOD: {lods[cfg.lod]}" if cfg.lod in lods else "LOD")
        self._choice_menu(self.lod_menu, lods.items(), cfg.lod,
                          lambda v: apply(f"LOD {lods[v]}", lambda dev: dev.set_lod(v)))

        sleeps = {v: sleep_label(secs) for v, secs in SLEEP_OPTIONS}
        self.sleep_menu.setTitle(tr("Sleep time: {t}", t=sleeps[cfg.sleep_time])
                                 if cfg.sleep_time in sleeps else tr("Sleep time"))
        self._choice_menu(self.sleep_menu, sleeps.items(), cfg.sleep_time,
                          lambda v: apply(tr("Sleep time: {t}", t=sleeps[v]),
                                          lambda dev: dev.set_sleep_time(v)))

        values = {p.Addr.MOTION_SYNC: cfg.motion_sync, p.Addr.ANGLE_SNAP: cfg.angle_snap,
                  p.Addr.RIPPLE: cfg.ripple}
        for act, addr in self.flag_acts:
            act.setChecked(bool(values[addr]))

    def _on_message(self, text: str, kind: str, _op: str) -> None:
        # Pencere kapalıyken menüden yapılan değişikliklerin hatalarını bildir.
        if kind != "ok" and (self.window is None or not self.window.isVisible()):
            self._notify(text, warning=True)

    def _notify(self, text: str, warning: bool = False, kind: str = "") -> None:
        self._balloon = kind
        icon = QSystemTrayIcon.MessageIcon.Warning if warning else QSystemTrayIcon.MessageIcon.Information
        self.tray.showMessage("Scyrox S-App", text, icon, 8000)

    # ---- güncelleme -------------------------------------------------------

    def check_updates(self, manual: bool = False) -> None:
        self.updater.check(manual)

    def _show_update(self, downloading: bool = False) -> None:
        rel = getattr(self, "release", None)       # tanıtım görüntüsünde yok
        self.update_act.setVisible(rel is not None)
        self.update_act.setEnabled(not downloading)
        if rel is not None:
            self.update_act.setText(tr("Downloading update…") if downloading
                                    else tr("Install update {v}", v=rel.version))

    def _on_update_found(self, rel: update.Release) -> None:
        known = self.release is not None and self.release.version == rel.version
        self.release = rel
        self._show_update()
        if not known:
            self._notify(tr("Version {v} is available. Click to install.", v=rel.version), kind="update")

    def _on_up_to_date(self) -> None:
        self._notify(tr("Scyrox S-App is up to date ({v})", v=__version__))

    def _on_update_failed(self, stage: str, _error: str) -> None:
        self._show_update()
        self._notify(tr("Could not download the update") if stage == "download"
                     else tr("Could not check for updates"), warning=True)

    def _on_balloon_clicked(self) -> None:
        if self._balloon == "update":
            self.install_update()

    def install_update(self) -> None:
        """Kurulumla çalışıyorsak indirip sessizce kur; değilse yayın sayfasını aç."""
        rel = self.release
        if rel is None:
            return
        if update.can_self_install() and rel.setup_url:
            self._show_update(downloading=True)
            self.updater.fetch(rel)
        else:
            QDesktopServices.openUrl(QUrl(rel.page_url))

    def _run_installer(self, path: str) -> None:
        # Kurulum, çalışan uygulamayı kapatır, dosyaları değiştirir ve yeniden açar.
        # Yönetici izni (UAC) gerektirdiği için Popen değil ShellExecute ile başlatılır.
        try:
            os.startfile(path, "open", "/SILENT /SUPPRESSMSGBOXES /NORESTART")
        except OSError as e:
            if getattr(e, "winerror", None) == 1223:     # yönetici izni penceresinde "Hayır"
                self._show_update()
            else:
                self._on_update_failed("download", str(e))
            return
        self.quit()

    def _tooltip(self) -> str:
        name = self.ident.model.display_name if self.ident else tr("Scyrox S-App: no device")
        if self.last_battery:
            return f"{name}  ·  " + tr("Battery {p}%", p=self.last_battery.percent)
        return f"{name}  " + tr("(click for battery)")

    def _show_idle(self) -> None:
        icon = model_icon(self.ident.model if self.ident else None)
        self.tray.setIcon(icon)
        self.app.setWindowIcon(icon)   # pencereler, uyarı kutuları, görev çubuğu
        self.tray.setToolTip(self._tooltip())

    def measure(self) -> None:
        if self.querying:
            return
        self.querying = True
        self.svc.query_battery()

    def _on_battery(self, b) -> None:
        # Pencereden yapılan ölçümler yalnızca metni günceller; ikon sadece tıklayınca değişir.
        clicked, self.querying = self.querying, False
        if isinstance(b, d.Battery):
            self.last_battery = b
            self.batt_act.setText(battery_text(b))
            if clicked or self.revert.isActive():
                self.tray.setIcon(battery_icon(b.percent))
            self.tray.setToolTip(self._tooltip())
        elif clicked:
            self.tray.setIcon(battery_icon(None))
            self.tray.setToolTip(str(b))
        if clicked:
            self.revert.start(SHOW_BATTERY_MS)

    def show_welcome(self) -> None:
        if self._welcome is not None and self._welcome.isVisible():
            self._welcome.raise_()
            self._welcome.activateWindow()
            return
        self._welcome = WelcomeDialog(*demo_menu_picture())
        self._welcome.show()

    def _new_window(self) -> SettingsWindow:
        w = SettingsWindow(self.svc)
        w.language_changed.connect(self._change_language)
        w.welcome_requested.connect(self.show_welcome)
        w.update_requested.connect(lambda: self.check_updates(manual=True))
        return w

    def open_settings(self) -> None:
        if self.window is None:
            self.window = self._new_window()
        w = self.window
        if not w.isVisible():
            self._place_near_tray(w)
            w.show()
            self._place_near_tray(w)      # çerçeve (başlık çubuğu) boyutu gösterince belli olur
        w.raise_()
        w.activateWindow()

    def _place_near_tray(self, w: QWidget) -> None:
        """Pencereyi tepsi ikonunun bulunduğu köşeye koy. Ekrandan uzunsa
        kısalt; ayarlar kısmı kaydırılabilir."""
        icon = self.tray.geometry()
        screen = QGuiApplication.screenAt(icon.center()) if icon.isValid() else None
        avail = (screen or QGuiApplication.primaryScreen()).availableGeometry()
        frame_extra = w.frameGeometry().height() - w.height()   # başlık çubuğu
        w.resize(w.width(), min(w.sizeHint().height(), avail.height() - 2 * MARGIN - frame_extra))
        frame = w.frameGeometry()
        w.move(corner_position(icon, avail, frame.width(), frame.height()))

    def _change_language(self, code) -> None:
        """Dili değiştir: menüyü ve pencereyi yeni dille yeniden kur. Penceredeki
        uygulanmamış değişiklikler ve pencerenin yeri korunur."""
        i18n.choose(code)
        self._build_menu()
        self._on_device(self.ident)
        old = self.window
        pending, pos = old.pending(), old.pos()
        old.quitting = True
        old.close()
        old.deleteLater()
        self.window = self._new_window()
        self.window.restore_pending(pending)
        self.window.move(pos)
        self.window.show()

    def quit(self) -> None:
        if self.window is not None:
            if not self.window.confirm_close():
                return                   # kullanıcı "İptal" dedi
            self.window.quitting = True  # Qt kapanırken pencereye "kapan" der; artık reddetme
        self.tray.hide()
        self.svc.stop()                  # "Uygula" seçildiyse yazma bitene kadar bekler
        self.app.quit()


def _log_unhandled(exc_type, exc, tb) -> None:
    """Yakalanmamış hata: PyQt6 varsayılan olarak uygulamayı kapatır (tepsi
    ikonu kaybolur). Bunun yerine hatayı kaydet, uygulama çalışmaya devam etsin."""
    import traceback
    from datetime import datetime

    try:
        with open(os.path.join(data_dir(), "error.log"), "a", encoding="utf-8") as f:
            f.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} v{__version__}\n")
            traceback.print_exception(exc_type, exc, tb, file=f)
    except OSError:
        pass
    traceback.print_exception(exc_type, exc, tb)


def main() -> int:
    sys.excepthook = _log_unhandled
    if sys.platform == "win32":
        # Kendi kimliğimiz olmazsa Windows görev çubuğunda pencere ikonunu değil,
        # programı açan kısayolun (veya python.exe'nin) ikonunu gösterir.
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ScyroxSApp")
    app = QApplication(sys.argv)
    app.setApplicationName("Scyrox S-App")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    style.install()
    i18n.install_qt_translation()

    lock = QLockFile(os.path.join(QDir.tempPath(), "scyrox-sapp.lock"))
    if not lock.tryLock(100):
        return 0  # zaten çalışıyor

    # Kurulumun sonunda açılırken kurulumda seçilen dil gelir (--lang=tr); arayüz o dille başlasın.
    lang = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--lang=")), None)
    if lang in i18n.LANGUAGES:
        i18n.choose(lang)
    autostart.refresh()      # exe taşındıysa başlangıç kaydındaki yol güncellensin
    tray = Tray(app)  # noqa: F841 - referansı canlı tutmak için
    if "--settings" in sys.argv:
        tray.open_settings()
    if not prefs.welcome_shown():
        QTimer.singleShot(600, tray.show_welcome)
    if tray.updater.auto_check_due():    # açılışta, en fazla günde bir; ağ gelsin diye biraz sonra
        QTimer.singleShot(20_000, tray.check_updates)
    return app.exec()


def demo_menu_picture() -> tuple[QPixmap, dict[str, QRect]]:
    """Tanıtım için tepsi menüsünün görüntüsü (gerçek menü, örnek fareyle) ve
    animasyonda imlecin gideceği satırların menü içindeki yerleri."""
    app = QApplication.instance()
    t = Tray.__new__(Tray)
    # Uygulama ikonunu değiştirmesin diye setWindowIcon etkisiz
    t.app = SimpleNamespace(palette=app.palette, setWindowIcon=lambda _icon: None)
    t.svc = DemoService()
    t.window = None
    t.ident = None
    t.last_battery = None
    t.querying = False
    t.tray = QSystemTrayIcon()      # gösterilmez
    t.revert = QTimer()
    t._build_menu()
    t._on_device(t.svc.identity)
    t._on_battery(t.svc.battery)
    t._fill_quick(t.svc.config)
    t.menu.adjustSize()
    rows = {"rate": t.menu.actionGeometry(t.rate_menu.menuAction()),
            "settings": t.menu.actionGeometry(t._actions[1])}
    return t.menu.grab(), rows
