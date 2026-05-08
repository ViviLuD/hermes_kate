#!/usr/bin/env python3
"""Lightweight scheduler for Kate cognitive automation when cron/systemd are unavailable.

Runs:
- heartbeat every 5 minutes
- sensing every 6 hours
- dreaming once per day around 03:00 local server time

Designed to be simple, robust, and log-only. No network service, no external deps.
"""
from __future__ import annotations

import datetime as dt
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BASE = Path('/opt/data/kate_evolution')
LOG = BASE / 'kate_scheduler.log'
PID = BASE / 'kate_scheduler.pid'

TASKS = {
    'heartbeat': {
        'cmd': ['python3', str(BASE / 'heartbeat.py'), '--json'],
        'interval': 5 * 60,
        'log': BASE / 'heartbeat_log.jsonl',
        'next': 0.0,
    },
    'sensing': {
        'cmd': ['python3', str(BASE / 'sensing.py')],
        'interval': 6 * 60 * 60,
        'log': BASE / 'sensing.log',
        'next': 0.0,
    },
}

last_dream_date: str | None = None
running = True


def log(msg: str) -> None:
    ts = dt.datetime.now().isoformat(timespec='seconds')
    line = f'[{ts}] {msg}\n'
    with LOG.open('a', encoding='utf-8') as f:
        f.write(line)
    print(line, end='', flush=True)


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ensure_singleton() -> None:
    if PID.exists():
        try:
            old = int(PID.read_text().strip())
            if old != os.getpid() and pid_alive(old):
                print(f'kate_scheduler already running with PID {old}', file=sys.stderr)
                sys.exit(0)
        except Exception:
            pass
    PID.write_text(str(os.getpid()))


def run_task(name: str, cmd: list[str], logfile: Path) -> None:
    log(f'START {name}: {" ".join(cmd)}')
    try:
        with logfile.open('a', encoding='utf-8') as out:
            out.write(f'\n--- {name} {dt.datetime.now().isoformat(timespec="seconds")} ---\n')
            proc = subprocess.run(cmd, cwd=str(BASE), stdout=out, stderr=subprocess.STDOUT, timeout=1800)
        log(f'END {name}: exit={proc.returncode}')
    except subprocess.TimeoutExpired:
        log(f'TIMEOUT {name}')
    except Exception as e:
        log(f'ERROR {name}: {type(e).__name__}: {e}')


def should_dream(now: dt.datetime) -> bool:
    global last_dream_date
    today = now.date().isoformat()
    if last_dream_date == today:
        return False
    return now.hour == 3 and now.minute < 10


def handle_signal(signum, frame):  # noqa: ANN001
    global running
    log(f'SIGNAL {signum}; stopping')
    running = False


def main() -> None:
    ensure_singleton()
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    log(f'Kate scheduler started pid={os.getpid()}')

    # Run heartbeat immediately; delay heavier jobs slightly.
    TASKS['heartbeat']['next'] = 0.0
    TASKS['sensing']['next'] = time.time() + 60

    global last_dream_date
    while running:
        now_ts = time.time()
        now = dt.datetime.now()
        for name, cfg in TASKS.items():
            if now_ts >= float(cfg['next']):
                run_task(name, cfg['cmd'], cfg['log'])
                cfg['next'] = time.time() + float(cfg['interval'])

        if should_dream(now):
            run_task('dreaming', ['python3', str(BASE / 'dreaming.py')], BASE / 'dreaming.log')
            last_dream_date = now.date().isoformat()

        time.sleep(20)

    try:
        PID.unlink(missing_ok=True)
    except Exception:
        pass
    log('Kate scheduler stopped')


if __name__ == '__main__':
    main()
