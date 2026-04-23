from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.rule import to_me
from nonebot.params import CommandArg

# 创建帮助命令
help_cmd = on_command("help", aliases={"帮助", "?", "？", "菜单"}, block=True)

@help_cmd.handle()
async def handle_help(event: MessageEvent, args=CommandArg()):
    """显示帮助信息"""
    
    help_text = """
📌 可用命令：
  /绑定(bd/band) [昵称] - 绑定QQ号到游戏账号
  /录分(lf) [东] [南] [西] [北] - 录入对局分数（按东南西北顺序）
  /吃鱼(查询/cy) - 查看个人资料和段位
  /roll - 调整为活跃状态
  /run - 退出活跃状态
  /echo - 复读姬
  /start(开局/kj/开一局) [昵称] [昵称] [昵称] [昵称] - 开一局！
  /预约（yy/ap) -显示预约相关指令
  /实况(live/sk) - 显示正在进行的对局
  /月榜(yb) [玩家昵称] /月榜(yb) [排名数字] - 查看月榜
  /段位(dw) [玩家昵称] /段位(dw) [排名数字] - 查看段位榜
  /帮助(?/？/help) - 显示此帮助

"""
    await help_cmd.finish(help_text.strip())
