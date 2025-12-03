
from __future__ import annotations
import json
import os
from typing import List, Dict, Any

from .settings import get_base_dir
from .models import Category

_games_cache: List[Dict[str, Any]] | None = None


def _load_games() -> List[Dict[str, Any]]:
    """
    Загружаем games_from_main.json один раз.
    Формат:
    [
      {
        "game": "Roblox",
        "url": "https://funpay.com/chips/99/",
        "offers": [
          {"name": "Робуксы", "url": "..."},
          {"name": "Blox Fruits", "url": "..."},
          ...
        ]
      },
      ...
    ]
    """
    global _games_cache
    if _games_cache is not None:
        return _games_cache

    base_dir = get_base_dir()
    path = os.path.join(base_dir, "games_from_main.json")
    if not os.path.exists(path):
        _games_cache = []
        return _games_cache

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            _games_cache = data
        else:
            _games_cache = []
    except Exception:
        _games_cache = []

    return _games_cache


def search_categories_local(query: str) -> List[Category]:
    """
    Старый вариант поиска: сразу игры+офферы одним списком.
    Сейчас он используется в CLI как фолбэк.
    """
    games = _load_games()
    if not games:
        return []

    q = query.lower()
    results: Dict[str, Category] = {}

    for g in games:
        game_name = g.get("game", "") or ""
        game_url = g.get("url", "") or ""
        offers = g.get("offers") or []

        # совпадение по имени игры
        if q in game_name.lower() and game_url:
            key = game_url
            if key not in results:
                results[key] = Category(name=game_name, url=game_url, count=None)

        # совпадения по предложениям внутри игры
        for off in offers:
            off_name = off.get("name", "") or ""
            off_url = off.get("url", "") or ""
            if not off_url:
                continue

            combo = f"{game_name} {off_name}".lower()
            if q in off_name.lower() or q in combo:
                key = off_url
                cat_name = f"{game_name} — {off_name}"
                if key not in results:
                    results[key] = Category(name=cat_name, url=off_url, count=None)

    return list(results.values())


def find_games(query: str) -> List[Dict[str, Any]]:
    """
    Ищем игры по имени (без офферов).
    """
    games = _load_games()
    q = query.lower()
    return [g for g in games if q in (g.get("game") or "").lower()]


def get_offers_for_game(game_dict: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Возвращаем список офферов (подкатегорий) для игры.
    """
    offers = game_dict.get("offers") or []
    result: List[Dict[str, str]] = []
    for off in offers:
        name = off.get("name", "")
        url = off.get("url", "")
        if not name or not url:
            continue
        result.append({"name": name, "url": url})
    return result
