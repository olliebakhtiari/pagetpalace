# Python standard.
from typing import Dict

# Third-party.
import pandas as pd
import numpy as np


def ssl_channel(data: pd.DataFrame, prices: str = 'mid', periods: int = 20) -> np.ndarray:
    close_prices = data[f'{prices}Close'].apply(pd.to_numeric).reset_index(drop=True)
    high_sma = data[f'{prices}High'].apply(pd.to_numeric).rolling(window=periods).mean()
    low_sma = data[f'{prices}Low'].apply(pd.to_numeric).rolling(window=periods).mean()
    hi_lo_vals = np.array([0 for _ in range(len(close_prices))])
    for i in range(len(high_sma)):
        if close_prices[i] > high_sma[i]:
            hi_lo_vals[i] = 1
        elif close_prices[i] < low_sma[i]:
            hi_lo_vals[i] = -1
        else:
            hi_lo_vals[i] = hi_lo_vals[i - 1]

    return hi_lo_vals


def append_ssl_channel(data: pd.DataFrame, periods: int = 20):
    hlv = ssl_channel(data, periods=periods)
    data[f'HighLowValue_{periods}_period'] = hlv


def append_average_true_range(df: pd.DataFrame, prices: str = 'mid', periods: int = 14):
    data = df.copy()
    data.reset_index(drop=True)
    high = data[f'{prices}High'].apply(pd.to_numeric)
    low = data[f'{prices}Low'].apply(pd.to_numeric)
    close = data[f'{prices}Close'].apply(pd.to_numeric)
    data['tr0'] = abs(high - low)
    data['tr1'] = abs(high - close.shift())
    data['tr2'] = abs(low - close.shift())
    data['true_range'] = data[['tr0', 'tr1', 'tr2']].max(axis=1)
    df[f'ATR_{periods}'] = data['true_range'].ewm(alpha=1 / periods).mean()


def append_ssma(df: pd.DataFrame, periods: int = 50, prices: str = "midClose"):
    df[f'SSMA_{periods}'] = df[prices].ewm(ignore_na=False, alpha=1.0 / periods, min_periods=0, adjust=False).mean()


def is_long_green_hammer(prices: Dict[str, float], body_coeff: float, head_tail_coeff: float) -> bool:
    return (prices['o'] - prices['l'] > (body_coeff*(prices['c'] - prices['o']))) \
            and ((head_tail_coeff*(prices['h'] - prices['c'])) < prices['o'] - prices['l'])


def is_long_red_hammer(prices: Dict[str, float], body_coeff: float, head_tail_coeff: float) -> bool:
    return (prices['c'] - prices['l'] > (body_coeff*(prices['o'] - prices['c']))) \
           and ((head_tail_coeff*(prices['h'] - prices['o'])) < prices['c'] - prices['l'])


def is_short_green_pin(prices: Dict[str, float], body_coeff: float, head_tail_coeff: float) -> bool:
    return (prices['h'] - prices['c'] > (body_coeff*(prices['c'] - prices['o']))) \
           and ((head_tail_coeff*(prices['o'] - prices['l'])) < prices['h'] - prices['c'])


def is_short_red_pin(prices: Dict[str, float], body_coeff: float, head_tail_coeff: float) -> bool:
    return (prices['h'] - prices['o'] > (body_coeff*(prices['o'] - prices['c']))) \
           and ((head_tail_coeff*(prices['c'] - prices['l'])) < prices['h'] - prices['o'])


def get_hammer_pin_signal(candle: pd.DataFrame, body_coeff: float, head_tail_coeff: float) -> str:
    signal = ''
    prices = {
        'o': float(candle['midOpen']),
        'h': float(candle['midHigh']),
        'l': float(candle['midLow']),
        'c': float(candle['midClose']),
    }
    if prices['c'] > prices['o']:

        # Green candle
        if is_long_green_hammer(prices, body_coeff, head_tail_coeff):
            signal = 'long'
        elif is_short_green_pin(prices, body_coeff, head_tail_coeff):
            signal = 'short'
    else:

        # Red candle
        if is_long_red_hammer(prices, body_coeff, head_tail_coeff):
            signal = 'long'
        elif is_short_red_pin(prices, body_coeff, head_tail_coeff):
            signal = 'short'

    return signal
