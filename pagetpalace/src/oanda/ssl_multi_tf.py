# Python standard.
import abc
import concurrent.futures
import math
import sys
from typing import List, Dict

# Third-party.
import pandas as pd
from pagetpalace.src.oanda import OandaPricingData, create_stop_order, OandaInstrumentData, OandaAccount
from pagetpalace.src.oanda.calculations import calculate_new_sl_price, check_pct_hit
from pagetpalace.src.indicators import append_ssl_channel
from pagetpalace.tools.logger import *


class SSLMultiTimeFrame:
    def __init__(
            self,
            account: OandaAccount,
            instrument: str,
            margin_ratio: int,
            unrestricted_margin_cap: float,
            strategy_multipliers: dict,
            open_trade_params: dict,
            boundary_multipliers: dict,
            time_frames: List[str],
    ):
        """
        _STRATEGY_MULTIPLIERS = {
            '1': {'long': {'sl': 3, 'tp': 4}, 'short': {'sl': 2.5, 'tp': 2.5}},
            '2': {'long': {'sl': 3.5, 'tp': 3.5}},
        }
        _PARAMS = {
            'check_1': 0.35,
            'check_2': 0.65,
            'sl_move_1': 0.01,
            'sl_move_2': 0.35,
            'close_amount_1': 0.5,
            'close_amount_2': 0.7,
        }
        _BOUNDARY_MULTIPLIERS = {
            'margin_adjustment': {'1': {'long': {'above': 2, 'below': 3}, 'short': {'above': 1.25, 'below': 3.5}}},
            'reverse': {'1': {'short': {'below': 2}}}
        }
        """
        self._account = account
        self._instrument = instrument
        self._margin_ratio = margin_ratio
        self._unrestricted_margin_cap = unrestricted_margin_cap
        self._strategy_multipliers = strategy_multipliers
        self._open_trade_params = open_trade_params
        self._boundary_multipliers = boundary_multipliers
        self._time_frames = time_frames
        self._pricing = OandaPricingData(account.access_token, account.account_id, account.account_type)
        self._pending_orders_1 = []
        self._pending_orders_2 = []
        self._partially_closed_1 = []
        self._partially_closed_2 = []
        self._sl_adjusted_1 = []
        self._sl_adjusted_2 = []
        self._last_price = 0

    def _get_prices_to_check(self) -> Dict[str, float]:
        latest_5s_prices = self._pricing.get_latest_candles(f'{self._instrument}:S5:AB')['latestCandles'][0]['candles'][-1]

        return {'ask_low': float(latest_5s_prices['ask']['l']), 'bid_high': float(latest_5s_prices['bid']['h'])}

    def _check_and_adjust_stops(
            self,
            prices: Dict[str, float],
            open_trades: List[dict],
            check_pct: float,
            move_pct: float,
            adjusted_count: int,
    ):
        ids_already_processed = self._sl_adjusted_1.copy() if adjusted_count == 1 else self._sl_adjusted_2.copy()
        for trade in open_trades:
            if trade['id'] not in ids_already_processed and check_pct_hit(prices, trade, check_pct):
                new_stop_loss_price = calculate_new_sl_price(trade=trade, pct=move_pct)
                self._account.update_stop_loss(trade_specifier=trade['id'], price=new_stop_loss_price)
                getattr(self, f'_sl_adjusted_{adjusted_count}').append(trade['id'])

    def check_and_partially_close(
            self,
            prices: Dict[str, float],
            open_trades: List[dict],
            check_pct: float,
            close_pct: float,
            partial_close_count: int,
    ):
        ids_processed = self._partially_closed_1.copy() if partial_close_count == 1 else self._partially_closed_2.copy()
        for trade in open_trades:
            if trade['id'] not in ids_processed and check_pct_hit(prices, trade, check_pct):
                pct_of_units = round(abs(float(trade['currentUnits'])) * close_pct)
                to_close = pct_of_units if pct_of_units > 1 else 1
                self._account.close_trade(trade_specifier=trade['id'], close_amount=str(to_close))
                getattr(self, f'_partially_closed_{partial_close_count}').append(trade['id'])

    def add_id_to_pending_orders(self, order: dict, strategy: str):
        getattr(self, f'_pending_orders_{strategy}').append(order['orderCreateTransaction']['id'])

    def sync_pending_orders(self, pending_orders_in_account: List[dict]):
        ids_in_account = [p_o['id'] for p_o in pending_orders_in_account]
        for local_pending in [self._pending_orders_1, self._pending_orders_2]:
            for id_ in local_pending:
                if id_ not in ids_in_account:
                    local_pending.remove(id_)

    def _clean_local_lists(self, open_trade_ids: List[str]):
        for locals_ in [self._partially_closed_1, self._partially_closed_2, self._sl_adjusted_1, self._sl_adjusted_2]:
            for id_ in locals_:
                if id_ not in open_trade_ids:
                    locals_.remove(id_)

    def clean_lists(self):
        try:
            open_trade_ids = [t['id'] for t in self._account.get_open_trades()['trades']]
            self._clean_local_lists(open_trade_ids)
        except Exception as exc:
            logger.info(f'Failed to clean lists. {exc}', exc_info=True)

    def _clear_pending_orders(self, strategy: str):
        for id_ in getattr(self, f'_pending_orders_{strategy}'):
            self._account.cancel_order(id_)
        getattr(self, f'_pending_orders_{strategy}').clear()

    def check_and_clear_pending_orders(self, entry_signals_to_check: Dict[str, Dict[str, str]]):
        for strategy_num, entry_signals in entry_signals_to_check.items():
            if entry_signals['previous'] != entry_signals['current']:
                try:
                    self._clear_pending_orders(strategy=strategy_num)
                except Exception as exc:
                    logger.error(f'Failed to clear pending order for strategy {strategy_num}.  {exc}', exc_info=True)

    def _check_and_adjust_stop_losses(self, prices_to_check: Dict[str, float], open_trades: List[dict]):
        try:
            sl_adjust_args = [
                (self._open_trade_params['check_1'], self._open_trade_params['sl_move_1'], 1),
                (self._open_trade_params['check_2'], self._open_trade_params['sl_move_2'], 2),
            ]
            for args in sl_adjust_args:
                self._check_and_adjust_stops(
                    prices=prices_to_check,
                    open_trades=open_trades,
                    check_pct=args[0],
                    move_pct=args[1],
                    adjusted_count=args[2],
                )
        except Exception as exc:
            logger.error(f'Failed to check and adjust stop losses. {exc}', exc_info=True)

    def _check_and_partially_close(self, prices_to_check: Dict[str, float], open_trades: List[dict]):
        try:
            partial_close_args = [
                (self._open_trade_params['check_1'], self._open_trade_params['close_amount_1'], 1),
                (self._open_trade_params['check_2'], self._open_trade_params['close_amount_2'], 2),
            ]
            for args in partial_close_args:
                self.check_and_partially_close(
                    prices=prices_to_check,
                    open_trades=open_trades,
                    check_pct=args[0],
                    close_pct=args[1],
                    partial_close_count=args[2],
                )
        except Exception as exc:
            logger.error(f'Failed to check and partially close trades. {exc}', exc_info=True)

    def monitor_and_adjust_current_trades(self):
        try:
            open_trades = self._account.get_open_trades()['trades']
            if len(open_trades) > 0:
                prices_to_check = self._get_prices_to_check()
                self._check_and_partially_close(prices_to_check=prices_to_check, open_trades=open_trades)
                self._check_and_adjust_stop_losses(prices_to_check=prices_to_check, open_trades=open_trades)
        except Exception as exc:
            logger.error(f'Failed to monitor and adjust current trades. {exc}', exc_info=True)

    def get_unit_size_per_trade(self, account_data: dict) -> float:
        balance = float(account_data['balance'])
        margin_size = self._get_valid_margin_size(
            margin_size=(balance * self._unrestricted_margin_cap) / 1.75,
            usable_margin=self._margin_not_being_used_in_orders(account_data),
            balance=balance,
        )
        units_to_place = self._convert_gbp_to_max_num_units(margin_size)

        return units_to_place if units_to_place < 10000 else 10000

    def _margin_not_being_used_in_orders(self, account_data: dict) -> float:
        units_pending = 0
        for order in account_data['orders']:
            units_in_order = order.get('units')
            if units_in_order:
                units_pending += abs(int(units_in_order))
        available = float(account_data['marginAvailable']) - self._convert_units_to_gbp(units_pending)

        return available if available > 0 else 0.

    def _get_latest_instrument_price(self, retry_count: int = 0) -> float:
        price = self._last_price
        latest_price = self._pricing.get_pricing_info(instruments=[self._instrument], include_home_conversions=False)
        if not len(latest_price['prices']) and retry_count < 5:
            self._get_latest_instrument_price(retry_count=retry_count + 1)
        elif len(latest_price['prices']):
            price = latest_price['prices'][0]['asks'][0]['price']
            self._last_price = price

        return float(price)

    def _convert_units_to_gbp(self, units: int) -> float:
        return round((self._get_latest_instrument_price() * units) / self._margin_ratio, 4)

    def _convert_gbp_to_max_num_units(self, margin: float) -> int:
        return math.floor((margin * self._margin_ratio) / self._get_latest_instrument_price())

    @classmethod
    def _get_valid_margin_size(cls, margin_size: float, usable_margin: float, balance: float) -> float:
        available_minus_restricted = usable_margin - (balance * 0.1)
        if (margin_size > available_minus_restricted) and (available_minus_restricted < 200):
            margin_size = 0
        elif (margin_size > available_minus_restricted) and (available_minus_restricted >= 200):
            margin_size = available_minus_restricted

        return margin_size

    def get_data(self) -> Dict[str, pd.DataFrame]:
        od = OandaInstrumentData()
        data = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_tf = {}
            for granularity in self._time_frames:
                future_to_tf[
                    executor.submit(od.get_complete_candlesticks, self._instrument, 'ABM', granularity, 1000)
                ] = granularity
            for future in concurrent.futures.as_completed(future_to_tf):
                time_frame = future_to_tf[future]
                try:
                    data[time_frame] = od.convert_to_df(future.result(), 'ABM')
                except ConnectionError as exc:
                    logger.error(
                        f'Failed to retrieve Oanda candlestick data for time frame: {time_frame}. {exc}',
                        exc_info=True,
                    )
                    return {}

        return data

    @classmethod
    def _calculate_atr_factor(cls, price: float, smoothed_ma: float, atr_value: float) -> float:
        return abs((price - smoothed_ma) / atr_value)

    def _calculate_boundary(self,
                            type_: str,
                            bias: str,
                            atr_value: float,
                            smoothed_ma: float,
                            price: float,
                            strategy: str) -> float:
        try:
            if price >= smoothed_ma:
                boundary = self._boundary_multipliers[type_][strategy][bias]['above'] * atr_value
            else:
                boundary = self._boundary_multipliers[type_][strategy][bias]['below'] * atr_value
        except KeyError:  # Not interested in these situations, don't trade.
            boundary = sys.maxsize

        return boundary

    def is_within_valid_boundary(self,
                                 bias: str,
                                 atr_value: float,
                                 smoothed_ma: float,
                                 price: float,
                                 strategy: str) -> bool:
        boundary = self._calculate_boundary('margin_adjustment', bias, atr_value, smoothed_ma, price, strategy)

        return not (self._calculate_atr_factor(price, smoothed_ma, atr_value) * atr_value > boundary)

    def calculate_distance_factor(self,
                                  bias: str,
                                  atr_value: float,
                                  smoothed_ma: float,
                                  price: float,
                                  strategy: str) -> bool:
        boundary = self._calculate_boundary('reverse', bias, atr_value, smoothed_ma, price, strategy)

        return self._calculate_atr_factor(price, smoothed_ma, atr_value) * atr_value >= boundary

    def construct_order(self,
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

        return create_stop_order(entry, price_bound, sl, tp, self._instrument, units)

    def get_ssl_values(self, data: Dict[str, pd.DataFrame]) -> Dict[str, int]:
        for df in data.values():
            append_ssl_channel(df)

        return {tf: data[tf].iloc[-1]['HighLowValue'] for tf in self._time_frames}

    @abc.abstractmethod
    def is_reverse_trade_long_criteria_met(self) -> bool:
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def get_atr_values(self, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def get_ssma_values(self) -> Dict[str, float]:
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def get_signals(self) -> Dict[str, str]:
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def execute(self):
        """ Run the complete strategy. """
        raise NotImplementedError('Not implemented in subclass.')
