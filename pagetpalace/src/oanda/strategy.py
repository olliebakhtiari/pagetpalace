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
            max_risk_pct: float = 0.15,
            num_trades_cap: int = 2,
    ):
        self.equity_split = equity_split
        self.account = account
        self.instrument = instrument
        self.time_frames = time_frames
        self.entry_timeframe = entry_timeframe
        self.sub_strategies_count = sub_strategies_count
        self._risk_manager = RiskManager(self.instrument, max_risk_pct)
        self._pricing = OandaPricingData(LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER, 'LIVE_API')
        self._num_trades_cap = num_trades_cap
        self._pending_orders = {str(i + 1): [] for i in range(sub_strategies_count)}
        self._latest_price = 0
        self._latest_data = {}

    def _send_mail_alert(self, source: str, additional_msg: str = ''):
        source_to_msgs = {
            'place_order': 'Failed to place new order',
            'get_data': 'Failed to retrieve latest data',
            'clear_pending': 'Failed to clear pending orders',
            'no_margin_available': 'Not enough margin available to place an order',
            'successful_order': 'Order placed successfully',
            'ins_trade_cap': 'Max trade cap for single instrument reached, order not placed',
        }
        msg = f'{source_to_msgs[source]} for {self.instrument}'
        try:
            EmailSender().send_mail(subject=msg.upper(), body=f'{msg}. {additional_msg}')
        except Exception as exc:
            logger.error(f'Failed to send email alert. {exc}', exc_info=True)

    def _is_instrument_below_num_of_trades_cap(self) -> bool:
        count = 0
        for open_trade in self.account.get_open_trades()['trades']:
            if open_trade.get('instrument') == self.instrument.symbol:
                count += 1

        return count < self._num_trades_cap

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
            self._send_mail_alert(source='clear_pending', additional_msg=str(exc))

    def _get_unit_size_of_trade(self, entry_price: float) -> int:
        return UnitConversions(self.instrument, entry_price) \
            .calculate_unit_size_of_trade(self.account.get_full_account_details()['account'], self.equity_split)

    @classmethod
    def _validate_and_round_unit_size(cls, signal: str, units: float):
        units = math.floor(units) if signal == 'long' else math.ceil(units)
        if units == 0:
            if signal == 'long':
                units = 1
            else:
                units = -1

        return units

    def _construct_stop_order(self,
                              signal: str,
                              last_close_price: float,
                              entry_offset: float,
                              worst_price_bound_offset: float,
                              tp_pip_amount: float,
                              sl_pip_amount: float,
                              units: int) -> str:
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
            price_bound = round(entry + worst_price_bound_offset, precision) if worst_price_bound_offset else None
        elif signal == 'short':
            entry = round(last_close_price - entry_offset, precision)
            tp = round(entry - tp_pip_amount, precision)
            sl = round(entry + sl_pip_amount, precision)
            price_bound = round(entry - worst_price_bound_offset, precision) if worst_price_bound_offset else None
            units = units * -1
        else:
            raise ValueError('Invalid signal received.')

        return Orders.create_stop_order(
            entry=entry,
            price_bound=price_bound,
            stop_loss_price=sl,
            take_profit_price=tp,
            instrument=self.instrument.symbol,
            units=self._validate_and_round_unit_size(signal, units),
        )

    def _construct_market_order(self,
                                signal: str,
                                units: int,
                                last_close_price: float,
                                sl_pip_amount: float,
                                tp_pip_amount: float) -> str:
        precision = self.instrument.price_precision
        units = self._risk_manager.calculate_unit_size_within_max_risk(
            float(self.account.get_full_account_details()['account']['balance']),
            units,
            last_close_price,
            sl_pip_amount
        )
        if signal == 'long':
            tp = round(last_close_price + tp_pip_amount, precision)
            sl = round(last_close_price - sl_pip_amount, precision)
        elif signal == 'short':
            tp = round(last_close_price - tp_pip_amount, precision)
            sl = round(last_close_price + sl_pip_amount, precision)
            units = units * -1
        else:
            raise ValueError('Invalid signal received.')

        return Orders.create_market_order(sl, tp, self.instrument.symbol, math.floor(units))

    def _place_pending_order(
            self,
            price_to_offset_from: float,
            entry_offset: float,
            worst_price_bound_offset: Union[float, None],
            sl_pip_amount: float,
            tp_pip_amount: float,
            strategy: str,
            signal: str,
            units: int,
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
        msg = f'GTC pending order placed: {pending_order}'
        logger.info(msg)
        logger.info(f'pending_orders: {self._pending_orders}')
        self._send_mail_alert(source='successful_order', additional_msg=msg)

    def _place_market_order(self,
                            last_close_price: float,
                            sl_pip_amount: float,
                            tp_pip_amount: float,
                            signal: str,
                            units: int) -> dict:
        """
        {
            'orderCreateTransaction': {
                'id': '20',
                'accountID': '001-004-3448019-009',
                'userID': 3448019,
                'batchID': '20',
                'requestID': '132871614305289672',
                'time': '2021-02-25T22:00:13.336751636Z',
                'type': 'MARKET_ORDER',
                'instrument': 'XAU_XAG',
                'units': '3',
                'timeInForce': 'IOC',
                'positionFill': 'DEFAULT',
                'takeProfitOnFill': {'price': '67.174', 'timeInForce': 'GTC'},
                'stopLossOnFill': {'price': '61.318', 'timeInForce': 'GTC'},
                'reason': 'CLIENT_ORDER'
            },
            'orderCancelTransaction': {
                    'id': '21',
                    'accountID': '001-004-3448019-009',
                    'userID': 3448019,
                    'batchID': '20',
                    'requestID': '132871614305289672',
                    'time': '2021-02-25T22:00:13.336751636Z',
                    'type': 'ORDER_CANCEL',
                    'orderID': '20',
                    'reason': 'MARKET_HALTED'
            },
            'relatedTransactionIDs': ['20', '21'],
            'lastTransactionID': '21'
            }
        """
        order_schema = self._construct_market_order(
            signal=signal,
            last_close_price=last_close_price,
            tp_pip_amount=tp_pip_amount,
            sl_pip_amount=sl_pip_amount,
            units=units,
        )
        market_order = self.account.create_order(order_schema)
        msg = f'IOC market order placed: {market_order}'
        logger.info(msg)
        self._send_mail_alert(source='successful_order', additional_msg=msg)

        return market_order

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
                    self._send_mail_alert(source='get_data', additional_msg=msg)
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
