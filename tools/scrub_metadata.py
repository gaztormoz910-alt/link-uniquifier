#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EPOCH = 315532800
ZIP_DT = (1980, 1, 1, 0, 0, 0)
PE_EXT = (".exe", ".dll", ".pyd", ".so")


def _pefile():
    try:
        import pefile
        return pefile
    except ImportError:
        print("SCRUB_FAIL нет модуля pefile (pip install pefile)")
        sys.exit(2)


def _pe_stamps(pe):
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


def remove_ads(path):
    if os.name == "nt":
        zone = f"{path}:Zone.Identifier"
        if os.path.exists(zone):
            try:
                os.remove(zone)
            except Exception:
                pass


def set_file_times(path):
    remove_ads(path)
    os.utime(path, (EPOCH, EPOCH))
    if os.name == "nt":
        _win_set_create_time(path, EPOCH)


def _filetime(epoch):
    return int((epoch + 11644473600) * 10_000_000)


def _win_set_create_time(path, epoch):
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    FILE_WRITE_ATTRIBUTES = 0x0100
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    ft = _filetime(epoch)
    val = wintypes.FILETIME(ft & 0xFFFFFFFF, ft >> 32)
    h = k.CreateFileW(str(path), FILE_WRITE_ATTRIBUTES, 0, None, OPEN_EXISTING,
                      FILE_FLAG_BACKUP_SEMANTICS, None)
    if h == -1 or h == ctypes.c_void_p(-1).value:
        return False
    try:
        ref = ctypes.byref(val)
        ok = k.SetFileTime(h, ref, ref, ref)
        return bool(ok)
    finally:
        k.CloseHandle(h)


def _win_create_time(path):
    return int(os.stat(path).st_ctime)


def scrub_zip(path):
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
