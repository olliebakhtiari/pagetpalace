# Local.
from src.oanda_account import OandaAccount


class OandaPricingData(OandaAccount):

    def __init__(self, access_token: str, account_id: str, account_type: str):
        super().__init__(access_token, account_id, account_type)

    def get_latest_candles(self,
                           candle_specifications: str,
                           units: float = 1,
                           smooth: bool = False,
                           daily_alignment: int = 22,
                           alignment_timezone: str = 'Europe/London',
                           weekly_alignment: str = 'Sunday') -> dict:
        """ Get dancing bears and most recently completed candles within an Account for specified combinations of
            instrument, granularity and price component.

            candle_specifications: A string containing the following, all delimited by “:” characters:
                                   1) InstrumentName
                                   2) CandlestickGranularity
                                   3) PricingComponent e.g. EUR_USD:S10:BM
        """
        params = {
            "candleSpecifications": candle_specifications,
            "units": units,
            "smooth": smooth,
            "dailyAlignment": daily_alignment,
            "alignmentTimezone": alignment_timezone,
            "weeklyAlignment": weekly_alignment,
        }

        return self._request(endpoint='candles/latest', params=params)

    def get_pricing_info(self) -> dict:
        """ Get pricing information for a specified list of instruments within an Account. """

        return self._request(endpoint='pricing')

