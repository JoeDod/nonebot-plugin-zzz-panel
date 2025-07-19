from .config import plugin_dir
from .utils import load_json_file

common_data_dir = plugin_dir / "data" / "common"

try:
    avatar_id_name = load_json_file(common_data_dir / "avatar_id_name.json")
    icon_info = load_json_file(common_data_dir / "icon_info.json")
except FileNotFoundError:
    avatar_id_name = {}
    icon_info = {"data": {"avatar_icon": {}}}
