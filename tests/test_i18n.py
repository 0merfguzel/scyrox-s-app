"""Her dilde her arayüz metninin karşılığı var mı, yer tutucular tutuyor mu."""

import ast
import glob
import os
import string
import unittest

from scyrox_sapp import i18n
from scyrox_sapp.locales import LANGUAGES, strings
from scyrox_sapp.models import COLORS, MODELS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ui_texts() -> set[str]:
    found = set()
    for path in glob.glob(os.path.join(ROOT, "scyrox_sapp", "*.py")):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "tr"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                found.add(node.args[0].value)
    found |= {name for name, _hex in COLORS.values()}
    found |= {m.name for m in MODELS.values() if not m.name.startswith("V")}
    return found


def fields(text: str) -> set[str]:
    return {name for _lit, name, _spec, _conv in string.Formatter().parse(text) if name}


class TranslationTests(unittest.TestCase):
    def test_every_language_translates_every_text(self):
        wanted = ui_texts()
        for code in LANGUAGES:
            if code == "en":
                continue
            with self.subTest(code):
                table = strings(code)
                self.assertEqual(sorted(wanted - set(table)), [], "eksik")
                self.assertEqual(sorted(set(table) - wanted), [], "kullanılmayan")

    def test_placeholders_match(self):
        for code in LANGUAGES:
            for en, text in strings(code).items():
                self.assertEqual(fields(en), fields(text), (code, en))

    def test_qt_standard_buttons_follow_language(self):
        from PyQt6.QtWidgets import QMessageBox
        old = i18n.LANG
        try:
            texts = {}
            for code in ("tr", "de", "en"):
                i18n.use(code)
                box = QMessageBox()
                box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                texts[code] = box.button(QMessageBox.StandardButton.Yes).text().replace("&", "")
            self.assertEqual(texts, {"tr": "Evet", "de": "Ja", "en": "Yes"})
        finally:
            i18n.use(old)

    def test_language_switch(self):
        old = i18n.LANG
        try:
            i18n.use("en")
            self.assertEqual(i18n.tr("Battery {p}%", p=50), "Battery 50%")
            i18n.use("tr")
            self.assertEqual(i18n.tr("Battery {p}%", p=50), "Pil %50")
            i18n.use("de")
            self.assertEqual(i18n.tr("Battery {p}%", p=50), "Akku 50 %")
        finally:
            i18n.use(old)


class EncodingTests(unittest.TestCase):
    def test_sources_are_clean_utf8(self):
        """UTF-8 metnin ANSI sanılıp yeniden kaydedilmesi ("aÃ§Ä±lÄ±ÅŸ") ekranda bozuk
        karakter olarak görünür; kaynaklarda böyle dizi ya da BOM olmasın."""
        patterns = ("Ã", "Ä°", "Å\u009f", "ÅŸ", "â€", "ğŸ", "\ufeff")
        files = glob.glob(os.path.join(ROOT, "scyrox_sapp", "**", "*.py"), recursive=True)
        files += glob.glob(os.path.join(ROOT, "packaging", "*.*")) + [os.path.join(ROOT, "README.md")]
        for path in files:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for pat in patterns:
                self.assertNotIn(pat, text, path)


if __name__ == "__main__":
    unittest.main()
