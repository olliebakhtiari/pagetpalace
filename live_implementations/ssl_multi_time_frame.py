# Python standard.
import concurrent.futures
import datetime
import math
from typing import List, Dict, Union

# Third-party.
import pytz
import pandas as pd

# Local.
from src.oanda_account import OandaAccount
from src.oanda_pricing import OandaPricingData
from src.oanda_orders import create_market_if_touched_order
from src.indicators import get_ssl_value, append_average_true_range
from src.oanda_instrument import OandaInstrumentData
from settings import DEMO_V20_ACCOUNT_NUMBER, DEMO_ACCESS_TOKEN
from tools.logger import *


class SSLMultiTimeFrame:
    UNRESTRICTED_MARGIN_CAP = 0.9
    MARGIN_RATIO = 20

    def __init__(self, account: OandaAccount):
        self.account = account
        self._pricing = OandaPricingData(
            account_id=account.account_id,
            access_token=account.access_token,
            account_type=account.account_type,
        )
        self._pending_orders_1 = []
        self._pending_orders_2 = []
        self._partially_closed_1 = []
        self._partially_closed_2 = []
        self._sl_adjusted_1 = []
        self._sl_adjusted_2 = []
        self._last_spx500_gbp_price = 2450  # Set rough fall back price if can't get latest.

    def check_and_adjust_stops(
            self,
            prices: Dict[str, float],
            open_trades: List[dict],
            check_pct: float,
            move_pct: float,
            adjusted_count: int,
    ):
        ids_already_processed = self._sl_adjusted_1.copy() if adjusted_count == 1 else self._sl_adjusted_2.copy()
        for trade in open_trades:
            if trade['id'] not in ids_already_processed and self._check_pct_hit(prices, trade, check_pct):
                new_stop_loss_price = self._calculate_new_sl_price(trade=trade, pct=move_pct)
                s.account.update_stop_loss(trade_specifier=trade['id'], price=new_stop_loss_price)
                getattr(self, f'_sl_adjusted_{adjusted_count}').append(trade['id'])

    def check_and_partially_close(
            self,
            prices: Dict[str, float],
            open_trades: List[dict],
            check_pct: float,
            close_pct: float,
            partial_close_count: int,
    ):
        ids_processed = self._partially_closed_1.copy() if partial_close_count == 1 else self._partially_closed_1.copy()
        for trade in open_trades:
            if trade not in ids_processed and self._check_pct_hit(prices, trade, check_pct):
                pct_of_units = round(float(trade['currentUnits']) * close_pct)
                to_close = pct_of_units if pct_of_units > 1 else 1
                self.account.close_trade(trade_specifier=trade['id'], close_amount=str(to_close))
                getattr(self, f'_partially_closed_{partial_close_count}').append(trade['id'])

    def add_id_to_pending_orders(self, order: dict, strategy: str):
        getattr(self, f'_pending_orders_{strategy}').append(order['orderCreateTransaction']['id'])

    def sync_pending_orders(self, pending_orders_in_account: List[dict]):
        ids_in_account = [p_o['id'] for p_o in pending_orders_in_account]
        for local_pending in [self._pending_orders_1, self._pending_orders_2]:
            for id_ in local_pending:
                if id_ not in ids_in_account:
                    local_pending.remove(id_)

    def clean_local_lists(self, open_trade_ids: List[str]):
        for locals_ in [self._partially_closed_1, self._partially_closed_2, self._sl_adjusted_1, self._sl_adjusted_2]:
            for id_ in locals_:
                if id_ not in open_trade_ids:
                    locals_.remove(id_)

    def clear_pending_orders(self, strategy: str):
        for id_ in getattr(self, f'_pending_orders_{strategy}'):
            self.account.cancel_order(id_)

    def get_unit_size_per_trade(self, account_data: dict) -> float:
        balance = float(account_data['balance'])
        margin_size = self._get_valid_margin_size(
            margin_size=(balance * self.UNRESTRICTED_MARGIN_CAP) / 1.75,
            usable_margin=self._margin_not_being_used_in_orders(account_data),
            balance=balance,
        )
        units_to_place = self._convert_gbp_to_max_num_units(margin_size)

        return units_to_place if units_to_place < 10000 else 10000

    def get_prices_to_check(self) -> Dict[str, float]:
        latest_5s_prices = self._pricing.get_latest_candles('SPX500_USD:S5:AB')['latestCandles'][0]['candles'][-1]

        return {'ask_low': float(latest_5s_prices['ask']['l']), 'bid_high': float(latest_5s_prices['bid']['h'])}

    def _check_pct_hit(self, prices: Dict[str, float], trade: dict, pct: float) -> bool:
        has_hit = False
        if int(trade['currentUnits']) > 0:
            has_hit = self._check_long_pct_hit(prices['bid_high'], trade, pct)
        elif int(trade['currentUnits']) < 0:
            has_hit = self._check_short_pct_hit(prices['ask_low'], trade, pct)

        return has_hit

    def _check_long_pct_hit(self, price: float, trade: dict, pct: float):
        return price >= round((float(trade['price']) + self._get_long_trade_pct_target_pips(trade, pct)), 1)

    def _check_short_pct_hit(self, price: float, trade: dict, pct: float):
        return price <= round((float(trade['price']) - self._get_short_trade_pct_target_pips(trade, pct)), 1)

    def _calculate_new_sl_price(self, trade: dict, pct: float) -> float:
        price = trade['price']
        if int(trade['currentUnits']) > 0:
            price = self._calculate_new_long_sl(trade, pct)
        elif int(trade['currentUnits']) < 0:
            price = self._calculate_new_short_sl(trade, pct)

        return float(price)

    def _calculate_new_long_sl(self, trade: dict, pct: float) -> float:
        return float(trade['price']) + self._get_long_trade_pct_target_pips(trade, pct)

    def _calculate_new_short_sl(self, trade: dict, pct: float) -> float:
        return float(trade['price']) - self._get_short_trade_pct_target_pips(trade, pct)

    def _margin_not_being_used_in_orders(self, account_data: dict) -> float:
        units_pending = 0
        for order in account_data['orders']:
            units_in_order = order.get('units')
            if units_in_order:
                units_pending += abs(int(units_in_order))
        available = float(account_data['marginAvailable']) - self._convert_units_to_gbp(units_pending)

        return available if available > 0 else 0.

    def _get_latest_spx500_gbp_price(self, retry_count: int = 0) -> float:
        price = self._last_spx500_gbp_price
        spx500_gbp = self._pricing.get_pricing_info(instruments=['SPX500_GBP'], include_home_conversions=False)
        if not len(spx500_gbp['prices']) and retry_count < 5:
            self._get_latest_spx500_gbp_price(retry_count=retry_count + 1)
        elif len(spx500_gbp['prices']):
            price = spx500_gbp['prices'][0]['asks'][0]['price']
            self._last_spx500_gbp_price = price

        return float(price)

    def _convert_units_to_gbp(self, units: int) -> float:
        return round((self._get_latest_spx500_gbp_price() * units) / self.MARGIN_RATIO, 4)

    def _convert_gbp_to_max_num_units(self, margin: float) -> int:
        return math.floor((margin * self.MARGIN_RATIO) / self._get_latest_spx500_gbp_price())

    @classmethod
    def _get_long_trade_pct_target_pips(cls, trade: dict, pct: float) -> float:
        return (float(trade['takeProfitOrder']['price']) - float(trade['price'])) * pct

    @classmethod
    def _get_short_trade_pct_target_pips(cls, trade: dict, pct: float) -> float:
        return (float(trade['price']) - float(trade['takeProfitOrder']['price'])) * pct

    @classmethod
    def _get_valid_margin_size(cls, margin_size: float, usable_margin: float, balance: float) -> float:
        available_minus_restricted = usable_margin - (balance * 0.1)
        if (margin_size > available_minus_restricted) and (available_minus_restricted < 200):
            margin_size = 0
        elif (margin_size > available_minus_restricted) and (available_minus_restricted >= 200):
            margin_size = available_minus_restricted

        return margin_size

    @classmethod
    def get_data(cls) -> Dict[str, pd.DataFrame]:
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
    def get_atr_values(cls, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        append_average_true_range(data['H1'])
        append_average_true_range(data['M5'])

        return {
            '1': data['H1']['ATR'].iloc[-1],
            '2': data['M5']['ATR'].iloc[-1],
        }

    @classmethod
    def get_signals(cls, data: Dict[str, pd.DataFrame]) -> Dict[str, Union[str, None]]:
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
    def construct_order(cls,
                        signal: str,
                        ask_high: float,
                        bid_low: float,
                        entry_offset: float,
                        worst_price_bound_offset: float,
                        tp_pip_amount: float,
                        sl_pip_amount: float,
                        units: float) -> dict:
        entry = None
        sl = None
        tp = None
        price_bound = None
        if signal == 'long':
            entry = round(ask_high + entry_offset, 1)
            tp = round(entry + tp_pip_amount, 1)
            sl = round(entry - sl_pip_amount, 1)
            price_bound = round(entry + worst_price_bound_offset, 1)
        elif signal == 'short':
            entry = round(bid_low - entry_offset, 1)
            tp = round(entry - tp_pip_amount, 1)
            sl = round(entry + sl_pip_amount, 1)
            price_bound = round(entry - worst_price_bound_offset, 1)
            units = units * -1

        return create_market_if_touched_order(entry, price_bound, sl, tp, 'SPX500_USD', units)

    def execute(self):
        london_tz = pytz.timezone('Europe/London')
        prev_exec = -1
        prev_1_entry = ''
        prev_2_entry = ''
        while 1:
            now = datetime.datetime.now().astimezone(london_tz)
            full_account_details = s.account.get_full_account_details()['account']
            pending_orders = full_account_details['orders']
            self.sync_pending_orders(pending_orders)
            if now.minute % 5 == 0 and now.minute != prev_exec:
                data = self.get_data()
                signals = self.get_signals(data)
                strategy_atr_values = self.get_atr_values(data)
                print(now, signals)
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
                        self.clear_pending_orders(strategy=strategy_num)
                # New orders.
                for strategy, signal in signals.items():
                    compare_signals = entry_signals_to_check[strategy]
                    units = self.get_unit_size_per_trade(full_account_details)
                    if units \
                            and signal \
                            and compare_signals['previous'] != compare_signals['current']:
                        sl_pip_amount = strategy_atr_values[strategy] * 3.25
                        if units > 0:
                            tp_pip_amount = sl_pip_amount * 2.
                            order_schema = self.construct_order(
                                signal=signal,
                                ask_high=float(data['M5']['askHigh'].values[-1]),
                                bid_low=float(data['M5']['bidLow'].values[-1]),
                                entry_offset=strategy_atr_values[strategy] / 5,
                                worst_price_bound_offset=strategy_atr_values[strategy] / 2,
                                tp_pip_amount=tp_pip_amount,
                                sl_pip_amount=sl_pip_amount,
                                units=units,
                            )
                            pending_order = self.account.create_order(order_schema)
                            print(pending_order)
                            self.add_id_to_pending_orders(pending_order, strategy)
                            print(s._pending_orders_1, s._pending_orders_2)
                            print(s._sl_adjusted_1, s._sl_adjusted_2)
                            print(s._partially_closed_1, s._partially_closed_2)
                prev_exec = now.minute
                prev_1_entry = signals['1']
                prev_2_entry = signals['2']

            # Monitor and adjust current trades, if any.
            if int(full_account_details['openTradeCount']) > 0:
                open_trades = s.account.get_open_trades()['trades']
                prices_to_check = self.get_prices_to_check()
                for args in [(0.35, 0.5, 1), (0.65, 0.7, 2)]:
                    self.check_and_partially_close(
                        prices=prices_to_check,
                        open_trades=open_trades,
                        check_pct=args[0],
                        close_pct=args[1],
                        partial_close_count=args[2],
                    )
                for args in [(0.35, 0.01, 1), (0.65, 0.35, 2)]:
                    self.check_and_adjust_stops(
                        prices=prices_to_check,
                        open_trades=open_trades,
                        check_pct=args[0],
                        move_pct=args[1],
                        adjusted_count=args[2],
                    )
            if now.hour % 24 == 0:
                open_trade_ids = [t['id'] for t in full_account_details['trades']]
                self.clean_local_lists(open_trade_ids)


if __name__ == '__main__':
    s = SSLMultiTimeFrame(
        OandaAccount(account_id=DEMO_V20_ACCOUNT_NUMBER, access_token=DEMO_ACCESS_TOKEN, account_type='DEMO_API')
    )
    s.execute()

