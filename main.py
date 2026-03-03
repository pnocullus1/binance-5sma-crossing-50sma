import requests
import pandas as pd
import time
import os
from telegram import Bot

# ==========================
# TELEGRAM SETTINGS (Replit Secrets)
# ==========================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Your Telegram bot token
CHAT_ID = os.getenv("CHAT_ID")      # Your Telegram chat ID

# ==========================
# BOT SETTINGS
# ==========================
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
TIMEFRAMES = ["1", "5", "15", "60"]  # in minutes
RSI_PERIOD = 14
RSI_BULL = 50
RSI_BEAR = 50

bot = Bot(token=BOT_TOKEN)
LAST_SIGNAL = {}  # To prevent duplicate alerts

# ==========================
# FUNCTIONS
# ==========================
def get_klines_binance(symbol, interval, limit=60, market_type="spot"):
    if market_type == "spot":
        url = "https://api.binance.com/api/v3/klines"
    elif market_type == "futures":
        url = "https://fapi.binance.com/fapi/v1/klines"
    else:
        raise ValueError("Invalid market_type")

    params = {"symbol": symbol, "interval": interval+"m", "limit": limit}
    response = requests.get(url, params=params)
    data = response.json()
    df = pd.DataFrame(data, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_asset_volume","num_trades",
        "taker_buy_base","taker_buy_quote","ignore"
    ])
    df["close"] = df["close"].astype(float)
    return df

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def check_cross(df):
    df["SMA5"] = df["close"].rolling(5).mean()
    df["SMA50"] = df["close"].rolling(50).mean()
    df["RSI"] = compute_rsi(df["close"], RSI_PERIOD)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    if prev["SMA5"] < prev["SMA50"] and last["SMA5"] > last["SMA50"] and last["RSI"] > RSI_BULL:
        return "bullish", last["SMA5"], last["SMA50"], last["RSI"]

    if prev["SMA5"] > prev["SMA50"] and last["SMA5"] < last["SMA50"] and last["RSI"] < RSI_BEAR:
        return "bearish", last["SMA5"], last["SMA50"], last["RSI"]

    return None, None, None, None

# ==========================
# MAIN LOOP
# ==========================
print("✅ Binance Multi-Coin Multi-Timeframe Bot Started...")

while True:
    try:
        for symbol in SYMBOLS:
            for market, market_name in [("spot","SPOT"), ("futures","USDT-Futures")]:
                for tf in TIMEFRAMES:
                    df = get_klines_binance(symbol, tf, market_type=market)
                    signal, sma5, sma50, rsi = check_cross(df)
                    key = f"{symbol}-{market}-{tf}"

                    if signal and LAST_SIGNAL.get(key) != signal:
                        msg = f"{'🚀 BULLISH' if signal=='bullish' else '🔻 BEARISH'} CROSS ALERT\n"
                        msg += f"Symbol: {symbol}\nMarket: {market_name}\nTimeframe: {tf}m\n"
                        msg += f"SMA5: {sma5:.2f}\nSMA50: {sma50:.2f}\nRSI: {rsi:.2f}"
                        bot.send_message(chat_id=CHAT_ID, text=msg)
                        LAST_SIGNAL[key] = signal

        time.sleep(60)  # Check every minute

    except Exception as e:
        print("Error:", e)
        time.sleep(30)
