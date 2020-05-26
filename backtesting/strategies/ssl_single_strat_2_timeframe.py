# Python standard.
import datetime
from typing import Tuple, List, Union

# Third-party.
import pandas as pd
from tqdm import tqdm

# Local.
from backtesting.account import BackTestingAccount
from src.indicators import append_average_true_range, append_ssl_channel
from tools.data_operations import read_oanda_data
from tools.plot import plot_overlay_balance_and_ssl
from tools.datetime_utils import (
    get_nearest_daily_or_weekly_data,
    get_nearest_1hr_data,
)


def get_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    day = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/SPX500_USD/SPX500USD_D.csv')
    hourly = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/SPX500_USD/SPX500USD_H1.csv')
    five_min = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/SPX500_USD/SPX500USD_M5.csv')

    return day, hourly, five_min


def has_new_signal(prev: int, curr: int) -> bool:
    return prev != curr


def check_signal(trend: int, entry: int) -> Union[str, None]:
    signal = None
    if trend == 1 and entry == 1:
        signal = 'long'
    elif trend == -1 and entry == -1:
        signal = 'short'

    return signal


def place_trade(
        account: BackTestingAccount,
        signal: str,
        prev_candle: pd.DataFrame,
        curr_dt: datetime.datetime,
        instrument_point_type: str,
        tp_pip_amount: float,
        sl_pip_amount: float,
        label: str,
        spread: float,
        entry_offset: float,
        margin_size: float,
):
    if signal == 'long':
        entry_price = round(prev_candle['askHigh'], 5) + entry_offset
        account.open_trade(
            instrument_point_type=instrument_point_type,
            opened_at=curr_dt,
            order_type='long_dynamic_sl',
            entry=entry_price,
            take_profit=round(entry_price + tp_pip_amount, 5),
            stop_loss=round(entry_price - sl_pip_amount, 5),
            margin_size=margin_size,
            label=label,
            spread=spread,
        )
    elif signal == 'short':
        entry_price = round(prev_candle['bidLow'], 5) - entry_offset
        account.open_trade(
            instrument_point_type=instrument_point_type,
            opened_at=curr_dt,
            order_type='short_dynamic_sl',
            entry=entry_price,
            take_profit=round(entry_price - tp_pip_amount, 5),
            stop_loss=round(entry_price + sl_pip_amount, 5),
            margin_size=margin_size,
            label=label,
            spread=spread,
        )


# Construct data.
daily, hr1, m5 = get_data()

# Trend indicator values.
append_ssl_channel(data=daily, periods=20)

# Entry indicator values.
append_ssl_channel(data=hr1, periods=20)

# Used to calculate tp/sl.
append_average_true_range(df=hr1, prices='mid', periods=14)


def execute() -> Tuple[BackTestingAccount, List[float]]:
    is_even_cycle = False
    prev_entry = 0

    # Set up and track account.
    balances = []
    account = BackTestingAccount(starting_capital=10000, equity_split=2)
    prev_month_deposited = 0

    # ~ 3 years: 134447. 21st Feb 2020: 346535.
    for curr_dt, curr_candle in tqdm(m5[267186:346535:].iterrows()):
        spread = curr_candle['askOpen'] - curr_candle['bidOpen']
        idx = int(curr_candle['idx'])

        # Get valid candles.
        d_candle, is_even_cycle = get_nearest_daily_or_weekly_data(daily, curr_dt, is_even_cycle)
        hr1_candle = get_nearest_1hr_data(hr1, curr_dt)
        previous_5m_candlestick = m5.iloc[idx - 1]

        # Strategy SSL.
        trend = d_candle['HighLowValue'].values[0]
        entry = hr1_candle['HighLowValue'].values[0]

        # Used to set stop loss and take profits.
        atr_value = hr1_candle['ATR'].values[0]

        # Data to plot.
        balances.append(account.get_current_total_balance())

        # Add 2k margin every month.
        if prev_month_deposited != curr_dt.month:
            account.deposit_funds(2000.)
            prev_month_deposited = curr_dt.month

        # Check signal and act.
        signal = check_signal(trend, entry)

        # Prices to use to process pending and active orders.
        long_prices_to_check = [
            previous_5m_candlestick['bidHigh'],
            previous_5m_candlestick['bidLow'],
            curr_candle['bidOpen'],
        ]
        short_prices_to_check = [
            previous_5m_candlestick['askHigh'],
            previous_5m_candlestick['askLow'],
            curr_candle['askOpen'],
        ]

        # Remove outdated pending orders depending on entry signals.
        account.process_pending_orders(long_prices_to_check, short_prices_to_check, [f'1_{signal}'])

        # Place new pending orders.
        if signal \
                and has_new_signal(prev=prev_entry, curr=entry) \
                and account.has_margin_available() \
                and account.count_orders_by_label(label='1') < 1000:
            sl_pip_amount = atr_value * 3.25
            margin_size = account.get_margin_size_per_trade()
            if margin_size > 0:
                tp_pip_amount = sl_pip_amount * 2.
                place_trade(
                    account=account,
                    signal=signal,
                    prev_candle=previous_5m_candlestick,
                    curr_dt=curr_dt,
                    tp_pip_amount=tp_pip_amount,
                    sl_pip_amount=sl_pip_amount,
                    instrument_point_type='spx500usd',
                    label=f'1_{signal}',
                    spread=spread,
                    entry_offset=atr_value / 5,
                    margin_size=margin_size,
                )

        # Monitor and act on active trades.
        if account.has_active_trades():
            for i in range(3):
                long_price = long_prices_to_check[i]
                short_price = short_prices_to_check[i]
                account.monitor_and_close_active_trades(
                    current_date_time=curr_dt,
                    long_price=long_price,
                    short_price=short_price,
                )
                account.check_and_adjust_stop_losses(
                    long_price=long_price,
                    short_price=short_price,
                    check_pct=0.35,
                    move_pct=0.01,
                )
                account.check_and_adjust_stop_losses(
                    long_price=long_price,
                    short_price=short_price,
                    check_pct=0.65,
                    move_pct=0.35,
                )
                account.check_and_partially_close_profits(
                    check_pct=0.35,
                    close_pct=0.5,
                    long_price=long_price,
                    short_price=short_price,
                    partial_close_count=1,
                )
                account.check_and_partially_close_profits(
                    check_pct=0.65,
                    close_pct=0.7,
                    long_price=long_price,
                    short_price=short_price,
                    partial_close_count=2,
                )
        prev_entry = entry

    return account, balances


if __name__ == '__main__':
    acc, bal = execute()
    print(acc)
    print(acc.get_individual_strategy_wins_losses(['1']))
    plot_overlay_balance_and_ssl(
        datetimes=hr1.index,
        opens=hr1['midOpen'],
        highs=hr1['midHigh'],
        lows=hr1['midLow'],
        closes=hr1['midClose'],
        account_balance_over_time=bal,
        ssl_ups=hr1['SSLUp'],
        ssl_downs=hr1['SSLDown'],
    )
