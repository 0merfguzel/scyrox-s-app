# -*- mode: python -*-
# PyInstaller tarifi. Doğrudan değil, packaging/build.py ile çalıştırın.
import os
import sys

from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                 VarFileInfo, VarStruct, VSVersionInfo)

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 - PyInstaller verir
sys.path.insert(0, ROOT)
from scyrox_sapp import __version__  # noqa: E402

NUMS = tuple(int(x) for x in __version__.split(".")) + (0,)

# Görev Yöneticisi ve "Başlangıç uygulamaları" listesi adı buradan okur.
version = VSVersionInfo(
    ffi=FixedFileInfo(filevers=NUMS, prodvers=NUMS),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("FileDescription", "Scyrox S-App"),
            StringStruct("ProductName", "Scyrox S-App"),
            StringStruct("FileVersion", __version__),
            StringStruct("ProductVersion", __version__),
            StringStruct("InternalName", "ScyroxSApp"),
            StringStruct("OriginalFilename", "ScyroxSApp.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "ScyroxSApp.pyw")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "assets", "icons"), os.path.join("assets", "icons"))],
    # Geliştirme ortamında kurulu ama uygulamanın kullanmadığı büyük paketler
    excludes=["numpy", "cv2", "PIL", "tkinter", "PyInstaller"],
    noarchive=False,
)
# Qt'nin bu uygulamada kullanılmayan büyük parçaları: yazılım OpenGL'i (20 MB,
# 3B çizim yok) ve PDF görüntüleme eklentisi (5 MB).
UNUSED = ("opengl32sw.dll", "qt6pdf.dll", "qpdf.dll")
a.binaries = [b for b in a.binaries if os.path.basename(b[0]).lower() not in UNUSED]

pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ScyroxSApp",
    console=False,                       # tepsi uygulaması: konsol penceresi yok
    icon=os.path.join(ROOT, "packaging", "icons", "ScyroxSApp.ico"),   # beş fare, çiçek gibi
    version=version,
    upx=False,                           # sıkıştırma antivirüs yanlış alarmlarını artırır
)
coll = COLLECT(exe, a.binaries, a.datas, name="ScyroxSApp", upx=False)  # noqa: F821
