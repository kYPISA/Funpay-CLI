
from __future__ import annotations
from typing import List, Optional

from bs4 import BeautifulSoup

from .models import Category, Lot, Seller


def parse_categories(html: str) -> List[Category]:
    soup = BeautifulSoup(html, "html.parser")
    categories: List[Category] = []

    blocks = soup.find_all("div", class_="counter-list")
    for block in blocks:
        classes = block.get("class", [])
        if "counter-list-pills" not in classes:
            continue
        for a in block.find_all("a", class_="counter-item", href=True):
            href = a["href"]
            inside = a.find("div", class_="inside")
            if not inside:
                continue
            name_div = inside.find("div", class_="counter-param")
            value_div = inside.find("div", class_="counter-value")
            if not name_div:
                continue
            name = name_div.get_text(" ", strip=True)
            count: Optional[int] = None
            if value_div:
                txt = value_div.get_text(" ", strip=True).replace(" ", "")
                if txt.isdigit():
                    try:
                        count = int(txt)
                    except Exception:
                        count = None
            categories.append(Category(name=name, url=href, count=count))

    uniq = {}
    for c in categories:
        key = (c.name.lower(), c.url)
        if key not in uniq:
            uniq[key] = c
    return list(uniq.values())


def _parse_price(text: str) -> float:
    s = text.replace("\xa0", " ").replace(" ", "")
    for bad in ("руб", "₽", "р.", "р"):
        s = s.replace(bad, "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


def parse_lots(html: str) -> List[Lot]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("div", class_="showcase-table")
    if table is None:
        table = soup.find("div", class_="tc")
        if table is None:
            return []

    lots: List[Lot] = []
    rows = table.find_all("a", class_="tc-item", href=True)
    if not rows:
        return lots

    for idx, a in enumerate(rows, start=1):
        classes = a.get("class", [])
        promo = any("offer-promo" in c or "offer-promoted" in c for c in classes)
        pinned = promo

        desc_div = a.find("div", class_="tc-server")
        description = desc_div.get_text(" ", strip=True) if desc_div else ""

        user_div = a.find("div", class_="tc-user")
        seller_name = ""
        years = None
        rating_stars = None
        reviews = None
        online = None

        if user_div:
            name_div = user_div.find("div", class_="media-user-name")
            if name_div:
                seller_name = name_div.get_text(" ", strip=True)
            info_div = user_div.find("div", class_="media-user-info")
            if info_div:
                years = info_div.get_text(" ", strip=True)
            rev_span = user_div.find("span", class_="rating-mini-count")
            if rev_span:
                txt = rev_span.get_text(" ", strip=True).replace(" ", "")
                if txt.isdigit():
                    try:
                        reviews = int(txt)
                    except Exception:
                        reviews = None
            rating_div = user_div.find("div", class_="rating-stars")
            if rating_div:
                full_stars = rating_div.find_all("i", class_="fas")
                rating_stars = len(full_stars) if full_stars else None
            media_block = user_div.find("div", class_="media-user")
            if media_block:
                m_classes = media_block.get("class", [])
                online = any("online" in c for c in m_classes)

        amount_div = a.find("div", class_="tc-amount")
        stock = amount_div.get_text(" ", strip=True) if amount_div else None

        price_div = a.find("div", class_="tc-price")
        price_text = ""
        if price_div:
            inner = price_div.find("div")
            price_text = inner.get_text(" ", strip=True) if inner else price_div.get_text(" ", strip=True)
        price = _parse_price(price_text)
        currency = "₽"
        if "₽" in price_text or "руб" in price_text:
            currency = "₽"

        href = a.get("href", "")

        # читаем атрибуты data-f-* для игры/типа/способа получения
        game_attr = (a.get("data-f-game") or "").strip()
        type_attr = (a.get("data-f-type") or "").strip()
        method_attr = (a.get("data-f-method") or "").strip()

        seller = Seller(
            name=seller_name or "Неизвестно",
            rating_stars=rating_stars,
            reviews=reviews,
            online=online,
            years_on_site=years,
        )

        lots.append(
            Lot(
                id=idx,
                description=description,
                seller=seller,
                stock=stock,
                price=price,
                currency=currency,
                url=href,
                pinned=pinned,
                promo=promo,
                game=game_attr or None,
                type=type_attr or None,
                method=method_attr or None,
            )
        )

    lots.sort(key=lambda l: l.price)
    return lots
