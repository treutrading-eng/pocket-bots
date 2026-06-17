"""
TREU AI — Trading Signal Bot
с пошаговой проверкой регистрации и депозита через PocketPartners API
"""
import os, io, logging, random, hashlib, aiohttp
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)

# ── PocketPartners настройки ──────────────────────────────────
POCKET_PARTNER_ID = os.getenv("POCKET_PARTNER_ID", "ВАШ_PARTNER_ID")
POCKET_API_TOKEN  = os.getenv("POCKET_API_TOKEN",  "ВАШ_API_TOKEN")
POCKET_REF_LINK   = os.getenv("POCKET_REF_LINK",   "ВАША_РЕФЕРАЛЬНАЯ_ССЫЛКА")
POCKET_API_BASE   = "https://pocketpartners.com/api/user-info"

def _pocket_hash(user_id: str) -> str:
    raw = f"{user_id}:{POCKET_PARTNER_ID}:{POCKET_API_TOKEN}"
    return hashlib.md5(raw.encode()).hexdigest()

async def check_pocket_user(pocket_id: str) -> dict | None:
    """Запрос к PocketPartners API по ID пользователя с платформы."""
    url = f"{POCKET_API_BASE}/{pocket_id}/{POCKET_PARTNER_ID}/{_pocket_hash(pocket_id)}"
    logging.info(f"[PocketPartners] Запрос URL: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                raw_text = await resp.text()
                logging.info(f"[PocketPartners] Статус: {resp.status} | Ответ: {raw_text}")
                if resp.status == 200:
                    try:
                        return await resp.json(content_type=None)
                    except Exception as parse_err:
                        logging.error(f"[PocketPartners] Не удалось распарсить JSON: {parse_err}")
                        return None
                logging.warning(f"[PocketPartners] HTTP {resp.status} для user {pocket_id}")
                return None
    except Exception as e:
        logging.error(f"[PocketPartners] Ошибка запроса: {e}")
        return None

def _is_registered(data: dict | None) -> bool:
    """
    Пользователь считается зарегистрированным, если API вернул его карточку
    (есть uid и дата регистрации). API не отдаёт отдельное поле "registered" —
    если запись найдена (status 200), значит пользователь существует в системе.
    """
    if not data:
        return False
    return bool(data.get("uid")) or bool(data.get("reg_date"))

def _has_deposit(data: dict | None) -> bool:
    """
    Депозит подтверждён, если есть хотя бы один платёж.
    Используем count_deposits / sum_deposits из реального ответа API.
    """
    if not data:
        return False
    count = data.get("count_deposits", 0) or 0
    total = data.get("sum_deposits", 0) or 0
    try:
        return float(count) > 0 or float(total) > 0
    except (TypeError, ValueError):
        return False

# ── Состояния пользователей ───────────────────────────────────
# Хранит на каком этапе находится пользователь
# "await_reg_id"  — ждём ввода ID для проверки регистрации
# "await_dep_id"  — ждём ввода ID для проверки депозита
USER_STATE: dict[int, str] = {}

# Хранит pocket_id после успешной регистрации
USER_POCKET_ID: dict[int, str] = {}

USER_LANG: dict[int, str] = {}
def lang(uid): return USER_LANG.get(uid, "en")

# ── Images ────────────────────────────────────────────────────
REGISTRATION_IMG  = "https://treutrading-eng.github.io/pocket-bots/registration.jpg"
LAST_STAGE_IMG    = "https://treutrading-eng.github.io/pocket-bots/last_stage.png"
ID_NOT_FOUND_IMG  = "https://treutrading-eng.github.io/pocket-bots/id_not_found.png"
WELCOME_IMG_URL   = "https://treutrading-eng.github.io/pocket-bots/welcome.jpg"
RECEIVE_IMG_URL   = "https://treutrading-eng.github.io/pocket-bots/receive.jpg"

def make_welcome_img():         return WELCOME_IMG_URL
def make_receive_img():         return RECEIVE_IMG_URL
def make_signal_img(direction): return RECEIVE_IMG_URL
def make_registration_img():    return REGISTRATION_IMG
def make_last_stage_img():      return LAST_STAGE_IMG
def make_id_not_found_img():    return ID_NOT_FOUND_IMG

# ── Pairs & Analysis ──────────────────────────────────────────
PAIRS = {
    "EUR/USD":     {"base":1.0842,"vol":0.0008,"dec":5,"cat":"forex"},
    "GBP/USD":     {"base":1.2714,"vol":0.0012,"dec":5,"cat":"forex"},
    "USD/JPY":     {"base":157.42,"vol":0.15,  "dec":3,"cat":"forex"},
    "AUD/USD":     {"base":0.6634,"vol":0.0007,"dec":5,"cat":"forex"},
    "USD/CAD":     {"base":1.3612,"vol":0.0009,"dec":5,"cat":"forex"},
    "NZD/USD":     {"base":0.6124,"vol":0.0007,"dec":5,"cat":"forex"},
    "EUR/JPY":     {"base":170.52,"vol":0.18,  "dec":3,"cat":"forex"},
    "GBP/JPY":     {"base":199.84,"vol":0.22,  "dec":3,"cat":"forex"},
    "EUR/USD OTC": {"base":1.0842,"vol":0.0010,"dec":5,"cat":"otc"},
    "GBP/USD OTC": {"base":1.2714,"vol":0.0014,"dec":5,"cat":"otc"},
    "USD/JPY OTC": {"base":157.42,"vol":0.18,  "dec":3,"cat":"otc"},
    "AUD/USD OTC": {"base":0.6634,"vol":0.0009,"dec":5,"cat":"otc"},
    "EUR/GBP OTC": {"base":0.8524,"vol":0.0009,"dec":5,"cat":"otc"},
    "EUR/JPY OTC": {"base":170.52,"vol":0.20,  "dec":3,"cat":"otc"},
    "GBP/JPY OTC": {"base":199.84,"vol":0.25,  "dec":3,"cat":"otc"},
    "NZD/USD OTC": {"base":0.6124,"vol":0.0009,"dec":5,"cat":"otc"},
}

EXPIRY = {
    "S3":"3 сек","S15":"15 сек","S30":"30 сек",
    "M1":"1 мин","M3":"3 мин","M5":"5 мин",
    "M15":"15 мин","M30":"30 мин","H1":"1 час",
}
EXPIRY_EN = {
    "S3":"3 sec","S15":"15 sec","S30":"30 sec",
    "M1":"1 min","M3":"3 min","M5":"5 min",
    "M15":"15 min","M30":"30 min","H1":"1 hour",
}

def gen_candles(base, vol, n=60):
    price = base*(0.997+random.random()*0.006)
    c = []
    for _ in range(n):
        o=price; cl=o+random.uniform(-vol,vol)
        c.append({"o":o,"c":cl}); price=cl
    return c

def calc_rsi(closes, p=14):
    g=l=0
    for i in range(len(closes)-p, len(closes)):
        d=closes[i]-closes[i-1]
        if d>0: g+=d
        else: l-=d
    return 100-100/(1+(g/p)/((l/p) or 1e-9))

def analyze(pair, tf, uid):
    info = PAIRS[pair]
    candles = gen_candles(info["base"], info["vol"])
    closes = [c["c"] for c in candles]
    rsi = calc_rsi(closes)
    ma20 = sum(closes[-20:])/20; ma50 = sum(closes[-50:])/50
    macd = sum(closes[-12:])/12 - sum(closes[-26:])/26
    last = closes[-1]; prev = closes[-2]
    score = 0
    if rsi<45: score+=1
    elif rsi>60: score-=1
    if ma20>ma50: score+=1
    else: score-=1
    if macd>0: score+=1
    else: score-=1
    if last>prev: score+=1
    else: score-=1
    direction = "buy" if score>=0 else "sell"
    conf = min(95, max(74, 74+abs(score)*4+random.uniform(0,8)))
    now = datetime.now(timezone(timedelta(hours=3)))
    ln = lang(uid)
    exp_map = EXPIRY_EN if ln=="en" else EXPIRY
    return {
        "pair": pair, "tf": tf, "direction": direction, "conf": conf,
        "price": f"{last:.{info['dec']}f}",
        "expiry": exp_map.get(tf, tf),
        "entry_time": now.strftime("%H:%M"),
        "strength": ("Strong" if ln=="en" else "Сильный") if conf>=85 else ("Medium" if ln=="en" else "Средний"),
    }

# ── Text ──────────────────────────────────────────────────────
def welcome_text(uid):
    return (
        "👋 *Welcome to TREU TRADING AI*\n\n"
        "📊 A community focused on market analysis, trading technologies, and AI-powered insights.\n\n"
        "🤖 Our assistant processes market data using advanced analytical models to identify potential opportunities and market trends."
    )

def congrats_text(uid):
    return (
        "⚡ *Congratulations!* Your signal access has been unlocked.\n\n"
        "Press *\"Receive a Signal\"* to get your first AI-powered trading signal."
    )

def signal_text(d, uid):
    ln = lang(uid)
    icon = "🟢" if d["direction"]=="buy" else "🔴"
    pos = ("📈 CALL — BUY" if ln=="en" else "📈 CALL — ПОКУПКА") if d["direction"]=="buy" else ("📉 PUT — SELL" if ln=="en" else "📉 PUT — ПРОДАЖА")
    entry_lbl = "Entry Time" if ln=="en" else "Время входа"
    exp_lbl = "Expiry" if ln=="en" else "Экспирация"
    str_lbl = "Strength" if ln=="en" else "Сила сигнала"
    acc_lbl = "Accuracy" if ln=="en" else "Точность"
    bars = int(d["conf"]/10); bar = "🟩"*bars + "⬜"*(10-bars)
    return (
        f"{icon} *{d['pair']}* | ⏱ {d['tf']}\n\n"
        f"📊 *{pos}*\n\n"
        f"🕐 *{entry_lbl}:* `{d['entry_time']} UTC+3`\n"
        f"⌛ *{exp_lbl}:* `{d['expiry']}`\n"
        f"✅ *{str_lbl}:* `{d['strength']}`\n\n"
        f"🎯 *{acc_lbl}:* {bar} `{d['conf']:.2f}%`\n\n"
        f"⚠️ _{'For analysis only. Trading is your risk.' if ln=='en' else 'Только для анализа. Торговля — ваш риск.'}_"
    )

# ── Step texts ────────────────────────────────────────────────
def step1_text():
    return (
        "First, you need to register with the broker using the button below\n\n"
        "If you already had an account, you must create a new one, otherwise the bot won't be able to identify you and you won't be able to receive signals.\n\n"
        "After that, press the button \"Registration completed\""
    )

def ask_id_text():
    return (
        "Now send your platform ID to the bot\n\n"
        "IMPORTANT! Do not enter anything except numbers into the bot"
    )

def reg_ok_text():
    return (
        "You have successfully registered!\n\n"
        "Now you have one last step left: top up your balance with any amount (we recommend starting with $50 or $100, but $10 also works).\n\n"
        "We need to understand that you are really serious about working. We cannot give access to the trading bot to everyone who wants it.\n\n"
        "After topping up, press the button \"Deposit completed\""
    )

def reg_fail_text():
    return (
        "Your ID was not found in our system.\n\n"
        "Please make sure you registered via the referral link and entered the correct ID, then try again."
    )

def dep_ok_text():
    return (
        "🎉 *Deposit confirmed!*\n\n"
        "You now have full access to TREU TRADING AI.\n\n"
        "Press *Start Trading* to get your first signal!"
    )

def dep_fail_text():
    return "⁉️ We couldn't find any deposit linked to your ID."

def ask_dep_id_text():
    return (
        "Now send your platform ID to the bot\n\n"
        "IMPORTANT! Do not enter anything except numbers into the bot"
    )

# ── Keyboards ─────────────────────────────────────────────────
def lang_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang:en"),
    ]])

def main_kb(uid):
    ln = lang(uid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 " + ("START TRADING" if ln=="en" else "НАЧАТЬ ТОРГОВЛЮ"), callback_data="start_trading")],
        [InlineKeyboardButton("📊 " + ("VIEW RESULTS" if ln=="en" else "СМОТРЕТЬ РЕЗУЛЬТАТЫ"), callback_data="results")],
        [InlineKeyboardButton("🆘 " + ("SUPPORT" if ln=="en" else "ПОДДЕРЖКА"), url="https://t.me/treu_support")],
    ])

def step1_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Register", url=POCKET_REF_LINK)],
        [InlineKeyboardButton("✅ Registration completed", callback_data="check_reg")],
        [InlineKeyboardButton("Support", url="https://t.me/treu_support")],
    ])

def ask_id_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅ Back", callback_data="back_to_step1")],
    ])

def reg_fail_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Try again", callback_data="check_reg")],
        [InlineKeyboardButton("⬅ Back", callback_data="back_to_step1")],
    ])

def reg_ok_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Deposit", url=POCKET_REF_LINK)],
        [InlineKeyboardButton("✅ Deposit completed", callback_data="check_dep")],
        [InlineKeyboardButton("Support", url="https://t.me/treu_support")],
    ])

def dep_fail_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Check deposit", callback_data="check_dep")],
        [InlineKeyboardButton("⬅ Back", callback_data="back_to_reg_ok")],
    ])

def dep_ok_kb(uid):
    return main_kb(uid)

def signal_kb(uid):
    ln = lang(uid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 " + ("RECEIVE A SIGNAL" if ln=="en" else "ПОЛУЧИТЬ СИГНАЛ"), web_app=WebAppInfo(url="https://treutrading-eng.github.io/pocket-bots/miniapp.html"))],
        [InlineKeyboardButton("🏠 " + ("HOME PAGE" if ln=="en" else "ГЛАВНАЯ"), callback_data="home")],
    ])

def pair_cat_kb(uid):
    ln = lang(uid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Forex", callback_data="cat:forex"),
         InlineKeyboardButton("🕐 OTC", callback_data="cat:otc")],
        [InlineKeyboardButton("◀ " + ("Back" if ln=="en" else "Назад"), callback_data="home")],
    ])

def pairs_kb(cat, uid):
    pairs = [p for p,v in PAIRS.items() if v["cat"]==cat]
    rows = []
    row = []
    for p in pairs:
        row.append(InlineKeyboardButton(p, callback_data=f"pair:{p}"))
        if len(row)==2: rows.append(row); row=[]
    if row: rows.append(row)
    ln = lang(uid)
    rows.append([InlineKeyboardButton("◀ " + ("Back" if ln=="en" else "Назад"), callback_data="get_signal")])
    return InlineKeyboardMarkup(rows)

def tf_kb(pair, uid):
    ln = lang(uid)
    cat = PAIRS[pair]["cat"]
    tfs = ["S3","S15","S30","M1","M3","M5"] if cat=="otc" else ["M1","M3","M5","M15"]
    rows = []
    row = []
    for tf in tfs:
        row.append(InlineKeyboardButton(tf, callback_data=f"tf:{pair}:{tf}"))
        if len(row)==3: rows.append(row); row=[]
    if row: rows.append(row)
    rows.append([InlineKeyboardButton("◀ " + ("Back" if ln=="en" else "Назад"), callback_data="get_signal")])
    return InlineKeyboardMarkup(rows)

# ── Handlers ──────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    USER_LANG[uid] = "en"
    USER_STATE.pop(uid, None)

    # Если уже верифицирован — сразу в бот
    if uid in USER_POCKET_ID:
        pocket_id = USER_POCKET_ID[uid]
        data = await check_pocket_user(pocket_id)
        if data:
            registered = _is_registered(data)
            deposited  = _has_deposit(data)
            if registered and deposited:
                await update.message.reply_photo(
                    photo=make_welcome_img(),
                    caption=welcome_text(uid),
                    parse_mode="Markdown",
                    reply_markup=main_kb(uid)
                )
                return

    await update.message.reply_photo(
        photo=make_registration_img(),
        caption=step1_text(),
        reply_markup=step1_kb()
    )

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения — ввод PocketPartners ID."""
    uid = update.message.from_user.id
    state = USER_STATE.get(uid)

    if state == "await_reg_id":
        pocket_id = update.message.text.strip()

        if not pocket_id.isdigit():
            await update.message.reply_text(
                "⚠️ Please enter numbers only."
            )
            return  # остаёмся в том же состоянии, ждём корректный ID

        USER_STATE.pop(uid, None)
        data = await check_pocket_user(pocket_id)
        registered = _is_registered(data)

        if registered:
            USER_POCKET_ID[uid] = pocket_id
            await update.message.reply_photo(
                photo=make_last_stage_img(),
                caption=reg_ok_text(),
                reply_markup=reg_ok_kb()
            )
        else:
            await update.message.reply_photo(
                photo=make_id_not_found_img(),
                caption=reg_fail_text(),
                reply_markup=reg_fail_kb()
            )
        return

    if state == "await_dep_id":
        pocket_id = update.message.text.strip()

        if not pocket_id.isdigit():
            await update.message.reply_text(
                "⚠️ Please enter numbers only."
            )
            return

        USER_STATE.pop(uid, None)
        data = await check_pocket_user(pocket_id)
        deposited = _has_deposit(data)

        if deposited:
            USER_POCKET_ID[uid] = pocket_id
            await update.message.reply_photo(
                photo=make_welcome_img(),
                caption=dep_ok_text(),
                parse_mode="Markdown",
                reply_markup=dep_ok_kb(uid)
            )
        else:
            await update.message.reply_text(
                dep_fail_text(),
                reply_markup=dep_fail_kb()
            )
        return

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    if data == "check_reg":
        USER_STATE[uid] = "await_reg_id"
        try: await q.message.delete()
        except: pass
        await q.message.chat.send_photo(
            photo=make_registration_img(),
            caption=ask_id_text(),
            reply_markup=ask_id_kb()
        )
        return

    if data == "check_dep":
        USER_STATE[uid] = "await_dep_id"
        try: await q.message.delete()
        except: pass
        await q.message.chat.send_photo(
            photo=make_last_stage_img(),
            caption=ask_dep_id_text(),
            reply_markup=ask_id_kb()
        )
        return

    if data == "back_to_step1":
        USER_STATE.pop(uid, None)
        try: await q.message.delete()
        except: pass
        await q.message.chat.send_photo(
            photo=make_registration_img(),
            caption=step1_text(),
            reply_markup=step1_kb()
        )
        return

    if data == "back_to_reg_ok":
        USER_STATE.pop(uid, None)
        try: await q.message.delete()
        except: pass
        await q.message.chat.send_photo(
            photo=make_last_stage_img(),
            caption=reg_ok_text(),
            reply_markup=reg_ok_kb()
        )
        return

    # ── Проверка доступа для всех остальных кнопок ───────────
    if not data.startswith("lang:"):
        pocket_id = USER_POCKET_ID.get(uid)
        if not pocket_id:
            await q.message.chat.send_photo(
                photo=make_registration_img(),
                caption=step1_text(),
                reply_markup=step1_kb()
            )
            return
        api_data = await check_pocket_user(pocket_id)
        registered = _is_registered(api_data)
        deposited  = _has_deposit(api_data)
        if not registered or not deposited:
            if registered:
                await q.message.chat.send_photo(
                    photo=make_last_stage_img(),
                    caption=reg_ok_text(),
                    reply_markup=reg_ok_kb()
                )
            else:
                await q.message.chat.send_photo(
                    photo=make_registration_img(),
                    caption=step1_text(),
                    reply_markup=step1_kb()
                )
            return
    # ─────────────────────────────────────────────────────────

    if data.startswith("lang:"):
        USER_LANG[uid] = data.split(":")[1]
        await q.message.delete()
        await q.message.chat.send_photo(
            photo=make_welcome_img(),
            caption=welcome_text(uid),
            parse_mode="Markdown",
            reply_markup=main_kb(uid)
        )
        return

    if data == "home":
        try: await q.message.delete()
        except: pass
        await q.message.chat.send_photo(
            photo=make_welcome_img(),
            caption=welcome_text(uid),
            parse_mode="Markdown",
            reply_markup=main_kb(uid)
        )
        return

    if data == "start_trading":
        try: await q.message.delete()
        except: pass
        await q.message.chat.send_photo(
            photo=make_receive_img(),
            caption=congrats_text(uid),
            parse_mode="Markdown",
            reply_markup=signal_kb(uid)
        )
        return

    if data == "results":
        await q.message.chat.send_message(
            "📊 *Results*\n\n⏳ Your results are currently being processed. Please check back soon.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀ Back", callback_data="home")]]))
        return

    if data == "get_signal":
        ln = lang(uid)
        await q.message.chat.send_message(
            "🌍 *Choose category:*",
            parse_mode="Markdown",
            reply_markup=pair_cat_kb(uid)
        )
        return

    if data.startswith("cat:"):
        cat = data.split(":")[1]
        await q.message.chat.send_message(
            "💱 *Choose pair:*",
            parse_mode="Markdown",
            reply_markup=pairs_kb(cat, uid)
        )
        return

    if data.startswith("pair:"):
        pair = data[5:]
        await q.message.chat.send_message(
            "⏱ *Choose timeframe:*",
            parse_mode="Markdown",
            reply_markup=tf_kb(pair, uid)
        )
        return

    if data.startswith("tf:"):
        parts = data.split(":")
        tf = parts[-1]; pair = ":".join(parts[1:-1])
        d = analyze(pair, tf, uid)
        try: await q.message.delete()
        except: pass
        await q.message.chat.send_photo(
            photo=make_signal_img(d["direction"]),
            caption=signal_text(d, uid),
            parse_mode="Markdown",
            reply_markup=signal_kb(uid)
        )
        return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("✅ TREU AI Bot запущен.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
