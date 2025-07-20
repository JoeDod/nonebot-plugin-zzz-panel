from .config import plugin_dir
from .utils import load_json_file

common_data_dir = plugin_dir / "data" / "common"

try:
    avatar_id_name = load_json_file(common_data_dir / "avatar_id_name.json")
    icon_info = load_json_file(common_data_dir / "icon_info.json")
except FileNotFoundError:
    avatar_id_name = {}
    icon_info = {"data": {"avatar_icon": {}}}
import asyncio
from typing import Dict
from .config import plugin_dir
from .utils import load_json_file

common_data_dir = plugin_dir / "data" / "common"

try:
    avatar_id_name = load_json_file(common_data_dir / "avatar_id_name.json")
    icon_info = load_json_file(common_data_dir / "icon_info.json")
except FileNotFoundError:
    avatar_id_name = {}
    icon_info = {"data": {"avatar_icon": {}}}

_locks: Dict[str, asyncio.Lock] = {}
_cleanup_lock = asyncio.Lock()  # 保护锁字典的修改操作


def get_id_lock(id: str) -> asyncio.Lock:
    """获取id对应的锁"""
    if id not in _locks:
        _locks[id] = asyncio.Lock()
    return _locks[id]


async def safe_cleanup_lock(id: str):
    """安全地清理锁对象"""

    async with _cleanup_lock:
        if id in _locks:
            lock = _locks[id]
            if not lock.locked():
                del _locks[id]
