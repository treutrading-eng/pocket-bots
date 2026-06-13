"""
Pocket Option — Signal Bot
с картинками, временем захода и описанием сигнала
"""

import os
import io
import logging
import random
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)

USER_LANG: dict[int, str] = {}

def lang(uid: int) -> str:
    return USER_LANG.get(uid, "ru")

T = {
    "welcome":    {"ru": "🌐 Выберите язык / Choose language:", "en": "🌐 Выберите язык / Choose language:"},
    "menu_title": {"ru": "╔══════════════════════════╗\n║  📊 POCKET OPTION BOT    ║\n╚══════════════════════════╝\n\nВыберите торговую пару:",
                   "en": "╔══════════════════════════╗\n║  📊 POCKET OPTION BOT    ║\n╚══════════════════════════╝\n\nChoose a trading pair:"},
    "forex":      {"ru": "🌍 Форекс",      "en": "🌍 Forex"},
    "otc":        {"ru": "🕐 OTC пары",    "en": "🕐 OTC pairs"},
    "crypto":     {"ru": "₿ Крипто",       "en": "₿ Crypto"},
    "all":        {"ru": "🔄 Все пары",    "en": "🔄 All pairs"},
    "back":       {"ru": "◀ Назад",        "en": "◀ Back"},
    "settings":   {"ru": "⚙️ Язык",        "en": "⚙️ Language"},
    "choose_tf":  {"ru": "⏱ Выберите таймфрейм:", "en": "⏱ Choose timeframe:"},
    "disclaimer": {"ru": "⚠️ Только для анализа. Торговля — ваш риск.", "en": "⚠️ For analysis only. Trading is your risk."},
    "oversold":   {"ru": "Перепродан",     "en": "Oversold"},
    "overbought": {"ru": "Перекуплен",     "en": "Overbought"},
    "neutral":    {"ru": "Нейтрально",     "en": "Neutral"},
    "bull_trend": {"ru": "Бычий тренд",    "en": "Bullish trend"},
    "bear_trend": {"ru": "Медвежий тренд", "en": "Bearish trend"},
    "sideways":   {"ru": "Боковик",        "en": "Sideways"},
    "bull_cross": {"ru": "Бычье пересечение", "en": "Bullish crossover"},
    "bear_cross": {"ru": "Медвежье пересечение", "en": "Bearish crossover"},
    "bull_candle":{"ru": "Бычья",          "en": "Bullish"},
    "bear_candle":{"ru": "Медвежья",       "en": "Bearish"},
    "unknown":    {"ru": "❌ Неизвестная пара.", "en": "❌ Unknown pair."},
    "tip_buy_ru": [
        "RSI вышел из зоны перепроданности — хороший момент для CALL.",
        "MA20 пробила MA50 снизу вверх — бычий разворот.",
        "MACD в положительной зоне — тренд подтверждён.",
        "Свеча закрылась выше — импульс вверх.",
    ],
    "tip_sell_ru": [
        "RSI в зоне перекупленности — возможен откат, рассмотри PUT.",
        "MA20 пробила MA50 сверху вниз — медвежий сигнал.",
        "MACD ушёл в минус — давление продавцов усиливается.",
        "Свеча закрылась ниже — импульс вниз.",
    ],
    "tip_wait_ru": [
        "Сигналы противоречат друг другу — лучше подождать.",
        "Рынок в боковике — нет чёткого направления.",
        "Слабая уверенность — пропусти этот вход.",
    ],
    "tip_buy_en": [
        "RSI exited oversold zone — good moment for CALL.",
        "MA20 crossed MA50 upward — bullish reversal.",
        "MACD is positive — trend confirmed.",
        "Candle closed above — upward momentum.",
    ],
    "tip_sell_en": [
        "RSI in overbought zone — possible pullback, consider PUT.",
        "MA20 crossed MA50 downward — bearish signal.",
        "MACD went negative — selling pressure increasing.",
        "Candle closed below — downward momentum.",
    ],
    "tip_wait_en": [
        "Signals contradict each other — better to wait.",
        "Market is sideways — no clear direction.",
        "Low confidence — skip this entry.",
    ],
}

def t(key, uid):
    return T[key][lang(uid)]

def get_tip(direction, uid):
    key = f"tip_{direction}_{lang(uid)}"
    return random.choice(T[key]) if key in T else ""

PAIRS = {
    "EUR/USD":     {"base": 1.0842, "vol": 0.0008, "dec": 5, "cat": "forex"},
    "GBP/USD":     {"base": 1.2714, "vol": 0.0012, "dec": 5, "cat": "forex"},
    "USD/JPY":     {"base": 157.42, "vol": 0.15,   "dec": 3, "cat": "forex"},
    "AUD/USD":     {"base": 0.6634, "vol": 0.0007, "dec": 5, "cat": "forex"},
    "USD/CAD":     {"base": 1.3612, "vol": 0.0009, "dec": 5, "cat": "forex"},
    "NZD/USD":     {"base": 0.6124, "vol": 0.0007, "dec": 5, "cat": "forex"},
    "EUR/JPY":     {"base": 170.52, "vol": 0.18,   "dec": 3, "cat": "forex"},
    "GBP/JPY":     {"base": 199.84, "vol": 0.22,   "dec": 3, "cat": "forex"},
    "EUR/USD OTC": {"base": 1.0842, "vol": 0.0010, "dec": 5, "cat": "otc"},
    "GBP/USD OTC": {"base": 1.2714, "vol": 0.0014, "dec": 5, "cat": "otc"},
    "USD/JPY OTC": {"base": 157.42, "vol": 0.18,   "dec": 3, "cat": "otc"},
    "AUD/USD OTC": {"base": 0.6634, "vol": 0.0009, "dec": 5, "cat": "otc"},
    "EUR/JPY OTC": {"base": 170.52, "vol": 0.20,   "dec": 3, "cat": "otc"},
    "GBP/JPY OTC": {"base": 199.84, "vol": 0.25,   "dec": 3, "cat": "otc"},
    "USD/CAD OTC": {"base": 1.3612, "vol": 0.0011, "dec": 5, "cat": "otc"},
    "NZD/USD OTC": {"base": 0.6124, "vol": 0.0009, "dec": 5, "cat": "otc"},
    "BTC/USD":     {"base": 67540,  "vol": 450,    "dec": 1, "cat": "crypto"},
    "ETH/USD":     {"base": 3521,   "vol": 28,     "dec": 2, "cat": "crypto"},
    "LTC/USD":     {"base": 84.5,   "vol": 1.2,    "dec": 2, "cat": "crypto"},
}

EXPIRY = {
    "S3":  {"ru": "3 секунды",  "en": "3 Seconds"},
    "S15": {"ru": "15 секунд",  "en": "15 Seconds"},
    "S30": {"ru": "30 секунд",  "en": "30 Seconds"},
    "M1":  {"ru": "1 минута",   "en": "1 Minute"},
    "M3":  {"ru": "3 минуты",   "en": "3 Minutes"},
    "M5":  {"ru": "5 минут",    "en": "5 Minutes"},
    "M30": {"ru": "30 минут",   "en": "30 Minutes"},
    "H1":  {"ru": "1 час",      "en": "1 Hour"},
    "H4":  {"ru": "4 часа",     "en": "4 Hours"},
}
TIMEFRAMES = ["S3", "S15", "S30", "M1", "M3", "M5", "M30", "H1", "H4"]

def gen_candles(base, vol, n=60):
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

def calc_rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, period + 1):
        d = closes[-period + i] - closes[-period + i - 1]
        (gains if d > 0 else losses).append(abs(d))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period or 1e-9
    return 100 - 100 / (1 + avg_g / avg_l)

def analyze(pair, uid, tf="M5"):
    info = PAIRS[pair]
    candles = gen_candles(info["base"], info["vol"])
    closes = [c["c"] for c in candles]
    rsi  = calc_rsi(closes)
    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50
    macd = sum(closes[-12:]) / 12 - sum(closes[-26:]) / 26
    last = closes[-1]; prev = closes[-2]
    change = (last - prev) / prev * 100
    ln = lang(uid)
    reasons = [
        {"name": "RSI (14)", "value": f"{rsi:.0f}",
         "dir": "up" if rsi < 45 else ("dn" if rsi > 60 else "nt"),
         "hint": t("oversold", uid) if rsi < 45 else (t("overbought", uid) if rsi > 60 else t("neutral", uid))},
        {"name": "MA20/MA50", "value": f"{ma20:.{info['dec']}f}/{ma50:.{info['dec']}f}",
         "dir": "up" if ma20 > ma50 else ("dn" if ma20 < ma50 else "nt"),
         "hint": t("bull_trend", uid) if ma20 > ma50 else (t("bear_trend", uid) if ma20 < ma50 else t("sideways", uid))},
        {"name": "MACD", "value": f"{macd:+.5f}",
         "dir": "up" if macd > 0 else ("dn" if macd < 0 else "nt"),
         "hint": t("bull_cross", uid) if macd > 0 else t("bear_cross", uid)},
        {"name": "Candle" if ln == "en" else "Свеча",
         "value": t("bull_candle", uid) if last > prev else t("bear_candle", uid),
         "dir": "up" if last > prev else "dn",
         "hint": ("Up" if ln == "en" else "Вверх") if last > prev else ("Down" if ln == "en" else "Вниз")},
    ]
    score = sum(1 if r["dir"] == "up" else (-1 if r["dir"] == "dn" else 0) for r in reasons)
    conf  = min(95, max(35, 50 + score * 12 + random.uniform(-5, 5)))
    direction = "buy" if score >= 2 else ("sell" if score <= -2 else "wait")
    now = datetime.now(timezone(timedelta(hours=3)))
    strength = "Strong" if conf >= 75 else ("Medium" if conf >= 55 else "Weak")
    strength_ru = "Сильный" if conf >= 75 else ("Средний" if conf >= 55 else "Слабый")
    return {
        "pair": pair, "price": f"{last:.{info['dec']}f}",
        "change": change, "rsi": rsi, "conf": conf,
        "direction": direction, "reasons": reasons, "cat": info["cat"], "tf": tf,
        "entry_time": now.strftime("%H:%M"),
        "entry_date": now.strftime("%d.%m.%Y"),
        "expiry": EXPIRY.get(tf, {"ru": tf, "en": tf})[lang(uid)],
        "expiry_en": EXPIRY.get(tf, {"ru": tf, "en": tf})["en"],
        "tip": get_tip(direction, uid),
        "strength": strength,
        "strength_ru": strength_ru,
    }

# ─── Генерация картинки ───────────────────────────────────────
def make_signal_image(data: dict, uid: int) -> io.BytesIO:
    W, H = 800, 480
    is_buy = data["direction"] == "buy"
    is_wait = data["direction"] == "wait"

    # Фон
    bg_color = (10, 10, 10)
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    # Цвета
    green = (34, 197, 94)
    red   = (239, 68, 68)
    gray  = (160, 160, 160)
    white = (255, 255, 255)
    accent = green if is_buy else (red if not is_wait else gray)

    # Верхняя полоса
    draw.rectangle([0, 0, W, 6], fill=accent)

    # Стрелка — рисуем вручную
    cx = W // 2
    if is_buy:
        # Зелёная стрелка вверх
        arrow_color = green
        points = [(cx, 60), (cx-70, 160), (cx-30, 160), (cx-30, 230), (cx+30, 230), (cx+30, 160), (cx+70, 160)]
    elif not is_wait:
        # Красная стрелка вниз
        arrow_color = red
        points = [(cx, 230), (cx-70, 130), (cx-30, 130), (cx-30, 60), (cx+30, 60), (cx+30, 130), (cx+70, 130)]
    else:
        arrow_color = gray
        points = None

    if points:
        draw.polygon(points, fill=arrow_color)

    # Слово BUY / SELL / WAIT
    try:
        font_big   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_med   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_label = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font_big = font_med = font_small = font_label = ImageFont.load_default()

    ln = lang(uid)
    if is_buy:
        word = "BUY" if ln == "en" else "ПОКУПКА"
    elif not is_wait:
        word = "SELL" if ln == "en" else "ПРОДАЖА"
    else:
        word = "WAIT" if ln == "en" else "ОЖИДАНИЕ"

    # Текст стрелки по центру
    bbox = draw.textbbox((0, 0), word, font=font_big)
    tw = bbox[2] - bbox[0]
    draw.text((cx - tw // 2, 248), word, fill=accent, font=font_big)

    # Разделитель
    draw.rectangle([40, 310, W - 40, 312], fill=(40, 40, 40))

    # Информация — левая колонка
    lx, rx = 50, 420
    y = 325
    dy = 32

    def row(label, value, color=white):
        draw.text((lx, y), label, fill=gray, font=font_label)
        draw.text((lx + 200, y), value, fill=color, font=font_small)

    if ln == "en":
        row("🕐 Entry Time:", f"{data['entry_time']} UTC+3")
        y += dy
        row("💱 Asset:", data["pair"])
        y += dy
        row("⏱ Duration:", data["expiry_en"])
        y += dy
        row("✅ Signal Strength:", data["strength"], accent)
        y += dy
        row("🎯 Confidence:", f"{int(data['conf'])}%", accent)
    else:
        row("🕐 Время входа:", f"{data['entry_time']} UTC+3")
        y += dy
        row("💱 Пара:", data["pair"])
        y += dy
        row("⏱ Экспирация:", data["expiry"])
        y += dy
        row("✅ Сила сигнала:", data["strength_ru"], accent)
        y += dy
        row("🎯 Уверенность:", f"{int(data['conf'])}%", accent)

    # Нижняя плашка с дисклеймером
    draw.rectangle([0, H - 36, W, H], fill=(20, 20, 20))
    disc = "For analysis only. Trading is your risk." if ln == "en" else "Только для анализа. Торговля — ваш риск."
    bbox2 = draw.textbbox((0, 0), disc, font=font_label)
    dw = bbox2[2] - bbox2[0]
    draw.text(((W - dw) // 2, H - 26), disc, fill=(100, 100, 100), font=font_label)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf

def caption_text(data: dict, uid: int) -> str:
    ln = lang(uid)
    icons = {"up": "🟢", "dn": "🔴", "nt": "⚪"}
    ind_lines = "\n".join(
        f"{icons[r['dir']]} {r['name']}: {r['value']} — {r['hint']}"
        for r in data["reasons"]
    )
    if ln == "en":
        pos = "BUY 📈" if data["direction"] == "buy" else ("SELL 📉" if data["direction"] == "sell" else "WAIT ⏸")
        text = (
            f"🕐 *Entry Time:* `{data['entry_time']} UTC+3`\n"
            f"💱 *Asset:* `{data['pair']}`\n"
            f"{'🔼' if data['direction']=='buy' else ('🔽' if data['direction']=='sell' else '▶️')} *Position:* `{pos}`\n"
            f"✅ *Signal Strength:* `{data['strength']}`\n"
            f"⏱ *Duration:* `{data['expiry_en']}`\n"
            f"🎯 *Confidence:* `{int(data['conf'])}%`\n"
            f"\n📊 *Indicators:*\n{ind_lines}\n"
            f"\n💡 _{data['tip']}_\n"
            f"\n⚠️ _For analysis only. Trading is your risk._"
        )
    else:
        pos = "ПОКУПКА 📈" if data["direction"] == "buy" else ("ПРОДАЖА 📉" if data["direction"] == "sell" else "ОЖИДАНИЕ ⏸")
        text = (
            f"🕐 *Время входа:* `{data['entry_time']} UTC+3`\n"
            f"💱 *Пара:* `{data['pair']}`\n"
            f"{'🔼' if data['direction']=='buy' else ('🔽' if data['direction']=='sell' else '▶️')} *Позиция:* `{pos}`\n"
            f"✅ *Сила сигнала:* `{data['strength_ru']}`\n"
            f"⏱ *Экспирация:* `{data['expiry']}`\n"
            f"🎯 *Уверенность:* `{int(data['conf'])}%`\n"
            f"\n📊 *Индикаторы:*\n{ind_lines}\n"
            f"\n💡 _{data['tip']}_\n"
            f"\n⚠️ _Только для анализа. Торговля — ваш риск._"
        )
    return text

# ─── Клавиатуры ───────────────────────────────────────────────
def lang_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang:ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="setlang:en"),
    ]])

def main_keyboard(uid):
    ln = lang(uid)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(T["forex"][ln], callback_data="cat:forex"),
         InlineKeyboardButton(T["otc"][ln],   callback_data="cat:otc")],
        [InlineKeyboardButton(T["crypto"][ln], callback_data="cat:crypto")],
        [InlineKeyboardButton(T["all"][ln],    callback_data="all:M5")],
        [InlineKeyboardButton(T["settings"][ln], callback_data="settings")],
    ])

def cat_keyboard(cat, uid):
    pairs = [p for p, v in PAIRS.items() if v["cat"] == cat]
    rows = []
    row = []
    for p in pairs:
        row.append(InlineKeyboardButton(p, callback_data=f"pair:{p}:M5"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t("back", uid), callback_data="back")])
    return InlineKeyboardMarkup(rows)

def tf_keyboard(pair, uid):
    rows = []
    row = []
    for tf in TIMEFRAMES:
        row.append(InlineKeyboardButton(tf, callback_data=f"pair:{pair}:{tf}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(t("back", uid), callback_data="back")])
    return InlineKeyboardMarkup(rows)

def back_keyboard(uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(t("back", uid), callback_data="back")]])

# ─── Handlers ─────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(T["welcome"]["ru"], reply_markup=lang_keyboard())

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data.startswith("setlang:"):
        USER_LANG[uid] = data.split(":")[1]
        await query.edit_message_text(t("menu_title", uid), parse_mode="Markdown",
                                      reply_markup=main_keyboard(uid))
        return

    if data == "settings":
        await query.edit_message_text(T["welcome"]["ru"], reply_markup=lang_keyboard())
        return

    if data == "back":
        # Если сообщение с фото — удаляем и отправляем новое текстовое
        try:
            await query.message.delete()
            await query.message.chat.send_message(
                t("menu_title", uid), parse_mode="Markdown", reply_markup=main_keyboard(uid)
            )
        except:
            await query.edit_message_text(t("menu_title", uid), parse_mode="Markdown",
                                          reply_markup=main_keyboard(uid))
        return

    if data.startswith("cat:"):
        cat = data.split(":")[1]
        try:
            await query.edit_message_text(t("choose_tf", uid), reply_markup=cat_keyboard(cat, uid))
        except:
            await query.message.delete()
            await query.message.chat.send_message(t("choose_tf", uid), reply_markup=cat_keyboard(cat, uid))
        return

    if data.startswith("all:"):
        tf = data.split(":")[1]
        ln = lang(uid)
        lines = [f"*📊 {'All pairs' if ln=='en' else 'Все пары'} — {tf}*\n"]
        for pair in PAIRS:
            d = analyze(pair, uid, tf)
            chg = f"+{d['change']:.2f}%" if d["change"] >= 0 else f"{d['change']:.2f}%"
            icon = "🟢" if d["direction"] == "buy" else ("🔴" if d["direction"] == "sell" else "⚪")
            sig = "CALL" if d["direction"] == "buy" else ("PUT" if d["direction"] == "sell" else "⏸")
            lines.append(f"{icon} *{pair}* — {sig} {int(d['conf'])}%")
        lines.append(f"\n⚠️ _{'For analysis only.' if ln=='en' else 'Только для анализа.'}_")
        try:
            await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=back_keyboard(uid))
        except:
            await query.message.delete()
            await query.message.chat.send_message("\n".join(lines), parse_mode="Markdown", reply_markup=back_keyboard(uid))
        return

    if data.startswith("pair:"):
        parts = data.split(":")
        tf = parts[-1]
        pair = ":".join(parts[1:-1])
        if pair not in PAIRS:
            await query.answer(t("unknown", uid))
            return

        d = analyze(pair, uid, tf)
        img_buf = make_signal_image(d, uid)
        cap = caption_text(d, uid)

        try:
            await query.message.delete()
        except:
            pass

        await query.message.chat.send_photo(
            photo=img_buf,
            caption=cap,
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
