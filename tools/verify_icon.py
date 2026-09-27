#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_icon.py — доказывает, что assets/Facet.ico собран ИЗ мастера assets/Facet.png
(один источник на все размеры), а не из чужой картинки.

Проверки:
  • каждый кадр .ico ≈ линейно-уменьшенному мастеру того же размера (среднее
    отклонение по видимым пикселям в ЕДИНИЦАХ уровней, порог 12);
  • НЕГАТИВНЫЙ КОНТРОЛЬ: заведомо другая картинка порогом отвергается (иначе порог
    пропускал бы что угодно);
  • яркость каждого кадра отклоняется от эталона не более чем на 5%.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_icon as mk  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

THRESH = 12.0          # порог среднего отклонения (уровни 0..255)
BRIGHT_TOL = 0.05      # 5%


def _mean_dev(a, b):
    """Среднее |a-b| по пикселям, где ХОТЯ БЫ один непрозрачен (в уровнях 0..255)."""
    aa = np.asarray(a.convert("RGBA"), dtype=np.float64)
    bb = np.asarray(b.convert("RGBA"), dtype=np.float64)
    m = (aa[..., 3] > 8) | (bb[..., 3] > 8)
    if not m.any():
        return 0.0
    return float(np.abs(aa[..., :3][m] - bb[..., :3][m]).mean())


def _luma(im):
    a = np.asarray(im.convert("RGBA"), dtype=np.float64)
    w = a[..., 3:4] / 255.0
    rgb = a[..., :3]
    tot = w.sum()
    if tot < 1e-6:
        return 0.0
    return float((rgb * w).sum() / (3 * tot))


def main():
    master = Image.open(mk.MASTER).convert("RGBA")
    ico = Image.open(mk.OUT)
    worst_dev = 0.0
    worst_neg = 1e9
    for size in mk.SIZES:
        ico.size = (size, size)          # выбрать кадр нужного размера
        frame = ico.copy().convert("RGBA")
        ref = mk.resize_linear(master, size)     # эталон тем же алгоритмом
        dev = _mean_dev(frame, ref)
        worst_dev = max(worst_dev, dev)
        if dev > THRESH:
            print(f"ICON_FAIL кадр {size}: отклонение {dev:.2f} > {THRESH}")
            sys.exit(1)
        # яркость
        lm, lf = _luma(ref), _luma(frame)
        if lm > 1e-6 and abs(lf - lm) / lm > BRIGHT_TOL:
            print(f"ICON_FAIL кадр {size}: яркость откл {100*abs(lf-lm)/lm:.1f}% > 5%")
            sys.exit(1)
        # негативный контроль: заведомо другая картинка (сплошной красный)
        neg = Image.new("RGBA", (size, size), (255, 0, 0, 255))
        worst_neg = min(worst_neg, _mean_dev(frame, neg))

    if worst_neg <= THRESH:
        print(f"ICON_FAIL негативный контроль не сработал: {worst_neg:.2f} <= {THRESH}")
        sys.exit(1)
    print(f"ICON_OK кадров={len(mk.SIZES)} худшее_отклонение={worst_dev:.2f} "
          f"(порог {THRESH}) негатив={worst_neg:.1f}")


if __name__ == "__main__":
    main()
