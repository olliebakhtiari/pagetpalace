# Python standard.
import abc
import concurrent.futures
import math
import sys
from typing import List, Dict

# Third-party.
from pagetpalace.src.indicators import append_ssl_channel
from pagetpalace.src.oanda import OandaPricingData, create_stop_order, OandaInstrumentData, OandaAccount
from pagetpalace.src.oanda.calculations import calculate_new_sl_price, check_pct_hit
from pagetpalace.tools.logger import *


class SSLMultiTimeFrame:

    def __init__(
            self,
            equity_split: float,
            margin_ratio: int,
            unrestricted_margin_cap: float,
            account: OandaAccount,
            instrument: str,
            time_frames: List[str],
            entry_timeframe: str,
            sub_strategies_count: int,
            trade_multipliers: dict,
            boundary_multipliers: dict,
            stop_loss_move_params: dict = None,
            partial_closure_params: dict = None,
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
            stop_loss_move_params = {1: {'check': 0.35, 'move': 0.01}}
            partial_close_params = {1: {'check': 0.35, 'close': 0.5}}
        """
        self.equity_split = equity_split
        self.margin_ratio = margin_ratio
        self.unrestricted_margin_cap = unrestricted_margin_cap
        self.account = account
        self.instrument = instrument
        self.time_frames = time_frames
        self.entry_timeframe = entry_timeframe
        self.sub_strategies_count = sub_strategies_count
        self.trade_multipliers = trade_multipliers
        self.boundary_multipliers = boundary_multipliers
        self.stop_loss_move_params = stop_loss_move_params
        self.partial_closure_params = partial_closure_params
        self._pricing = OandaPricingData(account.access_token, account.account_id, account.account_type)
        self._pending_orders = {str(i + 1): [] for i in range(sub_strategies_count)}
        self._partially_closed = {i: [] for i in range(len(self.partial_closure_params.keys()))}
        self._sl_adjusted = {i: [] for i in range(len(self.stop_loss_move_params.keys()))}
        self._latest_price = 0
        init_empty = {tf: 0 for tf in self.time_frames}
        self._latest_data = {}
        self._current_ssl_values = init_empty
        self._previous_ssl_values = init_empty
        self._atr_values = {}
        self._ssma_values = {}
        self._entry_signals = {}
        self.ssl_periods = ssl_periods

    def _get_prices_to_check(self) -> Dict[str, float]:
        latest_5s_prices = self._pricing.get_latest_candles(f'{self.instrument}:S5:AB')['latestCandles'][0]['candles'][-1]

        return {'ask_low': float(latest_5s_prices['ask']['l']), 'bid_high': float(latest_5s_prices['bid']['h'])}

    def _check_and_adjust_stops(
            self,
            prices: Dict[str, float],
            open_trades: List[dict],
            check_pct: float,
            move_pct: float,
            adjusted_count: int,
    ):
        ids_already_processed = self._sl_adjusted[adjusted_count].copy()
        for trade in open_trades:
            if trade['id'] not in ids_already_processed and check_pct_hit(prices, trade, check_pct):
                new_stop_loss_price = calculate_new_sl_price(trade=trade, pct=move_pct)
                self.account.update_stop_loss(trade_specifier=trade['id'], price=new_stop_loss_price)
                self._sl_adjusted[adjusted_count].append(trade['id'])

    def _check_and_partially_close(
            self,
            prices: Dict[str, float],
            open_trades: List[dict],
            check_pct: float,
            close_pct: float,
            partial_close_count: int,
    ):
        ids_processed = self._partially_closed[partial_close_count].copy()
        for trade in open_trades:
            if trade['id'] not in ids_processed and check_pct_hit(prices, trade, check_pct):
                pct_of_units = round(abs(float(trade['currentUnits'])) * close_pct)
                to_close = pct_of_units if pct_of_units > 1 else 1
                self.account.close_trade(trade_specifier=trade['id'], close_amount=str(to_close))
                self._partially_closed[partial_close_count].append(trade['id'])

    def _add_id_to_pending_orders(self, order: dict, strategy: str):
        self._pending_orders[strategy].append(order['orderCreateTransaction']['id'])

    def _sync_pending_orders(self, pending_orders_in_account: List[dict]):
        ids_in_account = [p_o['id'] for p_o in pending_orders_in_account]
        for local_pending in self._pending_orders.values():
            for id_ in local_pending:
                if id_ not in ids_in_account:
                    local_pending.remove(id_)

    def _clean_local_lists(self, open_trade_ids: List[str]):
        all_locals_lists = []
        all_locals_lists.extend(list(self._sl_adjusted.values()))
        all_locals_lists.extend(list(self._partially_closed.values()))
        for local_list in all_locals_lists:
            for id_ in local_list:
                if id_ not in open_trade_ids:
                    local_list.remove(id_)

    def _clean_lists(self):
        try:
            open_trade_ids = [t['id'] for t in self.account.get_open_trades()['trades']]
            self._clean_local_lists(open_trade_ids)
        except Exception as exc:
            logger.info(f'Failed to clean lists. {exc}', exc_info=True)

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
                logger.error(f'Failed to clear pending orders.  {exc}', exc_info=True)

    def _check_and_adjust_stop_losses(self, prices_to_check: Dict[str, float], open_trades: List[dict]):
        try:
            for count, values in self.stop_loss_move_params.values():
                self._check_and_adjust_stops(prices_to_check, open_trades, values['check'], values['move'], count)
        except Exception as exc:
            logger.error(f'Failed to check and adjust stop losses. {exc}', exc_info=True)

    def _partial_closures(self, prices_to_check: Dict[str, float], open_trades: List[dict]):
        try:
            for count, values in self.partial_closure_params.values():
                self._check_and_partially_close(prices_to_check, open_trades, values['check'], values['close'], count)
        except Exception as exc:
            logger.error(f'Failed to check and partially close trades. {exc}', exc_info=True)

    def _monitor_and_adjust_current_trades(self):
        try:
            open_trades = self.account.get_open_trades()['trades']
            if len(open_trades) > 0:
                prices_to_check = self._get_prices_to_check()
                self._partial_closures(prices_to_check=prices_to_check, open_trades=open_trades)
                self._check_and_adjust_stop_losses(prices_to_check=prices_to_check, open_trades=open_trades)
        except Exception as exc:
            logger.error(f'Failed to monitor and adjust current trades. {exc}', exc_info=True)

    def _get_latest_instrument_price(self, retry_count: int = 0) -> float:
        price = self._latest_price
        latest_price = self._pricing.get_pricing_info(instruments=[self.instrument], include_home_conversions=False)
        if not len(latest_price['prices']) and retry_count < 5:
            self._get_latest_instrument_price(retry_count=retry_count + 1)
        elif len(latest_price['prices']):
            price = latest_price['prices'][0]['asks'][0]['price']
            self._latest_price = price

        return float(price)

    def _convert_units_to_gbp(self, units: int) -> float:
        return round((self._get_latest_instrument_price() * units) / self.margin_ratio, 4)

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

    def _convert_gbp_to_max_num_units(self, margin: float) -> int:
        return math.floor((margin * self.margin_ratio) / self._get_latest_instrument_price())

    def _get_unit_size_of_trade(self, account_data: dict) -> float:
        return self._convert_gbp_to_max_num_units(self._get_valid_margin_size(account_data))

    def _construct_order(self,
                         signal: str,
                         last_close_price: float,
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
            entry = round(last_close_price + entry_offset, 5)
            tp = round(entry + tp_pip_amount, 5)
            sl = round(entry - sl_pip_amount, 5)
            price_bound = round(entry + worst_price_bound_offset, 5)
        elif signal == 'short':
            entry = round(last_close_price - entry_offset, 5)
            tp = round(entry - tp_pip_amount, 5)
            sl = round(entry + sl_pip_amount, 5)
            price_bound = round(entry - worst_price_bound_offset, 5)
            units = units * -1

        return create_stop_order(entry, price_bound, sl, tp, self.instrument, units)

    def _place_pending_order(
            self,
            price_to_offset_from: float,
            entry_offset: float,
            sl_pip_amount: float,
            tp_pip_amount: float,
            strategy: str,
            signal: str,
            margin: float,
    ):
        order_schema = self._construct_order(
            signal=signal,
            last_close_price=price_to_offset_from,
            entry_offset=entry_offset,
            worst_price_bound_offset=self._atr_values[self.entry_timeframe] / 2,
            tp_pip_amount=tp_pip_amount,
            sl_pip_amount=sl_pip_amount,
            units=margin,
        )
        pending_order = self.account.create_order(order_schema)
        self._add_id_to_pending_orders(pending_order, strategy)
        logger.info(f'pending order placed: {pending_order}')
        logger.info(f'pending_orders: {self._pending_orders}')
        logger.info(f'sl_adjusted: {self._sl_adjusted}')
        logger.info(f'partially_closed: {self._partially_closed}')

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
                    executor.submit(od.get_complete_candlesticks, self.instrument, 'ABM', granularity, 1000)
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

    @abc.abstractmethod
    def execute(self):
        """ Run the complete strategy. """
        raise NotImplementedError('Not implemented in subclass.')
