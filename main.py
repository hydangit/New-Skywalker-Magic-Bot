from keep_alive import keep_alive
import ccxt
import pandas as pd
import ta
import time
import requests
from datetime import datetime

# --- Konfigurasi Telegram ---
TOKEN = 'ISI_TOKEN_TELEGRAM_KAMU'
CHAT_ID = 'ISI_CHAT_ID_KAMU'

# --- Setup Binance Futures ---
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# --- Timeframes & Threshold ---
TIMEFRAMES = ['15m', '1h', '4h']
MAX_SINYAL_PER_CYCLE = 5
AKURASI_MINIMAL = 90

def kirim_telegram(pesan):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    requests.post(url, json={'chat_id': CHAT_ID, 'text': pesan, 'parse_mode': 'Markdown'})

def analisa_sinyal(pair, tf):
    try:
        ohlcv = exchange.fetch_ohlcv(pair, tf, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        df['EMA20'] = ta.trend.ema_indicator(df['close'], window=20)
        df['EMA50'] = ta.trend.ema_indicator(df['close'], window=50)
        macd = ta.trend.macd(df['close'])
        rsi = ta.momentum.rsi(df['close'], window=14)
        obv = ta.volume.on_balance_volume(df['close'], df['volume'])

        last = df.iloc[-1]
        prev = df.iloc[-2]

        arah = None
        akurasi = 0

        if last['close'] > last['EMA20'] > last['EMA50'] and macd.macd_diff().iloc[-1] > 0 and rsi.iloc[-1] > 50:
            arah = 'LONG'
        elif last['close'] < last['EMA20'] < last['EMA50'] and macd.macd_diff().iloc[-1] < 0 and rsi.iloc[-1] < 50:
            arah = 'SHORT'

        if arah:
            akurasi += 30 if macd.macd_diff().iloc[-1] * (1 if arah == 'LONG' else -1) > 0 else 0
            akurasi += 30 if (rsi.iloc[-1] > 55 and arah == 'LONG') or (rsi.iloc[-1] < 45 and arah == 'SHORT') else 0
            akurasi += 20 if obv.iloc[-1] > obv.iloc[-2] else 0
            akurasi += 20 if last['volume'] > prev['volume'] else 0

            leverage = 30 if akurasi >= 93 else 20 if akurasi >= 91 else 10

            harga = last['close']
            entry = f"{harga * 0.998:.4f} - {harga * 1.002:.4f}" if arah == 'LONG' else f"{harga * 1.002:.4f} - {harga * 0.998:.4f}"
            tp1 = harga * (1.01 if arah == 'LONG' else 0.99)
            tp2 = harga * (1.02 if arah == 'LONG' else 0.98)
            tp3 = harga * (1.03 if arah == 'LONG' else 0.97)
            sl = harga * (0.985 if arah == 'LONG' else 1.015)

            pesan = f"""
🧨 SINYAL TERPILIH NIH BANG!
#{pair.replace('/', '')} 🔺 {arah} {leverage}x ({tf.upper()})
📊 TF: {tf.upper()}
🎯 ENTRY: `{entry}`
🎯 TP1 (Cari Aman): {tp1:.4f}
🎯 TP2 (Butuh Duit): {tp2:.4f}
🎯 TP3 (Maruk): *{tp3:.4f}*
🛑 SL: {sl:.4f}
📈 ACC: *{akurasi}%*
💬 Nih sinyal udah disaring ketat, tinggal eksekusi.
"""
            return (akurasi, pesan)
    except:
        pass
    return None

def auto_sinyal():
    pairs = [m['symbol'] for m in exchange.fetch_markets() if m['quote'] == 'USDT' and m['contractType'] == 'PERPETUAL']
    sinyal_terbaik = []

    for pair in pairs:
        for tf in TIMEFRAMES:
            hasil = analisa_sinyal(pair, tf)
            if hasil and hasil[0] >= AKURASI_MINIMAL:
                sinyal_terbaik.append(hasil)

    sinyal_terbaik.sort(reverse=True)
    for _, pesan in sinyal_terbaik[:MAX_SINYAL_PER_CYCLE]:
        kirim_telegram(pesan)

keep_alive()

while True:
    auto_sinyal()
    time.sleep(900)  # 15 menit
