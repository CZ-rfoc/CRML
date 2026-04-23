import os
import shutil
import time
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

from app import app as flask_app  # 导入Flask应用实例
from app import db, User          # 导入数据库实例和User模型
from config import BEIJING_TZ     # 导入北京时区配置（若config.py可直接导入）

# -------------------------- 配置项 --------------------------
# 数据库文件路径（当前目录下的mahjong.db）
DB_SOURCE_PATH = os.path.join(os.path.dirname(__file__), "mahjong.db")
# 备份文件夹路径（当前目录下的backup）
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backup")
# 备份时间
BACKUP_HOUR = 5
BACKUP_MINUTE = 1
BACKUP_SECOND = 0
# 重置玩家状态的定时时间
RESET_STATUS_HOUR = 5
RESET_STATUS_MINUTE = 0
RESET_STATUS_SECOND = 0


# -------------------------- 重置所有玩家活跃状态函数 --------------------------
def reset_all_user_active_status():
    """
    定时任务：将所有用户的active字段置为False（不活跃）
    需在Flask应用上下文中执行，否则无法操作数据库
    """
    with flask_app.app_context():  # 手动推入Flask应用上下文
        try:
            # 查询所有用户，批量更新active=False
            User.query.update({User.active: False})
            db.session.commit()
            print(f"[{datetime.now(BEIJING_TZ)}] 定时任务执行成功：所有玩家活跃状态已重置为不活跃")
        except Exception as e:
            db.session.rollback()  # 出错回滚
            print(f"[{datetime.now(BEIJING_TZ)}] 定时任务执行失败：{str(e)}")


# -------------------------- 备份函数 --------------------------
def backup_mahjong_db():
    """
    备份mahjong.db到backup文件夹，命名为mahjong.月.日.db
    """
    try:
        # 1. 检查源文件是否存在
        if not os.path.exists(DB_SOURCE_PATH):
            print(f"[{get_beijing_time()}] 错误：源文件 {DB_SOURCE_PATH} 不存在，跳过备份")
            return

        # 2. 创建backup文件夹（若不存在）
        os.makedirs(BACKUP_DIR, exist_ok=True)

        # 3. 获取北京时间的当前月、日
        beijing_tz = pytz.timezone('Asia/Shanghai')
        now = datetime.now(beijing_tz)
        month = now.month
        day = now.day

        # 4. 拼接备份文件名和路径
        backup_filename = f"mahjong.{month}.{day}.db"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        # 5. 复制文件（覆盖同名文件，避免重复备份报错）
        shutil.copy2(DB_SOURCE_PATH, backup_path)  # copy2保留文件元数据

        print(f"[{get_beijing_time()}] 备份成功：{backup_path}")

    except Exception as e:
        print(f"[{get_beijing_time()}] 备份失败：{str(e)}")


# -------------------------- 辅助函数 --------------------------
def get_beijing_time():
    """获取格式化的北京时间"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")


# -------------------------- 定时任务配置 --------------------------
def start_scheduler():
    """启动定时任务调度器"""
    # 创建调度器
    scheduler = BackgroundScheduler(timezone='Asia/Shanghai')

    # 1. 添加：备份数据库任务
    scheduler.add_job(
        func=backup_mahjong_db,
        trigger='cron',
        hour=BACKUP_HOUR,
        minute=BACKUP_MINUTE,
        second=BACKUP_SECOND,
        id='mahjong_db_backup',
        replace_existing=True
    )

    # 2. 添加：重置玩家活跃状态任务
    scheduler.add_job(
        func=reset_all_user_active_status,
        trigger='cron',
        hour=RESET_STATUS_HOUR,
        minute=RESET_STATUS_MINUTE,
        second=RESET_STATUS_SECOND,
        id='reset_user_active',
        replace_existing=True
    )

    # 启动调度器
    scheduler.start()
    print(f"[{get_beijing_time()}] 定时备份任务已启动，每天{BACKUP_HOUR}:{BACKUP_MINUTE}执行")
    print(f"[{get_beijing_time()}] 定时重置玩家状态任务已启动，每天{RESET_STATUS_HOUR}:{RESET_STATUS_MINUTE}执行")

    # 注册退出钩子：程序停止时关闭调度器（防止进程残留）
    atexit.register(lambda: scheduler.shutdown())


# -------------------------- 手动触发备份 --------------------------
def manual_backup():
    """手动触发一次备份（用于测试）"""
    print(f"[{get_beijing_time()}] 手动触发备份...")
    backup_mahjong_db()


# -------------------------- 主程序 --------------------------
if __name__ == "__main__":

    # manual_backup()

    # 启动定时任务（同时包含备份和重置玩家状态）
    start_scheduler()

    # 保持脚本运行（防止主线程退出）
    try:
        while True:
            time.sleep(3600)  # 每小时检查一次
    except KeyboardInterrupt:
        print(f"\n[{get_beijing_time()}] 手动停止备份脚本")