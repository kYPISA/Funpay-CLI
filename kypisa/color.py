import os
from typing import Dict


def apply_color(code: str) -> None:
    """Применяем цвет консоли через команду COLOR (Windows)."""
    if not code:
        return
    if os.name != "nt":
        return
    os.system(f"color {code}")


def color_description(code: str) -> str:
    mapping: Dict[str, str] = {
        "0": "чёрный фон",
        "1": "тёмно-синий (у тебя может отображаться как зелёный)",
        "2": "тёмно-зелёный",
        "3": "бирюзовый",
        "4": "тёмно-фиолетовый",
        "5": "тёмно-красный",
        "6": "тёмно-жёлтый",
        "7": "серый (почти стандарт)",
        "8": "тёмно-серый",
        "9": "ярко-синий",
        "A": "ярко-зелёный",
        "B": "ярко-голубой",
        "C": "ярко-красный",
        "D": "розовый",
        "E": "ярко-жёлтый",
        "F": "ярко-белый",
    }
    return mapping.get((code or "").upper(), "по умолчанию")
