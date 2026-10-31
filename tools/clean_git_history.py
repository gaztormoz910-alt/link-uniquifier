#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_git_history.py — нормализует историю git:
  • автор и коммиттер приводятся к Facet <facet@localhost>
  • все даты коммитов переводятся в строгий UTC (+0000)
  • все теги преобразуются в легковесные (reset refs/tags/<name>, без объекта tagger)
"""
import os
import re
import sys
import subprocess

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

def rewrite():
    # 1. Экспортируем fast-export ветки main и тегов
    proc = subprocess.Popen(
        ["git", "fast-export", "refs/heads/main", "--tags"],
        stdout=subprocess.PIPE
    )
    stream = proc.stdout

    out = []
    while True:
        line = stream.readline()
        if not line:
            break
        if line.startswith(b"author ") or line.startswith(b"committer "):
            m = re.match(rb"^(author|committer)\s+(.*?)\s+<([^>]+)>\s+(\d+)\s+([+-]\d{4})$", line.strip())
            if m:
                kind, name, email, ts, tz = m.groups()
                line = b"%s Facet <facet@localhost> %s +0000\n" % (kind, ts)
            out.append(line)
        elif line.startswith(b"data "):
            datalen = int(line[5:].strip())
            out.append(line)
            payload = stream.read(datalen)
            out.append(payload)
        elif line.startswith(b"tag "):
            # tag v1.0.0
            parts = line.strip().split()
            tag_name = parts[1]
            from_line = stream.readline()
            mark = None
            if from_line.startswith(b"from "):
                mark = from_line.strip().split()[1]
            tagger_line = stream.readline()
            data_hdr = stream.readline()
            if data_hdr.startswith(b"data "):
                tag_datalen = int(data_hdr[5:].strip())
                tag_payload = stream.read(tag_datalen)
                nl = stream.read(1)
                if nl != b"\n":
                    out.append(nl)
            if mark:
                out.append(b"reset refs/tags/%s\nfrom %s\n\n" % (tag_name, mark))
        else:
            out.append(line)

    stream_data = b"".join(out)

    # 2. Удаляем старые теги перед импортом
    try:
        tags = subprocess.check_output(["git", "tag", "-l"], encoding="utf-8").splitlines()
        for t in tags:
            t = t.strip()
            if t:
                subprocess.check_call(["git", "tag", "-d", t])
    except Exception as e:
        print(f"Предупреждение при удалении тегов: {e}")

    # 3. Запускаем fast-import
    imp = subprocess.Popen(
        ["git", "fast-import", "--force"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = imp.communicate(stream_data)
    if imp.returncode != 0:
        print(f"FAIL: fast-import error: {stderr.decode('utf-8', errors='replace')}")
        sys.exit(imp.returncode)

    # 4. Сбрасываем ветку main на новый коммит
    subprocess.check_call(["git", "reset", "--hard", "refs/heads/main"])
    print("CLEAN_HISTORY_SUCCESS")

if __name__ == "__main__":
    rewrite()
