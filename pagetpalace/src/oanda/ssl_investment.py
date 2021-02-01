# Python standard.
import pytz
import time
from datetime import datetime
from typing import Dict

# Local.
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.live_trade_monitor import LiveTradeMonitor
from pagetpalace.src.oanda.ssl_multi import SSLMultiTimeFrame
from pagetpalace.src.indicators import append_average_true_range, append_ssma
from pagetpalace.tools.logger import *


class SSLInvestment(SSLMultiTimeFrame):
    def __init__(
            self,
            account: OandaAccount,
            instrument: Instrument,
            trade_multipliers: dict,
            boundary_multipliers: dict,
            live_trade_monitor: LiveTradeMonitor,
    ):
        super().__init__(
            equity_split=1.75,
            account=account,
            instrument=instrument,
            time_frames=['D', 'H1'],
            entry_timeframe='H1',
            sub_strategies_count=1,
            trade_multipliers=trade_multipliers,
            boundary_multipliers=boundary_multipliers,
            live_trade_monitor=live_trade_monitor,
        )

    def _update_atr_values(self):
        append_average_true_range(self._latest_data['H1'])
        self._atr_values['H1'] = round(self._latest_data['H1'].iloc[-1]['ATR_14'], 5)

    def _update_ssma_values(self):
        append_ssma(self._latest_data['H1'])
        self._ssma_values['H1'] = round(self._latest_data['H1'].iloc[-1]['SSMA_50'], 5)

    def _is_continuation_long_criteria_met(self, price):
        return self._current_ssl_values['D'] == 1 and self._current_ssl_values['H1'] == 1 \
               and self._is_within_valid_boundary('long', price, 'H1')

    def _get_signals(self, **kwargs) -> Dict[str, str]:
        return {'1': 'long' if self._is_continuation_long_criteria_met(kwargs['price']) else ''}

    def _place_new_pending_order_if_units_available(self, price_to_offset_from: float, strategy: str, signal: str):
        try:
            units = self._get_unit_size_of_trade(price_to_offset_from)
            if units > 0:
                sl_pip_amount = self._atr_values[self.entry_timeframe] * self.trade_multipliers[strategy][signal]['sl']
                self._place_pending_order(
                    price_to_offset_from=price_to_offset_from,
                    entry_offset=self._atr_values[self.entry_timeframe] / 5,
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
        is_first_run = True
        while 1:
            now = datetime.now().astimezone(london_tz)
            try:
                self._sync_pending_orders(self.account.get_pending_orders()['orders'])
            except Exception as exc:
                logger.error(f'Failed to sync pending orders. {exc}', exc_info=True)
            if now.minute == 0 and now.hour != prev_exec:
                time.sleep(8.1)
                self._update_latest_data()
                if self._latest_data:
                    self._update_current_indicators_and_signals()
                    last_h1_close = float(self._latest_data['H1']['midClose'].values[-1])
                    signals = self._get_signals(price=last_h1_close)
                    self._log_latest_values(now, signals)

                    # Remove outdated pending orders depending on entry signals.
                    self._check_and_clear_pending_orders()

                    # New orders.
                    for strategy, signal in signals.items():
                        if signal and self._has_new_entry_signal() and not is_first_run:
                            self._place_new_pending_order_if_units_available(last_h1_close, strategy, signal)
                prev_exec = now.hour
                self._update_previous_ssl_values()
                is_first_run = False

            # Monitor and adjust current trades, if any.
            time.sleep(1.1)
            self._live_trade_monitor.monitor_and_adjust_current_trades()

            # Remove outdated entries in local lists.
            if now.hour % 24 == 0:
                self._live_trade_monitor.clean_lists()
