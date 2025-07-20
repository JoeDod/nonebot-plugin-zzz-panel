import json
from jinja2 import Template
import httpx
from pathlib import Path
from typing import Dict, Union, Any, List
from .config import plugin_dir
from playwright.async_api import async_playwright


def load_json_file(file_path: Union[str, Path]) -> Dict[Any, Any]:
    """加载JSON文件"""
    file_path = Path(file_path)
    if not file_path.exists():
        return {}
    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except Exception as e:
        raise RuntimeError(f"读取文件失败: {e}")


def save_json_file(data: Any, file_path: Union[str, Path]) -> None:
    """保存数据到JSON文件"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise RuntimeError(f"保存文件失败: {e}")


def remove(path: Union[str, Path]) -> bool:
    """删除文件夹或者文件"""
    path = Path(path)
    try:
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            for child in path.iterdir():
                remove(child)
            path.rmdir()
        return True
    except Exception:
        return False


async def download_image(image_url: str, save_directory: Union[Path,
                                                               str]) -> str:
    """
    从指定URL下载图片并保存到本地
    
    参数:
    image_url (str): 图片的URL地址
    save_directory (str): 保存图片的目录
    
    返回:
    str: 下载成功返回文件名，失败返回空字符串
    """
    if not image_url:
        return ""

    try:
        # 从URL提取文件名
        filename = Path(image_url).name
        if not filename:
            return ""
        save_path = Path(save_directory) / filename
        if save_path.exists():
            return filename
        # 创建保存目录（如果不存在）
        save_path.parent.mkdir(parents=True, exist_ok=True)
        # 发送HTTP请求获取图片
        async with httpx.AsyncClient() as client:
            response = await client.get(
                image_url,
                headers={
                    "user-agent":
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
                })

            # 写入文件
            with save_path.open("wb") as file:
                file.write(response.content)

        return filename

    except Exception as e:
        print(f"下载图片时发生未知错误 ({image_url}): {e}")

    return ""


async def process_avatar_images(data: Dict) -> Dict:
    """处理角色相关图片下载"""
    images = plugin_dir / "images"
    bg = await download_image(data["vertical_painting"],
                              images / "vertical_painting")

    gp = await download_image(data["avatar"]["group_icon_path"],
                              images / "group_icon_path")
    equips = []

    for equip in data["equip"]:
        icon = equip["icon"]
        equip["icon"] = await download_image(icon, images / "equip-icon")
        equips.append(equip)

    data["vertical_painting"] = bg
    data["avatar"]["group_icon_path"] = gp
    data["equips"] = equips
    return data


def render_html(data, template_html: str, save_directory: Path):
    template = Template(template_html)
    save_directory.parent.mkdir(parents=True, exist_ok=True)
    with save_directory.open("w", encoding="utf-8") as file:
        file.write(template.render(**data))


async def html_render_image(html_paths: List[Path], tag_id=None) -> List[Path]:
    results = []

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            async with await browser.new_page() as page:
                for html_path in html_paths:
                    html_path = Path(html_path)

                    image_path = html_path.parent / f"{html_path.stem}.png"
                    await page.goto(f"file://{html_path.absolute()}")
                    if tag_id:
                        await page.wait_for_timeout(500)
                        await page.locator(f"{tag_id}").screenshot(
                            path=image_path)
                    else:
                        await page.wait_for_timeout(500)
                        await page.screenshot(path=image_path)
                    results.append(image_path)
                return results
    except Exception:
        return []


def find_avatar_id(avatar_name: str, data: Dict) -> str:
    data = {name: str(k) for k, v in data.items() for name in v}
    if avatar_name in data:
        return data[avatar_name]
    for k, v in data.items():
        if avatar_name in k:
            return v
    return "-1"
