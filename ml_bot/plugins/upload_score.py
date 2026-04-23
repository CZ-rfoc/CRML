from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
import sys
from pathlib import Path
sys.path.extend(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))
from utils.database import Session
from config import User, GameRecord, GameProgress
from datetime import datetime
import pytz

BEIJING_TZ = pytz.timezone('Asia/Shanghai')

# 段位配置
DAN_ORDER = ["初段", "一段", "二段", "三段", "四段", "五段", "六段", "七段", "八段", "九段"]
DAN_INFO = {
    "初段": (100.0, 50.0),
    "一段": (200.0, 100.0),
    "二段": (300.0, 150.0),
    "三段": (400.0, 200.0),
    "四段": (500.0, 250.0),
    "五段": (600.0, 300.0),
    "六段": (800.0, 400.0),
    "七段": (1000.0, 500.0),
    "八段": (1200.0, 600.0),
    "九段": (10000.0, 0.0)
}

# 创建命令（不需要@）
record_score = on_command("录分", aliases={"lf", "记分"}, block=True)

def calculate_ranks(scores):
    """计算名次"""
    sorted_with_idx = sorted(enumerate(scores), key=lambda x: -x[1])
    ranks = [0] * 4
    sorted_scores = [s for _, s in sorted_with_idx]
    
    for i, (idx, score) in enumerate(sorted_with_idx):
        if i == 0:
            ranks[idx] = 1
        elif score == sorted_scores[i - 1]:
            ranks[idx] = ranks[sorted_with_idx[i - 1][0]]
        else:
            ranks[idx] = i + 1
    return ranks

def calculate_pt(score, rank, all_ranks):
    """计算PT"""
    rank_count = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in all_ranks:
        rank_count[r] += 1
    
    if rank_count[1] == 2:  # 并列第一
        bonus = 25.0 if rank == 1 else (-15.0 if rank == 3 else -35.0)
    elif rank_count[2] == 2:  # 并列第二
        bonus = 45.0 if rank == 1 else (-5.0 if rank == 2 else -35.0)
    elif rank_count[3] == 2:  # 并列第三
        bonus = 45.0 if rank == 1 else (5.0 if rank == 2 else -25.0)
    else:  # 无并列
        bonus = 45.0 if rank == 1 else (5.0 if rank == 2 else (-15.0 if rank == 3 else -35.0))
    
    return round(score / 1000 + bonus - 25.0, 1)

def get_dan_index(dan):
    """获取段位索引"""
    return DAN_ORDER.index(dan)

def update_user_dan(user, game_pt):
    """更新用户段位和段内PT"""
    user.dan_pt = round(user.dan_pt + game_pt, 1)
    messages = []
    
    # 升段逻辑
    if user.dan_pt >= user.promote_cond and get_dan_index(user.dan) < 9:
        new_dan_idx = get_dan_index(user.dan) + 1
        new_dan = DAN_ORDER[new_dan_idx]
        user.dan = new_dan
        user.promote_cond = DAN_INFO[new_dan][0]
        user.dan_pt = DAN_INFO[new_dan][1]
        messages.append(f" 恭喜升段至{new_dan}！段内PT重置为{user.dan_pt}")
    
    # 降段逻辑
    elif user.dan_pt < 0:
        if user.dan in ["初段", "一段", "二段"]:
            user.dan_pt = 0.0
            messages.append("段内PT不足，已重置为0（掉段保护）")
        else:
            new_dan_idx = get_dan_index(user.dan) - 1
            new_dan = DAN_ORDER[new_dan_idx]
            user.dan = new_dan
            user.promote_cond = DAN_INFO[new_dan][0]
            user.dan_pt = DAN_INFO[new_dan][1]
            messages.append(f"段内PT不足，降段至{new_dan}！段内PT重置为{user.dan_pt}")
    
    return " / ".join(messages) if messages else None

@record_score.handle()
async def handle_record_score(event: MessageEvent, args=CommandArg()):
    """
    录入分数（自动检测玩家对局）
    格式：/录分 东家分数 南家分数 西家分数 北家分数
    示例：/录分 25000 24000 23000 28000
    """
    qq_num = event.get_user_id()
    args_str = args.extract_plain_text().strip()
    parts = args_str.split()
    
    # 验证参数数量
    if len(parts) != 4:
        await record_score.send(
            "参数格式错误！\n"
            "正确格式：/录分 东家分数 南家分数 西家分数 北家分数\n"
            "示例：/录分 25000 24000 23000 28000\n\n"
            "注意：分数顺序必须对应东、南、西、北四个方位"
        )
        return
    
    # 解析分数
    try:
        scores = [int(p) for p in parts]
    except ValueError:
        await record_score.send("分数必须是整数！")
        return
    
    # 验证分数总和
    if sum(scores) != 100000:
        await record_score.send(
            f"分数总和必须为100000！当前总和：{sum(scores)}"
        )
        return
    
    session = Session()
    try:
        # 通过QQ号查找当前用户
        current_user = session.query(User).filter(User.bd_qq == qq_num).first()
        if not current_user:
            await record_score.send("您尚未绑定游戏账号！请先使用 /绑定 进行绑定")
            return
        
        # 查找当前用户参与的所有进行中的对局
        ongoing_progress = session.query(GameProgress).filter(
            GameProgress.status == "ongoing"
        ).all()
        
        # 筛选出包含当前用户的对局
        user_progress = []
        for progress in ongoing_progress:
            players = progress.get_players()
            player_nicks = [p["nickname"] for p in players]
            if current_user.nickname in player_nicks:
                user_progress.append(progress)
        
        if not user_progress:
            await record_score.send("您当前没有进行中的对局！请先创建对局")
            return
        
        if len(user_progress) > 1:
            # 理论上不应该发生，但以防万一
            await record_score.send("系统错误：您参与了多个进行中的对局，请联系管理员处理")
            return
        
        # 获取当前用户的对局
        progress = user_progress[0]
        players = progress.get_players()
        
        # 按东南西北顺序获取玩家信息
        seat_order = ["东", "南", "西", "北"]
        seat_players = {}
        for player in players:
            seat_players[player["seat"]] = player["nickname"]
        
        # 验证所有座位都有玩家
        for seat in seat_order:
            if seat not in seat_players:
                await record_score.send(f"对局配置错误：缺少{seat}家玩家")
                return
        
        # 按东南西北顺序获取玩家名
        selected_nicks = [seat_players[seat] for seat in seat_order]
        
        # 验证所有玩家是否存在
        user_objects = []
        for nick in selected_nicks:
            user = session.query(User).filter(User.nickname == nick).first()
            if not user:
                await record_score.send(f"玩家「{nick}」不存在！请先在网页端注册")
                return
            user_objects.append(user)
        
        # 计算名次和PT
        ranks = calculate_ranks(scores)
        pts = [calculate_pt(scores[i], ranks[i], ranks) for i in range(4)]
        
        # 创建对局记录
        game_time = datetime.now(BEIJING_TZ)
        record = GameRecord(
            game_time=game_time,
            u1_nickname=selected_nicks[0], u1_score=scores[0], u1_rank=ranks[0], u1_pt=pts[0],
            u2_nickname=selected_nicks[1], u2_score=scores[1], u2_rank=ranks[1], u2_pt=pts[1],
            u3_nickname=selected_nicks[2], u3_score=scores[2], u3_rank=ranks[2], u3_pt=pts[2],
            u4_nickname=selected_nicks[3], u4_score=scores[3], u4_rank=ranks[3], u4_pt=pts[3]
        )
        session.add(record)
        
        # 更新玩家数据
        dan_messages = []
        for i, user in enumerate(user_objects):
            user.melon_count += 5
            msg = update_user_dan(user, pts[i])
            if msg:
                dan_messages.append(f"{selected_nicks[i]}: {msg}")
        
        # 标记对局为已完成
        progress.status = "completed"
        session.commit()
        
        # 构建回复消息
        result = "分数录入成功！\n━━━━━━━━━━━━━━\n本局结果：\n"
        
        # 按名次排序显示
        data = []
        for i in range(4):
            data.append({
                "seat": seat_order[i],
                "nickname": selected_nicks[i],
                "score": scores[i],
                "rank": ranks[i],
                "pt": pts[i]
            })
        sorted_data = sorted(data, key=lambda x: x["rank"])
        
        rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉", 4: "💀"}
        for d in sorted_data:
            result += f"{rank_emoji[d['rank']]} {d['seat']}家 {d['nickname']}: {d['score']}分 | 名次{d['rank']} | PT{d['pt']:+.1f}\n"
        
        
        if dan_messages:
            result += "\n 段位变化：\n" + "\n".join(f"  {msg}" for msg in dan_messages)
        
        await record_score.send(result.strip())
        return
        
    except Exception as e:
        session.rollback()
        await record_score.send(f"录入失败：{str(e)}")
    finally:
        session.close()