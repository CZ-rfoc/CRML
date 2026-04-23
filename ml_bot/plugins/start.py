from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from nonebot.rule import to_me
import sys
from pathlib import Path
import random
import uuid
import json

sys.path.append(str(Path(__file__).parent.parent))
from utils.database import Session
from config import User, GameProgress

# 创建开局命令
start_game = on_command("开局", aliases={"开一局", "kj","start"})

@start_game.handle()
async def handle_start_game(event: MessageEvent, args=CommandArg()):
    """
    开局
    格式：/开局 玩家1 玩家2 玩家3 玩家4
    示例：/开局 张三 李四 王五 赵六
    """
    args_str = args.extract_plain_text().strip()
    players = args_str.split()
    
    # 验证参数数量
    if len(players) != 4:
        await start_game.send(
            "参数格式错误！\n"
            "正确格式：/开局 玩家1 玩家2 玩家3 玩家4\n"
            "示例：/开局 张三 李四 王五 赵六"
        )
        return
    
    session = Session()
    try:
        # 验证玩家是否存在且活跃
        user_objects = []
        for player in players:
            user = session.query(User).filter(User.nickname == player).first()
            if not user:
                await start_game.send(f"玩家「{player}」不存在！请先注册")
                return
            if not user.active:
                await start_game.send(f"玩家「{player}」当前处于休眠状态，无法参与对局")
                return
            user_objects.append(user)
        
        # 检查这些玩家是否已经在进行中的对局里
        ongoing_progress = session.query(GameProgress).filter(
            GameProgress.status == "ongoing"
        ).all()
        
        locked_players = set()
        for progress in ongoing_progress:
            try:
                for p in progress.get_players():
                    locked_players.add(p["nickname"])
            except:
                pass
        
        for player in players:
            if player in locked_players:
                await start_game.send(f"玩家「{player}」已在其他进行中的对局中，请等待该对局结束")
                return
        
        # 随机分配东南西北
        seats = ["东", "南", "西", "北"]
        random.shuffle(seats)
        
        # 创建玩家列表（按座位顺序）
        seat_players = []
        for i, seat in enumerate(seats):
            seat_players.append({
                "nickname": players[i],
                "seat": seat,
                "avatar": user_objects[i].avatar
            })
        
        # 创建对局进度记录
        progress_id = str(uuid.uuid4())
        progress = GameProgress(
            id=progress_id,
            status="ongoing"
        )
        # 使用 set_players 方法存储玩家信息
        progress.set_players(seat_players)
        
        session.add(progress)
        session.commit()
        
        # 构建返回消息
        result = "对局创建成功！\n━━━━━━━━━━━━━━\n 座位分配：\n"
        
        # 按东、南、西、北顺序显示
        seat_order = ["东", "南", "西", "北"]
        for seat in seat_order:
            for p in seat_players:
                if p["seat"] == seat:
                    result += f"  {seat}家：{p['nickname']}\n"
        
        result += f"\n 对局ID：{progress_id[:8]}...\n"
        result += "\n 录入分数：/录分 东家分数 南家分数 西家分数 北家分数\n"
        result += "   示例：/录分 25000 24000 23000 28000"
        
        # 使用 send 而不是 finish，避免 FinishedException
        await start_game.send(result.strip())
        return
        
    except Exception as e:
        session.rollback()
        await start_game.send(f"开局失败：{str(e)}")
        return
    finally:
        session.close()