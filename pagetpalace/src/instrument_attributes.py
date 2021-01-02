class BaseCurrencies:
    EUR = 'EUR'
    GBP = 'GBP'
    USD = 'USD'


class InstrumentTypes:
    COMMODITY = 'COMMODITY'
    CURRENCY = 'CURRENCY'
    INDEX = 'INDEX'


class InstrumentLeverage:
    COMMODITY = 10
    CURRENCY = 30
    INDEX = 20


class InstrumentDecimalRatio:
    COMMODITY = 1e2
    CURRENCY = 1e4
    INDEX = 1
