import os
import sys

# Путь к ЭТОМУ файлу: ...\Funpay CLI\plugins\Notifer\main.py
HERE = os.path.abspath(__file__)

# Папка Notifer
NOTIFER_DIR = os.path.dirname(HERE)

# Папка plugins
PLUGINS_DIR = os.path.dirname(NOTIFER_DIR)

# Корень проекта Funpay CLI
PROJECT_ROOT = os.path.dirname(PLUGINS_DIR)

# Добавляем корень проекта в sys.path
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Теперь можно импортировать kypisa
from kypisa.notifier import run_notifier


if __name__ == "__main__":
    run_notifier()
