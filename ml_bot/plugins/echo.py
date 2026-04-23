from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg

echo = on_command("echo")

@echo.handle()
async def handle_echo(event: MessageEvent, args = CommandArg()):
    """复读用户输入的内容"""
    msg = args.extract_plain_text().strip()
    if msg:
        await echo.finish(msg)
    else:
        await echo.finish("请告诉我需要复读的内容")