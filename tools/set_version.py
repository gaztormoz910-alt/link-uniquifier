#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
set_version.py <версия> — ЕДИНЫЙ источник версии.

Пишет корневой файл VERSION. Отсюда версию читают все: окно (app_version в
gui.py), установщик (.iss через FileRead), CI (пишет VERSION из тега). Так тег,
окно и деинсталляция не могут разойтись.

Ресурс версии у .exe (вкладка «Подробно») намеренно НЕ генерируется: компания,
описание и внутреннее имя — метаданные файла, их в проекте не держим.
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 2:
        print("usage: set_version.py X.Y.Z"); sys.exit(2)
    ver = sys.argv[1].strip().lstrip("v")
    # Формат прежний (до 4 чисел): Inno Setup принимает AppVersion любым, но
    # единообразие с тегами vX.Y.Z удобно и CI на нём построен.
    if not re.fullmatch(r"\d+(\.\d+){1,3}", ver):
        print("плохая версия:", ver); sys.exit(2)

    with open(os.path.join(_ROOT, "VERSION"), "w", encoding="utf-8") as f:
        f.write(ver)
    print(f"VERSION_OK {ver}")


if __name__ == "__main__":
    main()
