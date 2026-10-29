"""Protokol kodlayıcı testleri. Örnek baytlar gerçek cihazlardan okundu."""

import unittest

from scyrox_sapp import protocol as p
from scyrox_sapp.device import MouseConfig
from scyrox_sapp.models import lookup


class PacketTests(unittest.TestCase):
    def test_battery_query_matches_v1_app(self):
        # v1 uygulamasının çalışan sorgusu (bayt 2 hariç, o cevapta durum baytı)
        pkt = p.build(p.Cmd.BATTERY)
        self.assertEqual(len(pkt), 17)
        self.assertEqual(pkt[16], (0x55 - sum(pkt[:16])) & 0xFF)

    def test_real_responses_have_valid_checksum(self):
        for hexstr in ("08030000000101b5d7810000000000003b",
                       "0801000000086f22d8aa3e1105000000dd",
                       "08040000000237000f2e000000000000d3"):
            r = p.parse(bytes.fromhex(hexstr))
            self.assertTrue(r.valid, hexstr)

    def test_handshake_fields(self):
        r = p.parse(bytes.fromhex("0801000000086f22d8aa3e1105000000dd"))
        self.assertEqual((r.data[4], r.data[5], r.data[6]), (62, 17, 5))
        self.assertEqual(lookup(62, 17).display_name, "Scyrox V6s Beyaz")

    def test_write_pair_packet(self):
        # site: st(addr, v) -> [7,0,hi,lo,2,v,0x55-v,...]
        pkt = p.build(p.Cmd.WRITE_FLASH, p.Addr.REPORT_RATE, p.pair(1))
        self.assertEqual(list(pkt[:8]), [8, 7, 0, 0, 0, 2, 1, 0x54])


class DpiTests(unittest.TestCase):
    def test_3955_roundtrip_real_bytes(self):
        real = {200: "c700c70000c7", 400: "8f018f010035", 800: "1f031f030011",
                1600: "3f063f0600cb", 3200: "7f0c7f0c003f"}
        for dpi, hexstr in real.items():
            self.assertEqual(p.LAYOUT_3955.encode(dpi).hex(), hexstr)
            self.assertEqual(p.LAYOUT_3955.decode(bytes.fromhex(hexstr)), dpi)

    def test_3950_roundtrip_real_bytes(self):
        real = {400: "07070047", 800: "0f0f0037", 1600: "1f1f0017", 3200: "3f3f00d7", 6400: "7f7f0057"}
        for dpi, hexstr in real.items():
            self.assertEqual(p.LAYOUT_3950.encode(dpi).hex(), hexstr)
            self.assertEqual(p.LAYOUT_3950.decode(bytes.fromhex(hexstr)), dpi)

    def test_high_ranges_roundtrip(self):
        for layout, values in ((p.LAYOUT_3950, (12800, 26000, 30000, 30100, 30200)),
                               (p.LAYOUT_3955, (1234, 26000, 42000, 42002, 50000))):
            for dpi in values:
                self.assertEqual(layout.decode(layout.encode(dpi)), dpi, (layout.name, dpi))

    def test_snap(self):
        self.assertEqual(p.LAYOUT_3950.snap(1630), 1650)
        self.assertEqual(p.LAYOUT_3950.snap(30150), 30200)
        self.assertEqual(p.LAYOUT_3955.snap(1234), 1234)

    def test_corrupt_slot_is_rejected(self):
        self.assertIsNone(p.LAYOUT_3950.decode(bytes.fromhex("07070048")))


class ConfigTests(unittest.TestCase):
    def test_parse_real_flash(self):
        head = bytes.fromhex("10 45 05 50 02 53 00 55 00 55 05 50 07 07 00 47")
        flash = head + b"\xff" * (256 - len(head))
        dpi = bytes.fromhex("c700c70000c7 8f018f010035 1f031f030011 3f063f0600cb 7f0c7f0c003f")
        dpi += b"\xff" * (48 - len(dpi))
        cfg = MouseConfig.parse(flash, dpi, p.LAYOUT_3955)
        self.assertEqual(cfg.report_rate, 2000)
        self.assertEqual(cfg.dpi_stages, 5)
        self.assertEqual(cfg.current_dpi, 2)
        self.assertEqual(cfg.lod, 5)
        self.assertEqual(cfg.dpis[:5], [200, 400, 800, 1600, 3200])
        self.assertIsNone(cfg.debounce)  # 0xFF çiftleri geçersiz


if __name__ == "__main__":
    unittest.main()
