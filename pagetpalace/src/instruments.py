# Local.
from pagetpalace.src.instrument_attributes import InstrumentDecimalRatio, InstrumentLeverage, InstrumentTypes


class Instrument:

    def __init__(self, symbol: str, type_: str, leverage: int, decimal_ratio: float, exchange_rate_pair: str):
        self.symbol = symbol
        self.base_currency = symbol.split('_')[0]
        self.type_ = type_
        self.leverage = leverage
        self.decimal_ratio = decimal_ratio
        self.exchange_rate_pair = exchange_rate_pair


class Currency(Instrument):
    def __init__(self, symbol: str, exchange_rate_pair: str = None):
        super().__init__(
            symbol,
            InstrumentTypes.CURRENCY,
            InstrumentLeverage.CURRENCY,
            InstrumentDecimalRatio.CURRENCY,
            exchange_rate_pair,
        )


class Commodity(Instrument):
    def __init__(self, symbol: str, exchange_rate_pair: str = None):
        super().__init__(
            symbol,
            InstrumentTypes.COMMODITY,
            InstrumentLeverage.COMMODITY,
            InstrumentDecimalRatio.COMMODITY,
            exchange_rate_pair,
        )


class Index(Instrument):
    def __init__(self, symbol: str, exchange_rate_pair: str = None):
        super().__init__(
            symbol,
            InstrumentTypes.INDEX,
            InstrumentLeverage.INDEX,
            InstrumentDecimalRatio.INDEX,
            exchange_rate_pair,
        )


class CurrencyPairs:
    EUR_GBP = Currency('EUR_GBP')
    EUR_USD = Currency('EUR_USD')
    GBP_USD = Currency('GBP_USD')


class Commodities:
    BCO_USD = Commodity('BCO_USD', CurrencyPairs.GBP_USD.symbol)


class Indices:
    IN50_USD = Index('IN50_USD')
    NAS100_USD = Index('NAS100_USD', CurrencyPairs.GBP_USD.symbol)
    SPX500_USD = Index('SPX500_USD', CurrencyPairs.GBP_USD.symbol)
