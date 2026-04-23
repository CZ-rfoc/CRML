from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

Base = declarative_base()

class User(Base):
    """用户表"""
    __tablename__ = 'user'
    
    nickname = Column(String(50), primary_key=True)
    avatar = Column(String(200), default='default_icon.png')
    melon_count = Column(Integer, default=0)
    dan = Column(String(20), default='初段')
    promote_cond = Column(Float, default=300.0)
    dan_pt = Column(Float, default=0.0)
    active = Column(Boolean, default=True)
    
    def get_dan_index(self):
        DAN_ORDER = ["初段", "一段", "二段", "三段", "四段", "五段", "六段", "七段", "八段", "九段"]
        return DAN_ORDER.index(self.dan)

class GameRecord(Base):
    """对局记录表"""
    __tablename__ = 'game_record'
    
    game_time = Column(DateTime, primary_key=True, default=datetime.now)
    u1_nickname = Column(String(50))
    u1_rank = Column(Integer)
    u1_score = Column(Integer)
    u1_pt = Column(Float)
    u2_nickname = Column(String(50))
    u2_rank = Column(Integer)
    u2_score = Column(Integer)
    u2_pt = Column(Float)
    u3_nickname = Column(String(50))
    u3_rank = Column(Integer)
    u3_score = Column(Integer)
    u3_pt = Column(Float)
    u4_nickname = Column(String(50))
    u4_rank = Column(Integer)
    u4_score = Column(Integer)
    u4_pt = Column(Float)
    
    def get_players(self):
        return [
            {"nickname": self.u1_nickname, "rank": self.u1_rank, "score": self.u1_score, "pt": self.u1_pt},
            {"nickname": self.u2_nickname, "rank": self.u2_rank, "score": self.u2_score, "pt": self.u2_pt},
            {"nickname": self.u3_nickname, "rank": self.u3_rank, "score": self.u3_score, "pt": self.u3_pt},
            {"nickname": self.u4_nickname, "rank": self.u4_rank, "score": self.u4_score, "pt": self.u4_pt}
        ]

class GameProgress(Base):
    """对局进度表"""
    __tablename__ = 'game_progress'
    
    id = Column(String(36), primary_key=True)
    status = Column(String(20), default='ongoing')
    players_json = Column(JSON, default=list)
    
    def set_players(self, players):
        self.players_json = players
    
    def get_players(self):
        return self.players_json if self.players_json else []