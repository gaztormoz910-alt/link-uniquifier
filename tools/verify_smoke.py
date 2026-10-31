#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_smoke.py — смоук-тест вычищенного бинарника:
  • headless --selftest
  • запуск GUI-окна
"""
import os
import sys
import time
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def main():
    exe_path = os.path.join("dist", "Facet", "Facet.exe")
    if not os.path.isfile(exe_path):
        print(f"FAIL: {exe_path} не найден! Необходима сборка.")
        sys.exit(1)

    # 1. Selftest
    log_file = "selftest.log"
    if os.path.exists(log_file):
        try: os.remove(log_file)
        except Exception: pass

    res = subprocess.run([exe_path, "--selftest", log_file], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAIL: selftest завершился с кодом {res.returncode}. stdout: {res.stdout}, stderr: {res.stderr}")
        sys.exit(1)

    if not os.path.isfile(log_file):
        print("FAIL: selftest.log не был создан!")
        sys.exit(1)

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        log_content = f.read().strip()
    try: os.remove(log_file)
    except Exception: pass

    if "SELFTEST_OK" not in log_content:
        print(f"FAIL: selftest не содержит SELFTEST_OK: {log_content}")
        sys.exit(1)

    # 2. Окно стартует
    proc = subprocess.Popen([exe_path])
    time.sleep(4)
    ret = proc.poll()
    if ret is not None:
        print(f"FAIL: GUI-процесс упал сразу после старта с кодом {ret}!")
        sys.exit(1)

    # Завершаем процесс
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()

    print("SMOKE_OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
