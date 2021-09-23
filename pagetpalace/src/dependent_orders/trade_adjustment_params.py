# Python standard.
from typing import Dict, List


class TradeAdjustmentParameters:
    def __init__(self, instrument_symbol: str, params: Dict[int, Dict[str, float]]):
        self.instrument_symbol = instrument_symbol
        self.params = params

    def __str__(self):
        return f'instrument_symbol - {self.instrument_symbol}, params - {self.params}'

    @property
    def instrument_symbol(self) -> str:
        return self._instrument_symbol

    @instrument_symbol.setter
    def instrument_symbol(self, value: str):
        if len(value.split('_')) < 2:
            raise ValueError('Invalid symbol specified.')
        self._instrument_symbol = value

    @classmethod
    def _validate_check_values_ascending(cls, params: Dict[int, Dict[str, float]]):
        check_pcts = [v['check'] for v in params.values()]
        if len(params.values()) > 1 and not all(check_pcts[i-1] < check_pcts[i] for i in range(1, len(check_pcts))):
            raise ValueError('"check" percentages need to be in ascending order.')

    @classmethod
    def _check_valid_input(cls, all_params: List['TradeAdjustmentParameters']):
        if all_params:
            if not isinstance(all_params, list):
                raise TypeError('Parameters must be a list of TradeAdjustmentParameters.')
            if all_params and any(not isinstance(p, (StopLossMoveParams, PartialClosureParams)) for p in all_params):
                raise TypeError('All members of list must be TradeAdjustmentParameter object.')

    @staticmethod
    def init_pair_to_params(all_params: List['TradeAdjustmentParameters']) -> Dict[str, Dict[int, Dict[str, float]]]:
        TradeAdjustmentParameters._check_valid_input(all_params)

        return {p.instrument_symbol: p.params for p in all_params} if all_params else {}

    @staticmethod
    def init_local_history(all_params: List['TradeAdjustmentParameters']) -> Dict[str, Dict[int, list]]:
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
    def params(self) -> Dict[int, Dict[str, float]]:
        return self._params

    @params.setter
    def params(self, value: Dict[int, Dict[str, float]]):
        if not all(isinstance(k, int) for k in value.keys()):
            raise ValueError('Keys in params not valid.')
        if any(not (d.get('check') and d.get('move')) for d in value.values()):
            raise ValueError('"check" or "move" keys missing in params.')
        self._validate_check_values_ascending(value)
        self._params = value


class PartialClosureParams(TradeAdjustmentParameters):
    def __init__(self, instrument_symbol: str, params: Dict[int, Dict[str, float]]):
        """ {1: {'check': 0.35, 'close': 0.5}} """
        super().__init__(instrument_symbol, params)

    @property
    def params(self) -> Dict[int, Dict[str, float]]:
        return self._params

    @params.setter
    def params(self, value: Dict[int, Dict[str, float]]):
        if not all(isinstance(k, int) for k in value.keys()):
            raise ValueError('Keys in params not valid.')
        if any(not (d.get('check') and d.get('close')) for d in value.values()):
            raise ValueError('"check" or "close" keys missing in params.')
        self._validate_check_values_ascending(value)
        self._params = value
