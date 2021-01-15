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
    def __init__(self, symbol: str, price_precision: int, exchange_rate_data: dict = None):
        super().__init__(
            symbol,
            InstrumentTypes.COMMODITY,
            InstrumentLeverage.COMMODITY,
            InstrumentDecimalRatio.COMMODITY,
            price_precision,
            exchange_rate_data,
        )


class Index(Instrument):
    def __init__(self, symbol: str, exchange_rate_data: dict = None):
        super().__init__(
            symbol,
            InstrumentTypes.INDEX,
            InstrumentLeverage.INDEX,
            InstrumentDecimalRatio.INDEX,
            1,
            exchange_rate_data,
        )


class CurrencyPairs:
    EUR_GBP = Currency('EUR_GBP', InstrumentLeverage.CURRENCY, 1e4, 5)
    GBP_USD = Currency('GBP_USD', InstrumentLeverage.CURRENCY, 1e4, 5)


class Commodities:
    BCO_USD = Commodity('BCO_USD', 3, {'symbol': CurrencyPairs.GBP_USD.symbol, 'inverse_required': False})


class Indices:
    NAS100_USD = Index('NAS100_USD', {'symbol': CurrencyPairs.GBP_USD.symbol, 'inverse_required': False})
    SPX500_USD = Index('SPX500_USD', {'symbol': CurrencyPairs.GBP_USD.symbol, 'inverse_required': False})
