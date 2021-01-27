# Python standard.
import inspect
from typing import Dict

# Local.
from pagetpalace.src.instrument_attributes import InstrumentDecimalRatio, InstrumentLeverage, InstrumentTypes


class Instrument:

    def __init__(
            self,
            symbol: str,
            type_: str,
            leverage: int,
            decimal_ratio: float,
            price_precision: int,
            exchange_rate_data: dict,
    ):
        self.symbol = symbol
        self.base_currency = symbol.split('_')[0]
        self.type_ = type_
        self.leverage = leverage
        self.decimal_ratio = decimal_ratio
        self.price_precision = price_precision
        self.exchange_rate_data = exchange_rate_data if exchange_rate_data else {}

    def __str__(self):
        return ' - '.join(f'{k}: {v}' for k, v in self.__dict__.items())


class Currency(Instrument):
    def __init__(
            self,
            symbol: str,
            leverage: int,
            decimal_ratio: float,
            price_precision: int,
            exchange_rate_data: dict = None,
    ):
        super().__init__(
            symbol,
            InstrumentTypes.CURRENCY,
            leverage,
            decimal_ratio,
            price_precision,
            exchange_rate_data,
        )


class Commodity(Instrument):
    def __init__(self, symbol: str, leverage: int, price_precision: int, exchange_rate_data: dict = None):
        super().__init__(
            symbol,
            InstrumentTypes.COMMODITY,
            leverage,
            InstrumentDecimalRatio.COMMODITY,
            price_precision,
            exchange_rate_data,
        )


class Index(Instrument):
    def __init__(self, symbol: str, leverage: int, exchange_rate_data: dict = None):
        super().__init__(
            symbol,
            InstrumentTypes.INDEX,
            leverage,
            InstrumentDecimalRatio.INDEX,
            1,
            exchange_rate_data,
        )


class CurrencyPairs:
    EUR_GBP = Currency('EUR_GBP', InstrumentLeverage.CURRENCY, 1e4, 5)
    GBP_USD = Currency('GBP_USD', InstrumentLeverage.CURRENCY, 1e4, 5)


class CurrencyConversions:
    POUND_DOLLAR_CONVERSION = {'symbol': CurrencyPairs.GBP_USD.symbol, 'inverse_required': False}


class Commodities:
    BCO_USD = Commodity('BCO_USD', 10, 3, CurrencyConversions.POUND_DOLLAR_CONVERSION)
    GOLD = Commodity('XAU_USD', 20, 3, CurrencyConversions.POUND_DOLLAR_CONVERSION)


class Indices:
    IN50_USD = Index('IN50_USD', 10, CurrencyConversions.POUND_DOLLAR_CONVERSION)
    NAS100_USD = Index('NAS100_USD', InstrumentLeverage.INDEX, CurrencyConversions.POUND_DOLLAR_CONVERSION)
    SPX500_USD = Index('SPX500_USD', InstrumentLeverage.INDEX, CurrencyConversions.POUND_DOLLAR_CONVERSION)


def get_all_instruments() -> Dict[str, Instrument]:
    all_instruments = {}
    for instrument_class in [CurrencyPairs, Commodities, Indices]:
        class_attributes = inspect.getmembers(instrument_class, lambda a: not(inspect.isroutine(a)))
        for name, attribute in class_attributes:
            if not (name.startswith('__') and name.endswith('__')):
                all_instruments[name] = attribute

    return all_instruments
