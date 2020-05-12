# Python standard.
import datetime
from typing import List

# Third-party.
import pandas as pd
import numpy as np


def get_url_list_from_file(file_path: str) -> List[str]:
    url_list = []
    with open(file_path, 'r') as file:
        for url in file.read().split():
            url_list.append(url)

    return url_list


def fxcm_date_parser(d):
    date, time = d.split()
    day, month, year = map(int, date.split('.'))
    hour, minutes, seconds = map(int, time.split('.')[0].split(':'))

    return datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minutes, second=seconds)


def read_fxcm_data(time_frames: list) -> dict:
    tf_dict = {}
    for tf in time_frames:
        tf_dict[tf] = pd.read_csv(
            filepath_or_buffer=f'/Users/oliver/Documents/forex_trader/data/fxcm/GBPUSD_Candlestick_{tf}_BID.csv',
            sep=',',
            index_col=0,
            parse_dates=[0],
            date_parser=lambda d: fxcm_date_parser(d),
            dtype={
                "Open": np.float32,
                "High": np.float32,
                "Low": np.float32,
                "Close": np.float32,
                "Volume": np.float32,
            },
            engine='c',
            infer_datetime_format=True,
            cache_dates=True,
        )

    return tf_dict


def read_oanda_data(file_path: str) -> pd.DataFrame:
    return pd.read_csv(
        filepath_or_buffer=file_path,
        sep=',',
        index_col='datetime',
        parse_dates=['datetime'],
        dtype={
            "idx": np.int64,
            "volume": np.int32,
            "askOpen": np.float32,
            "askHigh": np.float32,
            "askLow": np.float32,
            "askClose": np.float32,
            "bidOpen": np.float32,
            "bidHigh": np.float32,
            "bidLow": np.float32,
            "bidClose": np.float32,
            "midOpen": np.float32,
            "midHigh": np.float32,
            "midLow": np.float32,
            "midClose": np.float32,
        },
        engine='c',
        infer_datetime_format=True,
        cache_dates=True,
    )


def resample_ohlc_data(data: pd.DataFrame, time_frame: str):
    resampled = pd.DataFrame()
    resampled['Open'] = data['Open'].resample(time_frame).first()
    resampled['Close'] = data['Close'].resample(time_frame).last()
    resampled['High'] = data['High'].resample(time_frame).max()
    resampled['Low'] = data['Low'].resample(time_frame).min()
    resampled['Volume'] = data['Volume'].resample(time_frame).sum()

    return resampled


def drop_zero_volume_rows(data: pd.DataFrame):
    idxs = []
    for i in range(len(data)):
        if data['Volume'][i] == 0:
            idxs.append(data.index[i])
    data.drop(index=idxs, inplace=True)


def remove_duplicate_datetimes_from_csv(file_path: str):
    df = read_oanda_data(file_path)
    df.drop_duplicates(subset='datetime', inplace=True)
    df.to_csv(file_path, index=False)
