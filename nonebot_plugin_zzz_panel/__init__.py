from nonebot import on_command
from nonebot.adapters.onebot.v11 import Message, MessageSegment, MessageEvent
from nonebot.params import CommandArg
from .config import plugin_dir
from .user_operate import login_with_cache, create_response_handler, remove_user_cache, update_user_data, get_avatar_list
from .utils import find_avatar_id
import base64
from .common import avatar_id_name

menu = on_command("菜单")
user_bind = on_command("绑定", priority=10, block=True)
user_remove = on_command("解绑", priority=10, block=True)
avatar_panel = on_command("面板", priority=10, block=True)
update_avatar_panel = on_command("更新面板", priority=10, block=True)
avatar_list = on_command("代理人列表", priority=10, block=True)


@menu.handle()
async def _():
    menu_text = ("🎮 **功能中心** 🎮\n"
                 "━━━━━━━━━━━━━━━━━━━━\n\n"
                 "👥 **账号管理**\n"
                 "  🔗 `/绑定` → 绑定游戏账号\n"
                 "  ❌ `/解绑` → 解除账号绑定\n\n"
                 "📈 **数据查询**\n"
                 "  👤 `/面板 代理人` → 查看代理人面板\n"
                 "  🔄 `/更新面板` → 刷新面板数据\n"
                 "  📋 `/代理人列表` → 查看角色列表\n\n"
                 "━━━━━━━━━━━━━━━━━━━━\n"
                 "💬 回复对应命令使用功能")
    await menu.finish(menu_text)


@avatar_list.handle()
async def _(event: MessageEvent):
    user_id = event.get_user_id()
    await avatar_list.finish(await get_avatar_list(user_id), at_sender=True)


@user_bind.handle()
async def _(event: MessageEvent):
    user_id = event.get_user_id()
    if await login_with_cache(
            user_id, lambda qr_src: update_avatar_panel.send(
                MessageSegment.image(qr_src), at_sender=True),
            create_response_handler) == False:
        await user_bind.finish("绑定失败!")
    await update_user_data(user_id,
                           lambda qr_src: update_avatar_panel.send(
                               MessageSegment.image(qr_src), at_sender=True),
                           login=False)
    await user_bind.finish("绑定成功!")


@update_avatar_panel.handle()
async def _(event: MessageEvent):
    await update_avatar_panel.send("正在更新面板,请等待...", at_sender=True)
    user_id = event.get_user_id()
    if await update_user_data(
            user_id, lambda qr_src: update_avatar_panel.send(
                MessageSegment.image(qr_src), at_sender=True)):
        await update_avatar_panel.finish("更新面板成功!", at_sender=True)
    await update_avatar_panel.finish("更新面板失败!", at_sender=True)


@user_remove.handle()
async def _(event: MessageEvent):
    user_id = event.get_user_id()
    if await remove_user_cache(user_id):
        await user_remove.finish("解绑成功", at_sender=True)
    await user_remove.finish("解绑失败", at_sender=True)


@avatar_panel.handle()
async def _(event: MessageEvent, msg: Message = CommandArg()):
    try:
        user_id = event.get_user_id()
        content = msg.extract_plain_text().strip()

        avatar_id = find_avatar_id(content, avatar_id_name)
        if avatar_id == "-1":
            await avatar_panel.finish("代理人名称错误", at_sender=True)

        avatar_panel_image = plugin_dir / "data" / user_id / "images" / f"{avatar_id}.png"
        if not avatar_panel_image.exists():
            await avatar_panel.finish("代理人面板不存在,请更新面板!", at_sender=True)
        with avatar_panel_image.open("rb") as f:
            image64 = base64.b64encode(f.read()).decode()
        await avatar_panel.finish(
            MessageSegment.image(f"data:image/png;base64,{image64}"),
            at_sender=True)

    except FileNotFoundError as e:
        await avatar_panel.finish(f"代理人面板不存在,请更新面板!: {str(e)}", at_sender=True)
