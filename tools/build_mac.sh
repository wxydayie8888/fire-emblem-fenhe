#!/bin/bash
# 打包 Mac 分享版：生成带图标的 .app，封装为可拖拽安装的 .dmg
# 用法: ./tools/build_mac.sh    产出: dist/芬河战记-mac.dmg
set -euo pipefail
cd "$(dirname "$0")/.."
APP="芬河战记"
VENV=.venv

if [ ! -d assets/Characters ]; then
  echo "素材未就绪，先运行: $VENV/bin/python tools/fetch_assets.py"; exit 1
fi

# 1) 用键视觉生成 .icns 应用图标（失败不阻断打包）
echo "==> 生成应用图标"
ICON_ARG=""
SRC=assets/cinema/keyart_title.jpg
make_icon() {
  [ -f "$SRC" ] || return 1
  local ICONSET; ICONSET=$(mktemp -d)/icon.iconset; mkdir -p "$ICONSET"
  local sq=/tmp/fenhe_sq.png
  sips -s format png -c 816 816 "$SRC" --out "$sq" >/dev/null 2>&1 || return 1
  local s
  for s in 16 32 128 256 512; do
    sips -s format png -z $s $s "$sq" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
    sips -s format png -z $((s*2)) $((s*2)) "$sq" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o /tmp/fenhe.icns >/dev/null 2>&1
}
if make_icon && [ -f /tmp/fenhe.icns ]; then
  ICON_ARG="--icon /tmp/fenhe.icns"; echo "    图标已生成"
else
  echo "    （跳过图标，用默认）"
fi

# 2) PyInstaller 构建 .app
echo "==> PyInstaller 构建"
$VENV/bin/pyinstaller --noconfirm --windowed --name "$APP" \
  --add-data "assets:assets" \
  $ICON_ARG \
  --osx-bundle-identifier "tv.liblib.fenhe" \
  main.py >/dev/null

APP_PATH="dist/$APP.app"
[ -d "$APP_PATH" ] || { echo "构建失败：未生成 $APP_PATH"; exit 1; }

# 3) ad-hoc 签名（减少 Gatekeeper 报「已损坏」概率）
echo "==> ad-hoc 签名"
codesign --force --deep --sign - "$APP_PATH" 2>/dev/null || echo "(签名跳过)"

# 4) 封装 .dmg（含 Applications 快捷方式 + 安装说明）
echo "==> 封装 DMG"
STAGE=$(mktemp -d)/dmg
mkdir -p "$STAGE"
cp -R "$APP_PATH" "$STAGE/"
ln -s /Applications "$STAGE/应用程序"
cat > "$STAGE/⚠️ 首次打开说明.txt" << 'TXT'
《芬河战记》安装与首次打开
========================
1) 把「芬河战记.app」拖到旁边的「应用程序」文件夹。
2) 首次打开：在「应用程序」里【右键点击】芬河战记 →【打开】→ 再点【打开】。
   （因为没有付费苹果开发者签名，直接双击可能提示「已损坏 / 无法验证开发者」，
    用右键打开即可绕过，仅首次需要。）
3) 若仍提示「已损坏」，打开「终端」执行：
      xattr -cr "/Applications/芬河战记.app"
   然后再右键打开。

存档与战绩保存在：~/Library/Application Support/芬河战记/
祝游玩愉快！⚔️
TXT

OUT="dist/芬河战记-mac.dmg"
rm -f "$OUT"
hdiutil create -volname "芬河战记" -srcfolder "$STAGE" -ov -format UDZO "$OUT" >/dev/null

echo
echo "✅ 完成: $OUT  ($(du -h "$OUT" | cut -f1))"
echo "   分享这个 .dmg 即可；对方按 DMG 里的「首次打开说明」操作。"
