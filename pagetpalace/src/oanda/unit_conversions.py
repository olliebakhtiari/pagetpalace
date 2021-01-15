# Python standard.
import math

# Local.
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.instrument_attributes import BaseCurrencies, InstrumentTypes
from pagetpalace.src.oanda.pricing import OandaPricingData
from pagetpalace.src.oanda.settings import LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER


class UnitConversions:
    _ACCOUNT_CURRENCY = BaseCurrencies.GBP
    _UNRESTRICTED_MARGIN_CAP = 0.9

    def __init__(self, instrument: Instrument, entry_price: float):
        self._pricing = OandaPricingData(LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER, 'LIVE_API')
        self.instrument = instrument
        self.entry_price = entry_price
        self._pound_to_units_variable = 0.
        self._pound_to_pip_variable = 0.
        self._get_formula_variables()

    def _get_latest_instrument_price(self, symbol: str, retry_count: int = 0) -> float:
        price = 0.
        latest_price = self._pricing.get_pricing_info([symbol], include_home_conversions=False)
        if not len(latest_price['prices']) and retry_count < 5:
            self._get_latest_instrument_price(symbol, retry_count=retry_count + 1)
        elif len(latest_price['prices']):
            price = float(latest_price['prices'][0]['asks'][0]['price'])
        else:
            raise Exception('Failed to get latest instrument price when calculating conversions.')

        return price

    def _get_formula_variables(self):
        if self.instrument.exchange_rate_data:
            exchange_rate_price = self._get_latest_instrument_price(self.instrument.exchange_rate_data['symbol'])
            if self.instrument.exchange_rate_data['inverse_required']:
                inverse_price = 1 / exchange_rate_price
                self._pound_to_units_variable = inverse_price
                self._pound_to_pip_variable = inverse_price
            else:
                self._pound_to_units_variable = self.entry_price / exchange_rate_price
                self._pound_to_pip_variable = exchange_rate_price
        elif self.instrument.type_ == InstrumentTypes.CURRENCY and self.instrument.base_currency == BaseCurrencies.GBP:
            self._pound_to_units_variable = 1.
            self._pound_to_pip_variable = self.entry_price
        elif self.instrument.symbol.split('_')[-1] == BaseCurrencies.GBP:
            self._pound_to_units_variable = self.entry_price
            self._pound_to_pip_variable = 1.
        else:
            raise Exception("Denominator scenario not accounted for.")

    def calculate_units(self, margin_size: float) -> float:
        return math.floor((margin_size * self.instrument.leverage) / self._pound_to_units_variable)

    def calculate_pound_to_pip_ratio(self, units: float) -> float:
        if self.instrument.symbol.split('_')[-1] == BaseCurrencies.GBP:
            p2p_ratio = (units * (1. / self.instrument.decimal_ratio)) / self._pound_to_pip_variable
        elif self.instrument.type_ == InstrumentTypes.CURRENCY and self.instrument.base_currency == BaseCurrencies.GBP:
            p2p_ratio = (units * (1. / self.instrument.decimal_ratio)) / self._pound_to_pip_variable
        else:
            p2p_ratio = (units * (1. / self.instrument.decimal_ratio)) / self._pound_to_pip_variable

        return round(p2p_ratio, 2)

    def _convert_units_to_gbp(self, units: int) -> float:
        return round((units * self._pound_to_units_variable) / self.instrument.leverage, 2)

    def _margin_not_being_used_in_orders(self, account_data: dict) -> float:
        units_pending = 0
        for order in account_data['orders']:
            units_in_order = order.get('units')
            if units_in_order:
                units_pending += abs(int(units_in_order))
        available = float(account_data['marginAvailable']) - self._convert_units_to_gbp(units_pending)

        return available if available > 0 else 0.

    @classmethod
    def _adjust_according_to_restricted_margin(cls, margin_size: float, available_minus_restricted: float) -> float:
        if (margin_size > available_minus_restricted) and (available_minus_restricted < 200):
            margin_size = 0
        elif (margin_size > available_minus_restricted) and (available_minus_restricted >= 200):
            margin_size = available_minus_restricted

        return margin_size

    def _get_valid_margin_size(self, account_data: dict, equity_split: float) -> float:
        balance = float(account_data['balance'])
        margin_size = (balance * self._UNRESTRICTED_MARGIN_CAP) / equity_split
        available_minus_restricted = self._margin_not_being_used_in_orders(account_data) \
                                     - (balance * (1 - self._UNRESTRICTED_MARGIN_CAP))

        return self._adjust_according_to_restricted_margin(margin_size, available_minus_restricted)

    def calculate_unit_size_of_trade(self, account_data: dict, equity_split: float) -> float:
        return self.calculate_units(self._get_valid_margin_size(account_data, equity_split))
