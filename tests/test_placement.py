"""Ayarlar penceresi tepsi ikonunun bulunduğu köşede açılır."""

import unittest

from PyQt6.QtCore import QRect

from scyrox_sapp.app import MARGIN, corner_position

W, H = 500, 800


class CornerTests(unittest.TestCase):
    def test_taskbar_on_top(self):          # bu bilgisayardaki gibi
        avail = QRect(0, 32, 1920, 1048)
        p = corner_position(QRect(1401, 0, 24, 32), avail, W, H)
        self.assertEqual((p.x(), p.y()), (1920 - W - MARGIN, 32 + MARGIN))

    def test_taskbar_at_bottom_default(self):
        avail = QRect(0, 0, 1920, 1032)
        p = corner_position(QRect(1700, 1040, 24, 40), avail, W, H)
        self.assertEqual((p.x(), p.y()), (1920 - W - MARGIN, 1032 - H - MARGIN))

    def test_taskbar_on_left(self):
        avail = QRect(60, 0, 1860, 1080)
        p = corner_position(QRect(10, 1000, 40, 24), avail, W, H)
        self.assertEqual((p.x(), p.y()), (60 + MARGIN, 1080 - H - MARGIN))

    def test_unknown_icon_position_uses_bottom_right(self):
        avail = QRect(0, 0, 1366, 728)
        p = corner_position(QRect(), avail, W, 600)
        self.assertEqual((p.x(), p.y()), (1366 - W - MARGIN, 728 - 600 - MARGIN))

    def test_second_monitor_on_the_left(self):
        avail = QRect(-1920, 40, 1536, 832)
        p = corner_position(QRect(-500, 0, 24, 40), avail, W, H)
        self.assertEqual(p.x(), -1920 + 1536 - W - MARGIN)
        self.assertEqual(p.y(), 40 + MARGIN)

    def test_never_above_or_left_of_screen(self):
        avail = QRect(0, 0, 400, 300)                  # pencereden küçük ekran
        p = corner_position(QRect(390, 290, 10, 10), avail, W, H)
        self.assertEqual((p.x(), p.y()), (0, 0))


if __name__ == "__main__":
    unittest.main()
