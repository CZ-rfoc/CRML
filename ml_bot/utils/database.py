from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
import os

# 数据库文件路径（相对于这个文件的位置）
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'mahjong.db')

# 创建数据库引擎
engine = create_engine(
    f'sqlite:///{DB_PATH}',
    echo=False,
    connect_args={'check_same_thread': False}  # SQLite多线程必需
)

# 创建线程安全的会话
Session = scoped_session(sessionmaker(bind=engine))

# 导入你的模型（如果已经在 utils 中定义了）
# 如果没有，你需要在这里定义或从其他地方导入