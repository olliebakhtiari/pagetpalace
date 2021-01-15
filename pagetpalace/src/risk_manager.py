# Local.
from pagetpalace.src.instruments import Instrument
from pagetpalace.src.oanda.pricing import OandaPricingData
from pagetpalace.src.oanda.unit_conversions import UnitConversions
from pagetpalace.src.oanda.settings import LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER


class RiskManager:
    MAX_RISK_PCT = 0.15

    def __init__(self, instrument: Instrument):
        self.instrument = instrument
        self.current_max_risk_in_margin = None
        self._latest_exchange_rates = None
        if instrument.exchange_rate_data:
            self._oanda_pricing = OandaPricingData(LIVE_ACCESS_TOKEN, PRIMARY_ACCOUNT_NUMBER, 'LIVE_API')
            self._latest_exchange_rates = self._oanda_pricing.get_pricing_info(
                [self.instrument.exchange_rate_data['symbol']]
            )

    def _calculate_risk(self,
                        units: float,
                        entry_price: float,
                        stop_loss_amount: float) -> float:
        return UnitConversions(self.instrument, entry_price).calculate_pound_to_pip_ratio(units) \
               * (stop_loss_amount * self.instrument.decimal_ratio)

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
