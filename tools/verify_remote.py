#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_remote.py — проверяет синхронизацию с remote origin:
  • ветка main запушена (HEAD == origin/main)
"""
import sys
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def main():
    try:
        local_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        remote_head = subprocess.check_output(["git", "rev-parse", "origin/main"], text=True).strip()
    except Exception as e:
        print(f"FAIL: Ошибка получения ревизий: {e}")
        sys.exit(1)

    if local_head != remote_head:
        print(f"FAIL: local HEAD ({local_head}) != origin/main ({remote_head}). Требуется git push.")
        sys.exit(1)

    print("REMOTE_OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
