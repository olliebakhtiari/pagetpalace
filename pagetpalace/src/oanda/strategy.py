# Python standard.
import abc
import concurrent.futures
import math
from typing import Dict, List, Union

# Local.
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda.orders import Orders
from pagetpalace.src.oanda.account import OandaAccount
from pagetpalace.src.oanda.instrument import OandaInstrumentData
from pagetpalace.src.oanda.pricing import OandaPricingData
from pagetpalace.src.oanda.live_trade_monitor import LiveTradeMonitor
from pagetpalace.src.oanda.settings import LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER
from pagetpalace.src.oanda.unit_conversions import UnitConversions
from pagetpalace.src.risk_manager import RiskManager
from pagetpalace.tools.email_sender import EmailSender
from pagetpalace.tools.logger import *


class Strategy:
    def __init__(
            self,
            equity_split: float,
            account: OandaAccount,
            instrument: Instrument,
            time_frames: List[str],
            entry_timeframe: str,
            sub_strategies_count: int,
            live_trade_monitor: Union[LiveTradeMonitor, None],
    ):
        self.equity_split = equity_split
        self.account = account
        self.instrument = instrument
        self.time_frames = time_frames
        self.entry_timeframe = entry_timeframe
        self.sub_strategies_count = sub_strategies_count
        self.live_trade_monitor = live_trade_monitor
        self._live_trade_monitor = live_trade_monitor
        self._risk_manager = RiskManager(self.instrument)
        self._pricing = OandaPricingData(LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER, 'LIVE_API')
        self._pending_orders = {str(i + 1): [] for i in range(sub_strategies_count)}
        self._latest_price = 0
        self._latest_data = {}

    def _send_mail_alert(self, error_source: str, exc_msg: str = ''):
        error_source_to_msgs = {
            'place_order': 'Failed to place new order',
            'get_data': 'Failed to retrieve latest data',
            'clear_pending': 'Failed to clear pending orders',
        }
        msg = f'{error_source_to_msgs[error_source]} for {self.instrument}.'
        try:
            EmailSender().send_mail(subject=msg.upper(), body=f'{msg}, {exc_msg}. Check if manual action required.')
        except Exception as exc:
            logger.error(f'Failed to send email alert. {exc}', exc_info=True)

    def _add_id_to_pending_orders(self, order: dict, strategy: str):
        self._pending_orders[strategy].append(order['orderCreateTransaction']['id'])

    def _sync_pending_orders(self, pending_orders_in_account: List[dict]):
        ids_in_account = [p_o['id'] for p_o in pending_orders_in_account]
        for local_pending in self._pending_orders.values():
            for id_ in local_pending:
                if id_ not in ids_in_account:
                    local_pending.remove(id_)

    def _clear_pending_orders(self):
        try:
            for orders in list(self._pending_orders.values()):
                for id_ in orders:
                    self.account.cancel_order(id_)
            for key in list(self._pending_orders.keys()):
                self._pending_orders[key].clear()
        except Exception as exc:
            logger.error(f'Failed to clear pending orders. {exc}', exc_info=True)
            self._send_mail_alert(error_source='clear_pending')

    def _get_unit_size_of_trade(self, entry_price: float) -> float:
        return UnitConversions(self.instrument, entry_price) \
            .calculate_unit_size_of_trade(self.account.get_full_account_details()['account'], self.equity_split)

    def _construct_stop_order(self,
                              signal: str,
                              last_close_price: float,
                              entry_offset: float,
                              worst_price_bound_offset: float,
                              tp_pip_amount: float,
                              sl_pip_amount: float,
                              units: float) -> str:
        precision = self.instrument.price_precision
        units = self._risk_manager.calculate_unit_size_within_max_risk(
            float(self.account.get_full_account_details()['account']['balance']),
            units,
            last_close_price,
            sl_pip_amount
        )
        if signal == 'long':
            entry = round(last_close_price + entry_offset, precision)
            tp = round(entry + tp_pip_amount, precision)
            sl = round(entry - sl_pip_amount, precision)
            price_bound = round(entry + worst_price_bound_offset, precision)
        elif signal == 'short':
            entry = round(last_close_price - entry_offset, precision)
            tp = round(entry - tp_pip_amount, precision)
            sl = round(entry + sl_pip_amount, precision)
            price_bound = round(entry - worst_price_bound_offset, precision)
            units = units * -1
        else:
            raise ValueError('Invalid signal received.')

        return Orders.create_stop_order(entry, price_bound, sl, tp, self.instrument.symbol, math.floor(units))

    def _construct_market_order(self):
        # TODO.
        pass

    def _place_pending_order(
            self,
            price_to_offset_from: float,
            entry_offset: float,
            worst_price_bound_offset: float,
            sl_pip_amount: float,
            tp_pip_amount: float,
            strategy: str,
            signal: str,
            units: float,
    ):
        order_schema = self._construct_stop_order(
            signal=signal,
            last_close_price=price_to_offset_from,
            entry_offset=entry_offset,
            worst_price_bound_offset=worst_price_bound_offset,
            tp_pip_amount=tp_pip_amount,
            sl_pip_amount=sl_pip_amount,
            units=units,
        )
        pending_order = self.account.create_order(order_schema)
        self._add_id_to_pending_orders(pending_order, strategy)
        logger.info(f'pending order placed: {pending_order}')
        logger.info(f'pending_orders: {self._pending_orders}')

    def _place_market_order(self):
        # TODO.
        order_schema = self._construct_market_order()
        market_order = self.account.create_order(order_schema)
        logger.info(f'market order placed: {market_order}')

    def _update_latest_data(self):
        od = OandaInstrumentData()
        data = {}
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_tf = {}
            for granularity in self.time_frames:
                future_to_tf[
                    executor.submit(od.get_complete_candlesticks, self.instrument.symbol, 'ABM', granularity, 1000)
                ] = granularity
            for future in concurrent.futures.as_completed(future_to_tf):
                time_frame = future_to_tf[future]
                try:
                    data[time_frame] = od.convert_to_df(future.result(), 'ABM')
                except ConnectionError as exc:
                    msg = f'Failed to retrieve Oanda candlestick data for time frame: {time_frame}. {exc}'
                    logger.error(msg, exc_info=True)
                    self._send_mail_alert(error_source='get_data', exc_msg=msg)
                    self._latest_data = {}
                    return
        self._latest_data = data

    @abc.abstractmethod
    def _get_signals(self, **kwargs) -> Dict[str, str]:
        raise NotImplementedError('Not implemented in subclass.')

    @abc.abstractmethod
    def execute(self):
        """ Run the complete strategy. """
        raise NotImplementedError('Not implemented in subclass.')
