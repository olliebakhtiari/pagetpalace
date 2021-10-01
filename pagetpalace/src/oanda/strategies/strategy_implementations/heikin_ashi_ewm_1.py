# Python standard.
import pytz
import sys
import time
from datetime import datetime

# Local.
from pagetpalace.src.indicators.indicators import (
    get_average_true_range_value,
    append_heikin_ashi,
    append_exponentially_weighted_moving_average,
    append_ssma,
)
from pagetpalace.src.oanda.instruments.instruments import Instrument
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.strategies.strategy import Strategy
from pagetpalace.tools.logger import *


class HeikinAshiEwm1(Strategy):
    def __init__(
            self,
            account: OandaAccount,
            instrument: Instrument,
            ssma_period: int,
            ewm_period: int,
            boundary_multipliers: dict,
            trade_multipliers: dict,
            wait_time_precedence: int = 1,
            equity_split: float = 4,
    ):
        super().__init__(
            equity_split=equity_split,
            account=account,
            instrument=instrument,
            time_frames=['D'],
            entry_timeframe='D',
            sub_strategies_count=1,
            max_risk_pct=0.1,
        )
        self.ssma_period = ssma_period
        self.ewm_period = ewm_period
        self.trade_multipliers = trade_multipliers
        self.boundary_multipliers = boundary_multipliers
        self.directions = tuple(trade_multipliers['1'].keys())
        self._ewm_value = 0.
        self._ssma_value = 0.
        self._atr_value = 0.
        self._heikin_ashi_signal = ''
        self._previous_entry_signal = ''
        self.wait_time_precedence = wait_time_precedence
        self._prev_exec_datetime = None

    def _check_and_clear_pending_orders(self, ha_signal: str):
        if ha_signal != self._previous_entry_signal:
            try:
                self._clear_pending_orders()
            except Exception as exc:
                logger.error(f'Failed to clear pending orders. {exc}', exc_info=True)
                self._send_mail_alert(source='clear_pending', additional_msg=str(exc))

    def _update_atr_value(self):
        get_average_true_range_value(self._latest_data[self.entry_timeframe])
        self._atr_value = self._latest_data[self.entry_timeframe]['ATR_14'].values[-1]

    def _update_ssma_value(self):
        append_ssma(self._latest_data[self.entry_timeframe], periods=self.ssma_period)
        self._ssma_value = round(self._latest_data[self.entry_timeframe][f'SSMA_{self.ssma_period}'].values[-1], 5)

    def _update_ewm_value(self):
        append_exponentially_weighted_moving_average(self._latest_data[self.entry_timeframe], period=self.ewm_period)
        self._ewm_value = round(self._latest_data[self.entry_timeframe][f'EWM_{self.ewm_period}'].values[-1], 5)

    def _update_heikin_ashi_signals(self):
        signal = ''
        append_heikin_ashi(self._latest_data[self.entry_timeframe])
        if self._latest_data[self.entry_timeframe]['HA_Open'].values[-1] \
                < self._latest_data[self.entry_timeframe]['HA_Close'].values[-1]:
            signal = 'long'
        elif self._latest_data[self.entry_timeframe]['HA_Open'].values[-1] \
                > self._latest_data[self.entry_timeframe]['HA_Close'].values[-1]:
            signal = 'short'
        self._heikin_ashi_signal = signal

    def _update_current_indicators_and_signals(self):
        self._update_atr_value()
        self._update_ssma_value()
        self._update_ewm_value()
        self._update_heikin_ashi_signals()

    def _calculate_atr_factor(self, price: float) -> float:
        return abs((price - self._ssma_value) / self._atr_value)

    def _calculate_boundary(self, bias: str, price: float) -> float:
        try:
            if price >= self._ssma_value:
                boundary = self.boundary_multipliers[self.entry_timeframe][bias]['above']
            else:
                boundary = self.boundary_multipliers[self.entry_timeframe][bias]['below']
        except KeyError:  # Not interested in these situations, don't trade.
            boundary = sys.maxsize

        return boundary * self._atr_value

    def _is_within_valid_boundary(self, bias: str, price: float) -> float:
        return not (self._calculate_atr_factor(price) * self._atr_value > self._calculate_boundary(bias, price))

    def _is_long_condition(self) -> bool:
        return self._ewm_value > self._ssma_value \
            and self._heikin_ashi_signal == 'long' \
            and self._is_within_valid_boundary(
                    'long',
                    float(self._latest_data[self.entry_timeframe]['midClose'].values[-1])
                )

    def _is_short_condition(self) -> bool:
        return self._ewm_value < self._ssma_value \
            and self._heikin_ashi_signal == 'short' \
            and self._is_within_valid_boundary(
                    'short',
                    float(self._latest_data[self.entry_timeframe]['midClose'].values[-1])
                )

    def _get_signals(self, **kwargs) -> dict:
        signal = ''
        long = 'long'
        short = 'short'
        if long in self.directions and self._is_long_condition():
            signal = long
        elif short in self.directions and self._is_short_condition():
            signal = short

        return {'1': signal}

    def _place_new_pending_order_if_units_available(self, strategy: str, signal: str):
        price = 'askClose' if signal == 'long' else 'bidClose'
        last_close = float(self._latest_data[self.entry_timeframe][price].values[-1])
        if self._is_instrument_below_num_of_trades_cap(2):
            try:
                units = self._get_unit_size_of_trade(last_close)
                if units > 0:
                    self._place_pending_order(
                        price_to_offset_from=last_close,
                        entry_offset=self._atr_value / 15,
                        worst_price_bound_offset=None,
                        sl_pip_amount=self._atr_value * self.trade_multipliers[strategy][signal]['sl'],
                        tp_pip_amount=self._atr_value * self.trade_multipliers[strategy][signal]['tp'],
                        strategy=strategy,
                        signal=signal,
                        units=units,
                    )
            except Exception as exc:
                logger.info(f'Failed place new pending order. {exc}', exc_info=True)
                self._send_mail_alert(source='place_order', additional_msg=str(exc))
        else:
            logger.info(f'Instrument has reached trade cap of 2.')
            self._send_mail_alert(source='ins_trade_cap', additional_msg='trade not taken.')

    def _log_latest_values(self, now, signals):
        logger.info(f'latest candle: {self._latest_data[self.entry_timeframe].iloc[-1]}')
        logger.info(f'{now} signals: {signals}')

    def execute(self):
        london_tz = pytz.timezone('Europe/London')
        prev_exec = -1
        first_run = True
        while 1:
            now = datetime.now().astimezone(london_tz)
            if now.isoweekday() != 6:
                if now.minute == 0 and (now.hour == 21 or now.hour == 22) and now.hour != prev_exec:
                    time.sleep(8 + (self.wait_time_precedence / 5) + 0.03)
                    self._update_latest_data()
                    if self._latest_data:
                        prev_exec = now.hour
                        if self._prev_exec_datetime != self._latest_data[self.entry_timeframe].iloc[-1]['datetime']:
                            self._update_current_indicators_and_signals()
                            self._check_and_clear_pending_orders(self._heikin_ashi_signal)
                            signals = self._get_signals()
                            self._log_latest_values(now, signals)

                            # New orders.
                            for strategy, signal in signals.items():
                                if signal and self._previous_entry_signal != self._heikin_ashi_signal and not first_run:
                                    self._place_new_pending_order_if_units_available(strategy, signal)
                            self._prev_exec_datetime = self._latest_data[self.entry_timeframe].iloc[-1]['datetime']
                        self._previous_entry_signal = self._heikin_ashi_signal
                        first_run = False
