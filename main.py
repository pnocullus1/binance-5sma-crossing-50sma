import asyncio
import aiohttp
import pandas as pd
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ACCOUNT_BALANCE = 1000
RISK_PERCENT = 2
ATR_PERIOD = 14
ATR_MULTIPLIER = 1.5

SYMBOLS = [
"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
"ADAUSDT","AVAXUSDT","LINKUSDT","DOGEUSDT","LTCUSDT",
"TRXUSDT","DOTUSDT","ATOMUSDT","NEARUSDT","APTUSDT",
"ARBUSDT","OPUSDT","INJUSDT","FILUSDT","SUIUSDT",
"RNDRUSDT","SEIUSDT","TIAUSDT","AAVEUSDT","FTMUSDT",
"GALAUSDT","ALGOUSDT","EGLDUSDT","ICPUSDT","THETAUSDT"
]

ACTIVE_TRADES = {}
STATS = {"signals":0,"tp1":0,"tp2":0,"tp3":0,"sl":0}
TODAY = datetime.utcnow().date()

# ================= FETCHING =================

async def fetch_klines(session, symbol, interval):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol":symbol,"interval":interval,"limit":150}
    async with session.get(url, params=params) as resp:
        data = await resp.json()
        df = pd.DataFrame(data)
        df["close"] = df[4].astype(float)
        df["high"] = df[2].astype(float)
        df["low"] = df[3].astype(float)
        return df

async def fetch_price(session, symbol):
    url = "https://fapi.binance.com/fapi/v1/ticker/price"
    async with session.get(url, params={"symbol":symbol}) as resp:
        data = await resp.json()
        return float(data["price"])

# ================= LOGIC =================

def calculate_atr(df):
    df["H-L"] = df["high"] - df["low"]
    df["H-PC"] = abs(df["high"] - df["close"].shift())
    df["L-PC"] = abs(df["low"] - df["close"].shift())
    df["TR"] = df[["H-L","H-PC","L-PC"]].max(axis=1)
    return df["TR"].rolling(ATR_PERIOD).mean().iloc[-1]

def sma_trend(df):
    df["SMA5"] = df["close"].rolling(5).mean()
    df["SMA50"] = df["close"].rolling(50).mean()
    return df["SMA5"].iloc[-1] > df["SMA50"].iloc[-1]

def check_cross(df):
    df["SMA5"] = df["close"].rolling(5).mean()
    df["SMA50"] = df["close"].rolling(50).mean()
    prev,last = df.iloc[-2],df.iloc[-1]

    if prev["SMA5"] < prev["SMA50"] and last["SMA5"] > last["SMA50"]:
        return "LONG"
    if prev["SMA5"] > prev["SMA50"] and last["SMA5"] < last["SMA50"]:
        return "SHORT"
    return None

def position_size(entry, sl):
    risk_amount = ACCOUNT_BALANCE * (RISK_PERCENT/100)
    return round(risk_amount / abs(entry-sl),3)

# ================= SCANNER =================

async def scan_market(app):
    global TODAY, STATS

    async with aiohttp.ClientSession() as session:
        while True:

            if datetime.utcnow().date() != TODAY:
                TODAY = datetime.utcnow().date()
                STATS = {"signals":0,"tp1":0,"tp2":0,"tp3":0,"sl":0}

            tasks = []
            for symbol in SYMBOLS:
                tasks.append(process_symbol(app, session, symbol))

            await asyncio.gather(*tasks)
            await asyncio.sleep(25)

async def process_symbol(app, session, symbol):
    try:
        df15, df1h, df4h = await asyncio.gather(
            fetch_klines(session,symbol,"15m"),
            fetch_klines(session,symbol,"1h"),
            fetch_klines(session,symbol,"4h")
        )

        direction = check_cross(df15)
        if not direction:
            return

        if direction=="LONG" and not (sma_trend(df1h) and sma_trend(df4h)):
            return
        if direction=="SHORT" and (sma_trend(df1h) or sma_trend(df4h)):
            return

        entry = df15["close"].iloc[-1]
        atr = calculate_atr(df15)
        risk = atr * ATR_MULTIPLIER

        if direction=="LONG":
            sl = entry-risk
            tp1,tp2,tp3 = entry+risk*1.5,entry+risk*2,entry+risk*3
        else:
            sl = entry+risk
            tp1,tp2,tp3 = entry-risk*1.5,entry-risk*2,entry-risk*3

        size = position_size(entry,sl)

        ACTIVE_TRADES[symbol]={
            "dir":direction,"entry":entry,"sl":sl,
            "tp1":tp1,"tp2":tp2,"tp3":tp3,"be":False
        }

        STATS["signals"]+=1

        msg=f"""
{direction} {symbol}
Entry: {round(entry,4)}
SL: {round(sl,4)}
TP1: {round(tp1,4)}
TP2: {round(tp2,4)}
TP3: {round(tp3,4)}
Size: {size}
"""
        await app.bot.send_message(chat_id=CHAT_ID,text=msg)

    except:
        pass

# ================= DASHBOARD =================

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    winrate = 0
    if STATS["signals"]>0:
        wins = STATS["tp1"]+STATS["tp2"]+STATS["tp3"]
        winrate = round((wins/STATS["signals"])*100,2)

    msg=f"""
📊 DAILY STATS

Signals: {STATS["signals"]}
TP1: {STATS["tp1"]}
TP2: {STATS["tp2"]}
TP3: {STATS["tp3"]}
SL: {STATS["sl"]}

Win Rate: {winrate}%
Active Trades: {len(ACTIVE_TRADES)}
"""
    await update.message.reply_text(msg)

# ================= START BOT =================

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("stats", stats_command))

    asyncio.create_task(scan_market(app))

    print("🚀 Ultra Fast Async Futures Engine Running...")
    await app.run_polling()

asyncio.run(main())
