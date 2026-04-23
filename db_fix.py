import sqlite3

# 连接到数据库
conn = sqlite3.connect('mahjong.db')  # 数据库文件路径保持不变
cursor = conn.cursor()

# 添加 progress_id 列（整数类型，存储对局ID）
try:
    cursor.execute("ALTER TABLE game_record ADD COLUMN progress_id INTEGER")
    conn.commit()
    print("Column added successfully")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()