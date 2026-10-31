#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_clean_sources.py — проверяет чистоту исходного кода от метаданных:
  • отсутствие абсолютных путей (C:\\Users\\, /home/, /Users/)
  • отсутствие логинов ОС (Bog_1, etc.)
  • отсутствие личных email и копирайтов
  • негативный контроль: валидация детектора на грязных данных
"""
import os
import re
import sys
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

FORBIDDEN_PATTERNS = [
    (r"Bog_1", "Имя пользователя ОС Bog_1"),
    (r"bogdan", "Имя Bogdan"),
    (r"toyotakorova", "Личный email/логин toyotakorova"),
    (r"bgaz\d*", "Личный логин bgaz"),
    (r"[A-Za-z]:\\Users\\", "Абсолютный путь Windows C:\\Users\\"),
    (r"/home/[a-zA-Z0-9_-]+", "Абсолютный путь Linux /home/"),
    (r"/Users/[a-zA-Z0-9_-]+", "Абсолютный путь macOS /Users/"),
]

WHITELIST_FILES = {
    # .git игнорируется автоматически
}

def scan_text(text, filename="<buffer>"):
    found = []
    for pattern, desc in FORBIDDEN_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            found.append((desc, list(set(matches))))
    return found

def run_negative_control():
    sample_dirty = "User profile located at C:\\Users\\Bog_1\\Desktop and mail toyotakorova@gmail.com"
    res = scan_text(sample_dirty)
    if len(res) < 2:
        print("FAIL: Негативный контроль не сработал на заведомо грязном образце!")
        sys.exit(2)

def main():
    run_negative_control()
    
    # Получаем список отслеживаемых git файлов
    try:
        tracked = subprocess.check_output(
            ["git", "ls-files"], encoding="utf-8", errors="replace"
        ).splitlines()
    except Exception as e:
        print(f"FAIL: git ls-files error: {e}")
        sys.exit(1)
        
    violations = []
    for rel_path in tracked:
        if not os.path.isfile(rel_path):
            continue
        # Пропускаем сам верификатор и промпт-очистки (если он в репо)
        if rel_path.replace("\\", "/") in ("tools/verify_clean_sources.py", "Промпт-очистки-метаданных.md"):
            continue
            
        try:
            with open(rel_path, "rb") as f:
                content = f.read().decode("utf-8", errors="ignore")
            issues = scan_text(content, rel_path)
            if issues:
                for desc, matches in issues:
                    violations.append(f"{rel_path}: {desc} -> {matches}")
        except Exception as e:
            violations.append(f"{rel_path}: ошибка чтения: {e}")

    if violations:
        print("FAIL: Обнаружены метаданные в исходниках:")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)

    print("CLEAN_SOURCES_OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
