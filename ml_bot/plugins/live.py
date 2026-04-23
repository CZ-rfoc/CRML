from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.rule import to_me
import sys
from pathlib import Path
from datetime import datetime
import pytz

sys.path.append(str(Path(__file__).parent.parent))
from utils.database import Session
from config import User, GameProgress

BEIJING_TZ = pytz.timezone('Asia/Shanghai')

# 创建实况命令
live_cmd = on_command("实况", aliases={"对局列表", "进行中", "sk"})

@live_cmd.handle()
async def handle_live(event: MessageEvent):
    """显示正在进行的对局和活跃玩家"""
    
    session = Session()
    try:
        # 1. 查询所有进行中的对局
        ongoing_progress = session.query(GameProgress).filter(
            GameProgress.status == "ongoing"
        ).all()
        
        # 2. 查询所有活跃玩家
        active_users = session.query(User).filter(User.active == True).all()
        
        # 3. 获取正在对局中的玩家
        playing_players = set()
        for progress in ongoing_progress:
            try:
                for p in progress.get_players():
                    playing_players.add(p["nickname"])
            except:
                pass
        
        # 4. 筛选空闲的活跃玩家
        free_players = [u for u in active_users if u.nickname not in playing_players]
        
        result = "          实况\n"
        result += "━━━━━━━━━━━━━━━\n"
        
        # 显示进行中的对局
        if ongoing_progress:
            result += f"\n 正在进行中的对局（{len(ongoing_progress)}局）\n"
            for i, progress in enumerate(ongoing_progress, 1):
                try:
                    players = progress.get_players()
                    
                    # 获取对局ID（只显示前8位）
                    progress_id = progress.id[:8] if progress.id else "未知"
                    
                    # 获取创建时间
                    create_time = progress.create_time
                    if create_time:
                        if create_time.tzinfo is None:
                            create_time = create_time.replace(tzinfo=BEIJING_TZ)
                        time_str = create_time.strftime("%m-%d %H:%M")
                    else:
                        time_str = "未知"
                    
                    # 按东南西北顺序排列玩家
                    seat_order = ["东", "南", "西", "北"]
                    seat_players = {}
                    for p in players:
                        seat_players[p["seat"]] = p["nickname"]
                    
                    result += f"\n   对局 {i} (ID: {progress_id})\n"
                    result += f"      开局时间：{time_str}\n"
                    result += "      玩家："
                    player_list = []
                    for seat in seat_order:
                        if seat in seat_players:
                            player_list.append(f"{seat}{seat_players[seat]}")
                    result += "、".join(player_list) + "\n"
                    
                except Exception as e:
                    result += f"\n   对局 {i}: 数据异常\n"
        else:
            result += "\n 当前没有进行中的对局\n"
        
        # 显示活跃玩家
        result += f"\n━━━━━━━━━━━━━━\n"
        result += f" 活跃玩家（{len(active_users)}人）\n"
        
        if active_users:
            # 按段位排序显示
            DAN_WEIGHT = {'九段': 9, '八段': 8, '七段': 7, '六段': 6, '五段': 5,
                          '四段': 4, '三段': 3, '二段': 2, '一段': 1, '初段': 0}
            sorted_users = sorted(active_users, key=lambda u: DAN_WEIGHT.get(u.dan, 0), reverse=True)
            
            # 显示在线状态
            for user in sorted_users:
                status = "🟢 对局中" if user.nickname in playing_players else "⚪ 空闲"
                result += f"  {user.nickname} | {user.dan} | {status}\n"
        else:
            result += "  暂无活跃玩家\n"
        
        # 显示空闲玩家统计
        if free_players:
            result += f"\n 空闲玩家（{len(free_players)}人）："
            free_names = [u.nickname for u in free_players[:5]]  # 只显示前5个
            result += "、".join(free_names)
            if len(free_players) > 5:
                result += f" 等{len(free_players)}人"
            result += "\n"
        
        result += "\n━━━━━━━━━━━━━━\n"
        result += " 使用 /开局 玩家1 玩家2 玩家3 玩家4 开始新对局\n"
        result += " 使用 /录分 东家分数 南家分数 西家分数 北家分数 录入分数"
        
        await live_cmd.send(result.strip())
        return
        
    except Exception as e:
        await live_cmd.send(f"查询失败：{str(e)}")
        return
    finally:
        session.close()