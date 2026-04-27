from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os

# 数据库文件路径(默认基于文件夹下)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'mahjong.db')

# 创建数据库引擎
engine = create_engine(
    f'sqlite:///{DB_PATH}',
    echo=False,
    connect_args={'check_same_thread': False}  # SQLite多线程必需
)

# 创建线程安全的会话
Session = scoped_session(sessionmaker(bind=engine))
