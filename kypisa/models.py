
from dataclasses import dataclass
from typing import Optional


@dataclass
class Category:
    name: str
    url: str
    count: Optional[int] = None


@dataclass
class Seller:
    name: str
    rating_stars: Optional[int] = None
    reviews: Optional[int] = None
    online: Optional[bool] = None
    years_on_site: Optional[str] = None


@dataclass
class Lot:
    id: int
    description: str
    seller: Seller
    stock: Optional[str]
    price: float
    currency: str
    url: str = ""
    pinned: bool = False
    promo: bool = False
    game: Optional[str] = None      # игра (data-f-game)
    type: Optional[str] = None      # тип (игровая валюта / аккаунты / предметы / ...)
    method: Optional[str] = None    # способ получения (трейд, почта и т.п.)
