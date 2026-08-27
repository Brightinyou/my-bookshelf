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

# ── .app 이 없거나 버전이 다르면 먼저 빌드 ──────────────────
NEED_BUILD=1
if [ -d "$APP" ]; then
    CUR="$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$APP/Contents/Info.plist" 2>/dev/null || echo "")"
    [ "$CUR" = "$APP_VERSION" ] && NEED_BUILD=0
fi
if [ "$NEED_BUILD" = "1" ]; then
    echo "📦 .app 을 먼저 빌드합니다…"
    bash "$SCRIPT_DIR/build_mac_app.sh" < /dev/null > /dev/null
fi
[ -d "$APP" ] || { echo "❌ $APP 이 없습니다"; exit 1; }

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
PKG="$DIST/MyBookshelf-$APP_VERSION.pkg"
rm -f "$PKG"
pkgbuild \
    --root "$STAGE/root" \
    --component-plist "$COMPONENT" \
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
echo "  4. Launchpad 에서 My Bookshelf 실행 (첫 실행 패키지 설치 5~20분)"
