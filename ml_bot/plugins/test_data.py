from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.rule import to_me
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from utils.database import Session
from config import User, GameRecord
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

upload_score = on_command("强制录入分数")

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
    """
    更新用户段位和段内PT（与网页端逻辑完全一致）
    返回：段位变化消息（如果有）
    """
    # 段内PT累加本局PT
    user.dan_pt = round(user.dan_pt + game_pt, 1)
    messages = []
    
    # 升段逻辑
    if user.dan_pt >= user.promote_cond and get_dan_index(user.dan) < 9:
        new_dan_idx = get_dan_index(user.dan) + 1
        new_dan = DAN_ORDER[new_dan_idx]
        user.dan = new_dan
        user.promote_cond = DAN_INFO[new_dan][0]
        user.dan_pt = DAN_INFO[new_dan][1]
        messages.append(f"🎉 恭喜升段至{new_dan}！段内PT重置为{user.dan_pt}")
    
    # 降段逻辑（初段/一段/二段掉段保护）
    elif user.dan_pt < 0:
        if user.dan in ["初段", "一段", "二段"]:
            user.dan_pt = 0.0
            messages.append("⚠️ 段内PT不足，已重置为0（掉段保护）")
        else:  # 三段及以上降段
            new_dan_idx = get_dan_index(user.dan) - 1
            new_dan = DAN_ORDER[new_dan_idx]
            user.dan = new_dan
            user.promote_cond = DAN_INFO[new_dan][0]
            user.dan_pt = DAN_INFO[new_dan][1]
            messages.append(f"⚠️ 段内PT不足，降段至{new_dan}！段内PT重置为{user.dan_pt}")
    
    return " / ".join(messages) if messages else None

@upload_score.handle()
async def handle_upload_score(event: MessageEvent, args=CommandArg()):
    """上传分数"""
    args_str = args.extract_plain_text().strip()
    parts = args_str.split()
    
    if len(parts) != 8:
        await upload_score.send(
            "参数格式错误！\n"
            "正确格式：/上传分数 玩家1 分数1 玩家2 分数2 玩家3 分数3 玩家4 分数4\n"
            "示例：/上传分数 张三 25000 李四 24000 王五 23000 赵六 28000"
        )
        return
    
    # 提取数据
    players = []
    scores = []
    for i in range(4):
        players.append(parts[i * 2])
        try:
            scores.append(int(parts[i * 2 + 1]))
        except ValueError:
            await upload_score.send(f"分数必须是整数！{parts[i * 2 + 1]} 不是有效数字")
            return
    
    # 验证分数总和
    if sum(scores) != 100000:
        await upload_score.send(
            f"分数总和必须为100000！当前总和：{sum(scores)}"
        )
        return
    
    session = Session()
    try:
        # 验证玩家是否存在
        user_objects = []
        for player in players:
            user = session.query(User).filter(User.nickname == player).first()
            if not user:
                await upload_score.send(f"玩家「{player}」不存在！")
                return
            user_objects.append(user)
        
        # 计算名次和PT
        ranks = calculate_ranks(scores)
        pts = [calculate_pt(scores[i], ranks[i], ranks) for i in range(4)]
        
        # 创建对局记录
        game_time = datetime.now(BEIJING_TZ)
        record = GameRecord(
            game_time=game_time,
            u1_nickname=players[0], u1_score=scores[0], u1_rank=ranks[0], u1_pt=pts[0],
            u2_nickname=players[1], u2_score=scores[1], u2_rank=ranks[1], u2_pt=pts[1],
            u3_nickname=players[2], u3_score=scores[2], u3_rank=ranks[2], u3_pt=pts[2],
            u4_nickname=players[3], u4_score=scores[3], u4_rank=ranks[3], u4_pt=pts[3]
        )
        session.add(record)
        
        # 更新玩家数据
        dan_messages = []
        for i, user in enumerate(user_objects):
            # 增加西瓜币
            user.melon_count += 5
            # 更新段位（与网页端逻辑一致）
            msg = update_user_dan(user, pts[i])
            if msg:
                dan_messages.append(f"{players[i]}: {msg}")
        
        session.commit()
        
        # 构建回复
        result = "✅ 分数录入成功！\n━━━━━━━━━━━━━━━━━━━━\n📊 本局结果：\n"
        sorted_data = sorted(zip(players, scores, ranks, pts), key=lambda x: x[2])
        rank_emoji = {1: "🥇", 2: "🥈", 3: "🥉", 4: "💀"}
        for player, score, rank, pt in sorted_data:
            result += f"{rank_emoji[rank]} {player}: {score}分 | 名次{rank} | PT{pt:+.1f}\n"
        
        if dan_messages:
            result += "\n\n📢 段位变化：\n" + "\n".join(f"  {msg}" for msg in dan_messages)
        
        await upload_score.send(result.strip())
        return
        
    except Exception as e:
        session.rollback()
        await upload_score.send(f"录入失败：{str(e)}")
    finally:
        session.close()