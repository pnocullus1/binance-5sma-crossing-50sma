import os
import asyncio
import aiohttp
import pandas as pd
from telegram import Bot

# ================= CONFIG =================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=TELEGRAM_TOKEN)

BASE_URL = "https://fapi.binance.com"

PAIRS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
    "ADAUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","MATICUSDT",
    "DOTUSDT","LTCUSDT","TRXUSDT","ATOMUSDT","APTUSDT",
    "ARBUSDT","OPUSDT","NEARUSDT","FILUSDT","INJUSDT",
    "SUIUSDT","RUNEUSDT","FTMUSDT","GALAUSDT","PEPEUSDT",
    "AAVEUSDT","ETCUSDT","RNDRUSDT","ICPUSDT","IMXUSDT"
]

TIMEFRAMES = ["15m", "1h", "4h"]

# ===========================================

async def get_klines(session, symbol, interval):
    url = f"{BASE_URL}/fapi/v1/klines?symbol={symbol}&interval={interval}&limit=100"
    async with session.get(url) as response:
        data = await response.json()
        df = pd.DataFrame(data)
        df = df.iloc[:, :6]
        df.columns = ["time","open","high","low","close","volume"]
        df["close"] = df["close"].astype(float)
        return df

def check_sma_cross(df):
    df["SMA5"] = df["close"].rolling(5).mean()
    df["SMA50"] = df["close"].rolling(50).mean()

    if df["SMA5"].iloc[-2] < df["SMA50"].iloc[-2] and df["SMA5"].iloc[-1] > df["SMA50"].iloc[-1]:
        return "BULLISH CROSS 🚀"
    if df["SMA5"].iloc[-2] > df["SMA50"].iloc[-2] and df["SMA5"].iloc[-1] < df["SMA50"].iloc[-1]:
        return "BEARISH CROSS 🔻"
    return None

async def scan_pair(session, symbol):
    for tf in TIMEFRAMES:
        try:
            df = await get_klines(session, symbol, tf)
            signal = check_sma_cross(df)
            if signal:
                message = f"{symbol} | {tf}\n{signal}"
                await bot.send_message(chat_id=CHAT_ID, text=message)
        except Exception as e:
            print(f"Error {symbol} {tf}: {e}")

async def scanner():
    print("🚀 Futures SMA 5/50 Scanner Running...")
    async with aiohttp.ClientSession() as session:
        while True:
            tasks = []
            for pair in PAIRS:
                tasks.append(scan_pair(session, pair))
            await asyncio.gather(*tasks)
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(scanner())
