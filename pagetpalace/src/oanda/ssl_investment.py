# Python standard.
import pytz
import time
from datetime import datetime
from typing import Dict

# Local.
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda import OandaAccount, OandaPricingData
from pagetpalace.src.oanda.live_trade_monitor import LiveTradeMonitor
from pagetpalace.src.oanda.ssl_multi import SSLMultiTimeFrame
from pagetpalace.src.indicators import append_average_true_range, append_ssma
from pagetpalace.tools.logger import *


class SSLInvestment(SSLMultiTimeFrame):
    def __init__(
            self,
            account: OandaAccount,
            pricing_data_retriever: OandaPricingData,
            instrument: Instrument,
            trade_multipliers: dict,
            boundary_multipliers: dict,
            live_trade_monitor: LiveTradeMonitor,
    ):
        super().__init__(
            equity_split=1.75,
            unrestricted_margin_cap=0.9,
            account=account,
            pricing_data_retriever=pricing_data_retriever,
            instrument=instrument,
            time_frames=['D', 'H1', 'M5'],
            entry_timeframe='M5',
            sub_strategies_count=2,
            trade_multipliers=trade_multipliers,
            boundary_multipliers=boundary_multipliers,
            live_trade_monitor=live_trade_monitor,
        )

    def _update_atr_values(self):
        append_average_true_range(self._latest_data['H1'])
        append_average_true_range(self._latest_data['M5'])
        self._atr_values['H1'] = round(self._latest_data['H1'].iloc[-1]['ATR_14'], 5)
        self._atr_values['M5'] = round(self._latest_data['M5'].iloc[-1]['ATR_14'], 5)

    def _update_ssma_values(self):
        append_ssma(self._latest_data['H1'])
        append_ssma(self._latest_data['M5'])
        self._ssma_values['H1'] = round(self._latest_data['H1'].iloc[-1]['SSMA_50'], 5)
        self._ssma_values['M5'] = round(self._latest_data['M5'].iloc[-1]['SSMA_50'], 5)

    def _update_entry_signals(self):
        self._entry_signals = {
            '1': {
                'previous': self._previous_ssl_values['H1'],
                'current': self._current_ssl_values['H1'],
            },
            '2': {
                'previous': self._previous_ssl_values[self.entry_timeframe],
                'current': self._current_ssl_values[self.entry_timeframe],
            }
        }

    def _has_new_signal(self, strategy: str) -> bool:
        return self._entry_signals[strategy]['previous'] != self._entry_signals[strategy]['current']

    def _clear_pending_orders(self, strategy: str):
        for id_ in self._pending_orders[strategy]:
            self.account.cancel_order(id_)
        self._pending_orders[strategy].clear()

    def _check_and_clear_pending_orders(self):
        for strategy in ['1', '2']:
            if self._has_new_signal(strategy):
                try:
                    self._clear_pending_orders(strategy)
                except Exception as exc:
                    logger.error(f'Failed to clear pending orders. {exc}', exc_info=True)

    def _is_continuation_long_criteria_met(self, price):
        return self._current_ssl_values['D'] == 1 and self._current_ssl_values['H1'] == 1 \
               and self._is_within_valid_boundary('long', price, 'H1')

    def _is_reverse_trade_long_criteria_met(self, price: float) -> bool:
        return self._current_ssl_values['D'] == -1 and self._current_ssl_values['H1'] == 1 \
               and self._current_ssl_values['M5'] == 1 and self._has_met_reverse_trade_condition('long', price, 'H1')

    def _get_signals(self, **kwargs) -> Dict[str, str]:
        signals = {'1': '', '2': ''}

        # Strategy one.
        if self._is_continuation_long_criteria_met(kwargs['price']):
            signals['1'] = 'long'

        # Strategy two.
        if self._is_reverse_trade_long_criteria_met(kwargs['price']):
            signals['2'] = 'long'

        return signals

    def _place_new_pending_order_if_units_available(self, price_to_offset_from: float, strategy: str, signal: str):
        try:
            units = self._get_unit_size_of_trade(self.account.get_full_account_details()['account'])
            if units > 0:
                sl_pip_amount = self._atr_values['H1' if strategy == '1' else 'M5'] \
                                * self.trade_multipliers[strategy][signal]['sl']
                self._place_pending_order(
                    price_to_offset_from=price_to_offset_from,
                    entry_offset=self._atr_values[self.entry_timeframe] / 5,
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
            if now.minute % 5 == 0 and now.minute != prev_exec:
                time.sleep(8)
                self._update_latest_data()
                if self._latest_data:
                    self._update_current_indicators_and_signals()
                    last_m5_close = float(self._latest_data['M5']['midClose'].values[-1])
                    signals = self._get_signals(price=last_m5_close)
                    self._log_latest_values(now, signals)

                    # Remove outdated pending orders depending on entry signals.
                    self._check_and_clear_pending_orders()

                    # New orders.
                    for strategy, signal in signals.items():
                        if signal and self._has_new_signal(strategy) and not is_first_run:
                            self._place_new_pending_order_if_units_available(last_m5_close, strategy, signal)
                prev_exec = now.minute
                self._update_previous_ssl_values()
                is_first_run = False

            # Monitor and adjust current trades, if any.
            time.sleep(1)
            self._live_trade_monitor.monitor_and_adjust_current_trades()

            # Remove outdated entries in local lists.
            if now.hour % 24 == 0:
                self._live_trade_monitor.clean_lists()
