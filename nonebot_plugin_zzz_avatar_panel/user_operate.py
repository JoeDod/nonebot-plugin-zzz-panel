from typing import Dict
from playwright.async_api import async_playwright
import asyncio
from .utils import load_json_file, save_json_file, remove, process_avatar_images, render_html, html_render_image
from .config import plugin_dir
from pathlib import Path
from .common import *


async def login_with_cache(
    user_id,
    on_qr_code=None,
    on_response=None,
    headless=True,
) -> bool:

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        cookies_path = plugin_dir / "data" / user_id / "cookies.json"
        cookies = load_json_file(cookies_path)

        if cookies:
            await context.add_cookies(list(cookies))

        page = await context.new_page()
        if on_response:
            page.on("response", on_response(user_id))

        await page.goto(
            "https://act.mihoyo.com/zzz/gt/character-builder-h/index.html?utm_source=media&utm_medium=mys&utm_campaign=icon#/"
        )
        await page.wait_for_load_state("networkidle")

        # 简单检查：如果没有登录框，说明已登录
        login_button = page.get_by_role("button", name="去登录")
        if await login_button.count() != 0:
            # 扫码登录流程
            await login_button.click()
            await page.get_by_text("米哈游通行证登录").click()
            await page.wait_for_timeout(2 * 1000)
            iframe = page.locator("#mihoyo-login-platform-iframe")
            await iframe.content_frame.get_by_role("img").click()
            await page.wait_for_timeout(3 * 1000)
            qr_loaded = iframe.content_frame.locator("img").nth(1)
            qr_src = await qr_loaded.get_attribute("src")
            if on_qr_code:
                await on_qr_code(qr_src)

            # 等待扫码登录成功结果
            try:
                await page.wait_for_selector(
                    "iframe",
                    state="detached",
                )
            except Exception:
                return False

        cookies = await context.cookies()
        save_json_file(cookies, cookies_path)

        try:
            for _ in range(50):
                await page.locator(
                    "div:nth-child(3) > .gt-icon > .gt-icon__img > use"
                ).first.click()
                await page.wait_for_timeout(100)
            await browser.close()
            return True
        except Exception:
            return False


async def get_avatar_list(user_id) -> str:
    # 加载用户数据
    user_dir = plugin_dir / "data" / user_id
    user_info = load_json_file(user_dir / "user_info.json")

    # 获取已解锁角色列表
    basic_list = load_json_file(user_dir / "avatar_basic_list.json").get(
        "data", {}).get("list", [])
    unlocked_avatars_list = [
        str(basic["avatar"]["id"]) for basic in basic_list
        if basic.get("unlocked")
    ]
    # 获取角色详情
    avatar_detail_list = load_json_file(user_dir / "avatar_detail.json").get(
        "data", {}).get("list", [])
    avatar_map = {
        str(item["avatar"]["id"]): item
        for item in avatar_detail_list
    }

    return "---".join([
        avatar_map.get(id, {})["avatar"]["name_mi18n"]
        for id in unlocked_avatars_list
    ])


async def update_user_data(user_id, on_qr_code, login=True) -> bool:
    if login:
        if not await login_with_cache(user_id, on_qr_code,
                                      create_response_handler):
            return False

    try:

        user_dir = plugin_dir / "data" / user_id
        user_info = load_json_file(user_dir / "user_info.json")
        basic_list = load_json_file(user_dir / "avatar_basic_list.json").get(
            "data", {}).get("list", [])
        unlocked_avatars_list = [
            str(basic["avatar"]["id"]) for basic in basic_list
            if basic.get("unlocked")
        ]

        # 获取角色详情
        avatar_detail_list = load_json_file(
            user_dir / "avatar_detail.json").get("data", {}).get("list", [])
        avatar_map = {
            str(item["avatar"]["id"]): item
            for item in avatar_detail_list
        }
        html_template = plugin_dir / "template" / "avatar_panel.html"
        output_html_list = []
        with html_template.open("r", encoding="utf-8") as f:
            template_content = f.read()
        for avatar_id in unlocked_avatars_list:
            avatar = avatar_map.get(avatar_id, {})
            avatar["uid"] = user_info.get("data", {}).get("user",
                                                          {}).get("uid", "")
            avatar["vertical_painting"] = icon_info.get("data", {}).get(
                "avatar_icon", {}).get(avatar_id,
                                       {}).get("vertical_painting", "")

            await process_avatar_images(avatar)

            output_html = user_dir / "images" / f"{avatar_id}.html"

            render_html(avatar, template_content, output_html)
            output_html_list.append(output_html)

        await html_render_image(output_html_list, "#container")
        for html_path in output_html_list:
            remove(html_path)
    except Exception as e:
        print(f"更新用户数据时出错: {e}")
        return False

    return True


def create_response_handler(user_id):

    async def on_response(response):
        # 处理 avatar_basic_list
        if "avatar_basic_list" in response.url and response.status == 200:
            file_path = plugin_dir / "data" / user_id / "avatar_basic_list.json"
            lock = get_id_lock(file_path)

            async with lock:
                save_json_file(await response.json(), file_path)
            await safe_cleanup_lock(file_path)
        # 处理 user_info
        if "user/index?uid=" in response.url and response.status == 200:
            file_path = plugin_dir / "data" / user_id / "user_info.json"
            lock = get_id_lock(file_path)

            async with lock:
                save_json_file(await response.json(), file_path)
            await safe_cleanup_lock(file_path)
        # 处理 batch_avatar_detail_v2 - 这里需要特别注意，因为涉及读写操作
        if "batch_avatar_detail_v2" in response.url and response.status == 200:
            file_path = plugin_dir / "data" / user_id / "avatar_detail.json"
            lock = get_id_lock(file_path)

            async with lock:
                # 在锁内完成所有读写操作
                data = load_json_file(file_path)
                data_list_map = {
                    avatar["avatar"]["id"]: avatar
                    for avatar in data.get("data", {}).get("list", [])
                }

                resp = await response.json()
                resp_data_list = resp.get("data", {}).get("list", [])
                new_data_list = {
                    avatar["avatar"]["id"]: avatar
                    for avatar in resp_data_list
                }

                if data_list_map:
                    # 更新现有数据
                    for id, avatar in new_data_list.items():
                        data_list_map[id] = avatar
                    data["data"]["list"] = [
                        v for _, v in data_list_map.items()
                    ]
                    save_json_file(data, file_path)
                else:
                    # 保存新数据
                    save_json_file(resp, file_path)
            await safe_cleanup_lock(file_path)
        # 处理 icon_info - 公共数据，需要全局锁
        if "nap_cultivate_tool/user/icon_info?" in response.url and response.status == 200:
            file_path = plugin_dir / "data" / "common" / "icon_info.json"
            lock = get_id_lock(str(file_path))

            async with lock:
                save_json_file(await response.json(), file_path)
            await safe_cleanup_lock(str(file_path))

    return on_response


async def remove_user_cache(user_id):
    file_path = Path(plugin_dir / "data" / user_id)

    return remove(file_path)
