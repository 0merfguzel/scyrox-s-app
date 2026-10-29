"""Kullanıcı tercihleri (%APPDATA%\\ScyroxSApp\\settings.json).

Tutulanlar: elle seçilen fare rengi, arayüz dili, hoş geldin ekranının
gösterilip gösterilmediği. Dongle seri numarası vermediği için renk anahtarı,
cihazın bildirdiği model kimliğidir (cid:mid).
"""

from __future__ import annotations

import json
import os
from typing import Optional

from .paths import data_dir


def _path() -> str:
    return os.path.join(data_dir(), "settings.json")


def _load() -> dict:
    try:
        with open(_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save(data: dict) -> None:
    try:
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
    except OSError:
        pass


def color_override(cid: int, mid: int) -> Optional[str]:
    return _load().get("colors", {}).get(f"{cid}:{mid}")


def set_color_override(cid: int, mid: int, color: Optional[str]) -> None:
    data = _load()
    colors = data.setdefault("colors", {})
    if color is None:
        colors.pop(f"{cid}:{mid}", None)
    else:
        colors[f"{cid}:{mid}"] = color
    _save(data)


def welcome_shown() -> bool:
    return bool(_load().get("welcome_shown"))


def set_welcome_shown() -> None:
    data = _load()
    data["welcome_shown"] = True
    _save(data)


def auto_update() -> bool:
    return bool(_load().get("auto_update", True))


def set_auto_update(on: bool) -> None:
    data = _load()
    data["auto_update"] = bool(on)
    _save(data)


def last_update_check() -> float:
    return float(_load().get("last_update_check", 0))


def set_last_update_check(when: float) -> None:
    data = _load()
    data["last_update_check"] = when
    _save(data)


def language() -> Optional[str]:
    """Seçilen dil kodu; None: Windows diline göre."""
    return _load().get("language")


def set_language(code: Optional[str]) -> None:
    data = _load()
    if code is None:
        data.pop("language", None)
    else:
        data["language"] = code
    _save(data)
