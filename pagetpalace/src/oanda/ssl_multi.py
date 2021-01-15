# Python standard.
import abc
import concurrent.futures
import math
import sys
from typing import List, Dict

# Local.
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.indicators import append_ssl_channel
from pagetpalace.src.oanda import create_stop_order, OandaAccount, OandaInstrumentData, OandaPricingData
from pagetpalace.src.oanda.live_trade_monitor import LiveTradeMonitor
from pagetpalace.src.risk_manager import RiskManager
from pagetpalace.tools.logger import *


class SSLMultiTimeFrame:

    def __init__(
            self,
            equity_split: float,
            unrestricted_margin_cap: float,
            account: OandaAccount,
            pricing_data_retriever: OandaPricingData,
            instrument: Instrument,
            time_frames: List[str],
            entry_timeframe: str,
            sub_strategies_count: int,
            boundary_multipliers: dict,
            live_trade_monitor: LiveTradeMonitor,
            trade_multipliers: dict = None,
            ssl_periods: int = 20,
    ):
        """
            boundary_multipliers = {
                'continuation': {
                    'D': {'long': {'above': 100, 'below': 100}, 'short': {'above': 100, 'below': 100}},
                    'M5': {'long': {'above': 100, 'below': 100}, 'short': {'above': 100, 'below': 100}},
                },
                'reverse': {
                    'H1': {'long': {'above': 0}, 'short': {'below': 0}},
                }
            }
            trade_multipliers = {
                '1': {'long': {'sl': 2, 'tp': 2}, 'short': {sl': 2, 'tp': 2}},
                '2': {'long': {'sl': 2, 'tp': 2}, 'short': {'sl': 2, 'tp': 2}},
                '3': {'long': {'sl': 2, 'tp': 2}, 'short': {'sl': 2, 'tp': 2}},
                '4': {'long': {'sl': 2, 'tp': 2}, 'short': {'sl': 2, 'tp': 2}},
            }
        """
        self.ssl_periods = ssl_periods
        self.equity_split = equity_split
        self.unrestricted_margin_cap = unrestricted_margin_cap
        self.account = account
        self.instrument = instrument
        self.time_frames = time_frames
        self.entry_timeframe = entry_timeframe
        self.sub_strategies_count = sub_strategies_count
        self.trade_multipliers = trade_multipliers
        self.boundary_multipliers = boundary_multipliers
        self._pricing = pricing_data_retriever
        self._pending_orders = {str(i + 1): [] for i in range(sub_strategies_count)}
        self._latest_price = 0
        init_empty = {tf: 0 for tf in self.time_frames}
        self._latest_data = {}
        self._current_ssl_values = init_empty
        self._previous_ssl_values = init_empty
        self._atr_values = {}
        self._ssma_values = {}
        self._entry_signals = {}
        self._live_trade_monitor = live_trade_monitor
        self._risk_manager = RiskManager(self.instrument)

    def _add_id_to_pending_orders(self, order: dict, strategy: str):
        self._pending_orders[strategy].append(order['orderCreateTransaction']['id'])

    def _sync_pending_orders(self, pending_orders_in_account: List[dict]):
        ids_in_account = [p_o['id'] for p_o in pending_orders_in_account]
        for local_pending in self._pending_orders.values():
            for id_ in local_pending:
                if id_ not in ids_in_account:
                    local_pending.remove(id_)

    def _clear_pending_orders(self):
        for orders in list(self._pending_orders.values()):
            for id_ in orders:
                self.account.cancel_order(id_)
        for key in list(self._pending_orders.keys()):
            self._pending_orders[key].clear()

    def _check_and_clear_pending_orders(self):
        if self._has_new_signal():
            try:
                self._clear_pending_orders()
            except Exception as exc:
                logger.error(f'Failed to clear pending orders. {exc}', exc_info=True)

    def _get_latest_instrument_price(self, symbol: str, retry_count: int = 0) -> float:
        price = self._latest_price
        latest_price = self._pricing.get_pricing_info([self.instrument.symbol], include_home_conversions=False)
        if not len(latest_price['prices']) and retry_count < 5:
            self._get_latest_instrument_price(symbol, retry_count=retry_count + 1)
        elif len(latest_price['prices']):
            price = float(latest_price['prices'][0]['asks'][0]['price'])
            self._latest_price = price

        return price

    def _convert_units_to_gbp(self, units: int) -> float:
        if self.instrument.base_currency == self.account.ACCOUNT_CURRENCY:
            return round(units / self.instrument.leverage, 4)

        return round((self._get_latest_instrument_price(self.instrument.symbol) * units) / self.instrument.leverage, 4)

    def _convert_gbp_to_max_num_units(self, margin: float) -> int:
        if self.instrument.base_currency == self.account.ACCOUNT_CURRENCY:
            return math.floor(margin * self.instrument.leverage)

        return math.floor((margin * self.instrument.leverage) / self._get_latest_instrument_price(self.instrument.symbol))

    def _get_unit_size_of_trade(self, account_data: dict) -> float:
        return self._convert_gbp_to_max_num_units(self._get_valid_margin_size(account_data))

    def _margin_not_being_used_in_orders(self, account_data: dict) -> float:
        units_pending = 0
        for order in account_data['orders']:
            units_in_order = order.get('units')
            if units_in_order:
                units_pending += abs(int(units_in_order))
        available = float(account_data['marginAvailable']) - self._convert_units_to_gbp(units_pending)

        return available if available > 0 else 0.

    @classmethod
    def _adjust_according_to_restricted_margin(cls, margin_size: float, available_minus_restricted: float) -> float:
        if (margin_size > available_minus_restricted) and (available_minus_restricted < 200):
            margin_size = 0
        elif (margin_size > available_minus_restricted) and (available_minus_restricted >= 200):
            margin_size = available_minus_restricted

        return margin_size

    def _get_valid_margin_size(self, account_data: dict) -> float:
        balance = float(account_data['balance'])
        margin_size = (balance * self.unrestricted_margin_cap) / self.equity_split
        available_minus_restricted = self._margin_not_being_used_in_orders(account_data) \
                                     - (balance * (1 - self.unrestricted_margin_cap))

        return self._adjust_according_to_restricted_margin(margin_size, available_minus_restricted)

    def _construct_order(self,
                         signal: str,
                         last_close_price: float,
                         entry_offset: float,
                         worst_price_bound_offset: float,
                         tp_pip_amount: float,
                         sl_pip_amount: float,
                         units: float) -> dict:
        precision = self.instrument.price_precision
        units = self._risk_manager.calculate_unit_size_within_max_risk(
            float(self.account.get_full_account_details()['account']['balance']),
            units,
            last_close_price,
            sl_pip_amount
        )
        if signal == 'long':
            entry = round(last_close_price + entry_offset, precision)
            tp = round(entry + tp_pip_amount, precision)
            sl = round(entry - sl_pip_amount, precision)
            price_bound = round(entry + worst_price_bound_offset, precision)
        elif signal == 'short':
            entry = round(last_close_price - entry_offset, precision)
            tp = round(entry - tp_pip_amount, precision)
            sl = round(entry + sl_pip_amount, precision)
            price_bound = round(entry - worst_price_bound_offset, precision)
            units = units * -1
        else:
            raise ValueError('Invalid signal received.')

        return create_stop_order(entry, price_bound, sl, tp, self.instrument.symbol, units)

    def _place_pending_order(
            self,
            price_to_offset_from: float,
            entry_offset: float,
            sl_pip_amount: float,
            tp_pip_amount: float,
            strategy: str,
            signal: str,
            units: float,
    ):
        order_schema = self._construct_order(
            signal=signal,
            last_close_price=price_to_offset_from,
            entry_offset=entry_offset,
            worst_price_bound_offset=self._atr_values[self.entry_timeframe] / 2,
            tp_pip_amount=tp_pip_amount,
            sl_pip_amount=sl_pip_amount,
            units=units,
        )
        pending_order = self.account.create_order(order_schema)
        self._add_id_to_pending_orders(pending_order, strategy)
        logger.info(f'pending order placed: {pending_order}')
        logger.info(f'pending_orders: {self._pending_orders}')
        logger.info(f'sl_adjusted: {self._live_trade_monitor.sl_adjusted}')
        logger.info(f'partially_closed: {self._live_trade_monitor.partially_closed}')

    def _calculate_atr_factor(self, price: float, timeframe: str) -> float:
        return abs((price - self._ssma_values[timeframe]) / self._atr_values[timeframe])

    def _calculate_boundary(self, type_: str, bias: str, price: float, timeframe: str) -> float:
        try:
            if price >= self._ssma_values[timeframe]:
                boundary = self.boundary_multipliers[type_][timeframe][bias]['above'] * self._atr_values[timeframe]
            else:
                boundary = self.boundary_multipliers[type_][timeframe][bias]['below'] * self._atr_values[timeframe]
        except KeyError:  # Not interested in these situations, don't trade.
            boundary = sys.maxsize

        return boundary

    def _is_within_valid_boundary(self, bias: str, price: float, timeframe: str) -> bool:
        return not (self._calculate_atr_factor(price, timeframe) * self._atr_values[timeframe]
                    > self._calculate_boundary('continuation', bias, price, timeframe))

    def _has_met_reverse_trade_condition(self, bias: str, price: float, timeframe: str) -> bool:
        return self._calculate_atr_factor(price, timeframe) * self._atr_values[timeframe] \
               >= self._calculate_boundary('reverse', bias, price, timeframe)

    def _update_latest_data(self):
        od = OandaInstrumentData()
        data = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_tf = {}
            for granularity in self.time_frames:
                future_to_tf[
                    executor.submit(od.get_complete_candlesticks, self.instrument.symbol, 'ABM', granularity, 1000)
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
                    self._latest_data = {}
                    return
        self._latest_data = data

    @abc.abstractmethod
    def _update_atr_values(self):
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def _update_ssma_values(self):
        raise NotImplementedError('Not implemented in subclass.')

    def _update_current_ssl_values(self):
        for df in self._latest_data.values():
            append_ssl_channel(df, periods=self.ssl_periods)
        self._current_ssl_values = {
            tf: self._latest_data[tf].iloc[-1][f'HighLowValue_{self.ssl_periods}_period'] for tf in self.time_frames
        }

    def _update_previous_ssl_values(self):
        self._previous_ssl_values = {tf: self._current_ssl_values[tf] for tf in self.time_frames}

    def _update_entry_signals(self):
        self._entry_signals = {
            'previous': self._previous_ssl_values[self.entry_timeframe],
            'current': self._current_ssl_values[self.entry_timeframe],
        }

    def _has_new_signal(self) -> bool:
        return self._entry_signals['previous'] != self._entry_signals['current']

    def _update_current_indicators_and_signals(self):
        self._update_atr_values()
        self._update_ssma_values()
        self._update_current_ssl_values()
        self._update_entry_signals()

    @abc.abstractmethod
    def _get_signals(self, **kwargs) -> Dict[str, str]:
        raise NotImplementedError('Not implemented in subclass.')

    def _log_latest_values(self, now, signals):
        logger.info(f'ssl values: {self._current_ssl_values}')
        logger.info(f'ssma values: {self._ssma_values}')
        logger.info(f'atr values: {self._atr_values}')
        logger.info(f'{now} signals: {signals}')

    @abc.abstractmethod
    def execute(self):
        """ Run the complete strategy. """
        raise NotImplementedError('Not implemented in subclass.')
