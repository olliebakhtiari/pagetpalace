# Python standard.
import datetime
from typing import Tuple, List

# Third-party.
import pandas as pd
import numpy as np
from tqdm import tqdm

# Local.
from tools.plot import plot_candles_and_overlay_account_balance
from backtesting.account import BackTestingAccount
from src.indicators import stochastic_rsi, append_average_true_range
from tools.data_operations import read_oanda_data
from tools.datetime_utils import get_nearest_4hr_loc, get_nearest_hr_loc

SPREAD = 2e-4


def get_all_time_frames() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/GBPUSD_D.csv')
    four_hr = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/GBPUSD_H4.csv')
    hourly = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/GBPUSD_H1.csv')
    fifteen_min = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/GBPUSD_M15.csv')

    return daily, four_hr, hourly, fifteen_min


def append_stochastic_rsi(data: pd.DataFrame):
    _rsi, k, d = stochastic_rsi(
        prices=data['midOpen'],
        periods=14,
        smooth_k=3,
        smooth_d=3,
    )
    data['StochK'] = k
    data['StochD'] = d


def check_4hr_stoch_signal(k: float, d: float) -> str:
    signal = 'undetermined'
    if k > 0.5:
        signal = 'long'
    elif k < 0.5:
        signal = 'short'

    return signal


def check_hourly_stoch_signal(k: float, d: float) -> str:
    signal = 'undetermined'
    if k < 0.5:
        signal = 'long'
    elif k > 0.5:
        signal = 'short'

    return signal


def check_15min_stoch_signal(k: float, d: float) -> str:
    signal = 'undetermined'
    if k > 0.5:
        signal = 'long'
    elif k < 0.5:
        signal = 'short'

    return signal


def check_signals(four_kd: Tuple[float, float], hr_kd: Tuple[float, float], fifteen_kd: Tuple[float, float]) -> str:
    signal = 'undetermined'
    four = check_4hr_stoch_signal(four_kd[0], four_kd[1])
    hr = check_hourly_stoch_signal(hr_kd[0], hr_kd[1])
    fifteen = check_15min_stoch_signal(fifteen_kd[0], fifteen_kd[1])
    if four == hr == fifteen:
        signal = four

    return signal


def execute(equity_split: int = 2,
            check_pct: float = 0.5,
            move_pct: float = 0.01) -> Tuple[BackTestingAccount, List[float]]:
    is_even_cycle = False

    # Construct data.
    gbp_usd_daily, gbp_usd_4hr, gbp_usd_hourly, gbp_usd_15m = get_all_time_frames()
    for df in [gbp_usd_4hr, gbp_usd_hourly, gbp_usd_15m]:
        append_stochastic_rsi(df)
        append_average_true_range(df, prices='mid', periods=14)

    # Set up and track account.
    balances = []
    account = BackTestingAccount(starting_capital=10000, equity_split=equity_split)
    for curr_dt, current_15_candlestick in tqdm(gbp_usd_15m.iterrows()):
        idx = current_15_candlestick['idx']

        # Data to plot.
        balances.append(account.get_current_total_balance())

        # Add 2k margin every 30 days.
        if idx % 2880 == 0:
            account.deposit_funds(2000.)

        # Calculate correct df locations for other time frames and retrieve stochastic values.
        hr_loc = get_nearest_hr_loc(curr_dt)
        four_hr_loc = get_nearest_4hr_loc(curr_dt, is_even_cycle=is_even_cycle)
        try:
            f_kd = (gbp_usd_4hr.loc[four_hr_loc]['StochK'], gbp_usd_4hr.loc[four_hr_loc]['StochD'])
        except KeyError as exc:
            is_even_cycle = not is_even_cycle
            print(f'{exc}, daylight savings cycle changing. is_odd_cycle = {is_even_cycle}')
            four_hr_loc = get_nearest_4hr_loc(curr_dt, is_even_cycle=is_even_cycle)
            f_kd = (gbp_usd_4hr.loc[four_hr_loc]['StochK'], gbp_usd_4hr.loc[four_hr_loc]['StochD'])
        hr_kd = (gbp_usd_hourly.loc[hr_loc]['StochK'], gbp_usd_hourly.loc[hr_loc]['StochD'])
        fif_kd = (current_15_candlestick['StochK'], current_15_candlestick['StochD'])

        # Check signals and act.
        signal = check_signals(f_kd, hr_kd, fif_kd)
        if signal != 'undetermined' \
                and account.number_of_active_trades() < account.equity_split \
                and account.has_margin_available():
            sl_pip_amount = gbp_usd_hourly.loc[hr_loc]['ATR'] * 2.5
            tp_pip_amount = sl_pip_amount * 1.5
            if signal == 'long':
                entry_price = round(current_15_candlestick['midOpen'] + SPREAD, 5)
                account.open_trade(
                    opened_at=curr_dt,
                    order_type='long_dynamic_sl',
                    entry=entry_price,
                    take_profit=round(entry_price + tp_pip_amount, 5),
                    stop_loss=round(entry_price - sl_pip_amount, 5),
                    margin_size=account.get_current_total_balance() * 0.2,
                )
            elif signal == 'short':
                entry_price = round(current_15_candlestick['midOpen'] - SPREAD, 5)
                account.open_trade(
                    opened_at=curr_dt,
                    order_type='short_dynamic_sl',
                    entry=entry_price,
                    take_profit=round(entry_price - tp_pip_amount, 5),
                    stop_loss=round(entry_price + sl_pip_amount, 5),
                    margin_size=account.get_current_total_balance() * 0.2,
                )

        # Monitor and act on existing trades.
        if account.has_active_trades():
            previous_candlestick = gbp_usd_15m.iloc[idx - 1]
            prices_to_check = [
                previous_candlestick['midHigh'],
                previous_candlestick['midLow'],
                current_15_candlestick['midOpen'],
            ]
            for price in prices_to_check:
                account.monitor_and_close_active_trades(
                    current_date_time=curr_dt,
                    price=price,
                )
                account.check_and_adjust_stop_losses(
                    price=price,
                    check_pct=check_pct,
                    move_pct=move_pct,
                )

    return account, balances


if __name__ == '__main__':
    # a, b, c, d = get_all_time_frames()
    # print(a['midOpen'])
    acc, bal = execute()
    print(acc)
    # d = datetime.datetime(year=2015, month=3, day=13, hour=5, minute=0, second=0)
    # print(get_nearest_4hr_loc(d, True))
    # plot_candles_and_overlay_account_balance(
    #     bal,
    #
    # )
