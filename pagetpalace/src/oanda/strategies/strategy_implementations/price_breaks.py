# Python standard.
import pytz
import time
from datetime import datetime
from typing import Dict

# Local.
from pagetpalace.src.constants.timeframe import TimeFrame
from pagetpalace.src.constants.price import Price
from pagetpalace.src.constants.data_point import DataPoint
from pagetpalace.src.constants.direction import Direction
from pagetpalace.src.indicators.indicators import (
    append_average_true_range,
    append_chaikin_money_flow,
    calculate_local_high_and_low,
)
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.instruments.instruments import Instrument
from pagetpalace.src.indicators.trading_session_validator import TradingSessionValidator
from pagetpalace.src.oanda.strategies.strategy import Strategy
from pagetpalace.tools.logger import *


class PriceBreaks(Strategy):
    SESSION_TRADES_PER_DIRECTION = 1
    TIME_FRAME = TimeFrame.H1

    def __init__(
            self,
            account: OandaAccount,
            equity_split: float,
            instrument: Instrument,
            tp_mult: Dict[Direction, float],
            sl_mult: Dict[Direction, float],
            session_reset_look_back: Dict[Direction, int],
            entry_offset_factor: Dict[Direction, float],
            max_candle_factor: Dict[Direction, float],
            num_candles_allowed_to_fill: Dict[Direction, int],
    ):
        super().__init__(
            equity_split=equity_split,
            account=account,
            instrument=instrument,
            time_frames=[self.TIME_FRAME],
            entry_timeframe=self.TIME_FRAME,
            sub_strategies_count=1,
            max_risk_pct=0.05,
        )
        self.equity_split = equity_split
        self.tp_mult = tp_mult
        self.sl_mult = sl_mult
        self.session_reset_look_back = session_reset_look_back
        self.entry_offset_factor = entry_offset_factor
        self.max_candle_factor = max_candle_factor
        self.num_candles_allowed_to_fill = num_candles_allowed_to_fill
        self.directions = list(tp_mult.keys())
        self._atr_value = 0.
        self._cmf_value = 0.
        self._prev_candle = None
        self._local_extremas = {Direction.LONG: {DataPoint.HIGH: 0.}, Direction.SHORT: {DataPoint.LOW: 0.}}
        self._new_extrema_flags = {Direction.LONG: {DataPoint.HIGH: False}, Direction.SHORT: {DataPoint.LOW: False}}
        self._session_trade_counts = {k: self.SESSION_TRADES_PER_DIRECTION for k in [Direction.LONG, Direction.SHORT]}
        self._trading_session_validator = TradingSessionValidator(self.start_candle.name)

    def _is_new_candle(self):
        return self._prev_candle.iloc[-1]['datetime'] != self._latest_data['H1'].iloc[-1]['datetime']

    def _check_and_clear_pending_orders(self):
        """ Override method to clear regardless of new signal, clear based on time. (A trade has an hour to fill). """
        try:
            self._clear_pending_orders()
        except Exception as exc:
            logger.error(f'Failed to clear pending orders. {exc}', exc_info=True)
            self._send_mail_alert(source='clear_pending', additional_msg=str(exc))

    def _reset_local_extremas(self, init: bool = False):
        for direction in self.directions:
            local_high_low = calculate_local_high_and_low(
                df=self.all_timeframes_data[self.entry_timeframe],
                index=int(self.start_candle['idx'] - 1)
                if init
                else int(self._latest_data[self.entry_timeframe]['idx']),
                look_back=self.session_reset_look_back[direction],
            )
            dp = DataPoint.HIGH if direction == Direction.LONG else DataPoint.LOW
            self._local_extremas[direction] = {dp: local_high_low[dp]}

    def _reset_session_trades_count(self):
        self._session_trade_counts = {k: self.SESSION_TRADES_PER_DIRECTION for k in [Direction.LONG, Direction.SHORT]}

    def _reset_new_extrema_flags(self):
        self._new_extrema_flags = {Direction.LONG: {DataPoint.HIGH: False}, Direction.SHORT: {DataPoint.LOW: False}}

    def _update_new_extrema_flags(self):
        close = self._latest_data[self.entry_timeframe][Price.MID_CLOSE].values[0]
        if close > self._local_extremas[Direction.LONG][DataPoint.HIGH]:
            self._new_extrema_flags[Direction.LONG][DataPoint.HIGH] = True
        if close < self._local_extremas[Direction.SHORT][DataPoint.LOW]:
            self._new_extrema_flags[Direction.SHORT][DataPoint.LOW] = True

    def _update_atr_value(self):
        append_average_true_range(self._latest_data[self.entry_timeframe])
        self._atr_value = round(self._latest_data[self.entry_timeframe].iloc[-1]['ATR_14'], 2)

    def _update_cmf_value(self):
        append_chaikin_money_flow(self._latest_data[self.entry_timeframe])
        self._cmf_value = round(self._latest_data[self.entry_timeframe]['CMF'].values[0], 2)

    def _update_for_new_session(self):
        self._reset_local_extremas()
        self._reset_session_trades_count()
        self._reset_new_extrema_flags()

    def _update(self):
        self._check_and_clear_pending_orders()
        self._trading_session_validator.date_time = self._latest_data['H1'].iloc[-1]['datetime']
        self._update_atr_value()
        self._update_cmf_value()
        self._update_new_extrema_flags()
        if self._trading_session_validator.is_new_session():
            self._update_for_new_session()

    def _adjust_session_trades_count(self, signal: Direction):
        if self._session_trade_counts[signal] > 0:
            self._session_trade_counts[signal] -= 1

    def _is_valid_size(self, direction: Direction) -> bool:
        is_valid = abs(
            self._latest_data[self.entry_timeframe][Price.MID_OPEN].values[0]
            - self._latest_data[self.entry_timeframe][Price.MID_CLOSE].values[0]
        ) < self._atr_value * self.max_candle_factor[direction]

        return is_valid

    def _is_long_signal(self) -> bool:
        is_valid_size = self._is_valid_size(Direction.LONG)
        if not is_valid_size and self._new_extrema_flags[Direction.LONG][DataPoint.HIGH]:
            self._adjust_session_trades_count(Direction.LONG)
            return False

        return is_valid_size \
            and self._session_trade_counts[Direction.LONG] > 0 \
            and self._new_extrema_flags[Direction.LONG][DataPoint.HIGH] \
            and self._is_green_candle() \
            and self._cmf_value > 0

    def _is_short_signal(self) -> bool:
        is_valid_size = self._is_valid_size(Direction.SHORT)
        if not is_valid_size and self._new_extrema_flags[Direction.SHORT][DataPoint.LOW]:
            self._adjust_session_trades_count(Direction.SHORT)
            return False

        return is_valid_size \
            and self._session_trade_counts[Direction.SHORT] > 0 \
            and self._new_extrema_flags[Direction.SHORT][DataPoint.LOW] \
            and self._is_red_candle()

    def _get_signals(self, **kwargs) -> dict:
        signals = {'1': ''}
        if Direction.LONG in self.directions and self._is_long_signal():
            signals['1'] = Direction.LONG
        elif Direction.SHORT in self.directions and self._is_short_signal():
            signals['1'] = Direction.SHORT

        return signals

    def _get_entry_price_to_offset_from(self, signal: Direction) -> float:
        price_key = Price.ASK_HIGH if signal == Direction.LONG else Price.BID_LOW

        return self._latest_data[self.entry_timeframe][price_key].values[0]

    def _get_tp_pip_amount(self, signal: Direction) -> float:
        return self._atr_value * self.tp_mult[signal]

    def _get_stop_loss_price(self, signal: Direction) -> float:
        price_key = Price.BID_LOW if signal == Direction.LONG else Price.ASK_HIGH
        offset = self._atr_value * self.sl_mult[signal]
        if signal == Direction.LONG:
            offset *= -1

        return self._latest_data[self.entry_timeframe][price_key].values[0] + offset

    def _execute_and_act_on_new_order(self, signal: Direction):
        entry_price = self._get_entry_price_to_offset_from(signal)
        units = self._get_unit_size_of_trade(entry_price)
        if units > 0:
            self._place_pending_order(
                price_to_offset_from=entry_price,
                entry_offset=self._atr_value / self.entry_offset_factor[signal],
                worst_price_bound_offset=self._atr_value / 2,
                sl_pip_amount=self._get_stop_loss_price(signal),
                tp_pip_amount=self._get_tp_pip_amount(signal),
                strategy='1',
                signal=signal,
                units=units,
            )
            self._adjust_session_trades_count(signal)
            self._reset_new_extrema_flags()

    def execute(self):
        prev_exec = -1
        london_tz = pytz.timezone('Europe/London')
        self._reset_local_extremas(init=True)
        while 1:
            now = datetime.now().astimezone(london_tz)
            if self._should_run(now):
                try:
                    self._sync_pending_orders(self.account.get_pending_orders()['orders'])
                except Exception as exc:
                    logger.error(f'Failed to sync pending orders. {exc}', exc_info=True)
                if now.minute == 0 and now.hour != prev_exec:
                    time.sleep(8)
                    self._update_latest_data()
                    if self._latest_data:
                        prev_exec = now.hour
                        if self._is_new_candle():
                            self._update()
                            signals = self._get_signals()

                            # New orders.
                            for strategy, signal in signals.items():
                                if signal:
                                    self._execute_and_act_on_new_order(signal)
                            self._prev_candle = self._latest_data['H1'].iloc[-1]
