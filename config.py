import os
from datetime import datetime, timedelta
import pytz
import json
from flask_sqlalchemy import SQLAlchemy

# 初始化SQLAlchemy，操作SQLite数据库
db = SQLAlchemy()

# 项目根目录
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# 登录密码(部署时要改）
ADMIN_PASS = "rfocrfoc"

# 邀请码-学校映射表
INVITE_CODE_SCHOOL = {
    "xigongda": "西北工业大学",
    "xidian": "西安电子科技大学",
    "xijiao": "西安交通大学",
    "xijianda": "西安建筑科技大学"
}


class Config:
    # Flask密钥
    SECRET_KEY = "mahjong_site_2026_melon_rfocrfoc"
    # SQLite数据库路径（自动创建在根目录）
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'mahjong.db')}"
    # 关闭SQLAlchemy修改跟踪
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # 头像上传目录
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static/uploads")
    # 最大上传文件大小（2MB）
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    # 允许的头像后缀
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
    # 会话过期时间（24小时）
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)


# 开发环境配置（直接使用）
config = Config()

# -------------------------- 核心常量（段位/升段条件/初始段内PT） --------------------------
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
BEIJING_TZ = pytz.timezone("Asia/Shanghai")

# 段位权重字典
DAN_WEIGHT = {
    '九段': 9, '八段': 8, '七段': 7, '六段': 6, '五段': 5,
    '四段': 4, '三段': 3, '二段': 2, '一段': 1, '初段': 0
}


# -------------------------- 数据库模型 --------------------------
# 用户表
class User(db.Model):
    __tablename__ = "user"
    user_id = db.Column(db.Integer, primary_key=True, comment="8位数字用户ID（主键）")
    nickname = db.Column(db.String(50), unique=True, nullable=False, comment="用户昵称（唯一）")
    melon_count = db.Column(db.Integer, default=0, comment="积分个数")
    dan = db.Column(db.String(10), default="初段", comment="段位（初段-九段）")
    promote_cond = db.Column(db.Float, default=DAN_INFO["初段"][0], comment="升段条件")
    dan_pt = db.Column(db.Float, default=DAN_INFO["初段"][1], comment="段内PT")
    active = db.Column(db.Boolean, default=False, comment="活动状态（True/False）")
    avatar = db.Column(db.String(100), default="default_icon.png", comment="头像文件名")
    bd_qq = db.Column(db.String(20), default="", comment="绑定QQ")
    # 新增字段：学校、MD5密码
    school = db.Column(db.String(50), default="", comment="所属学校")
    password = db.Column(db.String(32), default="", comment="密码（MD5加密）")

    def get_dan_index(self):
        return DAN_ORDER.index(self.dan)

    def band(self, qq_num):
        self.bd_qq = qq_num
        return

    def activate(self):
        self.active = True
        return

    def inactivate(self):
        self.active = False
        return

    def get_dan(self):
        return self.dan, self.dan_pt, self.promote_cond

    def get_name(self):
        return self.nickname


# 对局记录表
class GameRecord(db.Model):
    __tablename__ = "game_record"
    game_time = db.Column(db.DateTime, primary_key=True, default=lambda: datetime.now(BEIJING_TZ), comment="对局时间")
    progress_id = db.Column(db.String(64), unique=True, nullable=True, comment="对局进度ID")
    # 替换昵称字段为用户ID（Integer类型）
    u1_user_id = db.Column(db.Integer, comment="玩家1用户ID")
    u1_rank = db.Column(db.Integer, comment="玩家1名次")
    u1_score = db.Column(db.Integer, comment="玩家1素点")
    u1_pt = db.Column(db.Float, comment="玩家1PT")

    u2_user_id = db.Column(db.Integer, comment="玩家2用户ID")
    u2_rank = db.Column(db.Integer, comment="玩家2名次")
    u2_score = db.Column(db.Integer, comment="玩家2素点")
    u2_pt = db.Column(db.Float, comment="玩家2PT")

    u3_user_id = db.Column(db.Integer, comment="玩家3用户ID")
    u3_rank = db.Column(db.Integer, comment="玩家3名次")
    u3_score = db.Column(db.Integer, comment="玩家3素点")
    u3_pt = db.Column(db.Float, comment="玩家3PT")

    u4_user_id = db.Column(db.Integer, comment="玩家4用户ID")
    u4_rank = db.Column(db.Integer, comment="玩家4名次")
    u4_score = db.Column(db.Integer, comment="玩家4素点")
    u4_pt = db.Column(db.Float, comment="玩家4PT")

    def get_players(self):
        """通过用户ID查询用户信息，返回包含昵称的玩家列表"""
        players = []
        # 遍历4个玩家的字段
        for i in range(1, 5):
            user_id = getattr(self, f"u{i}_user_id")
            rank = getattr(self, f"u{i}_rank")
            score = getattr(self, f"u{i}_score")
            pt = getattr(self, f"u{i}_pt")

            # 查询用户信息
            user = User.query.get(user_id)
            nickname = user.nickname if user else "未知用户"

            players.append({
                "user_id": user_id,
                "nickname": nickname,
                "rank": rank,
                "score": score,
                "pt": pt
            })
        return players


# 新增：游戏进度表
class GameProgress(db.Model):
    __tablename__ = "game_progress"
    id = db.Column(db.String(36), primary_key=True, comment="对局唯一ID（UUID）")
    # 存储用户ID相关的座次信息（JSON格式：[{user_id, seat, avatar}, ...]）
    players = db.Column(db.Text, comment="4位玩家座次信息（JSON格式：[{user_id, seat, avatar}, ...]）")
    create_time = db.Column(db.DateTime, default=lambda: datetime.now(BEIJING_TZ), comment="创建时间")
    status = db.Column(db.String(20), default="ongoing",
                       comment="状态：ongoing(进行中)/completed(已完成)/dissolved(已解散)")

    # 序列化玩家信息（基于user_id）
    def get_players(self):
        return json.loads(self.players) if self.players else []

    # 更新玩家信息（基于user_id）
    def set_players(self, players_list):
        self.players = json.dumps(players_list, ensure_ascii=False)