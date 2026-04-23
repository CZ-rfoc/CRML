from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg
from utils.database import Session
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config import User, GameProgress
# 临时删除对局命令
del_game = on_command("删对局", aliases={"删除对局"}, block=True)

@del_game.handle()
async def handle_del_game(event: MessageEvent, args=CommandArg()):
    """删除指定的对局（紧急修复用）"""
    game_id = args.extract_plain_text().strip()
    
    if not game_id:
        await del_game.finish("请提供对局ID，例如：/删对局 8b434b38")
    
    session = Session()
    try:
        # 支持输入完整ID或前8位
        if len(game_id) == 8:
            progress = session.query(GameProgress).filter(
                GameProgress.id.like(f"{game_id}%")
            ).first()
        else:
            progress = session.query(GameProgress).filter(
                GameProgress.id == game_id
            ).first()
        
        if not progress:
            await del_game.finish(f"未找到对局ID：{game_id}")
        
        # 获取对局信息用于提示
        players = progress.get_players() if hasattr(progress, 'get_players') else []
        player_names = [p["nickname"] for p in players] if players else []
        
        # 删除对局
        session.delete(progress)
        session.commit()
        
        await del_game.finish(
            f" 已删除对局\n"
            f"ID：{progress.id[:8]}...\n"
            f"玩家：{'、'.join(player_names)}"
        )
    except Exception as e:
        session.rollback()
        await del_game.finish(f"删除失败：{str(e)}")
    finally:
        session.close()