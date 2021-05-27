# Python standard.
import pytz
import time
from datetime import datetime
from typing import Dict, Union

# Local.
from pagetpalace.src.indicators import (
    append_average_true_range,
    append_ssma,
    get_hammer_pin_signal,
    is_candle_range_greater_than_x,
)
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.ssl_multi import SSLMultiTimeFrame
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
            ssl_periods: Dict[str, int] = None,
            wait_time_precedence: int = 1,
            equity_split: float = 2.25,
            entry_ssma_period: int = 20,
            x_atr_coeffs: Dict[str, float] = None,
    ):
        time_frames = ['D', 'H1']
        super().__init__(
            equity_split=equity_split,
            account=account,
            instrument=instrument,
            time_frames=time_frames,
            entry_timeframe='H1',
            sub_strategies_count=1,
            boundary_multipliers=boundary_multipliers,
            trade_multipliers=trade_multipliers,
            ssl_periods={tf: 10 for tf in time_frames} if not ssl_periods else ssl_periods,
        )
        self.hammer_pin_coefficients = hammer_pin_coefficients
        self.trading_restriction = trading_restriction  # 'trading_hours' or 'spread_cap'.
        self.directions = tuple(hammer_pin_coefficients.keys())
        self.x_atr_coeffs = {direction: 0.0001 for direction in self.directions} if not x_atr_coeffs else x_atr_coeffs
        self.spread_cap = spread_cap
        self.entry_ssma_period = entry_ssma_period
        self._prev_latest_candle_datetime = None
        self._wait_time_precedence = wait_time_precedence

    def _check_and_clear_pending_orders(self):
        """ Overwrite method to clear regardless of new signal, clear based on time. (A trade has an hour to fill). """
        try:
            self._clear_pending_orders()
        except Exception as exc:
            logger.error(f'Failed to clear pending orders. {exc}', exc_info=True)
            self._send_mail_alert(source='clear_pending', additional_msg=str(exc))

    def _update_atr_values(self):
        for tf in self.time_frames:
            append_average_true_range(self._latest_data[tf])
            self._atr_values[tf] = round(self._latest_data[tf].iloc[-1]['ATR_14'], 5)

    def _update_ssma_values(self):
        append_ssma(self._latest_data['H1'], periods=self.entry_ssma_period)
        self._ssma_values['H1'] = round(self._latest_data['H1'].iloc[-1][f'SSMA_{self.entry_ssma_period}'], 5)

    def _is_long_signal(self) -> bool:
        candle = self._latest_data['H1'].iloc[-1]
        bias = 'long'
        coeffs = self.hammer_pin_coefficients[bias]
        hammer_pin_signal = get_hammer_pin_signal(candle, coeffs['body'], coeffs['head_tail'])
        midlow_distance_met = self._has_met_reverse_trade_condition(bias, float(candle['midLow']), 'H1')

        return hammer_pin_signal == bias and self._current_ssl_values['D'] == 1 and midlow_distance_met

    def _is_short_signal(self) -> bool:
        candle = self._latest_data['H1'].iloc[-1]
        bias = 'short'
        coeffs = self.hammer_pin_coefficients[bias]
        hammer_pin_signal = get_hammer_pin_signal(candle, coeffs['body'], coeffs['head_tail'])
        midhigh_distance_met = self._has_met_reverse_trade_condition(bias, float(candle['midHigh']), 'H1')

        return hammer_pin_signal == bias and self._current_ssl_values['D'] == -1 and midhigh_distance_met

    def _is_big_enough_movement(self, bias: str) -> bool:
        return is_candle_range_greater_than_x(
            self._latest_data['H1'].iloc[-1],
            self._atr_values[self.entry_timeframe] * self.x_atr_coeffs[bias],
        )

    def _get_s1_signal(self) -> Union[str, None]:
        signal = None
        long = 'long'
        short = 'short'
        if long in self.directions and self._is_big_enough_movement(long) and self._is_long_signal():
            signal = long
        elif short in self.directions and self._is_big_enough_movement(short) and self._is_short_signal():
            signal = short

        return signal

    def _get_signals(self, **kwargs) -> Dict[str, Union[str, None]]:
        return {'1': self._get_s1_signal()}

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
        if self._is_instrument_below_num_of_trades_cap():
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
                else:
                    logger.warning('Not enough margin available to place an order!')
                    self._send_mail_alert(source='no_margin_available', additional_msg='trade missed.')
            except Exception as exc:
                logger.info(f'Failed place new pending order. {exc}', exc_info=True)
                self._send_mail_alert(source='place_order', additional_msg=str(exc))
        else:
            logger.info(f'Instrument has reached trade cap of {self._num_trades_cap}, order not placed.')
            self._send_mail_alert(source='ins_trade_cap', additional_msg='trade not taken.')

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
                    time.sleep(8 + (self._wait_time_precedence / 10))
                    self._update_latest_data()
                    if self._latest_data:
                        prev_exec = now.hour
                        if self._prev_latest_candle_datetime != self._latest_data['H1'].iloc[-1]['datetime']:
                            self._check_and_clear_pending_orders()
                            self._update_current_indicators_and_signals()
                            signals = self._get_signals()
                            self._log_latest_values(now, signals)

                            # New orders.
                            if self._is_within_trading_restriction(now):
                                for strategy, signal in signals.items():
                                    if signal:
                                        self._place_new_pending_order_if_units_available(strategy, signal)
                            self._update_previous_ssl_values()
                            self._prev_latest_candle_datetime = self._latest_data['H1'].iloc[-1]['datetime']
