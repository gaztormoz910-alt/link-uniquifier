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

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    if len(sys.argv) < 2:
        print("usage: set_version.py X.Y.Z"); sys.exit(2)
    ver = sys.argv[1].strip().lstrip("v")
    if not re.fullmatch(r"\d+(\.\d+){1,3}", ver):
        print("плохая версия:", ver); sys.exit(2)

    with open(os.path.join(_ROOT, "VERSION"), "w", encoding="utf-8") as f:
        f.write(ver)
    print(f"VERSION_OK {ver}")


if __name__ == "__main__":
    main()
