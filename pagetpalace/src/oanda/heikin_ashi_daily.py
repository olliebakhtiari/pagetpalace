# Python standard.
import pytz
import sys
import time
from datetime import datetime

# Local.
from pagetpalace.src.indicators import append_average_true_range, append_ssma, append_heikin_ashi
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.strategy import Strategy
from pagetpalace.tools.logger import *


class HeikinAshiDaily(Strategy):
    def __init__(
            self,
            account: OandaAccount,
            instrument: Instrument,
            ssma_period: int,
            boundary_multipliers: dict,
            trade_multipliers: dict,
            wait_time_precedence: int = 1,
            equity_split: float = 3.5,
    ):
        super().__init__(
            equity_split=equity_split,
            account=account,
            instrument=instrument,
            time_frames=['D'],
            entry_timeframe='D',
            sub_strategies_count=1,
        )
        self.ssma_period = ssma_period
        self.trade_multipliers = trade_multipliers
        self.boundary_multipliers = boundary_multipliers
        self._ssma_value = 0.
        self._atr_value = 0.
        self._heikin_ashi_signal = ''
        self.previous_entry_signal = ''
        self.re_entry_allowed = True
        self.wait_time_precedence = wait_time_precedence
        self._prev_exec_datetime = None

    def _update_atr_value(self):
        append_average_true_range(self._latest_data[self.entry_timeframe])
        self._atr_value = self._latest_data[self.entry_timeframe]['ATR_14'].values[-1]

    def _update_ssma_value(self):
        append_ssma(self._latest_data[self.entry_timeframe], periods=self.ssma_period)
        self._ssma_value = round(self._latest_data[self.entry_timeframe][f'SSMA_{self.ssma_period}'].values[-1], 5)

    def _update_heikin_ashi_signal(self):
        signal = ''
        append_heikin_ashi(self._latest_data[self.entry_timeframe])
        if self._latest_data[self.entry_timeframe]['HA_Open'].values[-1] \
                < self._latest_data[self.entry_timeframe]['HA_Close'].values[-1]:
            signal = 'long'
        self._heikin_ashi_signal = signal

    def _update_current_indicators_and_signals(self):
        self._update_atr_value()
        self._update_ssma_value()
        self._update_heikin_ashi_signal()
        if self._latest_data[self.entry_timeframe]['HA_High'].values[-1] > self._ssma_value:
            self.re_entry_allowed = True

    def _calculate_atr_factor(self) -> float:
        return abs((self._latest_data[self.entry_timeframe]['HA_Low'].values[-1] - self._ssma_value) / self._atr_value)

    def _calculate_boundary(self) -> float:
        price = self._latest_data[self.entry_timeframe]['HA_Low'].values[-1]
        try:
            if price >= self._ssma_value:
                boundary = self.boundary_multipliers['above']
            else:
                boundary = self.boundary_multipliers['below']
        except KeyError:  # Not interested in these situations, don't trade.
            boundary = sys.maxsize

        return boundary * self._atr_value

    def _has_met_reverse_trade_condition(self) -> bool:
        return self._calculate_atr_factor() * self._atr_value >= self._calculate_boundary()

    def _is_long_signal(self) -> bool:
        return self._heikin_ashi_signal == 'long' and self._has_met_reverse_trade_condition()

    def _get_signals(self, **kwargs) -> dict:
        return {'1': 'long' if self._is_long_signal() else ''}

    def _is_valid_new_signal(self) -> bool:
        return (self.previous_entry_signal != self._heikin_ashi_signal) and self.re_entry_allowed

    def _get_stop_loss_pip_amount(self) -> float:
        return self._latest_data[self.entry_timeframe]['midClose'].values[-1] \
               - self._latest_data[self.entry_timeframe]['midLow'].values[-1] \
               + ((self._atr_value / 15) * 2) \
               + (self._atr_value * self.trade_multipliers['1']['sl'])

    def _log_latest_values(self, now, signals):
        logger.info(f'latest candle: {self._latest_data[self.entry_timeframe].iloc[-1]}')
        logger.info(f'{now} signals: {signals}')

    def _place_new_pending_order_if_units_available(self, strategy: str, signal: str):
        last_close = self._latest_data[self.entry_timeframe]['midClose'].values[-1]
        try:
            units = self._get_unit_size_of_trade(last_close)
            if units > 0:
                self._place_pending_order(
                    price_to_offset_from=last_close,
                    entry_offset=self._atr_value / 15,
                    worst_price_bound_offset=self._atr_value / 5,
                    sl_pip_amount=self._get_stop_loss_pip_amount(),
                    tp_pip_amount=self._atr_value * self.trade_multipliers[strategy][signal]['tp'],
                    strategy=strategy,
                    signal=signal,
                    units=units,
                )
        except Exception as exc:
            logger.info(f'Failed place new pending order. {exc}', exc_info=True)
            self._send_mail_alert(error_source='place_order', exc_msg=str(exc))

    def execute(self):
        london_tz = pytz.timezone('Europe/London')
        prev_exec = -1
        while 1:
            now = datetime.now().astimezone(london_tz)
            if now.isoweekday() != 6:
                if now.minute == 0 and (now.hour == 21 or now.hour == 22) and now.hour != prev_exec:
                    time.sleep(8 + (self.wait_time_precedence / 10) + 0.06)
                    self._update_latest_data()
                    if self._latest_data:
                        prev_exec = now.hour
                        if self._prev_exec_datetime != self._latest_data[self.entry_timeframe].iloc[-1]['datetime']:
                            self._update_current_indicators_and_signals()
                            signals = self._get_signals()
                            self._log_latest_values(now, signals)

                            # New orders.
                            for strategy, signal in signals.items():
                                if signal and self._is_valid_new_signal():
                                    self._place_new_pending_order_if_units_available(strategy, signal)
                                    self.re_entry_allowed = False
                            self._prev_exec_datetime = self._latest_data[self.entry_timeframe].iloc[-1]['datetime']
                        self.previous_entry_signal = self._heikin_ashi_signal
