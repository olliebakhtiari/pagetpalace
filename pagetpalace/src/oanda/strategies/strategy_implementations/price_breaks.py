# Python standard.
import pytz
import time
from datetime import datetime, timedelta
from typing import Dict

# Local.
from pagetpalace.src.constants.timeframe import TimeFrame
from pagetpalace.src.constants.price import Price
from pagetpalace.src.constants.data_point import DataPoint
from pagetpalace.src.constants.direction import Direction
from pagetpalace.src.indicators.indicators import (
    get_average_true_range_value,
    get_chaikin_money_flow_value,
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
    STRATEGY_LABEL = '1'

    def __init__(
            self,
            account: OandaAccount,
            equity_split: float,
            instrument: Instrument,
            tp_multipliers: Dict[Direction, float],
            sl_multipliers: Dict[Direction, float],
            session_reset_look_backs: Dict[Direction, int],
            entry_offset_factors: Dict[Direction, float],
            max_candle_factors: Dict[Direction, float],
    ):
        super().__init__(
            equity_split=equity_split,
            account=account,
            instrument=instrument,
            time_frames=[self.TIME_FRAME],
            entry_timeframe=self.TIME_FRAME,
            max_risk_pct=0.05,
        )
        self.equity_split = equity_split
        self.tp_multipliers = tp_multipliers
        self.sl_multipliers = sl_multipliers
        self.session_reset_look_back = session_reset_look_backs
        self.entry_offset_factors = entry_offset_factors
        self.max_candle_factors = max_candle_factors
        self.directions = list(tp_multipliers.keys())
        self._atr_value = 0.
        self._cmf_value = 0.
        self._local_extremas = {Direction.LONG: {DataPoint.HIGH: 1000000.}, Direction.SHORT: {DataPoint.LOW: -1.}}
        self._new_extrema_flags = {Direction.LONG: {DataPoint.HIGH: False}, Direction.SHORT: {DataPoint.LOW: False}}
        self._session_trade_counts = {k: self.SESSION_TRADES_PER_DIRECTION for k in [Direction.LONG, Direction.SHORT]}
        self._latest_candle = None
        self._prev_candle_datetime = None
        self._trading_session_validator = TradingSessionValidator(datetime.now())
        self._prev_exec = -1
        self._dynamic_tp_targets = {}
        self._update_dynamic_tp_targets()
        logger.info({k: v for k, v in self.__dict__.items()})

    def _get_latest_datetime(self) -> datetime:
        return datetime.strptime(self._latest_candle['datetime'], '%Y-%m-%d %H:%M:%S')

    def _is_new_candle(self):
        return self._prev_candle_datetime != self._get_latest_datetime()

    def _reset_local_extremas(self):
        for direction in self.directions:
            local_high_low = calculate_local_high_and_low(
                df=self._latest_data[self.entry_timeframe],
                index=len(self._latest_data[self.entry_timeframe]) - 1,
                look_back=self.session_reset_look_back[direction],
            )
            dp = DataPoint.HIGH if direction == Direction.LONG else DataPoint.LOW
            self._local_extremas[direction] = {dp: local_high_low[dp]}

    def _reset_session_trades_count(self):
        self._session_trade_counts = {k: self.SESSION_TRADES_PER_DIRECTION for k in [Direction.LONG, Direction.SHORT]}

    def _reset_new_extrema_flags(self):
        self._new_extrema_flags = {Direction.LONG: {DataPoint.HIGH: False}, Direction.SHORT: {DataPoint.LOW: False}}

    def _update_new_extrema_flags(self):
        close = float(self._latest_candle[Price.MID_CLOSE])
        if close > self._local_extremas[Direction.LONG][DataPoint.HIGH]:
            self._new_extrema_flags[Direction.LONG][DataPoint.HIGH] = True
        if close < self._local_extremas[Direction.SHORT][DataPoint.LOW]:
            self._new_extrema_flags[Direction.SHORT][DataPoint.LOW] = True

    def _update_atr_value(self):
        self._atr_value = round(get_average_true_range_value(self._latest_data[self.entry_timeframe]), 2)

    def _update_cmf_value(self):
        self._cmf_value = round(get_chaikin_money_flow_value(self._latest_data[self.entry_timeframe]), 2)

    def _update_for_new_session(self):
        self._reset_local_extremas()
        self._reset_session_trades_count()
        self._reset_new_extrema_flags()

    def _update_oanda_candlestick_data(self, now):
        self._update_latest_data()
        if self._latest_data:
            self._latest_candle = self._latest_data[self.entry_timeframe].iloc[-1]
            self._prev_exec = now.hour

    def _update_dynamic_tp_targets(self):
        self._dynamic_tp_targets = {
            trade['id']: round(float(trade['price']) + self._atr_value, self.instrument.price_precision)
            for trade
            in self.account.get_open_trades()['trades']
        }

    def _update_strategy_reqs(self):
        self._clear_pending_orders()
        self._trading_session_validator.date_time = self._get_latest_datetime() + timedelta(hours=1)
        self._update_atr_value()
        self._update_cmf_value()
        self._update_new_extrema_flags()
        if self._trading_session_validator.is_new_session():
            self._update_for_new_session()
        self._update_dynamic_tp_targets()

    def _close_active_if_dynamic_tp_hit(self):
        to_delete = []
        latest_prices = self._pricing.get_pricing_info([self.instrument.symbol], include_home_conversions=False)
        for trade_id, target_price in self._dynamic_tp_targets.items():
            if float(latest_prices['prices'][0]['bids'][0]['price']) >= target_price:
                try:
                    self.account.close_trade(trade_specifier=trade_id)
                    to_delete.append(trade_id)
                except Exception as exc:
                    logger.error(f"Failed to close trade: {trade_id} - {exc}", exc_info=True)
        for key in to_delete:
            del self._dynamic_tp_targets[key]

    def _adjust_session_trades_count(self, signal: Direction):
        if self._session_trade_counts[signal] > 0:
            self._session_trade_counts[signal] -= 1

    def _is_valid_size(self, direction: Direction) -> bool:
        return abs(float(self._latest_candle[Price.MID_OPEN]) - float(self._latest_candle[Price.MID_CLOSE])) \
                   < self._atr_value * self.max_candle_factors[direction]

    def _is_long_signal(self) -> bool:
        is_valid_size = self._is_valid_size(Direction.LONG)
        if not is_valid_size and self._new_extrema_flags[Direction.LONG][DataPoint.HIGH]:
            self._adjust_session_trades_count(Direction.LONG)
            return False
        if self._cmf_value <= 0:
            self._new_extrema_flags[Direction.LONG][DataPoint.HIGH] = False

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
        signals = {self.STRATEGY_LABEL: ''}
        if Direction.LONG in self.directions and self._is_long_signal():
            signals[self.STRATEGY_LABEL] = Direction.LONG
        elif Direction.SHORT in self.directions and self._is_short_signal():
            signals[self.STRATEGY_LABEL] = Direction.SHORT

        return signals

    def _get_entry_price_to_offset_from(self, signal: Direction) -> float:
        return float(self._latest_candle[Price.ASK_HIGH if signal == Direction.LONG else Price.BID_LOW])

    def _get_tp_pip_amount(self, signal: Direction) -> float:
        return self._atr_value * self.tp_multipliers[signal]

    def _get_sl_pip_amount(self, signal: Direction, entry_price: float) -> float:
        offset = self._atr_value * self.sl_multipliers[signal]
        if signal == Direction.LONG:
            offset *= -1
        sl_price = float(self._latest_candle[Price.BID_LOW if signal == Direction.LONG else Price.ASK_HIGH]) + offset

        return round(
            entry_price - sl_price if signal == Direction.LONG else sl_price - entry_price,
            self.instrument.price_precision,
        )

    def _execute_and_act_on_new_order(self, signal: Direction):
        entry_price = self._get_entry_price_to_offset_from(signal)
        units = self._get_unit_size_of_trade(entry_price)
        if units > 0:
            try:
                self._place_pending_order(
                    price_to_offset_from=entry_price,
                    entry_offset=self._atr_value / self.entry_offset_factors[signal],
                    worst_price_bound_offset=self._atr_value / 3,
                    sl_pip_amount=self._get_sl_pip_amount(signal, entry_price),
                    tp_pip_amount=self._get_tp_pip_amount(signal),
                    strategy=self.STRATEGY_LABEL,
                    signal=signal,
                    units=units,
                )
                self._adjust_session_trades_count(signal)
                self._reset_new_extrema_flags()
            except Exception as exc:
                logger.info(f'Failed place new pending order. {exc}', exc_info=True)
                self._send_mail_alert(source='place_order', additional_msg=str(exc))

    def _log_latest(self, signals: dict):
        logger.info(self._trading_session_validator)
        logger.info(f'prev candle: {self._prev_candle_datetime}')
        logger.info(f'latest candle: {self._latest_candle}')
        logger.info(f'chaikin money flow value: {self._cmf_value}')
        logger.info(f'average true range value: {self._atr_value}')
        logger.info(f'local extremas: {self._local_extremas}')
        logger.info(f'new extrema flags: {self._new_extrema_flags}')
        logger.info(f'remaining trades: {self._session_trade_counts}')
        logger.info(f'signals: {signals}')
        logger.info(f'dynamic tp targets: {self._dynamic_tp_targets}')

    def execute(self):
        london_tz = pytz.timezone('Europe/London')
        while 1:
            now = datetime.now().astimezone(london_tz)
            if self._should_run(now):
                self._close_active_if_dynamic_tp_hit()
                if now.minute == 0 and now.hour != self._prev_exec:
                    try:
                        self._sync_pending_orders(self.account.get_pending_orders()['orders'])
                    except Exception as exc:
                        logger.error(f'Failed to sync pending orders. {exc}', exc_info=True)
                    time.sleep(2)
                    self._update_oanda_candlestick_data(now)
                    if self._is_new_candle():
                        self._update_strategy_reqs()
                        signals = self._get_signals()
                        self._log_latest(signals)
                        for strategy, signal in signals.items():
                            if signal:
                                self._execute_and_act_on_new_order(signal)
                        self._prev_candle_datetime = self._get_latest_datetime()
