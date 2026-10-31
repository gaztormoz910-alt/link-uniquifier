#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_clean_binaries.py — проверяет собранные бинарники и установщик:
  • наличие dist/Facet/Facet.exe и installer/Facet-setup.exe
  • нормализацию PE-таймстемпов к константе 1980-01-01 (EPOCH = 315532800)
  • корректность PE-checksum
  • отсутствие абсолютных путей PDB в DIRECTORY_ENTRY_DEBUG
  • отсутствие потоков ADS Zone.Identifier
  • нормализацию дат файлов
"""
import os
import sys
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

EPOCH = 315532800

def check_pe_file(pe_path):
    import pefile
    with open(pe_path, "rb") as f:
        data = f.read()
    pe = pefile.PE(data=data, fast_load=False)
    
    errors = []
    # 1. FILE_HEADER.TimeDateStamp
    if pe.FILE_HEADER.TimeDateStamp != EPOCH:
        errors.append(f"{pe_path}: FILE_HEADER.TimeDateStamp = {hex(pe.FILE_HEADER.TimeDateStamp)}, ожидался {hex(EPOCH)}")
        
    # 2. CheckSum
    cs = pe.OPTIONAL_HEADER.CheckSum
    gen_cs = pe.generate_checksum()
    if cs != gen_cs:
        errors.append(f"{pe_path}: CheckSum = {hex(cs)}, вычисленный = {hex(gen_cs)}")
        
    # 3. DIRECTORY_ENTRY_DEBUG
    for d in getattr(pe, "DIRECTORY_ENTRY_DEBUG", []) or []:
        pdb_name = getattr(d.entry, "PdbFileName", b"")
        if isinstance(pdb_name, bytes):
            pdb_str = pdb_name.decode("utf-8", errors="ignore")
        else:
            pdb_str = str(pdb_name)
        if "\\" in pdb_str or "/" in pdb_str:
            errors.append(f"{pe_path}: PDB путь содержит каталоги: {pdb_str}")
        if d.struct.TimeDateStamp != EPOCH:
            errors.append(f"{pe_path}: DEBUG TimeDateStamp = {hex(d.struct.TimeDateStamp)}, ожидался {hex(EPOCH)}")

    pe.close()
    return errors

def check_ads(path):
    # На Windows проверяем отсутствие :Zone.Identifier
    zone_path = f"{path}:Zone.Identifier"
    if os.path.exists(zone_path):
        return f"{path} содержит альтернативный поток Zone.Identifier (Mark of the Web)!"
    return None

def main():
    exe_path = os.path.join("dist", "Facet", "Facet.exe")
    setup_path = os.path.join("installer", "Facet-setup.exe")
    
    for req in (exe_path, setup_path):
        if not os.path.isfile(req):
            print(f"FAIL: Требуемый файл {req} отсутствует! Запустите сборку.")
            sys.exit(1)
            
    all_errors = []
    for pe_file in (exe_path, setup_path):
        pe_errs = check_pe_file(pe_file)
        all_errors.extend(pe_errs)
        ads_err = check_ads(pe_file)
        if ads_err:
            all_errors.append(ads_err)

    # Прогоняем scrub_metadata.py --verify
    try:
        r1 = subprocess.run(
            [sys.executable, "tools/scrub_metadata.py", "--verify", os.path.join("dist", "Facet")],
            capture_output=True, text=True
        )
        if r1.returncode != 0:
            all_errors.append(f"scrub_metadata.py --verify dist/Facet вернул код {r1.returncode}: {r1.stdout} {r1.stderr}")
    except Exception as e:
        all_errors.append(f"Ошибка вызова scrub_metadata для dist: {e}")

    try:
        r2 = subprocess.run(
            [sys.executable, "tools/scrub_metadata.py", "--verify", "--file", setup_path],
            capture_output=True, text=True
        )
        if r2.returncode != 0:
            all_errors.append(f"scrub_metadata.py --verify installer вернул код {r2.returncode}: {r2.stdout} {r2.stderr}")
    except Exception as e:
        all_errors.append(f"Ошибка вызова scrub_metadata для setup: {e}")

    if all_errors:
        print("FAIL: Ошибки проверки бинарников:")
        for e in all_errors:
            print(f"  {e}")
        sys.exit(1)

    print("CLEAN_BINARIES_OK")
    sys.exit(0)

if __name__ == "__main__":
    main()
