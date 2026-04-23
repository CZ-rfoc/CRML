import os
import requests
import uuid
import json
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from PIL import Image
from datetime import datetime, date, timedelta
import pytz
import hashlib
import random
from captcha.image import ImageCaptcha
import string
import io

# 导入自定义模块
from config import (
    config, db, User, GameRecord, GameProgress,
    DAN_ORDER, DAN_INFO, BEIJING_TZ, DAN_WEIGHT,
    ADMIN_PASS, INVITE_CODE_SCHOOL
)

# -------------------------- 初始化Flask应用 --------------------------
app = Flask(__name__)
# 加载配置
app.config.from_object(config)
# 初始化数据库
db.init_app(app)
# 创建上传目录（若不存在）
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

@app.template_filter('enumerate')
def jinja2_enumerate(iterable, start=0):
    """让Jinja2支持enumerate过滤器，用法：列表|enumerate(起始值)"""
    return enumerate(iterable, start=start)

# 启动时自动创建数据库表（若不存在）
with app.app_context():
    db.create_all()

# -------------------------- 工具函数（核心业务） --------------------------
# 1. 检查文件后缀是否允许（头像上传）
def generate_captcha():
    # 验证码字符池：数字+大小写字母
    captcha_chars = string.digits + string.ascii_letters
    captcha_code = ''.join(random.choice(captcha_chars) for _ in range(4))
    # 生成验证码图片
    image = ImageCaptcha(width=120, height=40)  # 图片尺寸可按需调整
    image_io = io.BytesIO()
    image.write(captcha_code, image_io, format='PNG')
    image_io.seek(0)
    return captcha_code, image_io

# 验证码图片接口（供前端调用）
@app.route('/captcha')
def captcha():
    captcha_code, image_io = generate_captcha()
    # 验证码存入session，用于后续校验
    session['captcha_code'] = captcha_code.lower()  # 统一转小写，忽略大小写校验
    return image_io.getvalue(), 200, {'Content-Type': 'image/png'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def validate_nickname(nickname):
    if not nickname:
        return False
    if len(nickname) > 10:
        return False
    if nickname.isdigit() and len(nickname) == 8:
        return False
    danger_chars = ["'", '"', ";" , "OR", "AND", "\\"]
    if any(c in nickname.upper() for c in danger_chars):
        return False
    return True

def validate_qq(qq_num):
    """验证QQ号格式：非空、纯数字、5-13位"""
    if not qq_num:
        return False
    if not qq_num.isdigit():
        return False
    if len(qq_num) < 5 or len(qq_num) > 13:
        return False
    return True

def get_qq_avatar(qq_num, user_id):
    """
    下载QQ头像并按规则处理（重命名+裁剪200*200）
    :param qq_num: QQ号
    :param user_id: 用户ID（用于重命名）
    :return: 处理后的头像文件名
    """
    try:
        # QQ头像公开接口（s=100表示100x100尺寸）
        qq_avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={qq_num}&s=100"
        response = requests.get(qq_avatar_url, timeout=5)
        response.raise_for_status()  # 抛出HTTP错误

        # 读取图片流
        img = Image.open(BytesIO(response.content))
        # 裁剪为正方形+缩放到200*200（与原有头像逻辑一致）
        img = img.crop((0, 0, min(img.size), min(img.size)))
        img.thumbnail((200, 200))

        # 重命名为{user_id}.jpg（基于用户ID而非昵称）
        filename = f"{user_id}.jpg"
        filepath = os.path.join(config.UPLOAD_FOLDER, filename)
        img.save(filepath)
        return filename
    except Exception as e:
        print(f"获取QQ头像失败：{e}")
        return "default_icon.png"  # 失败则返回默认头像

# 2. 处理头像上传（改用user_id命名）
def handle_avatar_upload(user_id, file):
    if file and allowed_file(file.filename):
        # 获取后缀
        ext = file.filename.rsplit('.', 1)[1].lower()
        # 重命名为{user_id}.后缀（基于用户ID）
        filename = f"{user_id}.{ext}"
        # 安全路径
        filepath = os.path.join(config.UPLOAD_FOLDER, filename)
        # 保存并裁剪为200*200正方形
        img = Image.open(file.stream)
        img = img.crop((0, 0, min(img.size), min(img.size)))  # 裁剪正方形
        img.thumbnail((200, 200))  # 缩放到200*200
        img.save(filepath)
        return filename
    # 不符合条件返回默认头像
    return "default_icon.png"

# 3. 计算名次（无修改，仅处理分数列表）
def calculate_ranks(scores):
    # 生成（分数，索引）的列表，按分数降序排序
    sorted_with_idx = sorted(enumerate(scores), key=lambda x: -x[1])
    # 初始化名次列表
    ranks = [0] * 4
    # 提取排序后的分数
    sorted_scores = [s for _, s in sorted_with_idx]

    # 处理并列逻辑：相同分数赋予相同名次，不同分数按当前排序位置+1定名次
    for i, (idx, score) in enumerate(sorted_with_idx):
        if i == 0:
            ranks[idx] = 1
        elif score == sorted_scores[i - 1]:
            # 与上一名分数相同，名次一致
            ranks[idx] = ranks[sorted_with_idx[i - 1][0]]
        else:
            # 分数不同，名次为当前排序位置+1
            ranks[idx] = i + 1
    return ranks

# 4. 计算单玩家PT（素点/1000 + 名次补正，无昵称依赖）
def calculate_pt(score, rank, all_ranks):
    # 提取四位名次，判断并列类型
    rank_count = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in all_ranks:
        rank_count[r] += 1
    # 重新统计实际名次分布
    bonus = 0.0
    if rank_count[1] == 2:  # 并列第一（1,1,3,4）
        bonus = 25.0 if rank == 1 else (-15.0 if rank == 3 else -35.0)
    elif rank_count[2] == 2:  # 并列第二（1,2,2,4）
        bonus = 45.0 if rank == 1 else (-5.0 if rank == 2 else -35.0)
    elif rank_count[3] == 2:  # 并列第三（1,2,3,3）
        bonus = 45.0 if rank == 1 else (5.0 if rank == 2 else -25.0)
    else:  # 无并列
        bonus = 45.0 if rank == 1 else (5.0 if rank == 2 else (-15.0 if rank == 3 else -35.0))
    # 计算PT（一位小数）
    pt = round(score / 1000 + bonus - 25.0, 1)
    return pt

# 5. 更新用户段位+段内PT（入参为user对象，无昵称依赖）
def update_user_dan(user, game_pt):
    # 段内PT累加本局PT
    user.dan_pt = round(user.dan_pt + game_pt, 1)
    # 升段逻辑
    if user.dan_pt >= user.promote_cond and user.get_dan_index() < 9:  # 未到九段
        new_dan_idx = user.get_dan_index() + 1
        new_dan = DAN_ORDER[new_dan_idx]
        user.dan = new_dan
        user.promote_cond = DAN_INFO[new_dan][0]
        user.dan_pt = DAN_INFO[new_dan][1]
        flash(f"恭喜{user.nickname}升段至{new_dan}！", "success")
    # 降段逻辑（初段/一段/二段掉段保护）
    elif user.dan_pt < 0:
        if user.dan in ["初段", "一段", "二段"]:
            user.dan_pt = 0.0
            flash(f"{user.nickname}触发掉段保护", "warning")
        else:  # 三段及以上降段
            new_dan_idx = user.get_dan_index() - 1
            new_dan = DAN_ORDER[new_dan_idx]
            user.dan = new_dan
            user.promote_cond = DAN_INFO[new_dan][0]
            user.dan_pt = DAN_INFO[new_dan][1]
            flash(f"{user.nickname}降段至{new_dan}", "danger")

# 6. 统计用户对局数据（参数改为user_id）
def get_user_stats(user_id):
    # 获取该用户所有对局记录
    records = GameRecord.query.all()
    user_records = []
    for r in records:
        for p in r.get_players():
            if p["user_id"] == user_id:
                user_records.append(p)
    # 基础统计
    total_games = len(user_records)
    avg_score = round(sum(p["score"] for p in user_records) / total_games, 0) if total_games > 0 else 0
    avg_rank = round(sum(p["rank"] for p in user_records) / total_games, 1) if total_games > 0 else 0
    avg_pt = round(sum(p["pt"] for p in user_records) / total_games, 1) if total_games > 0 else 0
    # 名次概率（饼图）
    rank_count = {1: 0, 2: 0, 3: 0, 4: 0}
    for p in user_records:
        rank_count[p["rank"]] += 1
    rank_rate = [rank_count[1], rank_count[2], rank_count[3], rank_count[4]]
    # 最近10战名次（折线图，倒序取最新10条）
    last_10_ranks = [p["rank"] for p in user_records[-10:]] if total_games > 0 else []
    # 返回统计结果
    return {
        "total_games": total_games,
        "avg_score": avg_score,
        "avg_rank": avg_rank,
        "avg_pt": avg_pt,
        "rank_rate": rank_rate,
        "last_10_ranks": last_10_ranks
    }

# 7. 统计本月PT排名（月报）（基于user_id累加）
# 原函数不动，只修改 【数据组装】 这一小段
def get_monthly_pt_ranking(school=None):
    now = datetime.now(BEIJING_TZ)
    month_start = datetime(now.year, now.month, 1, tzinfo=BEIJING_TZ)
    month_end = datetime(now.year, now.month + 1, 1, tzinfo=BEIJING_TZ) if now.month < 12 else datetime(now.year + 1, 1,
                                                                                                        1,
                                                                                                        tzinfo=BEIJING_TZ)
    records = GameRecord.query.filter(GameRecord.game_time >= month_start, GameRecord.game_time < month_end).all()
    pt_total = {}
    for r in records:
        for p in r.get_players():
            user_id = p["user_id"]
            pt = p["pt"]
            pt_total[user_id] = pt_total.get(user_id, 0) + round(pt, 1)

    sorted_ranking = sorted(pt_total.items(), key=lambda x: -x[1])
    ranking = []
    for user_id, pt in sorted_ranking:
        user = User.query.get(user_id)
        if user:
            if school and user.school != school:
                continue

            user_stats = get_user_stats(user_id)

            ranking.append({
                "user_id": user_id,
                "nickname": user.nickname,
                "pt_total": pt,
                "avatar": user.avatar,
                "stats": user_stats,
                "school": user.school
                # 统计数据注入，前端正常使用
            })
    return ranking

# 8. 获取段位排名数据（九段→初段，同段位按段内PT降序）（无修改，基于User模型的user_id）
def get_dan_rank_list(school=None):
    # 查询所有用户 + 按学校筛选
    query = User.query
    if school is not None:
        query = query.filter(User.school == school)
    all_users = query.all()
    # 排序规则：先按段位权重降序，再按段内PT降序
    sorted_users = sorted(
        all_users,
        key=lambda u: (DAN_WEIGHT[u.dan], u.dan_pt),
        reverse=True
    )
    # 补充用户统计信息
    rank_list = []
    for user in sorted_users:
        rank_list.append({
            "user": user,
            "stats": get_user_stats(user.user_id)
        })
    return rank_list

# 获取被锁定的玩家ID/昵称（正在进行中的对局）
def get_locked_players():
    ongoing_progress = GameProgress.query.filter(GameProgress.status == "ongoing").all()
    locked_user_ids = []
    for progress in ongoing_progress:
        for player in progress.get_players():
            locked_user_ids.append(player["user_id"])
    # 转换为昵称返回（前端展示用）
    locked_nicks = [User.query.get(uid).nickname for uid in locked_user_ids if User.query.get(uid)]
    return list(set(locked_nicks))

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 如果没有管理端登录标记，强制跳转到验证页面
        if not session.get("is_manage"):
            flash("请先验证管理端口令！", "danger")
            return redirect(url_for("manage_verify"))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------- 路由 --------------------------
# 根页面：登录验证（替换原口令验证为密码验证）
@app.route("/", methods=["GET", "POST"])
def index_verify():
    # 已登录直接跳转（保留原有逻辑）
    if session.get("verified") and session.get("user_id"):
        return redirect(url_for("main_index"))

    if request.method == "POST":
        # ========== 1. 获取数据（新增验证码输入项） ==========
        account = request.form.get("account", "").strip()
        password_md5 = request.form.get("password_md5", "").strip()
        input_captcha = request.form.get("captcha", "").strip().lower()  # 统一转小写

        # ========== 2. 验证码校验（仅登录出错后触发） ==========
        need_captcha = session.get("need_captcha", False)
        if need_captcha:
            # 校验验证码：空值/不一致均报错
            session_captcha = session.get("captcha_code", "")
            if not input_captcha or input_captcha != session_captcha:
                flash("验证码错误", "danger")
                session["need_captcha"] = True  # 保持需要验证码的状态
                return render_template("index_verify.html", need_captcha=need_captcha)

        # ========== 3. 基础校验（保留原有逻辑，新增need_captcha标记） ==========
        if not account or not password_md5:
            flash("账号/密码不能为空", "danger")
            session["need_captcha"] = True  # 出错后标记需要验证码
            return render_template("index_verify.html", need_captcha=True)

        # 防SQL注入（保留原有逻辑，新增need_captcha标记）
        danger_chars = ["'", '"', ";", "OR", "AND", "\\"]
        if any(c in account.upper() for c in danger_chars):
            flash("输入包含非法字符", "danger")
            session["need_captcha"] = True  # 出错后标记需要验证码
            return render_template("index_verify.html", need_captcha=True)

        # ========== 4. 多条件查询用户（核心逻辑完全保留） ==========
        user = None
        # 情况1：8位数字 → 查询 user_id（主键）
        if account.isdigit() and len(account) == 8:
            user = User.query.get(int(account))
        # 情况2：查询昵称（兼容，最终存储user_id）
        else:
            user = User.query.filter_by(nickname=account).first()
            # 情况3：昵称不存在 → 查询QQ号（排除空QQ）
            if not user and account.isdigit():
                user = User.query.filter(User.bd_qq == account, User.bd_qq != "").first()

        # ========== 5. 密码验证（保留原有逻辑，新增need_captcha标记） ==========
        if not user:
            flash("账号不存在", "danger")
            session["need_captcha"] = True  # 出错后标记需要验证码
            return render_template("index_verify.html", need_captcha=True)
        if user.password != password_md5:
            flash("密码错误", "danger")
            session["need_captcha"] = True  # 出错后标记需要验证码
            return render_template("index_verify.html", need_captcha=True)

        # ========== 6. 登录成功（重置验证码标记，保留原有逻辑） ==========
        session["need_captcha"] = False  # 登录成功后重置验证码要求
        session["verified"] = True
        session["user_id"] = user.user_id  # 核心存储user_id
        session["nickname"] = user.nickname  # 仅展示用
        session.permanent = True

        flash(f"欢迎回来，{user.nickname}", "success")
        return redirect(url_for("main_index"))

    # GET请求：渲染页面，传递是否需要验证码的标记
    return render_template("index_verify.html", need_captcha=session.get("need_captcha", False))


# 首页：
# 首页：
@app.route("/index", methods=["GET", "POST"])
def main_index():
    # 检查登录状态（基于user_id）
    user_id = session.get("user_id")
    if not user_id:
        flash("请先登录！", "danger")
        return redirect(url_for("index_verify"))
    user = User.query.get(user_id)
    if not user:
        flash("用户不存在！", "danger")
        return redirect(url_for("index_verify"))

    # 处理头像重新上传（基于user_id）
    if request.method == "POST" and request.files.get("avatar"):
        avatar_file = request.files.get("avatar")
        if avatar_file and avatar_file.filename != "":
            user.avatar = handle_avatar_upload(user_id, avatar_file)  # 传入user_id
            db.session.commit()
            flash("头像上传成功！", "success")
        return redirect(url_for("main_index"))

    # 切换活动状态
    if request.method == "POST" and not request.files.get("avatar"):
        user.active = not user.active
        db.session.commit()
        flash(f"活动状态已切换为：{'开启' if user.active else '关闭'}", "success")
        return redirect(url_for("main_index"))

    # 获取用户统计数据（传入user_id）
    stats = get_user_stats(user_id)

    # 查询该用户参与的所有对局记录详情（基于user_id）
    game_records = []
    # 获取所有对局记录并按时间倒序排列
    all_game_records = GameRecord.query.order_by(GameRecord.game_time.desc()).all()
    for record in all_game_records:
        # 提取该对局的所有玩家信息
        players = record.get_players()
        # 检查当前用户是否在该对局中（基于user_id）
        user_in_game = any(p["user_id"] == user_id for p in players)
        if user_in_game:
            # 格式化对局时间为北京时间字符串
            game_time = record.game_time.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
            # 整理玩家信息：用户ID、昵称、分数、PT
            game_players = [
                {
                    "user_id": p["user_id"],
                    "nickname": p["nickname"],
                    "score": p["score"],
                    "pt": p["pt"]
                }
                for p in players
            ]
            game_records.append({
                "game_time": game_time,
                "players": game_players
            })

    return render_template("index.html", user=user, stats=stats, game_records=game_records, school=user.school)

@app.route("/reg", methods=["GET", "POST"])
def reg():
    if session.get("verified") and session.get("user_id"):
        return redirect(url_for("main_index"))

    if request.method == "POST":
        # 1. 获取表单数据
        nickname = request.form.get("nickname", "").strip()
        invite_code = request.form.get("invite_code", "").strip()
        password_md5 = request.form.get("password_md5", "").strip()
        bd_qq = request.form.get("bd_qq", "").strip()
        qq_avatar_url = request.form.get("qq_avatar_url", "").strip()
        avatar_file = request.files.get("avatar")

        # 调试打印
        print(f"【后端接收】password_md5: [{password_md5}]")
        print(f"【后端接收】QQ号: [{bd_qq}]")

        # 2. 用户名校验
        if not nickname:
            flash("用户名不能为空", "danger")
            return render_template("reg.html")
        if len(nickname) > 10:
            flash("用户名最长10个字符", "danger")
            return render_template("reg.html")
        if nickname.isdigit() and len(nickname) == 8:
            flash("禁止使用8位纯数字用户名", "danger")
            return render_template("reg.html")
        danger_chars = ["'", '"', ";" , "OR", "AND", "\\"]
        if any(c in nickname.upper() for c in danger_chars):
            flash("用户名包含非法字符", "danger")
            return render_template("reg.html")
        if User.query.filter_by(nickname=nickname).first():
            flash("用户名已存在", "danger")
            return render_template("reg.html")

        # 3. QQ号唯一校验
        if bd_qq:
            if User.query.filter_by(bd_qq=bd_qq).first():
                flash("该QQ号已被绑定，请更换！", "danger")
                return render_template("reg.html")

        # 4. 邀请码校验
        if invite_code not in INVITE_CODE_SCHOOL:
            flash("邀请码无效", "danger")
            return render_template("reg.html")
        school = INVITE_CODE_SCHOOL[invite_code]

        # 5. 密码校验
        if not password_md5:
            flash("密码不能为空，请重新输入", "danger")
            return render_template("reg.html")

        # 6. 生成8位唯一ID
        while True:
            user_id = random.randint(10000000, 99999999)
            if not User.query.get(user_id):
                break

        # 7. 头像处理：手动上传 > QQ自动同步 > 默认头像（基于user_id命名）
        avatar_filename = "default_icon.png"
        # 优先使用手动上传的头像（传入user_id）
        if avatar_file and allowed_file(avatar_file.filename):
            avatar_filename = handle_avatar_upload(user_id, avatar_file)
        # 无手动上传则使用QQ同步头像（文件名基于user_id）
        elif qq_avatar_url and bd_qq:
            avatar_filename = f"qq_{user_id}.png"  # 改用user_id命名
            try:
                import requests
                from PIL import Image
                import io
                response = requests.get(qq_avatar_url, timeout=5)
                if response.status_code == 200:
                    img = Image.open(io.BytesIO(response.content))
                    img_path = os.path.join(config.UPLOAD_FOLDER, avatar_filename)
                    img.save(img_path)
            except:
                avatar_filename = "default_icon.png"

        # 8. 创建用户
        new_user = User(
            user_id=user_id,
            nickname=nickname,
            password=password_md5,
            school=school,
            bd_qq=bd_qq,
            avatar=avatar_filename,
            dan="初段",
            promote_cond=DAN_INFO["初段"][0],
            dan_pt=DAN_INFO["初段"][1],
            active=True
        )

        try:
            db.session.add(new_user)
            db.session.commit()
            flash(f"注册成功！您的ID：{user_id}", "success")
            return redirect(url_for("index_verify"))
        except Exception as e:
            db.session.rollback()
            flash(f"注册失败：{str(e)}", "danger")
            return render_template("reg.html")

    return render_template("reg.html")


@app.route("/create_game_progress", methods=["POST"])
def create_game_progress():
    selected_user_ids = request.json.get("selected_user_ids", [])  # 前端传用户ID列表
    if len(selected_user_ids) != 4:
        return jsonify({"code": 400, "msg": "必须选择4位玩家"})

    # 获取玩家信息并随机分配座次（基于user_id）
    seat_names = ['东', '南', '西', '北']
    users = [User.query.get(uid) for uid in selected_user_ids]
    # 过滤无效用户
    valid_users = [u for u in users if u is not None]
    if len(valid_users) != 4:
        return jsonify({"code": 400, "msg": "部分玩家ID无效"})

    shuffled_users = sorted(valid_users, key=lambda x: uuid.uuid4())  # 随机排序
    players_list = []
    for i, user in enumerate(shuffled_users):
        players_list.append({
            "user_id": user.user_id,  # 存储user_id而非昵称
            "seat": seat_names[i],
            "avatar": url_for('static', filename='uploads/' + user.avatar)
            if user.avatar != 'default_icon.png'
            else url_for('static', filename='default_icon.png')
        })

    # 创建对局进度记录
    progress_id = str(uuid.uuid4())
    progress = GameProgress(
        id=progress_id,
        status="ongoing"
    )
    progress.set_players(players_list)
    db.session.add(progress)
    db.session.commit()

    return jsonify({
        "code": 200,
        "msg": "创建成功",
        "data": {
            "progress_id": progress_id,
            "players": players_list
        }
    })


@app.route("/dissolve_game_progress/<progress_id>", methods=["POST"])
def dissolve_game_progress(progress_id):
    progress = GameProgress.query.get(progress_id)
    if not progress:
        return jsonify({"code": 404, "msg": "对局不存在"})
    if progress.status != "ongoing":
        return jsonify({"code": 400, "msg": "非进行中的对局无法解散"})

    # 更新状态为解散
    progress.status = "dissolved"
    db.session.commit()
    return jsonify({"code": 200, "msg": "对局已解散"})


# -------------------------- 剩余路由（全量ID依赖，无昵称） --------------------------

# 对局管理页（录入分数、计算PT、更新用户数据）
# -------------------------- 剩余路由（全量ID依赖，无昵称） --------------------------
# 对局管理页（录入分数、计算PT、更新用户数据）
@app.route("/game", methods=["GET", "POST"])
def game_manage():
    # 新增：获取当前登录用户并校验，过滤当前学校数据
    # 🔴 改动1：新增导入异常类
    from flask import session, flash, redirect, url_for
    from sqlalchemy.exc import IntegrityError
    if 'user_id' not in session:
        flash("请先登录后再操作", "danger")
        return redirect(url_for('index_verify'))
    current_user = User.query.get(session['user_id'])
    current_school = current_user.school  # 假设User模型有school字段存储学校信息

    # 获取进行中的对局
    ongoing_progress = GameProgress.query.filter(GameProgress.status == "ongoing").all()

    # 过滤进行中的对局：仅保留当前学校玩家参与的对局
    filtered_ongoing_progress = []
    for progress in ongoing_progress:
        players = progress.get_players()
        player_uids = [p["user_id"] for p in players]
        # 检查对局内所有玩家是否属于当前学校
        is_current_school_game = True
        for uid in player_uids:
            user = User.query.get(uid)
            if not user or user.school != current_school:
                is_current_school_game = False
                break
        if is_current_school_game:
            filtered_ongoing_progress.append(progress)
    ongoing_progress = filtered_ongoing_progress

    # 获取活跃且未被锁定的玩家（基于user_id + 过滤当前学校）
    locked_uids = get_locked_players()
    active_users = User.query.filter(
        User.active == True,
        ~User.user_id.in_(locked_uids),
        User.school == current_school  # 仅显示当前学校的活跃玩家
    ).all()

    game_result = None
    current_progress = None
    progress_id = request.args.get("progress_id")

    # 加载指定的进行中对局（额外校验：仅加载当前学校的对局）
    if progress_id:
        current_progress = GameProgress.query.get(progress_id)
        if current_progress:
            # 校验当前对局是否属于当前学校
            players = current_progress.get_players()
            player_uids = [p["user_id"] for p in players]
            is_current_school_game = True
            for uid in player_uids:
                user = User.query.get(uid)
                if not user or user.school != current_school:
                    is_current_school_game = False
                    break
            if not is_current_school_game or current_progress.status != "ongoing":
                flash("对局不存在或已结束，或无访问权限", "warning")
                current_progress = None
        else:
            flash("对局不存在或已结束", "warning")
            current_progress = None

    # 处理表单提交（录入点数 - 全ID依赖）
    if request.method == "POST":
        progress_id = request.form.get("progress_id")
        if not progress_id:
            flash("无效的对局ID", "danger")
            return redirect(url_for("game_manage"))

        progress = GameProgress.query.get(progress_id)
        if not progress or progress.status != "ongoing":
            flash("对局不存在或已结束", "danger")
            return redirect(url_for("game_manage"))

        # 额外校验：提交的对局必须属于当前学校
        players = progress.get_players()
        player_uids = [p["user_id"] for p in players]
        is_current_school_game = True
        for uid in player_uids:
            user = User.query.get(uid)
            if not user or user.school != current_school:
                is_current_school_game = False
                break
        if not is_current_school_game:
            flash("无权限操作该对局", "danger")
            return redirect(url_for("game_manage"))

        # 获取玩家列表（user_id）
        players = progress.get_players()
        selected_uids = [p["user_id"] for p in players]

        # 获取分数（表单字段：score_{user_id}）
        try:
            scores = [int(request.form.get(f"score_{uid}")) for uid in selected_uids]
        except:
            flash("素点必须为整数！", "danger")
            return redirect(url_for("game_manage", progress_id=progress_id))

        # 验证素点总和
        if sum(scores) != 100000:
            flash(f"素点总和必须为100000！当前总和：{sum(scores)}", "danger")
            return redirect(url_for("game_manage", progress_id=progress_id))

        # 计算名次和PT
        ranks = calculate_ranks(scores)
        pts = [calculate_pt(scores[i], ranks[i], ranks) for i in range(4)]

        # 创建对局记录（存储user_id）
        game_time = datetime.now(BEIJING_TZ)
        while GameRecord.query.get(game_time):
            game_time = game_time + timedelta(microseconds=1)

        record = GameRecord(
            game_time=game_time, progress_id=progress.id,
            u1_user_id=selected_uids[0], u1_rank=ranks[0], u1_score=scores[0], u1_pt=pts[0],
            u2_user_id=selected_uids[1], u2_rank=ranks[1], u2_score=scores[1], u2_pt=pts[1],
            u3_user_id=selected_uids[2], u3_rank=ranks[2], u3_score=scores[2], u3_pt=pts[2],
            u4_user_id=selected_uids[3], u4_rank=ranks[3], u4_score=scores[3], u4_pt=pts[3]
        )
        db.session.add(record)

        # 更新玩家数据（基于user_id）
        game_result = []

        for i in range(4):
            uid = selected_uids[i]
            pt = pts[i]
            user = User.query.get(uid)
            user.melon_count += 5
            update_user_dan(user, pt)
            game_result.append({
                "user_id": user.user_id,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "dan": user.dan,
                "dan_pt": user.dan_pt,
                "rank": ranks[i],
                "pt": pt,
                "melon_count": user.melon_count
            })

        # 标记对局为已完成
        progress.status = "completed"

        try:
            db.session.commit()

        except IntegrityError:
            db.session.rollback()
            flash("请勿重复提交！该对局已完成录入", "danger")
            return redirect(url_for("game_manage"))

        # 刷新对局列表（重新过滤当前学校的对局）
        ongoing_progress = GameProgress.query.filter(GameProgress.status == "ongoing").all()
        filtered_ongoing_progress = []
        for progress_item in ongoing_progress:
            players_item = progress_item.get_players()
            player_uids_item = [p["user_id"] for p in players_item]
            is_current_school_game_item = True
            for uid in player_uids_item:
                user_item = User.query.get(uid)
                if not user_item or user_item.school != current_school:
                    is_current_school_game_item = False
                    break
            if is_current_school_game_item:
                filtered_ongoing_progress.append(progress_item)
        ongoing_progress = filtered_ongoing_progress

    return render_template(
        "game.html",
        active_users=active_users,
        ongoing_progress=ongoing_progress,
        current_progress=current_progress,
        game_result=game_result,
        User=User
    )


@app.route("/game_global", methods=["GET", "POST"])
def game_manage_global():
    from flask import session, flash, redirect, url_for
    # 🔴 新增：导入异常类
    from sqlalchemy.exc import IntegrityError
    if 'user_id' not in session:
        flash("请先登录后再操作", "danger")
        return redirect(url_for('index_verify'))
    # 获取进行中的对局

    ongoing_progress = GameProgress.query.filter(GameProgress.status == "ongoing").all()
    # 获取活跃且未被锁定的玩家（基于user_id）
    locked_uids = get_locked_players()
    active_users = User.query.filter(User.active == True, ~User.user_id.in_(locked_uids)).all()

    game_result = None
    current_progress = None
    progress_id = request.args.get("progress_id")

    # 加载指定的进行中对局
    if progress_id:
        current_progress = GameProgress.query.get(progress_id)
        if not current_progress or current_progress.status != "ongoing":
            flash("对局不存在或已结束", "warning")
            current_progress = None

    # 处理表单提交（录入点数 - 全ID依赖）
    if request.method == "POST":
        progress_id = request.form.get("progress_id")
        if not progress_id:
            flash("无效的对局ID", "danger")
            return redirect(url_for("game_manage_global"))  # 🔴 修复重定向

        progress = GameProgress.query.get(progress_id)
        if not progress or progress.status != "ongoing":
            flash("对局不存在或已结束", "danger")
            return redirect(url_for("game_manage_global"))  # 🔴 修复重定向

        # 获取玩家列表（user_id）
        players = progress.get_players()
        selected_uids = [p["user_id"] for p in players]

        # 获取分数（表单字段：score_{user_id}）
        try:
            scores = [int(request.form.get(f"score_{uid}")) for uid in selected_uids]
        except:
            flash("素点必须为整数！", "danger")
            return redirect(url_for("game_manage_global", progress_id=progress_id))  # 🔴 修复重定向

        # 验证素点总和
        if sum(scores) != 100000:
            flash(f"素点总和必须为100000！当前总和：{sum(scores)}", "danger")
            return redirect(url_for("game_manage_global", progress_id=progress_id))  # 🔴 修复重定向

        # 计算名次和PT
        ranks = calculate_ranks(scores)
        pts = [calculate_pt(scores[i], ranks[i], ranks) for i in range(4)]

        # 创建对局记录（存储user_id）
        game_time = datetime.now(BEIJING_TZ)
        while GameRecord.query.get(game_time):
            game_time = game_time + timedelta(microseconds=1)

        record = GameRecord(
            game_time=game_time,
            progress_id=progress.id,  # 🔴 新增：绑定对局ID
            u1_user_id=selected_uids[0], u1_rank=ranks[0], u1_score=scores[0], u1_pt=pts[0],
            u2_user_id=selected_uids[1], u2_rank=ranks[1], u2_score=scores[1], u2_pt=pts[1],
            u3_user_id=selected_uids[2], u3_rank=ranks[2], u3_score=scores[2], u3_pt=pts[2],
            u4_user_id=selected_uids[3], u4_rank=ranks[3], u4_score=scores[3], u4_pt=pts[3]
        )
        db.session.add(record)

        # 更新玩家数据（基于user_id）
        game_result = []
        for i in range(4):
            uid = selected_uids[i]
            pt = pts[i]
            user = User.query.get(uid)
            user.melon_count += 5
            update_user_dan(user, pt)
            game_result.append({
                "user_id": user.user_id,
                "nickname": user.nickname,
                "avatar": user.avatar,
                "dan": user.dan,
                "dan_pt": user.dan_pt,
                "rank": ranks[i],
                "pt": pt,
                "melon_count": user.melon_count
            })

        # 标记对局为已完成
        progress.status = "completed"

        # 🔴 新增：捕获重复提交报错
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("请勿重复提交！该对局已完成录入", "danger")
            return redirect(url_for("game_manage_global"))

        # 刷新对局列表
        ongoing_progress = GameProgress.query.filter(GameProgress.status == "ongoing").all()

    return render_template(
        "game_global.html",
        active_users=active_users,
        ongoing_progress=ongoing_progress,
        current_progress=current_progress,
        game_result=game_result,
        User=User
    )

# 月报统计页（本月PT总和排名）
@app.route("/monthly_report", methods=["GET"])
def monthly_report():
    # 检查登录状态
    user_id = session.get("user_id")
    if not user_id:
        flash("请先登录！", "danger")
        return redirect(url_for("index_verify"))
    current_user = User.query.get(user_id)
    if not current_user:
        flash("用户不存在！", "danger")
        return redirect(url_for("index_verify"))

    # 获取筛选参数：all（全系统）/school（本校）
    filter_type = request.args.get("filter", "school")
    # 确定筛选的学校：本校则传当前用户学校，全系统则传None
    school_filter = current_user.school if filter_type == "school" else None
    # 获取排名数据
    ranking = get_monthly_pt_ranking(school_filter)

    return render_template(
        "monthly_report.html",
        ranking=ranking,
        current_filter=filter_type,
        current_school=current_user.school
    )


# 段位排名页
@app.route("/ranklist", methods=["GET"])
def ranklist():
    # 检查登录状态
    user_id = session.get("user_id")
    if not user_id:
        flash("请先登录！", "danger")
        return redirect(url_for("index_verify"))
    current_user = User.query.get(user_id)
    if not current_user:
        flash("用户不存在！", "danger")
        return redirect(url_for("index_verify"))

    # 获取筛选参数：all（全系统）/school（本校）
    filter_type = request.args.get("filter", "school")
    # 确定筛选的学校
    school_filter = current_user.school if filter_type == "school" else None
    # 获取段位排名数据
    rank_list = get_dan_rank_list(school_filter)

    return render_template(
        "ranklist.html",
        rank_list=rank_list,
        current_filter=filter_type,
        current_school=current_user.school
    )


# 管理端入口：口令验证
@app.route("/manage/verify", methods=["GET", "POST"])
def manage_verify():
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if password == ADMIN_PASS:
            session["is_manage"] = True
            return redirect(url_for("manage"))
        else:
            flash("管理端口令错误！", "danger")
    return render_template("manage_verify.html")


# 管理端主页面（用户增删改、对局记录删除 - 全ID依赖）
@app.route('/manage', methods=['GET', 'POST'])
def manage():

    if not session.get("is_manage"):
        flash("请先验证管理端口令！", "danger")
        return redirect(url_for("manage_verify"))
    # 管理员权限验证（若有原有验证逻辑，保留不变）
    if request.method == 'POST':
        action = request.form.get('action')

        # 1. 原有：添加用户（完全保留，仅确保昵称字段正常入库）
        if action == 'add_user':
            nickname = request.form.get('nickname')
            bd_qq = request.form.get('bd_qq')
            school = request.form.get('school')
            melon_count = int(request.form.get('melon_count', 0))
            dan = request.form.get('dan')
            active = request.form.get('active') == 'True'
            avatar_file = request.files.get('avatar')

            # 生成用户ID（保持原有逻辑）
            user_id = str(uuid.uuid4())
            # 处理头像（保持原有逻辑）
            avatar = "default_icon.png"
            if avatar_file:
                avatar = handle_avatar_upload(user_id, avatar_file)
            elif bd_qq:
                avatar = get_qq_avatar(bd_qq, user_id)

            # 创建用户（昵称字段正常写入）
            new_user = User(
                user_id=user_id,
                nickname=nickname,  # 昵称入库
                bd_qq=bd_qq,
                school=school,
                melon_count=melon_count,
                dan=dan,
                dan_pt=DAN_INFO[dan][1],
                promote_cond=DAN_INFO[dan][0],
                active=active,
                avatar=avatar
            )
            db.session.add(new_user)
            db.session.commit()
            flash(f"用户{nickname}添加成功！", "success")
            return redirect(url_for('manage'))

        # 2. 原有：删除用户（完全保留）
        elif action == 'del_user':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                # （可选）删除关联对局记录（原有逻辑）
                records = GameRecord.query.all()
                for r in records:
                    players = r.get_players()
                    new_players = [p for p in players if p['user_id'] != user_id]
                    if len(new_players) != len(players):
                        r.players = json.dumps(new_players)
                        db.session.commit()
                # 删除用户
                db.session.delete(user)
                db.session.commit()
                flash(f"用户{user.nickname}已删除！", "success")
            else:
                flash("用户不存在！", "danger")
            return redirect(url_for('manage'))

        # 3. 原有：重置密码（完全保留）
        elif action == 'reset_pwd':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                # 示例：重置为默认密码（原有加密逻辑保留）
                default_pwd = "123456"
                user.password = hashlib.md5(default_pwd.encode()).hexdigest()
                db.session.commit()
                flash(f"用户{user.nickname}密码已重置！", "success")
            else:
                flash("用户不存在！", "danger")
            return redirect(url_for('manage'))

        # 4. 重点：修改用户（新增昵称更新逻辑，其他字段保留原有逻辑）
        elif action == 'edit_user':
            user_id = request.form.get('user_id')
            user = User.query.get(user_id)
            if user:
                # 核心：更新昵称
                user.nickname = request.form.get('nickname', user.nickname)
                # 原有字段更新（完全保留）
                user.bd_qq = request.form.get('bd_qq', user.bd_qq)
                user.school = request.form.get('school', user.school)
                user.melon_count = int(request.form.get('melon_count', user.melon_count))
                user.dan = request.form.get('dan', user.dan)
                user.dan_pt = float(request.form.get('dan_pt', user.dan_pt))
                user.active = request.form.get('active') == 'True'

                # 原有：头像更新逻辑
                avatar_file = request.files.get('avatar')
                if avatar_file and allowed_file(avatar_file.filename):
                    user.avatar = handle_avatar_upload(user_id, avatar_file)

                # 原有：段位条件更新
                user.promote_cond = DAN_INFO[user.dan][0]

                db.session.commit()
                flash(f"用户{user.nickname}信息修改成功！", "success")
            else:
                flash("用户不存在！", "danger")
            return redirect(url_for('manage'))

    # GET请求：展示管理页面（完全保留）
    all_users = User.query.all()
    all_records = GameRecord.query.all()
    return render_template(
        'manage.html',
        all_users=all_users,
        all_records=all_records,
        DAN_ORDER=DAN_ORDER,
        BEIJING_TZ=BEIJING_TZ
    )

# 退出登录/管理端
@app.route("/logout")
def logout():
    session.clear()
    flash("已退出！", "info")
    return redirect(url_for("index_verify"))


# 用户统计API（参数改为user_id）
@app.route("/api/user/stats")
def get_user_stats_api():
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"code": 400, "msg": "缺少用户ID参数"})

    try:
        stats = get_user_stats(int(user_id))
        return jsonify({
            "code": 200,
            "msg": "success",
            "data": {
                "user_id": user_id,
                "total_games": stats["total_games"],
                "avg_score": stats["avg_score"],
                "avg_rank": stats["avg_rank"],
                "last_10_ranks": stats["last_10_ranks"]
            }
        })
    except Exception as e:
        return jsonify({"code": 500, "msg": f"获取数据失败：{str(e)}"})


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    # 检查用户是否登录
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    if not user:
        flash('用户不存在', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action')

        # 处理头像上传
        if action == 'update_avatar':
            avatar_file = request.files.get('avatar')
            if avatar_file:
                # 调用工具函数处理头像上传
                new_avatar = handle_avatar_upload(user.user_id, avatar_file)
                user.avatar = new_avatar
                db.session.commit()
                flash('头像修改成功！', 'success')
            return redirect(url_for('settings'))

        # 处理昵称修改
        elif action == 'update_nickname':
            new_nickname = request.form.get('new_nickname', '').strip()
            if validate_nickname(new_nickname):
                # 检查昵称是否重复（可选，根据业务需求）
                if User.query.filter(User.nickname == new_nickname, User.user_id != user.user_id).first():
                    flash('昵称已存在', 'danger')
                else:
                    user.nickname = new_nickname
                    db.session.commit()
                    flash('昵称修改成功！', 'success')
            else:
                flash('昵称不符合规则（长度1-10位，不含危险字符）', 'danger')
            return redirect(url_for('settings'))

        # 处理所属组织修改
        elif action == 'update_school':
            new_invite_code = request.form.get('new_invite_code', '').strip()
            # 验证邀请码（根据INVITE_CODE_SCHOOL配置）
            if new_invite_code in INVITE_CODE_SCHOOL:
                user.school = INVITE_CODE_SCHOOL[new_invite_code]
                db.session.commit()
                flash('所属组织修改成功！', 'success')
            else:
                flash('邀请码无效', 'danger')
            return redirect(url_for('settings'))
        elif action == 'update_qq':
            new_qq = request.form.get('new_qq').strip()
            if not validate_qq(new_qq):
                flash('QQ号格式不正确（需为5-13位纯数字）！', 'danger')
                return redirect(url_for('settings'))
            # 更新QQ号
            user.bd_qq = new_qq
            # 可选：自动拉取QQ头像并更新（不需要可注释）
            qq_avatar_filename = get_qq_avatar(new_qq, user.user_id)
            user.avatar = qq_avatar_filename
            # 提交数据库
            db.session.commit()
            flash('QQ绑定成功！', 'success')
            return redirect(url_for('settings'))

        # 处理密码修改
        elif action == 'update_password':
            old_pwd_md5 = request.form.get('old_password_md5')
            new_pwd_md5 = request.form.get('new_password_md5')

            # 验证原密码
            if user.password != old_pwd_md5:
                flash('原密码错误', 'danger')
            else:
                user.password = new_pwd_md5
                db.session.commit()
                flash('密码修改成功，请重新登录', 'success')
                return redirect(url_for('logout'))  # 强制登出，要求重新登录
            return redirect(url_for('settings'))

    # GET请求渲染设置页面
    return render_template('settings.html', user=user)

# 确保app能独立运行
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=False)

