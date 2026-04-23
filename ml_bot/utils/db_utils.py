from .database import SessionLocal
from .models import User, GameRecord, GameProgress
from datetime import datetime, timedelta
import pytz

# 北京时间时区
BEIJING_TZ = pytz.timezone('Asia/Shanghai')

DAN_ORDER = ["初段", "一段", "二段", "三段", "四段", "五段", "六段", "七段", "八段", "九段"]
DAN_INFO = {
    "初段": (300.0, 0.0),
    "一段": (300.0, 0.0),
    "二段": (300.0, 0.0),
    "三段": (300.0, 0.0),
    "四段": (300.0, 0.0),
    "五段": (300.0, 0.0),
    "六段": (300.0, 0.0),
    "七段": (300.0, 0.0),
    "八段": (300.0, 0.0),
    "九段": (0.0, 0.0)
}
DAN_WEIGHT = {
    "初段": 1, "一段": 2, "二段": 3, "三段": 4,
    "四段": 5, "五段": 6, "六段": 7, "七段": 8,
    "八段": 9, "九段": 10
}

def get_user(nickname):
    """获取用户信息"""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.nickname == nickname).first()
    finally:
        db.close()

def get_all_users(active_only=True):
    """获取所有用户"""
    db = SessionLocal()
    try:
        query = db.query(User)
        if active_only:
            query = query.filter(User.active == True)
        return query.all()
    finally:
        db.close()

def get_user_stats(nickname):
    """获取用户统计数据"""
    db = SessionLocal()
    try:
        # 获取用户所有对局记录
        records = db.query(GameRecord).all()
        user_records = []
        for r in records:
            for p in r.get_players():
                if p["nickname"] == nickname:
                    user_records.append(p)
        
        total_games = len(user_records)
        if total_games == 0:
            return {
                "total_games": 0,
                "avg_score": 0,
                "avg_rank": 0,
                "avg_pt": 0,
                "rank_rate": [0, 0, 0, 0],
                "last_10_ranks": []
            }
        
        avg_score = round(sum(p["score"] for p in user_records) / total_games, 0)
        avg_rank = round(sum(p["rank"] for p in user_records) / total_games, 1)
        avg_pt = round(sum(p["pt"] for p in user_records) / total_games, 1)
        
        rank_count = {1: 0, 2: 0, 3: 0, 4: 0}
        for p in user_records:
            rank_count[p["rank"]] += 1
        rank_rate = [rank_count[1], rank_count[2], rank_count[3], rank_count[4]]
        last_10_ranks = [p["rank"] for p in user_records[-10:]]
        
        return {
            "total_games": total_games,
            "avg_score": avg_score,
            "avg_rank": avg_rank,
            "avg_pt": avg_pt,
            "rank_rate": rank_rate,
            "last_10_ranks": last_10_ranks
        }
    finally:
        db.close()

def get_monthly_ranking():
    """获取本月PT排名"""
    db = SessionLocal()
    try:
        now = datetime.now(BEIJING_TZ)
        month_start = datetime(now.year, now.month, 1, tzinfo=BEIJING_TZ)
        month_end = datetime(now.year, now.month + 1, 1, tzinfo=BEIJING_TZ) if now.month < 12 else datetime(now.year + 1, 1, 1, tzinfo=BEIJING_TZ)
        
        records = db.query(GameRecord).filter(
            GameRecord.game_time >= month_start,
            GameRecord.game_time < month_end
        ).all()
        
        pt_total = {}
        for r in records:
            for p in r.get_players():
                nick = p["nickname"]
                pt = p["pt"]
                pt_total[nick] = pt_total.get(nick, 0) + pt
        
        sorted_ranking = sorted(pt_total.items(), key=lambda x: -x[1])
        return sorted_ranking
    finally:
        db.close()

def update_user_pt(nickname, pt_change):
    """更新用户PT（用于机器人录入分数）"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.nickname == nickname).first()
        if not user:
            return False, "用户不存在"
        
        user.dan_pt = round(user.dan_pt + pt_change, 1)
        
        # 升段逻辑
        if user.dan_pt >= user.promote_cond and user.get_dan_index() < 9:
            new_dan_idx = user.get_dan_index() + 1
            new_dan = DAN_ORDER[new_dan_idx]
            user.dan = new_dan
            user.promote_cond = DAN_INFO[new_dan][0]
            user.dan_pt = DAN_INFO[new_dan][1]
            db.commit()
            return True, f"恭喜升段至{new_dan}！"
        
        # 降段逻辑
        elif user.dan_pt < 0:
            if user.dan in ["初段", "一段", "二段"]:
                user.dan_pt = 0.0
                db.commit()
                return True, f"段内PT不足，已重置为0（掉段保护）"
            else:
                new_dan_idx = user.get_dan_index() - 1
                new_dan = DAN_ORDER[new_dan_idx]
                user.dan = new_dan
                user.promote_cond = DAN_INFO[new_dan][0]
                user.dan_pt = DAN_INFO[new_dan][1]
                db.commit()
                return True, f"降段至{new_dan}"
        
        db.commit()
        return True, "更新成功"
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()
