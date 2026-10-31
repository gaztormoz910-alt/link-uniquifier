#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_clean_git.py — проверяет чистоту git-истории ветки main и тегов:
  • 100% коммитов ветки main: author/committer == Facet <facet@localhost>
  • 100% дат коммитов: строго UTC (+00:00 или Z), никаких локальных таймзон (+06:00 и т.д.)
  • 100% тегов: только легковесные (commit, не tag)
  • негативный контроль детектора
"""
import sys
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def check_log_line(line):
    parts = line.strip().split("|")
    if len(parts) != 6:
        return f"Неверный формат строки лога: {line}"
    an, ae, cn, ce, ad, cd = parts
    if an != "Facet" or ae != "facet@localhost":
        return f"Грязный author: {an} <{ae}>"
    if cn != "Facet" or ce != "facet@localhost":
        return f"Грязный committer: {cn} <{ce}>"
    if not (ad.endswith("+00:00") or ad.endswith("Z")):
        return f"Не-UTC author_date (выдаёт таймзону/регион): {ad}"
    if not (cd.endswith("+00:00") or cd.endswith("Z")):
        return f"Не-UTC committer_date (выдаёт таймзону/регион): {cd}"
    return None

def run_negative_control():
    bad_line = "Ivan|ivan@mail.com|Ivan|ivan@mail.com|2026-10-10T23:32:08+06:00|2026-10-10T23:32:08+06:00"
    if not check_log_line(bad_line):
        print("FAIL: Негативный контроль не поймал грязную запись коммита!")
        sys.exit(2)
        
    bad_tz = "Facet|facet@localhost|Facet|facet@localhost|2026-10-10T23:32:08+06:00|2026-10-10T23:32:08+06:00"
    if not check_log_line(bad_tz):
        print("FAIL: Негативный контроль не поймал таймзону +06:00!")
        sys.exit(2)

def main():
    run_negative_control()
    
    # 1. Проверяем коммиты ветки main и всех тегов
    try:
        log_out = subprocess.check_output(
            ["git", "log", "refs/heads/main", "--tags", "--format=%an|%ae|%cn|%ce|%ad|%cd", "--date=iso-strict"],
            encoding="utf-8", errors="replace"
        )
    except Exception as e:
        print(f"FAIL: git log error: {e}")
        sys.exit(1)

    errors = []
    lines = [l for l in log_out.splitlines() if l.strip()]
    if not lines:
        print("FAIL: git log пуст!")
        sys.exit(1)

    for line in lines:
        err = check_log_line(line)
        if err:
            errors.append(err)

    # 2. Проверяем теги: только commit (легковесные)
    try:
        tags_out = subprocess.check_output(
            ["git", "for-each-ref", "--format=%(objecttype) %(refname)", "refs/tags"],
            encoding="utf-8", errors="replace"
        )
    except Exception as e:
        print(f"FAIL: git for-each-ref error: {e}")
        sys.exit(1)

    for tline in tags_out.splitlines():
        tline = tline.strip()
        if not tline:
            continue
        obj_type, ref_name = tline.split(None, 1)
        if obj_type != "commit":
            errors.append(f"Аннотированный тег {ref_name} (тип {obj_type}) содержит метаданные теггера! Требуется легковесный тег.")

    if errors:
        print("FAIL: Обнаружены следы в git:")
        for err in set(errors):
            print(f"  {err}")
        sys.exit(1)

    print("CLEAN_GIT_OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
