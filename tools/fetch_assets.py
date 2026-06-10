"""一键下载 DawnLike 素材包到 assets/ 目录。"""
import io
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

URL = "https://opengameart.org/sites/default/files/DawnLike_5.zip"
ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "assets"


def _ssl_context():
    """macOS 系统 Python 常缺证书链，优先用 certifi 的根证书。"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def main():
    DEST.mkdir(exist_ok=True)
    print(f"正在下载 {URL} ...")
    try:
        data = urllib.request.urlopen(URL, timeout=60, context=_ssl_context()).read()
    except Exception as e:
        print(f"下载失败: {e}\n请手动下载 {URL} 并解压到 {DEST}/")
        sys.exit(1)
    print(f"下载完成 ({len(data) // 1024} KB)，正在解压 ...")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(DEST)
    # 找到包含 Objects/Floor.png 的基准目录，确认解压成功
    hits = list(DEST.rglob("Objects/Floor.png"))
    if not hits:
        print("解压后未找到关键文件 Objects/Floor.png，素材可能已损坏")
        sys.exit(1)
    print(f"素材就绪: {hits[0].parent.parent}")


if __name__ == "__main__":
    main()
