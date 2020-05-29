# Python standard.
import concurrent.futures
import datetime
import time

# Local.
from src.account import Account
from src.indicators import get_ssl_value, append_average_true_range
from src.oanda_data import OandaInstrumentData
from tools.logger import *
from settings import DEMO_V20_ACCOUNT_NUMBER, DEMO_ACCESS_TOKEN


def get_data() -> dict:
    od = OandaInstrumentData()
    data = {}
    time_frames = ['D', 'H1', 'M5']
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_tf = {}
        for granularity in time_frames:
            future_to_tf[executor.submit(od.get_candlesticks, 'SPX500_USD', 'ABM', granularity, 20)] = granularity
        for future in concurrent.futures.as_completed(future_to_tf):
            time_frame = future_to_tf[future]
            try:
                data[time_frame] = od.convert_to_df(future.result()['candles'], 'ABM')
            except Exception as exc:
                logger.error(
                    f'Failed to retrieve Oanda candlestick data for time frame: {time_frame}. {exc}',
                    exc_info=True,
                )

    return data


def get_atr_values(data: dict) -> dict:
    append_average_true_range(data['H1'])
    append_average_true_range(data['M5'])

    return {
        '1': data['H1']['ATR'].iloc[-1],
        '2': data['M5']['ATR'].iloc[-1],
    }


def get_signals(data: dict):
    ssl_values = {k: get_ssl_value(v) for k, v in data.items()}
    signals = {
        '1': None,
        '2': None,
    }

    # Strategy one.
    if ssl_values['D'] == 1 and ssl_values['H1'] == 1:
        signals['1'] = 'long'
    elif ssl_values['D'] == -1 and ssl_values['H1'] == -1:
        signals['1'] = 'short'

    # Strategy two.
    if ssl_values['H1'] == 1 and ssl_values['M5'] == 1:
        signals['2'] = 'long'
    elif ssl_values['H1'] == -1 and ssl_values['M5'] == -1:
        signals['2'] = 'short'

    # Only trade in same direction.
    if signals['2'] != signals['1']:
        signals['2'] = None

    return signals


def place_trade(
        signal: str,
        ask_high: float,
        bid_low: float,
        entry_offset: float,
        take_profit: float,
        stop_loss: float,
        margin_size: float,
):
    if signal == 'long':
        entry_price = round(ask_high + entry_offset, 1)
    elif signal == 'short':
        entry_price = round(bid_low - entry_offset, 1)


def monitor_and_adjust_orders():
    pass


def execute():
    account = Account(account_id=DEMO_V20_ACCOUNT_NUMBER, access_token=DEMO_ACCESS_TOKEN, account_type='DEMO_API')
    prev_exec = -1
    prev_1_entry = 0
    prev_2_entry = 0

    # Prevent doing operations more frequently than is required/correct.
    partially_closed_once = []
    partially_closed_twice = []
    sl_moved_once = []
    sl_moved_twice = []
    while 1:
        now = datetime.datetime.now()
        if now.minute % 5 == 0 and now.minute != prev_exec:
            data = get_data()
            signals = get_signals(data)

            # Remove outdated pending orders depending on entry signals.
            # if prev_1_entry != signals['H1']:
            #     account.delete_pending_orders(valid_positions=signals['H1'])

            strategy_atr_values = get_atr_values(data)
            strategy_entry_offsets = {
                '1': strategy_atr_values['1'] / 5,
                '2': strategy_atr_values['2'] / 5,
            }

            # Check for new signals, don't re-enter every candle with same entry signal.
            entry_signals_to_check = {
                '1': {
                    'previous': prev_1_entry,
                    'current': signals['1'],
                },
                '2': {
                    'previous': prev_2_entry,
                    'current': signals['2'],
                },
            }
            print(data['M5']['askHigh'].iloc[-1])
            print(data['M5']['bidLow'].iloc[-1])
            # for strategy, signal in signals.items():
            #     compare_signals = entry_signals_to_check[strategy]
            #     if signal \
            #             and compare_signals['previous'] != compare_signals['current'] \
            #             and account.has_margin_available():
            #         sl_pip_amount = strategy_atr_values[strategy] * 3.25
            #         margin_size = account.get_margin_size_per_trade()
            #         if margin_size > 0:
            #             tp_pip_amount = sl_pip_amount * 2.
            #             place_trade(
            #                 signal=signal,
            #                 ask_high=data['M5']['askHigh'],
            #                 bid_low=data['M5']['bidLow'],
            #                 entry_offset=strategy_entry_offsets[strategy],
            #                 take_profit=tp_pip_amount,
            #                 stop_loss=sl_pip_amount,
            #                 margin_size=margin_size,
            #             )
            prev_exec = now.minute
            prev_1_entry = signals['1']
            prev_2_entry = signals['2']
        # account.check_and_partially_close_profits()
        # account.check_and_adjust_stops()


if __name__ == '__main__':
    # start = time.time()
    # print(time.time() - start)
    execute()
