import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

telegram_file = BASE_DIR / "telebot.py"
rubika_file = BASE_DIR / "rub.py"

telegram_proc = None
rubika_proc = None

try:
    rubika_proc = subprocess.Popen([sys.executable, str(rubika_file)])
    telegram_proc = subprocess.Popen([sys.executable, str(telegram_file)])

    while True:
        rubika_code = rubika_proc.poll()
        telegram_code = telegram_proc.poll()
        if rubika_code is not None:
            raise RuntimeError(f"rub.py exited with code {rubika_code}")
        if telegram_code is not None:
            raise RuntimeError(f"telebot.py exited with code {telegram_code}")
        time.sleep(1)

except KeyboardInterrupt:
    pass
finally:
    for proc in [telegram_proc, rubika_proc]:
        if proc and proc.poll() is None:
            proc.terminate()
