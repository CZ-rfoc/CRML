import json
import os
import random
from pathlib import Path
import asyncio
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.params import CommandArg

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
sys.path.append(str(Path(__file__).parent.parent))
from utils.database import Session
from config import User, GameProgress
import uuid
from datetime import datetime
import pytz

BEIJING_TZ = pytz.timezone('Asia/Shanghai')

APPOINTMENT_FILE = Path(__file__).parent.parent / "appointments.json"

if not APPOINTMENT_FILE.exists():
    with open(APPOINTMENT_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)


def load_appointments():
    """加载预约对局数据"""
    with open(APPOINTMENT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_appointments(data):
    """保存预约对局数据"""
    with open(APPOINTMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


appointment = on_command("预约", aliases={"yy","ap"})

@appointment.handle()
async def handle_appointment(event: MessageEvent, args=CommandArg()):
    raw_args = args.extract_plain_text().strip()
    if not raw_args:
        await appointment.finish(
            "请提供子命令和参数，如：\n"
            "/预约 列表/list \n"
            "/预约 create [对局名]\n"
            "/预约 join [对局名]\n"
            "/预约 exit [对局名]\n"
            "/预约 disband [对局名]\n"
            "/预约 开局/kj [对局名]\n"

        )
    parts = raw_args.split(maxsplit=1)
    subcmd = parts[0].lower()
    param = parts[1] if len(parts) > 1 else ""

    if subcmd == "create":
        await create_room(event, param)
    elif subcmd == "join":
        await join_room(event, param)
    elif subcmd == "exit":
        await exit_room(event, param)
    elif subcmd == "disband":
        await disband_room(event, param)
    elif subcmd == "开局" or subcmd == "kj":
        await start_room(event, param)
    elif subcmd == "列表" or subcmd == "list":
        await list_rooms(event)
    else:
        await appointment.finish(f"未知子命令：{subcmd}")


async def create_room(event: MessageEvent, room_name: str):
    if not room_name:
        await appointment.finish("请提供对局名称，例如：/预约 create 一点")
    
    qq = event.get_user_id()
    session = Session()
    try:
        user = session.query(User).filter(User.bd_qq == qq).first()
        if not user:
            await appointment.finish("您尚未绑定游戏账号，请先使用 /绑定 昵称")
        nickname = user.nickname

        appointments = load_appointments()
        for name, data in appointments.items():
            if nickname in data.get("participants", []):
                await appointment.finish(f"您已在预约对局「{name}」中，请先退出")
        
        if room_name in appointments:
            await appointment.finish(f"对局名「{room_name}」已被使用")
        
        appointments[room_name] = {
            "creator": nickname,
            "participants": [nickname],
            "create_time": datetime.now(BEIJING_TZ).isoformat()
        }
        save_appointments(appointments)
        await appointment.finish(f"预约对局「{room_name}」创建成功！\n使用 /预约 join {room_name} 加入对局（当前1/4人）")
    finally:
        session.close()


async def join_room(event: MessageEvent, room_name: str):
    if not room_name:
        await appointment.finish("请提供对局名称，例如：/预约 join 欢乐局")
    
    qq = event.get_user_id()
    session = Session()
    try:
        user = session.query(User).filter(User.bd_qq == qq).first()
        if not user:
            await appointment.finish("您尚未绑定游戏账号，请先使用 /绑定 昵称")
        nickname = user.nickname

        appointments = load_appointments()
        if room_name not in appointments:
            await appointment.finish(f"预约对局「{room_name}」不存在")
        
        room = appointments[room_name]
        participants = room.get("participants", [])
        if nickname in participants:
            await appointment.finish(f"您已在「{room_name}」中")
        if len(participants) >= 4:
            await appointment.finish(f"对局已满员（4/4）")
        
        for name, data in appointments.items():
            if nickname in data.get("participants", []) and name != room_name:
                await appointment.finish(f"您已在预约对局「{name}」中，请先退出")
        
        participants.append(nickname)
        room["participants"] = participants
        save_appointments(appointments)
        await appointment.finish(f"{nickname} 已加入预约对局「{room_name}」 ({len(participants)}/4)")
    finally:
        session.close()


async def exit_room(event: MessageEvent, room_name: str):
    if not room_name:
        await appointment.finish("请提供对局名称，例如：/预约 exit 欢乐局")
    
    qq = event.get_user_id()
    session = Session()
    try:
        user = session.query(User).filter(User.bd_qq == qq).first()
        if not user:
            await appointment.finish("您尚未绑定游戏账号")
        nickname = user.nickname

        appointments = load_appointments()
        if room_name not in appointments:
            await appointment.finish(f"预约对局「{room_name}」不存在")
        
        room = appointments[room_name]
        participants = room.get("participants", [])
        if nickname not in participants:
            await appointment.finish(f"您不在对局「{room_name}」中")
        
        participants.remove(nickname)
        if not participants:
            del appointments[room_name]
        else:
            room["participants"] = participants
        save_appointments(appointments)
        await appointment.finish(f"{nickname} 已退出预约对局「{room_name}」 (剩余{len(participants)}人)")
    finally:
        session.close()


async def disband_room(event: MessageEvent, room_name: str):
    if not room_name:
        await appointment.finish("请提供对局名称，例如：/预约 disband 欢乐局")
    
    qq = event.get_user_id()
    session = Session()
    try:
        user = session.query(User).filter(User.bd_qq == qq).first()
        if not user:
            await appointment.finish("您尚未绑定游戏账号")
        nickname = user.nickname

        appointments = load_appointments()
        if room_name not in appointments:
            await appointment.finish(f"预约对局「{room_name}」不存在")
        
        del appointments[room_name]
        save_appointments(appointments)
        await appointment.finish(f" 预约对局「{room_name}」已解散")
    finally:
        session.close()


async def start_room(event: MessageEvent, room_name: str):
    if not room_name:
        await appointment.finish("请提供对局名称，例如：/预约 开局 欢乐局")
    
    qq = event.get_user_id()
    session = Session()
    try:
        user = session.query(User).filter(User.bd_qq == qq).first()
        if not user:
            await appointment.finish("您尚未绑定游戏账号")
        nickname = user.nickname

        appointments = load_appointments()
        if room_name not in appointments:
            await appointment.finish(f"预约对局「{room_name}」不存在")
        
        room = appointments[room_name]
        participants = room.get("participants", [])
        if len(participants) != 4:
            await appointment.finish(f"对局人数不足4人，当前 {len(participants)}/4，无法开局")
        
        for nick in participants:
            u = session.query(User).filter(User.nickname == nick, User.active == True).first()
            if not u:
                await appointment.finish(f"玩家「{nick}」不存在或未激活，无法开局")
        
        ongoing_progress = session.query(GameProgress).filter(
            GameProgress.status == "ongoing"
        ).all()
        
        ongoing_players = set()
        for progress in ongoing_progress:
            try:
                for p in progress.get_players():
                    ongoing_players.add(p["nickname"])
            except:
                pass
        
        for nick in participants:
            if nick in ongoing_players:
                await appointment.finish(f"玩家「{nick}」已在其他进行中的对局中，无法开局")
        
        # 随机分配东南西北
        seats = ["东", "南", "西", "北"]
        random.shuffle(seats)
        seat_players = []
        for i, nick in enumerate(participants):
            u = session.query(User).filter(User.nickname == nick).first()
            seat_players.append({
                "nickname": nick,
                "seat": seats[i],
                "avatar": u.avatar
            })
        
        # 创建 GameProgress 记录
        progress_id = str(uuid.uuid4())
        progress = GameProgress(
            id=progress_id,
            status="ongoing"
        )
        progress.set_players(seat_players)
        session.add(progress)
        session.commit()
        
        # 从预约列表中删除该对局
        del appointments[room_name]
        save_appointments(appointments)
        
        # 构建返回消息
        result = f"✅ 预约对局「{room_name}」已转为正式对局！\n座位分配：\n"
        seat_order = ["东", "南", "西", "北"]
        seat_map = {p["seat"]: p["nickname"] for p in seat_players}
        for seat in seat_order:
            result += f"  {seat}家：{seat_map.get(seat, '无')}\n"
        result += f"\n💡 使用 /录分 东家分数 南家分数 西家分数 北家分数 录入分数"
        await appointment.finish(result.strip())
    except Exception as e:
        session.rollback()
        return
    finally:
        session.close()

async def list_rooms(event: MessageEvent):
    """显示所有预约对局列表"""
    appointments = load_appointments()
    
    if not appointments:
        await appointment.finish("当前没有预约对局")
    
    result = " 预约对局列表\n"
    result += "━━━━━━━━━━━━━━\n"
    
    for i, (room_name, room_data) in enumerate(appointments.items(), 1):
        participants = room_data.get("participants", [])
        creator = room_data.get("creator", "未知")
        create_time = room_data.get("create_time", "")
        
        if create_time:
            try:
                dt = datetime.fromisoformat(create_time)
                time_str = dt.strftime("%m-%d %H:%M")
            except:
                time_str = "未知"
        else:
            time_str = "未知"
        
        result += f"\n{i}. {room_name}\n"
        result += f"   创建者：{creator}\n"
        result += f"   创建时间：{time_str}\n"
        result += f"   参与者：{len(participants)}/4人\n"
        if participants:
            result += f"   玩家：{'、'.join(participants)}\n\n"
    
    result += "\n━━━━━━━━━━━━━━\n"
    result += "💡 使用 /预约 join [对局名] 加入对局"
    
    await appointment.finish(result.strip())
