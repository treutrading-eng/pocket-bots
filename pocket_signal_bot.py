"""
Pocket Option — Signal Bot для Telegram
Запуск: python pocket_signal_bot.py
"""

import os
import logging
import random
import math
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

# ─── Настройки ────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")   # Вставь токен от @BotFather
ADMIN_ID   = None                # Опционально: твой Telegram user_id

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)

# ─── Пары и параметры ─────────────────────────────────────────
PAIRS = {
    "EUR/USD": {"base": 1.0842, "vol": 0.0008, "dec": 5},
    "GBP/USD": {"base": 1.2714, "vol": 0.0012, "dec": 5},
    "USD/JPY": {"base": 157.42, "vol": 0.15,   "dec": 3},
    "BTC/USD": {"base": 67540,  "vol": 450,     "dec": 1},
    "ETH/USD": {"base": 3521,   "vol": 28,      "dec": 2},
    "AUD/USD": {"base": 0.6634, "vol": 0.0007,  "dec": 5},
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

# ─── Расчёт RSI ───────────────────────────────────────────────
def calc_rsi(closes: list[float], period: int = 14) -> float:
    gains, losses = [], []
    for i in range(1, period + 1):
        d = closes[-period + i] - closes[-period + i - 1]
        (gains if d > 0 else losses).append(abs(d))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period or 1e-9
    return 100 - 100 / (1 + avg_g / avg_l)

# ─── Основной анализ ──────────────────────────────────────────
def analyze(pair: str) -> dict:
    info = PAIRS[pair]
    candles = gen_candles(info["base"], info["vol"])
    closes  = [c["c"] for c in candles]
    n = len(closes)

    rsi    = calc_rsi(closes)
    ma20   = sum(closes[-20:]) / 20
    ma50   = sum(closes[-50:]) / 50
    macd   = sum(closes[-12:]) / 12 - sum(closes[-26:]) / 26
    last   = closes[-1]
    prev   = closes[-2]
    change = (last - prev) / prev * 100

    # Направление каждого индикатора
    reasons = [
        {
            "name":  "RSI (14)",
            "value": f"{rsi:.0f}",
            "dir":   "up" if rsi < 45 else ("dn" if rsi > 60 else "nt"),
            "hint":  "Перепродан" if rsi < 45 else ("Перекуплен" if rsi > 60 else "Нейтрально"),
        },
        {
            "name":  "MA20 vs MA50",
            "value": f"{ma20:.{info['dec']}f} / {ma50:.{info['dec']}f}",
            "dir":   "up" if ma20 > ma50 else ("dn" if ma20 < ma50 else "nt"),
            "hint":  "Бычий тренд" if ma20 > ma50 else ("Медвежий тренд" if ma20 < ma50 else "Боковик"),
        },
        {
            "name":  "MACD",
            "value": f"{macd:+.5f}",
            "dir":   "up" if macd > 0 else ("dn" if macd < 0 else "nt"),
            "hint":  "Бычье пересечение" if macd > 0 else "Медвежье пересечение",
        },
        {
            "name":  "Свеча",
            "value": "Бычья" if last > prev else "Медвежья",
            "dir":   "up" if last > prev else "dn",
            "hint":  "Закрытие выше" if last > prev else "Закрытие ниже",
        },
    ]

    score = sum(1 if r["dir"] == "up" else (-1 if r["dir"] == "dn" else 0) for r in reasons)
    conf  = min(95, max(35, 50 + score * 12 + random.uniform(-5, 5)))
    sig   = "CALL 📈" if score >= 2 else ("PUT 📉" if score <= -2 else "ОЖИДАНИЕ ⏸")
    direction = "buy" if score >= 2 else ("sell" if score <= -2 else "wait")

    return {
        "pair":      pair,
        "price":     f"{last:.{info['dec']}f}",
        "change":    change,
        "rsi":       rsi,
        "conf":      conf,
        "signal":    sig,
        "direction": direction,
        "reasons":   reasons,
    }

# ─── Форматирование сообщения ─────────────────────────────────
def format_signal(data: dict, tf: str) -> str:
    d = data
    arrow = "🟢" if d["direction"] == "buy" else ("🔴" if d["direction"] == "sell" else "⚪")
    chg_sign = "+" if d["change"] >= 0 else ""

    bars = int(d["conf"] / 10)
    conf_bar = "█" * bars + "░" * (10 - bars)

    lines = [
        f"{arrow} *{d['pair']}* | {tf}",
        f"Цена: `{d['price']}` ({chg_sign}{d['change']:.2f}%)",
        f"Сигнал: *{d['signal']}*",
        f"Уверенность: `{conf_bar}` {d['conf']:.0f}%",
        "",
        "📊 *Индикаторы:*",
    ]

    icons = {"up": "🟢", "dn": "🔴", "nt": "⚪"}
    for r in d["reasons"]:
        lines.append(f"{icons[r['dir']]} {r['name']}: `{r['value']}` — {r['hint']}")

    lines += [
        "",
        "⚠️ _Сигналы носят аналитический характер. Торговля — ваш риск._",
    ]
    return "\n".join(lines)

# ─── Клавиатура ───────────────────────────────────────────────
def main_keyboard() -> InlineKeyboardMarkup:
    pairs_btns = [
        [
            InlineKeyboardButton("EUR/USD", callback_data="pair:EUR/USD:M5"),
            InlineKeyboardButton("GBP/USD", callback_data="pair:GBP/USD:M5"),
            InlineKeyboardButton("USD/JPY", callback_data="pair:USD/JPY:M5"),
        ],
        [
            InlineKeyboardButton("BTC/USD", callback_data="pair:BTC/USD:M5"),
            InlineKeyboardButton("ETH/USD", callback_data="pair:ETH/USD:M5"),
            InlineKeyboardButton("AUD/USD", callback_data="pair:AUD/USD:M5"),
        ],
        [
            InlineKeyboardButton("🔄 Все пары (M5)", callback_data="all:M5"),
        ],
    ]
    return InlineKeyboardMarkup(pairs_btns)

def tf_keyboard(pair: str) -> InlineKeyboardMarkup:
    btns = [
        [InlineKeyboardButton(tf, callback_data=f"pair:{pair}:{tf}") for tf in TIMEFRAMES]
    ]
    btns.append([InlineKeyboardButton("◀ Назад", callback_data="back")])
    return InlineKeyboardMarkup(btns)

# ─── Handlers ─────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Pocket Option Signal Bot*\n\nВыбери торговую пару для анализа:",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )

async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Быстрый сигнал: /signal EURUSD M5"""
    args = ctx.args
    pair = (args[0].upper().replace("USD", "/USD").replace("EUR/", "EUR/")
            if args else "EUR/USD")
    if "/" not in pair:
        pair = pair[:3] + "/" + pair[3:]
    tf = args[1].upper() if len(args) > 1 else "M5"
    if pair not in PAIRS:
        await update.message.reply_text("❌ Неизвестная пара. Пример: /signal EURUSD M5")
        return
    data = analyze(pair)
    await update.message.reply_text(
        format_signal(data, tf),
        parse_mode="Markdown",
        reply_markup=tf_keyboard(pair),
    )

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back":
        await query.edit_message_text(
            "Выбери торговую пару:",
            reply_markup=main_keyboard(),
        )
        return

    if query.data.startswith("all:"):
        tf = query.data.split(":")[1]
        lines = [f"📊 *Все пары — {tf}*\n"]
        for pair in PAIRS:
            d = analyze(pair)
            chg = f"+{d['change']:.2f}%" if d["change"] >= 0 else f"{d['change']:.2f}%"
            lines.append(f"{'🟢' if d['direction']=='buy' else ('🔴' if d['direction']=='sell' else '⚪')} "
                         f"*{pair}* `{d['price']}` ({chg}) — {d['signal']} {d['conf']:.0f}%")
        lines.append("\n⚠️ _Только для анализа._")
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀ Назад", callback_data="back")]
            ]),
        )
        return

    if query.data.startswith("pair:"):
        _, pair, tf = query.data.split(":")
        data = analyze(pair)
        await query.edit_message_text(
            format_signal(data, tf),
            parse_mode="Markdown",
            reply_markup=tf_keyboard(pair),
        )

# ─── Запуск ───────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.add_handler(CallbackQueryHandler(on_callback))

    print("✅ Бот запущен. Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
