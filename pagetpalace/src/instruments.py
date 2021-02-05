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
            leverage: int = InstrumentLeverage.CURRENCY,
            decimal_ratio: float = 1e4,
            price_precision: int = 5,
            exchange_rate_data: dict = None,
    ):
        if symbol.split('_')[-1] == 'JPY':
            decimal_ratio = 1e2
            price_precision = 3
        super().__init__(
            symbol,
            InstrumentTypes.CURRENCY,
            leverage,
            decimal_ratio,
            price_precision,
            exchange_rate_data,
        )


class Commodity(Instrument):
    def __init__(
            self,
            symbol: str,
            leverage: int = InstrumentLeverage.COMMODITY,
            decimal_ratio: float = InstrumentDecimalRatio.COMMODITY,
            price_precision: int = 3,
            exchange_rate_data: dict = None,
    ):
        if not exchange_rate_data and symbol.split('_')[-1] == 'USD':
            exchange_rate_data = {'symbol': 'GBP_USD', 'inverse_required': False}
        super().__init__(
            symbol,
            InstrumentTypes.COMMODITY,
            leverage,
            decimal_ratio,
            price_precision,
            exchange_rate_data,
        )


class Index(Instrument):
    def __init__(
            self,
            symbol: str,
            leverage: int = InstrumentLeverage.INDEX,
            decimal_ratio: float = InstrumentDecimalRatio.INDEX,
            price_precision: int = 1,
            exchange_rate_data: dict = None,
    ):
        if not exchange_rate_data and symbol.split('_')[-1] == 'USD':
            exchange_rate_data = {'symbol': 'GBP_USD', 'inverse_required': False}
        super().__init__(
            symbol,
            InstrumentTypes.INDEX,
            leverage,
            decimal_ratio,
            price_precision,
            exchange_rate_data,
        )


class CurrencyPairs:
    AUD_JPY = Currency('AUD_JPY', leverage=20, exchange_rate_data={'symbol': 'GBP_AUD', 'inverse_required': True})
    AUD_USD = Currency('AUD_USD', leverage=20, exchange_rate_data={'symbol': 'GBP_AUD', 'inverse_required': True})
    CAD_CHF = Currency('CAD_CHF', leverage=25, exchange_rate_data={'symbol': 'GBP_CAD', 'inverse_required': True})
    EUR_GBP = Currency('EUR_GBP')
    EUR_JPY = Currency('EUR_JPY', exchange_rate_data={'symbol': 'EUR_GBP', 'inverse_required': False})
    EUR_USD = Currency('EUR_USD', exchange_rate_data={'symbol': 'EUR_GBP', 'inverse_required': False})
    GBP_USD = Currency('GBP_USD')
    USD_CAD = Currency('USD_CAD', exchange_rate_data={'symbol': 'GBP_USD', 'inverse_required': True})
    USD_CHF = Currency('USD_CHF', leverage=25, exchange_rate_data={'symbol': 'GBP_USD', 'inverse_required': True})


class Commodities:
    BCO_USD = Commodity('BCO_USD')
    GOLD_SILVER = Commodity('XAU_XAG', exchange_rate_data={'symbol': 'XAU_GBP', 'inverse_required': False})
    GOLD_USD = Commodity('XAU_USD', leverage=20)
    PLATINUM_USD = Commodity('XPT_USD')
    SUGAR_USD = Commodity('SUGAR_USD', decimal_ratio=1e4)


class Indices:
    IN50_USD = Index('IN50_USD', leverage=10)
    NAS100_USD = Index('NAS100_USD')
    SPX500_USD = Index('SPX500_USD')
    US30_USD = Index('US30_USD')


def get_all_instruments() -> Dict[str, Instrument]:
    all_instruments = {}
    for instrument_class in [CurrencyPairs, Commodities, Indices]:
        class_attributes = inspect.getmembers(instrument_class, lambda a: not(inspect.isroutine(a)))
        for name, attribute in class_attributes:
            if not (name.startswith('__') and name.endswith('__')):
                all_instruments[name] = attribute

    return all_instruments
