#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def fail(msg):
    print("VERSION_FAIL", msg); sys.exit(1)


def spec_sets_version(text):
    code = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
    return re.search(r"\bversion\s*=", code) is not None


def main():
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        ver = f.read().strip()
    if not re.fullmatch(r"\d+(\.\d+){1,3}", ver):
        fail(f"VERSION имеет плохой формат: {ver!r}")

    if not spec_sets_version("exe = EXE(pyz, version='v.txt')"):
        fail("детектор version= не сработал на контрольном образце")
    with open(os.path.join(ROOT, "Facet.spec"), encoding="utf-8") as f:
        if spec_sets_version(f.read()):
            fail("Facet.spec задаёт ресурс версии (version=) — свойства exe вернулись")

    import gui
    if gui.app_version() != ver:
        fail(f"gui.app_version()={gui.app_version()!r} != VERSION {ver!r}")
    title = f"{gui.APP_NAME}  {ver}"
    if not title.startswith("Facet") or ver not in title:
        fail(f"заголовок окна не сойдётся: {title!r}")

    print(f"VERSION_OK {ver} сходится: VERSION == gui.app_version() == title; ресурса версии exe нет")


if __name__ == "__main__":
    main()
