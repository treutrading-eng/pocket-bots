"""
TREU AI — Trading Signal Bot
с проверкой регистрации и депозита через PocketPartners API
"""
import os, io, logging, random, hashlib, aiohttp
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)

# ── PocketPartners настройки ──────────────────────────────────
# Замени на свои реальные данные
POCKET_PARTNER_ID = os.getenv("POCKET_PARTNER_ID", "ВАШ_PARTNER_ID")
POCKET_API_TOKEN  = os.getenv("POCKET_API_TOKEN",  "ВАШ_API_TOKEN")
POCKET_REF_LINK   = os.getenv("POCKET_REF_LINK",   "ВАША_РЕФЕРАЛЬНАЯ_ССЫЛКА")  # ссылка для регистрации
POCKET_API_BASE   = "https://pocketpartners.com/api/user-info"

def _pocket_hash(user_id: str) -> str:
    raw = f"{user_id}{POCKET_PARTNER_ID}{POCKET_API_TOKEN}"
    return hashlib.md5(raw.encode()).hexdigest()

async def check_pocket_user(telegram_id: int) -> dict | None:
    """Запрос к PocketPartners API. Возвращает dict или None при ошибке."""
    uid = str(telegram_id)
    url = f"{POCKET_API_BASE}/{uid}/{POCKET_PARTNER_ID}/{_pocket_hash(uid)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                logging.warning(f"[PocketPartners] HTTP {resp.status} для user {uid}")
                return None
    except Exception as e:
        logging.error(f"[PocketPartners] Ошибка запроса: {e}")
        return None

async def is_verified(telegram_id: int) -> tuple[bool, bool]:
    """
    Возвращает (is_registered, has_deposit).
    ⚠️ Замени ключи "registered" и "deposited" на реальные поля из ответа API.
    """
    data = await check_pocket_user(telegram_id)
    if data is None:
        return False, False
    # Подстрой ключи под реальный ответ PocketPartners
    registered = bool(data.get("registered", False))
    deposited  = bool(data.get("deposited",  False))
    return registered, deposited

# ─────────────────────────────────────────────────────────────

USER_LANG: dict[int, str] = {}
def lang(uid): return USER_LANG.get(uid, "ru")

# ── Images ────────────────────────────────────────────────────
WELCOME_IMG_URL = "https://treutrading-eng.github.io/pocket-bots/welcome.jpg"
RECEIVE_IMG_URL = "https://treutrading-eng.github.io/pocket-bots/receive.jpg"

def make_welcome_img():  return WELCOME_IMG_URL
def make_receive_img():  return RECEIVE_IMG_URL
def make_signal_img(direction): return RECEIVE_IMG_URL

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

# ── Access denied texts ───────────────────────────────────────
def not_registered_text(uid):
    ln = lang(uid)
    if ln == "en":
        return (
            "🔒 *Access Denied*\n\n"
            "To use this bot you need to:\n"
            "1️⃣ Register via the referral link\n"
            "2️⃣ Make a deposit\n\n"
            "After completing both steps, press /start again."
        )
    return (
        "🔒 *Доступ закрыт*\n\n"
        "Для использования бота необходимо:\n"
        "1️⃣ Зарегистрироваться по реферальной ссылке\n"
        "2️⃣ Внести депозит\n\n"
        "После выполнения обоих шагов нажмите /start снова."
    )

def no_deposit_text(uid):
    ln = lang(uid)
    if ln == "en":
        return (
            "✅ *Registration confirmed!*\n\n"
            "⚠️ No deposit detected yet.\n\n"
            "Please make a deposit to unlock full access to the bot.\n"
            "After depositing, press /start again."
        )
    return (
        "✅ *Регистрация подтверждена!*\n\n"
        "⚠️ Депозит не обнаружен.\n\n"
        "Пожалуйста, внесите депозит для получения доступа к боту.\n"
        "После пополнения нажмите /start снова."
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

def register_kb(uid):
    ln = lang(uid)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "📝 " + ("Register" if ln=="en" else "Зарегистрироваться"),
            url=POCKET_REF_LINK
        )
    ]])

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

    # ── Проверка регистрации и депозита ──────────────────────
    registered, deposited = await is_verified(uid)

    if not registered:
        await update.message.reply_photo(
            photo=make_welcome_img(),
            caption=not_registered_text(uid),
            parse_mode="Markdown",
            reply_markup=register_kb(uid)
        )
        return

    if not deposited:
        await update.message.reply_photo(
            photo=make_welcome_img(),
            caption=no_deposit_text(uid),
            parse_mode="Markdown",
            reply_markup=register_kb(uid)
        )
        return
    # ─────────────────────────────────────────────────────────

    await update.message.reply_photo(
        photo=make_welcome_img(),
        caption=welcome_text(uid),
        parse_mode="Markdown",
        reply_markup=main_kb(uid)
    )

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    # ── Проверка на всех callback кроме lang ─────────────────
    if not data.startswith("lang:"):
        registered, deposited = await is_verified(uid)
        if not registered or not deposited:
            caption = not_registered_text(uid) if not registered else no_deposit_text(uid)
            await q.message.chat.send_message(
                caption,
                parse_mode="Markdown",
                reply_markup=register_kb(uid)
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
    print("✅ TREU AI Bot запущен.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
