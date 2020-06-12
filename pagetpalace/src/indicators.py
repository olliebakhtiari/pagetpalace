# Local.
from typing import Union

# Third-party.
import pandas as pd


def get_ssl_value(df: pd.DataFrame, prices: str = 'mid') -> Union[int, None]:
    close = df[f'{prices}Close'].apply(pd.to_numeric).iloc[-1]
    if close > df[f'{prices}High'].apply(pd.to_numeric).mean():
        return 1
    if close < df[f'{prices}Low'].apply(pd.to_numeric).mean():
        return -1


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
