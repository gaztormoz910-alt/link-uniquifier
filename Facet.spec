# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets'), ('VERSION', '.')]
binaries = []
hiddenimports = ['html', 'json', 'traceback']

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
    console=False,
    icon='assets/Facet.ico',
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='Facet')

exe_standalone = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Facet-standalone',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='assets/Facet.ico',
)
