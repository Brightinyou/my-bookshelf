#!/bin/bash
# build_mac_pkg.sh — MyBookshelf.pkg 빌드 (더블클릭 설치)
# 사용: dev/build_mac_pkg.sh
# 결과: dist/.mac-build.noindex/MyBookshelf-vX.Y.Z.pkg  +  MyBookshelf.pkg(고정 이름)
#
# dmg 안의 .app을 더블클릭하면 macOS가 격리·translocation 때문에 읽기 전용
# 임시 경로에서 실행해 자가설치가 멈춘다. .pkg는 Apple 설치 관리자가
# /Applications 로 직접 풀어 놓으므로 그 경로 자체가 생기지 않는다. (2026-08-27)

set -e
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
DIST="$ROOT_DIR/dist/.mac-build.noindex"
APP="$DIST/MyBookshelf.app"
APP_VERSION="$(python3 -c "import sys; sys.path.insert(0,'$ROOT_DIR/core'); from version import APP_VERSION; print(APP_VERSION)")"
APP_VERSION_NUMBER="${APP_VERSION#v}"
IDENTIFIER="com.mybookshelf.app"

# ── .app 을 언제나 다시 빌드한다 ────────────────────────────
# 처음에는 «버전이 같으면 건너뛰기» 였는데, 이 저장소는 판올림을 Windows 쪽에서
# 하므로 맥에서는 버전이 같은 채로 소스만 바뀌는 것이 보통이다. 그 조건이면
# 바뀐 코드가 통째로 빠진 pkg 가 나온다 — requirements.txt 를 고치고도 옛
# 것이 담겼다. 빌드는 몇 초라 아낄 이유가 없다. (2026-08-29)
if [ "${1:-}" != "--no-build" ]; then
    echo "📦 .app 을 먼저 빌드합니다…"
    bash "$SCRIPT_DIR/build_mac_app.sh" < /dev/null > /dev/null
fi
[ -d "$APP" ] || { echo "❌ $APP 이 없습니다 (--no-build 로 건너뛰었나?)"; exit 1; }

echo "📦 MyBookshelf.pkg 빌드 시작… ($APP_VERSION)"

# ── 스테이징: .app 하나만 담은 폴더가 /Applications 로 풀린다 ──
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -R "$APP" "$STAGE/MyBookshelf.app"
# 개발 머신에서 붙었을 수 있는 격리 속성을 털어낸다
xattr -cr "$STAGE/MyBookshelf.app" 2>/dev/null || true

# ── 컴포넌트 설정: 재배치 끄기 ──────────────────────────────
# 기본값(BundleIsRelocatable=true)이면 설치 관리자가 다른 곳에 있는 옛
# MyBookshelf.app 을 찾아 거기에 덮어쓴다. 항상 /Applications 로 고정한다.
COMPONENT="$STAGE/component.plist"
mkdir -p "$STAGE/root"
mv "$STAGE/MyBookshelf.app" "$STAGE/root/MyBookshelf.app"
pkgbuild --analyze --root "$STAGE/root" "$COMPONENT" >/dev/null
/usr/libexec/PlistBuddy -c "Set :0:BundleIsRelocatable false" "$COMPONENT"
/usr/libexec/PlistBuddy -c "Set :0:BundleIsVersionChecked false" "$COMPONENT" 2>/dev/null || true

# ── pkg 생성 ────────────────────────────────────────────────
# ── 설치 직후 스크립트: 파이썬 환경 준비 ─────────────────
# Windows 의 [Run] «setup.bat --installer» 와 같은 자리. 설치가 끝나면 바로
# 실행되도록 만든다 — 첫 실행 때 기다리지 않는다.
SCRIPTS="$STAGE/scripts"
mkdir -p "$SCRIPTS"
cp "$SCRIPT_DIR/installer/mac_postinstall.sh" "$SCRIPTS/postinstall"
chmod +x "$SCRIPTS/postinstall"

PKG="$DIST/MyBookshelf-$APP_VERSION.pkg"
rm -f "$PKG"
pkgbuild \
    --root "$STAGE/root" \
    --component-plist "$COMPONENT" \
    --scripts "$SCRIPTS" \
    --install-location /Applications \
    --identifier "$IDENTIFIER" \
    --version "$APP_VERSION_NUMBER" \
    "$PKG" >/dev/null

# 버전 없는 고정 이름 사본 — releases/latest/download/MyBookshelf.pkg 영구 링크용
cp "$PKG" "$DIST/MyBookshelf.pkg"

echo "✅ PKG: $PKG"
echo "✅ 고정 이름: $DIST/MyBookshelf.pkg"
echo
echo "받는 사람이 할 일:"
echo "  1. MyBookshelf.pkg 더블클릭"
echo "  2. «확인되지 않은 개발자» 경고 → 우클릭 → 열기 (첫 1회)"
echo "  3. 설치 관리자에서 [계속] → [설치] → 암호 입력"
echo "  4. Launchpad 에서 My Bookshelf 실행 — 설치 때 환경을 미리 갖추므로 바로 열린다"
