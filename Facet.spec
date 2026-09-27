# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec для Facet:
#   • точка входа — gui.py (окно; freeze_support на месте для frozen-multiprocessing);
#   • GUI-фреймворк customtkinter возит темы/иконки данными → collect_all;
#   • ленивые импорты (html/json/traceback — внутри функций) в hiddenimports;
#   • на диск приложение пишет только в выбранный ПОЛЬЗОВАТЕЛЕМ файл → доп. данных нет;
#   • numpy НЕ используется приложением (только сборкой иконки) → в excludes;
#   • ресурса версии (version=) НЕТ намеренно: компания/описание/имя во вкладке
#     «Подробно» — метаданные файла, их в проекте не держим. Версию показывает окно.
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets'), ('VERSION', '.')]
binaries = []
hiddenimports = ['html', 'json', 'traceback']   # ленивые импорты (внутри функций)

for pkg in ('customtkinter',):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=['numpy', 'matplotlib', 'scipy', 'pandas', 'pytest',
              'IPython', 'jedi', 'zmq', 'tornado'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='Facet',
    debug=False, strip=False, upx=False,
    console=False,                       # GUI: без чёрного окна консоли
    icon='assets/Facet.ico',
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Facet')
