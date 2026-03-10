import os
import asyncio
import pandas as pd
from binance.client import Client
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

client = Client()

pairs = [
"BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT",
"ADAUSDT","DOGEUSDT","AVAXUSDT","DOTUSDT","LINKUSDT",
"MATICUSDT","LTCUSDT","BCHUSDT","ATOMUSDT","FILUSDT",
"APTUSDT","ARBUSDT","OPUSDT","INJUSDT","NEARUSDT",
"SUIUSDT","SEIUSDT","RUNEUSDT","AAVEUSDT","UNIUSDT",
"ALGOUSDT","FTMUSDT","SANDUSDT","MANAUSDT","GALAUSDT"
