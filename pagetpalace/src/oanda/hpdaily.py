# Python standard.
import pytz
import sys
import time
from datetime import datetime
from typing import Dict, Union

# Local.
from pagetpalace.src.indicators import (
    append_average_true_range,
    append_ssma,
    get_hammer_pin_signal_v2,
    is_candle_range_greater_than_x,
    was_price_ascending,
    was_price_descending,
    was_previous_green_streak,
    was_previous_red_streak,
)
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.strategy import Strategy
from pagetpalace.tools.logger import *


class HPDaily(Strategy):
    def __init__(
            self,
            account: OandaAccount,
            instrument: Instrument,
            boundary_multipliers: dict,
            trade_multipliers: dict,
            coefficients: dict,
            spread_cap: float = None,
            wait_time_precedence: int = 1,
            equity_split: float = 8,
    ):
        super().__init__(
            equity_split=equity_split,
            account=account,
            instrument=instrument,
            time_frames=['D'],
            entry_timeframe='D',
            sub_strategies_count=1,
            live_trade_monitor=None,
        )
        """     
            coefficients = {
                'hp_coeffs': {
                    'long': {'body': 2.25, 'shadow': 5.5},
                    'short': {'body': 2.25, 'shadow': 4}},
                'streak_look_back': {'long': 1, 'short': 1},
                'price_movement_lb': {'long': 1, 'short': 1},
                'x_atr': {'long': 0.5, 'short': 0.5},
            },
            'trade_m': {'1': {'long': {'tp': 3.5, 'sl': 1.5}, 'short': {'tp': 3, 'sl': 1.5}}},
            'boun_m': {'D': {'long': {'below': 0.01}, 'short': {'above': 0.01}}},
        }
        """
        self._prev_exec_datetime = None
        self.wait_time_precedence = wait_time_precedence
        self.trade_multipliers = trade_multipliers
        self.boundary_multipliers = boundary_multipliers
        self.coefficients = coefficients
        self.directions = tuple(coefficients['hp_coeffs'].keys())
        self.spread_cap = spread_cap
        self._strategy_atr_values = {}
        self._strategy_ssma_values = {}

    def _calculate_atr_factor(self, price: float, sma_value: float) -> float:
        return abs((price - sma_value) / self._strategy_atr_values[self.entry_timeframe])

    def _calculate_boundary(self, bias: str, price: float, sma_value: float) -> float:
        try:
            if price >= sma_value:
                boundary = self.boundary_multipliers[self.entry_timeframe][bias]['above'] \
                           * self._strategy_atr_values[self.entry_timeframe]
            else:
                boundary = self.boundary_multipliers[self.entry_timeframe][bias]['below'] \
                           * self._strategy_atr_values[self.entry_timeframe]
        except KeyError:  # Not interested in these situations, don't trade.
            boundary = sys.maxsize

        return boundary

    def _has_met_reverse_trade_condition(self, bias: str, price: float, sma_value: float) -> bool:
        return self._calculate_atr_factor(price, sma_value) * self._strategy_atr_values[self.entry_timeframe] \
               >= self._calculate_boundary(bias, price, sma_value)

    def _update_strategy_atr_values(self):
        append_average_true_range(self._latest_data[self.entry_timeframe])
        self._strategy_atr_values = {self.entry_timeframe: self._latest_data[self.entry_timeframe]['14_ATR'].values[-1]}

    def _update_strategy_ssma_values(self):
        append_ssma(self._latest_data[self.entry_timeframe])
        self._strategy_ssma_values = {
            self.entry_timeframe: round(self._latest_data[self.entry_timeframe]['SSMA_50'].values[-1], 5)
        }

    def _update_current_indicators_and_signals(self):
        self._update_strategy_atr_values()
        self._update_strategy_ssma_values()

    def _is_long_hp_signal(self, idx_to_analyse: int) -> bool:
        return get_hammer_pin_signal_v2(
            self._latest_data[self.entry_timeframe],
            idx_to_analyse,
            self.coefficients['hp_coeffs']['long'],
        ) == 'long'

    def _is_short_hp_signal(self, idx_to_analyse: int) -> bool:
        return get_hammer_pin_signal_v2(
            self._latest_data[self.entry_timeframe],
            idx_to_analyse,
            self.coefficients['hp_coeffs']['short'],
        ) == 'short'

    def _has_long_price_setup(self, idx_to_analyse) -> bool:
        bias = 'long'
        midlow_20_distance_met = self._has_met_reverse_trade_condition(
            bias,
            self._latest_data[self.entry_timeframe]['midLow'].values[-1],
            self._strategy_ssma_values[self.entry_timeframe],
        )
        red_streak = was_previous_red_streak(
            self._latest_data[self.entry_timeframe],
            idx_to_analyse,
            look_back=self.coefficients['streak_look_back'][bias],
        )
        price_descending = was_price_descending(
            self._latest_data[self.entry_timeframe],
            idx_to_analyse,
            look_back=self.coefficients['price_movement_lb'][bias],
        )

        return (red_streak or price_descending) and midlow_20_distance_met

    def _has_short_price_setup(self, idx_to_analyse) -> bool:
        bias = 'short'
        midhigh_20_distance_met = self._has_met_reverse_trade_condition(
            bias,
            self._latest_data[self.entry_timeframe]['midHigh'].values[-1],
            self._strategy_ssma_values[self.entry_timeframe],
        )
        green_streak = was_previous_green_streak(
            self._latest_data[self.entry_timeframe],
            idx_to_analyse,
            look_back=self.coefficients['streak_look_back'][bias],
        )
        price_ascending = was_price_ascending(
            self._latest_data[self.entry_timeframe],
            idx_to_analyse,
            look_back=self.coefficients['price_movement_lb'][bias],
        )

        return (green_streak or price_ascending) and midhigh_20_distance_met

    def _is_long_signal(self, idx_to_analyse: int) -> bool:
        return self._has_long_price_setup(idx_to_analyse) and self._is_long_hp_signal(idx_to_analyse)

    def _is_short_signal(self, idx_to_analyse: int) -> bool:
        return self._has_short_price_setup(idx_to_analyse) and self._is_short_hp_signal(idx_to_analyse)

    def _is_big_enough_movement(self, bias: str) -> bool:
        return is_candle_range_greater_than_x(
            self._latest_data[self.entry_timeframe],
            self._strategy_atr_values[self.entry_timeframe] * self.coefficients['x_atr'][bias],
        )

    def _get_s1_signal(self) -> Union[str, None]:
        signal = None
        idx_to_analyse = self._latest_data[self.entry_timeframe]['idx'].values[-1]
        long = 'long'
        short = 'short'
        if long in self.directions and self._is_big_enough_movement(long) and self._is_long_signal(idx_to_analyse):
            signal = long
        elif short in self.directions and self._is_big_enough_movement(short) and self._is_short_signal(idx_to_analyse):
            signal = short

        return signal

    def _get_signals(self, **kwargs) -> Dict[str, Union[str, None]]:
        return {'1': self._get_s1_signal()}

    def _is_within_spread_cap(self) -> bool:
        return float(self._latest_data[self.entry_timeframe]['askOpen'].values[-1]) \
               - float(self._latest_data[self.entry_timeframe]['bidOpen'].values[-1]) <= self.spread_cap

    def _get_stop_loss_pip_amount(self, signal: str) -> float:
        close = self._latest_data[self.entry_timeframe]['midClose'].values[-1]
        if signal == 'short':
            amount = abs((self._latest_data[self.entry_timeframe]['midHigh'].values[-1] - close)
                         + (close - self._latest_data[self.entry_timeframe]['midLow'].values[-1]))
        else:
            amount = abs((close - self._latest_data[self.entry_timeframe]['midLow'].values[-1])
                         + (self._latest_data[self.entry_timeframe]['midHigh'].values[-1] - close))

        return amount \
               + (self._strategy_atr_values[self.entry_timeframe] / 10) \
               + (self._strategy_atr_values[self.entry_timeframe] * self.trade_multipliers['1'][signal]['sl'])

    def _log_latest_values(self, now, signals):
        logger.info(f'latest candle: {self._latest_data[self.entry_timeframe][-1]}')
        logger.info(f'ssma values: {self._strategy_ssma_values}')
        logger.info(f'atr values: {self._strategy_atr_values}')
        logger.info(f'{now} signals: {signals}')

    def _place_market_order_if_units_available(self, strategy: str, signal: str):
        try:
            units = self._get_unit_size_of_trade(self._latest_data[self.entry_timeframe]['midClose'].values[-1])
            if units > 0:
                sl_pip_amount = self._get_stop_loss_pip_amount(signal)
                tp_pip_amount = self._strategy_atr_values[self.entry_timeframe] \
                                * self.trade_multipliers[strategy][signal]['tp']
                self._place_market_order(
                    sl_pip_amount=sl_pip_amount,
                    tp_pip_amount=tp_pip_amount,
                    signal=signal,
                    units=units,
                )
        except Exception as exc:
            logger.info(f'Failed place new market order. {exc}', exc_info=True)
            self._send_mail_alert(error_source='place_order')

    def execute(self):
        london_tz = pytz.timezone('Europe/London')
        prev_exec = -1
        while 1:
            now = datetime.now().astimezone(london_tz)
            if now.isoweekday() != 6:
                try:
                    self._sync_pending_orders(self.account.get_pending_orders()['orders'])
                except Exception as exc:
                    logger.error(f'Failed to sync pending orders. {exc}', exc_info=True)
                if now.minute == 0 and (now.hour == 21 or now.hour == 22) and now.hour != prev_exec:
                    time.sleep(8 + (self.wait_time_precedence / 10) + 0.05)
                    self._update_latest_data()
                    if self._latest_data:
                        prev_exec = now.hour
                        if self._prev_exec_datetime != self._latest_data[self.entry_timeframe].iloc[-1]['datetime']:
                            self._update_current_indicators_and_signals()
                            signals = self._get_signals()
                            self._log_latest_values(now, signals)

                            # New orders.
                            if self._is_within_spread_cap():
                                for strategy, signal in signals.items():
                                    if signal:
                                        # TODO. place instant market order.
                                        self._place_market_order_if_units_available(strategy, signal)
                            self._prev_exec_datetime = self._latest_data[self.entry_timeframe].iloc[-1]['datetime']
