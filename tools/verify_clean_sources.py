#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_WIN_USER_RX = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:\\" + "Users" + r"\\[^\\\s\"'`<>|]+", re.IGNORECASE)
_POSIX_HOME_RX = re.compile(r"(?<![A-Za-z0-9_/])/(?:home|" + "Users)/[A-Za-z0-9_.-]+")
_TOKEN_RX = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")
_AI_TRACE_PATTERNS = (
    (re.compile(r"\b" + "C" + "LAUDE" + r"\.md\b", re.IGNORECASE), "AI instruction file marker"),
    (re.compile(r"\b" + "GA" + "TES" + r"\.md\b", re.IGNORECASE), "process ledger marker"),
    (re.compile(r"(?<![A-Za-z0-9_])\." + "un" + "lazy" + r"(?![A-Za-z0-9_])", re.IGNORECASE), "process directory marker"),
    (re.compile(r"co-" + "authored-" + "by:", re.IGNORECASE), "AI trailer marker"),
    (re.compile(r"generated\s+with\s+" + "cl" + "aude", re.IGNORECASE), "AI attribution marker"),
)

_CI_SAFE_USERS = {
    "runneradmin",
    "runner",
    "actions",
    "vscode",
    "root",
    "system",
    "administrator",
    "defaultuser0",
    "facet",
    "facet@localhost",
}


def _collect_dynamic_markers():
    markers = set()
    candidates = [
        os.environ.get("USERNAME", ""),
        os.environ.get("USER", ""),
        Path.home().name,
    ]
    try:
        candidates.append(getpass.getuser())
    except Exception:
        pass
    try:
        for key in ("user.name", "user.email"):
            out = subprocess.check_output(
                ["git", "config", "--get", key],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            if out:
                candidates.append(out)
                if "@" in out:
                    candidates.append(out.split("@", 1)[0])
    except Exception:
        pass
    for env_name in ("PRIVATE_MARKERS", "SCRUB_MARKERS"):
        raw = os.environ.get(env_name, "")
        for part in raw.split(","):
            part = part.strip()
            if part:
                candidates.append(part)
    for item in candidates:
        low = item.strip().lower()
        if len(low) >= 3 and low not in _CI_SAFE_USERS:
            markers.add(item.strip())
    return sorted(markers, key=len, reverse=True)


def scan_text(text, filename="<buffer>", dynamic_markers=None):
    issues = []
    checks = [
        (_WIN_USER_RX, "Windows user profile path"),
        (_POSIX_HOME_RX, "POSIX home path"),
        (_TOKEN_RX, "GitHub access token"),
        *_AI_TRACE_PATTERNS,
    ]
    for pattern, desc in checks:
        matches = pattern.findall(text)
        if matches:
            unique = sorted(set(matches))[:5]
            issues.append((desc, unique))

    if dynamic_markers is None:
        dynamic_markers = _collect_dynamic_markers()
    for m in dynamic_markers:
        rx = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(m) + r"(?![A-Za-z0-9_])", re.IGNORECASE)
        found = rx.findall(text)
        if found:
            issues.append(("Local identity marker", sorted(set(found))[:5]))
    return issues


def run_negative_control():
    root_drv = "C:" + "\\"
    sample_dirty = (
        root_drv + "Users" + "\\sample_user\\Desktop "
        + "ghp_" + ("A" * 36) + " "
        + ".".join(["GA" + "TES", "md"])
    )
    res = scan_text(sample_dirty, dynamic_markers=["sample_user"])
    if len(res) < 4:
        print("FAIL: Negative control did not catch synthetic violations!")
        sys.exit(2)


def main():
    run_negative_control()
    if "--selftest" in sys.argv[1:]:
        print("CLEAN_SOURCES_SELFTEST_OK")
        sys.exit(0)

    try:
        raw_out = subprocess.check_output(["git", "ls-files"], text=True)
        files = [f.strip() for f in raw_out.splitlines() if f.strip()]
    except Exception as e:
        print(f"FAIL: git ls-files failed: {e}")
        sys.exit(1)

    skip_ext = {".png", ".ico", ".exe", ".dll", ".pyd", ".zip", ".webp", ".jpg", ".gif"}
    dynamic_markers = _collect_dynamic_markers()
    violations = []

    for rel_path in files:
        if not os.path.isfile(rel_path):
            continue
        if os.path.splitext(rel_path)[1].lower() in skip_ext:
            continue
        try:
            with open(rel_path, "rb") as f:
                content = f.read().decode("utf-8", errors="ignore")
            issues = scan_text(content, rel_path, dynamic_markers=dynamic_markers)
            for desc, matches in issues:
                violations.append(f"{rel_path}: {desc} -> {matches}")
        except Exception as e:
            violations.append(f"{rel_path}: read error: {e}")

    if violations:
        print("FAIL: Metadata or identity traces found in sources:")
        for v in violations:
            print(f"  {v}")
        sys.exit(1)

    print("CLEAN_SOURCES_OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
