# Third-party.
import pandas as pd


def read_oanda_data(file_path: str) -> pd.DataFrame:
    return pd.read_csv(
        filepath_or_buffer=file_path,
        sep=',',
        index_col='datetime',
        parse_dates=['datetime'],
        engine='c',
        infer_datetime_format=True,
        cache_dates=True,
    )


def remove_duplicate_datetimes_from_csv(file_path: str):
    df = read_oanda_data(file_path)
    df.drop_duplicates(subset='datetime', inplace=True)
    df.reset_index(drop=True)
    df.to_csv(file_path, index=False)
