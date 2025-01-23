# Add the list of symbols here
symbols = []  # List of symbols to fetch data for

# Rest of the code remains exactly the same
import requests
import numpy as np
import pandas as pd
import time
from datetime import datetime

# Replace with your actual CryptoCompare API key
api_key = ''

# Replace with your Telegram bot token and chat ID
bot_token = ''
chat_id = ''

# Dictionary to store active and inactive alerts
active_alerts = {
}  # Format: {(chat_id, symbol, timeframe): (threshold, direction, type)}
inactive_alerts = {
}  # Format: {(chat_id, symbol, timeframe): (threshold, direction, type)}

# Track bot start time for uptime calculation
start_time = time.time()


# Function to calculate RSI using TradingView methodology
def rsi_tradingview(ohlc: pd.DataFrame,
                    period: int = 14,
                    round_rsi: bool = True):
    delta = ohlc["close"].diff()
    up = delta.copy()
    up[up < 0] = 0
    up = pd.Series.ewm(up, alpha=1 / period).mean()
    down = delta.copy()
    down[down > 0] = 0
    down *= -1
    down = pd.Series.ewm(down, alpha=1 / period).mean()
    rsi = np.where(up == 0, 0,
                   np.where(down == 0, 100, 100 - (100 / (1 + up / down))))
    return np.round(rsi, 2) if round_rsi else rsi


# Function to calculate Stochastic RSI using TradingView methodology
def stoch_rsi_tradingview(ohlc: pd.DataFrame, period=14, smoothK=3, smoothD=3):
    rsi = rsi_tradingview(ohlc, period=period, round_rsi=False)
    rsi = pd.Series(rsi)
    stochrsi = (rsi - rsi.rolling(period).min()) / (rsi.rolling(period).max() -
                                                    rsi.rolling(period).min())
    stochrsi_K = stochrsi.rolling(smoothK).mean()
    stochrsi_D = stochrsi_K.rolling(smoothD).mean()
    return round(stochrsi_K * 100, 2)  # Return only the %K values


# Function to fetch data and calculate Stochastic RSI for a given symbol and time frame
def get_stoch_rsi(symbol, timeframe):
    if timeframe == "1D":
        url = f'https://min-api.cryptocompare.com/data/histoday?fsym={symbol}&tsym=USDT&limit=100&api_key={api_key}&e=Kucoin'
    elif timeframe == "1W":
        url = f'https://min-api.cryptocompare.com/data/histoday?fsym={symbol}&tsym=USDT&limit=700&api_key={api_key}&e=Kucoin'
    elif timeframe == "4H":
        url = f'https://min-api.cryptocompare.com/data/histohour?fsym={symbol}&tsym=USDT&limit=100&api_key={api_key}&e=Kucoin'
    elif timeframe == "1H":
        url = f'https://min-api.cryptocompare.com/data/histohour?fsym={symbol}&tsym=USDT&limit=200&api_key={api_key}&e=Kucoin'
    elif timeframe == "15M":
        url = f'https://min-api.cryptocompare.com/data/histominute?fsym={symbol}&tsym=USDT&limit=200&api_key={api_key}&e=Kucoin'
    else:
        return None  # Invalid timeframe

    response = requests.get(url)
    data = response.json()
    if 'Data' in data:
        ohlc = pd.DataFrame(data['Data'])
        stochrsi_K = stoch_rsi_tradingview(ohlc,
                                           period=14,
                                           smoothK=3,
                                           smoothD=3)
        return stochrsi_K.iloc[-1]  # Return the latest %K value
    else:
        return None  # Return None if data fetching fails


# Function to get the current price of a symbol
def get_current_price(symbol):
    url = f'https://min-api.cryptocompare.com/data/price?fsym={symbol}&tsyms=USDT&api_key={api_key}'
    response = requests.get(url)
    data = response.json()
    return data.get('USDT')


# Function to send a message via Telegram
def send_telegram_message(chat_id, message):
    telegram_url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    payload = {'chat_id': chat_id, 'text': message}
    response = requests.post(telegram_url, data=payload)
    if response.status_code == 200:
        print("Message sent to Telegram successfully!")
    else:
        print("Failed to send message to Telegram:", response.text)


# Function to handle Telegram commands
def handle_telegram_commands():
    offset = None
    while True:
        # Fetch updates from Telegram
        updates_url = f'https://api.telegram.org/bot{bot_token}/getUpdates'
        params = {'offset': offset, 'timeout': 30}  # Long polling
        response = requests.get(updates_url, params=params)
        updates = response.json()
        if updates.get('ok'):
            for update in updates['result']:
                offset = update[
                    'update_id'] + 1  # Update offset to avoid processing the same update again
                if 'message' in update and 'text' in update['message']:
                    chat_id = update['message']['chat']['id']
                    text = update['message']['text']

                    # Handle /stochrsi command
                    if text.startswith('/stochrsi'):
                        parts = text.split(' ')
                        if len(parts) == 3:
                            symbol = parts[1]
                            timeframe = parts[2]
                            stochrsi_K = get_stoch_rsi(symbol, timeframe)
                            if stochrsi_K is not None:
                                response_message = f"{symbol} Stochastic RSI %K value for {timeframe} timeframe: {stochrsi_K:.2f}"
                            else:
                                response_message = f"Error fetching data for {symbol} in {timeframe} timeframe."
                        elif len(parts) == 2:  # Only timeframe is provided
                            timeframe = parts[1]
                            below_50 = [
                            ]  # Symbols with Stochastic RSI below 50
                            above_50 = [
                            ]  # Symbols with Stochastic RSI equal to or above 50

                            for symbol in symbols:
                                stochrsi_K = get_stoch_rsi(symbol, timeframe)
                                if stochrsi_K is not None:
                                    if stochrsi_K < 50:
                                        below_50.append(
                                            f"{symbol}: {stochrsi_K:.2f}")
                                    else:
                                        above_50.append(
                                            f"{symbol}: {stochrsi_K:.2f}")
                                else:
                                    below_50.append(
                                        f"{symbol}: Error fetching data")

                            # Build the response message
                            response_message = "Stochastic RSI Values:\n"
                            response_message += "\n**Symbols below 50:**\n"
                            response_message += "\n".join(
                                below_50
                            ) if below_50 else "No symbols below 50.\n"
                            response_message += "\n\n**Symbols equal to or above 50:**\n"
                            response_message += "\n".join(
                                above_50
                            ) if above_50 else "No symbols above 50.\n"
                        else:
                            response_message = "Invalid command format. Use /stochrsi <symbol> <timeframe> or /stochrsi <timeframe>."
                        send_telegram_message(chat_id, response_message)

                    # Handle /setalert command (existing functionality)
                    elif text.startswith('/setalert'):
                        parts = text.split(' ')
                        if len(parts) == 5:
                            symbol = parts[1]
                            timeframe = parts[2]
                            threshold = float(parts[3])
                            direction = parts[4].lower()
                            if direction in ["below", "above"]:
                                active_alerts[(chat_id, symbol,
                                               timeframe)] = (threshold,
                                                              direction,
                                                              "stoch_rsi")
                                response_message = f"Stochastic RSI alert set for {symbol} in {timeframe} timeframe: %K {direction} {threshold}."
                            else:
                                response_message = "Invalid direction. Use 'below' or 'above'."
                        else:
                            response_message = "Invalid command format. Use /setalert <symbol> <timeframe> <threshold> <direction>."
                        send_telegram_message(chat_id, response_message)

                    # Handle /setpricealert command (existing functionality)
                    elif text.startswith('/setpricealert'):
                        parts = text.split(' ')
                        if len(parts) == 4:
                            symbol = parts[1]
                            threshold = float(parts[2])
                            direction = parts[3].lower()
                            if direction in ["below", "above"]:
                                active_alerts[(chat_id, symbol,
                                               "price")] = (threshold,
                                                            direction, "price")
                                response_message = f"Price alert set for {symbol}: {direction} {threshold}."
                            else:
                                response_message = "Invalid direction. Use 'below' or 'above'."
                        else:
                            response_message = "Invalid command format. Use /setpricealert <symbol> <threshold> <direction>."
                        send_telegram_message(chat_id, response_message)

                    # Handle /clearalerts command (existing functionality)
                    elif text == '/clearalerts':
                        for (alert_chat_id, symbol,
                             timeframe) in list(active_alerts.keys()):
                            if alert_chat_id == chat_id:
                                inactive_alerts[(
                                    chat_id, symbol,
                                    timeframe)] = active_alerts.pop(
                                        (chat_id, symbol, timeframe))
                        send_telegram_message(
                            chat_id,
                            "All your alerts have been cleared and moved to inactive alerts."
                        )

                    # Handle /listalerts command (existing functionality)
                    elif text == '/listalerts':
                        active_stoch_rsi_alerts = []
                        active_price_alerts = []
                        inactive_stoch_rsi_alerts = []
                        inactive_price_alerts = []

                        for (alert_chat_id, symbol,
                             timeframe), (threshold, direction,
                                          alert_type) in active_alerts.items():
                            if alert_chat_id == chat_id:
                                if alert_type == "stoch_rsi":
                                    active_stoch_rsi_alerts.append(
                                        f"{symbol} {timeframe}: %K {direction} {threshold}"
                                    )
                                elif alert_type == "price":
                                    active_price_alerts.append(
                                        f"{symbol}: Price {direction} {threshold}"
                                    )

                        for (alert_chat_id, symbol, timeframe), (
                                threshold, direction,
                                alert_type) in inactive_alerts.items():
                            if alert_chat_id == chat_id:
                                if alert_type == "stoch_rsi":
                                    inactive_stoch_rsi_alerts.append(
                                        f"{symbol} {timeframe}: %K {direction} {threshold}"
                                    )
                                elif alert_type == "price":
                                    inactive_price_alerts.append(
                                        f"{symbol}: Price {direction} {threshold}"
                                    )

                        response_message = "Active Alerts:\n"
                        if active_stoch_rsi_alerts:
                            response_message += "Stochastic RSI Alerts:\n" + "\n".join(
                                active_stoch_rsi_alerts) + "\n"
                        if active_price_alerts:
                            response_message += "Price Alerts:\n" + "\n".join(
                                active_price_alerts) + "\n"
                        if not active_stoch_rsi_alerts and not active_price_alerts:
                            response_message += "No active alerts.\n"

                        response_message += "\nInactive Alerts:\n"
                        if inactive_stoch_rsi_alerts:
                            response_message += "Stochastic RSI Alerts:\n" + "\n".join(
                                inactive_stoch_rsi_alerts) + "\n"
                        if inactive_price_alerts:
                            response_message += "Price Alerts:\n" + "\n".join(
                                inactive_price_alerts) + "\n"
                        if not inactive_stoch_rsi_alerts and not inactive_price_alerts:
                            response_message += "No inactive alerts.\n"

                        send_telegram_message(chat_id, response_message)

                    # Handle /status command (existing functionality)
                    elif text == '/status':
                        active_count = len([
                            key for key in active_alerts.keys()
                            if key[0] == chat_id
                        ])
                        inactive_count = len([
                            key for key in inactive_alerts.keys()
                            if key[0] == chat_id
                        ])
                        uptime = time.strftime(
                            '%H:%M:%S', time.gmtime(time.time() - start_time))
                        status_message = (
                            f"Bot status:\n"
                            f"Active alerts: {active_count}\n"
                            f"Inactive alerts: {inactive_count}\n"
                            f"Uptime: {uptime}")
                        send_telegram_message(chat_id, status_message)

                    # Handle /start command (existing functionality)
                    elif text == '/start':
                        send_telegram_message(
                            chat_id,
                            "Welcome! Use /stochrsi <symbol> <timeframe> to get the Stochastic RSI %K values for a specific coin. Available timeframes: 1D, 4H, 1H, 15M, 1W.\n"
                            "Use /setalert <symbol> <timeframe> <threshold> <direction> to set a Stochastic RSI alert. Example: /setalert BTC 1H 20 below.\n"
                            "Use /setpricealert <symbol> <threshold> <direction> to set a price alert. Example: /setpricealert BTC 30000 below.\n"
                            "Use /clearalerts to clear all your alerts.\n"
                            "Use /listalerts to view active and inactive alerts.\n"
                            "Use /status to check the bot's status.\n")

                    # Handle unknown commands
                    else:
                        send_telegram_message(
                            chat_id,
                            "Unknown command. Use /stochrsi <symbol> <timeframe> to get the Stochastic RSI %K values for a specific coin. Available timeframes: 1D, 4H, 1H, 15M, 1W.\n"
                            "Use /setalert <symbol> <timeframe> <threshold> <direction> to set a Stochastic RSI alert.\n"
                            "Use /setpricealert <symbol> <threshold> <direction> to set a price alert.\n"
                            "Use /clearalerts to clear all your alerts.\n"
                            "Use /listalerts to view active and inactive alerts.\n"
                            "Use /status to check the bot's status.\n")

        # Check alerts (existing functionality)
        for (alert_chat_id, symbol,
             timeframe), (threshold, direction,
                          alert_type) in list(active_alerts.items()):
            if alert_type == "stoch_rsi":
                stochrsi_K = get_stoch_rsi(symbol, timeframe)
                if stochrsi_K is not None:
                    if (direction == "below" and stochrsi_K < threshold) or (
                            direction == "above" and stochrsi_K > threshold):
                        alert_message = f"Alert! {symbol} Stochastic RSI %K in {timeframe} timeframe is {direction} {threshold}: {stochrsi_K:.2f}"
                        send_telegram_message(alert_chat_id, alert_message)
                        inactive_alerts[(alert_chat_id, symbol,
                                         timeframe)] = active_alerts.pop(
                                             (alert_chat_id, symbol,
                                              timeframe))
            elif alert_type == "price":
                current_price = get_current_price(symbol)
                if current_price is not None:
                    if (direction == "below" and current_price
                            < threshold) or (direction == "above"
                                             and current_price > threshold):
                        alert_message = f"Alert! {symbol} price is {direction} {threshold}: {current_price:.2f}"
                        send_telegram_message(alert_chat_id, alert_message)
                        inactive_alerts[(alert_chat_id, symbol,
                                         timeframe)] = active_alerts.pop(
                                             (alert_chat_id, symbol,
                                              timeframe))

        time.sleep(1)  # Wait before polling again


# Start the bot
if __name__ == '__main__':
    print("Bot is running...")
    handle_telegram_commands()
