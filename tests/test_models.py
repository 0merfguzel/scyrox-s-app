"""Model / renk tablosu."""

import unittest

from scyrox_sapp.models import colors_for, lookup, with_color


class ColorTests(unittest.TestCase):
    def test_colors_for_model_family(self):
        self.assertEqual(colors_for(lookup(62, 2)), ["black", "white", "blue"])
        self.assertEqual(colors_for(lookup(62, 17)), ["black", "white", "blue", "pink"])
        self.assertEqual(colors_for(lookup(62, 1)), ["black", "white", "yellow"])
        self.assertEqual(colors_for(lookup(62, 5)), colors_for(lookup(62, 17)))

    def test_with_color_keeps_everything_else(self):
        v6 = lookup(62, 2)
        blue = with_color(v6, "blue")
        self.assertEqual(blue.display_name, "Scyrox V6 Mavi")
        self.assertEqual((blue.layout, blue.max_dpi, blue.known), (v6.layout, v6.max_dpi, v6.known))


if __name__ == "__main__":
    unittest.main()
