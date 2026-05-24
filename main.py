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
        for proc, name in ((rubika_proc, "worker"), (telegram_proc, "bot")):
            code = proc.poll()
            if code is not None:
                print(f"tele2rub child exited: {name} code={code}", file=sys.stderr, flush=True)
                raise SystemExit(code or 1)
        time.sleep(1)

except KeyboardInterrupt:
    pass
finally:
    for proc in [telegram_proc, rubika_proc]:
        if proc and proc.poll() is None:
            proc.terminate()
