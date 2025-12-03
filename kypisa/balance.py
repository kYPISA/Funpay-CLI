from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup


@dataclass
class BalanceInfo:
    rub: float
    usd: float
    eur: float


def _parse_amount(text: str) -> float:
    # '4.42 ₽' -> 4.42 ; '0 $' -> 0.0
    parts = text.strip().split()
    if not parts:
        return 0.0
    num = parts[0].replace(" ", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return 0.0


def fetch_balance(golden_key: str, user_agent: Optional[str]) -> BalanceInfo:
    """
    Получает общий баланс аккаунта с https://funpay.com/account/balance.
    Берёт три значения из .balances-value: RUB, USD, EUR.
    """
    headers = {
        "cookie": f"golden_key={golden_key}; cookie_prefs=1",
        "accept": "*/*",
    }
    if user_agent:
        headers["user-agent"] = user_agent

    url = "https://funpay.com/account/balance"
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    # базовая проверка, что мы залогинены
    user_link = soup.find("div", class_="user-link-name")
    if not user_link:
        raise RuntimeError("Не удалось авторизоваться по golden_key. Проверь, что кука актуальна.")

    vals = soup.find_all(class_="balances-value")
    if len(vals) < 3:
        raise RuntimeError("Не удалось найти блоки с балансами (RUB/USD/EUR). Структура сайта изменилась.")

    rub = _parse_amount(vals[0].get_text(" ", strip=True))
    usd = _parse_amount(vals[1].get_text(" ", strip=True))
    eur = _parse_amount(vals[2].get_text(" ", strip=True))

    return BalanceInfo(rub=rub, usd=usd, eur=eur)
