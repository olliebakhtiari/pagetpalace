# Python standard.
from typing import Dict, List


class TradeAdjustmentParameters:
    def __init__(self, instrument_symbol: str, params: Dict[int, Dict[str, float]]):
        self.instrument_symbol = instrument_symbol
        self.params = params

    def __str__(self):
        return f'instrument_symbol - {self.instrument_symbol}, params - {self.params}'

    @property
    def instrument_symbol(self):
        return self._instrument_symbol

    @instrument_symbol.setter
    def instrument_symbol(self, value: str):
        if len(value.split('_')) < 2:
            raise ValueError('Invalid symbol specified.')
        self._instrument_symbol = value

    @classmethod
    def _check_valid_input(cls, all_params: List['TradeAdjustmentParameters']):
        if all_params:
            if not isinstance(all_params, list):
                raise TypeError('Parameters must be a list of TradeAdjustmentParameters.')
            if all_params and any(not isinstance(p, (StopLossMoveParams, PartialClosureParams)) for p in all_params):
                raise TypeError('All members of list must be TradeAdjustmentParameter object.')

    @staticmethod
    def init_pair_to_params(all_params: List['TradeAdjustmentParameters']) -> dict:
        TradeAdjustmentParameters._check_valid_input(all_params)

        return {p.instrument_symbol: p.params for p in all_params} if all_params else {}

    @staticmethod
    def init_local_history(all_params: List['TradeAdjustmentParameters']) -> dict:
        TradeAdjustmentParameters._check_valid_input(all_params)
        init = {}
        if all_params:
            for params_obj in all_params:
                init[params_obj.instrument_symbol] = {i + 1: [] for i in range(len(params_obj.params.keys()))}

        return init


class StopLossMoveParams(TradeAdjustmentParameters):
    def __init__(self, instrument_symbol: str, params: Dict[int, Dict[str, float]]):
        """ {1: {'check': 0.35, 'move': 0.01}} """
        super().__init__(instrument_symbol, params)

    @property
    def params(self):
        return self._params

    @params.setter
    def params(self, value: Dict[int, Dict[str, float]]):
        if not all(isinstance(k, int) for k in value.keys()):
            raise ValueError('Keys in params not valid.')
        if any(not (d.get('check') and d.get('move')) for d in value.values()):
            raise ValueError('"check" or "move" keys missing in params.')
        self._params = value


class PartialClosureParams(TradeAdjustmentParameters):
    def __init__(self, instrument_symbol: str, params: Dict[int, Dict[str, float]]):
        """ {1: {'check': 0.35, 'close': 0.5}} """
        super().__init__(instrument_symbol, params)

    @property
    def params(self):
        return self._params

    @params.setter
    def params(self, value: Dict[int, Dict[str, float]]):
        if not all(isinstance(k, int) for k in value.keys()):
            raise ValueError('Keys in params not valid.')
        if any(not (d.get('check') and d.get('close')) for d in value.values()):
            raise ValueError('"check" or "close" keys missing in params.')
        self._params = value
