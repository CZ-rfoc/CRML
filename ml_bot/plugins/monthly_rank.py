from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.rule import to_me
import sys
from pathlib import Path
from datetime import datetime
import pytz
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))
from utils.database import Session
from config import User, GameRecord

BEIJING_TZ = pytz.timezone('Asia/Shanghai')

# 创建月榜命令
monthly_rank = on_command("月榜", aliases={"yb", "本月排行"})

@monthly_rank.handle()
async def handle_monthly_rank(event: MessageEvent, args=CommandArg()):
    """
    月榜查询
    格式：/月榜 [数字排名 或 玩家昵称]
    示例：/月榜 5          # 查看第5名附近的排名
    示例：/月榜 张三       # 查看张三附近的排名
    """
    query = args.extract_plain_text().strip()
    
    session = Session()
    if not query:
        user_qq=event.get_user_id()
        user=session.query(User).filter(User.bd_qq==user_qq).first()
        if not user:
            await monthly_rank.finish("当前帐号未绑定QQ，请绑定后查询\n或使用名称或位次进行查询:\n/月榜 5\n/yb 红厂长")
        query = user.nickname
    try:
        # 获取当前月份范围
        now = datetime.now(BEIJING_TZ)
        month_start = datetime(now.year, now.month, 1, tzinfo=BEIJING_TZ)
        if now.month == 12:
            month_end = datetime(now.year + 1, 1, 1, tzinfo=BEIJING_TZ)
        else:
            month_end = datetime(now.year, now.month + 1, 1, tzinfo=BEIJING_TZ)
        
        # 获取本月所有对局记录
        records = session.query(GameRecord).filter(
            GameRecord.game_time >= month_start,
            GameRecord.game_time < month_end
        ).all()
        
        # 计算每个玩家的本月总PT
        pt_total = {}
        for r in records:
            for p in r.get_players():
                nick = p["nickname"]
                pt = p["pt"]
                pt_total[nick] = pt_total.get(nick, 0) + pt
        
        # 如果没有对局记录
        if not pt_total:
            await monthly_rank.send(f"本月暂无对局记录")
            return
        
        # 按PT降序排序
        sorted_ranking = sorted(pt_total.items(), key=lambda x: -x[1])
        total = len(sorted_ranking)
        
        # 判断输入是数字还是昵称
        target_rank = None
        target_nick = None
        target_pt = None
        
        # 尝试解析为数字（排名）
        try:
            target_rank = int(query)
            if target_rank < 1 or target_rank > total:
                await monthly_rank.send(f"排名超出范围！当前共有{total}人参与")
                return
            target_nick = sorted_ranking[target_rank - 1][0]
            target_pt = sorted_ranking[target_rank - 1][1]
        except ValueError:
            # 不是数字，当作昵称处理
            for i, (nick, pt) in enumerate(sorted_ranking):
                if nick == query:
                    target_rank = i + 1
                    target_nick = nick
                    target_pt = pt
                    break
            
            if target_rank is None:
                await monthly_rank.send(f"玩家「{query}」本月暂无对局记录")
                return
        
        # 计算显示范围（前后各5名，共最多11名）
        start = max(0, target_rank - 6)  # 目标前5名（-6包含目标）
        end = min(total, target_rank + 5)  # 目标后5名
        
        # 获取显示范围内的玩家
        display_ranking = sorted_ranking[start:end]
        
        # 构建返回消息
        month_str = now.strftime("%Y年%m月")
        result = f" {month_str} PT排名榜\n"
        result += "━━━━━━━━━━━━━━\n\n"
        
        # 显示排名
        for i, (nick, pt) in enumerate(display_ranking):
            rank_num = start + i + 1
            
            # 标记目标玩家
            if rank_num == target_rank:
                result += f"👉 "
            else:
                result += "   "
            
            # 排名数字
            result += f"{rank_num}. {nick}"
            
            # 添加空格对齐
            if len(nick) < 6:
                result += " " * (6 - len(nick))
            
            result += f"  {pt:.1f} PT\n"
        
        # 添加统计信息
        result += "\n━━━━━━━━━━━━━━\n"
        result += f" 本月总参与人数：{total}人\n"
        result += f" 榜首：{sorted_ranking[0][0]} ({sorted_ranking[0][1]:.1f}PT)\n"
        
        result += f"\n 提示：使用 /月榜 [排名数字] 或 /月榜 [昵称]"
        
        await monthly_rank.send(result.strip())
        return
        
    except Exception as e:
        await monthly_rank.send(f"查询失败：{str(e)}")
        return
    finally:
        session.close()