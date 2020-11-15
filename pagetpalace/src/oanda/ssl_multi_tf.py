# Python standard.
import abc
import concurrent.futures
import datetime
import math
import pytz
import sys
import time
from typing import List, Dict

# Third-party.
import pandas as pd
from pagetpalace.src.oanda import OandaPricingData, create_stop_order, OandaInstrumentData, OandaAccount
from pagetpalace.src.oanda.calculations import calculate_new_sl_price, check_pct_hit
from pagetpalace.src.indicators import append_ssl_channel, append_ssma, append_average_true_range
from pagetpalace.tools.logger import *


class SSLMultiTimeFrame:
    _OPEN_TRADE_PARAMS = {
        'check_1': 0.35,
        'check_2': 0.65,
        'sl_move_1': 0.01,
        'sl_move_2': 0.35,
        'close_amount_1': 0.5,
        'close_amount_2': 0.7,
    }

    def __init__(
            self,
            account: OandaAccount,
            instrument: str,
            margin_ratio: int,
            unrestricted_margin_cap: float,
            trade_multipliers: dict,
            boundary_multipliers: dict,
            time_frames: List[str],
    ):
        """
        _trade_multipliers = {
            '1': {
                'long': {'above': {'sl': 2, 'tp': 2}, 'below': {'sl': 2, 'tp': 2}},
                'short': {'above': {'sl': 2, 'tp': 2}, 'below': {'sl': 2, 'tp': 2}},
            },
            '2': {
                'long': {'above': {'sl': 2, 'tp': 2}, 'below': {'sl': 2, 'tp': 2}},
                'short': {'above': {'sl': 2, 'tp': 2}, 'below': {'sl': 2, 'tp': 2}},
            },
            '3': {
                'long': {'above': {'sl': 2, 'tp': 2}, 'below': {'sl': 2, 'tp': 2}},
                'short': {'above': {'sl': 2, 'tp': 2}, 'below': {'sl': 2, 'tp': 2}},
            },
            '4': {
                'long': {'above': {'sl': 2, 'tp': 2}, 'below': {'sl': 2, 'tp': 2}},
                'short': {'above': {'sl': 2, 'tp': 2}, 'below': {'sl': 2, 'tp': 2}},
        },
    }
        _boundary_multipliers = {
            'margin_adjustment': {'1': {'long': {'above': 2, 'below': 3}, 'short': {'above': 1.25, 'below': 3.5}}},
            'reverse': {'1': {'short': {'below': 2}}}
        }
        """
        self._account = account
        self._instrument = instrument
        self._margin_ratio = margin_ratio
        self._unrestricted_margin_cap = unrestricted_margin_cap
        self._trade_multipliers = trade_multipliers
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

    def _check_and_partially_close(
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

    def _add_id_to_pending_orders(self, order: dict, strategy: str):
        getattr(self, f'_pending_orders_{strategy}').append(order['orderCreateTransaction']['id'])

    def _sync_pending_orders(self, pending_orders_in_account: List[dict]):
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

    def _clean_lists(self):
        try:
            open_trade_ids = [t['id'] for t in self._account.get_open_trades()['trades']]
            self._clean_local_lists(open_trade_ids)
        except Exception as exc:
            logger.info(f'Failed to clean lists. {exc}', exc_info=True)

    def _clear_pending_orders(self, strategy: str):
        for id_ in getattr(self, f'_pending_orders_{strategy}'):
            self._account.cancel_order(id_)
        getattr(self, f'_pending_orders_{strategy}').clear()

    def _check_and_clear_pending_orders(self, entry_signals_to_check: Dict[str, Dict[str, int]]):
        for strategy_num, entry_signals in entry_signals_to_check.items():
            if entry_signals['previous'] != entry_signals['current']:
                try:
                    self._clear_pending_orders(strategy=strategy_num)
                except Exception as exc:
                    logger.error(f'Failed to clear pending order for strategy {strategy_num}.  {exc}', exc_info=True)

    def _check_and_adjust_stop_losses(self, prices_to_check: Dict[str, float], open_trades: List[dict]):
        try:
            sl_adjust_args = [
                (self._OPEN_TRADE_PARAMS['check_1'], self._OPEN_TRADE_PARAMS['sl_move_1'], 1),
                (self._OPEN_TRADE_PARAMS['check_2'], self._OPEN_TRADE_PARAMS['sl_move_2'], 2),
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

    def _partial_closures(self, prices_to_check: Dict[str, float], open_trades: List[dict]):
        try:
            partial_close_args = [
                (self._OPEN_TRADE_PARAMS['check_1'], self._OPEN_TRADE_PARAMS['close_amount_1'], 1),
                (self._OPEN_TRADE_PARAMS['check_2'], self._OPEN_TRADE_PARAMS['close_amount_2'], 2),
            ]
            for args in partial_close_args:
                self._check_and_partially_close(
                    prices=prices_to_check,
                    open_trades=open_trades,
                    check_pct=args[0],
                    close_pct=args[1],
                    partial_close_count=args[2],
                )
        except Exception as exc:
            logger.error(f'Failed to check and partially close trades. {exc}', exc_info=True)

    def _monitor_and_adjust_current_trades(self):
        try:
            open_trades = self._account.get_open_trades()['trades']
            if len(open_trades) > 0:
                prices_to_check = self._get_prices_to_check()
                self._partial_closures(prices_to_check=prices_to_check, open_trades=open_trades)
                self._check_and_adjust_stop_losses(prices_to_check=prices_to_check, open_trades=open_trades)
        except Exception as exc:
            logger.error(f'Failed to monitor and adjust current trades. {exc}', exc_info=True)

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
        margin_size = (balance * self._unrestricted_margin_cap) / 1.75
        available_minus_restricted = self._margin_not_being_used_in_orders(account_data) - (balance * 0.1)

        return self._adjust_according_to_restricted_margin(margin_size, available_minus_restricted)

    def _convert_gbp_to_max_num_units(self, margin: float) -> int:
        return math.floor((margin * self._margin_ratio) / self._get_latest_instrument_price())

    def _get_unit_size_of_trade(self, account_data: dict) -> float:
        return self._convert_gbp_to_max_num_units(self._get_valid_margin_size(account_data))

    def _get_data(self) -> Dict[str, pd.DataFrame]:
        od = OandaInstrumentData()
        data = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_tf = {}
            for granularity in self._time_frames:
                future_to_tf[
                    executor.submit(od.get_complete_candlesticks, self._instrument, 'ABM', granularity, 500)
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

    def _is_within_valid_boundary(self,
                                  bias: str,
                                  atr_value: float,
                                  smoothed_ma: float,
                                  price: float,
                                  strategy: str) -> bool:
        boundary = self._calculate_boundary('margin_adjustment', bias, atr_value, smoothed_ma, price, strategy)

        return not (self._calculate_atr_factor(price, smoothed_ma, atr_value) * atr_value > boundary)

    def _calculate_distance_factor(self,
                                   bias: str,
                                   atr_value: float,
                                   smoothed_ma: float,
                                   price: float,
                                   strategy: str) -> bool:
        boundary = self._calculate_boundary('reverse', bias, atr_value, smoothed_ma, price, strategy)

        return self._calculate_atr_factor(price, smoothed_ma, atr_value) * atr_value >= boundary

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
            entry = round(last_close_price + entry_offset, 1)
            tp = round(entry + tp_pip_amount, 1)
            sl = round(entry - sl_pip_amount, 1)
            price_bound = round(entry + worst_price_bound_offset, 1)
        elif signal == 'short':
            entry = round(last_close_price - entry_offset, 1)
            tp = round(entry - tp_pip_amount, 1)
            sl = round(entry + sl_pip_amount, 1)
            price_bound = round(entry - worst_price_bound_offset, 1)
            units = units * -1

        return create_stop_order(entry, price_bound, sl, tp, self._instrument, units)

    def _get_ssl_values(self, data: Dict[str, pd.DataFrame]) -> Dict[str, int]:
        for df in data.values():
            append_ssl_channel(df)

        return {tf: data[tf].iloc[-1]['HighLowValue'] for tf in self._time_frames}

    @abc.abstractmethod
    def _get_atr_values(self, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def _get_ssma_values(self, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def _get_signals(self, price: float) -> Dict[str, str]:
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def execute(self):
        """ Run the complete strategy. """
        raise NotImplementedError('Not implemented in subclass.')


class SSLCurrencyStrategy(SSLMultiTimeFrame):
    def __init__(self, account: OandaAccount, instrument: str, strategy_multipliers: dict, boundary_multipliers: dict):
        super().__init__(
            account,
            instrument,
            30,
            0.9,
            strategy_multipliers,
            boundary_multipliers,
            ['W', 'D', 'H4', 'M30'],
        )
        self._previous_signals = {'W': 0, 'D': 0, 'H4': 0, 'M30': 0}
        self._ssl_values = {'W': 0, 'D': 0, 'H4': 0, 'M30': 0}
        self._entry_signals = {str(s): {'prev': 0, 'curr': 0} for s in range(1, 5)}
        self._strategy_atr_values = {'1': 0, '2': 0, '3': 0, '4': 0}
        self._strategy_ssma_values = {'1': 0, '2': 0, '3': 0, '4': 0}

    def _update_latest_values(self, data):
        ssmas = self._get_ssma_values(data)
        atrs = self._get_atr_values(data)
        self._ssl_values = self._get_ssl_values(data)
        self._strategy_ssma_values = {'1': ssmas['M30'], '2': ssmas['H4'], '3': ssmas['M30'], '4': ssmas['H4']}
        self._strategy_atr_values = {'1': atrs['M30'], '2': atrs['H4'], '3': atrs['M30'], '4': atrs['H4']}

        # Compare signals, don't re-enter every candle with same entry signal.
        self._entry_signals = {
            '1': {'prev': self._previous_signals['M30'], 'curr': self._ssl_values['M30']},
            '2': {'prev': self._previous_signals['M30'], 'curr': self._ssl_values['M30']},
            '3': {'prev': self._previous_signals['M30'], 'curr': self._ssl_values['M30']},
            '4': {'prev': self._previous_signals['H4'], 'curr': self._ssl_values['H4']},
        }

    def _log_latest_values(self, now, signals):
        logger.info(f'ssl values: {self._ssl_values}')
        logger.info(f'ssma values: {self._strategy_ssma_values}')
        logger.info(f'atr values: {self._strategy_atr_values}')
        logger.info(f'{now} signals: {signals}')

    def _update_previous_signals(self):
        self._previous_signals = {tf: self._ssl_values[tf] for tf in self._time_frames}

    def _is_new_signal(self, strategy: str) -> bool:
        return self._entry_signals[strategy]['previous'] != self._entry_signals[strategy]['current']

    def _get_atr_values(self, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        for df in data.values():
            append_average_true_range(df)

        return {tf: round(data[tf].iloc[-1]['ATR'], 2) for tf in self._time_frames}

    def _get_ssma_values(self, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        for df in data.values():
            append_ssma(df)

        return {tf: round(data[tf].iloc[-1]['SSMA_50'], 2) for tf in self._time_frames}

    def _s1_is_long(self) -> bool:
        return self._ssl_values['W'] == 1 and self._ssl_values['D'] == 1 \
               and self._ssl_values['H4'] == 1 and self._ssl_values['M30'] == 1

    def _s1_is_short(self) -> bool:
        return self._ssl_values['W'] == -1 and self._ssl_values['D'] == -1 \
                and self._ssl_values['H4'] == -1 and self._ssl_values['M30'] == -1

    def _s2_is_long(self, price: float) -> bool:
        return self._ssl_values['W'] == 1 and self._ssl_values['D'] == -1 \
               and self._ssl_values['H4'] == 1 and self._ssl_values['M30'] == 1 \
               and self._calculate_distance_factor(
                        'short', self._strategy_atr_values['2'], self._strategy_ssma_values['2'], price, '2'
                    )

    def _s2_is_short(self, price: float) -> bool:
        return self._ssl_values['W'] == -1 and self._ssl_values['D'] == 1 \
               and self._ssl_values['H4'] == -1 and self._ssl_values['M30'] == -1 \
               and self._calculate_distance_factor(
                        'long', self._strategy_atr_values['2'], self._strategy_ssma_values['2'], price, '2'
                    )

    def _s3_is_long(self, price: float) -> bool:
        return self._ssl_values['W'] == 1 and self._ssl_values['D'] == 1 \
               and self._ssl_values['H4'] == -1 and self._ssl_values['M30'] == 1 \
               and self._calculate_distance_factor(
                        'short', self._strategy_atr_values['3'], self._strategy_ssma_values['3'], price, '3'
                    )

    def _s3_is_short(self, price: float) -> bool:
        return self._ssl_values['W'] == -1 and self._ssl_values['D'] == -1 \
               and self._ssl_values['H4'] == 1 and self._ssl_values['M30'] == -1 \
               and self._calculate_distance_factor(
                        'long', self._strategy_atr_values['3'], self._strategy_ssma_values['3'], price, '3',
                    )

    def _add_signal_for_s1(self, signals: Dict[str, str]):
        if self._s1_is_long():
            signals['1'] = 'long'
        if self._s1_is_short():
            signals['1'] = 'short'

    def _add_signal_for_s2(self, signals: Dict[str, str], price: float):
        if self._s2_is_long(price):
            signals['2'] = 'long'
        elif self._s2_is_short(price):
            signals['2'] = 'short'

    def _add_signal_for_s3(self, signals: Dict[str, str], price: float):
        if self._s3_is_long(price):
            signals['3'] = 'long'
        elif self._s3_is_short(price):
            signals['3'] = 'short'

    def _add_signal_for_s4(self, signals: Dict[str, str]):
        if self._ssl_values['W'] == 1 and self._ssl_values['H4'] == 1:
            signals['4'] = 'long'
        elif self._ssl_values['W'] == -1 and self._ssl_values['H4'] == -1:
            signals['4'] = 'short'

    def _get_signals(self, price: float) -> Dict[str, str]:
        signals = {'1': '', '2': '', '3': '', '4': ''}
        for i in ['1', '4']:
            getattr(self, f'_add_signal_for_s{i}')(signals)
        for i in ['2', '3']:
            getattr(self, f'_add_signal_for_s{i}')(signals, price)

        return signals

    def _place_pending_order(self, last_close_price: float, strategy: str, signal: str, margin: float):
        price_position = 'above' if last_close_price > self._strategy_ssma_values[strategy] else 'below'
        sl_pip_amount = self._strategy_atr_values[strategy] * self._trade_multipliers[strategy][signal][price_position]['sl']
        order_schema = self._construct_order(
            signal=signal,
            last_close_price=last_close_price,
            entry_offset=self._strategy_atr_values[strategy] / 5,
            worst_price_bound_offset=self._strategy_atr_values[strategy] / 2,
            tp_pip_amount=sl_pip_amount * self._trade_multipliers[strategy][signal][price_position]['tp'],
            sl_pip_amount=sl_pip_amount,
            units=margin,
        )
        pending_order = self._account.create_order(order_schema)
        self._add_id_to_pending_orders(pending_order, strategy)
        logger.info(f'pending order placed: {pending_order}')
        logger.info(f'pending_1: {self._pending_orders_1} pending_2: {self._pending_orders_2}')
        logger.info(f'adjusted_1: {self._sl_adjusted_1} adjusted_2: {self._sl_adjusted_2}')
        logger.info(f'closed_1: {self._partially_closed_1} closed_2: {self._partially_closed_2}')

    def execute(self):
        london_tz = pytz.timezone('Europe/London')
        prev_exec = -1
        is_first_run = True
        while 1:
            now = datetime.datetime.now().astimezone(london_tz)
            try:
                self._sync_pending_orders(self._account.get_pending_orders()['orders'])
            except Exception as exc:
                logger.error(f'Failed to sync pending orders. {exc}', exc_info=True)
            if now.minute % 30 == 0 and now.minute != prev_exec:
                time.sleep(8)
                data = self._get_data()
                if data:
                    last_30m_close = float(data['M30']['midClose'].values[-1])
                    self._update_latest_values(data)
                    signals = self._get_signals(last_30m_close)
                    self._log_latest_values(now, signals)

                    # Remove outdated pending orders depending on entry signals.
                    self._check_and_clear_pending_orders(self._entry_signals)

                    # New orders.
                    for strategy, signal in signals.items():
                        try:
                            units = self._get_unit_size_of_trade(self._account.get_full_account_details()['account'])
                            is_within_valid_boundary = self._is_within_valid_boundary(
                                bias=signal,
                                atr_value=self._strategy_atr_values[strategy],
                                smoothed_ma=self._strategy_ssma_values[strategy],
                                price=last_30m_close,
                                strategy=strategy,
                            )
                            if units > 0 and is_within_valid_boundary \
                                    and signal and self._is_new_signal(strategy) \
                                    and not is_first_run:
                                self._place_pending_order(last_30m_close, strategy, signal, units)
                        except Exception as exc:
                            logger.info(f'Failed place new pending order. {exc}', exc_info=True)
                    prev_exec = now.minute
                    is_first_run = False
                    self._update_previous_signals()

            # Monitor and adjust current trades, if any.
            time.sleep(1)
            self._monitor_and_adjust_current_trades()

            # Remove outdated entries in local lists.
            if now.hour % 24 == 0:
                self._clean_lists()
