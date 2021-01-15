# Python standard.
import pytz
import time
from datetime import datetime
from typing import Dict

# Local.
from pagetpalace.src.indicators import append_average_true_range, append_ssma
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda import OandaAccount
from pagetpalace.src.oanda.live_trade_monitor import LiveTradeMonitor
from pagetpalace.src.oanda.ssl_multi import SSLMultiTimeFrame
from pagetpalace.tools.logger import *


class SSLCurrency(SSLMultiTimeFrame):
    def __init__(
            self,
            account: OandaAccount,
            instrument: Instrument,
            trade_multipliers: dict,
            boundary_multipliers: dict,
            live_trade_monitor: LiveTradeMonitor,
    ):
        super().__init__(
            equity_split=2,
            account=account,
            instrument=instrument,
            time_frames=['W', 'D', 'H4', 'M30'],
            entry_timeframe='M30',
            sub_strategies_count=1,
            trade_multipliers=trade_multipliers,
            boundary_multipliers=boundary_multipliers,
            live_trade_monitor=live_trade_monitor,
        )

    def _update_atr_values(self):
        append_average_true_range(self._latest_data['M30'])
        self._atr_values['M30'] = round(self._latest_data['M30'].iloc[-1]['ATR_14'], 5)

    def _update_ssma_values(self):
        append_ssma(self._latest_data['M30'])
        self._ssma_values['M30'] = round(self._latest_data['M30'].iloc[-1]['SSMA_50'], 5)

    def _get_signals(self) -> Dict[str, str]:
        signals = {'1': ''}
        if all(self._current_ssl_values[tf] == 1 for tf in self.time_frames):
            signals['1'] = 'long'
        if all(self._current_ssl_values[tf] == -1 for tf in self.time_frames):
            signals['1'] = 'short'

        return signals

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
            if now.minute % 30 == 0 and now.minute != prev_exec:
                time.sleep(8)
                self._update_latest_data()
                if self._latest_data:
                    last_30m_close = float(self._latest_data['M30']['midClose'].values[-1])
                    self._update_current_indicators_and_signals()
                    signals = self._get_signals()
                    self._log_latest_values(now, signals)

                    # Remove outdated pending orders depending on entry signals.
                    self._check_and_clear_pending_orders()

                    # New orders.
                    for strategy, signal in signals.items():
                        if signal:
                            try:
                                spread = float(self._latest_data['M30']['askOpen'].values[-1]) \
                                         - float(self._latest_data['M30']['bidOpen'].values[-1])
                                units = self._get_unit_size_of_trade(last_30m_close)
                                is_within_valid_boundary = self._is_within_valid_boundary(signal, last_30m_close, 'M30')
                                if units > 0 and spread <= 0.0004 and is_within_valid_boundary \
                                        and self._has_new_signal() and not is_first_run:
                                    sl_pip_amount = self._atr_values[self.entry_timeframe] \
                                                    * self.trade_multipliers[strategy][signal]['sl']
                                    self._place_pending_order(
                                        price_to_offset_from=last_30m_close,
                                        entry_offset=self._atr_values[self.entry_timeframe] / 5,
                                        sl_pip_amount=sl_pip_amount,
                                        tp_pip_amount=sl_pip_amount * self.trade_multipliers[strategy][signal]['tp'],
                                        strategy=strategy,
                                        signal=signal,
                                        units=units,
                                    )
                            except Exception as exc:
                                logger.info(f'Failed place new pending order. {exc}', exc_info=True)
                    prev_exec = now.minute
                    is_first_run = False
                    self._update_previous_ssl_values()

            # Monitor and adjust current trades, if any.
            time.sleep(1)
            self._live_trade_monitor.monitor_and_adjust_current_trades()

            # Remove outdated entries in local lists.
            if now.hour % 24 == 0:
                self._live_trade_monitor.clean_lists()
