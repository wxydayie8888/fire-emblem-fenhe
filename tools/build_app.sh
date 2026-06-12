#!/bin/bash
# 打包为独立 .app（无需 Python 环境，双击即玩）
# 用法: ./tools/build_app.sh   产出: dist/芬河战记.app
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d assets/Characters ]; then
  echo "素材未就绪，先运行: .venv/bin/python tools/fetch_assets.py"
  exit 1
fi

.venv/bin/pyinstaller --noconfirm --windowed --name "芬河战记" \
  --add-data "assets:assets" \
  main.py

echo
echo "✅ 打包完成: dist/芬河战记.app"
echo "   存档与战绩将写入 ~/Library/Application Support/芬河战记/"
