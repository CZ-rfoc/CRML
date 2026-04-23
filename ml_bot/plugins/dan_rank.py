from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.rule import to_me
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))
from utils.database import Session
from config import User

DAN_WEIGHT = {
    '九段': 9, '八段': 8, '七段': 7, '六段': 6, '五段': 5,
    '四段': 4, '三段': 3, '二段': 2, '一段': 1, '初段': 0
}

dan_rank = on_command("dw", aliases={"段位", "段位榜单"})

@dan_rank.handle()
async def handle_dan_rank(event: MessageEvent, args=CommandArg()):
    """
    段位榜查询
    格式：/段位榜 [数字排名 或 玩家昵称]
    示例：/段位榜 5          # 查看第5名附近的排名
    示例：/段位榜 张三       # 查看张三附近的排名
    """
    query = args.extract_plain_text().strip()
    session = Session()
    if not query:
        user_qq=event.get_user_id()
        user=session.query(User).filter(User.bd_qq==user_qq).first()
        if not user:
            await dan_rank.finish("当前帐号未绑定QQ，请绑定后查询\n或使用名称或位次进行查询:\n/月榜 5\n/yb 红厂长")
        query = user.nickname
    
    session = Session()
    try:
        all_users = session.query(User).all()
        # 排序：先按段位权重降序，再按段内PT降序
        sorted_users = sorted(
            all_users,
            key=lambda u: (DAN_WEIGHT.get(u.dan, 0), u.dan_pt),
            reverse=True
        )
        
        total = len(sorted_users)
        
        # 判断输入是数字还是昵称
        target_rank = None
        target_user = None

        try:
            target_rank = int(query)
            if target_rank < 1 or target_rank > total:
                await dan_rank.send(f"排名超出范围！当前共有{total}位活跃玩家")
                return
            target_user = sorted_users[target_rank - 1]
        except ValueError:
            for i, user in enumerate(sorted_users):
                if user.nickname == query:
                    target_rank = i + 1
                    target_user = user
                    break
            
            if target_rank is None:
                await dan_rank.send(f"玩家「{query}」不存在或未激活")
                return
        
        # 计算显示范围（前后各5名）
        start = max(0, target_rank - 6)
        end = min(total, target_rank + 5)
        
        # 获取显示范围内的玩家
        display_users = sorted_users[start:end]
        
        result = "段位排名榜\n"
        result += "━━━━━━━━━━━━━━\n\n"
        
        # 显示排名
        for i, user in enumerate(display_users):
            rank_num = start + i + 1
            
            # 标记目标玩家
            if rank_num == target_rank:
                result += "-> "
            else:
                result += "   "
            
            # 排名数字和昵称
            result += f"{rank_num}. {user.nickname}"
            
            # 添加空格对齐
            if len(user.nickname) < 6:
                result += " " * (6 - len(user.nickname))
            
            # 段位和PT
            result += f"  {user.dan}  {user.dan_pt:.1f}pt\n"
        
        # 添加统计信息
        result += "\n━━━━━━━━━━━━━━\n"
        result += f"总活跃人数：{total}人\n"
        if total > 0:
            result += f"榜首：{sorted_users[0].nickname} ({sorted_users[0].dan} {sorted_users[0].dan_pt:.1f}pt)\n"
        
        result += "\n提示：使用 /段位榜 [排名数字] 或 /段位榜 [昵称]"
        
        await dan_rank.send(result.strip())
        return
        
    except Exception as e:
        await dan_rank.send(f"查询失败：{str(e)}")
        return
    finally:
        session.close()