# Third-party.
import pandas as pd
import numpy as np


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


def remove_duplicate_datetimes_from_csv(file_path: str):
    df = read_oanda_data(file_path)
    df.drop_duplicates(subset='datetime', inplace=True)
    df.to_csv(file_path, index=False)
