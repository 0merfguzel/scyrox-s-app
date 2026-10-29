"""Windows açılınca başlatma. Gerçek kayıt defterine dokunulmaz: bellekte sahte winreg."""

import unittest
from types import SimpleNamespace
from unittest import mock

from scyrox_sapp import autostart


class FakeRegistry:
    def __init__(self):
        self.values = {}

    def module(self):
        reg = self

        class Key:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def query(_key, name):
            if name not in reg.values:
                raise FileNotFoundError(name)
            return reg.values[name], 1

        def delete(_key, name):
            if name not in reg.values:
                raise FileNotFoundError(name)
            del reg.values[name]

        return SimpleNamespace(
            HKEY_CURRENT_USER=0, KEY_SET_VALUE=2, REG_SZ=1,
            OpenKey=lambda *a: Key(),
            QueryValueEx=query,
            SetValueEx=lambda _k, name, _r, _t, value: reg.values.__setitem__(name, value),
            DeleteValue=delete)


class AutostartTests(unittest.TestCase):
    def setUp(self):
        self.reg = FakeRegistry()
        p = mock.patch.object(autostart, "winreg", self.reg.module())
        p.start()
        self.addCleanup(p.stop)

    def test_enable_and_disable(self):
        self.assertFalse(autostart.is_enabled())
        self.assertTrue(autostart.set_enabled(True))
        self.assertTrue(autostart.is_enabled())
        self.assertEqual(self.reg.values["ScyroxSApp"], autostart.command())
        self.assertTrue(autostart.set_enabled(False))
        self.assertFalse(autostart.is_enabled())
        self.assertTrue(autostart.set_enabled(False))       # zaten kapalıyken de hata yok

    def test_command_points_to_launcher_in_development(self):
        self.assertIn("pythonw.exe", autostart.command())
        self.assertIn("ScyroxSApp.pyw", autostart.command())

    def test_command_is_the_exe_when_packaged(self):
        with mock.patch.object(autostart.sys, "frozen", True, create=True), \
                mock.patch.object(autostart.sys, "executable", r"C:\Apps\Scyrox S-App\ScyroxSApp.exe"):
            self.assertEqual(autostart.command(), r'"C:\Apps\Scyrox S-App\ScyroxSApp.exe"')

    def test_refresh_updates_moved_exe_path(self):
        self.reg.values["ScyroxSApp"] = r'"C:\Old place\ScyroxSApp.exe"'
        autostart.refresh()
        self.assertEqual(self.reg.values["ScyroxSApp"], autostart.command())

    def test_refresh_does_not_enable_by_itself(self):
        autostart.refresh()
        self.assertFalse(autostart.is_enabled())


if __name__ == "__main__":
    unittest.main()
