"""Yayın sürümünü derle.

    python packaging/build.py                 # Masaüstü'ne
    python packaging/build.py D:\\Yayın        # başka bir klasöre

Çıktılar:
  <hedef>\\ScyroxSApp\\ScyroxSApp.exe (+ _internal): kurulumsuz sürüm; klasör
      olduğu gibi taşınabilir.
  <hedef>\\ScyroxSApp-<sürüm>-portable.zip: aynı klasörün zip'i (yayına eklenir).
  <hedef>\\ScyroxSApp-<sürüm>-Setup.exe: kurulum. GitHub'da yayına bu dosya
      eklenir; uygulama içi güncelleme adı "-Setup.exe" ile biten dosyayı arar.
      Inno Setup 6 kurulu değilse bu adım atlanır.
Ara dosyalar depo içindeki build\\ klasörüne yazılır (git'e girmez).
PyInstaller gerekir: pip install pyinstaller
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from scyrox_sapp import __version__  # noqa: E402


def find_iscc() -> str | None:
    """Inno Setup derleyicisi: PATH, makine geneli ya da kullanıcıya kurulu."""
    candidates = [shutil.which("iscc")]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        if base:
            candidates.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    return next((c for c in candidates if c and os.path.isfile(c)), None)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~"), "Desktop")
    cmd = [sys.executable, "-m", "PyInstaller", os.path.join(HERE, "ScyroxSApp.spec"),
           "--noconfirm", "--clean",
           "--distpath", target,
           "--workpath", os.path.join(ROOT, "build")]
    print(" ".join(cmd))
    code = subprocess.call(cmd, cwd=ROOT)
    if code != 0:
        return code
    print("\nHazır:", os.path.join(target, "ScyroxSApp", "ScyroxSApp.exe"))
    shutil.copy(os.path.join(ROOT, "LICENSE"), os.path.join(target, "ScyroxSApp", "LICENSE.txt"))
    archive = shutil.make_archive(os.path.join(target, f"ScyroxSApp-{__version__}-portable"), "zip",
                                  root_dir=target, base_dir="ScyroxSApp")
    print("Hazır:", archive)

    iscc = find_iscc()
    if iscc is None:
        print("Inno Setup 6 bulunamadı: kurulum dosyası atlandı (winget install JRSoftware.InnoSetup)")
        return 0
    code = subprocess.call([iscc, "/Q",
                            f"/DAppVersion={__version__}",
                            f"/DSourceDir={os.path.join(target, 'ScyroxSApp')}",
                            f"/DOutputDir={target}",
                            f"/DIconFile={os.path.join(HERE, 'icons', 'V6_white_dongle.ico')}",
                            os.path.join(HERE, "ScyroxSApp.iss")])
    if code == 0:
        print("Hazır:", os.path.join(target, f"ScyroxSApp-{__version__}-Setup.exe"))
    return code


if __name__ == "__main__":
    sys.exit(main())
