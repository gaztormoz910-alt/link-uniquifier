#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_icon.py — собирает assets/Facet.ico из ОДНОГО мастера assets/Facet.png.

Ключевое (почему так, а не Image.save(sizes=...)):
  • Уменьшение — в ЛИНЕЙНОМ свете (sRGB нелинеен: 128 ≈ 21% яркости), иначе
    яркие тонкие линии на тёмном фоне тускнеют (замерено до −33% на 16px).
  • Премультипликация на альфу перед ресемплингом — иначе прозрачные пиксели за
    краем вносят свой чёрный в края.
  • Резкость мелких размеров — тоже в линейном свете и с ВОЗВРАТОМ ЭНЕРГИИ
    (unsharp несимметричен и подсвечивает картинку; возврат перераспределяет
    контраст, а не осветляет).
  • 10 размеров (16,20,24,32,40,48,64,96,128,256): 20/40/96 Windows запрашивает
    при масштабе 125%/175% — без них система жмёт чужой размер сама.
  • .ico пишем ВРУЧНУЮ, вкладывая наши готовые кадры как PNG: Image.save с
    sizes= сам ресемплит в sRGB и убил бы весь смысл.
"""
import io
import os
import struct
import sys

import numpy as np
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
# радиус и сила резкости — только для мелких размеров
SHARPEN = {16: (0.5, 0.45), 20: (0.5, 0.45), 24: (0.55, 0.40),
           32: (0.6, 0.35), 40: (0.6, 0.30), 48: (0.7, 0.25)}

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(_ROOT, "assets", "Facet.png")
OUT = os.path.join(_ROOT, "assets", "Facet.ico")


def _srgb_to_linear(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def _linear_to_srgb(a):
    a = np.clip(a, 0.0, 1.0)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)


def _gaussian_blur(arr, radius):
    """Разделимое гауссово размытие на numpy-float (Pillow GaussianBlur не
    работает с mode 'F', а перевод в 8 бит убил бы точность линейных значений)."""
    sigma = max(float(radius), 1e-6)
    r = max(1, int(round(sigma * 3)))
    x = np.arange(-r, r + 1, dtype=np.float64)
    k = np.exp(-(x ** 2) / (2 * sigma * sigma))
    k /= k.sum()
    out = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 0, arr)
    out = np.apply_along_axis(lambda m: np.convolve(m, k, mode="same"), 1, out)
    return out


def resize_linear(img, size):
    """sRGB → линейный → премультипликация → LANCZOS → (резкость) → обратно."""
    arr = np.asarray(img.convert("RGBA"), dtype=np.float64) / 255.0
    rgb, alpha = arr[..., :3], arr[..., 3]
    lin = _srgb_to_linear(rgb) * alpha[..., None]              # премультипликация

    planes = []
    for ch in (lin[..., 0], lin[..., 1], lin[..., 2], alpha):
        # mode 'F' — единственный способ отдать Pillow дробные значения без
        # округления до 8 бит (в линейном пространстве тёмные тона узкие).
        f = Image.fromarray(ch.astype(np.float32), mode="F")
        planes.append(np.asarray(f.resize((size, size), Image.LANCZOS), dtype=np.float64))

    out_a = np.clip(planes[3], 0.0, 1.0)
    safe = np.where(out_a > 1e-6, out_a, 1.0)                  # защита от /0
    out_rgb = np.stack(planes[:3], axis=-1) / safe[..., None]
    out_rgb = np.where(out_a[..., None] > 1e-6, out_rgb, 0.0)

    sp = SHARPEN.get(size)
    if sp:
        radius, strength = sp
        blur = _gaussian_blur(out_rgb, radius)
        sharp = out_rgb + strength * (out_rgb - blur)         # нерезкое маскирование
        w = out_a[..., None]
        before = float((out_rgb * w).sum())
        after = float((sharp * w).sum())
        if after > 1e-9:
            sharp *= before / after                           # ВОЗВРАТ энергии
        out_rgb = np.clip(sharp, 0.0, 1.0)

    data = np.concatenate([_linear_to_srgb(out_rgb), out_a[..., None]], axis=-1)
    return Image.fromarray(np.round(data * 255).astype(np.uint8), mode="RGBA")


def _write_ico(frames, path):
    """Ручная запись .ico: каждый кадр вложен как PNG (Windows это читает начиная
    с Vista), поэтому наши линейно-уменьшенные пиксели сохраняются как есть."""
    blobs = []
    for im in frames:
        b = io.BytesIO()
        im.save(b, format="PNG")
        blobs.append(b.getvalue())
    n = len(frames)
    header = struct.pack("<HHH", 0, 1, n)                     # reserved, type=icon, count
    offset = 6 + n * 16
    entries, body = b"", b""
    for im, blob in zip(frames, blobs):
        w, h = im.size
        entries += struct.pack("<BBBBHHII",
                               w if w < 256 else 0, h if h < 256 else 0,
                               0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        body += blob
    with open(path, "wb") as f:
        f.write(header + entries + body)


def build():
    if not os.path.isfile(MASTER):
        print("НЕТ мастера:", MASTER); sys.exit(1)
    master = Image.open(MASTER).convert("RGBA")
    if master.width != master.height:
        print("мастер не квадратный:", master.size); sys.exit(1)
    frames = [resize_linear(master, s) for s in SIZES]
    _write_ico(frames, OUT)
    print("ICON_OK", "->", OUT, "| размеры:", ",".join(map(str, SIZES)),
          "| мастер:", f"{master.width}x{master.height}")


if __name__ == "__main__":
    build()
