import sys
from pathlib import Path
import os
sys.path.extend(str(Path(__file__).parent.parent.parent))
sys.path.extend(str(Path(__file__).parent.parent))
from config import (config, User, GameRecord, GameProgress)
from utils.database import Session
from utils.generate_query import generate_player_card
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent,MessageSegment
from nonebot.params import CommandArg

query = on_command("查询",aliases={'cy','吃鱼'})

@query.handle()
async def handle_echo(event: MessageEvent, args = CommandArg()):
    """查询个人画像"""
    qq_num=event.get_user_id()
    session=Session()
    user=session.query(User).filter(User.bd_qq==qq_num).first()
    if user is None:
        await query.finish("账户不存在！请使用/绑定 网站注册名称进行绑定")
    else:
        await query.send("正在生成查询图......")
        nickname=user.nickname
        user_records = []
        records=session.query(GameRecord).all()
        for r in records:
            for p in r.get_players():
                if p["nickname"] == nickname:
                    user_records.append(p)
        total_games=len(user_records)
        avg_score = round(sum(p["score"] for p in user_records) / total_games, 0) if total_games > 0 else 0
        max_score = round(max(p["score"] for p in user_records),0)if total_games > 0 else 0
        avg_rank = round(sum(p["rank"] for p in user_records) / total_games, 1) if total_games > 0 else 0
        avg_pt = round(sum(p["pt"] for p in user_records) / total_games, 1) if total_games > 0 else 0
        rank_count = {1: 0, 2: 0, 3: 0, 4: 0}
        for p in user_records:
            rank_count[p["rank"]] += 1
        rank_rate = [rank_count[1], rank_count[2], rank_count[3], rank_count[4]]
        last_10_ranks = [p["rank"] for p in user_records[-10:]] if total_games > 0 else []
        avartar_path=f"static/uploads/{user.avatar}"
        img_path=generate_player_card(nickname,avartar_path,user.dan,user.dan_pt,avg_score,max_score,total_games,avg_rank,avg_pt,rank_count,last_10_ranks)
        if img_path:
            await query.send(MessageSegment.image(img_path))
        if os.path.exists(img_path):
            os.remove(img_path)
            await query.finish("已生成完成，本次生成消耗*error*token")
        