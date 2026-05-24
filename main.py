import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional


BASE_DIR = Path(__file__).resolve().parent
TELEGRAM_FILE = BASE_DIR / "telebot.py"
WORKER_FILE = BASE_DIR / "rub.py"

_shutdown_requested = False


def _request_shutdown(_signum, _frame) -> None:
    global _shutdown_requested
    _shutdown_requested = True


def _terminate_process(proc: Optional[subprocess.Popen], *, timeout: float = 10.0) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5.0)


def _spawn_children() -> Dict[str, subprocess.Popen]:
    return {
        "worker": subprocess.Popen([sys.executable, str(WORKER_FILE)]),
        "bot": subprocess.Popen([sys.executable, str(TELEGRAM_FILE)]),
    }


def main() -> int:
    signal.signal(signal.SIGTERM, _request_shutdown)
    signal.signal(signal.SIGINT, _request_shutdown)

    procs: Dict[str, subprocess.Popen] = _spawn_children()
    exit_code = 0
    failing_name = None
    try:
        while not _shutdown_requested:
            for name, proc in procs.items():
                code = proc.poll()
                if code is None:
                    continue
                # In combined mode both children must remain alive.
                # If one exits, stop the sibling and let systemd restart everything.
                failing_name = name
                exit_code = code if code != 0 else 1
                raise RuntimeError(f"{name} exited with code {code}")
            time.sleep(1.0)
    except RuntimeError:
        pass
    finally:
        for proc in procs.values():
            _terminate_process(proc)

    if failing_name:
        sys.stderr.write(f"[main] child process '{failing_name}' exited; supervisor stopping\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
