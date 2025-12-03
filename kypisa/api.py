from __future__ import annotations
from typing import List
import requests

from bs4 import BeautifulSoup

from .models import Category, Lot
from .parser import parse_categories, parse_lots


class FunPayClient:
    BASE_URL = "https://funpay.com"

    def __init__(self, golden_key: str, user_agent: str | None = None) -> None:
        self.golden_key = golden_key
        self.user_agent = user_agent or "Mozilla/5.0 (Kypisa CLI)"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "cookie": f"golden_key={self.golden_key}",
                "user-agent": self.user_agent,
            }
        )
        self._categories_cache: List[Category] | None = None

    def _absolute_url(self, href: str) -> str:
        if href.startswith("http://") or href.startswith("https://"):
            return href
        if not href:
            return self.BASE_URL
        if not href.startswith("/"):
            href = "/" + href
        return self.BASE_URL + href

    def get_lots_by_url(self, url: str) -> List[Lot]:
        """
        Загружает лоты по ЛЮБОЙ странице FunPay с витриной:
        просто даём URL категории/игры.
        """
        abs_url = self._absolute_url(url)
        r = self.session.get(abs_url, timeout=20)
        r.raise_for_status()
        lots = parse_lots(r.text)
        for lot in lots:
            lot.url = self._absolute_url(lot.url)
        return lots

    def get_username(self) -> str | None:
        try:
            r = self.session.get(self.BASE_URL + "/", timeout=10)
            r.raise_for_status()
        except Exception:
            return None

        soup = BeautifulSoup(r.text, "html.parser")
        link = soup.find("a", href=lambda h: h and "/users/" in h)
        if link:
            text = link.get_text(strip=True)
            return text or None
        return None

    def fetch_categories(self) -> List[Category]:
        if self._categories_cache is not None:
            return self._categories_cache

        url = self.BASE_URL + "/chips/99/"
        r = self.session.get(url, timeout=20)
        r.raise_for_status()
        cats = parse_categories(r.text)
        for c in cats:
            c.url = self._absolute_url(c.url)
        self._categories_cache = cats
        return cats

    def search_categories(self, query: str) -> List[Category]:
        cats = self.fetch_categories()
        q = query.lower()

        if any(alias in q for alias in ("roblox", "робл", "робукс", "robux", "rob ")):
            robux = [c for c in cats if c.name.lower().startswith("робукс")]
            if robux:
                return robux

        starts = [c for c in cats if c.name.lower().startswith(q)]
        contains = [c for c in cats if q in c.name.lower() and c not in starts]
        return starts + contains

    def get_lots_for_category(
        self,
        category: Category,
        game: str | None = None,
        type_: str | None = None,
    ) -> List[Lot]:
        """
        Загружает лоты для категории.
        Для страниц типа 'Прочие игры Roblox' можно дополнительно
        указать фильтры 'Игра' (f-game) и 'Тип' (f-type).
        """
        url = self._absolute_url(category.url)

        params: dict[str, str] = {}
        if game:
            params["f-game"] = game
        if type_:
            params["f-type"] = type_

        if params:
            r = self.session.get(url, params=params, timeout=20)
        else:
            r = self.session.get(url, timeout=20)

        r.raise_for_status()
        lots = parse_lots(r.text)
        for lot in lots:
            lot.url = self._absolute_url(lot.url)
        return lots

    def search_categories(self, query: str) -> List[Category]:
        cats = self.fetch_categories()
        q = query.lower()

        if any(alias in q for alias in ("roblox", "робл", "робукс", "robux", "rob ")):
            robux = [c for c in cats if c.name.lower().startswith("робукс")]
            if robux:
                return robux

        starts = [c for c in cats if c.name.lower().startswith(q)]
        contains = [c for c in cats if q in c.name.lower() and c not in starts]
        return starts + contains
