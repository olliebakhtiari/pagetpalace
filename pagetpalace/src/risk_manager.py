# Local.
from pagetpalace.src.instruments import Instrument, InstrumentTypes
from pagetpalace.src.instrument_attributes import BaseCurrencies
from pagetpalace.src.oanda.pricing import OandaPricingData
from pagetpalace.src.oanda.settings import DEMO_ACCESS_TOKEN, DEMO_ACCOUNT_NUMBER


class RiskManager:
    MAX_RISK_PCT = 0.15

    def __init__(self, instrument: Instrument):
        self.instrument = instrument
        self.current_max_risk_in_margin = None
        self._latest_exchange_rates = None
        if instrument.exchange_rate_pair:
            self._oanda_pricing = OandaPricingData(DEMO_ACCESS_TOKEN, DEMO_ACCOUNT_NUMBER, 'DEMO_API')
            self._latest_exchange_rates = self._oanda_pricing.get_pricing_info([self.instrument.exchange_rate_pair])

    def _get_denominator(self, entry_price: float):
        if self.instrument.exchange_rate_pair:
            denominator = float(self._latest_exchange_rates['prices'][0]['asks'][0]['price'])
        elif self.instrument.type_ == InstrumentTypes.CURRENCY and self.instrument.base_currency == BaseCurrencies.GBP:
            denominator = entry_price
        else:
            denominator = 1.

        return denominator

    def _calculate_risk(self,
                        units: float,
                        entry_price: float,
                        stop_loss_amount: float) -> float:
        pound_to_pip_ratio = units * ((1 / self.instrument.decimal_ratio) / self._get_denominator(entry_price))

        return pound_to_pip_ratio * (stop_loss_amount * self.instrument.decimal_ratio)

    def _is_more_than_max_risk(self, trade_risk: float, current_balance: float) -> bool:
        self.current_max_risk_in_margin = current_balance * self.MAX_RISK_PCT

        return trade_risk > self.current_max_risk_in_margin

    def _adjust_risk(self, units: float, trade_risk: float) -> float:
        return units / (trade_risk / self.current_max_risk_in_margin)

    def calculate_unit_size_within_max_risk(self,
                                            current_balance: float,
                                            units: float,
                                            entry_price: float,
                                            stop_loss_amount: float) -> float:
        trade_risk = self._calculate_risk(units, entry_price, stop_loss_amount)
        is_too_high_risk = self._is_more_than_max_risk(trade_risk, current_balance)

        return self._adjust_risk(units, trade_risk) if is_too_high_risk else units
