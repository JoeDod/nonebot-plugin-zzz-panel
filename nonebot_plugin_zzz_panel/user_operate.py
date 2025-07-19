from playwright.async_api import async_playwright
import asyncio
from .utils import load_json_file, save_json_file, remove, process_avatar_images, render_html, html_render_image
from .config import plugin_dir
from pathlib import Path
from .common import *

file_locks = {}


async def get_file_lock(file_path):
    """获取文件路径对应的锁，如果不存在则创建一个新锁"""
    file_path_str = str(file_path)
    if file_path_str not in file_locks:
        file_locks[file_path_str] = asyncio.Lock()
    return file_locks[file_path_str]


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
        lock = await get_file_lock(cookies_path)
        await lock.acquire()
        try:
            cookies = load_json_file(cookies_path)
        finally:
            lock.release()
        if cookies == {}:
            await context.add_cookies([])
        else:
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
        # 保存该用户的cookies
        lock = await get_file_lock(cookies_path)
        await lock.acquire()
        try:
            cookies = await context.cookies()
            save_json_file(cookies, cookies_path)
        finally:
            lock.release()
        for _ in range(50):
            await page.locator(
                "div:nth-child(3) > .gt-icon > .gt-icon__img > use"
            ).first.click()
            await page.wait_for_timeout(100)
        await browser.close()
        return True


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


async def update_user_data(user_id, on_qr_code) -> bool:
    if not await login_with_cache(user_id, on_qr_code,
                                  create_response_handler):
        return False
    try:
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
        avatar_detail_list = load_json_file(
            user_dir / "avatar_detail.json").get("data", {}).get("list", [])
        avatar_map = {
            str(item["avatar"]["id"]): item
            for item in avatar_detail_list
        }

        async def process_avatar(avatar_id):
            avatar = avatar_map.get(avatar_id, {})

            # 补充角色数据
            avatar["uid"] = user_info.get("data", {}).get("user",
                                                          {}).get("uid", "")
            avatar["vertical_painting"] = icon_info.get("data", {}).get(
                "avatar_icon", {}).get(avatar_id,
                                       {}).get("vertical_painting", "")

            # 处理角色图片
            await process_avatar_images(avatar)

            # 渲染HTML和图片
            html_template = plugin_dir / "template" / "avatar_panel.html"
            output_html = user_dir / "images" / f"{avatar_id}.html"

            with html_template.open("r", encoding="utf-8") as f:
                render_html(avatar, f.read(), output_html)

            await html_render_image(output_html, "#container")
            remove(output_html)

        await asyncio.gather(
            *
            [process_avatar(avatar_id) for avatar_id in unlocked_avatars_list])
    except Exception:
        return False
    return True


def create_response_handler(user_id):

    async def on_response(response):
        if "avatar_basic_list" in response.url and response.status == 200:
            file_path = plugin_dir / "data" / user_id / "avatar_basic_list.json"
            file_lock = await get_file_lock(file_path)
            await file_lock.acquire()
            try:
                save_json_file(await response.json(), file_path)
            finally:
                file_lock.release()
        if "user/index?uid=" in response.url and response.status == 200:
            save_json_file(await response.json(),
                           plugin_dir / "data" / user_id / "user_info.json")

        if "batch_avatar_detail_v2" in response.url and response.status == 200:
            file_path = plugin_dir / "data" / user_id / "avatar_detail.json"
            file_lock = await get_file_lock(file_path)
            await file_lock.acquire()
            try:
                data = load_json_file(file_path)
                resp = await response.json()

                if data != {}:
                    st = set([i["avatar"]["id"] for i in data["data"]["list"]])
                    for i in resp["data"]["list"]:
                        if i["avatar"]["id"] not in st:
                            data["data"]["list"].append(i)
                    save_json_file(data, file_path)
                else:
                    save_json_file(resp, file_path)
            finally:
                file_lock.release()
        if "nap_cultivate_tool/user/icon_info?" in response.url and response.status == 200:
            file_path = plugin_dir / "data" / "common" / "icon_info.json"
            file_lock = await get_file_lock(file_path)
            await file_lock.acquire()
            try:
                save_json_file(await response.json(), file_path)
            finally:
                file_lock.release()

    return on_response


async def remove_user_cache(user_id):
    file_path = Path(plugin_dir / "data" / user_id)

    return remove(file_path)
