from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import os
import json
import re
import statistics
import time

import requests

from .settings import get_base_dir
from .logger import log
from .models import Lot

AI_STATS_FILE = os.path.join(get_base_dir(), "ai_stats.json")


@dataclass
class ExternalPrice:
    site: str
    url: str
    price_per_1000: float  # в валюте сайта (например, USD)


def _load_stats():
    if not os.path.exists(AI_STATS_FILE):
        return []
    try:
        return json.load(open(AI_STATS_FILE, "r", encoding="utf-8"))
    except Exception:
        return []


def _save_stats(items):
    json.dump(items, open(AI_STATS_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def fetch_external_robux_prices() -> List[ExternalPrice]:
    """Пытаемся вытащить примерные цены на Robux за 1000 с других сайтов."""
    res: List[ExternalPrice] = []

    url = "https://www.g2a.com/news/features/roblox-price-robux-cost-per-dollar-guide/"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        text = r.text
        pairs = re.findall(r"\$(\d+[.,]?\d*)\s*[–-]\s*([\d,]+)\s*Robux", text)
        per1000 = []
        for dollars, robux in pairs:
            d = float(dollars.replace(",", "."))
            rb = float(robux.replace(",", ""))
            if rb <= 0:
                continue
            per1000.append(d / rb * 1000)
        if per1000:
            avg = statistics.mean(per1000)
            res.append(ExternalPrice("G2A guide", url, avg))
    except Exception as e:
        log(f"AI: ошибка при загрузке внешних цен (G2A): {e}")

    return res


def analyze(funpay_lots: List[Lot]) -> Optional[dict]:
    """
    Универсальный анализ цен на FunPay для ЛЮБОЙ категории.

    Берём все лоты с положительной ценой, режем крайние выбросы
    и считаем минимальную и среднюю цену за 1 лот.
    """
    prices: List[float] = []

    # собираем корректные цены
    for lot in funpay_lots:
        try:
            if lot.price is None:
                continue
            if lot.price <= 0:
                continue
            prices.append(lot.price)
        except Exception:
            continue

    if not prices:
        return None

    prices.sort()

    # лёгкая защита от жёстких выбросов: обрезаем 10% самых дешёвых и дорогих,
    # но только если лотов достаточно много
    n = len(prices)
    if n >= 10:
        trim = max(1, n // 10)
        core = prices[trim : n - trim] or prices
    else:
        core = prices

    fun_min = min(core)
    fun_avg = statistics.mean(core)

    # пока внешние сайты не используем для общих категорий
    ext_avg = None
    externals: List[ExternalPrice] = []

    # берём твою же логику рекомендаций, но уже для "цены за лот"
    rec_low = fun_min * 1.05
    rec_high = fun_avg * 0.95 if fun_avg > fun_min else fun_min * 1.1

    # если статистика подключена — аккуратно сохраняем, но не ломаемся при ошибках
    try:
        stats = _load_stats()
    except Exception:
        stats = None

    if isinstance(stats, list):
        stats.append(
            {
                "ts": time.time(),
                "fun_min": fun_min,
                "fun_avg": fun_avg,
                "ext_avg": ext_avg,
            }
        )
        try:
            _save_stats(stats)
        except Exception as e:
            log(f"AI: ошибка при сохранении статистики: {e}")

    return {
        "fun_min": fun_min,
        "fun_avg": fun_avg,
        "ext_avg": ext_avg,
        "rec_low": rec_low,
        "rec_high": rec_high,
        "externals": [e.__dict__ for e in externals],
    }
