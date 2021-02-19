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


def is_candle_range_greater_than_x(candle: pd.DataFrame, value: float):
    return (float(candle['midHigh']) - float(candle['midLow'])) > value


def _adjust_if_zero(value: float) -> float:
    return value if value > 0 else 0.00001


def _get_range_of_body(prices: Dict[str, float]) -> float:
    return _adjust_if_zero(prices['o'] - prices['c'] if prices['o'] > prices['c'] else prices['c'] - prices['o'])


def _get_range_of_tail(prices: Dict[str, float]) -> float:
    return _adjust_if_zero(min(prices['o'], prices['c']) - prices['l'])


def _get_range_of_head(prices: Dict[str, float]) -> float:
    return _adjust_if_zero(prices['h'] - max(prices['o'], prices['c']))


def _get_candlestick_ranges(prices: Dict[str, float]):
    return {'body': _get_range_of_body(prices), 'head': _get_range_of_head(prices), 'tail': _get_range_of_tail(prices)}


def was_price_ascending(dataframe: pd.DataFrame,
                        idx_to_analyse: int,
                        prices: str = 'midHigh',
                        look_back: int = 2) -> bool:
    is_ascending = True
    while look_back > 0:
        if dataframe.iloc[idx_to_analyse - look_back][prices] > dataframe.iloc[idx_to_analyse - look_back + 1][prices]:
            return False
        look_back -= 1

    return is_ascending


def was_price_descending(dataframe: pd.DataFrame,
                         idx_to_analyse: int,
                         prices: str = 'midLow',
                         look_back: int = 2) -> bool:
    is_descending = True
    while look_back > 0:
        if dataframe.iloc[idx_to_analyse - look_back][prices] < dataframe.iloc[idx_to_analyse - look_back + 1][prices]:
            return False
        look_back -= 1

    return is_descending


def _is_doji_candlestick(prices: Dict[str, float]) -> bool:
    """
        In isolation, a doji candlestick is a neutral indicator that provides little information.
        Moreover, a doji is not a common occurrence; therefore, it is not a reliable tool for spotting things like
        price reversals.
    """
    return prices['o'] == prices['c']


def _is_hammer_candlestick(ranges: Dict[str, float], coeffs: Dict[str, float]) -> bool:
    is_tail_x_times_bigger_than_body = (ranges['tail'] > (coeffs['body'] * ranges['body']))
    is_head_x_times_smaller_than_tail = (ranges['head'] < (ranges['tail'] / coeffs['shadow']))

    return is_tail_x_times_bigger_than_body and is_head_x_times_smaller_than_tail


def _is_pin_candlestick(ranges: Dict[str, float], coeffs: Dict[str, float]) -> bool:
    is_head_x_times_bigger_than_body = (ranges['head'] > (coeffs['body'] * ranges['body']))
    is_tail_x_times_smaller_than_head = (ranges['tail'] < (ranges['head'] / coeffs['shadow']))

    return is_head_x_times_bigger_than_body and is_tail_x_times_smaller_than_head


def get_hammer_pin_signal_v2(dataframe: pd.DataFrame, idx_to_analyse: int, coeffs: Dict[str, float]) -> str:
    signal = ''
    candle_to_check = dataframe.iloc[idx_to_analyse]
    prices_to_check = {
        'o': float(candle_to_check['midOpen']),
        'h': float(candle_to_check['midHigh']),
        'l': float(candle_to_check['midLow']),
        'c': float(candle_to_check['midClose']),
    }
    ranges = _get_candlestick_ranges(prices_to_check)
    if _is_doji_candlestick(prices_to_check):
        signal = ''
    elif _is_hammer_candlestick(ranges, coeffs):
        signal = 'long'
    elif _is_pin_candlestick(ranges, coeffs):
        signal = 'short'

    return signal


def was_previous_green_streak(dataframe: pd.DataFrame, idx_to_analyse: int, look_back: int = 4) -> bool:
    is_green_streak = True
    while look_back > 0:
        candle = dataframe.iloc[idx_to_analyse - look_back]
        if candle['midOpen'] > candle['midClose']:
            return False
        look_back -= 1

    return is_green_streak


def was_previous_red_streak(dataframe: pd.DataFrame, idx_to_analyse: int, look_back: int = 4) -> bool:
    is_red_streak = True
    while look_back > 0:
        candle = dataframe.iloc[idx_to_analyse - look_back]
        if candle['midOpen'] < candle['midClose']:
            return False
        look_back -= 1

    return is_red_streak


def append_heikin_ashi(df: pd.DataFrame):
    opens = pd.to_numeric(df.midOpen, downcast='float')
    highs = pd.to_numeric(df.midHigh, downcast='float')
    lows = pd.to_numeric(df.midLow, downcast='float')
    closes = pd.to_numeric(df.midClose, downcast='float')
    df['HA_Close'] = ((opens + highs + lows + closes) / 4)
    ha_open = [(opens[0] + closes[0]) / 2]
    [ha_open.append((ha_open[i] + df.HA_Close.values[i]) / 2) for i in range(0, len(df) - 1)]
    df['HA_Open'] = ha_open
    df['HA_Open'] = df['HA_Open'].round(5)
    df['HA_High'] = df[['HA_Open', 'HA_Close', 'midHigh']].max(axis=1).round(5)
    df['HA_Low'] = df[['HA_Open', 'HA_Close', 'midLow']].min(axis=1).round(5)

    return df
