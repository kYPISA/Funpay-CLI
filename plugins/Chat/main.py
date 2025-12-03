# -*- coding: utf-8 -*-
"""
Плагин чатов FunPay CLI:

- показывает список диалогов;
- показывает сообщения в выбранном чате;
- позволяет отправлять сообщения (через /runner/), как на сайте.
"""

import os
import time
import json
import requests
from typing import List, Dict, Optional

from bs4 import BeautifulSoup

try:
    import winsound
except ImportError:
    winsound = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

try:
    from winotify import Notification, audio
    print("[Chat] winotify: OK (будут Windows-уведомления)")
except ImportError:
    Notification = None
    audio = None
    print("[Chat] winotify: НЕ УСТАНОВЛЕН, уведомлений не будет")


from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup
from html import unescape

BASE_URL = "https://funpay.com"


# ---------- цвета ANSI ----------

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




#--------бебебеб-----

def _clear_screen() -> None:
    """
    Очистить консоль (Windows / Linux).
    """
    try:
        os.system("cls" if os.name == "nt" else "clear")
    except Exception:
        # если по какой-то причине не сработало – просто напечатаем много переводов строк
        print("\n" * 100)


#------------- Звуууууууууууууууууууууууууууууууууууууууууууууууууук------------

def _play_notify() -> None:
    """
    Звуковой сигнал о новом сообщении.
    На Windows используем winsound, в остальном просто '\a'.
    """
    if winsound is not None:
        try:
            winsound.MessageBeep()
            return
        except Exception:
            pass
    # запасной вариант – текстовый "бип"
    print("\a", end="", flush=True)


#----------виндавс-натификаталы-------

def _notify_windows_chat(chat_name: str, last_message: str, chat_url: str) -> None:
    """
    Windows-уведомление о новом сообщении в чате.
    """
    print(f"[Chat] DEBUG: вызываю _notify_windows_chat для {chat_name}: {last_message}")
    if Notification is None:
        print("[Chat] DEBUG: Notification is None, winotify не доступен")
        return  # winotify не установлен или не импортировался

    title = "FunPay CLI: новое сообщение"
    msg = f"{chat_name}: {last_message}"

    try:
        toast = Notification(
            app_id="FunPay CLI Chat",
            title=title,
            msg=msg,
            duration="short",
        )
        try:
            toast.set_audio(audio.Default, loop=False)
        except Exception as e:
            print(f"[Chat] DEBUG: ошибка установки звука уведомления: {e}")

        if chat_url:
            toast.add_actions(label="Открыть чат", launch=chat_url)

        toast.show()
        print("[Chat] DEBUG: toast.show() вызван")
    except Exception as e:
        print(f"[Chat] DEBUG: ошибка при показе уведомления: {e}")




# ---------- утилиты ----------

def _short(text: str, width: int = 60) -> str:
    text = text.replace("\r", " ").replace("\n", " ")
    if len(text) <= width:
        return text
    try:
        return textwrap.shorten(text, width=width, placeholder="…")
    except Exception:
        return text[: width - 1] + "…"


def _input(prompt: str) -> str:
    try:
        return input(prompt)
    except EOFError:
        return ""


# ---------- работа с config.json ----------

def _load_config() -> dict:
    """
    Ищем config.json в корне проекта FunPay CLI и читаем golden_key / user_agent.
    """
    print("[Chat] Ищу config.json...")
    here = os.path.abspath(__file__)
    chat_dir = os.path.dirname(here)
    plugins_dir = os.path.dirname(chat_dir)
    project_root = os.path.dirname(plugins_dir)

    cfg_path = os.path.join(project_root, "config.json")
    print(f"[Chat] Путь до config.json: {cfg_path}")

    if not os.path.exists(cfg_path):
        print("[Chat] Не найден config.json в корне проекта.")
        print("Сначала запусти основной FunPay CLI и настрой golden_key / user_agent.")
        return {}

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"[Chat] Ошибка чтения config.json: {e}")
        return {}

    return cfg


def _make_session(cfg: dict) -> Optional[requests.Session]:
    gk = cfg.get("golden_key") or ""
    ua = cfg.get("user_agent") or "Mozilla/5.0 (FunPay CLI)"

    if not gk:
        print("[Chat] В config.json нет golden_key. Настрой FunPay CLI.")
        return None

    # Чиним user-agent, если там нелатинские символы.
    try:
        ua.encode("latin-1")
    except UnicodeEncodeError:
        try:
            ua = ua.encode("latin-1", "ignore").decode("latin-1")
        except Exception:
            ua = "Mozilla/5.0 (FunPay CLI)"
        if not ua.strip():
            ua = "Mozilla/5.0 (FunPay CLI)"

    print("[Chat] Создаю сессию FunPay...")
    s = requests.Session()

    # Только user-agent в заголовки:
    s.headers.update(
        {
            "user-agent": ua,
        }
    )

    # golden_key кладём как нормальную куку,
    s.cookies.set("golden_key", gk, domain="funpay.com")

    return s



# ---------- список диалогов ----------

def fetch_chat_list(session: requests.Session) -> List[Dict]:
    """
    Забирает список диалогов с https://funpay.com/chat/

    Возвращает список словарей:
        {
            "name": str,
            "last_message": str,
            "time": str,
            "url": str,
            "unread": bool
        }
    """
    url = f"{BASE_URL}/chat/"
    print(f"[Chat] Загружаю список диалогов: {url}")
    resp = session.get(url)
    print(f"[Chat] Ответ /chat/: {resp.status_code}")
    resp.raise_for_status()

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    items: List[Dict] = []

    # пробуем сразу два варианта селектора
    for a in soup.select(".contact-list .contact-item, .contact-item"):
        classes = a.get("class", [])
        unread = "unread" in classes

        name_el = a.select_one(".media-user-name")
        msg_el = a.select_one(".contact-item-message")
        time_el = a.select_one(".contact-item-time")

        name = name_el.get_text(strip=True) if name_el else "???"
        last_message = msg_el.get_text(" ", strip=True) if msg_el else ""
        time_str = time_el.get_text(strip=True) if time_el else ""

        href = a.get("href") or ""
        if href.startswith("http"):
            chat_url = href
        else:
            chat_url = BASE_URL + href

        items.append(
            {
                "name": name,
                "last_message": last_message,
                "time": time_str,
                "url": chat_url,
                "unread": unread,
            }
        )

    if not items:
        # Если вообще ничего не нашли – сохраним HTML, чтобы можно было посмотреть.
        debug_path = os.path.join(os.path.dirname(__file__), "chat_debug.html")
        try:
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[Chat] В списке чатов 0 диалогов. HTML сохранён в {debug_path}")
        except Exception as e:
            print(f"[Chat] Не удалось сохранить chat_debug.html: {e}")

    print(f"[Chat] Найдено диалогов: {len(items)}")
    return items




# ---------- сообщения одного чата ----------

def _extract_app_data(soup: BeautifulSoup) -> dict:
    """
    В <body data-app-data="..."> лежит JSON с csrf-token и userId.
    """
    body = soup.select_one("body")
    if not body:
        return {}

    raw = body.get("data-app-data") or ""
    if not raw:
        return {}

    try:
        decoded = unescape(raw)
        return json.loads(decoded)
    except Exception:
        return {}


def fetch_chat_messages(
    session: requests.Session,
    chat_url: str,
    limit: int = 50,
) -> (List[Dict], Dict):
    """
    Забирает сообщения из конкретного диалога (/chat/?node=...).

    Возвращает (messages, meta).

    messages: список словарей:
        {
            "author": str,
            "time": str,
            "day": str | None,
            "text": str,
        }

    meta:
        {
            "node_id": int,
            "node_name": str,
            "user_id": int,
            "other_id": int | None,
            "csrf_token": str | None,
            "last_message_id": int | None,
            "chat_url": str,
        }
    """
    print(f"[Chat] Загружаю чат: {chat_url}")
    resp = session.get(chat_url)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # данные из div.chat.chat-float
    chat_div = soup.select_one(".chat.chat-float")
    node_id = None
    node_name = None
    other_id = None

    if chat_div:
        try:
            node_id = int(chat_div.get("data-id") or 0)
        except (TypeError, ValueError):
            node_id = None

        node_name = chat_div.get("data-name")  # типа "users-10380273-17799650"
        if node_name and "-" in node_name:
            try:
                other_id = int(node_name.split("-")[-1])
            except ValueError:
                other_id = None

    # csrf-token и userId из data-app-data
    app_data = _extract_app_data(soup)
    csrf_token = app_data.get("csrf-token")
    user_id = app_data.get("userId")

    messages: List[Dict] = []
    last_message_id: Optional[int] = None

    # Каждый .chat-msg-item — одно сообщение
    for item in soup.select(".chat-message-list .chat-msg-item"):
        # id="message-4031282597"
        msg_id_str = item.get("id") or ""
        if msg_id_str.startswith("message-"):
            try:
                mid = int(msg_id_str.replace("message-", ""))
                last_message_id = max(last_message_id or 0, mid)
            except ValueError:
                pass

        # день (типа "30 ноября")
        day_el = item.select_one(".chat-message-list-date .inside")
        day_label = day_el.get_text(strip=True) if day_el else None

        msg_block = item.select_one(".chat-message")
        if not msg_block:
            continue

        author_el = msg_block.select_one(".media-user-name a.chat-msg-author-link")
        time_el = msg_block.select_one(".chat-msg-date")
        text_el = msg_block.select_one(".chat-msg-text")

        if text_el is None:
            continue

        author = author_el.get_text(strip=True) if author_el else "?"
        time_str = time_el.get_text(strip=True) if time_el else ""
        text = text_el.get_text("\n", strip=True)

        messages.append(
            {
                "author": author,
                "time": time_str,
                "day": day_label,
                "text": text,
            }
        )

    if limit and len(messages) > limit:
        messages = messages[-limit:]

    print(f"[Chat] Сообщений в чате: {len(messages)}")

    meta = {
        "node_id": node_id,
        "node_name": node_name,
        "user_id": user_id,
        "other_id": other_id,
        "csrf_token": csrf_token,
        "last_message_id": last_message_id,
        "chat_url": chat_url,
    }

    return messages, meta


# ---------- отправка сообщения ----------

def send_chat_message(
    session: requests.Session,
    meta: Dict,
    content: str,
) -> bool:
    """
    Отправка сообщения через /runner/ так же, как это делает браузер.

    В HAR видно, что:
    - параметр request = JSON: {"action":"chat_message","data":{...}}
    - параметр objects = JSON-массив с orders_counters, chat_node, chat_bookmarks, c-p-u
    """

    csrf_token = meta.get("csrf_token")
    user_id = meta.get("user_id")
    node_name = meta.get("node_name")
    node_id = meta.get("node_id")
    last_message_id = meta.get("last_message_id")
    other_id = meta.get("other_id")
    chat_url = meta.get("chat_url") or f"{BASE_URL}/chat/"

    if not csrf_token or not user_id or not node_name or not node_id:
        print("[Chat] Нет csrf_token / user_id / node_name / node_id — не могу отправить сообщение.")
        return False

    if last_message_id is None:
        last_message_id = 0

    # То, что браузер кладёт в параметр request
    request_obj = {
        "action": "chat_message",
        "data": {
            "node": node_name,
            "last_message": last_message_id,
            "content": content,
        },
    }

    # Минимальный набор объектов, как в HAR:
    objects = [
        {
            "type": "orders_counters",
            "id": str(user_id),
            "tag": "cli-oc",
            "data": False,
        },
        {
            "type": "chat_node",
            "id": node_name,
            "tag": "cli-chat",
            "data": {
                "node": node_name,
                "last_message": last_message_id,
                "content": content,
            },
        },
        {
            "type": "chat_bookmarks",
            "id": str(user_id),
            "tag": "cli-bm",
            "data": [
                [int(node_id), int(last_message_id)],
            ],
        },
        {
            "type": "c-p-u",
            "id": str(other_id) if other_id is not None else "",
            "tag": "cli-cpu",
            "data": False,
        },
    ]

    payload = {
        "objects": json.dumps(objects, separators=(",", ":")),
        "request": json.dumps(request_obj, separators=(",", ":")),
        "csrf_token": csrf_token,
    }

    url = f"{BASE_URL}/runner/"
    headers = {
        "Origin": BASE_URL,
        "Referer": chat_url,
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    print("[Chat] Отправляю сообщение через /runner/...")
    resp = session.post(url, data=payload, headers=headers)
    print(f"[Chat] Ответ сервера: {resp.status_code}")
    print("[Chat] Кусок ответа:", (resp.text or "")[:300].replace("\n", " "))

    return resp.status_code == 200



def show_chat(session: requests.Session, chat_url: str) -> None:
    """
    Показать один диалог и дать возможность писать сообщения.
    """
    while True:
        print(f"\n{YELLOW}[Chat]{RESET} Загружаю диалог...\n")
        try:
            messages, meta = fetch_chat_messages(session, chat_url, limit=100)
        except Exception as e:
            print(f"{RED}[Chat]{RESET} Ошибка при загрузке чата: {e}")
            _input("\nНажми Enter, чтобы вернуться к списку диалогов...")
            return

        if not messages:
            print(f"{YELLOW}[Chat]{RESET} В чате пока нет сообщений.")
        else:
            print(f"{BOLD}{CYAN}======================================================================{RESET}")
            last_day = None
            last_author: str | None = None

            for msg in messages:
                # новая дата
                if msg["day"] and msg["day"] != last_day:
                    print(f"\n{YELLOW}📅 --- {msg['day']} ---{RESET}")
                    last_day = msg["day"]

                # сырое имя автора из парсинга
                raw_author = (msg.get("author") or "").strip()

                # если автор пустой или "?", берем предыдущего
                if not raw_author or raw_author == "?":
                    author = last_author or "?"
                else:
                    author = raw_author

                # определяем, твое ли сообщение
                is_me = author.strip().lower() == "kypisa"

                # запоминаем автора для следующих сообщений
                last_author = author

                if is_me:
                    # твои сообщения – зелёный ник, синий фон
                    header = f"{DIM}{msg['time']}{RESET} {BOLD}{GREEN}{author}{RESET}:"
                    print(header)
                    text = _short(msg["text"], width=200)
                    print(f"{BG_BLUE}{WHITE}  💬 {text}  {RESET}")
                else:
                    # собеседник – фиолетовый ник, розовый фон
                    header = f"{DIM}{msg['time']}{RESET} {BOLD}{MAGENTA}{author}{RESET}:"
                    print(header)
                    text = _short(msg["text"], width=200)
                    print(f"{BG_MAGENTA}{WHITE}  💬 {text}  {RESET}")

                print(f"{DIM}" + "-" * 70 + RESET)

            print(f"{BOLD}{CYAN}======================================================================{RESET}")

        print("\nКоманды:")
        print("  пусто — вернуться к списку диалогов")
        print("  текст — отправить сообщение в этот чат")
        user_text = _input("\nНапиши сообщение (или просто Enter, чтобы выйти из чата): ").strip()

        if not user_text:
            # назад к списку диалогов
            return

        ok = False
        try:
            ok = send_chat_message(session, meta, user_text)
        except Exception as e:
            print(f"{RED}[Chat]{RESET} Ошибка при отправке сообщения: {e}")

        if not ok:
            _input("\nСообщение НЕ отправлено. Нажми Enter, чтобы вернуться в список диалогов...")
            return

        print(f"{GREEN}[Chat]{RESET} Сообщение отправлено, обновляю чат...")




# ---------- основной цикл CLI ----------

def run_chat_cli(session: requests.Session) -> None:
    """
    Главное меню плагина чатов.
    """

    # баннер
    print(r"""
┌────────────────────────┐
│        KYPISA          │
│        CLI Chat        │
└────────────────────────┘
""")

    print(f"\n{BOLD}{YELLOW}=== FunPay / Чаты (плагин Chat) ==={RESET}\n")
    print("Режим отображения диалогов:")
    print("  1 - Все диалоги")
    print("  2 - Только с новыми сообщениями (мониторинг, звук) ✉️")
    mode = _input("Выбери режим (1/2, по умолчанию 1): ").strip()
    if mode not in ("1", "2"):
        mode = "1"

    if mode == "2":
        # режим мониторинга только новых чатов
        monitor_unread_chats(session)
        return

    # ---------- обычный режим: все диалоги ----------

    while True:
        print(f"\n{BOLD}{YELLOW}=== FunPay / Чаты (плагин Chat) ==={RESET}")

        try:
            chats = fetch_chat_list(session)
        except Exception as e:
            print(f"{YELLOW}[Chat]{RESET} Ошибка при загрузке списка диалогов: {e}")
            _input("\nНажми Enter для выхода...")
            return

        if not chats:
            print(f"{YELLOW}[Chat]{RESET} Диалогов не найдено.")
            _input("\nНажми Enter для выхода...")
            return

        for i, ch in enumerate(chats, start=1):
            unread = ch["unread"]
            last = _short(ch["last_message"])
            time_str = f"{DIM}{ch['time']}{RESET}" if ch["time"] else ""

            if unread:
                # непрочитанный чат — жёлтый фон и иконка
                name_part = f"{BG_YELLOW}{BLACK} ✉ {ch['name']} {RESET}"
                line = f"{CYAN}{i:2d}.{RESET} {name_part} {WHITE}{last}{RESET} {time_str}"
            else:
                # обычный чат
                name_part = f"{MAGENTA}{ch['name']}{RESET}"
                if time_str:
                    line = f"{CYAN}{i:2d}.{RESET} [ ] {name_part}: {DIM}{last}{RESET} {time_str}"
                else:
                    line = f"{CYAN}{i:2d}.{RESET} [ ] {name_part}: {DIM}{last}{RESET}"

            print(line)


        print("\n0 - Выход")
        choice = _input("Введите номер диалога: ").strip()

        if not choice:
            continue
        if not choice.isdigit():
            print(f"{YELLOW}[Chat]{RESET} Введи номер или 0.")
            continue

        idx = int(choice)
        if idx == 0:
            print(f"{YELLOW}[Chat]{RESET} Выход из плагина чатов.")
            return

        if not (1 <= idx <= len(chats)):
            print(f"{YELLOW}[Chat]{RESET} Нет диалога с таким номером.")
            continue

        chat = chats[idx - 1]
        show_chat(session, chat["url"])




#-------а зачем код мой читаешь мммммм?-----------

def monitor_unread_chats(session: requests.Session) -> None:
    """
    Мониторинг только чатов с новыми сообщениями.

    Автообновление каждые 5 секунд + неблокирующий ввод:
    - список чатов сам обновляется;
    - можно в любой момент набрать номер и нажать Enter, чтобы зайти в чат;
    - 0 + Enter — выход.
    """

    if msvcrt is None:
        print(f"{YELLOW}[Chat]{RESET} Неблокирующий режим доступен только на Windows. Включаю простой мониторинг.")
        # простой резервный вариант: нужно жать Enter, чтобы обновлять
        simple_monitor_unread_chats(session)
        return

    print(f"\n{BOLD}{YELLOW}Режим мониторинга новых сообщений (✉️){RESET}")
    print("Проверяю новые сообщения каждые 5 секунд.")
    print("В любой момент набери номер диалога и нажми Enter.")
    print("0 + Enter — выход.\n")

    prev_last: dict[str, str] = {}
    last_refresh = 0.0
    input_buffer = ""
    last_unread: List[Dict] = []

    def refresh():
        nonlocal prev_last, last_refresh, last_unread, input_buffer

        _clear_screen()  # ← вот это добавили

        try:
            chats = fetch_chat_list(session)
        except Exception as e:
            print(f"{YELLOW}[Chat]{RESET} Ошибка при загрузке списка диалогов: {e}")
            return

        unread_chats = [ch for ch in chats if ch["unread"]]
        new_events: list[Dict] = []

        for ch in unread_chats:
            key = ch["url"]
            last_msg = ch["last_message"]
            old_last = prev_last.get(key)

            # первое появление чата или изменилось последнее сообщение
            if old_last is None or last_msg != old_last:
                new_events.append(ch)

            prev_last[key] = last_msg


        if new_events:
            _play_notify()
            print(f"\n{GREEN}[Chat]{RESET} Новые сообщения в диалогах:")

            for ch in new_events:
                name_plain = ch["name"]
                name_colored = f"{MAGENTA}{name_plain}{RESET}"
                last = _short(ch["last_message"])
                print(f"  ✉️ {name_colored}: {last}")

                # Windows-тост
                _notify_windows_chat(name_plain, last, ch["url"])

            print()



        print(f"{BOLD}{YELLOW}=== Новые диалоги (unread) ==={RESET}")
        if not unread_chats:
            print(f"{GRAY}Пока нет новых сообщений. Жду...{RESET}")
        else:
            for i, ch in enumerate(unread_chats, start=1):
                name = f"{MAGENTA}{ch['name']}{RESET}"
                last = _short(ch["last_message"])
                if ch["time"]:
                    time_str = f"{DIM}{ch['time']}{RESET}"
                    line = f"{CYAN}{i:2d}.{RESET} [✉️] {name}: {last}  {time_str}"
                else:
                    line = f"{CYAN}{i:2d}.{RESET} [✉️] {name}: {last}"
                print(line)

        print("\nВведите номер диалога (0 - выход) > ", end="", flush=True)
        print(input_buffer, end="", flush=True)

        last_unread = unread_chats
        last_refresh = time.time()


    try:
        refresh()  # первый вывод

        while True:
            now = time.time()
            if now - last_refresh >= 5.0:
                print()  # перенос строки перед новым выводом
                refresh()

            if msvcrt.kbhit():
                ch = msvcrt.getwch()

                # Enter — обработка введённого
                if ch in ("\r", "\n"):
                    cmd = input_buffer.strip()
                    input_buffer = ""
                    print()  # перенос строки после ввода

                    if cmd == "0":
                        print(f"{YELLOW}[Chat]{RESET} Выход из мониторинга.")
                        return

                    if cmd.isdigit():
                        idx = int(cmd)
                        if 1 <= idx <= len(last_unread):
                            chat = last_unread[idx - 1]
                            show_chat(session, chat["url"])
                            # после выхода из чата форсим обновление
                            prev_last = {}
                            last_refresh = 0.0
                            print()
                            refresh()
                        else:
                            print(f"{YELLOW}[Chat]{RESET} Нет диалога с таким номером.")
                            print("Введите номер диалога (0 - выход) > ", end="", flush=True)
                    else:
                        print(f"{YELLOW}[Chat]{RESET} Введи номер или 0.")
                        print("Введите номер диалога (0 - выход) > ", end="", flush=True)

                # Backspace
                elif ch in ("\x08", "\x7f"):
                    if input_buffer:
                        input_buffer = input_buffer[:-1]
                        # стираем символ в консоли
                        print("\b \b", end="", flush=True)

                else:
                    # добавляем символ в буфер и печатаем
                    input_buffer += ch
                    print(ch, end="", flush=True)

            time.sleep(0.1)

    except KeyboardInterrupt:
        print(f"\n{YELLOW}[Chat]{RESET} Мониторинг остановлен (Ctrl+C).")







def main() -> None:
    print("[Chat] Старт плагина чатов FunPay CLI.")
    cfg = _load_config()
    if not cfg:
        _input("\nНажми Enter для выхода...")
        return

    session = _make_session(cfg)
    if session is None:
        _input("\nНажми Enter для выхода...")
        return

    run_chat_cli(session)


if __name__ == "__main__":
    main()
