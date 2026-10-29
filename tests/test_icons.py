"""Pil renkleri ve simgeleri."""

import unittest

from scyrox_sapp.icons import battery_color, battery_glyph


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


if __name__ == "__main__":
    unittest.main()
