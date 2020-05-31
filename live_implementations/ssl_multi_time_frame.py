# Python standard.
import concurrent.futures
import datetime

# Third-party.
import pytz

# Local.
from src.account import Account
from src.orders import create_market_if_touched_order
from src.indicators import get_ssl_value, append_average_true_range
from src.oanda_data import OandaInstrumentData
from settings import DEMO_V20_ACCOUNT_NUMBER, DEMO_ACCESS_TOKEN
from tools.logger import *


class SSLMultiTimeFrame:
    UNRESTRICTED_MARGIN_CAP = 0.9

    def __init__(self, account: Account):
        self.account = account
        self._pending_orders_1 = []
        self._pending_orders_2 = []
        self._partially_closed_1 = []
        self._partially_closed_2 = []
        self._sl_moved_once = []
        self._sl_moved_twice = []

    def check_and_adjust_stops(self, open_trades: dict, check_pct: float, move_pct: float, adjusted_count: int):
        for trade in open_trades:
            pass

    def check_and_partially_close(self, open_trades: dict, check_pct: float, close_pct: float, partial_close_count):
        partial_close_once = self._partially_closed_1.copy()
        partial_close_twice = self._partially_closed_1.copy()
        list_to_check = partial_close_once + partial_close_twice if partial_close_count == 1 else partial_close_twice
        # TODO: convert close_pct to units.
        #       - look at structure of trades, only append IDs to local lists.
        for trade in open_trades:
            if trade not in list_to_check and self.check_pct_hit(trade):
                self.account.close_trade(trade_specifier=, close_amount=)
                getattr(self, f'_partially_closed_{partial_close_count}').append(trade)
        pass

    def check_pct_hit(self, trade: dict):
        pass

    def add_to_pending_orders(self, order: dict, strategy: str):
        # TODO: only add IDs to local lists.
        getattr(self, f'_pending_orders_{strategy}').append(order)

    def sync_pending_orders(self, pending_orders_in_account: dict):
        # TODO: only add IDs to local lists.
        for local_pending_list in [self._pending_orders_1, self._pending_orders_2]:
            for id_ in local_pending_list:
                if id_ not in pending_orders_in_account: # TODO: make this list of IDs.
                    local_pending_list.remove(id_)

    def delete_invalid_pending_orders(self, strategy: str):
        for id_ in getattr(self, f'_pending_orders_{strategy}'):
            self.account.cancel_order(id_)

    def get_unit_size_per_trade(self, balance: float, total_margin_available: float, pending_orders: dict) -> float:
        margin_size = self._get_valid_margin_size(
            margin_size=(balance * self.UNRESTRICTED_MARGIN_CAP) / 2,
            usable_margin=self._margin_not_being_used_in_orders(total_margin_available, pending_orders),
            balance=balance,
        )
        # TODO: convert margin size to unit size.

        return 1.

    @classmethod
    def _get_valid_margin_size(cls, margin_size: float, usable_margin: float, balance: float):
        available_minus_restricted = usable_margin - (balance * 0.1)
        if (margin_size > available_minus_restricted) and (available_minus_restricted < 200):
            margin_size = 0
        elif (margin_size > available_minus_restricted) and (available_minus_restricted >= 200):
            margin_size = available_minus_restricted

        return margin_size

    @classmethod
    def _margin_not_being_used_in_orders(cls, total_margin_available: float, pending_orders: dict) -> float:
        """ Available margin - margin in pending orders. """
        margin_tied_to_pending = 1

        return total_margin_available - margin_tied_to_pending

    @classmethod
    def get_data(cls) -> dict:
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

    @classmethod
    def get_atr_values(cls, data: dict) -> dict:
        append_average_true_range(data['H1'])
        append_average_true_range(data['M5'])

        return {
            '1': data['H1']['ATR'].iloc[-1],
            '2': data['M5']['ATR'].iloc[-1],
        }

    @classmethod
    def get_signals(cls, data: dict):
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

    @classmethod
    def construct_order(
            cls,
            signal: str,
            ask_high: float,
            bid_low: float,
            entry_offset: float,
            tp_pip_amount: float,
            sl_pip_amount: float,
            units: float,
    ):
        entry = 0
        sl = 0
        tp = 0
        if signal == 'long':
            entry = round(ask_high + entry_offset, 1)
            tp = round(entry + tp_pip_amount, 1)
            sl = round(entry - sl_pip_amount, 1)
        elif signal == 'short':
            entry = round(bid_low - entry_offset, 1)
            tp = round(entry - tp_pip_amount, 1)
            sl = round(entry + sl_pip_amount, 1)
            units = units * -1

        return create_market_if_touched_order(entry=entry, sl=sl, tp=tp, instrument='SPX500_USD', units=units)

    @classmethod
    def monitor_and_adjust_orders(cls):
        pass

    def execute(self):
        london_tz = pytz.timezone('Europe/London')
        prev_exec = -1
        prev_1_entry = 0
        prev_2_entry = 0
        while 1:
            now = datetime.datetime.now().astimezone(london_tz)
            pending_orders = self.account.get_pending_orders()
            self.sync_pending_orders(pending_orders)
            account_summary = s.account.get_summary()['account']
            if now.minute % 5 == 0 and now.minute != prev_exec:
                data = self.get_data()
                signals = self.get_signals(data)
                strategy_atr_values = self.get_atr_values(data)
                strategy_entry_offsets = {
                    '1': strategy_atr_values['1'] / 5,
                    '2': strategy_atr_values['2'] / 5,
                }

                # Compare signals, don't re-enter every candle with same entry signal.
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
                # Remove outdated pending orders depending on entry signals.
                for strategy_num, entry_signals in entry_signals_to_check.items():
                    if entry_signals['previous'] != entry_signals['current']:
                        self.delete_invalid_pending_orders(strategy=strategy_num)

                # New orders.
                for strategy, signal in signals.items():
                    compare_signals = entry_signals_to_check[strategy]
                    units = self.get_unit_size_per_trade(
                        balance=float(account_summary['balance']),
                        total_margin_available=float(account_summary['marginAvailable']),
                        pending_orders=pending_orders,
                    )
                    if units \
                            and signal \
                            and compare_signals['previous'] != compare_signals['current']:
                        sl_pip_amount = strategy_atr_values[strategy] * 3.25
                        if units > 0:
                            tp_pip_amount = sl_pip_amount * 2.
                            order_schema = self.construct_order(
                                signal=signal,
                                ask_high=data['M5']['askHigh'],
                                bid_low=data['M5']['bidLow'],
                                entry_offset=strategy_entry_offsets[strategy],
                                tp_pip_amount=tp_pip_amount,
                                sl_pip_amount=sl_pip_amount,
                                units=units,
                            )
                            pending_order = self.account.create_order(order_schema)
                            self.add_to_pending_orders(pending_order, strategy)
                prev_exec = now.minute
                prev_1_entry = signals['1']
                prev_2_entry = signals['2']
            if account_summary['openTradeCount'] > 0 or account_summary['openPositionCount'] > 0:
                open_trades = self.account.get_open_trades()
                self.check_and_partially_close(open_trades, check_pct=0.35, close_pct=0.5, partial_close_count=1)
                self.check_and_partially_close(open_trades, check_pct=0.65, close_pct=0.7, partial_close_count=2)
                self.check_and_adjust_stops(open_trades, check_pct=0.35, move_pct=0.01, adjusted_count=1)
                self.check_and_adjust_stops(open_trades, check_pct=0.65, move_pct=0.35, adjusted_count=2)


if __name__ == '__main__':
    s = SSLMultiTimeFrame(
        Account(account_id=DEMO_V20_ACCOUNT_NUMBER, access_token=DEMO_ACCESS_TOKEN, account_type='DEMO_API')
    )
    # s.execute()
    summary = s.account.get_summary()
    print(summary)
