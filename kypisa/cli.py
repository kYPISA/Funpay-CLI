from __future__ import annotations

import os
from pathlib import Path
from typing import List

from .api import FunPayClient
from .models import Category, Lot
from .settings import load_settings, save_settings, get_base_dir
from .color import apply_color, color_description
from .logger import log
from .utils import greet_time_phrase
from . import ai_bot
from . import games_index
from .balance import fetch_balance

# ---------- цвета ANSI для CLI ----------

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

BLACK   = "\033[30m"
GRAY    = "\033[90m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"

BG_BLUE    = "\033[44m"
BG_YELLOW  = "\033[43m"
BG_MAGENTA = "\033[45m"
BG_GREEN   = "\033[42m"


def _clean_account_name(name: str | None) -> str | None:
    """Убираем лишнее типа 'Профиль' из ника аккаунта FunPay."""
    if not name:
        return None
    txt = name.replace("Профиль", "").strip()
    return txt or None


# ───────────────────── Первичная настройка ─────────────────────


def initial_setup(cfg: dict) -> dict:
    """Первичный запуск: обращение (обязательно), User-Agent, golden_key."""
    os.system("cls")

    print("=== Первичная настройка Kypisa CLI ===")
    print("Если что-то не знаешь — просто нажми Enter, кроме полей, которые нельзя оставить пустыми.\n")

    # Обращение ОБЯЗАТЕЛЬНО
    if not cfg.get("nickname"):
        while True:
            nick = input("Как к вам можно обращаться (обращение нельзя оставить пустым): ").strip()
            if nick:
                cfg["nickname"] = nick
                break
            print("Обращение не может быть пустым, нужно что-то написать.\n")

    # User-Agent ОБЯЗАТЕЛЕН
    if not cfg.get("user_agent"):
        print(
            "\nЧтобы узнать свой User-Agent, просто вбей в браузере: my user agent\n"
            "И скопируй строку, которую тебе покажет сайт."
        )
        while True:
            ua = input("Введите User-Agent (ОБЯЗАТЕЛЬНО): ").strip()
            if ua:
                cfg["user_agent"] = ua
                break
            print("User-Agent не может быть пустым.\n")

    # golden_key ОБЯЗАТЕЛЕН, но без жёсткой онлайн-блокировки
    print(
        "\nКак получить golden_key БЕЗ расширений:\n"
        "  1) Открой funpay.com и войди в аккаунт.\n"
        "  2) Нажми F12 → вкладка Network (Сеть).\n"
        "  3) Обнови страницу (F5) и выбери любой запрос к funpay.com.\n"
        "  4) В правой части найди раздел Cookies / Заголовки.\n"
        "  5) Найди cookie с именем golden_key и скопируй её значение.\n"
    )
    while True:
        gk = input("Введите golden_key (ОБЯЗАТЕЛЬНО, из cookie golden_key): ").strip()
        if not gk:
            print("golden_key не может быть пустым.\n")
            continue

        ok_chars = "abcdefghijklmnopqrstuvwxyz0123456789"
        looks_valid = len(gk) >= 32 and all(c in ok_chars for c in gk)
        if not looks_valid:
            print("Этот golden_key выглядит странно (слишком короткий или есть лишние символы).")
            confirm = input("Использовать всё равно? [y/N]: ").strip().lower()
            if confirm != "y":
                continue

        cfg["golden_key"] = gk

        # Пытаемся в фоне узнать имя аккаунта, но НЕ ломаем настройку, если не получилось
        try:
            test_client = FunPayClient(gk, cfg.get("user_agent"))
            username = _clean_account_name(test_client.get_username())
        except Exception:
            username = None

        if username:
            print(f"Успешно определён аккаунт FunPay: {username}")
            cfg["account_name"] = username
        else:
            print("Не удалось автоматически определить имя аккаунта FunPay.")
            print("Это не страшно: позже бот попробует ещё раз, а ты всё равно можешь работать.")

        break

    save_settings(cfg)
    return cfg


# ───────────────────── Настройки ─────────────────────


def settings_menu(cfg: dict) -> dict:
    while True:
        print("\n=== Настройки Kypisa ===")
        print(f"1 - Обращение (как к вам обращаться): {cfg.get('nickname', 'не задано')}")
        print(
            f"2 - Цвет интерфейса: {cfg.get('color_code') or 'по умолчанию'} "
            f"({color_description(cfg.get('color_code'))})"
        )
        print(f"3 - Логи: {'вкл' if cfg.get('log_enabled', True) else 'выкл'}")
        print("4 - Изменить golden_key")
        print("5 - Изменить User-Agent")
        print("0 - Назад")
        cmd = input("> ").strip()

        if cmd == "1":
            while True:
                new_nick = input("Новое обращение (нельзя пустое): ").strip()
                if new_nick:
                    cfg["nickname"] = new_nick
                    break
                print("Обращение не может быть пустым.")
        elif cmd == "2":
            print("Введите код COLOR (0-9, A-F). Например:")
            print("1 - 'зелёный', 2 - тёмно-зелёный, A - ярко-зелёный.")
            code = input("COLOR код: ").strip().upper()
            if code:
                cfg["color_code"] = code
                apply_color(code)
        elif cmd == "3":
            cfg["log_enabled"] = not cfg.get("log_enabled", True)
        elif cmd == "4":
            print(
                "\nПодсказка по golden_key:\n"
                "  — Открой funpay.com, залогинься.\n"
                "  — F12 → Network → любой запрос к funpay.com.\n"
                "  — В Cookies найди golden_key.\n"
            )
            while True:
                new_gk = input("Новый golden_key (ОБЯЗАТЕЛЬНО): ").strip()
                if not new_gk:
                    print("golden_key не может быть пустым.")
                    continue
                ok_chars = "abcdefghijklmnopqrstuvwxyz0123456789"
                looks_valid = len(new_gk) >= 32 and all(c in ok_chars for c in new_gk)
                if not looks_valid:
                    print("Этот golden_key выглядит странно (слишком короткий или есть лишние символы).")
                    confirm = input("Использовать всё равно? [y/N]: ").strip().lower()
                    if confirm != "y":
                        continue

                cfg["golden_key"] = new_gk

                try:
                    test_client = FunPayClient(new_gk, cfg.get("user_agent"))
                    username = _clean_account_name(test_client.get_username())
                except Exception:
                    username = None
                if username:
                    cfg["account_name"] = username
                    print(f"Успешно определён аккаунт FunPay: {username}")
                else:
                    print("Сохранил новый golden_key, но не смог определить имя аккаунта.")
                break
        elif cmd == "5":
            print(
                "\nЧтобы узнать свой User-Agent, вбей в браузер: my user agent\n"
                "Выбери любой сайт из результатов, скопируй то, что он покажет."
            )
            while True:
                ua = input("Новый User-Agent (нельзя пустой): ").strip()
                if ua:
                    cfg["user_agent"] = ua
                    break
                print("User-Agent не может быть пустым.")
        elif cmd == "0":
            break
        else:
            print("Не понял.")
            continue

        save_settings(cfg)
        print("Сохранено.")
    return cfg


# ───────────────────── Плагины ─────────────────────


def _get_plugins_root() -> Path:
    base_dir = Path(get_base_dir())
    return base_dir / "plugins"


def _discover_plugins() -> list[tuple[str, Path]]:
    plugins_dir = _get_plugins_root()
    if not plugins_dir.exists():
        return []
    res: list[tuple[str, Path]] = []
    for child in plugins_dir.iterdir():
        if child.is_dir():
            res.append((child.name, child))
    res.sort(key=lambda x: x[0].lower())
    return res


def _launch_plugin(name: str, path: Path) -> None:
    bat_candidates = [
        path / "start.bat",
        path / "run.bat",
        path / f"{name}.bat",
    ]
    for bat in bat_candidates:
        if bat.exists():
            print(f"Запускаю плагин '{name}' через {bat.name} ...")
            os.system(f'start "" "{bat}"')
            return

    py_candidates = [
        path / "main.py",
        path / f"{name}.py",
    ]
    for pyfile in py_candidates:
        if pyfile.exists():
            print(f"Запускаю плагин '{name}' (py {pyfile.name}) ...")
            os.system(f'start "" py "{pyfile}"')
            return

    print(
        f"Для плагина '{name}' не найден .bat или .py для запуска.\n"
        f"Создай, например, start.bat или main.py внутри папки '{name}'."
    )


def plugins_menu() -> None:
    plugins = _discover_plugins()
    print("\n=== Плагины (plugins) ===")
    if not plugins:
        print("Папка plugins пуста или не найдена.")
        return

    for i, (name, path) in enumerate(plugins, start=1):
        print(f"{i} - {name}")
    print("0 - Назад")

    while True:
        choice = input("> ").strip()
        if choice in ("0", ""):
            return
        if not choice.isdigit():
            print("Нужно число.")
            continue
        idx = int(choice)
        if not (1 <= idx <= len(plugins)):
            print("Нет такого номера.")
            continue
        name, path = plugins[idx - 1]
        _launch_plugin(name, path)
        return


# ───────────────────── Выбор игры / категории ─────────────────────


def select_category(client: FunPayClient) -> Category | None:
    """
    1) сначала выбираем игру,
    2) потом выбираем, что в ней смотреть (робуксы, аккаунты, режимы и т.п.).
    """
    while True:
        raw_query = input(
            "Введите название ИГРЫ (rust, roblox, cs2, ...) "
            "ИЛИ прямую ссылку на раздел FunPay: "
        ).strip()
        if not raw_query:
            return None

        if raw_query.lower().startswith("http"):
            return Category(name="Custom", url=raw_query, count=None)

        games = games_index.find_games(raw_query)
        if not games:
            print("Игр по такому запросу не нашёл. Попробуй иначе или вставь ссылку.")
            continue

        print("\nНайденные игры:")
        for i, g in enumerate(games[:40], start=1):
            print(f"{i}. {g.get('game', '???')}")
        print("0 - Отмена")
        raw = input("Выбери игру номером или введи новый запрос / ссылку: ").strip()

        if not raw:
            return None
        if raw.lower().startswith("http"):
            return Category(name="Custom", url=raw, count=None)
        if not raw.isdigit():
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
        if not offers:
            if not game_url:
                print("У этой игры нет офферов и URL. Попробуй другую.")
                return None
            return Category(name=game_name, url=game_url, count=None)

        while True:
            print(f"\nИгра: {game_name}")
            print("Что именно показать?")
            items: list[tuple[str, str]] = []

            if game_url:
                items.append((game_name, game_url))

            for off in offers:
                items.append((off["name"], off["url"]))

            for i, (name, url) in enumerate(items, start=1):
                print(f"{i}. {name}")
            print("0 - Отмена")

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


# ───────────────────── Таблица лотов ─────────────────────


def _format_rating(stars: int | None, reviews: int | None) -> str:
    if stars is None:
        if reviews:
            return f"(отзывов: {reviews})"
        return "—"
    s = "★" * stars + "☆" * (5 - stars)
    if reviews is not None:
        return f"{s} ({reviews})"
    return s


def show_lots(lots: List[Lot], nickname: str) -> None:
    if not lots:
        print("Лоты не найдены.")
        return

    print(
        "\n№ | Пр | Закр | Продавец                 | Рейтинг           "
        "| Цена        | Наличие        | Стаж            | Описание"
    )
    print("-" * 130)
    for i, lot in enumerate(lots, start=1):
        promo_flag = "P" if lot.promo else " "
        pin_flag = "*" if lot.pinned else " "
        seller = lot.seller.name[:22].ljust(22)
        rating = _format_rating(lot.seller.rating_stars, lot.seller.reviews).ljust(16)
        price = f"{lot.price:.2f} {lot.currency}".ljust(11)
        stock = (lot.stock or "").ljust(14)
        years = (lot.seller.years_on_site or "—")[:14].ljust(14)
        method = lot.description[:20].ljust(20)
        print(
            f"{i:2d} | {promo_flag}  |  {pin_flag}  | {seller} | {rating} | "
            f"{price} | {stock} | {years} | {method}"
        )
    print("-" * 130)

    while True:
        raw = input(
            "Введите номер лота для шаблона сообщения (или Enter для выхода): "
        ).strip()
        if not raw:
            return
        if not raw.isdigit():
            print("Нужно число.")
            continue
        idx = int(raw)
        if not (1 <= idx <= len(lots)):
            print("Нет такого номера.")
            continue
        lot = lots[idx - 1]
        greet = greet_time_phrase()
        msg = f"{greet}, {lot.seller.name}! Это {nickname} с FunPay."
        print("\n===== Шаблон сообщения =====")
        print(msg)
        print("============================")
        print("Скопируй этот текст и вставь в чат на сайте.")
        if lot.url:
            print(f"Ссылка на лот: {lot.url}")


# ───────────────────── ИИ-анализ ─────────────────────

def run_ai_for_category(client: FunPayClient, category: Category) -> None:
    print(f"Загружаю лоты для: {category.name} ...")
    try:
        lots = client.get_lots_for_category(category)
    except Exception as e:
        print(f"Ошибка при загрузке лотов: {e}")
        log(f"AI: ошибка при загрузке лотов: {e}")
        return

    if not lots:
        print("Лоты не найдены, ИИ нечего анализировать.")
        return

    result = ai_bot.analyze(lots)
    if not result:
        print("ИИ не смог посчитать цены (нет подходящих лотов).")
        return

    # попытаемся взять валюту из первого лота
    currency = lots[0].currency if lots and lots[0].currency else "₽"
    unit_label = "лот"

    print("\n=== ИИ-анализ Kypisa ===")
    print(f"Категория: {category.name}")
    print(f"Мин. цена FunPay:       {result['fun_min']:.4f} {currency} за {unit_label}")
    print(f"Средняя цена FunPay:    {result['fun_avg']:.4f} {currency} за {unit_label}")

    if result.get("rec_low") and result.get("rec_high"):
        print(
            f"Рекомендация ИИ Кипся: {result['rec_low']:.4f} – "
            f"{result['rec_high']:.4f} {currency} за {unit_label}"
        )

    # ищем просто самый дешёвый лот с положительной ценой
    valid_lots = [l for l in lots if l.price and l.price > 0]
    cheapest = min(valid_lots, key=lambda l: l.price) if valid_lots else None
    if cheapest and cheapest.url:
        print("\nСамый дешёвый найденный лот:")
        print(f"  Продавец: {cheapest.seller.name}")
        print(f"  Цена: {cheapest.price:.4f} {cheapest.currency}")
        print(f"  Ссылка: {cheapest.url}")



# ───────────────────── Баланс ─────────────────────


def print_balance_inline(cfg: dict) -> None:
    """Краткий баланс под строкой 'Держу жизнь...' в главном меню."""
    golden_key = cfg.get("golden_key")
    if not golden_key:
        return
    user_agent = cfg.get("user_agent")
    try:
        info = fetch_balance(golden_key, user_agent)
    except Exception:
        print("Баланс: [ошибка получения]")
        return

    print(f"Баланс: ₽ {info.rub:.2f} | $ {info.usd:.2f} | € {info.eur:.2f}")


# ───────────────────── Пчелиный дизайн ─────────────────────


def clear_screen() -> None:
    os.system("cls")


def print_bee_header(cfg: dict) -> None:
    logs = "ON" if cfg.get("log_enabled", True) else "OFF"
    acc_name = cfg.get("account_name") or "—"
    username = cfg.get("nickname") or "—"

    # Верхний баннер
    print(f"{CYAN}╔════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{CYAN}║{RESET}  {BOLD}FunPay CLI Bot — Kypisa Edition{RESET}                                   {CYAN}║{RESET}")
    print(f"{CYAN}╚════════════════════════════════════════════════════════════════════╝{RESET}")
    print(f"{YELLOW}┌────────────────────────────────────────────────────────────────────┐{RESET}")
    print(f"{YELLOW}│{RESET}  {BOLD}ДЕРЖУ ЖИЗНЬ — FUNPAY CLI BOT{RESET}                                      {YELLOW}│{RESET}")
    print(f"{YELLOW}└────────────────────────────────────────────────────────────────────┘{RESET}")
    print()

    # Статусная строка
    print(f"{GREEN}Привет, {BOLD}{username}{RESET}{GREEN}! Добро пожаловать в Kypisa CLI.{RESET}")
    print(f"{BLUE}Аккаунт FunPay:{RESET} {WHITE}{acc_name}{RESET}")
    print(f"{DIM}[User: {username}] [Mode: CLI+Plugins] [Logs: {logs}]{RESET}")
    print()


def print_main_menu(cfg: dict) -> None:
    print(f"{MAGENTA}┌ Главное меню ──────────────────────────────────────────────────────┐{RESET}")
    print(f"{MAGENTA}│{RESET}  1 — Найти игру / предложение и показать лоты                      {MAGENTA}│{RESET}")
    print(f"{MAGENTA}│{RESET}  2 — Настройки Kypisa                                              {MAGENTA}│{RESET}")
    print(f"{MAGENTA}│{RESET}  3 — Аналитика цен (ИИ Кипся)                                      {MAGENTA}│{RESET}")
    print(f"{MAGENTA}│{RESET}  4 — Плагины (Notifier и др.)                                      {MAGENTA}│{RESET}")
    print(f"{MAGENTA}│{RESET}  0 — Выход                                                         {MAGENTA}│{RESET}")
    print(f"{MAGENTA}└────────────────────────────────────────────────────────────────────┘{RESET}")
    print(f"{GREEN}FunPay: CONNECTED{RESET} | {YELLOW}Golden key: OK{RESET} | {BLUE}User-Agent: OK{RESET}")
    print(f"{DIM}Держу жизнь — мониторю самые дешёвые лоты ради тебя 🐝{RESET}")
    print()
    print_balance_inline(cfg)
    print()



# ───────────────────── main ─────────────────────


def main() -> None:
    cfg = load_settings()

    # Если чего-то важного нет — гоним в первичную настройку
    if not cfg.get("golden_key") or not cfg.get("user_agent") or not cfg.get("nickname"):
        cfg = initial_setup(cfg)

    # Цвет по умолчанию: жёлтый текст на чёрном фоне (код E)
    if not cfg.get("color_code"):
        cfg["color_code"] = "E"
        save_settings(cfg)
    apply_color(cfg.get("color_code", ""))

    client = FunPayClient(cfg["golden_key"], cfg.get("user_agent"))

    # Подтягиваем реальное имя аккаунта, если вдруг его ещё нет
    if not cfg.get("account_name"):
        try:
            acc_name = _clean_account_name(client.get_username())
        except Exception:
            acc_name = None
        if acc_name:
            cfg["account_name"] = acc_name
            save_settings(cfg)

    log(
        f"Запуск Kypisa CLI, обращение: {cfg.get('nickname')}, "
        f"аккаунт FunPay: {cfg.get('account_name') or '—'}"
    )

    while True:
        clear_screen()
        print_bee_header(cfg)
        print_main_menu(cfg)
        cmd = input("> ").strip()

        if cmd == "1":
            log("Меню: поиск игры/предложения")
            cat = select_category(client)
            if not cat:
                continue
            log(f"Выбрана категория: {cat.name} ({cat.url})")
            print(f"Загружаю лоты для: {cat.name} ...")
            try:
                lots = client.get_lots_for_category(cat)
            except Exception as e:
                print(f"Ошибка при загрузке лотов: {e}")
                log(f"Ошибка при загрузке лотов: {e}")
                input("\nНажми Enter, чтобы продолжить...")
                continue
            log(f"Загружено лотов: {len(lots)}")
            show_lots(lots, cfg.get("nickname") or "—")
            input("\nНажми Enter, чтобы вернуться в меню...")

        elif cmd == "2":
            log("Открыты настройки")
            cfg = settings_menu(cfg)

        elif cmd == "3":
            log("Открыта аналитика ИИ")

            # Используем общий выбор категории через games_from_main.json
            category = select_category(client)
            if not category:
                print("Категория не выбрана.")
                input("\nНажми Enter, чтобы вернуться в меню...")
                continue

            log(f"ИИ-анализ для категории: {category.name} ({category.url})")
            run_ai_for_category(client, category)
            input("\nНажми Enter, чтобы вернуться в меню...")


        elif cmd == "4":
            log("Открыто меню плагинов")
            plugins_menu()

        elif cmd == "0":
            log("Выход из программы")
            print("Пока, от Кипси :)")
            break

        else:
            print("Не понял команду.")
            input("\nНажми Enter, чтобы вернуться в меню...")


if __name__ == "__main__":
    main()
