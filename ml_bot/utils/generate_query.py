from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path
import math
from datetime import datetime

def generate_player_card(name, icon_path, dan, pt, avg_score, max_score, 
                         total_games, avg_rank, avg_pt, rank_count, last_10_rank):
    """
    生成玩家数据卡片图片
    
    参数：
        name: 玩家昵称
        icon_path: 头像路径
        dan: 段位名称
        pt: 段内PT
        avg_score: 平均得分
        max_score: 最高得分
        total_games: 总对局数
        avg_rank: 平均名次
        avg_pt: 平均PT
        rank_count: 名次分布字典 {1: n, 2: n, 3: n, 4: n}
        last_10_rank: 最近10场名次列表 [1,2,3,1,2,3,4...]
    
    返回：
        PIL Image 对象
    """
    
    # ========== 颜色配置（素色系）==========
    colors = {
        'bg': (250, 250, 245),        # 米白背景
        'card': (255, 255, 255),      # 纯白卡片
        'title': (100, 100, 100),     # 灰色标题
        'text': (80, 80, 80),         # 深灰文字
        'accent': (139, 69, 19),      # 棕色强调
        'border': (220, 220, 220),    # 浅灰边框
        'rank_1': (255, 215, 0),      # 金色（1位）
        'rank_2': (192, 192, 192),    # 银色（2位）
        'rank_3': (205, 127, 50),     # 铜色（3位）
        'rank_4': (139, 69, 19),      # 棕色（4位）
        'pie_colors': [(255, 215, 0), (192, 192, 192), (205, 127, 50), (139, 69, 19)],
        'grid': (200, 220, 240),      # 更淡的蓝色格子线（接近浅蓝灰）
    }
    # 字体文件位置，注意非windows时需要修改
    def get_font(size):
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "/System/Library/Fonts/PingFang.ttc",
        ]
        for path in font_paths:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except:
                    continue
        return ImageFont.load_default()
    
    font_title = get_font(37)
    font_large = get_font(32)
    font_medium = get_font(24)
    font_small = get_font(19)
    
    # ========== 创建画布 ==========
    width, height = 800, 900
    img = Image.new('RGB', (width, height), colors['bg'])
    draw = ImageDraw.Draw(img)
    
    # 绘制圆角矩形卡片
    def draw_rounded_rect(x1, y1, x2, y2, fill, radius=20, outline=None):
        draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
        draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
        draw.pieslice([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=fill)
        draw.pieslice([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=fill)
        draw.pieslice([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=fill)
        draw.pieslice([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=fill)
        
        if outline:
            draw.rectangle([x1, y1, x2, y2], outline=outline, width=1)
    
    # 主卡片
    draw_rounded_rect(40, 40, width - 40, height - 40, colors['card'], outline=colors['border'])
    
    # ========== 在卡片内部添加格子线 ==========
    card_x1, card_y1 = 40, 40
    card_x2, card_y2 = width - 40, height - 40
    
    # 格子大小，可修改
    grid_size = 45
    
    # 在卡片内部绘制淡蓝色格子线
    for x in range(card_x1 + grid_size, card_x2, grid_size):
        draw.line([(x, card_y1), (x, card_y2)], fill=colors['grid'], width=1)
    
    for y in range(card_y1 + grid_size, card_y2, grid_size):
        draw.line([(card_x1, y), (card_x2, y)], fill=colors['grid'], width=1)
    
    # ========== 1. 头部 ==========
    y = 60
    draw.text((60, y), " 个人数据总览", font=font_title, fill=colors['title'])
    
    # 昵称和段位
    name_bbox = draw.textbbox((0, 0), name, font=font_title)
    name_width = name_bbox[2] - name_bbox[0]
    name_x = width - 200 - name_width  # 从120改为200，向左移动
    name_y = y + 50
    draw.text((name_x, name_y), name, font=font_title, fill=colors['accent'])
    draw.text((name_x, name_y + 45), f"{dan} ({pt:.1f})",  # 增加间距，适应更大字体
              font=font_small, fill=colors['text'])
    
    # ========== 2. 头像（放在右边名字下方，也向左移动）==========
    avatar = None
    if icon_path and os.path.exists(icon_path):
        try:
            avatar = Image.open(icon_path).convert('RGBA')
            avatar = avatar.resize((200, 200))  # 头像放大到200x200（原150，放大1/3）
        except:
            pass
    
    if avatar:
        # 头像位置与名字左对齐，也向左移动
        avatar_x = name_x
        avatar_y = name_y + 90
        mask = Image.new('L', (200, 200), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, 200, 200), fill=255)
        img.paste(avatar, (avatar_x, avatar_y), mask)
    
    # ========== 3. 数据区域（位置保持不变）==========
    y = 120
    data_x = 200
    stats = [
        ("总对局", f"{total_games} 局"),
        ("平均得分", f"{avg_score:.0f}"),
        ("最高得分", f"{max_score:.0f}"),
        ("平均名次", f"{avg_rank:.1f}"),
        ("平均PT", f"{avg_pt:.1f}"),
    ]
    for i, (label, value) in enumerate(stats):
        draw.text((data_x - 20, y + i * 35), f"{label}：", font=font_medium, fill=colors['text']) 
        draw.text((data_x + 100, y + i * 35), value, font=font_medium, fill=colors['accent'])
    
    y += 150
    
    # ========== 4. 名次分布（饼状图）==========
    draw.text((40, y), "   名次分布", font=font_medium, fill=colors['title'])
    y += 40
    
    # 饼状图参数
    pie_x = 60
    pie_y = y
    pie_size = 180
    
    total = total_games
    counts = [rank_count.get(i, 0) for i in range(1, 5)]
    
    # 绘制饼状图
    start_angle = -90
    for i, count in enumerate(counts):
        if count > 0:
            angle = 360 * (count / total)
            end_angle = start_angle + angle
            draw.pieslice([pie_x, pie_y, pie_x + pie_size, pie_y + pie_size], 
                         start_angle, end_angle, fill=colors['pie_colors'][i])
            start_angle = end_angle
    
    # 绘制中心圆
    center_x = pie_x + pie_size // 2
    center_y = pie_y + pie_size // 2
    inner_radius = 55
    draw.ellipse([center_x - inner_radius, center_y - inner_radius,
                  center_x + inner_radius, center_y + inner_radius], 
                 fill=colors['card'])
    
    # 中心文字
    draw.text((center_x - 15, center_y - 30), f"{total}", font=font_large, fill=colors['accent'])
    draw.text((center_x - 28, center_y), "总对局", font=font_small, fill=colors['text'])
    
    # 图例
    legend_x = pie_x + pie_size + 30
    legend_y = pie_y
    legend_items = [
        (f"1位 {counts[0]}局 ({counts[0]/total*100:.1f}%)", colors['pie_colors'][0]),
        (f"2位 {counts[1]}局 ({counts[1]/total*100:.1f}%)", colors['pie_colors'][1]),
        (f"3位 {counts[2]}局 ({counts[2]/total*100:.1f}%)", colors['pie_colors'][2]),
        (f"4位 {counts[3]}局 ({counts[3]/total*100:.1f}%)", colors['pie_colors'][3]),
    ]
    
    for i, (text, color) in enumerate(legend_items):
        draw.rectangle([legend_x, legend_y + i * 30, legend_x + 25, legend_y + i * 30 + 20], 
                      fill=color)
        draw.text((legend_x + 35, legend_y + i * 30), text, font=font_small, fill=colors['text'])
    
    y += pie_size + 30
    
    # ========== 5. 最近名次走势 ==========
    y = y + 40
    
    draw.text((60, y), "   最近名次走势", font=font_medium, fill=colors['title'])
    y += 40
    
    if last_10_rank:
        chart_x = 100
        chart_y = y
        chart_w = 620
        chart_h = 160
        
        # 绘制背景网格
        for i in range(5):
            grid_y = chart_y + i * (chart_h / 4)
            draw.line([chart_x - 10, grid_y, chart_x + chart_w, grid_y], 
                     fill=colors['border'], width=1)
        
        # 绘制Y轴标签
        for i, rank in enumerate([1, 2, 3, 4]):
            y_pos = chart_y + (i / 3) * chart_h
            draw.text((chart_x - 40, y_pos - 10), f"{rank}位", font=font_small, fill=colors['text'])
        
        # 绘制点线和连线
        points = []
        for i, r in enumerate(last_10_rank[:10]):
            x = chart_x + (i / (len(last_10_rank[:10]) - 1 if len(last_10_rank[:10]) > 1 else 1)) * chart_w
            y_pos = chart_y + ((r - 1) / 3) * chart_h
            points.append((x, y_pos))
            radius = 7  # 从6增加到7
            draw.ellipse([x - radius, y_pos - radius, x + radius, y_pos + radius], 
                        fill=colors['accent'])
        
        # 绘制连线
        if len(points) > 1:
            for i in range(len(points) - 1):
                draw.line([points[i], points[i+1]], fill=colors['accent'], width=2)
        
        # X轴标签
        for i in range(min(10, len(last_10_rank))):
            x = chart_x + (i / (min(10, len(last_10_rank)) - 1 if min(10, len(last_10_rank)) > 1 else 1)) * chart_w
            draw.text((x - 8, chart_y + chart_h + 8), str(i+1), font=font_small, fill=colors['text'])
    
    # 保存图片
    save_dir = Path(__file__).parent.parent
    cache_dir = save_dir / "_cache_"
    cache_dir.mkdir(exist_ok=True)
    save_path = cache_dir / f"{name}.png"
    img.save(save_path)
    return save_path


# ========== 使用示例 ==========
if __name__ == "__main__":
    rank_count = {1: 10, 2: 8, 3: 5, 4: 3}
    last_10 = [1, 2, 1, 3, 2, 4, 1, 2, 3, 1]
    
    save_path = generate_player_card(
        name="张三",
        icon_path="default_icon.png",
        dan="五段",
        pt=150.5,
        avg_score=24500,
        max_score=32000,
        total_games=26,
        avg_rank=2.1,
        avg_pt=12.5,
        rank_count=rank_count,
        last_10_rank=last_10
    )
    print(f"图片已保存到：{save_path}")
