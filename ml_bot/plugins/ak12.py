from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import to_me
from pathlib import Path

# 创建命令
ak12_cmd = on_command("ak12", aliases={"AK12"}, block=True)

# 图片路径（根据你的实际路径修改）
IMAGE_DIR =Path(__file__).parent.parent
CACHE_DIR = IMAGE_DIR / "_cache_"
IMAGE_PATH = CACHE_DIR / "ak12.jpg"
@ak12_cmd.handle()
async def handle_ak12(event: MessageEvent):
    """发送AK12图片"""
    await ak12_cmd.send("我是TYHappier！AK12是谁，不熟")
    await ak12_cmd.finish(MessageSegment.image(IMAGE_PATH))