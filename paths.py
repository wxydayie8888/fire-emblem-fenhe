"""运行时路径：源码运行时一切都在项目目录；打包(frozen)后资源在
PyInstaller 的 _MEIPASS，存档/战绩写到用户数据目录。零 pygame 依赖。"""
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, 'frozen', False))


def resource_root():
    """只读资源（assets/ 等）所在目录。"""
    if FROZEN:
        return Path(getattr(sys, '_MEIPASS'))
    return Path(__file__).resolve().parent


def user_data_dir():
    """可写数据（save.json / records.json）目录。"""
    if not FROZEN:
        return Path(__file__).resolve().parent
    if sys.platform == 'darwin':
        d = Path.home() / 'Library' / 'Application Support' / '芬河战记'
    elif sys.platform.startswith('win'):
        d = Path.home() / 'AppData' / 'Roaming' / '芬河战记'
    else:
        d = Path.home() / '.fenhe-saga'
    d.mkdir(parents=True, exist_ok=True)
    return d
