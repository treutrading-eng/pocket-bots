"""
Pocket Option — Signal Bot для Telegram
с выбором языка (RU/EN) и улучшенным дизайном
"""

import os
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

# ─── Язык пользователей (user_id -> "ru"/"en") ────────────────
USER_LANG: dict[int, str] = {}

def lang(uid: int) -> str:
    return USER_LANG.get(uid, "ru")

# ─── Переводы ─────────────────────────────────────────────────
T = {
    "welcome": {
        "ru": "🌐 Выберите язык / Choose language:",
        "en": "🌐 Выберите язык / Choose language:",
    },
    "menu_title": {
        "ru": (
            "╔══════════════════════════╗\n"
            "║  📊 POCKET OPTION BOT    ║\n"
            "╚══════════════════════════╝\n\n"
            "Выберите торговую пару:"
        ),
        "en": (
            "╔══════════════════════════╗\n"
            "║  📊 POCKET OPTION BOT    ║\n"
            "╚══════════════════════════╝\n\n"
            "Choose a trading pair:"
        ),
    },
    "forex": {"ru": "🌍 Форекс пары", "en": "🌍 Forex pairs"},
    "otc":   {"ru": "🕐 OTC пары",    "en": "🕐 OTC pairs"},
    "crypto":{"ru": "₿ Крипто",       "en": "₿ Crypto"},
    "all":   {"ru": "🔄 Все пары",    "en": "🔄 All pairs"},
    "back":  {"ru": "◀ Назад",        "en": "◀ Back"},
    "choose_tf": {"ru": "⏱ Выберите таймфрейм:", "en": "⏱ Choose timeframe:"},
    "indicators":{"ru": "📊 Индикаторы", "en": "📊 Indicators"},
    "price":     {"ru": "Цена",          "en": "Price"},
    "signal":    {"ru": "Сигнал",        "en": "Signal"},
    "confidence":{"ru": "Уверенность",   "en": "Confidence"},
    "disclaimer":{"ru": "⚠️ _Только для анализа. Торговля — ваш риск._",
                  "en": "⚠️ _For analysis only. Trading is your risk._"},
    "oversold":  {"ru": "Перепродан",    "en": "Oversold"},
    "overbought":{"ru": "Перекуплен",    "en": "Overbought"},
    "neutral":   {"ru": "Нейтрально",    "en": "Neutral"},
    "bull_trend":{"ru": "Бычий тренд",   "en": "Bullish trend"},
    "bear_trend":{"ru": "Медвежий тренд","en": "Bearish trend"},
    "sideways":  {"ru": "Боковик",       "en": "Sideways"},
    "bull_cross":{"ru": "Бычье пересечение","en": "Bullish crossover"},
    "bear_cross":{"ru": "Медвежье пересечение","en": "Bearish crossover"},
    "bull_candle":{"ru": "Бычья свеча",  "en": "Bullish candle"},
    "bear_candle":{"ru": "Медвежья свеча","en": "Bearish candle"},
    "call":  {"ru": "CALL 📈 — ПОКУПКА", "en": "CALL 📈 — BUY"},
    "put":   {"ru": "PUT 📉 — ПРОДАЖА",  "en": "PUT 📉 — SELL"},
    "wait":  {"ru": "⏸ ОЖИДАНИЕ",        "en": "⏸ WAIT"},
    "all_header": {"ru": "📊 Все пары", "en": "📊 All pairs"},
    "settings": {"ru": "⚙️ Язык", "en": "⚙️ Language"},
    "unknown":{"ru": "❌ Неизвестная пара.", "en": "❌ Unknown pair."},
}

def t(key: str, uid: int) -> str:
    return T[key][lang(uid)]

# ─── Пары ─────────────────────────────────────────────────────
PAIRS = {
    # Форекс
    "EUR/USD": {"base": 1.0842, "vol": 0.0008, "dec": 5, "cat": "forex"},
    "GBP/USD": {"base": 1.2714, "vol": 0.0012, "dec": 5, "cat": "forex"},
    "USD/JPY": {"base": 157.42, "vol": 0.15,   "dec": 3, "cat": "forex"},
    "AUD/USD": {"base": 0.6634, "vol": 0.0007, "dec": 5, "cat": "forex"},
    "USD/CAD": {"base": 1.3612, "vol": 0.0009, "dec": 5, "cat": "forex"},
    "NZD/USD": {"base": 0.6124, "vol": 0.0007, "dec": 5, "cat": "forex"},
    "EUR/JPY": {"base": 170.52, "vol": 0.18,   "dec": 3, "cat": "forex"},
    "GBP/JPY": {"base": 199.84, "vol": 0.22,   "dec": 3, "cat": "forex"},
    # OTC
    "EUR/USD OTC": {"base": 1.0842, "vol": 0.0010, "dec": 5, "cat": "otc"},
    "GBP/USD OTC": {"base": 1.2714, "vol": 0.0014, "dec": 5, "cat": "otc"},
    "USD/JPY OTC": {"base": 157.42, "vol": 0.18,   "dec": 3, "cat": "otc"},
    "AUD/USD OTC": {"base": 0.6634, "vol": 0.0009, "dec": 5, "cat": "otc"},
    "EUR/JPY OTC": {"base": 170.52, "vol": 0.20,   "dec": 3, "cat": "otc"},
    "GBP/JPY OTC": {"base": 199.84, "vol": 0.25,   "dec": 3, "cat": "otc"},
    "USD/CAD OTC": {"base": 1.3612, "vol": 0.0011, "dec": 5, "cat": "otc"},
    "NZD/USD OTC": {"base": 0.6124, "vol": 0.0009, "dec": 5, "cat": "otc"},
    # Крипто
    "BTC/USD": {"base": 67540, "vol": 450, "dec": 1, "cat": "crypto"},
    "ETH/USD": {"base": 3521,  "vol": 28,  "dec": 2, "cat": "crypto"},
    "LTC/USD": {"base": 84.5,  "vol": 1.2, "dec": 2, "cat": "crypto"},
}

TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1"]

# ─── Генерация свечей ─────────────────────────────────────────
def gen_candles(base: float, vol: float, n: int = 60) -> list[dict]:
    price = base * (0.997 + random.random() * 0.006)
    candles = []
    for _ in range(n):
        o = price
        c = o + random.uniform(-vol, vol)
        h = max(o, c) + random.uniform(0, vol * 0.5)
        lo = min(o, c) - random.uniform(0, vol * 0.5)
        candles.append({"o": o, "h": h, "l": lo, "c": c})
        price = c
    return candles

def calc_rsi(closes: list[float], period: int = 14) -> float:
    gains, losses = [], []
    for i in range(1, period + 1):
        d = closes[-period + i] - closes[-period + i - 1]
        (gains if d > 0 else losses).append(abs(d))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period or 1e-9
    return 100 - 100 / (1 + avg_g / avg_l)

# ─── Анализ ───────────────────────────────────────────────────
def analyze(pair: str, uid: int) -> dict:
    info = PAIRS[pair]
    candles = gen_candles(info["base"], info["vol"])
    closes = [c["c"] for c in candles]

    rsi  = calc_rsi(closes)
    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50
    macd = sum(closes[-12:]) / 12 - sum(closes[-26:]) / 26
    last = closes[-1]
    prev = closes[-2]
    change = (last - prev) / prev * 100

    reasons = [
        {
            "name":  "RSI (14)",
            "value": f"{rsi:.0f}",
            "dir":   "up" if rsi < 45 else ("dn" if rsi > 60 else "nt"),
            "hint":  t("oversold", uid) if rsi < 45 else (t("overbought", uid) if rsi > 60 else t("neutral", uid)),
        },
        {
            "name":  "MA20 / MA50",
            "value": f"{ma20:.{info['dec']}f} / {ma50:.{info['dec']}f}",
            "dir":   "up" if ma20 > ma50 else ("dn" if ma20 < ma50 else "nt"),
            "hint":  t("bull_trend", uid) if ma20 > ma50 else (t("bear_trend", uid) if ma20 < ma50 else t("sideways", uid)),
        },
        {
            "name":  "MACD",
            "value": f"{macd:+.5f}",
            "dir":   "up" if macd > 0 else ("dn" if macd < 0 else "nt"),
            "hint":  t("bull_cross", uid) if macd > 0 else t("bear_cross", uid),
        },
        {
            "name":  "Candle" if lang(uid) == "en" else "Свеча",
            "value": t("bull_candle", uid) if last > prev else t("bear_candle", uid),
            "dir":   "up" if last > prev else "dn",
            "hint":  ("Close above prev" if lang(uid) == "en" else "Закрытие выше") if last > prev
                     else ("Close below prev" if lang(uid) == "en" else "Закрытие ниже"),
        },
    ]

    score = sum(1 if r["dir"] == "up" else (-1 if r["dir"] == "dn" else 0) for r in reasons)
    conf  = min(95, max(35, 50 + score * 12 + random.uniform(-5, 5)))
    direction = "buy" if score >= 2 else ("sell" if score <= -2 else "wait")

    return {
        "pair": pair, "price": f"{last:.{info['dec']}f}",
        "change": change, "rsi": rsi, "conf": conf,
        "direction": direction, "reasons": reasons,
        "cat": info["cat"],
    }

# ─── Форматирование сообщения ─────────────────────────────────
def format_signal(data: dict, tf: str, uid: int) -> str:
    d = data
    is_otc = "OTC" in d["pair"]
    otc_badge = " 🕐OTC" if is_otc else ""

    if d["direction"] == "buy":
        sig_line = f"🟢 *{t('call', uid)}*"
        bar_fill = "🟩"
    elif d["direction"] == "sell":
        sig_line = f"🔴 *{t('put', uid)}*"
        bar_fill = "🟥"
    else:
        sig_line = f"⚪ *{t('wait', uid)}*"
        bar_fill = "⬜"

    conf_pct = int(d["conf"])
    filled = round(conf_pct / 10)
    bar = bar_fill * filled + "▪️" * (10 - filled)

    chg = f"+{d['change']:.2f}%" if d["change"] >= 0 else f"{d['change']:.2f}%"
    icons = {"up": "🟢", "dn": "🔴", "nt": "⚪"}

    lines = [
        f"┌─────────────────────────┐",
        f"│  📊 {d['pair']}{otc_badge} │ ⏱ {tf}",
        f"└─────────────────────────┘",
        f"",
        f"💰 *{t('price', uid)}:* `{d['price']}` ({chg})",
        f"📈 *{t('signal', uid)}:* {sig_line}",
        f"🎯 *{t('confidence', uid)}:* {bar} {conf_pct}%",
        f"",
        f"━━━ {t('indicators', uid)} ━━━",
    ]
    for r in d["reasons"]:
        lines.append(f"{icons[r['dir']]} *{r['name']}:* `{r['value']}` — _{r['hint']}_")

    lines += ["", t("disclaimer", uid)]
    return "\n".join(lines)

# ─── Клавиатуры ───────────────────────────────────────────────
def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang:ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en"),
    ]])

def main_keyboard(uid: int) -> InlineKeyboardMarkup:
    ln = lang(uid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(T["forex"][ln], callback_data="cat:forex"),
         InlineKeyboardButton(T["otc"][ln],   callback_data="cat:otc")],
        [InlineKeyboardButton(T["crypto"][ln], callback_data="cat:crypto")],
        [InlineKeyboardButton(T["all"][ln],    callback_data="all:M5")],
        [InlineKeyboardButton(T["settings"][ln], callback_data="settings")],
    ])

def cat_keyboard(cat: str, uid: int) -> InlineKeyboardMarkup:
    pairs = [p for p, v in PAIRS.items() if v["cat"] == cat]
    rows = []
    row = []
    for i, p in enumerate(pairs):
        row.append(InlineKeyboardButton(p, callback_data=f"pair:{p}:M5"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t("back", uid), callback_data="back")])
    return InlineKeyboardMarkup(rows)

def tf_keyboard(pair: str, uid: int) -> InlineKeyboardMarkup:
    btns = [[InlineKeyboardButton(tf, callback_data=f"pair:{pair}:{tf}") for tf in TIMEFRAMES]]
    btns.append([InlineKeyboardButton(t("back", uid), callback_data="back")])
    return InlineKeyboardMarkup(btns)

# ─── Handlers ─────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        T["welcome"]["ru"],
        reply_markup=lang_keyboard(),
    )

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data.startswith("setlang:"):
        USER_LANG[uid] = data.split(":")[1]
        await query.edit_message_text(
            t("menu_title", uid),
            parse_mode="Markdown",
            reply_markup=main_keyboard(uid),
        )
        return

    if data == "settings":
        await query.edit_message_text(
            T["welcome"]["ru"],
            reply_markup=lang_keyboard(),
        )
        return

    if data == "back":
        await query.edit_message_text(
            t("menu_title", uid),
            parse_mode="Markdown",
            reply_markup=main_keyboard(uid),
        )
        return

    if data.startswith("cat:"):
        cat = data.split(":")[1]
        await query.edit_message_text(
            t("choose_tf", uid),
            reply_markup=cat_keyboard(cat, uid),
        )
        return

    if data.startswith("all:"):
        tf = data.split(":")[1]
        lines = [f"*{t('all_header', uid)} — {tf}*\n"]
        for pair in PAIRS:
            d = analyze(pair, uid)
            chg = f"+{d['change']:.2f}%" if d["change"] >= 0 else f"{d['change']:.2f}%"
            icon = "🟢" if d["direction"] == "buy" else ("🔴" if d["direction"] == "sell" else "⚪")
            sig = t("call", uid).split(" ")[0] if d["direction"] == "buy" else (
                  t("put", uid).split(" ")[0] if d["direction"] == "sell" else "⏸")
            lines.append(f"{icon} *{pair}* `{d['price']}` ({chg}) — {sig} {int(d['conf'])}%")
        lines.append(f"\n{t('disclaimer', uid)}")
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(t("back", uid), callback_data="back")]
            ]),
        )
        return

    if data.startswith("pair:"):
        parts = data.split(":")
        # pair может содержать "/" и пробелы — берём всё кроме последнего элемента
        tf = parts[-1]
        pair = ":".join(parts[1:-1])
        if pair not in PAIRS:
            await query.answer(t("unknown", uid))
            return
        d = analyze(pair, uid)
        await query.edit_message_text(
            format_signal(d, tf, uid),
            parse_mode="Markdown",
            reply_markup=tf_keyboard(pair, uid),
        )

# ─── Запуск ───────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(on_callback))
    print("✅ Бот запущен.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
