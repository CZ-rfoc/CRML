import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))
from config import (config, User)
from utils.database import Session

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent



run = on_command("run",aliases={"润","下播"})

@run.handle()
async def handle_echo(event: MessageEvent):
    """调整为不活跃状态"""
    qq_num=event.get_user_id()
    session=Session()
    user=session.query(User).filter(User.bd_qq==qq_num).first()
    if user is None:
        await run.finish("当前QQ未绑定！请使用/绑定 网站注册名称进行绑定")
    else:
        user.inactivate()
        session.commit()
        await run.finish(f"{user.get_name()}已调整到不活跃状态")