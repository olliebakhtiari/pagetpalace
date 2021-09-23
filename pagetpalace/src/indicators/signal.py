# Local.
from pagetpalace.src.constants.direction import Direction


class Signal:
    VALID_BIAS = [Direction.LONG, Direction.SHORT]
    VALID_TRADE_TYPES = ['reverse', 'continuation']

    def __init__(self, trade_type: str, bias: str, take_profit_multiplier: float, stop_loss_multiplier: float):
        self.trade_type = trade_type
        self.bias = bias
        self.take_profit_multiplier = take_profit_multiplier
        self.stop_loss_multiplier = stop_loss_multiplier

    def __str__(self):
        return f'trade type - {self.trade_type}, bias - {self.bias}\n' \
               f'take profit multiplier - {self.take_profit_multiplier}\n' \
               f'stop loss multiplier - {self.stop_loss_multiplier}'

    @property
    def trade_type(self) -> str:
        return self._trade_type

    @trade_type.setter
    def trade_type(self, value: str):
        if not isinstance(value, str) or value not in self.VALID_TRADE_TYPES:
            raise ValueError('Invalid trade type.')
        self._trade_type = value

    @property
    def bias(self) -> str:
        return self._bias

    @bias.setter
    def bias(self, value: str):
        if not isinstance(value, str) or value not in self.VALID_BIAS:
            raise ValueError('Invalid bias.')
        self._bias = value

    @property
    def take_profit_multiplier(self) -> float:
        return self._take_profit_multiplier

    @take_profit_multiplier.setter
    def take_profit_multiplier(self, value: float):
        if not isinstance(value, float) or value <= 0:
            raise ValueError('Invalid take profit multiplier.')
        self._take_profit_multiplier = value

    @property
    def stop_loss_multiplier(self) -> float:
        return self._stop_loss_multiplier

    @stop_loss_multiplier.setter
    def stop_loss_multiplier(self, value: float):
        if not isinstance(value, float) or value <= 0:
            raise ValueError('Invalid stop loss multiplier.')
        self._stop_loss_multiplier = value
