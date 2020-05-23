# Python standard.
import datetime
import sys
from typing import List, Union

# Local.
from .orders import OrderFactory, LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL


class BackTestingAccount:
    TRADEABLE_MARGIN_CAP = 0.9
    MARGIN_TO_PIP_RATIOS = {
        'currency': 426,
        'index': 143,
    }

    def __init__(self, starting_capital: float, equity_split: float):
        self.starting_capital = starting_capital
        self.equity_split = equity_split
        self._total_margin = starting_capital
        self._available_margin = self._total_margin
        self._win_count = 0
        self._loss_count = 0
        self._pips_accumulated = float(0)
        self._pending_orders = []
        self._active_trades = []
        self._closed_trades = []
        self._highest_balance = 0
        self._lowest_balance = sys.maxsize
        self._partially_closed_1 = []
        self._partially_closed_2 = []
        self._losses_cut = []

    def __str__(self):
        return f'trades executed = {self._round_and_format(self.get_all_trades_count())}\n' \
               f'win rate = {self._round_and_format(self.get_win_rate())}%\n' \
               f'pips accumulated = {self._round_and_format(self._pips_accumulated)}\n' \
               f'final balance = £{self._round_and_format(self._total_margin)}\n' \
               f'highest balance = £{self._round_and_format(self._highest_balance)}\n' \
               f'lowest balance = £{self._round_and_format(self._lowest_balance)}'

    @staticmethod
    def _round_and_format(number: float):
        return f'{round(number, 2):,.2f}'

    @property
    def starting_capital(self) -> float:
        return self._starting_capital

    @starting_capital.setter
    def starting_capital(self, value):
        if value <= 0:
            raise ValueError('starting capital must be greater than 0.')
        self._starting_capital = value

    @property
    def equity_split(self) -> float:
        return self._equity_split

    @equity_split.setter
    def equity_split(self, value):
        if value < 1:
            raise ValueError('split must be at least 1.')
        self._equity_split = value

    def get_current_total_balance(self) -> float:
        return self._total_margin

    def _update_highest_and_lowest_balance(self):
        if self._total_margin > self._highest_balance:
            self._highest_balance = self._total_margin
        if self._total_margin < self._lowest_balance:
            self._lowest_balance = self._total_margin

    def get_tradeable_margin(self) -> float:
        return self._total_margin * self.TRADEABLE_MARGIN_CAP

    def get_available_margin(self) -> float:
        return self._available_margin

    def _check_and_get_valid_margin_size(self, margin_size: float) -> float:

        # Make sure not to trade if available margin is less than or equal to 10% of total margin.
        available_minus_restricted = self._available_margin - (self._total_margin * 0.1)
        if (margin_size > available_minus_restricted) and (available_minus_restricted < 500):
            margin_size = 0
        elif (margin_size > available_minus_restricted) and (available_minus_restricted >= 500):
            margin_size = available_minus_restricted

        return margin_size

    def _check_against_max_risk(self, margin_size: float, pips: float, point_type: str) -> float:

        # Calculate money being risked on this trade.
        pound_per_pip_ratio = margin_size / self.MARGIN_TO_PIP_RATIOS[point_type]
        margin_at_risk = self.calculate_pips_to_pounds(margin_size, pips, point_type)
        max_risk = self.get_current_total_balance() * 0.15

        # Set risk to 15% if it exceeds.
        if margin_at_risk > max_risk:
            risk_ratio = margin_at_risk / max_risk
            new_pound_per_pip_ratio = pound_per_pip_ratio / risk_ratio
            margin_size = new_pound_per_pip_ratio * self.MARGIN_TO_PIP_RATIOS[point_type]

        return margin_size

    def get_margin_size_per_trade(self) -> float:
        margin_size = self.get_tradeable_margin() / self.equity_split

        return self._check_and_get_valid_margin_size(margin_size)

    def deposit_funds(self, amount: float):
        self._total_margin += amount
        self._available_margin += amount

    def get_pending_orders(self) -> List[Union[LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL]]:
        return self._pending_orders

    def count_orders_by_label(self, label: str) -> int:
        count = 0
        for trade in self._active_trades:
            if label in trade.label:
                count += 1
        for trade in self._pending_orders:
            if label in trade.label:
                count += 1

        return count

    def get_all_trades_count(self):
        return len(self._active_trades) + len(self._closed_trades)

    def get_win_rate(self) -> float:
        return (self._win_count / self.get_all_trades_count()) * 100

    def get_individual_strategy_wins_losses(self, strategies_to_check: List[str]) -> dict:
        results = {label: {'wins': 0, 'losses': 0} for label in strategies_to_check}
        for trade in self.get_closed_trades():
            if trade.win_or_loss == 'win':
                results[trade.label]['wins'] += 1
            else:
                results[trade.label]['losses'] += 1

        return results

    def has_active_trades(self) -> bool:
        return len(self._active_trades) > 0

    def number_of_active_trades(self) -> int:
        return len(self._active_trades)

    def has_margin_available(self) -> bool:
        return self._available_margin > 0

    def get_used_margin(self) -> float:
        return self._total_margin - self._available_margin

    def get_closed_trades(self) -> List[Union[LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL]]:
        return self._closed_trades

    def get_partially_closed_trades(self) -> dict:
        return {
            1: self._partially_closed_1,
            2: self._partially_closed_2,
        }

    def _move_used_margin(self, margin_amount: float):
        self._available_margin -= margin_amount

    def _restore_margin(self, margin_from_trade: float, trade_outcome: float):
        self._total_margin += trade_outcome
        self._available_margin += (margin_from_trade + trade_outcome)

    @classmethod
    def calculate_pips_to_pounds(cls, margin: float, pips: float, point_type: str) -> float:
        return (margin / cls.MARGIN_TO_PIP_RATIOS[point_type]) * (pips * (1e4 if point_type == 'currency' else 1))

    @classmethod
    def _check_pct_target_hit(cls,
                              price: float,
                              trade: Union[LongDynamicSL, ShortDynamicSL, LongOrder, ShortOrder],
                              pct_of_target: float) -> bool:
        if pct_of_target <= 0:
            raise ValueError('percentage target cannot be 0 or less.')
        has_hit = False
        full_target_pips = trade.calculate_profit()
        pct_target_pips = full_target_pips * pct_of_target
        if isinstance(trade, LongDynamicSL) and price >= (trade.entry + pct_target_pips):
            has_hit = True
        elif isinstance(trade, ShortDynamicSL) and price <= (trade.entry - pct_target_pips):
            has_hit = True

        return has_hit

    @classmethod
    def _check_pct_stop_loss_hit(cls,
                                 price: float,
                                 trade: Union[LongDynamicSL, ShortDynamicSL, LongOrder, ShortOrder],
                                 pct_of_target: float) -> bool:
        if pct_of_target <= 0:
            raise ValueError('percentage target cannot be 0 or less.')
        has_hit = False
        full_stop_loss_pips = trade.calculate_loss()
        pct_loss_pips = full_stop_loss_pips * pct_of_target
        if isinstance(trade, (LongDynamicSL, LongOrder)) and price <= (trade.entry - pct_loss_pips):
            has_hit = True
        elif isinstance(trade, (ShortDynamicSL, ShortOrder)) and price >= (trade.entry + pct_loss_pips):
            has_hit = True

        return has_hit

    @classmethod
    def _move_stop_loss_to_profit(
            cls,
            current_price: float,
            trade: Union[LongDynamicSL, ShortDynamicSL],
            pct_of_target: float
    ):
        if pct_of_target <= 0:
            raise ValueError('percentage of target must be greater than zero.')
        if isinstance(trade, LongDynamicSL):
            new_price = trade.entry + (trade.calculate_profit() * pct_of_target)
            if new_price >= trade.take_profit or new_price >= current_price:
                raise ValueError('new stop loss equal to or greater than take profit or current price for long.')
            trade.stop_loss = new_price
        elif isinstance(trade, ShortDynamicSL):
            new_price = trade.entry - (trade.calculate_profit() * pct_of_target)
            if new_price <= trade.take_profit or new_price <= current_price:
                raise ValueError('new stop loss equal to or greater than take profit or current price for short.')
            trade.stop_loss = new_price

    def open_trade(
            self,
            instrument_point_type: str,
            opened_at: datetime.datetime,
            order_type: str,
            spread: float,
            entry: float,
            take_profit: float,
            stop_loss: float,
            margin_size: float,
            label: str,
    ):
        order = OrderFactory.create_order(
            instrument_point_type=instrument_point_type,
            opened_at=opened_at,
            spread=spread,
            order_type=order_type,
            margin_size=margin_size,
            entry=entry,
            take_profit=take_profit,
            stop_loss=stop_loss,
            label=label,
        )
        self._move_used_margin(order.margin_size)
        self._pending_orders.append(order)

    def process_pending_orders(
            self,
            long_prices_to_check: List[float],
            short_prices_to_check: List[float],
            valid_labels: List[str],
    ):
        self._delete_pending_orders_by_label(valid_labels)
        for idx, order in enumerate(self._pending_orders):
            if isinstance(order, (LongDynamicSL, LongOrder)) and max(long_prices_to_check) >= order.entry:
                self._transfer_pending_to_active(idx)
            elif isinstance(order, (ShortDynamicSL, ShortOrder)) and min(short_prices_to_check) <= order.entry:
                self._transfer_pending_to_active(idx)

    def _delete_pending_orders_by_label(self, valid_labels: List[str]):
        for idx, order in enumerate(self._pending_orders):
            if order.label not in valid_labels:
                self._restore_margin(margin_from_trade=order.margin_size, trade_outcome=0)
                self._pending_orders.pop(idx)

    def _transfer_pending_to_active(self, index: int):
        active_trade = self._pending_orders.pop(index)
        pending_label = active_trade.label
        active_label = pending_label.split('_')[0]
        active_trade.label = active_label
        self._active_trades.append(active_trade)

    def check_and_adjust_stop_losses(self, check_pct: float, move_pct: float, long_price: float, short_price: float):
        for trade in self._active_trades:
            if isinstance(trade, LongDynamicSL):
                if self._check_pct_target_hit(price=long_price, trade=trade, pct_of_target=check_pct):
                    self._move_stop_loss_to_profit(current_price=long_price, trade=trade, pct_of_target=move_pct)
            elif isinstance(trade, ShortDynamicSL):
                if self._check_pct_target_hit(price=short_price, trade=trade, pct_of_target=check_pct):
                    self._move_stop_loss_to_profit(current_price=short_price, trade=trade, pct_of_target=move_pct)

    def check_and_partially_close_profits(
            self,
            check_pct: float,
            long_price: float,
            short_price: float,
            close_pct: float,
            partial_close_count: int,
    ):
        if partial_close_count not in [1, 2]:
            raise ValueError('can only partially close twice.')
        partially_closed = self.get_partially_closed_trades()
        for trade in self._active_trades:
            if trade not in partially_closed[partial_close_count]:
                if isinstance(trade, (LongDynamicSL, LongOrder)):
                    if self._check_pct_target_hit(price=long_price, trade=trade, pct_of_target=check_pct):
                        self._partially_close_profit(trade, check_pct, close_pct)
                        self._add_trade_to_partially_closed(trade, partial_close_count)
                elif isinstance(trade, (ShortDynamicSL, ShortOrder)):
                    if self._check_pct_target_hit(price=short_price, trade=trade, pct_of_target=check_pct):
                        self._partially_close_profit(trade, check_pct, close_pct)
                        self._add_trade_to_partially_closed(trade, partial_close_count)

    def check_and_cut_losses(self, check_pct: float, long_price: float, short_price: float, close_pct: float):
        for trade in self._active_trades:
            if trade not in self._losses_cut:
                if isinstance(trade, (LongDynamicSL, LongOrder)):
                    if self._check_pct_stop_loss_hit(price=long_price, trade=trade, pct_of_target=check_pct):
                        self._cut_losses(trade, check_pct, close_pct)
                elif isinstance(trade, (ShortDynamicSL, ShortOrder)):
                    if self._check_pct_stop_loss_hit(price=short_price, trade=trade, pct_of_target=check_pct):
                        self._cut_losses(trade, check_pct, close_pct)

    def _partially_close_profit(
            self, trade: Union[LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL],
            check_pct: float,
            close_pct: float,
    ):
        pip_count = trade.calculate_profit() * check_pct
        margin_to_close = trade.margin_size * close_pct
        profit = self.calculate_pips_to_pounds(margin_to_close, pip_count, trade.instrument_point_type)
        self._restore_margin(margin_from_trade=margin_to_close, trade_outcome=profit)
        trade.margin_size -= margin_to_close
        self._pips_accumulated += (pip_count * check_pct)

    def _cut_losses(
            self,
            trade: Union[LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL],
            check_pct: float,
            close_pct: float,
    ):
        pip_count = trade.calculate_loss() * check_pct
        margin_to_close = trade.margin_size * close_pct
        loss = self.calculate_pips_to_pounds(margin_to_close, pip_count, trade.instrument_point_type) * -1
        self._restore_margin(margin_from_trade=margin_to_close, trade_outcome=loss)
        trade.margin_size -= margin_to_close
        self._pips_accumulated -= (pip_count * check_pct)
        self._losses_cut.append(trade)

    def _add_trade_to_partially_closed(
            self,
            trade: Union[LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL],
            partial_close_count: int,
    ):
        getattr(self, f'_partially_closed_{partial_close_count}').append(trade)

    def monitor_and_close_active_trades(
            self,
            current_date_time: datetime.datetime,
            long_price: float,
            short_price: float,
    ):
        for idx, trade in enumerate(self._active_trades):
            if isinstance(trade, LongDynamicSL):
                self._process_dynamic_trade(
                    trade=trade,
                    price=long_price,
                    index=idx,
                    current_date_time=current_date_time,
                )
            elif isinstance(trade, LongOrder):
                self._process_static_trade(
                    trade=trade,
                    price=long_price,
                    index=idx,
                    current_date_time=current_date_time,
                )
            elif isinstance(trade, ShortDynamicSL):
                self._process_dynamic_trade(
                    trade=trade,
                    price=short_price,
                    index=idx,
                    current_date_time=current_date_time,
                )
            elif isinstance(trade, ShortOrder):
                self._process_static_trade(
                    trade=trade,
                    price=short_price,
                    index=idx,
                    current_date_time=current_date_time,
                )

    def _process_static_trade(
            self,
            trade: Union[LongOrder, ShortOrder],
            price: float,
            index: int,
            current_date_time: datetime.datetime,
    ):
        margin = trade.margin_size
        action = trade.get_status(price)
        if action:
            pips = getattr(trade, f'calculate_{action}')()
            win_or_loss = 'win' if action == 'profit' else 'loss'
            pounds = self.calculate_pips_to_pounds(margin, pips, trade.instrument_point_type)
            getattr(self, f'_process_{action}')(pips, margin, pounds)
            self._close_trade(order_index=index, closed_at=current_date_time, win_or_loss=win_or_loss)

    def _process_dynamic_trade(
            self,
            trade: Union[LongDynamicSL, ShortDynamicSL],
            price: float,
            index: int,
            current_date_time: datetime.datetime,
    ):
        margin = trade.margin_size
        point_type = trade.instrument_point_type
        tp_hit = trade.calculate_take_profit_hit(price)
        sl_hit = trade.calculate_stop_loss_hit(price)
        if tp_hit:
            pounds = self.calculate_pips_to_pounds(margin, tp_hit, point_type)
            self._process_profit(pips=tp_hit, margin_from_trade=margin, pounds=pounds)
            self._close_trade(order_index=index, closed_at=current_date_time, win_or_loss='win')
        elif sl_hit:
            pounds = self.calculate_pips_to_pounds(margin, sl_hit, point_type)
            if sl_hit > 0 and isinstance(trade, (ShortDynamicSL, LongDynamicSL)):
                self._process_profit(pips=sl_hit, margin_from_trade=margin, pounds=pounds)
            else:
                self._process_loss(pips=abs(sl_hit), margin_from_trade=margin, pounds=abs(pounds))
            self._close_trade(
                order_index=index,
                closed_at=current_date_time,
                win_or_loss='win' if sl_hit > 0 else 'loss',
            )

    def _process_profit(self, pips: float, margin_from_trade: float, pounds: float):
        self._pips_accumulated += pips
        self._win_count += 1
        self._restore_margin(margin_from_trade=margin_from_trade, trade_outcome=pounds)

    def _process_loss(self, pips: float, margin_from_trade: float, pounds: float):
        self._pips_accumulated -= pips
        self._loss_count += 1
        self._restore_margin(margin_from_trade=margin_from_trade, trade_outcome=-1 * pounds)

    def _calculate_fees(self, trade: Union[LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL]):
        fee = self.calculate_pips_to_pounds(trade.margin_size, trade.spread, trade.instrument_point_type)
        self._total_margin -= fee
        self._available_margin -= fee

    def _close_trade(self, order_index: int, closed_at: datetime.datetime, win_or_loss: str):
        trade_to_close = self._active_trades.pop(order_index)
        self._calculate_fees(trade_to_close)
        trade_to_close.closed_at = closed_at
        trade_to_close.win_or_loss = win_or_loss
        self._closed_trades.append(trade_to_close)
        self._update_highest_and_lowest_balance()
