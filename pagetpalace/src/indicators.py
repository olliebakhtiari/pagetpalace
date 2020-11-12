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
    data['HighLowValue'] = hlv


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
    df['ATR'] = data['true_range'].ewm(alpha=1 / periods).mean()


def append_ssma(df: pd.DataFrame, periods: int = 50, prices: str = "midClose"):
    df[f'SSMA_{periods}'] = df[prices].ewm(ignore_na=False, alpha=1.0 / periods, min_periods=0, adjust=False).mean()
