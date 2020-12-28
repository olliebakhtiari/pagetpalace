# Python standard.
import pytz
import time
from datetime import datetime
from typing import Dict, Union

# Local.
from pagetpalace.src.indicators import append_average_true_range, append_ssma, get_hammer_pin_signal
from pagetpalace.src.oanda import OandaAccount
from pagetpalace.src.oanda.ssl_multi import SSLMultiTimeFrame
from pagetpalace.src.signal import Signal
from pagetpalace.tools.logger import *


class SSLHammerPin(SSLMultiTimeFrame):
    def __init__(self,
                 account: OandaAccount,
                 instrument: str,
                 boundary_multipliers: dict,
                 hammer_pin_coefficients: dict,
                 partial_closure_params: dict = None,
    ):
        super().__init__(
            equity_split=1.75,
            margin_ratio=30,
            unrestricted_margin_cap=0.9,
            account=account,
            instrument=instrument,
            time_frames=['D', 'H1'],
            entry_timeframe='H1',
            sub_strategies_count=1,
            boundary_multipliers=boundary_multipliers,
            partial_closure_params=partial_closure_params,
            ssl_periods=10,
        )
        """ 
            hammer_pin_coefficients = {
                'long': {'body': 2, 'head_tail': 5}, 
                'short': {'body': 6, 'head_tail': 3},
            }
        """
        self.hammer_pin_coefficients = hammer_pin_coefficients

    def _check_and_clear_pending_orders(self):
        """ Overwrite method to clear regardless of new signal, clear based on time. (A trade has an hour to fill). """
        try:
            self._clear_pending_orders()
        except Exception as exc:
            logger.error(f'Failed to clear pending orders. {exc}', exc_info=True)

    def _update_atr_values(self):
        for tf in self.time_frames:
            append_average_true_range(self._latest_data[tf])
            self._atr_values[tf] = round(self._latest_data[tf].iloc[-1]['ATR_14'], 5)

    def _update_ssma_values(self):
        append_ssma(self._latest_data['H1'], periods=20)
        self._ssma_values['H1'] = round(self._latest_data['H1'].iloc[-1]['SSMA_20'], 5)

    def _is_long_signal(self, prev_candle) -> bool:
        bias = 'long'
        coeffs = self.hammer_pin_coefficients[bias]
        hammer_pin_signal = get_hammer_pin_signal(prev_candle, coeffs['body'], coeffs['head_tail'])
        midlow_20_distance_met = self._has_met_reverse_trade_condition(bias, float(prev_candle['midLow'].values[0]), 'H1')

        return hammer_pin_signal == bias and self._current_ssl_values['D'] == 1 and midlow_20_distance_met

    def _is_short_signal(self, prev_candle) -> bool:
        bias = 'short'
        coeffs = self.hammer_pin_coefficients[bias]
        hammer_pin_signal = get_hammer_pin_signal(prev_candle, coeffs['body'], coeffs['head_tail'])
        midhigh_20_distance_met = self._has_met_reverse_trade_condition(bias, float(prev_candle['midHigh'].values[0]), 'H1')

        return hammer_pin_signal == bias and self._current_ssl_values['D'] == -1 and midhigh_20_distance_met

    def _get_s1_signal(self, prev_candle) -> Union[Signal, None]:
        signal = None
        if self._is_long_signal(prev_candle):
            signal = Signal('reverse', 'long', 4., 2.5)
        elif self._is_short_signal(prev_candle):
            signal = Signal('reverse', 'short', 1., 3.5)

        return signal

    def _get_signals(self, **kwargs) -> Dict[str, Union[Signal, None]]:
        return {'1': self._get_s1_signal(kwargs['prev_candle'])}

    @classmethod
    def _is_within_trading_hours(cls, curr_dt: datetime) -> bool:
        return 7 <= curr_dt.hour < 22

    def _get_price_to_use_for_entry_offset(self, signal: str) -> float:
        if signal == 'long':
            price = float(self._latest_data['H1']['midHigh'].values[0])
        else:
            price = float(self._latest_data['H1']['midLow'].values[0])

        return price

    def _place_new_pending_order_if_units_available(self, strategy: str, signal: Signal):
        try:
            units = self._get_unit_size_of_trade(self.account.get_full_account_details()['account'])
            if units > 0:
                sl_pip_amount = self._atr_values[self.entry_timeframe] * signal.stop_loss_multiplier
                self._place_pending_order(
                    price_to_offset_from=self._get_price_to_use_for_entry_offset(signal.bias),
                    entry_offset=self._atr_values[self.entry_timeframe] / 7,
                    sl_pip_amount=sl_pip_amount,
                    tp_pip_amount=sl_pip_amount * signal.take_profit_multiplier,
                    strategy=strategy,
                    signal=signal.bias,
                    margin=units,
                )
        except Exception as exc:
            logger.info(f'Failed place new pending order. {exc}', exc_info=True)

    def execute(self):
        london_tz = pytz.timezone('Europe/London')
        prev_exec = -1
        is_first_run = True
        while 1:
            now = datetime.now().astimezone(london_tz)
            if now.isoweekday() != 6:
                try:
                    self._sync_pending_orders(self.account.get_pending_orders()['orders'])
                except Exception as exc:
                    logger.error(f'Failed to sync pending orders. {exc}', exc_info=True)
                if now.minute == 0 and now.hour != prev_exec:

                    # Remove pending orders every hour.
                    self._check_and_clear_pending_orders()

                    time.sleep(8)
                    self._update_latest_data()
                    if self._latest_data:
                        self._update_current_indicators_and_signals()
                        signals = self._get_signals(prev_candle=self._latest_data['H1'])
                        self._log_latest_values(now, signals)

                        # New orders.
                        if self._is_within_trading_hours(now):
                            for strategy, signal in signals.items():
                                if signal and not is_first_run:
                                    self._place_new_pending_order_if_units_available(strategy, signal)
                        prev_exec = now.hour
                        is_first_run = False
                        self._update_previous_ssl_values()

                # Monitor and adjust current trades, if any.
                time.sleep(1)
                self._monitor_and_adjust_current_trades()

                # Remove outdated entries in local lists.
                if now.hour % 24 == 0:
                    self._clean_lists()
