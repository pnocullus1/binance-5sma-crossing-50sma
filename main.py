import os
import asyncio
import aiohttp
import pandas as pd
import numpy as np
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BASE_URL = "https://fapi.binance.com"

PAIRS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","MATICUSDT",
    "DOTUSDT","LTCUSDT","TRXUSDT","ATOMUSDT","APTUSDT",
    "ARBUSDT","OPUSDT","NEARUSDT","FILUSDT","INJUSDT",
    "SUIUSDT","RUNEUSDT","FTMUSDT","GALAUSDT","PEPEUSDT",
    "AAVEUSDT","ETCUSDT","RNDRUSDT","ICPUSDT","IMXUSDT"
]

TIMEFRAMES = ["15m","1h","4h"]

RISK_PERCENT = 1
ACCOUNT_SIZE = 1000

daily_stats = {
    "signals": 0,
    "wins": 0,
    "losses": 0
}

active_trades = {}

# ===========================================

async def get_price(session, symbol):
    url = f"{BASE_URL}/fapi/v1/ticker/price?symbol={symbol}"
    async with session.get(url) as r:
        data = await r.json()
        return float(data["price"])

async def get_klines(session, symbol, interval):
    url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=100"
    async with session.get(url) as response:
        data = await response.json()
        df = pd.DataFrame(data)
        df = df.iloc[:, :6]
        df.columns = ["time","open","high","low","close","volume"]
        df["close"] = df["close"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        return df

def calculate_atr(df, period=14):
    df["prev_close"] = df["close"].shift(1)
    df["tr"] = np.maximum(
        df["high"] - df["low"],
        np.maximum(abs(df["high"] - df["prev_close"]),
                   abs(df["low"] - df["prev_close"]))
    )
    atr = df["tr"].rolling(period).mean()
    return atr.iloc[-1]

def check_sma_cross(df):
    df["SMA5"] = df["close"].rolling(5).mean()
    df["SMA50"] = df["close"].rolling(50).mean()

    if df["SMA5"].iloc[-2] < df["SMA50"].iloc[-2] and df["SMA5"].iloc[-1] > df["SMA50"].iloc[-1]:
        return "LONG"
    if df["SMA5"].iloc[-2] > df["SMA50"].iloc[-2] and df["SMA5"].iloc[-1] < df["SMA50"].iloc[-1]:
        return "SHORT"
    return None

def calculate_trade_levels(entry, atr, direction):
    sl_distance = atr * 1.5
    risk_amount = ACCOUNT_SIZE * (RISK_PERCENT / 100)
    position_size = risk_amount / sl_distance

    if direction == "LONG":
        sl = entry - sl_distance
        tp1 = entry + sl_distance
        tp2 = entry + (sl_distance * 2)
        tp3 = entry + (sl_distance * 3)
    else:
        sl = entry + sl_distance
        tp1 = entry - sl_distance
        tp2 = entry - (sl_distance * 2)
        tp3 = entry - (sl_distance * 3)

    return sl, tp1, tp2, tp3, position_size

# ================= TRADE MONITOR =================

async def monitor_trade(session, app, symbol):
    global daily_stats

    trade = active_trades[symbol]

    while symbol in active_trades:
        price = await get_price(session, symbol)

        if trade["direction"] == "LONG":
            if not trade["be"] and price >= trade["tp1"]:
                trade["be"] = True
                await app.bot.send_message(chat_id=CHAT_ID,
                    text=f"{symbol} TP1 HIT ✅ Move SL to Break Even!")

            if price >= trade["tp3"]:
                daily_stats["wins"] += 1
                await app.bot.send_message(chat_id=CHAT_ID,
                    text=f"{symbol} FULL TP HIT 🎯 WIN")
                del active_trades[symbol]
                break

            if price <= trade["sl"]:
                daily_stats["losses"] += 1
                await app.bot.send_message(chat_id=CHAT_ID,
                    text=f"{symbol} STOP LOSS HIT ❌ LOSS")
                del active_trades[symbol]
                break

        else:
            if not trade["be"] and price <= trade["tp1"]:
                trade["be"] = True
                await app.bot.send_message(chat_id=CHAT_ID,
                    text=f"{symbol} TP1 HIT ✅ Move SL to Break Even!")

            if price <= trade["tp3"]:
                daily_stats["wins"] += 1
                await app.bot.send_message(chat_id=CHAT_ID,
                    text=f"{symbol} FULL TP HIT 🎯 WIN")
                del active_trades[symbol]
                break

            if price >= trade["sl"]:
                daily_stats["losses"] += 1
                await app.bot.send_message(chat_id=CHAT_ID,
                    text=f"{symbol} STOP LOSS HIT ❌ LOSS")
                del active_trades[symbol]
                break

        await asyncio.sleep(5)

# ================= SCANNER =================

async def scanner(app):
    global daily_stats

    async with aiohttp.ClientSession() as session:
        while True:
            for pair in PAIRS:
                if pair in active_trades:
                    continue

                for tf in TIMEFRAMES:
                    df = await get_klines(session, pair, tf)
                    signal = check_sma_cross(df)

                    if signal:
                        entry = df["close"].iloc[-1]
                        atr = calculate_atr(df)
                        sl, tp1, tp2, tp3, size = calculate_trade_levels(entry, atr, signal)

                        daily_stats["signals"] += 1

                        active_trades[pair] = {
                            "direction": signal,
                            "sl": sl,
                            "tp1": tp1,
                            "tp3": tp3,
                            "be": False
                        }

                        await app.bot.send_message(chat_id=CHAT_ID, text=f"""
{pair} | {tf}
Signal: {signal}
Entry: {entry:.4f}
SL: {sl:.4f}
TP1: {tp1:.4f}
TP3: {tp3:.4f}
Size: {size:.4f}
""")

                        asyncio.create_task(monitor_trade(session, app, pair))

            await asyncio.sleep(30)

# ================= DASHBOARD =================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = f"""
📊 Daily Stats
Signals: {daily_stats['signals']}
Wins: {daily_stats['wins']}
Losses: {daily_stats['losses']}
"""
    await update.message.reply_text(msg)

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global daily_stats
    daily_stats = {"signals":0,"wins":0,"losses":0}
    await update.message.reply_text("Stats reset.")

# ================= MAIN =================

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("reset", reset))

    asyncio.create_task(scanner(app))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
