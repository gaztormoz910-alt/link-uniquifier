#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrub_metadata.py — вычищает «датовые» метаданные из СОБРАННОГО приложения,
чтобы бинарники не выдавали, когда и на какой машине их собрали.

Зачем вообще: даже когда у Facet.exe убран ресурс версии (компания/копирайт), в
PE-заголовке остаётся TimeDateStamp — момент компоновки (UTC), а у файлов в папке
сборки остаются mtime/ctime машины сборщика. exiftool тут не поможет: для EXE/DLL/
ICO/ZIP он ТОЛЬКО ЧИТАЕТ и писать (удалять) не умеет (exiftool.org, таблица
read/write). Поэтому чистим на уровне PE через pefile.

Что делает:
  • PE-файлы (.exe/.dll/.pyd): FILE_HEADER.TimeDateStamp и метки времени в
    каталогах debug/export/resource → EPOCH; пересчитывает контрольную сумму PE.
    Ресурс версии, Rich header и строки вендоров НЕ трогает: режим — только даты
    и времена файлов, без тамперинга заголовка и без удаления чужих строк.
  • .zip внутри сборки: даты всех членов → EPOCH (PyInstaller и так пишет
    1980-01-01, нормализуем явно — вдруг иной сборщик положит иначе).
  • Времена каждого файла (mtime, atime и, на Windows, время создания) → EPOCH.

EPOCH = 1980-01-01 00:00:00 UTC. Синтетическая дата, НЕ связана со сборкой,
безопасна для zip/FAT (там это минимум) и совпадает с тем, что PyInstaller уже
кладёт в base_library.zip, — т.е. выбор не произвольный, а «родной» для сборки.

Идемпотентна: повторный запуск ничего не меняет (это проверяет гейт).

Запуск:
  scrub_metadata.py <dir>                 # вычистить дерево сборки
  scrub_metadata.py --file <pe>           # вычистить один PE (напр. установщик)
  scrub_metadata.py --verify <dir>        # проверка дерева  → SCRUB_VERIFY_OK / код!=0
  scrub_metadata.py --verify --file <pe>  # проверка одного PE
"""
import os
import sys
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 1980-01-01 00:00:00 UTC.
EPOCH = 315532800
ZIP_DT = (1980, 1, 1, 0, 0, 0)
PE_EXT = (".exe", ".dll", ".pyd", ".so")


def _pefile():
    try:
        import pefile  # noqa
        return pefile
    except ImportError:
        print("SCRUB_FAIL нет модуля pefile (pip install pefile)")
        sys.exit(2)


# ── PE ──────────────────────────────────────────────────────────────────
def _pe_stamps(pe):
    """Все метки времени PE, которые нормализуем: заголовок + каталоги."""
    yield pe.FILE_HEADER, "TimeDateStamp"
    for name in ("DIRECTORY_ENTRY_DEBUG",):
        for d in getattr(pe, name, []) or []:
            yield d.struct, "TimeDateStamp"
    exp = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
    if exp is not None:
        yield exp.struct, "TimeDateStamp"
    res = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
    if res is not None:
        yield res.struct, "TimeDateStamp"


def scrub_pe(path):
    pefile = _pefile()
    # Грузим из байтов, а НЕ по пути: pefile иначе мапит файл в память и на
    # Windows перезапись того же пути падает с нарушением доступа. Так же
    # гарантированно сохраняется оверлей (архив PyInstaller/данные Inno).
    with open(path, "rb") as f:
        raw = f.read()
    pe = pefile.PE(data=raw, fast_load=False)
    for struct_obj, field in _pe_stamps(pe):
        setattr(struct_obj, field, EPOCH)
    pe.OPTIONAL_HEADER.CheckSum = pe.generate_checksum()
    out = bytes(pe.write())
    pe.close()
    if out != raw:
        with open(path, "wb") as f:
            f.write(out)
    return True


def pe_stamp_values(path):
    pefile = _pefile()
    with open(path, "rb") as f:
        pe = pefile.PE(data=f.read(), fast_load=False)
    vals = [getattr(s, fld) for s, fld in _pe_stamps(pe)]
    cs_ok = pe.OPTIONAL_HEADER.CheckSum == pe.generate_checksum()
    pe.close()
    return vals, cs_ok


# ── файловые времена ────────────────────────────────────────────────────
def set_file_times(path):
    os.utime(path, (EPOCH, EPOCH))
    if os.name == "nt":
        _win_set_create_time(path, EPOCH)


def _filetime(epoch):
    # Windows FILETIME = 100-нс интервалы с 1601-01-01.
    return int((epoch + 11644473600) * 10_000_000)


def _win_set_create_time(path, epoch):
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    FILE_WRITE_ATTRIBUTES = 0x0100
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000  # нужен, чтобы открывать и каталоги
    ft = _filetime(epoch)
    val = wintypes.FILETIME(ft & 0xFFFFFFFF, ft >> 32)
    h = k.CreateFileW(str(path), FILE_WRITE_ATTRIBUTES, 0, None, OPEN_EXISTING,
                      FILE_FLAG_BACKUP_SEMANTICS, None)
    if h == -1 or h == ctypes.c_void_p(-1).value:
        return False
    try:
        ref = ctypes.byref(val)
        ok = k.SetFileTime(h, ref, ref, ref)  # create, access, write
        return bool(ok)
    finally:
        k.CloseHandle(h)


def _win_create_time(path):
    """Время создания файла (ctime на Windows), в unix-секундах."""
    return int(os.stat(path).st_ctime)


# ── zip ─────────────────────────────────────────────────────────────────
def scrub_zip(path):
    """Переписать архив, выставив всем членам дату ZIP_DT. Переписываем целиком,
    т.к. дата лежит в каждом local- и central-заголовке."""
    with zipfile.ZipFile(path) as z:
        if all(i.date_time == ZIP_DT for i in z.infolist()):
            return False
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    tmp = path + ".scrub.tmp"
    with zipfile.ZipFile(tmp, "w") as z:
        for info, data in items:
            ni = zipfile.ZipInfo(info.filename, ZIP_DT)
            ni.compress_type = info.compress_type
            ni.external_attr = info.external_attr
            ni.internal_attr = info.internal_attr
            ni.create_system = info.create_system
            z.writestr(ni, data)
    os.replace(tmp, path)
    return True


# ── обход ───────────────────────────────────────────────────────────────
def walk(root):
    for dp, _, fns in os.walk(root):
        for fn in fns:
            yield os.path.join(dp, fn)


def scrub_tree(root):
    pe = zips = files = 0
    for f in walk(root):
        low = f.lower()
        if low.endswith(".zip"):
            scrub_zip(f); zips += 1
        if low.endswith(PE_EXT):
            scrub_pe(f); pe += 1
        set_file_times(f); files += 1
    # времена самих каталогов тоже выдают сборку
    for dp, _, _ in os.walk(root):
        set_file_times(dp)
    print(f"SCRUB_OK pe={pe} zip={zips} files={files} epoch={EPOCH}")


def verify_tree(root):
    bad, pe, zips, files = [], 0, 0, 0
    for f in walk(root):
        low = f.lower()
        rel = os.path.relpath(f, root)
        if low.endswith(PE_EXT):
            pe += 1
            vals, cs_ok = pe_stamp_values(f)
            bad += [f"{rel}: PE stamp={v}" for v in vals if v != EPOCH]
            if not cs_ok:
                bad.append(f"{rel}: PE checksum не пересчитан")
        if low.endswith(".zip"):
            zips += 1
            with zipfile.ZipFile(f) as z:
                bad += [f"{rel}: zip-член {i.filename} дата={i.date_time}"
                        for i in z.infolist() if i.date_time != ZIP_DT]
        files += 1
        if int(os.path.getmtime(f)) != EPOCH:
            bad.append(f"{rel}: mtime={int(os.path.getmtime(f))}")
        if os.name == "nt" and _win_create_time(f) != EPOCH:
            bad.append(f"{rel}: ctime(создание)={_win_create_time(f)}")
    if files < 2:
        bad.append(f"подозрительно мало файлов: {files}")
    if bad:
        print("SCRUB_VERIFY_FAIL\n  " + "\n  ".join(bad[:40]))
        sys.exit(1)
    print(f"SCRUB_VERIFY_OK pe={pe} zip={zips} files={files} epoch={EPOCH}")


def verify_file(path):
    vals, cs_ok = pe_stamp_values(path)
    bad = [f"PE stamp={v}" for v in vals if v != EPOCH]
    if not cs_ok:
        bad.append("PE checksum не пересчитан")
    if bad:
        print("SCRUB_VERIFY_FAIL\n  " + "\n  ".join(bad))
        sys.exit(1)
    print(f"SCRUB_VERIFY_OK file stamps={len(vals)} epoch={EPOCH}")


def main():
    args = sys.argv[1:]
    verify = "--verify" in args
    args = [a for a in args if a != "--verify"]
    if "--file" in args:
        i = args.index("--file")
        path = args[i + 1]
        if verify:
            verify_file(path)
        else:
            scrub_pe(path)
            set_file_times(path)
            print(f"SCRUB_OK file={os.path.basename(path)} epoch={EPOCH}")
        return
    if not args:
        print("usage: scrub_metadata.py <dir> | --file <pe> | --verify ...")
        sys.exit(2)
    root = args[0]
    if verify:
        verify_tree(root)
    else:
        scrub_tree(root)


if __name__ == "__main__":
    main()
