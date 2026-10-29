"""Testler Türkçe metinlerle ve ekrana pencere açmadan çalışır."""

import os

os.environ.setdefault("SCYROX_LANG", "tr")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication([])
