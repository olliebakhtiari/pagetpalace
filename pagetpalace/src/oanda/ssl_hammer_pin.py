# Python standard.
import pytz
import time
from datetime import datetime
from typing import Dict, Union

# Local.
from pagetpalace.src.indicators import append_average_true_range, append_ssma, get_hammer_pin_signal
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.ssl_multi import SSLMultiTimeFrame
from pagetpalace.src.oanda.live_trade_monitor import LiveTradeMonitor
from pagetpalace.tools.logger import *


class SSLHammerPin(SSLMultiTimeFrame):
    def __init__(
            self,
            account: OandaAccount,
            instrument: Instrument,
            boundary_multipliers: dict,
            trade_multipliers: dict,
            hammer_pin_coefficients: dict,
            trading_restriction: str,
            spread_cap: float = None,
            live_trade_monitor: LiveTradeMonitor = None,
            ssl_periods: Dict[str, int] = None,
    ):
        time_frames = ['D', 'H1']
        super().__init__(
            equity_split=1.75,
            account=account,
            instrument=instrument,
            time_frames=time_frames,
            entry_timeframe='H1',
            sub_strategies_count=1,
            boundary_multipliers=boundary_multipliers,
            trade_multipliers=trade_multipliers,
            live_trade_monitor=live_trade_monitor,
            ssl_periods={tf: 10 for tf in time_frames} if not ssl_periods else ssl_periods,
        )
        self.hammer_pin_coefficients = hammer_pin_coefficients
        self.trading_restriction = trading_restriction  # 'trading_hours' or 'spread_cap'.
        self.directions = tuple(hammer_pin_coefficients.keys())
        self.spread_cap = spread_cap
        self._prev_latest_candle_datetime = None

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
        midlow_20_distance_met = self._has_met_reverse_trade_condition(bias, float(prev_candle['midLow']), 'H1')

        return hammer_pin_signal == bias and self._current_ssl_values['D'] == 1 and midlow_20_distance_met

    def _is_short_signal(self, prev_candle) -> bool:
        bias = 'short'
        coeffs = self.hammer_pin_coefficients[bias]
        hammer_pin_signal = get_hammer_pin_signal(prev_candle, coeffs['body'], coeffs['head_tail'])
        midhigh_20_distance_met = self._has_met_reverse_trade_condition(bias, float(prev_candle['midHigh']), 'H1')

        return hammer_pin_signal == bias and self._current_ssl_values['D'] == -1 and midhigh_20_distance_met

    def _get_s1_signal(self, prev_candle) -> Union[str, None]:
        signal = None
        long = 'long'
        short = 'short'
        if long in self.directions and self._is_long_signal(prev_candle):
            signal = long
        elif short in self.directions and self._is_short_signal(prev_candle):
            signal = short

        return signal

    def _get_signals(self, **kwargs) -> Dict[str, Union[str, None]]:
        return {'1': self._get_s1_signal(kwargs['prev_candle'])}

    @classmethod
    def _is_within_trading_hours(cls, curr_dt) -> bool:
        return 7 <= curr_dt.hour < 22

    def _is_within_spread_cap(self) -> bool:
        return float(self._latest_data['H1']['askOpen'].values[-1]) \
               - float(self._latest_data['H1']['bidOpen'].values[-1]) <= self.spread_cap

    def _is_within_trading_restriction(self, curr_dt) -> bool:
        if self.trading_restriction == 'trading_hours':
            is_valid = self._is_within_trading_hours(curr_dt)
        elif self.trading_restriction == 'spread_cap':
            is_valid = self._is_within_spread_cap()
        else:
            raise ValueError('Trading restriction not recognised.')

        return is_valid

    def _get_price_to_use_for_entry_offset(self, signal: str) -> float:
        if signal == 'long':
            price = float(self._latest_data['H1']['midHigh'].values[-1])
        else:
            price = float(self._latest_data['H1']['midLow'].values[-1])

        return price

    def _place_new_pending_order_if_units_available(self, strategy: str, signal: str):
        entry_price = self._get_price_to_use_for_entry_offset(signal)
        try:
            units = self._get_unit_size_of_trade(entry_price)
            if units > 0:
                sl_pip_amount = self._atr_values[self.entry_timeframe] * self.trade_multipliers[strategy][signal]['sl']
                self._place_pending_order(
                    price_to_offset_from=entry_price,
                    entry_offset=self._atr_values[self.entry_timeframe] / 7,
                    worst_price_bound_offset=self._atr_values[self.entry_timeframe] / 2,
                    sl_pip_amount=sl_pip_amount,
                    tp_pip_amount=sl_pip_amount * self.trade_multipliers[strategy][signal]['tp'],
                    strategy=strategy,
                    signal=signal,
                    units=units,
                )
        except Exception as exc:
            logger.info(f'Failed place new pending order. {exc}', exc_info=True)

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
                if now.minute == 0 and now.hour != prev_exec:
                    time.sleep(8)
                    self._update_latest_data()
                    if self._latest_data:
                        prev_exec = now.hour
                        if self._prev_latest_candle_datetime != self._latest_data['H1'].iloc[-1]['datetime']:
                            self._check_and_clear_pending_orders()
                            self._update_current_indicators_and_signals()
                            signals = self._get_signals(prev_candle=self._latest_data['H1'].iloc[-1])
                            self._log_latest_values(now, signals)

                            # New orders.
                            if self._is_within_trading_restriction(now):
                                for strategy, signal in signals.items():
                                    if signal:
                                        self._place_new_pending_order_if_units_available(strategy, signal)
                            self._update_previous_ssl_values()
                            self._prev_latest_candle_datetime = self._latest_data['H1'].iloc[-1]['datetime']
