# Python standard.
import abc
import sys
from typing import Dict, List, Union

# Local.
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.indicators import append_ssl_channel
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.live_trade_monitor import LiveTradeMonitor
from pagetpalace.src.oanda.strategy import Strategy
from pagetpalace.tools.logger import *


class SSLMultiTimeFrame(Strategy):

    def __init__(
            self,
            equity_split: float,
            account: OandaAccount,
            instrument: Instrument,
            time_frames: List[str],
            entry_timeframe: str,
            sub_strategies_count: int,
            boundary_multipliers: dict,
            live_trade_monitor: Union[LiveTradeMonitor, None],
            trade_multipliers: dict = None,
            ssl_periods: Dict[str, int] = None,
    ):
        """
            boundary_multipliers = {
                'continuation': {
                    'D': {'long': {'above': 100, 'below': 100}, 'short': {'above': 100, 'below': 100}},
                    'M5': {'long': {'above': 100, 'below': 100}, 'short': {'above': 100, 'below': 100}},
                },
                'reverse': {
                    'H1': {'long': {'above': 0}, 'short': {'below': 0}},
                }
            }
            trade_multipliers = {
                '1': {'long': {'sl': 2, 'tp': 2}, 'short': {sl': 2, 'tp': 2}},
                '2': {'long': {'sl': 2, 'tp': 2}, 'short': {'sl': 2, 'tp': 2}},
                '3': {'long': {'sl': 2, 'tp': 2}, 'short': {'sl': 2, 'tp': 2}},
                '4': {'long': {'sl': 2, 'tp': 2}, 'short': {'sl': 2, 'tp': 2}},
            }
        """
        super().__init__(
            equity_split,
            account,
            instrument,
            time_frames,
            entry_timeframe,
            sub_strategies_count,
            live_trade_monitor,
        )
        self.ssl_periods = {tf: 20 for tf in time_frames} if not ssl_periods else ssl_periods
        self.trade_multipliers = trade_multipliers
        self.boundary_multipliers = boundary_multipliers
        init_empty = {tf: 0 for tf in self.time_frames}
        self._current_ssl_values = init_empty
        self._previous_ssl_values = init_empty
        self._atr_values = {}
        self._ssma_values = {}
        self._entry_signals = {}

    def _check_and_clear_pending_orders(self):
        if self._has_new_entry_signal():
            try:
                self._clear_pending_orders()
            except Exception as exc:
                logger.error(f'Failed to clear pending orders. {exc}', exc_info=True)

    def _calculate_atr_factor(self, price: float, timeframe: str) -> float:
        return abs((price - self._ssma_values[timeframe]) / self._atr_values[timeframe])

    def _calculate_boundary(self, type_: str, bias: str, price: float, timeframe: str) -> float:
        try:
            if price >= self._ssma_values[timeframe]:
                boundary = self.boundary_multipliers[type_][timeframe][bias]['above'] * self._atr_values[timeframe]
            else:
                boundary = self.boundary_multipliers[type_][timeframe][bias]['below'] * self._atr_values[timeframe]
        except KeyError:  # Not interested in these situations, don't trade.
            boundary = sys.maxsize

        return boundary

    def _is_within_valid_boundary(self, bias: str, price: float, timeframe: str) -> bool:
        return not (self._calculate_atr_factor(price, timeframe) * self._atr_values[timeframe]
                    > self._calculate_boundary('continuation', bias, price, timeframe))

    def _has_met_reverse_trade_condition(self, bias: str, price: float, timeframe: str) -> bool:
        return self._calculate_atr_factor(price, timeframe) * self._atr_values[timeframe] \
               >= self._calculate_boundary('reverse', bias, price, timeframe)

    @abc.abstractmethod
    def _update_atr_values(self):
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def _update_ssma_values(self):
        raise NotImplementedError('Not implemented in subclass.')

    def _update_current_ssl_values(self):
        for tf, df in self._latest_data.items():
            append_ssl_channel(df, periods=self.ssl_periods[tf])
        self._current_ssl_values = {
            tf: self._latest_data[tf].iloc[-1][f'HighLowValue_{self.ssl_periods[tf]}_period'] for tf in self.time_frames
        }

    def _update_previous_ssl_values(self):
        self._previous_ssl_values = {tf: self._current_ssl_values[tf] for tf in self.time_frames}

    def _update_entry_signals(self):
        self._entry_signals = {
            'previous': self._previous_ssl_values[self.entry_timeframe],
            'current': self._current_ssl_values[self.entry_timeframe],
        }

    def _has_new_entry_signal(self) -> bool:
        return self._entry_signals['previous'] != self._entry_signals['current']

    def _update_current_indicators_and_signals(self):
        self._update_atr_values()
        self._update_ssma_values()
        self._update_current_ssl_values()
        self._update_entry_signals()

    def _log_latest_values(self, now, signals):
        logger.info(f'ssl values: {self._current_ssl_values}')
        logger.info(f'ssma values: {self._ssma_values}')
        logger.info(f'atr values: {self._atr_values}')
        logger.info(f'{now} signals: {signals}')
