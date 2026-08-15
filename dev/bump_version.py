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
    print(new_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
