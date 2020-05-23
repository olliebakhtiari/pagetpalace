# Python standard.
import datetime
from typing import Tuple

# Third-party.
import pandas as pd
import numpy as np


def get_days_in_months() -> dict:
    return {
        1: 31,
        2: 28,  # account for leap year when using.
        3: 31,
        4: 30,
        5: 31,
        6: 30,
        7: 31,
        8: 31,
        9: 30,
        10: 31,
        11: 30,
        12: 31,
    }


def is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def convert_from_timestamp(timestamp: int) -> str:
    return datetime.datetime.utcfromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def get_date_and_time(d_t: datetime.datetime) -> Tuple[datetime.date, datetime.time]:
    return datetime.date(d_t.year, d_t.month, d_t.day), datetime.time(d_t.hour, d_t.minute, d_t.second)


def is_market_open(date: datetime.date, time: str) -> bool:
    dow = date.isoweekday()
    hour = int(time.split(':')[0])
    if dow == 5 and hour >= 22:
        return False
    if dow == 6:
        return False
    if dow == 7 and hour < 22:
        return False

    return True


def get_nearest_15m_loc(dt: datetime.datetime) -> datetime.datetime:
    return datetime.datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute - dt.minute % 15, 0)


def get_nearest_15m_data(fif_data: pd.DataFrame, curr_dt: datetime.datetime) -> pd.DataFrame:
    fif_loc = str(get_nearest_15m_loc(curr_dt))
    idx = np.where(fif_data.index == fif_loc)[0]
    data = fif_data.iloc[idx - 1]

    return data


def get_nearest_hr_loc(dt: datetime.datetime) -> datetime.datetime:
    return datetime.datetime(dt.year, dt.month, dt.day, dt.hour, 0, 0)


def get_nearest_1hr_data(hr_data: pd.DataFrame, curr_dt: datetime.datetime) -> pd.DataFrame:
    hr_loc = str(get_nearest_hr_loc(curr_dt))
    idx = np.where(hr_data.index == hr_loc)[0]
    data = hr_data.iloc[idx - 1]

    return data


def get_nearest_4hr_loc(dt: datetime.datetime, is_even_cycle: bool, even_time_offset: bool) -> datetime.datetime:
    """ Four hr data set affected by daylight savings. odd cycle -> 01, 05, 09, 13, 17, 21.
        Even time can be 00, 04, 08, 12, 16, 20 or 02, 06, 10, 14, 18, 22. Use even_time_offset for second case.
     """
    loc = datetime.datetime(dt.year, dt.month, dt.day, dt.hour - dt.hour % 4, 0, 0)
    if even_time_offset:
        loc = calculate_even_time_with_offset_even_cycle(dt, loc)
        if not is_even_cycle:
            loc = calculate_even_time_with_offset_odd_cycle(dt, loc)
    else:
        if not is_even_cycle:
            if dt.hour % 4 == 0:
                loc -= datetime.timedelta(hours=3)
            else:
                loc += datetime.timedelta(hours=1)

    return loc


def calculate_even_time_with_offset_even_cycle(dt: datetime.datetime, loc: datetime.datetime) -> datetime.datetime:
    if dt.hour % 4 == 2 or dt.hour % 4 == 3:
        new_loc = loc + datetime.timedelta(hours=2)
    else:
        new_loc = loc - datetime.timedelta(hours=2)

    return new_loc


def calculate_even_time_with_offset_odd_cycle(dt: datetime.datetime, loc: datetime.datetime) -> datetime.datetime:
    if dt.hour % 4 == 1:
        new_loc = loc + datetime.timedelta(hours=3)
    else:
        new_loc = loc - datetime.timedelta(hours=1)

    return new_loc


def get_nearest_4hr_data(four_hr_data: pd.DataFrame,
                         curr_dt: datetime.datetime,
                         is_even_cycle: bool,
                         even_time_offset: bool) -> Tuple[pd.DataFrame, bool]:
    four_hr_loc = str(get_nearest_4hr_loc(curr_dt, is_even_cycle, even_time_offset))
    idx = np.where(four_hr_data.index == four_hr_loc)[0]
    data = four_hr_data.iloc[idx - 1]
    if not len(data.values):
        is_even_cycle = not is_even_cycle
        four_hr_loc = str(get_nearest_4hr_loc(curr_dt, is_even_cycle, even_time_offset))
        idx = np.where(four_hr_data.index == four_hr_loc)[0]
        data = four_hr_data.iloc[idx - 1]

    return data, is_even_cycle


def get_nearest_daily_loc(dt: datetime.datetime, is_even_cycle: bool) -> datetime.datetime:
    return datetime.datetime(dt.year, dt.month, dt.day, 22 if is_even_cycle else 21, 0, 0)


def get_nearest_daily_data(d_data: pd.DataFrame,
                           curr_dt: datetime.datetime,
                           is_even_cycle: bool) -> Tuple[pd.DataFrame, bool]:
    d_loc = str(get_nearest_daily_loc(curr_dt, is_even_cycle))
    idx = np.where(d_data.index == d_loc)[0]
    data = d_data.iloc[idx - 1]
    if not len(data.values):
        is_even_cycle = not is_even_cycle
        d_loc = str(get_nearest_daily_loc(curr_dt, is_even_cycle))
        idx = np.where(d_data.index == d_loc)[0]
        data = d_data.iloc[idx - 1]

    return data, is_even_cycle


if __name__ == '__main__':
    dt_ = datetime.datetime(year=2017, month=1, day=8, hour=6, minute=0, second=0)
    print(get_nearest_4hr_loc(dt_, is_even_cycle=False, even_time_offset=False))


