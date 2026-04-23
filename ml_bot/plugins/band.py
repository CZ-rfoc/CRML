import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))
from config import (config, User, GameRecord, GameProgress)
from utils.database import Session

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg



band = on_command("绑定",aliases={'bd','band'})

@band.handle()
async def handle_echo(event: MessageEvent, args = CommandArg()):
    """绑定id"""
    user_name = args.extract_plain_text().strip()
    qq_num=event.get_user_id()
    session=Session()
    _=session.query(User).filter(User.bd_qq==qq_num).first()
    if _:
        await band.finish(f"该QQ号已绑定{_.nickname}，暂不支持解绑")
    user=session.query(User).filter(User.nickname == user_name).first()
    if user is None:
        await band.finish("账户不存在！请使用/绑定 网站注册名称进行绑定")
    else:
        if user.bd_qq:
            await band.finish(f"账户已绑定到{user.bd_qq}!请勿重复绑定")
        else:
            user.band(qq_num)
            session.commit()
            await band.finish(f"绑定成功！QQ号{qq_num}已绑定至{user_name}")
