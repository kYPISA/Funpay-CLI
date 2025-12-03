from __future__ import annotations

import time
from typing import Optional, List

import os
import json
import requests
from winotify import Notification, audio

from .api import FunPayClient
from .models import Category
from .settings import load_settings, save_settings, get_base_dir
from .logger import log
from . import games_index

SUBS_FILE = os.path.join(get_base_dir(), "tg_subscribers.json")


def _load_subscribers() -> set[str]:
    """Читаем список подписчиков из tg_subscribers.json."""
    subs: set[str] = set()
    if os.path.exists(SUBS_FILE):
        try:
            with open(SUBS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                for x in data:
                    subs.add(str(x))
        except Exception as e:
            log(f"TG_SUB: ошибка чтения {SUBS_FILE}: {e}")
    return subs


def _save_subscribers(subs: set[str]) -> None:
    try:
        with open(SUBS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(subs)), f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"TG_SUB: ошибка записи {SUBS_FILE}: {e}") 


def _collect_subscribers_from_telegram(token: str) -> list[str]:
    """Обновляем список подписчиков через getUpdates и сохраняем.

    Логика:
      * читаем текущий список из файла;
      * через getUpdates берём все chat_id, которые писали боту (/start и т.п.);
      * добавляем их в множество и сохраняем.
    """ 
    subs = _load_subscribers()
    if not token:
        return sorted(list(subs))

    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates", timeout=10
        )
        data = resp.json()
        if data.get("ok") and isinstance(data.get("result"), list):
            for upd in data["result"]:
                msg = upd.get("message") or upd.get("channel_post") or {}
                chat = msg.get("chat") or {}
                cid = chat.get("id")
                if cid is not None:
                    subs.add(str(cid))
    except Exception as e:
        log(f"TG_SUB: ошибка getUpdates: {e}")

    _save_subscribers(subs)
    return sorted(list(subs))




def _parse_stock_amount(stock: str | None) -> str:
    if not stock:
        return "неизвестно"
    return stock.strip()


def _get_chat_ids(raw: str | None) -> List[str]:
    if not raw:
        return []
    parts: List[str] = []
    for chunk in raw.replace(",", " ").split():
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


def _send_telegram(
    lot,
    fun_min_per_1000: float,
    price_floor: float,
    token: str,
    chat_ids: list[str],
) -> None:
    """
    Отправка уведомления в Telegram.

    Токен берётся из аргумента, список chat_id:
      * если передан вручную — используется как есть;
      * если пустой — берём/обновляем подписчиков из tg_subscribers.json
        через getUpdates (все, кто нажали /start у бота).
    """
    if not token:
        # токен пустой — телега выключена
        return

    # авто-режим: chat_ids не задан → берём всех подписчиков
    if not chat_ids:
        chat_ids = _collect_subscribers_from_telegram(token)
        if not chat_ids:
            print("TG: нет подписчиков (никто не нажал /start?).")
            log("TG: нет подписчиков — список пуст.")
            return

    stock_str = _parse_stock_amount(getattr(lot, "stock", None))

    text = (
        "🟢 *Новый самый дешёвый лот на FunPay*\n"
        f"Категория: {getattr(lot, 'description', '')}\n"
        f"Продавец: `{lot.seller.name}`\n"
        f"Цена: *{lot.price:.4f} ₽* за единицу\n"
        f"≈ *{fun_min_per_1000:.2f} ₽* за 1000 (если применимо)\n"
        f"Наличие: *{stock_str}*\n"
        f"Фильтр минимальной цены: *{price_floor:.2f} ₽*\n"
    )
    if getattr(lot, "url", None):
        text += f"\nСсылка: {lot.url}"

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for cid in chat_ids:
        payload = {
            "chat_id": cid,
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            print(f"Пробую отправить уведомление в Telegram, chat_id={cid}...")
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code != 200:
                print(f"TG ERROR {r.status_code}: {r.text}")
                log(f"TG: ошибка отправки ({r.status_code}) для chat_id={cid}: {r.text}")
            else:
                print(f"TG: сообщение успешно отправлено в chat_id={cid}")
        except Exception as e:
            print(f"TG: исключение при отправке в chat_id={cid}: {e}")
            log(f"TG: исключение при отправке в chat_id={cid}: {e}")




def _notify_windows(lot, fun_min_per_1000: float, category_name: str) -> None:
    title = f"FunPay CLI Bot: новый минимум ({category_name})"
    stock_str = _parse_stock_amount(lot.stock)
    msg = (
        f"Продавец: {lot.seller.name}\n"
        f"Цена: {lot.price:.4f} ₽\n"
        f"≈ {fun_min_per_1000:.2f} ₽ за 1000 (если применимо)\n"
        f"Наличие: {stock_str}"
    )

    try:
        toast = Notification(
            app_id="FunPay CLI Bot",
            title=title,
            msg=msg,
            duration="short",
        )
        try:
            toast.set_audio(audio.Default, loop=False)
        except Exception:
            pass

        if lot.url:
            toast.add_actions(label="Открыть лот", launch=lot.url)

        toast.show()
    except Exception as e:
        log(f"NOTIFY: ошибка при показе уведомления: {e}")


def _choose_category(client: FunPayClient) -> Category | None:
    """
    1) Ищем игру по имени (rust, roblox, cs2, ...).
    2) Показываем список игр.
    3) После выбора игры показываем её офферы:
       - Аккаунты / Игровая валюта / Скины / Прочее / Конкретные режимы и т.д.
    4) Возвращаем Category с нужным URL.
    Также поддерживаем прямую ссылку (Custom).
    """
    while True:
        raw_query = input(
            "Введите ИГРУ для мониторинга (rust, roblox, cs2, ...) "
            "ИЛИ прямую ссылку на раздел FunPay: "
        ).strip()
        if not raw_query:
            return None

        # сразу дали ссылку — работаем как Custom
        if raw_query.lower().startswith("http"):
            return Category(name="Custom", url=raw_query, count=None)

        games = games_index.find_games(raw_query)
        if not games:
            print("Игр по такому запросу не нашли. Попробуй иначе или вставь ссылку.")
            continue

        # --- выбор игры ---
        print("\nНайденные игры:")
        for i, g in enumerate(games[:40], start=1):
            print(f"{i}. {g.get('game', '???')}")
        print("0. Отмена")
        raw = input("Выбери игру номером или введи новый запрос / ссылку: ").strip()

        if not raw:
            return None
        if raw.lower().startswith("http"):
            return Category(name="Custom", url=raw, count=None)
        if not raw.isdigit():
            # новый поисковый запрос — крутим цикл заново
            continue

        idx = int(raw)
        if idx == 0:
            return None
        if not (1 <= idx <= len(games[:40])):
            print("Нет такого номера.")
            continue

        game = games[idx - 1]
        game_name = game.get("game", "Игра")
        game_url = game.get("url", "")

        offers = games_index.get_offers_for_game(game)

        # если офферов нет — мониторим саму игру по её URL
        if not offers:
            if not game_url:
                print("У этой игры нет офферов и URL. Попробуй другую.")
                return None
            return Category(name=game_name, url=game_url, count=None)

        # --- выбор оффера (аккаунты / валюта / прочее / режимы и т.п.) ---
        while True:
            print(f"\nИгра: {game_name}")
            print("Что именно мониторить?")
            items: list[tuple[str, str]] = []

            if game_url:
                items.append((game_name, game_url))  # общая категория игры

            for off in offers:
                items.append((off["name"], off["url"]))

            for i, (name, url) in enumerate(items, start=1):
                print(f"{i}. {name}")
            print("0. Отмена")

            choice = input("Выбери номер варианта или вставь другую ссылку: ").strip()
            if not choice:
                return None
            if choice.lower().startswith("http"):
                return Category(name="Custom", url=choice, count=None)
            if not choice.isdigit():
                print("Нужно число или ссылка.")
                continue

            cidx = int(choice)
            if cidx == 0:
                return None
            if not (1 <= cidx <= len(items)):
                print("Нет такого номера.")
                continue

            sel_name, sel_url = items[cidx - 1]
            return Category(name=f"{game_name} — {sel_name}", url=sel_url, count=None)


def watch_cheapest(
    client: FunPayClient,
    category: Category,
    interval_seconds: int = 30,
    price_floor: float = 0.30,
    method_filter: str | None = None,
    tg_token: str | None = None,
    tg_chat_ids: list[str] | None = None,
) -> None:
    token = tg_token or ""
    chat_ids = tg_chat_ids or []

    print("=== Telegram настройки (плагин) ===")
    if not token:
        # вообще нет токена — телега реально выключена
        print("Telegram-уведомления выключены (нет токена).")
    else:
        if chat_ids:
            # обычный режим: токен + конкретные chat_id
            print("Бот настроен. Сообщения будут отправляться в чат(ы):")
            for cid in chat_ids:
                print(f" - chat_id = {cid}")
        else:
            # авто-режим: токен есть, chat_id пустые -> работаем через /start
            print("Токен есть, chat_id не заданы — используется авто-режим.")
            print("Все, кто нажали /start у бота, будут получать уведомления (через список подписчиков).")

    last_best_key: Optional[str] = None

    while True:
        try:
            if category.name == "Custom":
                lots = client.get_lots_by_url(category.url)
            else:
                lots = client.get_lots_for_category(category)
        except Exception as e:
            print(f"Ошибка при загрузке лотов: {e}")
            log(f"NOTIFY: ошибка при загрузке лотов: {e}")
            time.sleep(interval_seconds)
            continue

        # фильтр по минимальной цене
        valid_lots = [l for l in lots if l.price >= price_floor]

        # фильтр по ТИПУ/СПОСОБУ (если задан)
        if method_filter:
            mf = method_filter.lower()
            valid_lots = [
                l
                for l in valid_lots
                if mf in (l.method or "").lower()
                or mf in (l.type or "").lower()
            ]

        if not valid_lots:
            print("Нет валидных лотов (подходящих по цене/способу).")
            time.sleep(interval_seconds)
            continue

        cheapest = min(valid_lots, key=lambda l: l.price)
        fun_min_per_1000 = cheapest.price * 1000
        lot_key = f"{cheapest.seller.name}|{cheapest.price:.6f}|{cheapest.url}"

        if lot_key != last_best_key:
            stock_str = _parse_stock_amount(cheapest.stock)
            print(
                f"Новый самый дешёвый лот: {cheapest.seller.name} "
                f"по {cheapest.price:.4f} ₽ "
                f"(наличие: {stock_str}, ссылка: {cheapest.url})"
            )
            log(
                f"NOTIFY: новый минимум {cheapest.seller.name} "
                f"цена {cheapest.price:.4f}, stock={stock_str}, url={cheapest.url}"
            )
            _notify_windows(cheapest, fun_min_per_1000, category.name)
            _send_telegram(cheapest, fun_min_per_1000, price_floor, token, chat_ids)
            last_best_key = lot_key
        else:
            print("Изменений нет, самый дешёвый тот же.")

        time.sleep(interval_seconds)



def run_notifier() -> None:
    cfg = load_settings()
    if not cfg.get("golden_key") or not cfg.get("user_agent"):
        print("Сначала запусти main.py и введи golden_key и User-Agent.")
        return

    client = FunPayClient(cfg["golden_key"], cfg["user_agent"] or None)

    category = _choose_category(client)
    if category is None:
        print("Мониторинг отменён.")
        return

    try:
        raw = input("Интервал проверки (в секундах, по умолчанию 30): ").strip()
        interval = int(raw) if raw else 30
    except Exception:
        interval = 30
    if interval < 1:
        interval = 1

    try:
        raw_floor = input("Минимальная цена (по умолчанию 0.30): ").strip()
        price_floor = float(raw_floor.replace(",", ".")) if raw_floor else 0.30
    except Exception:
        price_floor = 0.30

    method_filter = input(
        "Тип/способ (например, 'аккаунты', 'валюта', 'трейд', 'почта'; можно оставить пустым): "
    ).strip()
    if not method_filter:
        method_filter = None

    # === Telegram блок с сохранением в config.json ===
    print("\n=== Telegram настройки для этого нотификатора ===")

    existing_token = cfg.get("tg_bot_token") or ""
    existing_chat_raw = cfg.get("tg_chat_id") or ""

    if existing_token:
        print("В конфиге уже есть токен Telegram бота.")
        print("Оставь пустым, чтобы использовать его.")
    print("Если не хотите получать сообщения в Telegram, напишите No вместо токена.")
    tg_token_input = input("Токен Telegram бота (или No, чтобы отключить): ").strip()

    if tg_token_input:
        if tg_token_input.lower() == "no":
            tg_token = ""
            cfg["tg_bot_token"] = ""
            print("Telegram-уведомления отключены для этого нотификатора.")
        else:
            tg_token = tg_token_input
            cfg["tg_bot_token"] = tg_token
    else:
        tg_token = existing_token

    if tg_token:
        if existing_chat_raw:
            print(f"В конфиге уже есть chat_id: {existing_chat_raw}")
            print("Оставь пустым, чтобы использовать их.")
        print("Если оставить поле chat_id пустым, бот будет отправлять сообщения всем, кто нажал /start,")
        print("и сам будет записывать новых пользователей в файл подписчиков.")
        tg_chat_input = input("Chat ID (один или несколько через запятую, можно оставить пустым): ").strip()

        if tg_chat_input:
            tg_chat_raw = tg_chat_input
            cfg["tg_chat_id"] = tg_chat_raw
        else:
            tg_chat_raw = existing_chat_raw
    else:
        # Telegram отключён (токен пустой / No) — чат-ID не спрашиваем
        tg_chat_raw = existing_chat_raw
        print("Telegram-уведомления отключены, ввод chat_id пропущен.")

    # сохраняем в config.json, если что-то поменялось
    save_settings(cfg)

    tg_chat_ids = _get_chat_ids(tg_chat_raw) if (tg_token and tg_chat_raw) else []

    print(f"\nЗапускаю мониторинг '{category.name}' с интервалом {interval} с...")
    watch_cheapest(
        client,
        category,
        interval_seconds=interval,
        price_floor=price_floor,
        method_filter=method_filter,
        tg_token=tg_token,
        tg_chat_ids=tg_chat_ids,
    )
