from __future__ import annotations

from .api import FunPayClient
from .settings import load_settings
from .color import apply_color
from .logger import log
from .cli import run_ai_for_category


def main() -> None:
    cfg = load_settings()
    if not cfg.get("golden_key") or not cfg.get("user_agent"):
        print("Сначала запусти обычный Kypisa CLI (main.py) и введи golden_key и User-Agent в настройках.")
        return

    apply_color(cfg.get("color_code", ""))

    client = FunPayClient(cfg["golden_key"], cfg["user_agent"] or None)
    log("Запуск отдельного ИИ-бота (bot_main)")

    cats = client.search_categories("Робуксы")
    if not cats:
        print("Не нашёл категорию 'Робуксы' для анализа.")
        return
    category = cats[0]
    run_ai_for_category(client, category)
