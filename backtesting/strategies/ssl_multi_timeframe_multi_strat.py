# Python standard.
import datetime
from typing import Tuple, List

# Third-party.
import pandas as pd
from tqdm import tqdm

# Local.
from backtesting.account import BackTestingAccount
from src.indicators import append_average_true_range, append_ssl_channel
from tools.data_operations import read_oanda_data
from tools.datetime_utils import (
    get_nearest_daily_or_weekly_data,
    get_nearest_1hr_data,
)


def get_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    day = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/NAS100_USD/NAS100USD_D.csv')
    hour = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/NAS100_USD/NAS100USD_H1.csv')
    five_min = read_oanda_data('/Users/oliver/Documents/pagetpalace/data/oanda/NAS100_USD/NAS100USD_M5.csv')

    return day, hour, five_min


def has_new_signal(prev: int, curr: int) -> bool:
    return prev != curr


def check_signals(s1_params: tuple, s2_params: tuple) -> dict:
    """ TUPLE -> (TREND, ENTRY)

        S1 = D, H1
        S2 = H1, M5
    """
    strategy_ssl_values_to_check = {
        '1': s1_params,
        '2': s2_params,
    }
    signals = {
        '1': None,
        '2': None,
    }
    for i in range(1, 3):
        strategy = str(i)
        hi_lo_values = strategy_ssl_values_to_check[strategy]
        trend_ssl = hi_lo_values[0]
        entry_ssl = hi_lo_values[1]
        if trend_ssl == 1 and entry_ssl == 1:
            signals[strategy] = 'long'
        elif trend_ssl == -1 and entry_ssl == -1:
            signals[strategy] = 'short'
    if signals['2'] != signals['1']:
        signals['2'] = None

    return signals


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
for df in [daily, hr1, m5]:
    append_ssl_channel(data=df, periods=20)
for df in [hr1, m5]:
    append_average_true_range(df=df, prices='mid', periods=14)


def execute(equity_split: float) -> Tuple[BackTestingAccount, List[float]]:
    is_even_cycle = False
    prev_1_entry = 0
    prev_2_entry = 0

    # Set up and track account.
    balances = []
    account = BackTestingAccount(starting_capital=10000, equity_split=equity_split)
    prev_month_deposited = 0

    # Iterate through lowest time frame of all strategies being ran. 276711 ~1 year. 21st Feb 2020: 346535.
    for curr_dt, curr_candle in m5[276711:346535:].iterrows():
        valid_labels = []
        spread = curr_candle['askOpen'] - curr_candle['bidOpen']
        idx = int(curr_candle['idx'])

        # Get valid candles.
        d_candle, is_even_cycle = get_nearest_daily_or_weekly_data(daily, curr_dt, is_even_cycle)
        hr1_candle = get_nearest_1hr_data(hr1, curr_dt)
        previous_5m_candlestick = m5.iloc[idx - 1]

        # Strategy 1 SSL.
        trend_1 = d_candle['HighLowValue'].values[0]
        entry_1 = hr1_candle['HighLowValue'].values[0]

        # Strategy 2 SSL.
        trend_2 = hr1_candle['HighLowValue'].values[0]
        entry_2 = previous_5m_candlestick['HighLowValue']

        # Used to set stop loss and take profits.
        strategy_atr_values = {
            '1': hr1_candle['ATR'].values[0],
            '2': previous_5m_candlestick['ATR'],
        }
        strategy_entry_offsets = {
            '1': strategy_atr_values['1'] / 5,
            '2': strategy_atr_values['2'] / 5,
        }

        # Check for new signals, don't re-enter every candle with same entry signal.
        lowest_tf_candles_to_check = {
            '1': {
                'previous': prev_1_entry,
                'current': entry_1,
            },
            '2': {
                'previous': prev_2_entry,
                'current': entry_2,
            },
        }

        # Data to plot.
        balances.append(account.get_current_total_balance())

        # Add 2k margin every month.
        if prev_month_deposited != curr_dt.month:
            account.deposit_funds(2000.)
            prev_month_deposited = curr_dt.month

        # Check signals and act.
        signals = check_signals(
            s1_params=(trend_1, entry_1),
            s2_params=(trend_2, entry_2),
        )

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
        for strategy, signal in signals.items():
            if signal:
                valid_labels.append(f'{strategy}_{signal}')
        account.process_pending_orders(long_prices_to_check, short_prices_to_check, valid_labels)

        # Place new pending orders.
        for strategy, signal in signals.items():
            candles_to_check = lowest_tf_candles_to_check[strategy]
            if signal \
                    and has_new_signal(prev=candles_to_check['previous'], curr=candles_to_check['current']) \
                    and account.has_margin_available():
                sl_pip_amount = strategy_atr_values[strategy] * 3.25
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
                        instrument_point_type='nas100usd',
                        label=f'{strategy}_{signal}',
                        spread=spread,
                        entry_offset=strategy_entry_offsets[strategy],
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
        prev_1_entry = entry_1
        prev_2_entry = entry_2

    return account, balances


if __name__ == '__main__':
    for es in tqdm([1.5, 2]):
        acc, bal = execute(equity_split=es)
        print(f'equity_split={es}')
        print(acc)
        print(acc.get_individual_strategy_wins_losses(['1', '2', '3']))
