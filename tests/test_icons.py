"""Pil renkleri ve simgeleri."""

import unittest
from unittest import mock

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon

from scyrox_sapp import icons
from scyrox_sapp.icons import battery_color, battery_glyph, battery_icon, tray_icon


class BatteryColorTests(unittest.TestCase):
    def test_ranges(self):
        red, orange, yellow, light, dark = (battery_color(p).name() for p in (0, 20, 40, 60, 80))
        self.assertEqual(len({red, orange, yellow, light, dark}), 5)
        for p, expected in ((19, red), (39, orange), (59, yellow), (79, light), (100, dark)):
            self.assertEqual(battery_color(p).name(), expected, p)

    def test_glyph_fill_follows_percent(self):
        def filled(p):
            img = battery_glyph(p, 12)
            y = img.height() // 2
            return sum(1 for x in range(img.width()) if img.pixelColor(x, y) == battery_color(p))
        self.assertLess(filled(20), filled(60))
        self.assertLess(filled(60), filled(100))
        self.assertEqual(battery_glyph(None, 12).height(), 12)


def ink_gaps(percent, size):
    """Rakamlarla çerçeve arasındaki boş satır / sütun sayıları: (üst, alt, sol, sağ)."""
    img = icons._battery_image(str(percent), battery_color(percent).rgb(), size)
    b = max(1, size // 16)
    inked = [(x, y) for y in range(b, size - b) for x in range(b, size - b)
             if img.pixelColor(x, y).lightness() > 40]
    xs, ys = [p[0] for p in inked], [p[1] for p in inked]
    return min(ys) - b, size - b - 1 - max(ys), min(xs) - b, size - b - 1 - max(xs)


class BatteryIconTests(unittest.TestCase):
    def test_digits_centered_and_inside(self):
        """Rakamlar her boyutta tam ortada: üst = alt, sol = sağ boşluk; çerçeveye değmez."""
        for percent in (5, 15, 40, 65, 85, 100):
            for size in (16, 20, 24, 32):
                top, bottom, left, right = ink_gaps(percent, size)
                self.assertEqual(top, bottom, (percent, size))
                self.assertLessEqual(abs(left - right), 1, (percent, size))
                self.assertGreaterEqual(min(top, left, right), 1, (percent, size))

    def test_two_digit_numbers_same_height(self):
        heights = set()
        for percent in (15, 40, 65, 85):
            top, bottom, _l, _r = ink_gaps(percent, 16)
            heights.add(16 - 2 - top - bottom)
        self.assertEqual(len(heights), 1)

    def test_drawn_at_requested_pixels(self):
        pm = battery_icon(40).pixmap(QSize(16, 16), 1.25)
        self.assertEqual(pm.width(), 20)                 # büyütülüp küçültülmez, tam boyutta çizilir


class TrayIconTests(unittest.TestCase):
    def test_tray_gets_its_own_size_not_qts(self):
        """%100 monitör + %125 laptop: Qt 16 × 1.25 = 20 px ister; tepsi 16 px gösterir.
        20 px verilirse Windows küçültür, rakamlar kayıp bulanıklaşır."""
        with mock.patch.object(icons, "tray_px", return_value=16):
            pm = tray_icon(battery_icon(40)).pixmap(QSize(16, 16), 1.25)
        self.assertEqual((pm.width(), pm.height()), (16, 16))

    def test_wraps_any_icon(self):
        with mock.patch.object(icons, "tray_px", return_value=20):
            pm = tray_icon(QIcon(battery_icon(85))).pixmap(QSize(16, 16), 1.0)
        self.assertEqual(pm.width(), 20)


if __name__ == "__main__":
    unittest.main()
