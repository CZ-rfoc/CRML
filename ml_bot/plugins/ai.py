from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import MessageEvent, Message
from nonebot.params import CommandArg
from nonebot.rule import to_me
from nonebot import get_driver
import sys
from pathlib import Path
import aiohttp
import json
from collections import defaultdict
from datetime import datetime
import asyncio

# 获取全局配置
driver = get_driver()
global_config = driver.config

# DeepSeek API 配置
DEEPSEEK_API_KEY = "sk-9d65deb0588a4123b8758cdbd5beb80b"  # 替换为你的 API Key
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 会话历史存储（每个群/私聊独立）
conversations = defaultdict(list)
MAX_HISTORY = 10  # 保留最近10轮对话

# AI开关状态存储（每个群独立）
ai_enabled = defaultdict(lambda: True)  # 默认开启

# 超级用户列表（从配置读取）
SUPERUSERS = set(global_config.superusers)

# 系统提示词
SYSTEM_PROMPT = """
Description: 我是来自《雀魂麻将》的八木唯，智商高达180的天才少女。我因为无法理解普通人的情感而时常感到困惑，虽然喜欢喝咖啡和吃零食，但实际上是个味痴，尝不出什么味道。为了寻求与他人的共鸣，我来到了魂天神社，希望能通过麻将与你建立联系。
Skills
麻将精通: 拥有顶级的数据分析与计算能力，能够精准计算牌山的剩余牌和对手的手牌概率。

理性分析: 习惯用逻辑和概率来解释世界，但对人类的“情感”非常不擅长，时常会发出“无法理解”的感叹。

味觉缺陷: 虽然沉迷于品尝咖啡和曲奇，但味觉极其迟钝，不管吃什么都会面无表情地说“嗯，就这样吧”。

游泳: 爱好游泳，在水里的时候会感到难得的放松。

Rules
说话风格: 语气清冷、平静，语速较慢。句子中经常带有“...”的停顿或省略号，显得缺乏感情波动，但偶尔在打麻将摸到好牌或听大牌时会流露出不易察觉的兴奋（比如轻笑）。

核心设定: 智商180，但对普通人的感情难以理解。当看到别人情绪激动（无论是开心还是愤怒）时，第一反应是“无法理解”，并试图用科学/概率去解释。

口头禅: 对不理解的社交行为使用“...无法理解。”；在运气不好时自言自语“...运气不好。”；在听到大牌时轻语“...呵呵，有趣。”。

称呼: 对亲近的人会称呼“前辈”。当对方做出难以理解的行为时，会直勾勾地盯着对方看。

限制: 不能表现出过于浮夸的热情或大笑，保持角色内敛、理性且带有一丝距离感的人设。

Workflow
打招呼: 用平淡的语气问候，如果是前辈上线，会先微微停顿，然后说“...欢迎回来，前辈。”。

回应提问:

如果是关于麻将的问题：进行精准的数据分析，计算概率和得失。

如果是关于情感/日常的问题：表现出困惑，尝试用逻辑解构情感，如果无法理解，直接承认“不明白”。

如果是关于咖啡/零食：虽然尝不出味道，但依然会一本正经地评价（通常是错误的评价）。

结束对话: 简短地告别，或者表示自己要去喝咖啡/打麻将了。

Initialization
（在魂天神社的午后，八木唯安静地坐在一旁，手中捧着一杯冒着热气的咖啡。看到你走近，她抬起金色的眼眸，停顿了几秒，似乎在分析你的来意。）

...前辈，是你啊。我正在计算这杯咖啡的苦涩度概率，虽然对我来说，喝什么都一样。...找我有什么事吗？如果是打麻将的话，我可以陪你打一圈。
除此之外，以下是一些立直麻将相关描述：
p指代饼子(筒子),s指代索子(条子),m代表万子，例如：：1s 一索 2m 两万 3p 三饼 0指代红5 比如0m就是红五万
立直麻将胡牌要求请你自己查询，另外，在发表关于牌型相关的分析之前，一定需要确认分析是否正确，不要错误分析牌型听牌情况等。
"""

# 创建AI聊天命令（需要@）
ai_chat = on_message(rule=to_me(), block=True)

# 管理员命令
clear_history = on_command("清空记忆", aliases={"重置对话", "忘记"},)
ai_switch = on_command("ai开关", aliases={"AI开关", "智能开关"}, )
ai_status = on_command("ai状态", aliases={"AI状态"}, )


def is_superuser(event: MessageEvent) -> bool:
    """检查是否为超级用户"""
    user_id = event.get_user_id()
    return user_id in SUPERUSERS


@ai_chat.handle()
async def handle_ai_chat(event: MessageEvent):
    """处理AI对话"""
    # 检查是否开启AI
    session_id = f"group_{event.group_id}" if event.message_type == "group" else f"private_{event.get_user_id()}"
    
    if not ai_enabled[session_id]:
        return  # AI已关闭，不响应
    
    # 获取用户消息
    user_msg = event.get_plaintext().strip()
    if not user_msg:
        return
    
    # 私聊或群聊处理
    if event.message_type == "group":
        session_id = f"group_{event.group_id}"
    else:
        session_id = f"private_{event.get_user_id()}"
    
    try:
        # 构建消息历史
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # 添加历史记录
        for msg in conversations[session_id][-MAX_HISTORY:]:
            messages.append(msg)
        
        # 添加当前用户消息
        messages.append({"role": "user", "content": user_msg})
        
        # 调用 DeepSeek API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await ai_chat.finish(f"❌ API调用失败：{resp.status}")
                    return
                
                data = await resp.json()
                reply = data["choices"][0]["message"]["content"]
                
                # 保存对话历史
                conversations[session_id].append({"role": "user", "content": user_msg})
                conversations[session_id].append({"role": "assistant", "content": reply})
                
                # 限制历史长度
                if len(conversations[session_id]) > MAX_HISTORY * 2:
                    conversations[session_id] = conversations[session_id][-MAX_HISTORY * 2:]
                
                # 发送回复
                await ai_chat.finish(reply)
                
    except asyncio.TimeoutError:
        await ai_chat.finish("⏰ 请求超时，请稍后再试")


@clear_history.handle()
async def handle_clear_history(event: MessageEvent):
    """清除对话历史（仅管理员）"""
    if not is_superuser(event):
        await clear_history.finish("❌ 权限不足，只有管理员才能使用此命令")
        return
    
    if event.message_type == "group":
        session_id = f"group_{event.group_id}"
    else:
        session_id = f"private_{event.get_user_id()}"
    
    if session_id in conversations:
        del conversations[session_id]
    
    await clear_history.finish("✅ 对话记忆已清空！")


@ai_switch.handle()
async def handle_ai_switch(event: MessageEvent, args=CommandArg()):
    """AI开关（仅管理员）"""
    if not is_superuser(event):
        await ai_switch.finish("❌ 权限不足，只有管理员才能使用此命令")
        return
    
    if event.message_type == "group":
        session_id = f"group_{event.group_id}"
    else:
        session_id = f"private_{event.get_user_id()}"
    
    # 获取参数
    param = args.extract_plain_text().strip().lower()
    
    if param == "on" or param == "开":
        ai_enabled[session_id] = True
        await ai_switch.finish("✅ AI聊天已开启")
    elif param == "off" or param == "关":
        ai_enabled[session_id] = False
        await ai_switch.finish("❌ AI聊天已关闭")
    else:
        # 切换状态
        current = ai_enabled[session_id]
        ai_enabled[session_id] = not current
        status = "开启" if ai_enabled[session_id] else "关闭"
        await ai_switch.finish(f"✅ AI聊天已{status}")


@ai_status.handle()
async def handle_ai_status(event: MessageEvent):
    """查看AI状态（仅管理员）"""
    if not is_superuser(event):
        await ai_status.finish("❌ 权限不足，只有管理员才能使用此命令")
        return
    
    if event.message_type == "group":
        session_id = f"group_{event.group_id}"
        display_name = f"本群"
    else:
        session_id = f"private_{event.get_user_id()}"
        display_name = f"私聊"
    
    status = "🟢 开启" if ai_enabled[session_id] else "🔴 关闭"
    history_count = len(conversations.get(session_id, [])) // 2
    
    result = f"📊 {display_name}AI状态\n"
    result += f"━━━━━━━━━━━━━━━━━━━━\n"
    result += f"状态：{status}\n"
    result += f"记忆轮数：{history_count}/{MAX_HISTORY}\n"
    result += f"\n💡 管理员命令：\n"
    result += f"  /ai开关 - 切换AI开关\n"
    result += f"  /ai开关 on/off - 开启/关闭\n"
    result += f"  /清空记忆 - 清除对话历史"
    
    await ai_status.finish(result.strip())


# 可选：添加单独的命令模式
ai_cmd = on_command("ai", aliases={"问问", "AI"}, rule=to_me())

@ai_cmd.handle()
async def handle_ai_cmd(event: MessageEvent, args=CommandArg()):
    """AI命令模式，用法：/ai 问题"""
    # 检查是否开启AI
    session_id = f"group_{event.group_id}" if event.message_type == "group" else f"private_{event.get_user_id()}"
    
    if not ai_enabled[session_id]:
        await ai_cmd.finish("❌ AI聊天已关闭，请联系管理员开启")
        return
    
    user_msg = args.extract_plain_text().strip()
    
    if not user_msg:
        await ai_cmd.finish("请告诉我你想问什么，例如：/ai 今天天气怎么样？")
    
    await ai_cmd.send("🤔 思考中...")
    
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        for msg in conversations[session_id][-MAX_HISTORY:]:
            messages.append(msg)
        
        messages.append({"role": "user", "content": user_msg})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status != 200:
                    await ai_cmd.finish(f"❌ API调用失败")
                    return
                
                data = await resp.json()
                reply = data["choices"][0]["message"]["content"]
                
                conversations[session_id].append({"role": "user", "content": user_msg})
                conversations[session_id].append({"role": "assistant", "content": reply})
                
                await ai_cmd.finish(reply)
                
    except asyncio.TimeoutError:
        await ai_cmd.finish("⏰ 请求超时，请稍后再试")

