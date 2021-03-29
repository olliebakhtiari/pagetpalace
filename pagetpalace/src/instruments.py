# Python standard.
import inspect
from typing import Dict

# Local.
from pagetpalace.src.instrument_attributes import (
    InstrumentDecimalRatio,
    InstrumentLeverage,
    InstrumentTypes,
    InstrumentPricePrecision,
)


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
            decimal_ratio: float = InstrumentDecimalRatio.CURRENCY,
            price_precision: int = InstrumentPricePrecision.CURRENCY,
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
            price_precision: int = InstrumentPricePrecision.COMMODITY,
            exchange_rate_data: dict = None,
    ):
        if not exchange_rate_data and symbol.split('_')[-1] == 'USD':
            exchange_rate_data = {'p2p': {'symbol': 'GBP_USD', 'inverse_required': False}}
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
            price_precision: int = InstrumentPricePrecision.INDEX,
            exchange_rate_data: dict = None,
    ):
        if not exchange_rate_data and symbol.split('_')[-1] == 'USD':
            exchange_rate_data = {'p2p': {'symbol': 'GBP_USD', 'inverse_required': False}}
        super().__init__(
            symbol,
            InstrumentTypes.INDEX,
            leverage,
            decimal_ratio,
            price_precision,
            exchange_rate_data,
        )


class CurrencyPairs:
    AUD_JPY = Currency(
        'AUD_JPY',
        leverage=20,
        exchange_rate_data={
            'units': {'symbol': 'GBP_AUD', 'inverse_required': True},
            'p2p': {'symbol': 'GBP_JPY', 'inverse_required': False},
        }
    )
    AUD_NZD = Currency(
        'AUD_NZD',
        leverage=20,
        exchange_rate_data={
            'units': {'symbol': 'GBP_AUD', 'inverse_required': True},
            'p2p': {'symbol': 'GBP_NZD', 'inverse_required': False},
        }
    )
    AUD_USD = Currency(
        'AUD_USD',
        leverage=20,
        exchange_rate_data={
            'units': {'symbol': 'GBP_AUD', 'inverse_required': True},
            'p2p': {'symbol': 'GBP_USD', 'inverse_required': False},
        }
    )
    CAD_CHF = Currency(
        'CAD_CHF',
        leverage=25,
        exchange_rate_data={
            'units': {'symbol': 'GBP_CAD', 'inverse_required': True},
            'p2p': {'symbol': 'GBP_CHF', 'inverse_required': False},
        }
    )
    CAD_JPY = Currency(
        'CAD_JPY',
        exchange_rate_data={
            'units': {'symbol': 'GBP_CAD', 'inverse_required': True},
            'p2p': {'symbol': 'GBP_JPY', 'inverse_required': False},
        }
    )
    CHF_JPY = Currency(
        'CHF_JPY',
        leverage=25,
        exchange_rate_data={
            'units': {'symbol': 'GBP_CHF', 'inverse_required': True},
            'p2p': {'symbol': 'GBP_JPY', 'inverse_required': False},
        }
    )
    EUR_GBP = Currency('EUR_GBP')
    EUR_JPY = Currency(
        'EUR_JPY',
        exchange_rate_data={
            'units': {'symbol': 'EUR_GBP', 'inverse_required': False},
            'p2p': {'symbol': 'GBP_JPY', 'inverse_required': False},
        }
    )
    EUR_USD = Currency(
        'EUR_USD',
        exchange_rate_data={
            'units': {'symbol': 'EUR_GBP', 'inverse_required': False},
            'p2p': {'symbol': 'GBP_USD', 'inverse_required': False},
        }
    )
    GBP_CHF = Currency('GBP_CHF', leverage=25)
    GBP_JPY = Currency('GBP_JPY')
    GBP_USD = Currency('GBP_USD')
    USD_CAD = Currency(
        'USD_CAD',
        exchange_rate_data={
            'units': {'symbol': 'GBP_USD', 'inverse_required': True},
            'p2p': {'symbol': 'GBP_CAD', 'inverse_required': False},
        }
    )
    USD_CHF = Currency(
        'USD_CHF',
        leverage=25,
        exchange_rate_data={
            'units': {'symbol': 'GBP_USD', 'inverse_required': True},
            'p2p': {'symbol': 'GBP_CHF', 'inverse_required': False},
        }
    )


class Commodities:
    BCO_USD = Commodity('BCO_USD')
    CORN_USD = Commodity('CORN_USD')
    GOLD_SILVER = Commodity(
        'XAU_XAG',
        exchange_rate_data={
            'units': {'symbol': 'XAU_GBP', 'inverse_required': False},
            'p2p': {'symbol': 'XAG_GBP', 'inverse_required': True},
        }
    )
    GOLD_USD = Commodity('XAU_USD', leverage=20)
    NATGAS_USD = Commodity('NATGAS_USD')
    PALLADIUM_USD = Commodity('XPD_USD')
    PLATINUM_USD = Commodity('XPT_USD')
    SILVER_CHF = Commodity(
        'XAG_CHF',
        decimal_ratio=1e4,
        price_precision=5,
        exchange_rate_data={
            'units': {'symbol': 'XAG_GBP', 'inverse_required': False},
            'p2p': {'symbol': 'GBP_CHF', 'inverse_required': False},
        }
    )
    SILVER_GBP = Commodity('XAG_GBP', decimal_ratio=1e4, price_precision=5)
    SUGAR_USD = Commodity('SUGAR_USD', decimal_ratio=1e4, price_precision=5)


class Indices:
    CN50_USD = Index('CN50_USD', leverage=10)
    DE30_EUR = Index('DE30_EUR', exchange_rate_data={'p2p': {'symbol': 'EUR_GBP', 'inverse_required': True}})
    HK33_HKD = Index(
        'HK33_HKD',
        leverage=10,
        exchange_rate_data={'p2p': {'symbol': 'GBP_HKD', 'inverse_required': False}},
    )
    IN50_USD = Index('IN50_USD', leverage=10)
    JP225_USD = Index('JP225_USD')
    NAS100_USD = Index('NAS100_USD')
    SPX500_USD = Index('SPX500_USD')
    TWIX_USD = Index('TWIX_USD', leverage=10)
    UK100_GBP = Index('UK100_GBP')
    US2000_USD = Index('US2000_USD', leverage=10)
    US30_USD = Index('US30_USD')


def get_all_instruments() -> Dict[str, Instrument]:
    all_instruments = {}
    for instrument_class in [CurrencyPairs, Commodities, Indices]:
        class_attributes = inspect.getmembers(instrument_class, lambda a: not(inspect.isroutine(a)))
        for name, attribute in class_attributes:
            if not (name.startswith('__') and name.endswith('__')):
                all_instruments[name] = attribute

    return all_instruments
