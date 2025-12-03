import os
import sys

# BASE_DIR = корень проекта "Funpay CLI"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from kypisa.notifier import run_notifier


if __name__ == "__main__":
    run_notifier()
