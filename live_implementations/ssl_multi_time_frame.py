# Python standard.
import concurrent.futures
import datetime
import time

# Local.
from src.account import Account
from src.indicators import get_ssl_value, append_average_true_range
from src.oanda_data import OandaInstrumentData
from tools.logger import *


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


def get_ssl_signals(data: dict) -> dict:
    return {k: get_ssl_value(v) for k, v in data.items()}


def get_atr_values(data: dict) -> dict:
    append_average_true_range(data['H1'])
    append_average_true_range(data['M5'])

    return {k: v['ATR'].iloc[-1] for k, v in data.items()}


def monitor_and_adjust_orders():
    pass


def execute():
    acc = Account(account_id='', access_token='', account_type='')
    prev_exec = -1
    prev_1_entry = 0
    prev_2_entry = 0
    while 1:
        now = datetime.datetime.now()
        monitor_and_adjust_orders()
        if now.minute % 5 == 0 and now.minute != prev_exec:
            print(prev_1_entry, prev_2_entry)
            data = get_data()
            signals = get_ssl_signals(data)
            atr_values = get_atr_values(data)
            print(signals)
            print(atr_values)
            prev_exec = now.minute
            prev_1_entry = signals['H1']
            prev_2_entry = signals['M5']
            print(prev_1_entry, prev_2_entry)


if __name__ == '__main__':
    # start = time.time()
    # construct_data()['D']['ATR']
    # get_ssl_signals(construct_data())
    # print(time.time() - start)
    execute()
