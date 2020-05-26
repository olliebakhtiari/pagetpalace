# Python standard.
import datetime
from typing import Union


class Order:
    IMPLEMENTED_INSTRUMENT_TYPES = ['currency', 'spx500usd', 'nas100usd']

    def __init__(
            self,
            instrument_point_type: str,
            opened_at: datetime.datetime,
            spread: float,
            entry: float,
            take_profit: float = None,
            stop_loss: float = None,
            margin_size: float = None,
            closed_at: datetime.datetime = None,
            win_or_loss: str = None,
            label: str = None,
    ):
        self.instrument_point_type = instrument_point_type
        self.opened_at = opened_at
        self.spread = spread
        self.entry = entry
        self.take_profit = take_profit
        self.stop_loss = stop_loss
        self.margin_size = margin_size
        self.closed_at = closed_at
        self.win_or_loss = win_or_loss
        self.label = label

    def __str__(self):
        return self.label

    @property
    def instrument_point_type(self):
        return self._instrument_point_type

    @instrument_point_type.setter
    def instrument_point_type(self, value):
        if value not in self.IMPLEMENTED_INSTRUMENT_TYPES:
            raise ValueError('point type not implemented.')
        self._instrument_point_type = value

    @property
    def spread(self):
        return self._spread

    @spread.setter
    def spread(self, value):
        if value <= 0:
            raise ValueError('spread must be greater than 0.')
        self._spread = value

    @property
    def entry(self) -> float:
        return self._entry

    @entry.setter
    def entry(self, value):
        if value < 0:
            raise ValueError('entry price cannot be negative.')
        self._entry = value

    @property
    def margin_size(self) -> float:
        return self._margin_size

    @margin_size.setter
    def margin_size(self, value):
        if value <= 0:
            raise ValueError('margin size must be greater than 0.')
        self._margin_size = value

    @property
    def opened_at(self) -> datetime.datetime:
        return self._opened_at

    @opened_at.setter
    def opened_at(self, value):
        self._opened_at = value

    @property
    def closed_at(self) -> datetime.datetime:
        return self._closed_at

    @closed_at.setter
    def closed_at(self, value):
        self._closed_at = value

    @property
    def win_or_loss(self) -> str:
        return self._win_or_loss

    @win_or_loss.setter
    def win_or_loss(self, value):
        if value and value not in ['win', 'loss']:
            raise ValueError('needs to be recorded as "win" or "loss".')
        self._win_or_loss = value

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        if not isinstance(value, str):
            raise ValueError('label must be a string.')
        self._label = value

    def get_status(self, price) -> Union[str, None]:
        status = ''
        if self._check_take_profit_hit(price):
            status = 'profit'
        elif self._check_stop_loss_hit(price):
            status = 'loss'

        return status

    # implement following methods in subclasses.
    def _check_take_profit_hit(self, price: float) -> bool:
        pass

    def _check_stop_loss_hit(self, price: float) -> bool:
        pass


class LongOrder(Order):
    def __init__(
            self,
            instrument_point_type: str,
            opened_at: datetime.datetime,
            spread: float,
            entry: float,
            take_profit: float,
            stop_loss: float,
            margin_size: float,
            closed_at: datetime.datetime,
            win_or_loss: str = None,
            label: str = None,
    ):
        super().__init__(
            instrument_point_type,
            opened_at,
            spread,
            entry,
            take_profit,
            stop_loss,
            margin_size,
            closed_at,
            win_or_loss,
            label,
        )

    def __repr__(self):
        return f'LONG_TRADE => win/loss - {self.win_or_loss}, label = {self.label}, spread = {self.spread} ' \
               f' opened at - {self.opened_at}\n' \
               f'entry = {self.entry}, take_profit = {self.take_profit}, stop_loss = {self.stop_loss}\n' \
               f'closed at - {self.closed_at}'

    @property
    def take_profit(self) -> float:
        return self._take_profit

    @take_profit.setter
    def take_profit(self, value):
        if value and value <= self.entry:
            raise ValueError('take profit cannot be lower than or equal to entry for long trade.')
        self._take_profit = value

    @property
    def stop_loss(self) -> float:
        return self._stop_loss

    @stop_loss.setter
    def stop_loss(self, value):
        if value and value >= self.entry:
            raise ValueError('stop loss cannot be higher than or equal to entry for long trade.')
        self._stop_loss = value

    def _check_take_profit_hit(self, price: float) -> bool:
        return price >= self.take_profit

    def _check_stop_loss_hit(self, price: float) -> bool:
        return price <= self.stop_loss

    def calculate_profit(self):
        return round(self.take_profit - self.entry, 5)

    def calculate_loss(self):
        return round(self.entry - self.stop_loss, 5)


class ShortOrder(Order):
    def __init__(
            self,
            instrument_point_type: str,
            opened_at: datetime.datetime,
            spread: float,
            entry: float,
            take_profit: float,
            stop_loss: float,
            margin_size: float,
            closed_at: datetime.datetime,
            win_or_loss: str = None,
            label: str = None,

    ):
        super().__init__(
            instrument_point_type,
            opened_at,
            spread,
            entry,
            take_profit,
            stop_loss,
            margin_size,
            closed_at,
            win_or_loss,
            label,
        )

    def __repr__(self):
        return f'SHORT_TRADE => win/loss - {self.win_or_loss}, label = {self.label}, spread = {self.spread} ' \
               f'opened at - {self.opened_at}\n' \
               f'entry = {self.entry}, take_profit = {self.take_profit}, stop_loss = {self.stop_loss}\n' \
               f'closed at - {self.closed_at}'

    @property
    def take_profit(self) -> float:
        return self._take_profit

    @take_profit.setter
    def take_profit(self, value):
        if value and value >= self.entry:
            raise ValueError('take profit cannot be higher than or equal to entry for short trade.')
        self._take_profit = value

    @property
    def stop_loss(self) -> float:
        return self._stop_loss

    @stop_loss.setter
    def stop_loss(self, value):
        if value and value <= self.entry:
            raise ValueError('stop loss cannot be lower than or equal to entry for short trade.')
        self._stop_loss = value

    def _check_take_profit_hit(self, price: float) -> float:
        return price <= self.take_profit

    def _check_stop_loss_hit(self, price: float) -> float:
        return price >= self.stop_loss

    def calculate_profit(self) -> float:
        return round(self.entry - self.take_profit, 5)

    def calculate_loss(self) -> float:
        return round(self.stop_loss - self.entry, 5)


class LongDynamicSL(LongOrder):
    def __init__(
            self,
            instrument_point_type: str,
            opened_at: datetime.datetime,
            spread: float,
            entry: float,
            take_profit: float,
            stop_loss: float,
            margin_size: float,
            closed_at: datetime.datetime,
            win_or_loss: str = None,
            label: str = None,
    ):
        super().__init__(
            instrument_point_type,
            opened_at,
            spread,
            entry,
            take_profit,
            stop_loss,
            margin_size,
            closed_at,
            win_or_loss,
            label,
        )

    def __repr__(self):
        return f'LONG_DYNAMIC_SL => win/loss - {self.win_or_loss}, label = {self.label}, spread = {self.spread} ' \
               f'opened at - {self.opened_at}\n'\
               f'entry = {self.entry}, take_profit = {self.take_profit}, stop_loss = {self.stop_loss}\n' \
               f'closed at - {self.closed_at}'

    @property
    def take_profit(self) -> float:
        return self._take_profit

    @take_profit.setter
    def take_profit(self, value):
        if value and value <= self.entry:
            raise ValueError('take profit cannot be lower than or equal to entry for long trade.')
        self._take_profit = value

    @property
    def stop_loss(self) -> float:
        return self._stop_loss

    @stop_loss.setter
    def stop_loss(self, value):
        self._stop_loss = value

    def calculate_take_profit_hit(self, price: float) -> Union[float, None]:
        if self._check_take_profit_hit(price):
            return self.calculate_profit()

    def calculate_stop_loss_hit(self, price: float) -> Union[float, None]:
        if self._check_stop_loss_hit(price):
            return round(self._stop_loss - self._entry, 5)


class ShortDynamicSL(ShortOrder):
    def __init__(
            self,
            instrument_point_type: str,
            opened_at: datetime.datetime,
            spread: float,
            entry: float,
            take_profit: float,
            stop_loss: float,
            margin_size: float,
            closed_at: datetime.datetime,
            win_or_loss: str = None,
            label: str = None,

    ):
        super().__init__(
            instrument_point_type,
            opened_at,
            spread,
            entry,
            take_profit,
            stop_loss,
            margin_size,
            closed_at,
            win_or_loss,
            label,
        )

    def __repr__(self):
        return f'SHORT_DYNAMIC_SL => win/loss - {self.win_or_loss}, label = {self.label}, spread = {self.spread} ' \
               f'opened at - {self.opened_at}\n' \
               f'entry = {self.entry}, take_profit = {self.take_profit}, stop_loss = {self.stop_loss}\n' \
               f'closed at - {self.closed_at}'

    @property
    def take_profit(self) -> float:
        return self._take_profit

    @take_profit.setter
    def take_profit(self, value):
        if value and value >= self.entry:
            raise ValueError('take profit cannot be higher than or equal to entry for short trade.')
        self._take_profit = value

    @property
    def stop_loss(self) -> float:
        return self._stop_loss

    @stop_loss.setter
    def stop_loss(self, value):
        self._stop_loss = value

    def calculate_take_profit_hit(self, price: float) -> Union[float, None]:
        if self._check_take_profit_hit(price):
            return self.calculate_profit()

    def calculate_stop_loss_hit(self, price: float) -> Union[float, None]:
        if self._check_stop_loss_hit(price):
            return round(self._entry - self._stop_loss, 5)


class OrderFactory:
    @classmethod
    def create_order(cls,
                     instrument_point_type: str,
                     opened_at: datetime.datetime,
                     order_type: str,
                     spread: float,
                     entry: float,
                     margin_size: float,
                     take_profit: float = None,
                     stop_loss: float = None,
                     closed_at: datetime.datetime = None,
                     label: str = None) -> Union[LongOrder, ShortOrder, LongDynamicSL, ShortDynamicSL]:
        if order_type == 'long':
            return LongOrder(
                instrument_point_type=instrument_point_type,
                opened_at=opened_at,
                spread=spread,
                entry=entry,
                margin_size=margin_size,
                take_profit=take_profit,
                stop_loss=stop_loss,
                closed_at=closed_at,
                label=label,
            )
        elif order_type == 'short':
            return ShortOrder(
                instrument_point_type=instrument_point_type,
                opened_at=opened_at,
                spread=spread,
                entry=entry,
                margin_size=margin_size,
                take_profit=take_profit,
                stop_loss=stop_loss,
                closed_at=closed_at,
                label=label,
            )
        elif order_type == 'long_dynamic_sl':
            return LongDynamicSL(
                instrument_point_type=instrument_point_type,
                opened_at=opened_at,
                spread=spread,
                entry=entry,
                margin_size=margin_size,
                take_profit=take_profit,
                stop_loss=stop_loss,
                closed_at=closed_at,
                label=label,
            )
        elif order_type == 'short_dynamic_sl':
            return ShortDynamicSL(
                instrument_point_type=instrument_point_type,
                opened_at=opened_at,
                spread=spread,
                entry=entry,
                margin_size=margin_size,
                take_profit=take_profit,
                stop_loss=stop_loss,
                closed_at=closed_at,
                label=label,
            )
        else:
            raise ValueError(f'order type: {order_type} is not valid.')
