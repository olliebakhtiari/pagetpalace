class BaseCurrencies:
    AUD = 'AUD'
    EUR = 'EUR'
    GBP = 'GBP'
    NZD = 'NZD'
    USD = 'USD'


class InstrumentTypes:
    BOND = 'BOND'
    COMMODITY = 'COMMODITY'
    CURRENCY = 'CURRENCY'
    INDEX = 'INDEX'


class InstrumentLeverage:
    BOND = 5
    COMMODITY = 10
    CURRENCY = 30
    INDEX = 20


class InstrumentDecimalRatio:
    BOND = 1e2
    COMMODITY = 1e2
    CURRENCY = 1e4
    INDEX = 1
