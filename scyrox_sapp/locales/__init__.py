"""Dil dosyaları. Her modül, İngilizce metin -> çeviri eşlemesi olan STRINGS içerir.

Yeni dil eklemek: <kod>.py dosyasını oluşturup aşağıdaki iki listeye ekleyin;
tests/test_i18n.py eksik metinleri gösterir. (Modüller doğrudan içe aktarılır;
exe paketleyici hepsini görsün.)
"""

from __future__ import annotations

from . import de, es, fr, ja, ko, pt, ru, tr, zh

# Kod -> dilin kendi adı (ayarlar penceresindeki seçicide görünür)
LANGUAGES = {
    "en": "English",
    "tr": "Türkçe",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pt": "Português",
    "ru": "Русский",
    "zh": "简体中文",
    "ja": "日本語",
    "ko": "한국어",
}

_MODULES = {"tr": tr, "de": de, "es": es, "fr": fr, "pt": pt, "ru": ru, "zh": zh, "ja": ja, "ko": ko}


def strings(code: str) -> dict:
    module = _MODULES.get(code)
    return module.STRINGS if module else {}
