"""Güncelleme kontrolü: sürüm karşılaştırma, GitHub cevabı, sessiz/elle bildirim."""

import json
import unittest
from unittest import mock

from scyrox_sapp import update as U


def release_json(tag="v2.1.0", assets=("ScyroxSApp-2.1.0-Setup.exe",), **kw):
    data = {"tag_name": tag, "html_url": "https://github.com/x/y/releases/tag/" + tag,
            "assets": [{"name": n, "browser_download_url": "https://dl/" + n} for n in assets]}
    data.update(kw)
    return json.dumps(data).encode()


class VersionTests(unittest.TestCase):
    def test_compare(self):
        self.assertTrue(U.is_newer("2.0.1", "2.0.0"))
        self.assertTrue(U.is_newer("v2.10.0", "2.9.9"))
        self.assertFalse(U.is_newer("2.0.0", "2.0.0"))
        self.assertFalse(U.is_newer("1.9", "2.0.0"))
        self.assertEqual(U.parse_version("v3.1-beta"), (3, 1))


class ReleaseTests(unittest.TestCase):
    def test_parses_setup_asset(self):
        with mock.patch.object(U, "_get", return_value=release_json()):
            rel = U.latest_release()
        self.assertEqual(rel.version, "2.1.0")
        self.assertEqual(rel.setup_url, "https://dl/ScyroxSApp-2.1.0-Setup.exe")

    def test_without_installer_only_page(self):
        with mock.patch.object(U, "_get", return_value=release_json(assets=("source.zip",))):
            self.assertIsNone(U.latest_release().setup_url)

    def test_no_release_yet(self):
        err = U.urllib.error.HTTPError(U.API_URL, 404, "Not Found", None, None)
        with mock.patch.object(U, "_get", side_effect=err):
            self.assertIsNone(U.latest_release())

    def test_prerelease_ignored(self):
        with mock.patch.object(U, "_get", return_value=release_json(prerelease=True)):
            self.assertIsNone(U.latest_release())


class SelfInstallTests(unittest.TestCase):
    def test_only_installed_exe_updates_itself(self):
        with mock.patch.object(U.sys, "frozen", False, create=True):
            self.assertFalse(U.can_self_install())                       # kaynaktan çalışırken
        with mock.patch.object(U.sys, "frozen", True, create=True):
            with mock.patch.object(U.os.path, "isfile", return_value=False):
                self.assertFalse(U.can_self_install())                   # kurulumsuz (zip) sürüm
            with mock.patch.object(U.os.path, "isfile", return_value=True):
                self.assertTrue(U.can_self_install())                    # kurulumla gelen


class CheckerTests(unittest.TestCase):
    def setUp(self):
        for name in ("set_last_update_check",):
            patch = mock.patch.object(U.prefs, name)
            patch.start()
            self.addCleanup(patch.stop)
        self.c = U.UpdateChecker()
        self.events = []
        self.c.found.connect(lambda r: self.events.append(("found", r.version)))
        self.c.up_to_date.connect(lambda: self.events.append(("latest",)))
        self.c.failed.connect(lambda stage, _e: self.events.append(("failed", stage)))

    def test_newer_found(self):
        self.c._deliver("check", U.Release("9.0.0", "page", None))
        self.assertEqual(self.events, [("found", "9.0.0")])

    def test_up_to_date_only_reported_when_manual(self):
        current = U.Release(U.__version__, "page", None)
        self.c._deliver("check", current)
        self.assertEqual(self.events, [])
        self.c._manual = True
        self.c._deliver("check", current)
        self.assertEqual(self.events, [("latest",)])

    def test_automatic_check_errors_are_silent(self):
        self.c._deliver("check-error", "timeout")
        self.assertEqual(self.events, [])
        self.c._manual = True
        self.c._deliver("check-error", "timeout")
        self.assertEqual(self.events, [("failed", "check")])

    def test_manual_request_during_automatic_check_is_answered(self):
        with mock.patch.object(self.c, "_run"):
            self.c.check()                       # açılıştaki otomatik denetim
            self.c.check(manual=True)            # o sürerken kullanıcı bastı
        self.c._deliver("check", U.Release(U.__version__, "page", None))
        self.assertEqual(self.events, [("latest",)])

    def test_download_errors_always_reported(self):
        self.c._deliver("download-error", "boom")
        self.assertEqual(self.events, [("failed", "download")])

    def test_due_once_a_day_and_can_be_disabled(self):
        with mock.patch.object(U.prefs, "auto_update", return_value=True), \
             mock.patch.object(U.prefs, "last_update_check", return_value=0):
            self.assertTrue(self.c.auto_check_due())
        with mock.patch.object(U.prefs, "auto_update", return_value=True), \
             mock.patch.object(U.prefs, "last_update_check", return_value=U.time.time() - 3600):
            self.assertFalse(self.c.auto_check_due())
        with mock.patch.object(U.prefs, "auto_update", return_value=False), \
             mock.patch.object(U.prefs, "last_update_check", return_value=0):
            self.assertFalse(self.c.auto_check_due())


if __name__ == "__main__":
    unittest.main()
