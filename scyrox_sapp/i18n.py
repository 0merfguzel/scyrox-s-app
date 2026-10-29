"""Arayüz dili.

Koddaki metinler İngilizce yazılır ve `tr()` ile sarılır; diğer dillerin
karşılıkları scyrox_sapp/locales/<kod>.py içindedir. Karşılığı olmayan metin
İngilizce gösterilir. tests/test_i18n.py her dilde her metnin karşılığı
olduğunu ve {ad} yer tutucularının tuttuğunu denetler.

Seçim sırası: SCYROX_LANG ortam değişkeni > ayarlar penceresinde seçilen dil
> Windows görüntüleme dili (desteklenmiyorsa İngilizce).
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

from . import prefs
from .locales import LANGUAGES, strings


def system_language() -> str:
    """Windows görüntüleme dillerinden desteklenen ilki; yoksa İngilizce."""
    for tag in QLocale.system().uiLanguages():
        code = tag.split("-")[0].lower()
        if code in LANGUAGES:
            return code
    return "en"


def chosen() -> Optional[str]:
    """Kullanıcının seçtiği dil; None: otomatik."""
    code = prefs.language()
    return code if code in LANGUAGES else None


def _initial() -> str:
    forced = os.environ.get("SCYROX_LANG", "").lower()
    if forced in LANGUAGES:
        return forced
    return chosen() or system_language()


LANG = _initial()
_strings = strings(LANG)

# Qt'nin kendi düğme/menü metinleri (Evet/Hayır, Kopyala/Yapıştır…) qtbase_<kod>.qm'den gelir.
_QT_CODES = {"pt": "pt_BR", "zh": "zh_CN"}
_qt_translator: Optional[QTranslator] = None


def install_qt_translation() -> None:
    """Qt'nin standart metinlerini seçili dile çevir (uygulama oluşturulduktan sonra)."""
    global _qt_translator
    app = QCoreApplication.instance()
    if app is None:
        return
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    if LANG == "en":
        return
    translator = QTranslator(app)
    folders = [QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)]
    bundle = getattr(sys, "_MEIPASS", None)          # exe: paketin içindeki kopya
    if bundle:
        folders.append(os.path.join(bundle, "PyQt6", "Qt6", "translations"))
    for folder in folders:
        if translator.load(f"qtbase_{_QT_CODES.get(LANG, LANG)}", folder):
            app.installTranslator(translator)
            _qt_translator = translator
            return


def use(code: str) -> None:
    """Bu oturumda dili değiştir (kaydetmeden)."""
    global LANG, _strings
    LANG = code if code in LANGUAGES else "en"
    _strings = strings(LANG)
    install_qt_translation()


def choose(code: Optional[str]) -> None:
    """Dili seç ve kaydet; None: Windows diline göre."""
    prefs.set_language(code)
    use(code or system_language())


def tr(text: str, **kw) -> str:
    """Metni arayüz diline çevir; {ad} yer tutucuları kw ile doldurulur."""
    text = _strings.get(text, text)
    return text.format(**kw) if kw else text
