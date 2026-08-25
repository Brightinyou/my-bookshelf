#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version_file = root / "core" / "version.py"
    text = version_file.read_text(encoding="utf-8")
    m = re.search(r'APP_VERSION\s*=\s*"v(\d+)\.(\d+)\.(\d+)"', text)
    if not m:
        raise SystemExit("APP_VERSION 형식을 찾지 못했습니다")
    major, minor, patch = map(int, m.groups())
    patch += 1
    new_version = f"v{major}.{minor}.{patch}"
    version_file.write_text(
        f'APP_VERSION = "{new_version}"\nAPP_VERSION_NUMBER = APP_VERSION.removeprefix("v")\n',
        encoding="utf-8",
    )
    # 설치본 버전도 같이 올린다. 따로 두면 어긋난다 — 실제로 앱이 v1.2.32일 때
    # .iss는 1.2.17에 멈춰 있어서 "프로그램 추가/제거"에 옛 버전이 떴다.
    iss = root / "dev" / "installer" / "MyBookshelf.iss"
    if iss.exists():
        s = iss.read_text(encoding="utf-8-sig")
        s2 = re.sub(r'(#define MyAppVersion\s+")[\d.]+(")',
                    rf'\g<1>{major}.{minor}.{patch}\g<2>', s, count=1)
        if s2 != s:
            iss.write_text("﻿" + s2, encoding="utf-8")

    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
