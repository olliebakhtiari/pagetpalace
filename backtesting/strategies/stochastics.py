# Python standard.
from typing import Tuple, List

# Third-party.
import pandas as pd
from tqdm import tqdm

# Local.
from tools.data_operations import read_data
from tools.datetime_utils import get_date_and_time
from tools.plot import plot_candles_and_overlay_account_balance
from backtesting.account import BackTestingAccount
from src.indicators import stochastic_rsi


def get_data_and_append_indicator_values() -> Tuple[pd.DataFrame, pd.DataFrame]:
    gbp_usd_data = read_data(time_frames=['Hourly', 'Daily'], data_source='oanda')

    # Daily data with ATR and StochasticRSI values. Set datetime column as index to map hour candles to daily.
    gbp_usd_daily = gbp_usd_data['Daily']
    gbp_usd_daily.set_index(
        gbp_usd_daily['datetime'],
        inplace=True,
        drop=True,
        append=False,
        verify_integrity=False,
    )
    _daily_rsi, daily_k, daily_d = stochastic_rsi(
        prices=gbp_usd_daily['AskOpen'],
        periods=14,
        smooth_k=3,
        smooth_d=3,
    )
    gbp_usd_daily['StochK'] = daily_k
    gbp_usd_daily['StochD'] = daily_d
    append_average_true_range(gbp_usd_daily, periods=14)

    # Hourly data and stochastic values.
    gbp_usd_hourly = gbp_usd_data['Hourly']
    _hourly_rsi, hourly_k, hourly_d = stochastic_rsi(
        prices=gbp_usd_hourly['AskOpen'],
        periods=14,
        smooth_k=3,
        smooth_d=3,
    )
    gbp_usd_hourly['StochK'] = hourly_k
    gbp_usd_hourly['StochD'] = hourly_d

    return gbp_usd_daily, gbp_usd_hourly


def append_average_true_range(df: pd.DataFrame, periods: int = 14):
    data = df.copy()
    high = data['AskHigh']
    low = data['AskLow']
    close = data['AskClose']
    data['tr0'] = abs(high - low)
    data['tr1'] = abs(high - close.shift())
    data['tr2'] = abs(low - close.shift())
    data['true_range'] = data[['tr0', 'tr1', 'tr2']].max(axis=1)

    df['ATR'] = data['true_range'].ewm(alpha=1 / periods).mean()


def check_daily_stochastic_bias(k: float, d: float) -> str:
    """ 4 """
    bias = 'undetermined'
    if abs(k - d) > 4e-2:
        if k > d:
            bias = 'long'
        elif k < d:
            bias = 'short'

    return bias


def check_hourly_stochastic_signal(k: float, d: float) -> str:
    """ 7, 40/75, 60/24 """
    signal = 'undetermined'
    if abs(k - d) > 7e-2:
        if k > d and (40e-2 < k < 75e-2):
            signal = 'long'
        elif k < d and (60e-2 > k > 24e-2):
            signal = 'short'

    return signal


def get_long_multiplier(k: float) -> float:
    """ - multiplier scale: 2.5 - 1
        - k scale: 5 - 95
    """
    multiplier = 2.5
    if k > 5e-2:
        n = round(k * 1e2) - 5
        delta = 1.5 / 90
        multiplier = 2.5 - (n * delta)

    return multiplier


def get_short_multiplier(k: float) -> float:
    """ - multiplier scale: 1 - 2.5
        - k scale: 5 - 95
    """
    multiplier = 2.5
    if k < 95e-2:
        n = 95 - round(k * 1e2)
        delta = 1.5 / 90
        multiplier = 2.5 - (n * delta)

    return multiplier


def check_signals(d_k: float, d_d: float, h_k: float, h_d: float) -> str:
    signal = 'undetermined'
    daily_bias = check_daily_stochastic_bias(k=d_k, d=d_d)
    hourly_signal = check_hourly_stochastic_signal(k=h_k, d=h_d)
    if daily_bias == hourly_signal:
        signal = hourly_signal

    return signal


# 2015 - 2020 starting index = 50314.
# 2018 - 2020 starting index = 80752.
# 528 hours in 22 days.
def execute(sl_mult: float = 0.9,
            equity_split: int = 11,
            check: float = 0.5,
            move: float = 0.05) -> Tuple[BackTestingAccount, List[float]]:
    gbp_usd_daily, gbp_usd_hourly = get_data_and_append_indicator_values()
    balances = []
    account = BackTestingAccount(starting_capital=20000, equity_split=equity_split)
    for idx, current_hour_candlestick in tqdm(gbp_usd_hourly[50314::].iterrows()):

        # Data to plot.
        balances.append(account.get_current_total_balance())

        # Add 2k margin every 22 days.
        if idx % 528 == 0:
            account.deposit_funds(2000.)

        today_date, _current_time = get_date_and_time(str(current_hour_candlestick['datetime']))
        daily_candlestick = gbp_usd_daily.loc[str(today_date)]
        signal = check_signals(
            daily_candlestick['StochK'],
            daily_candlestick['StochD'],
            current_hour_candlestick['StochK'],
            current_hour_candlestick['StochD'],
        )
        if signal \
                and signal != 'undetermined' \
                and account.number_of_active_trades() < account.equity_split \
                and account.has_margin_available():
            spread = round(current_hour_candlestick['AskOpen'] - current_hour_candlestick['BidOpen'], 5)
            stop_loss_amount = daily_candlestick['ATR'] * sl_mult
            if signal == 'long':
                entry_price = round(current_hour_candlestick['AskOpen'] + spread, 5)
                take_profit_amount = round(
                    number=stop_loss_amount * get_long_multiplier(k=current_hour_candlestick['StochK']),
                    ndigits=5,
                )
                tp_price = round(entry_price + take_profit_amount, 5)
                sl_price = round(entry_price - stop_loss_amount, 5)
                account.open_trade(
                    opened_at=current_hour_candlestick['datetime'],
                    order_type='long_dynamic_sl',
                    entry=entry_price,
                    take_profit=tp_price,
                    stop_loss=sl_price,
                    margin_size=account.get_margin_size_per_trade(),
                )
            elif signal == 'short':
                entry_price = round(current_hour_candlestick['AskOpen'] - spread, 5)
                take_profit_amount = round(
                    number=stop_loss_amount * get_short_multiplier(k=current_hour_candlestick['StochK']),
                    ndigits=5,
                )
                tp_price = round(entry_price - take_profit_amount, 5)
                sl_price = round(entry_price + stop_loss_amount, 5)
                account.open_trade(
                    opened_at=current_hour_candlestick['datetime'],
                    order_type='short_dynamic_sl',
                    entry=entry_price,
                    take_profit=tp_price,
                    stop_loss=sl_price,
                    margin_size=account.get_margin_size_per_trade(),
                )
        if account.has_active_trades():
            previous_candlestick = gbp_usd_hourly.iloc[idx-1]
            prices_to_check = [
                previous_candlestick['AskHigh'],
                previous_candlestick['AskLow'],
                current_hour_candlestick['AskOpen'],
            ]
            for price in prices_to_check:
                account.monitor_and_close_active_trades(
                    current_date_time=current_hour_candlestick['datetime'],
                    price=price,
                )
                account.check_and_adjust_stop_losses(
                    price=price,
                    check_pct=check,
                    move_pct=move,
                )

    return account, balances


if __name__ == '__main__':
    _daily, hourly = get_data_and_append_indicator_values()
    two_years_h = hourly[50314::]
    a, b = execute()
    print(a)
    plot_candles_and_overlay_account_balance(
        two_years_h['datetime'],
        two_years_h['AskOpen'],
        two_years_h['AskHigh'],
        two_years_h['AskLow'],
        two_years_h['AskClose'],
        b,
    )

